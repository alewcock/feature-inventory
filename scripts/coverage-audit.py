#!/usr/bin/env python3
"""
Coverage audit script for feature-inventory plugin.

Enumerates ALL source files from the filesystem (not from plan.json file lists),
checks coverage in raw/ and details/ using filename-qualified grep, applies
proportionality thresholds, and outputs a structured gap report.

Exits 0 if no gaps, 1 if gaps found.
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Source file extensions to include
SOURCE_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".py", ".rb", ".cs", ".java", ".go",
    ".vue", ".svelte", ".php", ".razor", ".cpp", ".c", ".h", ".sql",
}

# Directories always excluded
DEFAULT_EXCLUDE_DIRS = {
    "node_modules", ".git", "dist", "build", "vendor", "__pycache__",
    "bin", "obj", "packages", "x64", "Debug", "Release", ".parcel-cache",
}

# Minimum source lines to audit (files below this are skipped)
MIN_SOURCE_LINES = 100


def parse_args():
    parser = argparse.ArgumentParser(description="Feature inventory coverage audit")
    parser.add_argument("--plan", required=True, help="Path to plan.json")
    parser.add_argument("--raw-dir", required=True, help="Path to raw/ output directory")
    parser.add_argument("--details-dir", required=True, help="Path to details/ output directory")
    parser.add_argument("--output", required=True, help="Path to write coverage-audit.json")
    parser.add_argument(
        "--exclude-patterns",
        nargs="*",
        default=[],
        help="Additional exclude patterns (beyond plan.json)",
    )
    return parser.parse_args()


def load_plan(plan_path):
    with open(plan_path, "r") as f:
        return json.load(f)


def count_lines(file_path):
    """Count non-empty lines in a file."""
    try:
        with open(file_path, "r", errors="replace") as f:
            return sum(1 for line in f)
    except (OSError, UnicodeDecodeError):
        return 0


def should_exclude(file_path, exclude_patterns):
    """Check if a file path matches any exclude pattern."""
    path_str = str(file_path)
    # Check default excluded directories
    parts = Path(file_path).parts
    for part in parts:
        if part in DEFAULT_EXCLUDE_DIRS:
            return True
    # Check custom exclude patterns
    for pattern in exclude_patterns:
        if pattern in path_str:
            return True
    return False


def enumerate_source_files(repo_path, exclude_patterns):
    """Walk the filesystem and find all source files, with line counts."""
    source_files = []
    repo_path = Path(repo_path).resolve()

    for root, dirs, files in os.walk(repo_path):
        # Prune excluded directories in-place for efficiency
        dirs[:] = [
            d for d in dirs
            if d not in DEFAULT_EXCLUDE_DIRS
            and not should_exclude(os.path.join(root, d), exclude_patterns)
        ]

        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in SOURCE_EXTENSIONS:
                continue

            full_path = os.path.join(root, fname)
            if should_exclude(full_path, exclude_patterns):
                continue

            line_count = count_lines(full_path)
            if line_count > MIN_SOURCE_LINES:
                rel_path = os.path.relpath(full_path, repo_path)
                source_files.append({
                    "file": rel_path,
                    "abs_path": full_path,
                    "source_lines": line_count,
                    "repo_path": str(repo_path),
                })

    return source_files


def count_references_in_dir(directory, filename, filename_no_ext):
    """
    Count lines in markdown files within a directory that reference a source file
    using filename-qualified patterns (not bare basename substrings).

    Returns the number of matching lines.
    """
    if not os.path.isdir(directory):
        return 0

    # Build patterns that reduce false positives:
    # 1. Full filename with extension: "programs.js"
    # 2. Path segment patterns: "/programs." or "/programs.js"
    patterns = [
        re.compile(re.escape(filename)),                           # e.g. "programs.js"
        re.compile(r"[/\\]" + re.escape(filename_no_ext) + r"\."),  # e.g. "/programs."
    ]

    total_lines = 0

    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="replace") as f:
                    for line in f:
                        for pattern in patterns:
                            if pattern.search(line):
                                total_lines += 1
                                break  # count the line once even if multiple patterns match
            except OSError:
                continue

    return total_lines


def check_coverage(source_file, raw_dir, details_dir, repo_name):
    """
    Check coverage for a single source file across BOTH raw/{repo}/ AND details/.
    Returns (analysis_lines, required_lines, status).
    """
    filename = os.path.basename(source_file["file"])
    filename_no_ext = Path(filename).stem
    source_lines = source_file["source_lines"]

    # Search in raw/{repo}/ for this file's own repo
    repo_raw_dir = os.path.join(raw_dir, repo_name)
    raw_lines = count_references_in_dir(repo_raw_dir, filename, filename_no_ext)

    # Also search in details/ (cross-references from all repos)
    details_lines = count_references_in_dir(details_dir, filename, filename_no_ext)

    # Total analysis coverage from both sources
    analysis_lines = raw_lines + details_lines

    # Proportionality threshold
    required_lines = math.ceil(source_lines / 50)

    if analysis_lines == 0:
        status = "MISSING"
    elif analysis_lines < required_lines:
        status = "SHALLOW"
    else:
        status = "ADEQUATE"

    return analysis_lines, required_lines, status


def classify_gap(source_file, status):
    """Classify a gap by severity for triage."""
    source_lines = source_file["source_lines"]
    filename = os.path.basename(source_file["file"])

    # Test file detection
    test_patterns = [
        r"Tests?\.cs$", r"Tests?\.js$", r"Tests?\.ts$", r"Tests?\.tsx$",
        r"\.test\.(js|ts|tsx|jsx)$", r"\.spec\.(js|ts|tsx|jsx)$",
        r"test_.*\.py$", r".*_test\.py$", r".*_test\.go$",
    ]
    is_test = any(re.search(p, filename) for p in test_patterns)

    if is_test:
        return "TEST"
    elif source_lines > 500 and status in ("MISSING", "SHALLOW"):
        return "CRITICAL"
    elif source_lines > 200 and status in ("MISSING", "SHALLOW"):
        return "IMPORTANT"
    else:
        return "MINOR"


def run_audit(plan, raw_dir, details_dir, extra_exclude_patterns):
    """Run the full coverage audit across all repos in the plan."""
    # Collect exclude patterns from plan.json + CLI args
    exclude_patterns = list(extra_exclude_patterns)
    if "exclude_patterns" in plan:
        exclude_patterns.extend(plan["exclude_patterns"])

    all_source_files = []
    total_source_files = 0
    total_source_lines = 0

    # Enumerate source files from each repo's filesystem
    for repo in plan.get("repos", []):
        repo_path = repo["path"]
        repo_name = repo["name"]

        if not os.path.isdir(repo_path):
            print(f"WARNING: repo path does not exist: {repo_path}", file=sys.stderr)
            continue

        files = enumerate_source_files(repo_path, exclude_patterns)
        for f in files:
            f["repo_name"] = repo_name
        all_source_files.extend(files)

    total_source_files = len(all_source_files)
    total_source_lines = sum(f["source_lines"] for f in all_source_files)

    # Check coverage for each file
    coverage = {"adequate": 0, "shallow": 0, "missing": 0}
    gaps = []

    for sf in all_source_files:
        analysis_lines, required_lines, status = check_coverage(
            sf, raw_dir, details_dir, sf["repo_name"]
        )

        if status == "ADEQUATE":
            coverage["adequate"] += 1
        else:
            bucket = status.lower()
            coverage[bucket] = coverage.get(bucket, 0) + 1
            severity = classify_gap(sf, status)
            gaps.append({
                "file": sf["file"],
                "repo": sf["repo_name"],
                "source_lines": sf["source_lines"],
                "analysis_lines": analysis_lines,
                "required_lines": required_lines,
                "status": status,
                "severity": severity,
            })

    # Sort gaps: CRITICAL first, then IMPORTANT, then MINOR, then TEST
    severity_order = {"CRITICAL": 0, "IMPORTANT": 1, "MINOR": 2, "TEST": 3}
    gaps.sort(key=lambda g: (severity_order.get(g["severity"], 99), -g["source_lines"]))

    # Build triage summary
    triage = {}
    for g in gaps:
        sev = g["severity"]
        if sev not in triage:
            triage[sev] = {"count": 0, "total_lines": 0}
        triage[sev]["count"] += 1
        triage[sev]["total_lines"] += g["source_lines"]

    result = {
        "audit_date": datetime.now(timezone.utc).isoformat(),
        "total_source_files": total_source_files,
        "total_source_lines": total_source_lines,
        "files_over_100_lines": total_source_files,  # all enumerated files are >100
        "coverage": coverage,
        "triage": triage,
        "gaps": gaps,
    }

    return result


def main():
    args = parse_args()

    plan = load_plan(args.plan)
    result = run_audit(plan, args.raw_dir, args.details_dir, args.exclude_patterns or [])

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    # Print summary to stderr for the orchestrator
    total = result["total_source_files"]
    adequate = result["coverage"]["adequate"]
    gap_count = len(result["gaps"])

    print(f"\nSource Coverage Audit", file=sys.stderr)
    print(f"=====================", file=sys.stderr)
    print(f"Total source files (>100 lines): {total} ({result['total_source_lines']} lines)", file=sys.stderr)
    print(f"Coverage: {adequate}/{total} files adequately analyzed", file=sys.stderr)
    print(f"Gaps found: {gap_count}", file=sys.stderr)

    if result["triage"]:
        print(f"\nGap Triage:", file=sys.stderr)
        for sev in ["CRITICAL", "IMPORTANT", "MINOR", "TEST"]:
            if sev in result["triage"]:
                t = result["triage"][sev]
                print(f"  {sev:10s}: {t['count']} files ({t['total_lines']} lines)", file=sys.stderr)

    # Exit code: 0 if no gaps, 1 if gaps found
    sys.exit(0 if gap_count == 0 else 1)


if __name__ == "__main__":
    main()
