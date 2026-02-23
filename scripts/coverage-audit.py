#!/usr/bin/env python3
"""
Coverage audit for feature-inventory plugin.

Two-layer structural audit:

Layer 1 (Element Coverage):
  Extracts named code elements (functions, classes, routes, handlers, etc.) from
  every source file using language-aware regex. Checks whether each element is
  referenced in the raw/ and details/ analysis output. Reports per-element coverage
  instead of proportional line counts.

Layer 2 (Shared Element Detection):
  Identifies elements defined in one file but referenced from multiple distinct
  source files. These are shared infrastructure (utilities, services, core functions)
  that serve multiple user-facing purposes. Outputs them for the purpose-auditor
  agent to verify that each calling context is represented as a distinct feature
  in the synthesis output.

Exits 0 if no gaps, 1 if gaps found.
"""

import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".py", ".rb", ".cs", ".java", ".go",
    ".vue", ".svelte", ".php", ".razor", ".cpp", ".c", ".h", ".sql",
}

DEFAULT_EXCLUDE_DIRS = {
    "node_modules", ".git", "dist", "build", "vendor", "__pycache__",
    "bin", "obj", "packages", "x64", "Debug", "Release", ".parcel-cache",
}

# Elements with these names are too generic to track individually.
# They'll match everywhere and produce false coverage signals.
SKIP_ELEMENT_NAMES = {
    # Lifecycle / framework boilerplate
    "constructor", "__init__", "__del__", "__str__", "__repr__", "__eq__",
    "__hash__", "__len__", "__iter__", "__next__", "__enter__", "__exit__",
    "__getattr__", "__setattr__", "__getitem__", "__setitem__",
    "toString", "hashCode", "equals", "dispose", "finalize", "clone",
    "init", "setup", "teardown", "configure", "register",
    # Accessors
    "get", "set", "getter", "setter",
    # Framework methods
    "render", "mount", "unmount", "update", "destroy",
    "componentDidMount", "componentWillUnmount", "componentDidUpdate",
    "ngOnInit", "ngOnDestroy", "ngOnChanges",
    "created", "mounted", "updated", "destroyed", "beforeCreate",
    "beforeMount", "beforeUpdate", "beforeDestroy",
    # Entry points
    "main", "run", "start", "stop", "execute",
    # Testing
    "test", "it", "describe", "beforeEach", "afterEach", "beforeAll",
    "afterAll", "setUp", "tearDown",
    # Serialization
    "toJSON", "fromJSON", "serialize", "deserialize", "parse", "stringify",
    "toDict", "from_dict", "to_dict",
    # Common CRUD that need context to be meaningful
    "index", "show", "new", "edit", "create", "store", "delete", "remove",
}

# Minimum characters for an element name to be tracked
MIN_ELEMENT_NAME_LENGTH = 3

# Elements must be referenced from this many distinct files (beyond their
# definition file) to be flagged as shared infrastructure for Layer 2.
SHARED_ELEMENT_MIN_CALLERS = 2

# Coverage thresholds
ADEQUATE_COVERAGE_PCT = 60  # >= 60% of elements covered = ADEQUATE
SHALLOW_COVERAGE_PCT = 1    # > 0% but < 60% = SHALLOW, 0% = MISSING

# ---------------------------------------------------------------------------
# Element extraction patterns by language family
# ---------------------------------------------------------------------------

# Each pattern is (compiled_regex, element_type).
# The regex must have exactly one capturing group for the element name.

def _build_patterns():
    """Build language-family → pattern list mapping."""
    patterns = {}

    # --- JavaScript / TypeScript / JSX / TSX ---
    js_ts = [
        # function declarations: function foo(
        (re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\('), "function"),
        # arrow / function expression: const foo = (...) => / const foo = function
        (re.compile(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)\s*=>|function\b)'), "function"),
        # class declarations
        (re.compile(r'(?:export\s+)?class\s+(\w+)'), "class"),
        # method definitions in classes/objects: foo( or async foo(
        (re.compile(r'^\s+(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{', re.MULTILINE), "method"),
        # Express/Koa/Hapi routes: app.get('/path' or router.post('/path'
        (re.compile(r'(?:app|router)\.\w+\s*\(\s*[\'"]([^\'"]+)'), "route"),
        # React component (function): export default function Foo
        (re.compile(r'export\s+default\s+function\s+(\w+)'), "component"),
    ]
    for ext in (".js", ".jsx", ".ts", ".tsx"):
        patterns[ext] = js_ts

    # --- Vue (script block uses JS/TS patterns) ---
    patterns[".vue"] = js_ts[:]
    # --- Svelte (script block uses JS/TS patterns) ---
    patterns[".svelte"] = js_ts[:]

    # --- Python ---
    py = [
        (re.compile(r'^\s*def\s+(\w+)\s*\(', re.MULTILINE), "function"),
        (re.compile(r'^\s*class\s+(\w+)', re.MULTILINE), "class"),
        # Flask/FastAPI routes
        (re.compile(r'@\w+\.(?:route|get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)'), "route"),
    ]
    patterns[".py"] = py

    # --- Ruby ---
    rb = [
        (re.compile(r'^\s*def\s+(\w+)', re.MULTILINE), "function"),
        (re.compile(r'^\s*class\s+(\w+)', re.MULTILINE), "class"),
        (re.compile(r'^\s*module\s+(\w+)', re.MULTILINE), "module"),
        # Rails routes
        (re.compile(r'(?:get|post|put|patch|delete)\s+[\'"]([^\'"]+)'), "route"),
    ]
    patterns[".rb"] = rb

    # --- C# ---
    cs = [
        # Methods: public async Task<Foo> BarMethod(
        (re.compile(r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?(?:override\s+)?(?:virtual\s+)?\S+\s+(\w+)\s*\('), "method"),
        (re.compile(r'^\s*class\s+(\w+)', re.MULTILINE), "class"),
        (re.compile(r'^\s*interface\s+(\w+)', re.MULTILINE), "interface"),
        (re.compile(r'^\s*enum\s+(\w+)', re.MULTILINE), "enum"),
        # ASP.NET routes
        (re.compile(r'\[(?:Http(?:Get|Post|Put|Delete|Patch)|Route)\s*\(\s*"([^"]+)'), "route"),
    ]
    patterns[".cs"] = cs
    patterns[".razor"] = cs

    # --- Java ---
    java = [
        (re.compile(r'(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?\S+\s+(\w+)\s*\('), "method"),
        (re.compile(r'^\s*(?:public\s+)?class\s+(\w+)', re.MULTILINE), "class"),
        (re.compile(r'^\s*(?:public\s+)?interface\s+(\w+)', re.MULTILINE), "interface"),
        (re.compile(r'^\s*(?:public\s+)?enum\s+(\w+)', re.MULTILINE), "enum"),
        # Spring routes
        (re.compile(r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:value\s*=\s*)?[\'"]([^\'"]+)'), "route"),
    ]
    patterns[".java"] = java

    # --- Go ---
    go = [
        # func FooBar(
        (re.compile(r'^func\s+(\w+)\s*\(', re.MULTILINE), "function"),
        # func (r *Receiver) FooBar(
        (re.compile(r'^func\s+\([^)]+\)\s+(\w+)\s*\(', re.MULTILINE), "method"),
        (re.compile(r'^\s*type\s+(\w+)\s+struct', re.MULTILINE), "struct"),
        (re.compile(r'^\s*type\s+(\w+)\s+interface', re.MULTILINE), "interface"),
    ]
    patterns[".go"] = go

    # --- PHP ---
    php = [
        (re.compile(r'(?:public|private|protected)?\s*(?:static\s+)?function\s+(\w+)\s*\('), "function"),
        (re.compile(r'^\s*class\s+(\w+)', re.MULTILINE), "class"),
        (re.compile(r'^\s*interface\s+(\w+)', re.MULTILINE), "interface"),
    ]
    patterns[".php"] = php

    # --- C / C++ ---
    c_cpp = [
        # Function definitions (heuristic: type name( at start of line)
        (re.compile(r'^(?:\w+[\s*]+)+(\w+)\s*\([^)]*\)\s*\{', re.MULTILINE), "function"),
        (re.compile(r'^\s*class\s+(\w+)', re.MULTILINE), "class"),
        (re.compile(r'^\s*struct\s+(\w+)', re.MULTILINE), "struct"),
        (re.compile(r'^\s*enum\s+(?:class\s+)?(\w+)', re.MULTILINE), "enum"),
        (re.compile(r'^\s*namespace\s+(\w+)', re.MULTILINE), "namespace"),
    ]
    for ext in (".c", ".cpp", ".h"):
        patterns[ext] = c_cpp

    # --- SQL ---
    sql = [
        (re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:\w+\.)?(\w+)', re.IGNORECASE), "table"),
        (re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+(?:\w+\.)?(\w+)', re.IGNORECASE), "function"),
        (re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(?:\w+\.)?(\w+)', re.IGNORECASE), "trigger"),
    ]
    patterns[".sql"] = sql

    return patterns


ELEMENT_PATTERNS = _build_patterns()


# ---------------------------------------------------------------------------
# Element extraction
# ---------------------------------------------------------------------------

def extract_elements(file_path, extension):
    """
    Extract named code elements from a source file.
    Returns list of dicts: {name, type, line_number}.
    """
    patterns = ELEMENT_PATTERNS.get(extension, [])
    if not patterns:
        return []

    try:
        with open(file_path, "r", errors="replace") as f:
            content = f.read()
    except OSError:
        return []

    elements = []
    seen_names = set()

    for pattern, elem_type in patterns:
        for match in pattern.finditer(content):
            name = match.group(1)
            if not name or len(name) < MIN_ELEMENT_NAME_LENGTH:
                continue
            if name.lower() in SKIP_ELEMENT_NAMES:
                continue
            if name in seen_names:
                continue
            seen_names.add(name)

            # Calculate line number
            line_num = content[:match.start()].count("\n") + 1

            elements.append({
                "name": name,
                "type": elem_type,
                "line": line_num,
            })

    return elements


# ---------------------------------------------------------------------------
# Analysis index
# ---------------------------------------------------------------------------

class AnalysisIndex:
    """
    Builds an in-memory index of all identifiers found in analysis output
    (.md files in raw/ and details/). Allows fast lookup of whether an
    element name appears in the analysis.
    """

    def __init__(self):
        # element_name → set of analysis file paths that mention it
        self._index = defaultdict(set)
        # For filename-level fallback: filename → set of analysis files
        self._filename_index = defaultdict(set)
        self._built = False

    def build(self, *directories):
        """Walk directories, read all .md files, extract identifiers."""
        identifier_re = re.compile(r'\b([A-Za-z_]\w{2,})\b')

        for directory in directories:
            if not os.path.isdir(directory):
                continue
            for root, _dirs, files in os.walk(directory):
                for fname in files:
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", errors="replace") as f:
                            for line in f:
                                for m in identifier_re.finditer(line):
                                    ident = m.group(1)
                                    self._index[ident].add(fpath)
                                # Also index filenames mentioned in analysis
                                # Match patterns like "foo.js", "bar.py", etc.
                                for fm in re.finditer(r'(\w+\.\w+)', line):
                                    self._filename_index[fm.group(1)].add(fpath)
                    except OSError:
                        continue

        self._built = True

    def is_element_covered(self, element_name):
        """Check if an element name appears anywhere in the analysis."""
        return element_name in self._index and len(self._index[element_name]) > 0

    def is_filename_mentioned(self, filename):
        """Check if a source filename appears anywhere in the analysis."""
        return filename in self._filename_index and len(self._filename_index[filename]) > 0

    def element_locations(self, element_name):
        """Return set of analysis files that mention this element."""
        return self._index.get(element_name, set())


# ---------------------------------------------------------------------------
# Shared element detection
# ---------------------------------------------------------------------------

def build_codebase_identifier_index(source_files):
    """
    For every source file, extract all identifier-like tokens. Returns a dict:
    identifier → set of file paths that contain it.

    Used to find elements referenced from multiple files (shared infrastructure).
    """
    identifier_re = re.compile(r'\b([A-Za-z_]\w{2,})\b')
    index = defaultdict(set)

    for sf in source_files:
        fpath = sf["abs_path"]
        try:
            with open(fpath, "r", errors="replace") as f:
                for line in f:
                    for m in identifier_re.finditer(line):
                        index[m.group(1)].add(sf["file"])
        except OSError:
            continue

    return index


def detect_shared_elements(all_elements_by_file, codebase_index):
    """
    Identify elements that are defined in one file but referenced from multiple
    other files. These are shared infrastructure candidates for the purpose audit.

    Returns list of dicts:
    {name, type, defined_in, callers: [file_paths], caller_count}
    """
    shared = []

    for file_rel_path, elements in all_elements_by_file.items():
        for elem in elements:
            name = elem["name"]
            # Skip short or common-looking names that would produce noise
            if len(name) < 4:
                continue
            # Skip names that are all lowercase single words (likely variables)
            if name.islower() and "_" not in name:
                continue

            # Find all files that reference this identifier
            referencing_files = codebase_index.get(name, set())
            # Exclude the definition file itself
            callers = sorted(f for f in referencing_files if f != file_rel_path)

            if len(callers) >= SHARED_ELEMENT_MIN_CALLERS:
                shared.append({
                    "name": name,
                    "type": elem["type"],
                    "defined_in": file_rel_path,
                    "line": elem["line"],
                    "callers": callers,
                    "caller_count": len(callers),
                })

    # Sort by caller count descending (most widely used first)
    shared.sort(key=lambda s: -s["caller_count"])
    return shared


# ---------------------------------------------------------------------------
# Source file enumeration
# ---------------------------------------------------------------------------

def count_lines(file_path):
    """Count lines in a file."""
    try:
        with open(file_path, "r", errors="replace") as f:
            return sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        return 0


def should_exclude(file_path, exclude_patterns):
    """Check if a file path matches any exclude pattern."""
    path_str = str(file_path)
    parts = Path(file_path).parts
    for part in parts:
        if part in DEFAULT_EXCLUDE_DIRS:
            return True
    for pattern in exclude_patterns:
        if pattern in path_str:
            return True
    return False


def enumerate_source_files(repo_path, exclude_patterns):
    """Walk the filesystem and find all source files with line counts."""
    source_files = []
    repo_path = Path(repo_path).resolve()

    for root, dirs, files in os.walk(repo_path):
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
            if line_count > 0:
                rel_path = os.path.relpath(full_path, repo_path)
                source_files.append({
                    "file": rel_path,
                    "abs_path": full_path,
                    "source_lines": line_count,
                    "repo_path": str(repo_path),
                    "extension": ext,
                })

    return source_files


# ---------------------------------------------------------------------------
# Coverage checking
# ---------------------------------------------------------------------------

def check_file_coverage(source_file, elements, analysis_index):
    """
    Check coverage for a single source file.

    If elements were extracted: coverage = % of elements found in analysis.
    If no elements extracted: fall back to filename mention check.

    Returns dict with coverage details.
    """
    filename = os.path.basename(source_file["file"])

    if not elements:
        # No extractable elements — fall back to filename mention
        mentioned = analysis_index.is_filename_mentioned(filename)
        return {
            "elements_total": 0,
            "elements_covered": 0,
            "elements_missing": [],
            "coverage_pct": 100.0 if mentioned else 0.0,
            "status": "ADEQUATE" if mentioned else "MISSING",
            "method": "filename_fallback",
        }

    covered = []
    missing = []

    for elem in elements:
        if analysis_index.is_element_covered(elem["name"]):
            covered.append(elem["name"])
        else:
            missing.append(elem["name"])

    total = len(elements)
    covered_count = len(covered)
    pct = (covered_count / total * 100) if total > 0 else 0

    if pct >= ADEQUATE_COVERAGE_PCT:
        status = "ADEQUATE"
    elif covered_count > 0:
        status = "SHALLOW"
    else:
        # Zero elements covered — but check if filename is at least mentioned
        if analysis_index.is_filename_mentioned(filename):
            status = "SHALLOW"  # File was mentioned but no elements tracked
        else:
            status = "MISSING"

    return {
        "elements_total": total,
        "elements_covered": covered_count,
        "elements_missing": missing,
        "coverage_pct": round(pct, 1),
        "status": status,
        "method": "element_coverage",
    }


def classify_gap(source_file, status, coverage_result):
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

    missing_count = len(coverage_result["elements_missing"])

    # CRITICAL: large files with significant gaps, or many missing elements
    if status == "MISSING":
        return "CRITICAL" if source_lines > 200 else "IMPORTANT"
    elif status == "SHALLOW":
        if missing_count > 5 or source_lines > 500:
            return "CRITICAL"
        elif missing_count > 2 or source_lines > 200:
            return "IMPORTANT"
        else:
            return "MINOR"

    return "MINOR"


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def run_audit(plan, raw_dir, details_dir, extra_exclude_patterns):
    """Run the full coverage audit across all repos in the plan."""

    # Collect exclude patterns
    exclude_patterns = list(extra_exclude_patterns)
    if "exclude_patterns" in plan:
        exclude_patterns.extend(plan["exclude_patterns"])

    # --- Phase 1: Enumerate source files ---
    all_source_files = []
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

    # --- Phase 2: Extract elements from every source file ---
    all_elements_by_file = {}  # rel_path → [elements]
    total_elements = 0

    for sf in all_source_files:
        elements = extract_elements(sf["abs_path"], sf["extension"])
        all_elements_by_file[sf["file"]] = elements
        total_elements += len(elements)

    # --- Phase 3: Build analysis index ---
    analysis_index = AnalysisIndex()
    analysis_index.build(raw_dir, details_dir)

    # --- Phase 4: Check element coverage per file ---
    coverage_counts = {"adequate": 0, "shallow": 0, "missing": 0}
    gaps = []
    total_elements_covered = 0

    for sf in all_source_files:
        elements = all_elements_by_file.get(sf["file"], [])
        result = check_file_coverage(sf, elements, analysis_index)

        total_elements_covered += result["elements_covered"]

        if result["status"] == "ADEQUATE":
            coverage_counts["adequate"] += 1
        else:
            bucket = result["status"].lower()
            coverage_counts[bucket] = coverage_counts.get(bucket, 0) + 1
            severity = classify_gap(sf, result["status"], result)
            gaps.append({
                "file": sf["file"],
                "repo": sf["repo_name"],
                "source_lines": sf["source_lines"],
                "elements_total": result["elements_total"],
                "elements_covered": result["elements_covered"],
                "elements_missing": result["elements_missing"],
                "coverage_pct": result["coverage_pct"],
                "status": result["status"],
                "severity": severity,
                "method": result["method"],
            })

    # Sort gaps: CRITICAL first, then by missing element count
    severity_order = {"CRITICAL": 0, "IMPORTANT": 1, "MINOR": 2, "TEST": 3}
    gaps.sort(key=lambda g: (
        severity_order.get(g["severity"], 99),
        -len(g.get("elements_missing", [])),
        -g["source_lines"],
    ))

    # --- Phase 5: Detect shared elements ---
    codebase_index = build_codebase_identifier_index(all_source_files)
    shared_elements = detect_shared_elements(all_elements_by_file, codebase_index)

    # --- Phase 6: Build triage summary ---
    triage = {}
    for g in gaps:
        sev = g["severity"]
        if sev not in triage:
            triage[sev] = {"count": 0, "total_lines": 0, "total_missing_elements": 0}
        triage[sev]["count"] += 1
        triage[sev]["total_lines"] += g["source_lines"]
        triage[sev]["total_missing_elements"] += len(g.get("elements_missing", []))

    element_coverage_pct = (
        round(total_elements_covered / total_elements * 100, 1)
        if total_elements > 0 else 100.0
    )

    result = {
        "audit_date": datetime.now(timezone.utc).isoformat(),
        "total_source_files": total_source_files,
        "total_source_lines": total_source_lines,
        "total_elements_extracted": total_elements,
        "total_elements_covered": total_elements_covered,
        "element_coverage_pct": element_coverage_pct,
        "coverage": coverage_counts,
        "triage": triage,
        "gaps": gaps,
        "shared_elements": shared_elements,
        "shared_element_count": len(shared_elements),
    }

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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


def main():
    args = parse_args()

    plan_path = args.plan
    with open(plan_path, "r") as f:
        plan = json.load(f)

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
    elem_total = result["total_elements_extracted"]
    elem_covered = result["total_elements_covered"]
    elem_pct = result["element_coverage_pct"]
    shared_count = result["shared_element_count"]

    print(f"\nStructural Coverage Audit", file=sys.stderr)
    print(f"========================", file=sys.stderr)
    print(f"Source files scanned: {total} ({result['total_source_lines']} lines)", file=sys.stderr)
    print(f"Code elements extracted: {elem_total}", file=sys.stderr)
    print(f"Elements covered in analysis: {elem_covered}/{elem_total} ({elem_pct}%)", file=sys.stderr)
    print(f"File-level coverage: {adequate}/{total} files adequately analyzed", file=sys.stderr)
    print(f"Gaps found: {gap_count}", file=sys.stderr)

    if result["triage"]:
        print(f"\nGap Triage:", file=sys.stderr)
        for sev in ["CRITICAL", "IMPORTANT", "MINOR", "TEST"]:
            if sev in result["triage"]:
                t = result["triage"][sev]
                print(
                    f"  {sev:10s}: {t['count']} files, "
                    f"{t['total_missing_elements']} missing elements, "
                    f"{t['total_lines']} source lines",
                    file=sys.stderr,
                )

    if shared_count > 0:
        print(f"\nShared Infrastructure Elements: {shared_count}", file=sys.stderr)
        print(f"  (These serve multiple callers and need purpose-level audit)", file=sys.stderr)
        # Show top 5
        for se in result["shared_elements"][:5]:
            print(
                f"  - {se['name']} ({se['defined_in']}) → "
                f"{se['caller_count']} callers",
                file=sys.stderr,
            )
        if shared_count > 5:
            print(f"  ... and {shared_count - 5} more", file=sys.stderr)

    # Exit code: 0 if no gaps, 1 if gaps found
    sys.exit(0 if gap_count == 0 else 1)


if __name__ == "__main__":
    main()
