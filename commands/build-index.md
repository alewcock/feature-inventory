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

This command handles all of Phase 1: mechanical indexing + connection hunting. When it
completes, `graph.db` contains the **enriched call graph** — every symbol, every direct
call, and every indirect connection — ready for the graph builder to consume in Phase 2.

The `create-graph` orchestrator delegates to this command. It should not be run directly
by users.

## Input

Receives from the calling orchestrator:
- `plan.json`: The analysis plan with indexing splits, languages, frameworks
- `graph.db` path: Where to write the SQLite database
- `repo_path`: Absolute path to the repository
- `discovery.json`: Repo structure and tech stack
- `product_context`: Brief summary from interview

## Step 1: Build Code Reference Index via Agent Teams

### 1a: Create the Team

Use `TeamCreate` to create a team named "feature-inventory-index". Enable delegate mode.

### 1b: Spawn Indexing Teammates in Batches

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
7. **Monitor agent liveness** using the heartbeat protocol (see
   `references/context-management.md`). Do NOT assume an agent is dead unless its
   output file has not been modified for 5+ minutes.
8. **Batch-level hard stop (every 2 batches).** See `references/context-management.md`.

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

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Step 2 spawns connection hunters.

Preserved files: `interview.md`, `user-feature-map.md`, `discovery.json`, `plan.json`,
`graph.db`, `intermediate/index--*.jsonl`

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
     assigned file. For each connection pattern you find (event emit, IPC send,
     pub/sub publish, etc.), Grep the codebase for its counterpart. Document each
     connection as you find it. When you can't find a match, write it as unresolved
     with a specific question for the user. When you're done with your file, write
     a summary line and terminate."**
5. **Monitor agent liveness** using the heartbeat protocol (see
   `references/context-management.md`). Do NOT assume an agent is dead unless its
   output file has not been modified for 5+ minutes.
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
