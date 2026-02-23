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

### 3c: Create SQLite Database and Merge Indexes

After all indexing teammates complete:

1. **Create the SQLite database** at `./docs/features/graph.db` with the schema from
   `code-indexer.md` (tables: `metadata`, `symbols`, `calls`, `imports`,
   `file_manifest`, `connection_hints`).
2. **Parse each JSONL split file** and INSERT rows into the appropriate tables.
   Use `BEGIN TRANSACTION` / `COMMIT` per split file for performance.
3. **Run the cross-reference pass** in SQL:
   - Resolve `called_by` edges: for each row in `calls`, find the callee's `symbols.id`
     and update `callee_id`. Update `caller_count` on each symbol.
   - Resolve imports: match `imports.source` to `symbols.file` for within-project imports.
   - Reconcile duplicate references across splits (same symbol indexed from different scopes).
4. **Verify counts:** `SELECT COUNT(*) FROM symbols`, `SELECT COUNT(*) FROM calls`, etc.

**This merge can be done by the orchestrator** using Python's built-in `sqlite3` module
via the Bash tool:
```bash
python3 -c "
import sqlite3, json, glob
db = sqlite3.connect('./docs/features/graph.db')
# ... create tables, parse JSONL, insert rows, cross-reference ...
db.commit()
"
```

For very large codebases (>50,000 symbols), spawn a dedicated merge teammate.

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
`graph.db`, `intermediate/index--*.jsonl`

## Step 4: Hunt Indirect Connections via Agent Teams

### 4a: Determine Connection Hunting File Assignments

After indexing is complete, identify which files need connection hunting:

1. **Query the index** for files with connection hints:
   ```sql
   SELECT DISTINCT file FROM connection_hints WHERE resolved = 0;
   ```
2. **Grep the codebase** for known connection patterns not covered by tree-sitter
   hints (emit, subscribe, publish, ipcRenderer, postMessage, on(', once(', etc.).
   Record which files contain matches.
3. **Combine and deduplicate** into a file list. Only files with at least one
   connection pattern get an agent.
4. **Write the file list** to `intermediate/connection-hunting-files.json`:
   ```json
   [
     {"file": "src/services/order.ts", "hints_count": 3, "pattern_matches": 5,
      "output": "intermediate/connections--src-services-order-ts.jsonl"},
     {"file": "src/handlers/ipc-handlers.ts", "hints_count": 12, "pattern_matches": 8,
      "output": "intermediate/connections--src-handlers-ipc-handlers-ts.jsonl"}
   ]
   ```

Present summary:
```
Connection Hunting — File Assignments
=======================================
Files with connection patterns: {N} out of {total} indexed files
  Connection hints from tree-sitter: {N} files
  Grep pattern matches: {N} additional files
  Skipped (no connection patterns): {N} files

Estimated batches: {ceil(N/5)} (5 agents per batch)
```

### 4b: Spawn Per-File Connection Hunters in Batches

For each file in the connection hunting list:

1. **Check for existing output.** Skip if the file's JSONL output exists and has a
   summary line (indicating the agent completed).
2. **Create tasks** for pending files.
3. **Spawn teammates in batches of up to 5.** Each teammate gets ONE file. Assign
   them the `feature-inventory:connection-hunter` agent.
4. **Each teammate receives:**
   - The specific file path to hunt connections for
   - The repo path
   - The SQLite database path (`./docs/features/graph.db`)
   - The `connection_hints` for this file only
   - Output path for their findings
   - This instruction verbatim: **"Hunt every indirect connection in or out of your
     assigned file. For each connection pattern you find (event emit, IPC send,
     pub/sub publish, etc.), Grep the codebase for its counterpart. Document each
     connection as you find it. When you can't find a match, write it as unresolved
     with a specific question for the user. When you're done with your file, write
     a summary line and terminate."**
5. **Monitor agent liveness** using the heartbeat protocol (see
   `references/context-management.md`). Do NOT assume an agent is dead unless its
   output file has not been modified for 5+ minutes.
6. **Batch-level hard stop (every 2 batches).**

### 4c: Merge Connections into SQLite

After all hunters complete:
1. Parse each per-file JSONL output, skipping heartbeat and summary lines.
2. **Deduplicate connections** — the same connection (e.g., event emit→listen) will
   be discovered by both the emitter file's agent and the listener file's agent.
   Deduplicate by (connection_type, key_name, source_file, source_line, target_file,
   target_line).
3. INSERT into the `connections` and `unresolved_connections` tables in `graph.db`.

### 4d: User Interview for Unresolved Connections

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

### 4e: Enrich Call Graph in SQLite

INSERT indirect edges into the `calls` table with the appropriate `connection_type`:
```sql
INSERT INTO calls (caller_id, callee_id, callee_name, call_file, call_line, connection_type)
VALUES ('SYM-emitter', 'SYM-listener', 'handlerName', 'file.ts', 42, 'event');
```

Update `caller_count` on affected symbols. This produces the **enriched call graph**
that the graph builder consumes — direct calls AND indirect connections in the same table,
queryable with a single SQL query.

### Context Checkpoint: After Connection Hunting

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Step 5 (graph building) needs headroom.

Preserved files: everything from previous steps, enriched `graph.db`,
`intermediate/connections--*.jsonl`

## Step 5: Build Outcome Graph

### 5a: Spawn Graph Builder

The graph builder is a single-agent task (it needs a holistic view of the codebase,
not a per-module view). Spawn ONE teammate with the
`feature-inventory:graph-builder` agent.

**The teammate receives:**
- Path to the SQLite database (`./docs/features/graph.db`)
- Product context from interview

The graph builder adds its tables (`entry_points`, `final_outcomes`, `pathways`,
`pathway_steps`, `fan_out_points`, `infrastructure`, `graph_validation`) directly to
`graph.db`. No separate output file needed.

**If the index is very large (>5000 symbols)**, split the graph builder into two phases:
1. Phase 1 teammate: Identify all entry points and all final outcomes (SQL queries
   against `symbols` and `connections` tables). INSERT into `entry_points` and
   `final_outcomes` tables.
2. Phase 2 teammates: Trace pathways — one per entry point group (by API resource,
   by UI page, by job scheduler, etc.), batched in groups of 5. Each writes to
   `pathways` and `pathway_steps` tables.

### 5b: Graph Validation & User Interview

Query the `graph_validation` table for issues:

- **Orphan entry points** → ALWAYS present to user for interview
- **Unreachable outcomes** → ALWAYS present to user for interview
- **Graph gaps** → ALWAYS present to user for interview (classify as missing connection, dead code, or infrastructure)

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

Preserved files: everything from previous steps + graph tables in `graph.db`

## Step 6: Annotate Pathways via Agent Teams

### 6a: Spawn Pathway Annotators in Batches

Group pathways by entry point for annotation (pathways from the same entry point share
early steps). Each teammate gets a set of pathways sharing an entry point group.

1. **Create tasks** for each pathway group.
2. **Spawn teammates in batches of up to 5.** Assign them the
   `feature-inventory:pathway-dimension-annotator` agent.
3. **Each teammate receives:**
   - Their assigned pathway IDs
   - Path to the SQLite database (`./docs/features/graph.db`)
   - Repo path (for reading source code at indexed locations)
   - Output path for annotated pathways (JSONL intermediate)
   - This instruction verbatim: **"For each pathway, read the source code at each
     step (using the index to find exact line ranges) and extract: what data is
     read/written, what auth is checked, what business logic is applied, what UI is
     rendered, what config is consumed, what side effects are triggered. Every
     annotation must have a source_map reference. Capture exact values: error messages
     verbatim, constant values exact, validation rules precise."**
4. **Batch-level hard stop (every 2 batches).**

### 6b: Merge Annotated Pathways

After all annotators complete:
1. Parse each annotation JSONL split file.
2. INSERT into the `pathway_annotations` and `annotation_source_maps` tables in `graph.db`.
3. Write annotation statistics to the `metadata` table.

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

Preserved files: everything from previous steps + annotations merged in `graph.db`

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
   - Path to the SQLite database (`./docs/features/graph.db`)
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
  SQLite database: docs/features/graph.db
    (index, connections, graph, annotations — all queryable)
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
- Step 3 (indexing): Use `.progress.json` to skip completed splits. Resume from
  exact batch. Fall back to scanning index split files.
- Step 3c-d (merge + validate): Re-run if any indexing splits were re-run.
- Step 4a (file assignments): Re-run if indexing changed. Fast — just queries the index.
- Step 4b (per-file hunting): Use `.progress.json` to skip completed files. Resume from
  exact batch. Fall back to scanning per-file JSONL outputs for summary lines.
- Step 4d (user interview): Skip if `clarifications.md` has connection resolutions.
  Re-run for new unresolved items only.
- Step 4e (enrich call graph): Re-run if connections changed.
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
| `user-feature-map.md` | Step 0 (Interview) | The user's mental model is input to feature clustering (Step 7a). |
| `discovery.json` | Step 1 (Discovery) | Repo structure hasn't changed. Skip discovery. |
| `clarifications.md` | Steps 4c, 5b | Previous user clarifications about dead code, external services, and ambiguous connections are still valid. |

### Cross-Reference Material (don't skip, but use as validation)

| Artifact | How the Graph Pipeline Uses It |
|----------|-------------------------------|
| `raw/` dimension outputs | After the graph pipeline derives features (Step 7), compare the graph-derived features against the raw dimension analysis outputs from the previous run. Mismatches reveal either: (a) dimensions the graph missed (missing connections), or (b) dimension analysis that was wrong (top-down misattribution). This cross-reference is the strongest validation that the graph pipeline captured everything. |
| Previous `details/` files | Don't import these — they're structured around the old pipeline's dimension-based hierarchy. But read them during Step 7c (user resolution) to verify that every previously-documented behavior appears somewhere in the new graph-derived features. Any behavior that appeared in the old pipeline but NOT in the graph pipeline is a red flag: either a missed connection or a false positive from the original analysis. |
| Previous `FEATURE-INDEX.json` | During Step 9 validation, compare the old feature list against the new one. Every feature in the old index should map to at least one feature in the new index (possibly renamed or restructured). Document any features that were present in the old pipeline but absent in the new one — these require user confirmation. |

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
