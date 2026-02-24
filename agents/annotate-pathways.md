---
name: annotate-pathways
description: >
  Phase 3 orchestrator agent. Spawned by create to annotate every pathway
  with dimensional information (data, auth, logic, UI, config, side effects)
  in its own context window.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage, Task, AskUserQuestion, TodoWrite
---
# Annotate Pathways — Phase 3 Orchestrator

## Purpose

This command handles all of Phase 3: pathway annotation. When it completes, `graph.db`
contains **dimensional annotations** on every pathway — what data is read/written, what
auth is checked, what business logic is applied, what UI is rendered, what config is
consumed, and what side effects are triggered — ready for feature derivation in Phase 4.

## Input

Receives from the calling orchestrator:
- `graph.db` path: The SQLite database with the outcome graph from Phase 2
- `repo_path`: Absolute path to the repository (for reading source code at indexed locations)

## Step 1: Spawn Pathway Annotators in Batches

### 1a: Create the Team

Use `TeamCreate` to create a team named "feature-inventory-annotate". Enable delegate mode.

### 1b: Group and Assign Pathways

Group pathways by entry point for annotation (pathways from the same entry point share
early steps). Each teammate gets a set of pathways sharing an entry point group.

1. **Query the graph** for pathway groupings:
   ```sql
   SELECT ep.id, ep.name, COUNT(p.id) as pathway_count
   FROM entry_points ep
   JOIN pathways p ON p.entry_point_id = ep.id
   GROUP BY ep.id;
   ```
2. **Group entry points** that share pathways into batches.
3. **Create tasks** for each pathway group.

### 1c: Spawn Annotators

1. **Spawn teammates in batches of up to 5.** Assign them the
   `feature-inventory:pathway-dimension-annotator` agent.
2. **Each teammate receives:**
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
3. **Monitor agent liveness** using the heartbeat protocol (see
   `references/context-management.md`). Do NOT assume an agent is dead unless its
   output file has not been modified for 5+ minutes.
4. **Batch-level hard stop (every 2 batches).** See `references/context-management.md`.

## Step 2: Merge Annotated Pathways

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

graph.db is ready for feature derivation.
```

## Resume Behavior

This command tracks its progress in the `annotation` section
of `./docs/features/.progress.json`.

Resume rules:
- Step 1 (annotator agents): Use `.progress.json` to skip completed pathway groups.
  Resume from exact batch. Re-run for pathways that changed in graph re-building.
- Step 2 (merge): Re-run if any annotation agents were re-run.
