# Context Window Management Guide

This reference is for all feature-inventory agents. Follow these rules to avoid
context exhaustion during analysis.

## Your Purpose

You are producing a specification that an AI/agent team will use to rebuild this
product from scratch. Your output is the ONLY reference they will have. This means:
- Completeness matters more than speed
- Every detail matters (defaults, edge cases, error messages, magic numbers)
- But you must manage context carefully to actually finish the job

## Hard Rules

1. **Never read a file without a line range** unless it's under 50 lines.
   Use `Read` with line ranges: `Read {file} lines 1-100`, then `lines 101-200`, etc.

2. **Never hold more than ~200 lines of source code in context at once.**
   Process a section, extract findings, write them to disk, then move on.

3. **Write incrementally.** After analyzing each module/file/component, append
   findings to the output file immediately. Don't accumulate everything in
   conversation context.

4. **Use Grep and Glob before Read.** Discovery should be:
   - `Glob` to find candidate files
   - `Grep` to find specific patterns and line numbers within files
   - `Read` (with line range) only for the specific lines you need to understand

5. **Process one logical unit at a time.** One endpoint, one model, one screen,
   one job. Extract it fully (every field, every edge case), write it, move on.

6. **Count your work.** After every ~20 items written, do a quick self-check:
   "Am I still operating efficiently, or has context grown too large?" If you feel
   like you're losing coherence, finalize what you have and note where you stopped.

7. **Source File Manifest is MANDATORY.** Your first action must be to enumerate all
   source files in your scope, write them as a manifest table at the top of your output
   file, and track their status. This is not optional. The coverage audit uses your
   manifest to verify you attempted every file in scope.

   If a file in your scope is >500 lines, you MUST either:
   a) Produce analysis meeting the proportionality threshold, OR
   b) Write an INCOMPLETE marker explaining why (e.g., "requires dedicated pass —
      4,048 lines of mixed UI rendering and state management")

   DO NOT silently skip files. A silent skip becomes an invisible gap.

## Incremental Write Pattern

```
First write (create file):
  Write the header/summary placeholder
  Write the first few findings

Subsequent writes (append):
  Read the last few lines of the output file to maintain continuity
  Append new findings

Final write:
  Go back and fill in the summary section with counts
```

## Exhaustiveness vs Context Limits

You might think "I can't capture everything because of context limits." Wrong approach.
The strategy is:
1. Capture one thing COMPLETELY (every field, every default, every edge case)
2. Write it to disk
3. Move to the next thing
4. Repeat

You don't need to hold the whole inventory in context. You just need to hold one
item at a time and write it out.

## Proportionality Rule

Your analysis depth MUST be proportional to source complexity. A source file with 1,000
lines of logic cannot be summarized in 3 lines — that's a 333:1 compression ratio and
means you've lost almost everything.

**Minimum analysis output per source file:**

| Source File Size | Minimum Analysis Lines |
|-----------------|----------------------|
| <50 lines | 3 lines |
| 50-200 lines | 5 lines |
| 200-500 lines | 10 lines |
| >500 lines | ceil(source_lines / 50) |

Examples:
- 538-line file → minimum 11 lines of analysis
- 1,433-line file → minimum 29 lines of analysis
- 2,775-line file → minimum 56 lines of analysis

**If you cannot meet the minimum for a file**, do NOT write a shallow stub. Instead:
1. Write `## INCOMPLETE - {filename} ({source_lines} lines) - requires dedicated pass`
2. The coverage audit will catch this and re-queue it for a focused agent task.

A shallow stub is worse than an INCOMPLETE marker. The stub looks like coverage but
contains no useful specification. INCOMPLETE triggers a re-queue; a stub silently
propagates a gap into the final output.

## Source File Manifest

**At the start of your analysis**, build a manifest of all source files in your scope
with their line counts. Write it to the top of your output file:

```markdown
## Source File Manifest
| File | Lines | Status |
|------|-------|--------|
| src/components/UserForm.tsx | 342 | Pending |
| src/components/Dashboard.tsx | 891 | Pending |
| ... | ... | ... |
```

Update the Status column as you process each file (Pending → Done). Before finishing,
review the manifest: any file still Pending needs analysis or an INCOMPLETE marker.

## When a Dimension Has Many Items

If a single dimension has 100+ items:
1. **Do not reduce depth.** Every item still gets full detail.
2. **Group items into logical sections** as you go.
3. **Write each section as you complete it.**
4. **If you must stop mid-dimension**, write a `## INCOMPLETE - Stopped at {location}`
   marker so the next run knows where to resume.

## Flagging Ambiguity

When you encounter something unclear:
- Complex conditionals with no comments
- Dead code that might or might not be active
- Config values that could mean multiple things
- Half-implemented features
- Behavior that seems like a bug vs intentional

Tag it inline: `[AMBIGUOUS] {description of what's unclear}`

The orchestrator will collect these and ask the user.

## Batch-Level Hard Stop Protocol (Orchestrators Only)

**This is the single most important context management mechanism.** All other
protections (step-boundary checkpoints, watchdog warnings) are secondary to this.

### The Problem

When the orchestrator dispatches agents in batches (e.g., 20 batches of 5 agents for
a large codebase = 100 agents), it runs in a continuous loop: spawn batch → monitor →
spawn next batch → monitor → ... This loop can run for **hours** without the
orchestrator ever yielding control back to the user. During this time:

- Context grows with every TaskCreate, TaskList, SendMessage, and output verification
- The step-boundary checkpoint is hours away (at the END of all batches)
- The user cannot intervene to `/compact` or `/clear` because the orchestrator is busy
- Auto-compaction may not trigger, or may not free enough space
- **The VS Code context percentage UI does not update during a long-running turn.** The
  user sees stale/low context usage because the UI only refreshes between turns. The
  orchestrator's continuous loop is one giant turn — the user has zero visibility into
  context health until the crash happens.
- Eventually: "prompt is too long" → crash → all running agents orphaned

### The Rule

**After completing every 2nd batch of agent work, the orchestrator MUST perform a
hard stop.** This is not a suggestion. This is not "evaluate and maybe continue."
This is: **save state, print checkpoint message, STOP.**

The user then:
1. Checks context health (visible in VS Code status bar)
2. Runs `/compact` to continue in the same session, OR `/clear` for a full reset
3. Re-runs the command — it resumes from `.progress.json`

### Hard Stop Procedure

After the 2nd, 4th, 6th, ... batch completes:

1. **Update `.progress.json`** with all completed work (batch number, completed items,
   pending items, failed items).

2. **Verify all batch outputs are on disk** — check that every teammate from the
   completed batches produced a non-empty output file.

3. **Present this message:**

   ```
   ⚠ BATCH CHECKPOINT — HARD STOP

   Completed: {N}/{total} batches ({completed_items} items done)
   Remaining: {remaining_items} items in {remaining_batches} batches

   The orchestrator has been monitoring agent work and context has grown.
   Continuing without compaction risks a session crash.

   To continue:
     1. Check your context usage (visible in VS Code status bar)
     2. Run /compact to free space, then re-run this command
        OR run /clear then re-run this command for a full reset
     3. The command will resume from batch {next_batch}

   All progress is saved:
     {progress_file_path}
     {list of completed output files}
   ```

4. **STOP.** Do not continue. Do not start the next batch. Do not do any more work.
   The orchestrator's turn ends here.

### Why Every 2 Batches?

Each batch of 5 agents requires approximately:
- 5 TaskCreate calls
- 5-15 TaskList polling calls
- 5-10 output verification reads
- 1 progress file write

That's ~15-30 tool calls per batch. Two batches = ~30-60 tool calls, which aligns
with the WARN→CRITICAL threshold in the watchdog. Stopping here prevents the
orchestrator from ever reaching the BLOCK threshold under normal operation.

For very small batches (1-2 agents), the orchestrator MAY continue through 3 batches
before stopping, but MUST stop after 3 regardless.

### Interaction with Step-Boundary Checkpoints

Step-boundary checkpoints still apply. The batch-level hard stop is **additional** —
it fires WITHIN long-running steps (Steps 3, 3.5, 4 of create.md; Step 4 of plan.md).
The two mechanisms complement each other:

| Mechanism | When | Enforcement |
|-----------|------|-------------|
| Step-boundary checkpoint | Between major steps | LLM compliance (soft) |
| Batch-level hard stop | Every 2 batches within a step | LLM compliance (hard instruction) |
| Context watchdog BLOCK | 75+ tool calls / 800KB | Deterministic code (hard block) |

The batch-level hard stop should prevent the watchdog from ever triggering under normal
operation. The watchdog is the safety net for when the orchestrator ignores the hard stop.

### Interaction with Progress File

The progress file schema already supports batch-level resume:

```json
{
  "batch_number": 4,        // ← resume from batch 5
  "batches_total": 10,
  "completed_dimensions": [...],  // ← skip these
  "pending_dimensions": [...],    // ← do these next
}
```

This is why the progress file update rules require updating **after every batch**, not
just at step boundaries. The batch-level hard stop depends on this.

---

## Context Checkpoint Protocol (Orchestrators Only)

**This section applies to the lead orchestrator, not to teammates.** Teammates have fresh
context windows and rarely hit limits. The orchestrator, however, runs for the entire
duration of a multi-step workflow (potentially hours) and its conversation history grows
with every tool call, monitoring response, and user interaction.

**If the orchestrator hits "prompt is too long", the entire session dies.** Running
teammates become orphaned. All orchestrator context is lost. The user must start over
(or resume from disk, losing the cost of everything since the last checkpoint). This
is catastrophic and must be prevented.

### Mandatory Context Checkpoints

At designated checkpoint locations in the orchestrator workflow, the orchestrator MUST:

1. **Verify all state is on disk.** Every piece of information needed to resume must
   exist as a file — interviews, plans, configs, raw outputs, audit results, synthesis
   plans, clarifications. The orchestrator should NOT be carrying state only in
   conversation context.

2. **Evaluate context health.** Consider how much work has been done since the last
   `/clear` or session start:
   - How many tool calls have been made?
   - How many agent batches have been monitored?
   - How many user interactions have occurred?
   - How many file reads/writes have accumulated in context?

3. **If context is heavy, MANDATE a clear.** Do not suggest it as optional. Tell the user:

   ```
   ⚠ CONTEXT CHECKPOINT — CLEAR REQUIRED

   Steps {completed} are done. All state is saved to disk.
   The orchestrator's context has accumulated significant history
   from {description of what was done}. Continuing without clearing
   risks a "prompt is too long" error that would kill this session
   and orphan any running teammates.

   Action required:
     1. Run /clear
     2. Re-run the command (it will resume from Step {next})

   Everything is preserved:
     {list of files that will be reloaded}
   ```

4. **If context is light, note the checkpoint and continue.**

   ```
   ✓ Context checkpoint (after Step {N}): context is healthy, continuing.
   ```

### How to Estimate Context Health

You cannot directly measure your context usage, but you can estimate based on activity
since the session started (or last `/clear`):

| Activity Since Start/Clear | Risk Level | Action |
|---|---|---|
| 1-2 steps, <10 tool calls | Low | Continue |
| 2-3 steps, 10-30 tool calls | Medium | Continue with caution |
| 3+ steps, 30-50 tool calls | High | Recommend clear |
| 4+ steps, 50+ tool calls, or any agent monitoring | Critical | MANDATE clear |

**Agent monitoring is the biggest context consumer.** Each `TaskList` call, each
`SendMessage` exchange, each batch completion check adds to context. After monitoring
even a single batch of 5 teammates, the orchestrator has typically consumed significant
context.

### Checkpoint Placement Rules

Checkpoints are placed at **every step boundary** in orchestrator workflows. Each
checkpoint is a natural resume point — all prior state is on disk, and the next step
can start from those files.

The orchestrator workflows (`create.md`, `plan.md`) specify exact checkpoint locations
with `### Context Checkpoint` markers. Do not skip them.

### Context Watchdog (Automated Enforcement)

The manual checkpoint protocol is backed by an automated watchdog that monitors context
health in real time via Claude Code hooks. The watchdog (`scripts/context-watchdog.py`):

1. **Fires on every tool call** (PostToolUse hook) — tracks cumulative tool call count
   and transcript file size as proxies for context usage.
2. **Injects warnings into Claude's context** at escalating urgency levels:
   - **WARN** (30+ tool calls or 300KB+ transcript): "Plan to checkpoint soon"
   - **CRITICAL** (50+ tool calls or 500KB+ transcript): "Checkpoint NOW"
   - **BLOCK** (75+ tool calls or 800KB+ transcript): "STOP ALL WORK"
3. **Blocks agent-spawning tools** (TaskCreate, TeamCreate, SendMessage) at CRITICAL
   level via a PreToolUse hook. This hard-prevents the orchestrator from starting
   expensive work that will be lost if the session crashes.
4. **Resets automatically** on SessionStart (including after `/clear`).

The watchdog is a safety net — the manual checkpoints should catch most situations
before the watchdog triggers. But if the orchestrator ignores checkpoints or a step
is unexpectedly expensive, the watchdog will force the issue.

**The watchdog's thresholds are deliberately conservative.** A false "clear now" costs
seconds (the user clears and resumes). A missed warning costs hundreds of dollars
in orphaned agents and lost context.

### Emergency Mid-Step Saves

If at any point during a step the orchestrator senses context is growing dangerously
(e.g., monitoring a large batch of teammates, or processing many gap-fill cycles),
OR if the context watchdog emits a CRITICAL or BLOCK warning:

1. **Finish the current sub-step** (e.g., let the current batch complete).
2. **Write all intermediate state to disk** (including the orchestrator progress file).
3. **Present the clear mandate** to the user with resume instructions.
4. **Do NOT start the next sub-step.**

This is an escape valve — it should rarely be needed if checkpoints are respected,
but it prevents the catastrophic "prompt is too long" crash.

## Orchestrator Progress File

The orchestrator MUST maintain a progress file that tracks exactly where it is in
the workflow. This enables instant resume after `/clear` without re-scanning all
output files.

### For `/feature-inventory:create`: `./docs/features/.progress.json`

```json
{
  "command": "create",
  "current_step": "3",
  "current_substep": "3b",
  "batch_number": 2,
  "batches_total": 4,
  "completed_dimensions": ["api-surface--repo1", "data-models--repo1"],
  "pending_dimensions": ["ui-screens--repo1", "business-logic--repo1"],
  "failed_dimensions": [],
  "gap_fill_cycle": 0,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### For `/feature-inventory:plan`: `./docs/plans/.progress.json`

```json
{
  "command": "plan",
  "current_step": "4",
  "current_substep": "4d",
  "batch_number": 1,
  "batches_total": 3,
  "completed_features": ["cross-cutting", "F-001", "F-002"],
  "pending_features": ["F-003", "F-004", "F-005"],
  "failed_features": [],
  "timestamp": "2024-01-15T14:20:00Z"
}
```

### Update Rules

- Update the progress file **after every batch completes**, not just at step boundaries.
- Update **before and after every context checkpoint**.
- On resume, read the progress file FIRST — it tells you exactly where to pick up.
- The progress file is the single source of truth for resume. Output file scanning is
  a fallback for when no progress file exists (first run or manual recovery).

## Teammate Disk Write Frequency

Teammates run with fresh context windows, but they can still lose work if they crash
or exhaust their own context. The incremental write pattern (see above) is critical,
but it needs a concrete frequency target.

### Write Frequency Rules

1. **Write after every 5-10 logical units** (endpoints, models, screens, etc.).
   Never accumulate more than 10 items in conversation before writing to disk.

2. **Write at least every 3 minutes** of wall-clock time. If a single item takes
   longer than 3 minutes to analyze (e.g., a very complex function), write what
   you have so far and continue.

3. **Write immediately after any large file read** (>200 lines). The read content
   is now in context — extract findings and write them before reading more.

4. **Each write should be self-contained** — if the teammate crashes after this write,
   the output file should still be valid and usable (even if incomplete). Use the
   `## INCOMPLETE` marker at the end of partial output.

### Why This Matters

A teammate analyzing a dimension might run for 5-15 minutes. If it writes only at
the end and crashes at minute 12, ALL work is lost. If it writes every 5 items or
3 minutes, at most ~3 minutes of work is lost.

**Target: no more than 3 minutes of work should ever be lost from a teammate crash.**

## Agent Liveness Protocol

### The Problem

When the orchestrator monitors agents via TaskList, it cannot distinguish between
"agent is actively working" and "agent is stuck/dead." Without a heartbeat signal,
the orchestrator may assume an agent is dead and move on — wasting every token the
agent spent. Conversely, it may wait indefinitely for a stuck agent.

### Heartbeat Rules (Teammates)

Every teammate MUST write heartbeat markers to their output file at regular intervals:

1. **Write a heartbeat line every 2 minutes** to your JSONL output file:
   ```json
   {"heartbeat": true, "timestamp": "2024-01-15T10:32:00Z", "items_completed": 5, "items_remaining": 12}
   ```
   For Markdown output files, append a comment line:
   ```markdown
   <!-- heartbeat: 2024-01-15T10:32:00Z | items_completed: 5 | items_remaining: 12 -->
   ```

2. **Write a heartbeat before any long operation** (reading a large file, running a
   complex query, grepping a large codebase). This tells the orchestrator "I'm about
   to do something that takes a while — I'm not stuck."

3. **Write a final summary line** when you're done. The orchestrator uses this to
   distinguish "completed" from "died mid-work."

### Liveness Monitoring (Orchestrator)

The orchestrator MUST check agent output files before making any liveness determination:

1. **Check output file modification time** before assuming an agent is dead:
   ```bash
   stat -c %Y intermediate/connections--src-services-order-ts.jsonl
   ```

2. **Liveness thresholds:**

   | Output File Age | Status | Action |
   |----------------|--------|--------|
   | Modified < 3 min ago | **Alive** | Continue waiting. Do not poll excessively. |
   | Modified 3-5 min ago | **Slow** | Log a note. Continue waiting. |
   | Modified 5-10 min ago | **Possibly stuck** | Check TaskList status. If task shows "in_progress", continue waiting — the agent may be doing a long grep. |
   | Modified > 10 min ago | **Likely dead** | Check TaskList status. If task shows "completed" but no summary line in output, the agent crashed. If task shows "in_progress", wait one more cycle (2 min) then flag for user. |

3. **NEVER kill an agent whose output file was modified in the last 5 minutes.**
   An agent that is actively writing is an agent that is working. Killing it wastes
   every token it has spent.

4. **When an agent appears stuck (>10 min no output, task still "in_progress"):**
   - Present to the user: "Agent for {file} hasn't written output in {N} minutes.
     It may be stuck on a complex file or a slow grep. Wait longer or cancel?"
   - Do NOT automatically cancel. Let the user decide.

5. **When an agent dies (task shows "failed" or "completed" with no summary line):**
   - Check what partial output exists in the JSONL file.
   - Add the file back to the pending list for the next batch.
   - Do NOT discard partial output — the next agent for this file should read it
     and continue from where the previous agent stopped.

### Why File Modification Time?

TaskList status is unreliable for liveness — a task can show "in_progress" whether
the agent is actively working or stuck in an infinite loop. The output file modification
time is the ground truth: if the agent is writing, it's working. If it hasn't written
in 10 minutes, something is wrong. This is simple, requires no extra infrastructure,
and works with the existing JSONL write pattern.

## Failure Recovery

If you're spawned and the output file already has partial content:
1. Read the last 30 lines to see where previous analysis stopped.
2. Look for `## INCOMPLETE` markers.
3. Continue from where it left off.
4. Don't duplicate entries that already exist in the file.
