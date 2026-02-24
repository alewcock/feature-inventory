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

## Resume Behavior

This command tracks its progress in the `graph_building` section
of `./docs/features/.progress.json`.

Resume rules:
- Step 1 (graph builder): Re-run if enriched index changed. Graph building is
  relatively cheap compared to indexing and connection hunting.
- Step 2 (validation interview): Re-run for new validation failures only. Skip
  previously resolved issues.
