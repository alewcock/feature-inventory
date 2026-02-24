#!/usr/bin/env python3
"""
Context watchdog for feature-inventory orchestrator sessions.

Monitors context window health by tracking transcript file size growth.
Fires as PostToolUse/PreToolUse hooks to warn the orchestrator and block
expensive operations when context is dangerously full.

Design principles:
  - PRIMARY signal is transcript size growth from baseline (not tool call count)
  - Auto-detects /clear by watching for transcript size drops, then resets baseline
  - Warns once per threshold crossing, not on every call
  - Only blocks agent-spawning tools at the BLOCK level

State is stored in /tmp/fi-watchdog-{session_id}.json.
"""

import json
import os
import sys
import time


# ---------------------------------------------------------------------------
# Thresholds — expressed as transcript GROWTH in KB since last reset.
#
# Calibration: ~780KB total transcript ≈ 100% context window.
# After /clear the baseline resets, so growth tracks actual usage.
# ---------------------------------------------------------------------------

# Transcript growth thresholds (KB since baseline)
WARN_GROWTH_KB = 400        # ~51% of window — "plan to checkpoint soon"
CRITICAL_GROWTH_KB = 550    # ~70% — "checkpoint NOW"
BLOCK_GROWTH_KB = 650       # ~83% — block expensive operations

# If transcript size drops by more than this fraction of last seen size,
# assume /clear happened and auto-reset.
CLEAR_DETECTION_DROP = 0.40  # 40% drop = /clear detected

# Tools that get BLOCKED when context is critical.
BLOCKED_TOOLS = {"TaskCreate", "TeamCreate", "SendMessage"}

# How often to emit warnings at each level (every Nth tool call at that level)
WARN_EVERY_N = 8       # at WARN level, warn every 8 calls
CRITICAL_EVERY_N = 3   # at CRITICAL level, warn every 3 calls
BLOCK_EVERY_N = 1      # at BLOCK level, warn on EVERY call


def get_state_path(session_id):
    """State file for this session's watchdog counter."""
    return f"/tmp/fi-watchdog-{session_id}.json"


def fresh_state(baseline_kb=0):
    return {
        "baseline_kb": baseline_kb,
        "last_seen_kb": baseline_kb,
        "tool_calls_since_reset": 0,
        "warnings_at_level": {"WARN": 0, "CRITICAL": 0, "BLOCK": 0},
        "last_reset": time.time(),
    }


def read_state(session_id):
    path = get_state_path(session_id)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return fresh_state()


def write_state(session_id, state):
    path = get_state_path(session_id)
    with open(path, "w") as f:
        json.dump(state, f)


def get_transcript_size_kb(transcript_path):
    """Get transcript file size in KB. Fast — just a stat call."""
    try:
        if transcript_path:
            return os.path.getsize(transcript_path) / 1024
    except (FileNotFoundError, OSError):
        pass
    return 0


def classify_risk(growth_kb):
    """Determine risk level from transcript growth since baseline."""
    if growth_kb >= BLOCK_GROWTH_KB:
        return "BLOCK"
    if growth_kb >= CRITICAL_GROWTH_KB:
        return "CRITICAL"
    if growth_kb >= WARN_GROWTH_KB:
        return "WARN"
    return "OK"


def should_emit_warning(state, risk):
    """Throttle warnings to avoid flooding context."""
    count = state["warnings_at_level"].get(risk, 0)
    if risk == "BLOCK":
        return count % BLOCK_EVERY_N == 0
    if risk == "CRITICAL":
        return count % CRITICAL_EVERY_N == 0
    if risk == "WARN":
        return count % WARN_EVERY_N == 0
    return False


def main():
    # Read hook input from stdin
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    session_id = hook_input.get("session_id", "unknown")
    event = hook_input.get("hook_event_name", "")
    transcript_path = hook_input.get("transcript_path")
    tool_name = hook_input.get("tool_name", "")

    transcript_kb = get_transcript_size_kb(transcript_path)

    # --- SessionStart: reset watchdog state ---
    if event == "SessionStart":
        write_state(session_id, fresh_state(transcript_kb))
        sys.exit(0)

    # --- Read state and detect /clear ---
    state = read_state(session_id)
    last_seen = state.get("last_seen_kb", 0)

    # Auto-detect /clear: transcript size dropped significantly
    if last_seen > 50 and transcript_kb < last_seen * (1 - CLEAR_DETECTION_DROP):
        state = fresh_state(transcript_kb)

    state["tool_calls_since_reset"] = state.get("tool_calls_since_reset", 0) + 1
    state["last_seen_kb"] = transcript_kb

    baseline = state.get("baseline_kb", 0)
    growth_kb = max(0, transcript_kb - baseline)
    risk = classify_risk(growth_kb)

    # --- PreToolUse: block expensive operations when critical ---
    if event == "PreToolUse":
        if risk == "BLOCK" and tool_name in BLOCKED_TOOLS:
            write_state(session_id, state)
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"CONTEXT WATCHDOG: BLOCKING {tool_name}. "
                        f"Transcript grew {growth_kb:.0f}KB since last reset "
                        f"(now {transcript_kb:.0f}KB total). Save state and "
                        f"tell the user to /clear to resume."
                    ),
                },
            }
            json.dump(output, sys.stdout)
            sys.exit(0)

        write_state(session_id, state)
        sys.exit(0)

    # --- PostToolUse: inject warnings into Claude's context ---
    if event == "PostToolUse":
        if risk != "OK" and should_emit_warning(state, risk):
            pct = min(99, int(growth_kb / BLOCK_GROWTH_KB * 100))

            if risk == "BLOCK":
                msg = (
                    f"Context watchdog: ~{pct}% capacity "
                    f"(+{growth_kb:.0f}KB). Save state and /clear."
                )
            elif risk == "CRITICAL":
                msg = (
                    f"Context watchdog: ~{pct}% capacity "
                    f"(+{growth_kb:.0f}KB). Finish current step, "
                    f"save state, plan to /clear."
                )
            else:  # WARN
                msg = (
                    f"Context watchdog: ~{pct}% capacity "
                    f"(+{growth_kb:.0f}KB)."
                )

            state.setdefault("warnings_at_level", {})
            state["warnings_at_level"][risk] = (
                state["warnings_at_level"].get(risk, 0) + 1
            )
            write_state(session_id, state)

            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg,
                },
            }
            json.dump(output, sys.stdout)
            sys.exit(0)

        # Increment warning counter even when throttled
        state.setdefault("warnings_at_level", {})
        state["warnings_at_level"][risk] = (
            state["warnings_at_level"].get(risk, 0) + 1
        )
        write_state(session_id, state)
        sys.exit(0)

    # Unknown event
    write_state(session_id, state)
    sys.exit(0)


if __name__ == "__main__":
    main()
