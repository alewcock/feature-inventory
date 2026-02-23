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
          "output": "index/code-reference-index--main.json"
        },
        {
          "scope": "src/renderer",
          "estimated_files": 78,
          "estimated_lines": 15200,
          "output": "index/code-reference-index--renderer.json"
        },
        {
          "scope": "src/shared",
          "estimated_files": 23,
          "estimated_lines": 4100,
          "output": "index/code-reference-index--shared.json"
        }
      ],
      "connection_hunting_splits": [
        {
          "connection_types": ["event", "ipc", "reactive"],
          "scope": "full",
          "output": "connections/connections--events-ipc-reactive.json"
        },
        {
          "connection_types": ["db_hook", "middleware_chain", "di_binding", "convention"],
          "scope": "full",
          "output": "connections/connections--framework.json"
        },
        {
          "connection_types": ["pubsub", "webhook", "dispatch_table", "file_watcher", "signal"],
          "scope": "full",
          "output": "connections/connections--external.json"
        }
      ]
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
- Split by connection TYPE, not by directory. Connection hunting must search the
  entire codebase for matching string keys — splitting by directory would miss
  cross-module connections.
- Group related connection types (events + IPC + reactive are all "indirect
  invocation"; middleware + DI + convention are all "framework wiring").

Write to `./docs/features/plan.json`.

### Context Checkpoint: After Planning

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Step 3 (indexing) is context-intensive.

## Step 3: Build Code Reference Index via Agent Teams

### 3a: Create the Team

Use `TeamCreate` to create a team named "feature-inventory-graph". Enable delegate mode.

### 3b: Spawn Indexing Teammates in Batches

For each indexing split in the plan:

1. **Check for existing output:** If the split's output file exists and is non-empty, skip.
2. **Create tasks** via `TaskCreate` for each pending split.
3. **Spawn teammates in batches of up to 5.** Each teammate gets ONE scope for ONE repo.
   Assign them the `feature-inventory:code-indexer` agent.
4. **Each teammate receives** via its task description:
   - The repo path, scope, and output path from the plan
   - The languages and frameworks detected
   - A pointer to read `references/context-management.md` before starting
   - This instruction verbatim: **"Index every named symbol in your scope: functions,
     classes, methods, routes, constants, types, variables, imports. Record definitions,
     call sites, signatures, and exports. Write to disk after every file. Flag dynamic
     dispatch, framework magic, and reflection for the connection hunter. Do NOT interpret
     meaning — only record structure."**
5. **Wait for each batch** before spawning the next.
6. **Update `.progress.json`** after each batch.
7. **Batch-level hard stop (every 2 batches).** See `references/context-management.md`.

### 3c: Merge Indexes

After all indexing teammates complete:

1. Read all split index files.
2. Merge into a single `./docs/features/index/code-reference-index.json`.
3. Run the cross-reference pass: resolve `called_by` edges across splits, resolve
   imports across module boundaries, reconcile duplicate symbol references.
4. Collect all `connection_hints` from the split files into the merged index.
5. Write the manifest file `./docs/features/index/code-reference-index-manifest.json`.

**This merge can be done by the orchestrator** if the splits are small enough (total
index entries < 2000). For larger indexes, spawn a dedicated merge teammate.

### 3d: Index Validation

Quick sanity checks on the merged index:
- Every import resolves to an actual file
- Symbol counts are proportional to file sizes (a 500-line file should have >5 symbols)
- No files in scope were missed (compare against discovery.json file counts)

Present index summary:
```
Code Reference Index — Complete
================================
Files indexed: {N} ({total lines})
Symbols found: {N}
  Functions: {N}  Classes: {N}  Methods: {N}  Routes: {N}
  Constants: {N}  Types: {N}  Variables: {N}
Imports: {N}
Connection hints (for hunter): {N}
  Dynamic calls: {N}  Framework magic: {N}  Reflection: {N}
```

### Context Checkpoint: After Indexing

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Step 4 spawns connection hunters.

Preserved files: `interview.md`, `user-feature-map.md`, `discovery.json`, `plan.json`,
`index/*`

## Step 4: Hunt Indirect Connections via Agent Teams

### 4a: Spawn Connection Hunters in Batches

For each connection hunting split in the plan:

1. **Check for existing output.** Skip if already done.
2. **Create tasks** for pending splits.
3. **Spawn teammates in batches of up to 5.** Each teammate gets a set of connection
   types to hunt for across the full repo. Assign them the
   `feature-inventory:connection-hunter` agent.
4. **Each teammate receives:**
   - The repo path and full scope
   - The merged code reference index path
   - The connection types to hunt for (from the plan split)
   - The `connection_hints` array relevant to their connection types
   - Output path for their findings
   - This instruction verbatim: **"Be relentless. Hunt for every instance of your
     assigned connection types across the entire codebase. Match every emitter to its
     listeners, every publisher to its subscribers, every IPC sender to its handler.
     When you can't make a connection, write it as unresolved with a specific question
     for the user. Do NOT guess. A missed connection means a broken feature in the
     rebuild."**
5. **Batch-level hard stop (every 2 batches).**

### 4b: Merge Connections

After all hunters complete:
1. Merge all split connection files into `./docs/features/connections/connections.json`.
2. Collect all unresolved items into `./docs/features/connections/unresolved-connections.json`.

### 4c: User Interview for Unresolved Connections

If there are unresolved connections, present them to the user in batches of 5-10:

```
Connection Resolution Interview
=================================
The connection hunter found {N} indirect connections and couldn't resolve {M}:

1. Event 'sync.complete' is emitted from src/services/sync.ts:89 but no listener
   was found in this codebase.
   → Is there an external consumer? [External service / Dead code / Explain]

2. Route GET /admin/debug/cache has no observable side effects.
   → Is this a developer tool? [Dev tool / Dead code / Missing link / Explain]

3. Plugin loader uses dynamic dispatch: plugins[name].execute(context)
   → What plugins exist? [List them / Config file location / Not used]
```

Save resolutions to `./docs/features/clarifications.md`. Re-run connection hunting
for any "Explain" or "Missing link" responses that reveal new patterns to search for.

### 4d: Merge Connections Back into Index

Update `code-reference-index.json` with the discovered connections:
- Event emitters get listener references in their `calls` array
- Listeners get emitter references in their `called_by` array
- IPC handlers get sender references
- DI consumers get concrete implementation references
- Middleware chains create ordered call edges

This produces the **enriched code reference index** that the graph builder consumes.

### Context Checkpoint: After Connection Hunting

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Step 5 (graph building) needs headroom.

Preserved files: everything from previous steps + `connections/*`,
enriched `index/code-reference-index.json`

## Step 5: Build Outcome Graph

### 5a: Spawn Graph Builder

The graph builder is a single-agent task (it needs a holistic view of the codebase,
not a per-module view). Spawn ONE teammate with the
`feature-inventory:graph-builder` agent.

**The teammate receives:**
- Path to the enriched code reference index
- Path to the connections file
- Output path: `./docs/features/graph/outcome-graph.json`
- Product context from interview

**If the index is very large (>5000 symbols)**, split the graph builder into two phases:
1. Phase 1 teammate: Identify all entry points and all final outcomes (from the index).
   Write to `graph/entry-points.json` and `graph/final-outcomes.json`.
2. Phase 2 teammates: Trace pathways — one per entry point group (by API resource,
   by UI page, by job scheduler, etc.), batched in groups of 5.

### 5b: Graph Validation & User Interview

Read the graph builder's output. Check the validation section for:

- **Orphan entry points** → ALWAYS present to user for interview
- **Unreachable outcomes** → ALWAYS present to user for interview
- **Graph gaps** → Present to user if likely meaningful (not pure infrastructure)

```
Outcome Graph — Validation
============================
Entry points: {N}
Final outcomes: {N}
Pathways: {N}
Fan-out points: {N}
Index coverage: {pct}%

Issues found: {N}
  Orphan entry points: {N} — need user input
  Unreachable outcomes: {N} — need user input
  Graph gaps: {N} — likely missing connections

{Present each issue with question for user}
```

After user responses, update the graph (add missing connections, mark dead code,
re-trace affected pathways).

### Context Checkpoint: After Graph Building

**MANDATORY — CLEAR STRONGLY RECOMMENDED.**

Preserved files: everything from previous steps + `graph/*`

## Step 6: Annotate Pathways via Agent Teams

### 6a: Spawn Pathway Annotators in Batches

Group pathways by entry point for annotation (pathways from the same entry point share
early steps). Each teammate gets a set of pathways sharing an entry point group.

1. **Create tasks** for each pathway group.
2. **Spawn teammates in batches of up to 5.** Assign them the
   `feature-inventory:pathway-dimension-annotator` agent.
3. **Each teammate receives:**
   - Their assigned pathway group (pathway objects from the graph)
   - Path to the code reference index
   - Path to the connections file
   - Repo path (for reading source code at indexed locations)
   - Output path for annotated pathways
   - This instruction verbatim: **"For each pathway, read the source code at each
     step (using the index to find exact line ranges) and extract: what data is
     read/written, what auth is checked, what business logic is applied, what UI is
     rendered, what config is consumed, what side effects are triggered. Every
     annotation must have a source_map reference. Capture exact values: error messages
     verbatim, constant values exact, validation rules precise."**
4. **Batch-level hard stop (every 2 batches).**

### 6b: Merge Annotated Pathways

Merge all teammate outputs into `./docs/features/annotated/annotated-pathways.json`.
Write annotation statistics to `./docs/features/annotated/annotation-stats.json`.

Present summary:
```
Pathway Annotation — Complete
===============================
Pathways annotated: {N}
Total annotations: {N}
  Data: {N}  Auth: {N}  Logic: {N}  UI: {N}  Config: {N}  Side Effects: {N}
Ambiguities flagged: {N}
```

### Context Checkpoint: After Annotation

**MANDATORY — CLEAR STRONGLY RECOMMENDED.**

Preserved files: everything from previous steps + `annotated/*`

## Step 7: Derive Features via Agent Teams

### 7a: Initial Clustering (Orchestrator — lightweight)

Before spawning feature derivation teammates, the orchestrator does a quick clustering
pass to assign pathways to major feature areas:

1. Read `user-feature-map.md` for the user's mental model.
2. Read the graph's entry points and final outcomes (summary, not full pathways).
3. Group entry points by API resource, UI page, job type, etc.
4. Map groups to the user's feature areas.
5. Identify unclaimed pathways → new feature areas or cross-cutting concerns.
6. Write initial clustering to `./docs/features/feature-clustering.json`:

```json
{
  "clusters": [
    {
      "feature_id": "F-001",
      "feature_name": "Order Management",
      "pathway_ids": ["PW-001", "PW-002", "PW-003", ...],
      "entry_point_ids": ["EP-001", "EP-010", "EP-015"],
      "source": "user_feature_map + graph entry points"
    }
  ],
  "unclaimed_pathways": ["PW-089", "PW-090"],
  "cross_cutting": ["PW-200", "PW-201"]
}
```

### 7b: Spawn Feature Derivation Teammates in Batches

For each cluster:

1. **Create tasks** for each major feature area.
2. **Spawn teammates in batches of up to 5.** Each teammate gets ONE major feature area.
   Assign them the `feature-inventory:feature-deriver` agent.
3. **Each teammate receives:**
   - Their assigned cluster (feature ID, name, pathway IDs)
   - Path to annotated pathways
   - Path to outcome graph
   - Path to code reference index
   - Path to interview.md and user-feature-map.md
   - Output path: `./docs/features/details/`
   - This instruction verbatim: **"Derive features from outcomes, not implementations.
     Each pathway traces what the system DOES — cluster related pathways into
     sub-features, name each by what users ACHIEVE, describe the outcome not the
     mechanism. Every behavior file needs source maps back to the code index so
     re-implementors can reference the legacy approach without being constrained by it.
     A feature description should tell a developer what to build. Source maps tell
     them how it was built before."**
4. **Batch-level hard stop (every 2 batches).**

### 7c: User Resolution Interview

After all feature derivation teammates complete, scan detail files for quality issues
using the same criteria as the standard pipeline's Step 4.5:
- Thin specs
- Overlapping features
- Unresolved ambiguities
- Orphan behaviors

Present candidates to the user and apply resolutions (define, merge, remove, clarify).
See the standard pipeline's Step 4.5b-e for the full interview protocol.

Save resolutions to `./docs/features/clarifications-features.md`.

### Context Checkpoint: After Feature Derivation

**MANDATORY — CLEAR STRONGLY RECOMMENDED.**

## Step 8: Build Index

**Identical to the standard pipeline's Step 4c.** Enumerate all detail files, build
the hierarchy, write FEATURE-INDEX.md and FEATURE-INDEX.json.

The JSON index includes additional graph metadata: pathway references, entry point IDs,
final outcome IDs, and source map symbol IDs. See `references/graph-output-format.md`.

## Step 9: Validation & Summary

1. **Graph coverage check:** Every pathway must appear in exactly one feature.
   Report any unclaimed or duplicate-claimed pathways.

2. **Entry point coverage:** Every entry point must appear in at least one feature.

3. **Final outcome coverage:** Every final outcome must appear in at least one behavior.

4. **Cross-check against user's feature map.** Every user-mentioned feature should appear.

5. **Index integrity:** Every source map reference should resolve to a valid symbol in
   the code reference index.

6. **Present summary:**
```
Feature Inventory (Graph Pipeline) — Complete
===============================================
Code Reference Index: {N} symbols across {N} files
Indirect Connections: {N} found ({N} resolved from user interview)
Outcome Graph: {N} entry points → {N} pathways → {N} final outcomes
Fan-out points: {N}
Infrastructure symbols: {N}
Dead code identified: {N} symbols

Features derived:
  Major features: {N}
  Sub-features: {N}
  Behaviors: {N}

Coverage:
  Pathways claimed by features: {N}/{N} ({pct}%)
  Entry points in features: {N}/{N} ({pct}%)
  Final outcomes in behaviors: {N}/{N} ({pct}%)
  Index symbols on pathways: {N}/{N} ({pct}%)

Ambiguities: {N} resolved, {N} unresolved

Output files:
  Code reference index: docs/features/index/code-reference-index.json
  Connections: docs/features/connections/connections.json
  Outcome graph: docs/features/graph/outcome-graph.json
  Annotated pathways: docs/features/annotated/annotated-pathways.json
  Feature details: docs/features/details/F-*.md
  Feature index: docs/features/FEATURE-INDEX.md
  Feature index (JSON): docs/features/FEATURE-INDEX.json
```

7. **Ask the user** to review the index and flag anything missing or miscategorized.

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
- `.progress.json` — resume state (cleared only after Step 9 completes)
- `index/` — expensive indexing output
- `connections/` — expensive connection hunting output
- `graph/` — expensive graph building output
- `annotated/` — expensive annotation output
- `details/` — verify mode patches incrementally
- `interview.md`, `user-feature-map.md`, `clarifications.md`, `clarifications-features.md`
- `discovery.json`, `plan.json`

Resume rules:
- Step 0: Skip if `interview.md` exists.
- Step 1: Skip if `discovery.json` exists.
- Step 2: Re-run unless `plan.json` exists and discovery hasn't changed.
- Step 3 (indexing): Use `.progress.json` to skip completed splits. Resume from
  exact batch. Fall back to scanning index split files.
- Step 3c-d (merge + validate): Re-run if any indexing splits were re-run.
- Step 4 (connections): Use `.progress.json` to skip completed splits. Resume from
  exact batch. Fall back to scanning connection split files.
- Step 4c (user interview): Skip if `clarifications.md` has connection resolutions.
  Re-run for new unresolved items only.
- Step 4d (merge into index): Re-run if connections changed.
- Step 5 (graph): Re-run if enriched index changed. Graph building is relatively
  cheap compared to indexing and connection hunting.
- Step 5b (validation interview): Re-run for new validation failures only.
- Step 6 (annotation): Use `.progress.json` to skip completed pathway groups.
  Resume from exact batch. Re-run for pathways that changed in graph re-building.
- Step 7 (feature derivation): Use `.progress.json` to skip completed feature areas.
  Re-run for features whose pathways changed.
- Step 7c (user resolution): Skip if `clarifications-features.md` exists. Re-run for
  affected features if derivation re-ran.
- Step 8-9: Always re-run (indexes were cleared).

## Progress File Schema

```json
{
  "command": "create-graph",
  "current_step": "4",
  "current_substep": "4a",
  "batch_number": 2,
  "batches_total": 4,

  "indexing": {
    "completed_splits": ["index--main", "index--shared"],
    "pending_splits": ["index--renderer"],
    "failed_splits": [],
    "merged": false
  },

  "connection_hunting": {
    "completed_splits": ["connections--events-ipc-reactive"],
    "pending_splits": ["connections--framework", "connections--external"],
    "failed_splits": [],
    "user_interview_done": false,
    "merged_into_index": false
  },

  "graph_building": {
    "completed": false,
    "validation_interview_done": false
  },

  "annotation": {
    "completed_groups": ["EP-001-group", "EP-010-group"],
    "pending_groups": ["EP-015-group", "EP-020-group"],
    "failed_groups": [],
    "merged": false
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
