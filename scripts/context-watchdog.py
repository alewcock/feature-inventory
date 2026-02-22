#!/usr/bin/env python3
"""
Context watchdog for feature-inventory orchestrator sessions.

Monitors context window health by tracking tool call count and transcript
file size. Fires as PostToolUse/PreToolUse hooks to warn the orchestrator
and block expensive operations when context is dangerously full.

How it works:
  - PostToolUse: Increments a per-session tool call counter, checks transcript
    file size, and injects progressively urgent warnings into Claude's context
    via additionalContext.
  - PreToolUse: When context is critical, BLOCKS agent-spawning tools
    (TaskCreate, TeamCreate, SendMessage) to prevent starting work that
    will be lost when the session inevitably crashes.
  - SessionStart: Resets the watchdog state for the new session.

State is stored in /tmp/fi-watchdog-{session_id}.json.
"""

import json
import os
import sys
import time


# ---------------------------------------------------------------------------
# Thresholds — aligned with the Context Checkpoint Protocol in
# references/context-management.md.
#
# These are deliberately conservative. A false "clear now" is cheap
# (user clears and resumes in seconds). A missed warning is catastrophic
# (session dies, agents orphaned, hundreds of dollars lost).
# ---------------------------------------------------------------------------

# Tool call thresholds (cumulative since session start or last /clear)
WARN_TOOL_CALLS = 30        # "plan to checkpoint soon"
CRITICAL_TOOL_CALLS = 50    # "checkpoint NOW"
BLOCK_TOOL_CALLS = 75       # block expensive operations

# Transcript file size thresholds (KB) — rough proxy for context usage.
# Transcript includes all messages + tool calls + responses in JSON.
WARN_TRANSCRIPT_KB = 300
CRITICAL_TRANSCRIPT_KB = 500
BLOCK_TRANSCRIPT_KB = 800

# Tools that get BLOCKED when context is critical. These start expensive
# operations (new agents, agent communication) that will be lost if the
# session crashes.
BLOCKED_TOOLS = {"TaskCreate", "TeamCreate", "SendMessage"}

# How often to emit warnings at each level (every Nth tool call)
# to avoid flooding context with repeated warnings.
WARN_EVERY_N = 5       # at WARN level, warn every 5 calls
CRITICAL_EVERY_N = 2   # at CRITICAL level, warn every 2 calls
BLOCK_EVERY_N = 1      # at BLOCK level, warn on EVERY call


def get_state_path(session_id):
    """State file for this session's watchdog counter."""
    return f"/tmp/fi-watchdog-{session_id}.json"


def read_state(session_id):
    path = get_state_path(session_id)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "tool_calls": 0,
            "last_reset": time.time(),
            "warnings_given": 0,
        }


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


def classify_risk(tool_calls, transcript_kb):
    """Determine risk level from tool calls and transcript size."""
    if tool_calls >= BLOCK_TOOL_CALLS or transcript_kb >= BLOCK_TRANSCRIPT_KB:
        return "BLOCK"
    if tool_calls >= CRITICAL_TOOL_CALLS or transcript_kb >= CRITICAL_TRANSCRIPT_KB:
        return "CRITICAL"
    if tool_calls >= WARN_TOOL_CALLS or transcript_kb >= WARN_TRANSCRIPT_KB:
        return "WARN"
    return "OK"


def should_emit_warning(state, risk):
    """Throttle warnings based on risk level to avoid flooding context."""
    count = state["warnings_given"]
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
        sys.exit(0)  # Silent failure — never break the session

    session_id = hook_input.get("session_id", "unknown")
    event = hook_input.get("hook_event_name", "")
    transcript_path = hook_input.get("transcript_path")
    tool_name = hook_input.get("tool_name", "")

    # --- SessionStart: reset watchdog state ---
    if event == "SessionStart":
        write_state(session_id, {
            "tool_calls": 0,
            "last_reset": time.time(),
            "warnings_given": 0,
        })
        sys.exit(0)

    # --- Read and update state ---
    state = read_state(session_id)
    state["tool_calls"] += 1
    tool_calls = state["tool_calls"]
    transcript_kb = get_transcript_size_kb(transcript_path)
    risk = classify_risk(tool_calls, transcript_kb)

    # --- PreToolUse: block expensive operations when critical ---
    if event == "PreToolUse":
        if risk in ("BLOCK", "CRITICAL") and tool_name in BLOCKED_TOOLS:
            write_state(session_id, state)
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"CONTEXT WATCHDOG: BLOCKING {tool_name}. "
                        f"Context is at {risk} level ({tool_calls} tool calls, "
                        f"{transcript_kb:.0f}KB transcript). You MUST save all state "
                        f"to disk and tell the user to /clear and re-run the command "
                        f"to resume. Do NOT attempt to start new agent work — it will "
                        f"be lost when the session crashes."
                    ),
                },
            }
            json.dump(output, sys.stdout)
            sys.exit(0)

        # Allow all other tools (even at critical — Claude needs Read/Write to save state)
        write_state(session_id, state)
        sys.exit(0)

    # --- PostToolUse: inject warnings into Claude's context ---
    if event == "PostToolUse":
        if risk != "OK" and should_emit_warning(state, risk):
            if risk == "BLOCK":
                msg = (
                    f"⚠ CONTEXT WATCHDOG — CRITICAL: {tool_calls} tool calls, "
                    f"{transcript_kb:.0f}KB transcript. Session crash imminent. "
                    f"STOP ALL WORK IMMEDIATELY. Save any unsaved state to disk. "
                    f"Tell the user: 'Context is critically full. Run /clear then "
                    f"re-run the command — it will resume from where we left off.' "
                    f"Agent-spawning tools are now BLOCKED."
                )
            elif risk == "CRITICAL":
                msg = (
                    f"⚠ CONTEXT WATCHDOG — HIGH: {tool_calls} tool calls, "
                    f"{transcript_kb:.0f}KB transcript. Context window approaching "
                    f"capacity. Complete your current sub-step, save state to disk, "
                    f"and trigger a context checkpoint NOW. Do NOT start new agent "
                    f"batches without /clear first."
                )
            else:  # WARN
                msg = (
                    f"Context watchdog: {tool_calls} tool calls, "
                    f"{transcript_kb:.0f}KB transcript. Approaching checkpoint "
                    f"threshold. Plan to /clear at the next step boundary."
                )

            state["warnings_given"] += 1
            write_state(session_id, state)

            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg,
                },
            }
            json.dump(output, sys.stdout)
            sys.exit(0)

        state["warnings_given"] += 1
        write_state(session_id, state)
        sys.exit(0)

    # Unknown event — pass through silently
    write_state(session_id, state)
    sys.exit(0)


if __name__ == "__main__":
    main()
