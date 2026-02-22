#!/usr/bin/env python3
"""Verify section files after plan-section-writer subagent completes.

This SubagentStop hook fires when a plan-section-writer teammate finishes.
It verifies the section file was written correctly:
1. Reads the agent transcript to find the output file path
2. Checks the file exists and is non-empty
3. Validates basic structure (YAML frontmatter, required sections)
4. Reports results via stdout for the orchestrator to see

Unlike deep-plan's write-section-on-stop.py which extracts content from
the transcript, our plan-section-writer has direct Write tool access and
writes files to disk itself. This hook is a verification/safety net.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Debug log file
DEBUG_LOG = Path.home() / ".claude" / "fi-verify-section-debug.log"


def debug_log(msg: str) -> None:
    """Append debug message to log file."""
    if not os.environ.get("DEBUG_FI_SECTION_HOOK"):
        return
    try:
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} {msg}\n")
    except OSError:
        pass


def wait_for_stable_file(
    path: str,
    stability_ms: int = 200,
    timeout_s: float = 5.0,
    poll_ms: int = 50,
) -> bool:
    """Wait for a file to stop being written to.

    Returns True if file is stable, False if timeout or missing.
    """
    deadline = time.time() + timeout_s
    last_size = -1
    stable_since = time.time()

    while time.time() < deadline:
        try:
            size = os.path.getsize(path)
        except OSError:
            time.sleep(poll_ms / 1000)
            continue

        if size != last_size:
            last_size = size
            stable_since = time.time()
        elif (time.time() - stable_since) >= stability_ms / 1000:
            return True

        time.sleep(poll_ms / 1000)

    return False


def find_section_path_from_transcript(transcript_path: str) -> str | None:
    """Extract the section output path from the agent transcript.

    Looks for Write tool calls in the transcript to find the section file path.
    """
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Look for Write tool results or tool_use with file_path
                content = entry.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            # Look for tool_use with Write
                            if block.get("type") == "tool_use" and block.get("name") == "Write":
                                inp = block.get("input", {})
                                file_path = inp.get("file_path", "")
                                if "section-" in file_path and file_path.endswith(".md"):
                                    return file_path
    except (OSError, json.JSONDecodeError):
        pass
    return None


def validate_section_file(path: str) -> list[str]:
    """Validate a section file has required structure.

    Returns list of issues (empty = valid).
    """
    issues = []
    try:
        content = Path(path).read_text()
    except OSError as e:
        return [f"Cannot read file: {e}"]

    if len(content.strip()) < 100:
        issues.append(f"File suspiciously short ({len(content)} bytes)")

    # Check for YAML frontmatter
    if not content.startswith("---"):
        issues.append("Missing YAML frontmatter")

    # Check for required sections
    required_sections = [
        "## Context",
        "## What to Build",
        "## Tests to Write First",
        "## Acceptance Criteria",
    ]
    for section in required_sections:
        if section not in content:
            issues.append(f"Missing required section: {section}")

    # Check for behavior IDs in acceptance criteria
    if "- [ ]" not in content:
        issues.append("No checkbox items in Acceptance Criteria")

    return issues


def main() -> int:
    """Verify section file from completed plan-section-writer.

    Returns:
        0 always (hooks should not fail the session)
    """
    debug_log("=== VERIFY SECTION HOOK STARTED ===")

    # 1. Parse stdin payload
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input else {}
    except (json.JSONDecodeError, Exception):
        debug_log("Failed to parse stdin")
        return 0

    # 2. Get transcript path
    transcript_path = payload.get("agent_transcript_path")
    debug_log(f"transcript_path = {transcript_path}")
    if not transcript_path:
        debug_log("No transcript path")
        return 0

    # 3. Wait for transcript to stabilize
    if not wait_for_stable_file(transcript_path):
        debug_log("Transcript file not stable")
        return 0

    # 4. Find section file path from transcript
    section_path = find_section_path_from_transcript(transcript_path)
    debug_log(f"section_path = {section_path}")
    if not section_path:
        debug_log("Could not find section path in transcript")
        return 0

    # 5. Verify the file exists
    if not Path(section_path).exists():
        debug_log(f"Section file MISSING: {section_path}")
        # Output warning for orchestrator
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStop",
                "additionalContext": (
                    f"[SECTION_VERIFICATION_FAILED] Section file not found: {section_path}. "
                    "The plan-section-writer may have failed to write. Re-queue this section."
                ),
            }
        }
        print(json.dumps(output))
        return 0

    # 6. Validate structure
    issues = validate_section_file(section_path)
    if issues:
        debug_log(f"Validation issues: {issues}")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStop",
                "additionalContext": (
                    f"[SECTION_VERIFICATION_WARNING] {section_path}: "
                    + "; ".join(issues)
                ),
            }
        }
        print(json.dumps(output))
    else:
        debug_log(f"Section verified OK: {section_path}")

    debug_log("=== VERIFY SECTION HOOK FINISHED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
