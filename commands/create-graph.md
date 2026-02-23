---
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: >
  Graph-based feature inventory pipeline. Builds a code reference index, hunts for indirect
  connections, constructs an outcome graph, annotates pathways with dimensions, and derives
  features from outcomes. Produces the same feature detail files as /feature-inventory:create
  but discovers features bottom-up from the code graph rather than top-down from dimension
  analysis. REQUIRES Agent Teams to be enabled.
  Run: /feature-inventory:create-graph [path]
---

# Feature Inventory (Graph Pipeline) - Orchestrator

## PREREQUISITE: Agent Teams Required

**Before doing anything else**, verify that Agent Teams is available:

1. Run: `echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
2. If the value is NOT "1", **stop immediately** and tell the user:

   > **This plugin requires Claude Code Agent Teams.**
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

3. Also verify you have access to the `TeamCreate` tool. If you attempt to call it
   and it's not available, stop with the same error message above.

---

You are the orchestrator for a graph-based product reverse-engineering effort. Unlike the
dimension-analysis approach, this pipeline discovers features BOTTOM-UP:

1. **Index** every symbol in the codebase (mechanical, exhaustive)
2. **Hunt** for every indirect connection (events, IPC, pub/sub, reactive chains, etc.)
3. **Build** the outcome graph (entry points → pathways → final outcomes)
4. **Annotate** each pathway with dimensional information (data, auth, logic, UI, config, side effects)
5. **Derive** features from annotated pathways (cluster, name, describe, link)

The result is the same feature hierarchy (F-001.md, F-001.01.md, F-001.01.01.md) but
discovered from what the code DOES (outcomes) rather than how it's structured (dimensions).
This produces outcome-focused features that free the re-implementor from replicating
the legacy architecture.

## Important: Context Window Management

**A "prompt is too long" error is CATASTROPHIC.** Follow the same context management
protocols as the standard create pipeline. See `references/context-management.md` for:
- Batch-level hard stops (every 2 batches)
- Step-boundary checkpoints
- Context watchdog integration
- Orchestrator progress file

## Step 0: User Interview

**Identical to the standard pipeline.** Interview the user to understand the product,
its major functional areas, tech stack, external services, and tribal knowledge.

If `./docs/features/interview.md` already exists, read it, summarize what you already
know, and ask only if there are gaps. Don't re-interview.

Save answers to `./docs/features/interview.md` and the user-provided feature map to
`./docs/features/user-feature-map.md`.

### Context Checkpoint: After Interview

**MANDATORY.** Follow the Context Checkpoint Protocol in `references/context-management.md`.

## Step 1: Discovery

**Identical to the standard pipeline.** Scan the codebase to identify repositories,
languages, frameworks, size, module structure, and vendor/generated code patterns.

Write discovery results to `./docs/features/discovery.json`.

### Context Checkpoint: After Discovery

**MANDATORY.** Follow the Context Checkpoint Protocol in `references/context-management.md`.

## Step 2: Plan

Based on discovery AND the user interview, create an analysis plan tailored for the
graph pipeline. The plan determines how to split the indexing and connection-hunting
work across agent teams.

```json
{
  "pipeline": "graph",
  "repos": [
    {
      "name": "repo-name",
      "path": "/absolute/path",
      "languages": ["typescript", "csharp"],
      "frameworks": ["express", "react", "electron"],
      "size": "large",
      "modules": ["src/main", "src/renderer", "src/shared"],
      "indexing_splits": [
        {
          "scope": "src/main",
          "estimated_files": 45,
          "estimated_lines": 8500,
          "output": "intermediate/index--main.jsonl"
        },
        {
          "scope": "src/renderer",
          "estimated_files": 78,
          "estimated_lines": 15200,
          "output": "intermediate/index--renderer.jsonl"
        },
        {
          "scope": "src/shared",
          "estimated_files": 23,
          "estimated_lines": 4100,
          "output": "intermediate/index--shared.jsonl"
        }
      ],
      "connection_hunting_strategy": "per_file",
      "connection_hunting_note": "File assignments determined after indexing (Step 3d) by querying connection_hints table and grepping for connection patterns. Each agent gets ONE file."
    }
  ],
  "exclude_patterns": ["node_modules", "vendor", ".Designer.cs"]
}
```

### Splitting Strategy

**Target: each teammate should complete in ~5 minutes.**

For indexing:
- Split by module/directory, aiming for ~5,000-10,000 lines per teammate.
- Very large files (>1,000 lines) get their own dedicated indexing task.

For connection hunting:
- Split by FILE, not by connection type. Each agent gets ONE file and hunts for
  ALL connection types in or out of that file. The agent knows exactly what strings
  to Grep for (event names, channel names, topic strings) so cross-module matching
  is fast — bounded by the patterns in that one file, not by scanning the entire
  codebase for every pattern category.
- File assignments are determined AFTER indexing completes (Step 3d), by querying
  the `connection_hints` table and grepping for known connection patterns. Only files
  with connection patterns get an agent — pure logic files are skipped.
- Connections span files and will be discovered from both ends (the emitter file's
  agent and the listener file's agent). The merge step deduplicates.

Write to `./docs/features/plan.json`.

### Context Checkpoint: After Planning

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Step 3 (indexing) is context-intensive.

## Step 3: Build Enriched Index (Phase 1)

**Delegate to `commands/build-index.md`.**

This step produces the enriched code reference index: every symbol indexed via
tree-sitter, every indirect connection hunted per-file, user interview for unresolved
connections, and the call graph enriched with indirect edges.

Read and follow `commands/build-index.md`. When it completes, `graph.db` contains the
full enriched call graph — direct calls AND indirect connections — ready for graph
construction.

**Do NOT proceed to Step 4 until `build-index.md` reports the enriched index is complete.**

### Context Checkpoint: After Phase 1

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Step 4 (graph building) needs headroom.

Preserved files: everything from previous steps, enriched `graph.db`,
`intermediate/index--*.jsonl`, `intermediate/connections--*.jsonl`

## Step 4: Build Outcome Graph (Phase 2)

**Delegate to `commands/build-graph.md`.**

This step constructs the outcome graph from the enriched index: identifies entry points
and final outcomes, traces pathways between them, validates the graph, and interviews
the user about orphans, unreachable outcomes, and graph gaps.

Read and follow `commands/build-graph.md`. When it completes, `graph.db` contains the
full outcome graph — entry points, pathways, final outcomes, fan-out points — ready for
pathway annotation.

**Do NOT proceed to Step 5 until `build-graph.md` reports the outcome graph is complete.**

### Context Checkpoint: After Phase 2

**MANDATORY — CLEAR STRONGLY RECOMMENDED.**

Preserved files: everything from previous steps + graph tables in `graph.db`

## Step 5: Annotate Pathways (Phase 3)

**Delegate to `commands/annotate-pathways.md`.**

This step annotates every pathway with dimensional information: data, auth, logic, UI,
config, and side effects — extracted from source code at each pathway step.

Read and follow `commands/annotate-pathways.md`. When it completes, `graph.db` contains
dimensional annotations on every pathway — ready for feature derivation.

**Do NOT proceed to Step 6 until `annotate-pathways.md` reports annotation is complete.**

### Context Checkpoint: After Phase 3

**MANDATORY — CLEAR STRONGLY RECOMMENDED.**

Preserved files: everything from previous steps + annotations merged in `graph.db`

## Step 6: Derive Features, Build Index & Validate (Phase 4)

**Delegate to `commands/derive-features.md`.**

This step clusters pathways into feature areas, spawns feature derivation agents,
interviews the user for quality resolution, builds the feature index, and validates
full coverage.

Read and follow `commands/derive-features.md`. When it completes, the full feature
inventory exists: detail files (`F-*.md`), navigable index (`FEATURE-INDEX.md`),
and machine-readable index (`FEATURE-INDEX.json`).

**This is the final phase. When `derive-features.md` reports completion, the pipeline
is done.**

## Resume Behavior

On every run, first **check for `.progress.json`**. If it exists, read it to determine
exactly where the previous run stopped.

Then **auto-clear derived artifacts** that are always regenerated:

```bash
rm -f ./docs/features/feature-clustering.json
rm -f ./docs/features/FEATURE-INDEX.md
rm -f ./docs/features/FEATURE-INDEX.json
```

**Do NOT clear:**
- `.progress.json` — resume state (cleared only after Step 6 completes)
- `graph.db` — the SQLite database (index, connections, graph, annotations). This is
  the most expensive artifact. Incremental steps update it in place.
- `intermediate/` — JSONL teammate output (can be deleted after merge into SQLite,
  but kept for debugging and re-merge if needed)
- `details/` — verify mode patches incrementally
- `interview.md`, `user-feature-map.md`, `clarifications.md`, `clarifications-features.md`
- `discovery.json`, `plan.json`

Resume rules:
- Step 0: Skip if `interview.md` exists.
- Step 1: Skip if `discovery.json` exists.
- Step 2: Re-run unless `plan.json` exists and discovery hasn't changed.
- Step 3 (Phase 1 — enriched index): Delegates to `build-index.md` which tracks its
  own progress in the `indexing` and `connection_hunting` sections of `.progress.json`.
  See `build-index.md` for detailed resume rules.
- Step 4 (Phase 2 — outcome graph): Delegates to `build-graph.md` which tracks its
  own progress in the `graph_building` section of `.progress.json`.
  See `build-graph.md` for detailed resume rules.
- Step 5 (Phase 3 — annotation): Delegates to `annotate-pathways.md` which tracks its
  own progress in the `annotation` section of `.progress.json`.
  See `annotate-pathways.md` for detailed resume rules.
- Step 6 (Phase 4 — derivation + index + validation): Delegates to `derive-features.md`
  which tracks its own progress in the `feature_derivation` section of `.progress.json`.
  See `derive-features.md` for detailed resume rules.

## Progress File Schema

```json
{
  "command": "create-graph",
  "current_step": "5",
  "current_substep": "annotate",
  "batch_number": 2,
  "batches_total": 4,

  "indexing": {
    "completed_splits": ["index--main", "index--shared"],
    "pending_splits": ["index--renderer"],
    "failed_splits": [],
    "merged_to_sqlite": false
  },

  "connection_hunting": {
    "total_files": 45,
    "completed_files": ["src/services/order.ts", "src/handlers/ipc-handlers.ts"],
    "pending_files": ["src/events/emitter.ts", "src/middleware/auth.ts"],
    "failed_files": [],
    "user_interview_done": false,
    "merged_to_sqlite": false,
    "call_graph_enriched": false
  },

  "enriched_index_complete": true,

  "graph_building": {
    "completed": false,
    "validation_interview_done": false
  },

  "annotation": {
    "completed_groups": ["EP-001-group", "EP-010-group"],
    "pending_groups": ["EP-015-group", "EP-020-group"],
    "failed_groups": [],
    "merged_to_sqlite": false
  },

  "feature_derivation": {
    "completed_features": ["F-001", "F-002"],
    "pending_features": ["F-003", "F-004"],
    "failed_features": [],
    "user_resolution_done": false
  },

  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Reusing Artifacts from Previous Pipeline Runs

If the standard `/feature-inventory:create` pipeline was run previously, several artifacts
can be consumed by the graph pipeline to save time and improve quality:

### Directly Reusable (skip the step entirely)

| Artifact | Graph Pipeline Step | Notes |
|----------|-------------------|-------|
| `interview.md` | Step 0 (Interview) | Same questions, same answers. Skip the interview entirely. |
| `user-feature-map.md` | Step 0 (Interview) | The user's mental model is input to feature clustering (`derive-features.md` Step 1). |
| `discovery.json` | Step 1 (Discovery) | Repo structure hasn't changed. Skip discovery. |
| `clarifications.md` | Phase 1 + 2 | Previous user clarifications about dead code, external services, and ambiguous connections are still valid. Used by `build-index.md` and `build-graph.md`. |

### Cross-Reference Material (don't skip, but use as validation)

| Artifact | How the Graph Pipeline Uses It |
|----------|-------------------------------|
| `raw/` dimension outputs | After Phase 4 derives features, compare the graph-derived features against the raw dimension analysis outputs from the previous run. Mismatches reveal either: (a) dimensions the graph missed (missing connections), or (b) dimension analysis that was wrong (top-down misattribution). This cross-reference is the strongest validation that the graph pipeline captured everything. |
| Previous `details/` files | Don't import these — they're structured around the old pipeline's dimension-based hierarchy. But read them during `derive-features.md` Step 3 (user resolution) to verify that every previously-documented behavior appears somewhere in the new graph-derived features. Any behavior that appeared in the old pipeline but NOT in the graph pipeline is a red flag: either a missed connection or a false positive from the original analysis. |
| Previous `FEATURE-INDEX.json` | During `derive-features.md` Step 5 (validation), compare the old feature list against the new one. Every feature in the old index should map to at least one feature in the new index (possibly renamed or restructured). Document any features that were present in the old pipeline but absent in the new one — these require user confirmation. |

### Not Reusable

| Artifact | Why |
|----------|-----|
| Previous `plan.json` | The graph pipeline has fundamentally different splitting logic (index by directory vs. analyze by feature area). |
| Previous `.progress.json` | Different step structure. |

### How to Detect Previous Run Artifacts

At the start of Step 0, check for the existence of previous-run artifacts:

```bash
# Check for reusable artifacts
ls ./docs/features/interview.md 2>/dev/null && echo "interview: reusable"
ls ./docs/features/user-feature-map.md 2>/dev/null && echo "feature-map: reusable"
ls ./docs/features/discovery.json 2>/dev/null && echo "discovery: reusable"
ls ./docs/features/clarifications.md 2>/dev/null && echo "clarifications: reusable"

# Check for cross-reference material
ls ./docs/features/raw/ 2>/dev/null && echo "raw dimensions: available for cross-reference"
ls ./docs/features/details/F-*.md 2>/dev/null && echo "previous features: available for cross-reference"
ls ./docs/features/FEATURE-INDEX.json 2>/dev/null && echo "previous index: available for cross-reference"
```

If previous-run artifacts are found, present to the user:

```
Previous Pipeline Artifacts Found
===================================
Reusable (will skip these steps):
  ✓ interview.md — User interview answers
  ✓ user-feature-map.md — User's mental model
  ✓ discovery.json — Repository scan results
  ✓ clarifications.md — Previous ambiguity resolutions

Cross-reference material (will validate against):
  ✓ raw/ — Previous dimension analysis outputs
  ✓ details/ — Previous feature detail files
  ✓ FEATURE-INDEX.json — Previous feature index

The graph pipeline will build the index and graph from scratch but will
cross-reference its results against the previous analysis to catch gaps.

Proceed? [Y/n]
```
