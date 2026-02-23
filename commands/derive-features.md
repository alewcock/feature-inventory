---
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: >
  Phase 4 orchestrator: derives features from annotated pathways in the outcome graph.
  Clusters pathways into feature areas, spawns feature derivation agents per cluster,
  interviews the user for quality resolution, builds the feature index, and validates
  coverage. Output: docs/features/details/F-*.md files, FEATURE-INDEX.md,
  FEATURE-INDEX.json, and final validation summary.
  This command is called by create-graph and should not be run directly.
---

# Derive Features — Phase 4 Orchestrator

## Purpose

This command handles all of Phase 4: feature derivation, user resolution, index building,
and final validation. When it completes, the full feature inventory exists as detail files
(`F-*.md`), a navigable index (`FEATURE-INDEX.md`), and a machine-readable index
(`FEATURE-INDEX.json`) — the final deliverable of the graph pipeline.

The `create-graph` orchestrator delegates to this command. It should not be run directly
by users.

## Input

Receives from the calling orchestrator:
- `graph.db` path: The SQLite database with annotated pathways from Phase 3
- `repo_path`: Absolute path to the repository
- `interview.md` path: User interview answers
- `user-feature-map.md` path: User's mental model of feature areas

## Step 1: Initial Clustering (Lightweight)

Before spawning feature derivation teammates, do a quick clustering pass to assign
pathways to major feature areas:

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
      "pathway_ids": ["PW-001", "PW-002", "PW-003"],
      "entry_point_ids": ["EP-001", "EP-010", "EP-015"],
      "source": "user_feature_map + graph entry points"
    }
  ],
  "unclaimed_pathways": ["PW-089", "PW-090"],
  "cross_cutting": ["PW-200", "PW-201"]
}
```

## Step 2: Spawn Feature Derivation Teammates in Batches

### 2a: Create the Team

Use `TeamCreate` to create a team named "feature-inventory-derive". Enable delegate mode.

### 2b: Spawn Derivation Agents

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
4. **Monitor agent liveness** using the heartbeat protocol (see
   `references/context-management.md`). Do NOT assume an agent is dead unless its
   output file has not been modified for 5+ minutes.
5. **Batch-level hard stop (every 2 batches).** See `references/context-management.md`.

## Step 3: User Resolution Interview

After all feature derivation teammates complete, scan detail files for quality issues
using the same criteria as the standard pipeline's Step 4.5:
- Thin specs
- Overlapping features
- Unresolved ambiguities
- Orphan behaviors

Present candidates to the user and apply resolutions (define, merge, remove, clarify).
See the standard pipeline's Step 4.5b-e for the full interview protocol.

Save resolutions to `./docs/features/clarifications-features.md`.

## Step 4: Build Index

**Identical to the standard pipeline's Step 4c.** Enumerate all detail files, build
the hierarchy, write FEATURE-INDEX.md and FEATURE-INDEX.json.

The JSON index includes additional graph metadata: pathway references, entry point IDs,
final outcome IDs, and source map symbol IDs. See `references/graph-output-format.md`.

## Step 5: Validation & Summary

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

This command tracks its progress in the `feature_derivation` section
of `./docs/features/.progress.json`.

Resume rules:
- Step 1 (clustering): Re-run — lightweight, just queries the graph.
- Step 2 (derivation agents): Use `.progress.json` to skip completed feature areas.
  Re-run for features whose pathways changed.
- Step 3 (user resolution): Skip if `clarifications-features.md` exists. Re-run for
  affected features if derivation re-ran.
- Steps 4-5 (index + validation): Always re-run (indexes are cleared on resume).
