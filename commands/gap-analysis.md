---
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: >
  Compares a new/in-progress project against a feature inventory to identify gaps:
  missing features, partial implementations, and unstarted work. Produces a structured
  task list consumable by both humans and AI/agent teams. REQUIRES Agent Teams enabled
  and a completed feature inventory. Run: /feature-inventory:gap-analysis [new-project-path] [inventory-path]
---

# Gap Analysis - Orchestrator

## PREREQUISITE: Agent Teams Required

**Before doing anything else**, verify that Agent Teams is available:

1. Run: `echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
2. If the value is NOT "1", **stop immediately** and tell the user:

   > **This command requires Claude Code Agent Teams.**
   >
   > To enable, add to `~/.claude/settings.json`:
   > ```json
   > {
   >   "env": {
   >     "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
   >   }
   > }
   > ```
   > Then restart Claude Code and run the command again.

   **Do not proceed. Do not fall back to sequential subagents.**

3. Also verify you have access to the `TeamCreate` tool.

---

You are the orchestrator for a gap analysis that compares a new/in-progress project
against a previously generated feature inventory. Your goal is to produce a precise,
structured task list that tells humans and AI/agent teams exactly what still needs to
be built.

**The output is actionable.** Every gap becomes a task. Every task has enough context
that an AI agent or human developer can pick it up and start working immediately. No
vague descriptions. No "implement remaining features." Each task references the specific
feature inventory detail file that defines what needs to be built.

## Important: Context Window Management

Gap analysis requires reading both the feature inventory AND the new project. Manage
context carefully:

1. **Load the feature index (JSON), not all detail files at once.** Use the index to
   understand scope, then read detail files only when comparing specific features.
2. **Delegate per-feature-area analysis to teammates.** Each teammate gets one major
   feature area to compare.
3. **All teammates write findings to disk immediately.** They do NOT return large
   payloads in conversation.
4. **Resume capability:** Check for existing gap analysis output files before spawning
   agents. Skip completed areas.

## Inputs

The command accepts two arguments:

1. **New project path** (required): Path to the project being built. If not provided,
   prompt the user.
2. **Inventory path** (optional): Path to the `docs/features/` directory.
   Defaults to `./docs/features/`. If it doesn't exist, tell the user to
   run `/feature-inventory:work` first.

## Step 0: Validate Inventory

1. Verify `{inventory-path}/FEATURE-INDEX.json` exists. If not, stop and tell the user
   they need a completed feature inventory first.
2. Read `FEATURE-INDEX.json` to get the full feature hierarchy.
3. Verify detail files exist for the features listed. Warn if any are missing.
4. Read `{inventory-path}/interview.md` for product context (brief summary).
5. Read `{inventory-path}/discovery.json` for original tech stack info.

## Step 1: New Project Discovery

Scan the new project to understand what exists:

1. Identify primary languages, frameworks, and structure (top 2 directory levels).
2. Count files by extension.
3. Identify key patterns: route definitions, models/schemas, UI components, test files,
   config files, migration files.
4. Write discovery to `./docs/gap-analysis/new-project-discovery.json`.

## Step 2: Plan Feature Area Assignments

Based on the feature index:

1. List all major feature areas (F-001, F-002, etc.).
2. For each, count sub-features and behaviors.
3. Group into batches of up to 5 for parallel analysis.
4. Write plan to `./docs/gap-analysis/plan.json`:

```json
{
  "inventory_path": "/path/to/feature-inventory-output",
  "new_project_path": "/path/to/new-project",
  "feature_areas": [
    {
      "id": "F-001",
      "name": "User Management",
      "sub_features": 8,
      "behaviors": 45,
      "batch": 1
    }
  ],
  "total_batches": 3
}
```

## Step 3: Execute Gap Analysis via Agent Teams

### 3a: Create the Team

Use `TeamCreate` to create a team named "gap-analysis". Enable delegate mode.

### 3b: Spawn Teammates in Batches

For each major feature area:

1. **Check for existing output:** If `./docs/gap-analysis/raw/{feature-id}.md`
   exists and is non-empty, skip it.
2. **Create tasks** via `TaskCreate` for each pending feature area.
3. **Spawn teammates in batches of up to 5.** Each teammate gets ONE major feature
   area. Assign each the `feature-inventory:gap-analyzer` agent.
4. **Each teammate receives** via its task description:
   - The new project path
   - The inventory path
   - The major feature ID and name
   - The list of sub-feature IDs and behavior IDs under this feature
   - The output file path (`./docs/gap-analysis/raw/{feature-id}.md`)
   - A pointer to read `references/context-management.md` before starting
   - This instruction verbatim: **"For every sub-feature and behavior in your assigned
     feature area, determine its implementation status in the new project: DONE,
     PARTIAL, or NOT STARTED. For PARTIAL items, describe precisely what exists and
     what's missing. For every item that is NOT DONE, produce a task entry with enough
     context for an implementer to start working. Reference the inventory detail file
     for full specifications."**
5. **Wait for the batch to finish** before spawning the next batch.
6. **Batch-level hard stop (every 2 batches).** After completing every 2nd batch,
   the orchestrator MUST perform a hard stop. See `references/context-management.md`
   § "Batch-Level Hard Stop Protocol." Update `.progress.json` (or scan raw output
   files for resume) so the command resumes at the next batch when re-invoked.

Use Sonnet for teammates. The lead (Opus) handles coordination and the final merge.

### 3c: Monitor Progress

While teammates work:
1. Monitor progress via `TaskList`.
2. After each batch completes, verify output files exist and are non-empty.
3. If a teammate fails, re-queue the feature area for the next batch.

## Step 4: Merge and Produce Final Output

After all teammates complete:

### 4a: Read all raw gap reports

Read each `./docs/gap-analysis/raw/{feature-id}.md` file.

### 4b: Build the consolidated gap analysis

Write `./docs/gap-analysis/GAP-ANALYSIS.md`:

```markdown
# Gap Analysis

> Comparing: {new project name/path}
> Against: {inventory product name}
> Generated: {date}
> Inventory source: {inventory path}

## Summary

| Metric | Count |
|--------|-------|
| Total features in inventory | {N} |
| Fully implemented (DONE) | {N} ({%}) |
| Partially implemented (PARTIAL) | {N} ({%}) |
| Not started (NOT STARTED) | {N} ({%}) |
| Total tasks generated | {N} |

## Coverage by Feature Area

| Feature Area | Sub-features | Behaviors | Done | Partial | Not Started | Coverage |
|--------------|-------------|-----------|------|---------|-------------|----------|
| F-001: User Management | 8 | 45 | 20 | 10 | 15 | 67% |
| F-002: Billing | 5 | 30 | 0 | 0 | 30 | 0% |
| ... | ... | ... | ... | ... | ... | ... |

## Implementation Status Detail

### F-001: User Management

#### DONE
- [x] F-001.01.01: Email format validation
- [x] F-001.01.02: Duplicate email check
{... list all completed items}

#### PARTIAL
- [ ] **F-001.01.03: Password strength requirements** - PARTIAL
  - Implemented: minimum length check (8 chars)
  - Missing: special character requirement, number requirement
  - Spec: [F-001.01.03](./path/to/details/F-001.01.03.md)

#### NOT STARTED
- [ ] F-001.01.04: Welcome email trigger - [spec](./path/to/details/F-001.01.04.md)
- [ ] F-001.01.05: Default role assignment - [spec](./path/to/details/F-001.01.05.md)

{Repeat for each feature area}

## Task List

Actionable tasks derived from all gaps, ordered by the inventory's suggested build
order (dependency-aware). Each task references the inventory detail file that serves
as its implementation specification.

### Phase 1: Foundation (no dependencies)

| # | Task | Feature ID | Type | Complexity | Spec |
|---|------|-----------|------|------------|------|
| 1 | {Implement/Complete} {behavior name} | F-003.01.01 | NOT STARTED | low | [spec](./details/F-003.01.01.md) |
| 2 | {Complete} {behavior name} - {what's missing} | F-003.01.02 | PARTIAL | medium | [spec](./details/F-003.01.02.md) |

### Phase 2: Core Features (depends on Phase 1)

| # | Task | Feature ID | Type | Complexity | Spec |
|---|------|-----------|------|------------|------|
| ... | ... | ... | ... | ... | ... |

{Continue for each phase from the inventory's build order}

## Cross-Cutting Gaps

{Any patterns that are systematically missing across features:
e.g., "No error handling implemented anywhere", "Auth checks missing on all endpoints",
"No test files found for any feature"}

## Notes

{Any observations about the new project's architecture, patterns that differ from
the inventory's assumptions, or structural decisions that affect how tasks should
be approached}
```

### 4c: Write JSON version

Write `./docs/gap-analysis/GAP-ANALYSIS.json`:

```json
{
  "generated_at": "ISO-8601",
  "inventory": {
    "path": "/path/to/feature-inventory-output",
    "product": "from inventory",
    "total_features": 432
  },
  "new_project": {
    "path": "/path/to/new-project",
    "tech_stack": ["typescript", "react"]
  },
  "summary": {
    "done": 120,
    "partial": 45,
    "not_started": 267,
    "coverage_percent": 33.1,
    "total_tasks": 312
  },
  "feature_areas": [
    {
      "id": "F-001",
      "name": "User Management",
      "coverage_percent": 67,
      "items": [
        {
          "id": "F-001.01.01",
          "name": "Email format validation",
          "tier": "behavior",
          "status": "done",
          "detail_file": "details/F-001.01.01.md"
        },
        {
          "id": "F-001.01.03",
          "name": "Password strength requirements",
          "tier": "behavior",
          "status": "partial",
          "implemented": "minimum length check (8 chars)",
          "missing": "special character requirement, number requirement",
          "detail_file": "details/F-001.01.03.md"
        },
        {
          "id": "F-001.01.04",
          "name": "Welcome email trigger",
          "tier": "behavior",
          "status": "not_started",
          "detail_file": "details/F-001.01.04.md"
        }
      ]
    }
  ],
  "tasks": [
    {
      "number": 1,
      "phase": 1,
      "feature_id": "F-003.01.01",
      "name": "Implement email service configuration",
      "type": "not_started",
      "complexity": "low",
      "detail_file": "details/F-003.01.01.md",
      "depends_on": [],
      "description": "Full implementation needed. See spec for complete requirements."
    },
    {
      "number": 2,
      "phase": 1,
      "feature_id": "F-003.01.02",
      "name": "Complete SMTP retry logic",
      "type": "partial",
      "complexity": "medium",
      "detail_file": "details/F-003.01.02.md",
      "depends_on": ["F-003.01.01"],
      "implemented": "Basic send functionality exists",
      "missing": "Retry logic with exponential backoff, dead letter queue",
      "description": "Partial implementation exists. Add retry logic with exponential backoff and dead letter queue handling. See spec for full requirements."
    }
  ],
  "cross_cutting_gaps": [
    "No error handling patterns implemented",
    "Auth middleware not yet created"
  ]
}
```

## Step 5: Present Summary

Present a concise summary to the user:

```
Gap Analysis Complete
=====================

Project: {new project path}
Inventory: {product name} ({inventory path})

Coverage: {N}% ({done}/{total} behaviors implemented)
  - Done: {N} behaviors
  - Partial: {N} behaviors
  - Not started: {N} behaviors

Tasks generated: {N}
  - Phase 1 (foundation): {N} tasks
  - Phase 2 (core): {N} tasks
  - Phase 3+: {N} tasks

Cross-cutting gaps: {N} patterns identified

Output:
  - Human-readable: ./docs/gap-analysis/GAP-ANALYSIS.md
  - Machine-readable: ./docs/gap-analysis/GAP-ANALYSIS.json
  - Raw analysis: ./docs/gap-analysis/raw/
```

### Orchestrator Progress File

Maintain `./docs/gap-analysis/.progress.json` throughout the workflow:

```json
{
  "command": "gap-analysis",
  "current_step": "3",
  "batch_number": 2,
  "batches_total": 4,
  "completed_features": ["F-001", "F-002", "F-003"],
  "pending_features": ["F-004", "F-005"],
  "failed_features": [],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Update after every batch completes. On resume, read this FIRST.

## Resume Behavior

On every run, first **check for `.progress.json`**. If it exists, read it to determine
exactly where the previous run stopped. Fall back to scanning raw output files if no
progress file exists.

If re-run after `/clear` or interruption:
- Step 0: Always validate inventory (quick).
- Step 1: Skip if `new-project-discovery.json` exists.
- Step 2: Skip if `plan.json` exists.
- Step 3: Use `.progress.json` to skip completed feature areas and resume from the
  exact batch that was in progress. Fall back to scanning raw output files if no
  progress file exists.
- Step 4: Always re-run to regenerate merged output from all raw files.
