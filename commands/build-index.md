---
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: >
  Phase 1 orchestrator: builds the enriched code reference index. Runs tree-sitter
  mechanical indexing via agent teams, then per-file connection hunting to find every
  indirect edge (events, IPC, pub/sub, DB triggers, etc.), interviews the user for
  unresolved connections, and enriches the call graph. Output: graph.db with all symbols,
  direct calls, indirect connections, and connection hints resolved — ready for graph
  construction (Phase 2).
  This command is called by create-graph and should not be run directly.
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

The `create-graph` orchestrator delegates to this command. It should not be run directly
by users.

## Input

Receives from the calling orchestrator:
- `plan.json`: The analysis plan with indexing splits, languages, frameworks
- `graph.db` path: Where to write the SQLite database
- `repo_path`: Absolute path to the repository
- `discovery.json`: Repo structure and tech stack
- `product_context`: Brief summary from interview

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
  Dynamic calls: {N}  Framework magic: {N}  Reflection: {N}
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

### 2b: Spawn Per-File Connection Hunters in Batches

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

### 2c: Merge Connections into SQLite

After all hunters complete:
1. Parse each per-file JSONL output, skipping heartbeat and summary lines.
2. **Deduplicate connections** — the same connection (e.g., event emit→listen) will
   be discovered by both the emitter file's agent and the listener file's agent.
   Deduplicate by (connection_type, key_name, source_file, source_line, target_file,
   target_line).
3. INSERT into the `connections` and `unresolved_connections` tables in `graph.db`.

### 2d: User Interview for Unresolved Connections

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

This command tracks its progress in the `indexing` and `connection_hunting` sections
of `./docs/features/.progress.json`.

Resume rules:
- Step 1b (indexing agents): Use `.progress.json` to skip completed splits. Resume from
  exact batch. Fall back to scanning index split files.
- Step 1c-d (merge + validate): Re-run if any indexing splits were re-run.
- Step 2a (file assignments): Re-run if indexing changed. Fast — just queries the index.
- Step 2b (per-file hunting): Use `.progress.json` to skip completed files. Resume from
  exact batch. Fall back to scanning per-file JSONL outputs for summary lines.
- Step 2d (user interview): Skip if `clarifications.md` has connection resolutions.
  Re-run for new unresolved items only.
- Step 2e (enrich call graph): Re-run if connections changed.
