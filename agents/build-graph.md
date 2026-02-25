---
name: build-graph
description: >
  Phase 2 orchestrator agent. Spawned by create to build the outcome graph
  in its own context window. Identifies entry points and final outcomes, traces
  pathways, validates the graph, and interviews the user about gaps.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage, Task, AskUserQuestion, TodoWrite
---

# Build Outcome Graph — Phase 2 Orchestrator

## Purpose

This command handles all of Phase 2: outcome graph construction and validation. When it
completes, `graph.db` contains the **outcome graph** — every entry point, every final
outcome, every pathway connecting them, and fan-out points — validated and ready for
pathway annotation in Phase 3.

## Input

Receives from the calling orchestrator:
- `graph.db` path: The SQLite database with the enriched call graph from Phase 1
- `product_context`: Brief summary from interview
- `repo_path`: Absolute path to the repository

## Step 1: Spawn Graph Builder

The graph builder is a single-agent task (it needs a holistic view of the codebase,
not a per-module view). Spawn ONE teammate with the
`feature-inventory:graph-builder` agent.

### 1a: Create the Team

Use `TeamCreate` to create a team named "feature-inventory-graph". Enable delegate mode.

### 1b: Spawn Graph Builder Agent

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

**Monitor agent liveness** using the heartbeat protocol (see
`references/context-management.md`). Do NOT assume an agent is dead unless its
output file has not been modified for 5+ minutes.

## Step 2: Graph Validation & User Interview

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

Present final graph summary:
```
Outcome Graph — Complete
==========================
Entry points: {N}
Final outcomes: {N}
Pathways: {N}
Fan-out points: {N}
Infrastructure symbols: {N}
Index coverage: {pct}%
Issues resolved: {N}

graph.db is ready for pathway annotation.
```

## Database Schema Integration

When the indexed codebase includes MySQL/SQL schema files (stored procedures, triggers,
views, tables), the graph builder MUST integrate them into the outcome graph rather than
treating them as dead ends.

### Entry Points from Database Objects

These database objects are **entry points** — they execute in response to schedules,
data changes, or application calls:

- **Stored procedures:** Called by application code (via `CALL proc_name()` or through
  data access layers like `SqlCommand`, `DbContext`, repository patterns). Trace from
  the application-layer call site through the procedure's body to its effects (INSERT,
  UPDATE, DELETE on tables, calls to other procedures).
- **Triggers:** Fire automatically on INSERT/UPDATE/DELETE. These are **implicit entry
  points** — no application code calls them directly, but they execute as side effects
  of data operations. The graph must show: `app code writes to table` -> `trigger fires`
  -> `trigger body effects`.
- **Scheduled events:** (`CREATE EVENT ... ON SCHEDULE`) are cron-like entry points.
  Treat them the same as HTTP endpoints or CLI commands — they initiate pathways.

### Infrastructure Nodes from Database Objects

- **Views:** Treat as infrastructure/utility nodes in pathways. A view is a derived
  query — when application code reads from a view, the pathway step should reference
  the view and note which underlying tables it queries.
- **Tables:** Tables are data-layer nodes. When a pathway involves reading or writing
  a specific table, that table becomes a pathway step.

### Data Access Layer Tracing

When application code (e.g., C# repository methods, Python ORM calls, Node.js query
builders) queries or writes a specific table:

1. **Identify the table** from the SQL string, ORM mapping, or repository method name.
2. **Create a pathway step** at that table node.
3. **Check for triggers** on that table. If a trigger exists for the operation type
   (INSERT/UPDATE/DELETE), the trigger's body is an implicit continuation of the pathway.
4. **Check for views** that reference the table. If downstream code reads from such a
   view, there is an indirect data-flow connection: `writer -> table -> view -> reader`.

### Table-to-Table Relationships

Include these as pathway connections in the graph:

- **Foreign key references:** `FOREIGN KEY (col) REFERENCES other_table(col)` creates
  a data relationship. When a pathway writes to a parent table, related child tables
  are potentially affected (CASCADE rules).
- **Trigger chains:** If trigger A on table X writes to table Y, and trigger B on
  table Y writes to table Z, this is a chain: `X -> trigger A -> Y -> trigger B -> Z`.
  The graph must trace through the full chain.
- **Procedure-to-procedure calls:** Stored procedures that call other stored procedures
  via `CALL` statements create direct call edges in the graph.

### How to Identify Database Connections

Query the enriched index for database-related symbols:
```sql
-- Find all stored procedures and triggers
SELECT * FROM symbols WHERE type IN ('procedure', 'trigger', 'event', 'view');

-- Find application code that references table names
SELECT * FROM calls WHERE callee_name LIKE '%table_name%';

-- Find data_store_access connection hints
SELECT * FROM connection_hints WHERE hint_type = 'data_store_access';

-- Find db_hook connection hints (triggers)
SELECT * FROM connection_hints WHERE hint_type = 'db_hook';
```

## Resume Behavior

This command tracks its progress in the `graph_building` section
of `./docs/features/.progress.json`.

Resume rules:
- Step 1 (graph builder): Re-run if enriched index changed. Graph building is
  relatively cheap compared to indexing and connection hunting.
- Step 2 (validation interview): Re-run for new validation failures only. Skip
  previously resolved issues.
