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

### Emergency Mid-Step Saves

If at any point during a step the orchestrator senses context is growing dangerously
(e.g., monitoring a large batch of teammates, or processing many gap-fill cycles):

1. **Finish the current sub-step** (e.g., let the current batch complete).
2. **Write all intermediate state to disk.**
3. **Present the clear mandate** to the user with resume instructions.
4. **Do NOT start the next sub-step.**

This is an escape valve — it should rarely be needed if checkpoints are respected,
but it prevents the catastrophic "prompt is too long" crash.

## Failure Recovery

If you're spawned and the output file already has partial content:
1. Read the last 30 lines to see where previous analysis stopped.
2. Look for `## INCOMPLETE` markers.
3. Continue from where it left off.
4. Don't duplicate entries that already exist in the file.
