---
name: build-index
description: >
  Phase 1 orchestrator agent. Spawned by create to build the enriched code
  reference index in its own context window. Creates its own team, spawns indexing
  and connection-hunting agents, merges results into graph.db.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage, Task, AskUserQuestion, TodoWrite
---

# Build Enriched Index — Phase 1 Orchestrator

## Purpose

This command handles all of Phase 1 as two explicit steps:

1. **Mechanical Indexing (tree-sitter only):** fast, deterministic extraction of symbols,
   direct calls, imports, exports, and connection hints.
2. **Connection Hunting (agent teams):** one file per agent; each agent hunts unresolved
   indirect connections **in OR out of that file**, writes each finding incrementally,
   reports, and terminates.

When it completes, `graph.db` contains the **enriched code index** (mechanical + hunted
connections) and the resulting enriched call graph — ready for the graph builder in
Phase 2.

## Input

Receives from the calling orchestrator:
- `plan.json`: The analysis plan with indexing splits, languages, frameworks
- `graph.db` path: Where to write the SQLite database
- `repo_path`: Absolute path to the repository
- `discovery.json`: Repo structure and tech stack
- `product_context`: Brief summary from interview
- `assigned_files` (optional): List of specific files to connection-hunt. When provided,
  skip Step 2a (file determination) and hunt ONLY these files.
- `max_files` (optional): Maximum number of files to process in this session. Defaults
  to 20. The orchestrator uses this to bound each build-index invocation to a
  context-safe file count.

## Preflight Gate: Tree-Sitter Required

Before spawning indexing teammates, run a preflight check and **fail fast** if the
runtime cannot import tree-sitter:

```bash
python3 -c "import tree_sitter, tree_sitter_languages; print('tree-sitter: ready')"
```

If this command fails, stop Phase 1 and report that tree-sitter is a hard prerequisite
for graph-pipeline mechanical indexing. Do not proceed with regex/manual extraction.

## Step 1: Build Code Reference Index via Agent Teams

### 1a: Create the Team

Use `TeamCreate` to create a team named "feature-inventory-index". Enable delegate mode.

### 1b: Spawn Indexing Teammates in Batches

For each indexing split in the plan:

1. **Check for existing output:** If the split's output file exists and is non-empty, skip.
2. **Create tasks** via `TaskCreate` for each pending split.
3. **Spawn teammates in batches of up to 5.** Each teammate gets ONE scope for ONE repo.
   Tree-sitter extraction is mandatory; teammates must fail the task if tree-sitter is
   unavailable rather than switching to manual extraction.
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
5. **Wait for agent messages** — do NOT poll output files in a sleep loop. Agents
   report back via `SendMessage` with progress updates, completion, and pre-death
   explanations. The orchestrator stays unblocked and processes messages as they arrive.
6. **Update `.progress.json`** after each batch.
7. **Batch-level hard stop (every 2 batches).** See `references/context-management.md`.

### 1c: Create SQLite Database and Merge Indexes

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
4. **Generate graph-derived connection hints** from the cross-referenced data. These
   are the most important hints — they identify every gap in the call graph that
   tree-sitter's 4 syntactic patterns miss, using pure graph analysis:
   ```sql
   -- Dead ends: calls where callee_id could not be resolved to any symbol.
   -- Every NULL callee_id is a gap — the call goes somewhere tree-sitter can't see.
   -- NO FILTERING. console.log → Browser Console. .forEach(cb) → callback target.
   -- Connection hunters resolve each one.
   INSERT INTO connection_hints (type, file, line, expression, note, resolved)
   SELECT 'dead_end', c.call_file, c.call_line, c.callee_name,
          'Unresolved call to ' || c.callee_name
            || ' from ' || COALESCE(s.qualified_name, s.name, 'unknown'),
          0
   FROM calls c
   LEFT JOIN symbols s ON c.caller_id = s.id
   WHERE c.callee_id IS NULL;

   -- Dead starts: symbols that are never called by anything in the indexed codebase.
   -- Every zero-caller symbol is either dead code (valid finding) or called through
   -- an indirect mechanism the indexer missed (a missing connection to find).
   -- NO FILTERING. Connection hunters resolve each one.
   INSERT INTO connection_hints (type, file, line, expression, note, resolved)
   SELECT 'dead_start', s.file, s.line_start, s.name,
          'Never called: ' || s.type || ' ' || COALESCE(s.qualified_name, s.name),
          0
   FROM symbols s
   WHERE s.caller_count = 0;
   ```
5. **Verify counts:** `SELECT COUNT(*) FROM symbols`, `SELECT COUNT(*) FROM calls`,
   `SELECT COUNT(*) FROM connection_hints WHERE type = 'dead_end'`,
   `SELECT COUNT(*) FROM connection_hints WHERE type = 'dead_start'`, etc.

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

### 1d: Index Validation

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
  Syntactic:   Dynamic calls: {N}  Framework magic: {N}  Reflection: {N}
  Graph-derived: Dead ends: {N}  Dead starts: {N}
```

### Context Checkpoint: After Indexing

**MANDATORY — CLEAR STRONGLY RECOMMENDED, but ONLY after confirming all indexing
agents have completed and their output has been merged to SQLite.** See
`references/context-management.md` "CRITICAL: /clear and /compact Kill In-Process
Agents" — never clear while agents are still running. Step 2 spawns connection hunters.

Preserved files: `interview.md`, `user-feature-map.md`, `discovery.json`, `plan.json`,
`graph.db`, `intermediate/index--*.jsonl`

### Phase 1 Output Contract (for Phase 2)

Treat the Phase 1 output as a single **code-index layer** stored in `graph.db`, built from:
- Mechanical indexing tables: `symbols`, `calls`, `imports`, `file_manifest`, `connection_hints`
- Connection-hunting tables: indirect connection records + resolution metadata

Phase 2 (`build-graph`) should query this code-index layer in `graph.db` as its source of
truth, rather than re-reading raw source files for discovery work already completed in
Phase 1.

Recommended: define a canonical view for unified edge traversal before Phase 2:

```sql
CREATE VIEW IF NOT EXISTS code_index_edges AS
SELECT
  'direct_call' AS edge_type,
  c.caller_id AS source_symbol_id,
  c.callee_id AS target_symbol_id,
  c.callee_name AS key_name,
  c.call_file AS source_file,
  c.call_line AS source_line
FROM calls c
WHERE COALESCE(c.connection_type, 'direct_call') = 'direct_call'
UNION ALL
SELECT
  cn.connection_type AS edge_type,
  cn.source_symbol_id,
  cn.target_symbol_id,
  cn.key_name,
  cn.source_file,
  cn.source_line
FROM connections_normalized cn;
```

The exact normalized-connection table name may vary by implementation (`connections` with
`details_json` or a denormalized helper table), but the contract is stable: Phase 2 reads
**one unified code-index edge layer** from SQLite.

## Step 2: Hunt Indirect Connections via Agent Teams

### 2a: Determine Connection Hunting File Assignments

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
5. **Check line counts and flag large files.** For each file in the list, run `wc -l`.
   Files >1000 lines are flagged as `large` in `.progress.json` (under `large_files`).
   They ARE still assigned to hunters — hunters now know how to chunk-read large files.

Present summary:
```
Connection Hunting — File Assignments
========================================
Files ≤1000 lines: {M} (standard hunting)
Files >1000 lines: {N} (chunked hunting — may produce partial results)
Total: {M+N}
```

**If `assigned_files` was provided:** Skip steps 1-5 above entirely. Use the provided
file list directly. The orchestrator has already determined which files to hunt.

### 2b: Spawn Per-File Connection Hunters in Batches

For each file in the connection hunting list:

1. **Check for existing output.** Skip if the file's JSONL output exists and has a
   summary line (indicating the agent completed).
2. **Create tasks** for pending files.
3. **Spawn teammates in batches of up to 10.** Each teammate gets ONE file. Assign
   them the `feature-inventory:connection-hunter` agent. Connection hunters are lighter
   than dimension analysts — they read one file and grep, vs. analyzing entire modules.
4. **Each teammate receives:**
   - The specific file path to hunt connections for
   - The repo path
   - The SQLite database path (`./docs/features/graph.db`)
   - The `connection_hints` for this file only
   - Output path for their findings
   - This instruction verbatim: **"Hunt every indirect connection in or out of your
     assigned file. Cover ALL 11 connection types: events, IPC, pub/sub, observables,
     DB triggers/hooks, middleware chains, DI bindings, convention routing,
     dispatch tables, webhooks, and file watchers. For each connection pattern you
     find, Grep the codebase for its counterpart. Document each connection as you
     find it. When you can't find a match, write it as unresolved with a specific
     question for the user. When you're done with your file, write a summary line
     and terminate."**
5. **Wait for agent messages** — do NOT poll output files. Connection hunters report
   progress, completion, and pre-death reasons via `SendMessage`. The orchestrator
   stays unblocked and processes messages as they arrive. Also pass the team lead name
   to each agent so it knows who to message.
6. **Batch-level hard stop (every 2 batches).**

> **CRITICAL: Hunt ALL assigned files.** Do NOT skip files, declare diminishing returns,
> stop based on hint coverage percentages, or mark connection hunting complete until every
> assigned file has been processed to at least partial status. If you run out of context,
> update `.progress.json` with exactly which files are done and which are pending, and
> return — the orchestrator will re-spawn you for the remaining files.

### 2b-return: Return Status

build-index returns one of:
- `INDEXING_COMPLETE` — mechanical indexing done, ready for connection hunting
- `HUNTING_BATCH_DONE` — processed all assigned files, more files may exist
- `ENRICHED_INDEX_COMPLETE` — all hints resolved, merge done, ready for Phase 2

When `assigned_files` was provided, return `HUNTING_BATCH_DONE` after processing all
assigned files. The calling orchestrator tracks overall completion.

### Phase 1 Completion Gate

**Phase 1 does NOT pass while unresolved dead_end or dead_start hints remain.**
Query `graph.db` to check:

```sql
SELECT type, COUNT(*) as remaining
FROM connection_hints
WHERE resolved = 0 AND type IN ('dead_end', 'dead_start')
GROUP BY type;
```

If this returns any rows, Phase 1 is incomplete. The orchestrator must:
1. Identify which files still have unresolved hints:
   ```sql
   SELECT DISTINCT file, COUNT(*) as unresolved_count
   FROM connection_hints
   WHERE resolved = 0 AND type IN ('dead_end', 'dead_start')
   GROUP BY file
   ORDER BY unresolved_count DESC;
   ```
2. Re-spawn connection hunters for those files (they will interview the user
   directly via `AskUserQuestion` to iterate to resolution).
3. After hunters complete, re-check the gate.

Only return `ENRICHED_INDEX_COMPLETE` when the query returns zero rows. This
guarantees Phase 2 receives a call graph with no dead ends — every call resolves
to a target, every reachable symbol has at least one caller.

### 2c: Merge Connections into SQLite

After all hunters complete:
1. Parse each per-file JSONL output, skipping heartbeat and summary lines.
2. **Deduplicate connections** — the same connection (e.g., event emit→listen) will
   be discovered by both the emitter file's agent and the listener file's agent.
   Deduplicate by (connection_type, key_name, source_file, source_line, target_file,
   target_line).
3. INSERT into the `connections` and `unresolved_connections` tables in `graph.db`.

### 2d: Resolve Remaining Unresolved Connections

Connection hunters now interview users directly via `AskUserQuestion` during their
run, so most resolutions happen in-agent. This step handles anything that fell
through (hunter hit context limit, AskUserQuestion was unavailable, etc.).

Check for remaining unresolved items:
```sql
SELECT COUNT(*) FROM connection_hints WHERE resolved = 0;
SELECT COUNT(*) FROM unresolved_connections WHERE resolved = 0;
```

If any remain, the orchestrator either:
1. **Re-spawns hunters** for the affected files (preferred — they have the context
   to interview effectively), OR
2. **Interviews directly** using `AskUserQuestion` for small numbers of remaining
   items, then marks them resolved in `graph.db`.

Save all resolutions to `./docs/features/clarifications.md` for auditability.

### 2e: Enrich Call Graph in SQLite

INSERT indirect edges into the `calls` table with the appropriate `connection_type`:
```sql
INSERT INTO calls (caller_id, callee_id, callee_name, call_file, call_line, connection_type)
VALUES ('SYM-emitter', 'SYM-listener', 'handlerName', 'file.ts', 42, 'event');
```

Update `caller_count` on affected symbols. This produces the **enriched call graph** —
direct calls AND indirect connections in the same table, queryable with a single SQL query.

Present final enriched index summary:
```
Enriched Index — Complete
===========================
Symbols: {N}
Direct calls: {N}
Indirect connections: {N} ({N} events, {N} IPC, {N} pub/sub, ...)
  Resolved from user interview: {N}
  Dead code identified: {N}
  External consumers: {N}
Total call graph edges: {N}

graph.db is ready for graph construction.
```

## Resume Behavior

**`graph.db` is the source of truth for resume**, not `.progress.json`. On resume,
query the database to determine current state — don't rely on stale file-based tracking.

Resume queries:
```sql
-- Step 1b: Are all files indexed?
SELECT COUNT(*) FROM file_manifest WHERE status != 'done';

-- Step 1c: Has cross-reference pass run? (caller_count > 0 anywhere = yes)
SELECT COUNT(*) FROM symbols WHERE caller_count > 0;

-- Step 1c.4: Have graph-derived hints been generated?
SELECT COUNT(*) FROM connection_hints WHERE type IN ('dead_end', 'dead_start');

-- Step 2: How many hints remain unresolved?
SELECT type, COUNT(*) FROM connection_hints WHERE resolved = 0 GROUP BY type;

-- Step 2: Which files still need hunting?
SELECT DISTINCT file FROM connection_hints WHERE resolved = 0;

-- Completion gate: ready for Phase 2?
SELECT COUNT(*) FROM connection_hints
WHERE resolved = 0 AND type IN ('dead_end', 'dead_start');
-- Must be 0 to pass.
```

Resume rules:
- **Step 1b** (indexing): Check `file_manifest` for `status != 'done'`. Re-index only
  incomplete files. Fall back to `.progress.json` if `graph.db` doesn't exist yet.
- **Step 1c-d** (merge + validate): Re-run if `file_manifest` has newly completed files.
- **Step 2a** (file assignments): Query `connection_hints WHERE resolved = 0` for files.
- **Step 2b** (hunting): Query unresolved hints per file — only spawn hunters for files
  with remaining unresolved hints.
- **Step 2d** (remaining unresolved): Query both `connection_hints` and
  `unresolved_connections` for `resolved = 0`.
- **Step 2e** (enrich call graph): Re-run if new connections were added since last run.
- **Completion gate**: Phase 1 passes only when zero dead_end/dead_start hints remain
  unresolved.
