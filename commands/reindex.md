---
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: >
  Incrementally updates the code reference index, outcome graph, and feature inventory
  after source code changes. Identifies changed files via git diff, re-indexes only
  affected symbols, re-hunts affected connections, re-traces affected pathways, and flags
  features whose behaviors may have changed. Produces user-facing change notes summarizing
  what changed in feature terms, not code terms.
  Run: /feature-inventory:reindex [--since <commit|tag>] [--diff <branch>]
---

# Feature Inventory Reindex - Orchestrator

## Purpose

After code changes are committed to the legacy codebase, this command incrementally
updates the feature inventory without regenerating everything from scratch. It:

1. Identifies which files changed
2. Re-indexes only those files (updates SQLite)
3. Re-hunts connections in affected files
4. Re-traces affected pathways in the graph
5. Re-annotates affected pathways
6. Flags features whose behaviors changed
7. Generates user-facing change notes

This is designed to be run manually after commits. Once the workflow is proven, it can
be extracted into a CI script that runs automatically.

## Prerequisites

- A completed graph-based inventory must exist (`./docs/features/graph.db` with all
  tables populated, plus `./docs/features/details/` with feature files)
- The legacy codebase must be a git repository
- Agent Teams must be enabled (same prerequisite as `create`)

## Input

The command accepts optional arguments to control the diff scope:

- `--since <commit|tag>`: Compare current state against a specific commit or tag.
  Default: the `last_reindex_commit` stored in the SQLite `metadata` table.
- `--diff <branch>`: Compare current branch against another branch (useful for
  reviewing a feature branch's impact on the inventory).

If no arguments are provided, the command diffs against the last reindex point.

## Step 1: Identify Changed Files

```bash
# Default: diff against last reindex commit
git diff --name-only --diff-filter=ACDMR <last_reindex_commit> HEAD

# With --since flag
git diff --name-only --diff-filter=ACDMR <specified_commit> HEAD

# With --diff flag
git diff --name-only --diff-filter=ACDMR <specified_branch>...HEAD
```

Classify changes:
- **A (Added)**: New files — need full indexing
- **D (Deleted)**: Removed files — remove symbols from index, invalidate pathways
- **M (Modified)**: Changed files — re-index, find affected pathways
- **R (Renamed)**: Renamed files — update file references in index
- **C (Copied)**: Copied files — index the new copy

Filter out files matching `plan.json.exclude_patterns` (vendor, generated, etc.).

Present summary:
```
Reindex Scope
==============
Changed files: {N} (Added: {A}, Modified: {M}, Deleted: {D}, Renamed: {R})
Excluded (vendor/generated): {N}
Files to process: {N}

Estimated impact: {light | moderate | heavy}
  (light: <10 files, moderate: 10-50 files, heavy: >50 files)
```

If heavy, warn the user that this may take significant time and suggest running the
full `create` pipeline instead if the changes are fundamental (new major feature,
architecture refactor, etc.).

## Step 2: Re-Index Changed Files

For each changed file:

### Modified Files
1. **Delete existing symbols** for this file from the SQLite database:
   ```sql
   DELETE FROM calls WHERE caller_id IN (SELECT id FROM symbols WHERE file = ?);
   DELETE FROM calls WHERE callee_id IN (SELECT id FROM symbols WHERE file = ?);
   DELETE FROM imports WHERE file = ?;
   DELETE FROM symbols WHERE file = ?;
   UPDATE file_manifest SET status = 'pending' WHERE file = ?;
   ```
2. **Re-index the file** using the same logic as `code-indexer.md`:
   - Extract all symbols, calls, imports
   - Write to a temporary JSONL file
   - INSERT into SQLite
3. **Re-run cross-referencing** for affected symbols:
   - Resolve `callee_id` for new call entries
   - Update `caller_count` on all symbols that gained or lost callers

### Added Files
Same as modified, but skip the DELETE step.

### Deleted Files
1. Record which symbols are being removed (needed for pathway invalidation).
2. DELETE all symbols, calls, and imports for the file.
3. Remove from file_manifest.

### Renamed Files
1. UPDATE `file` column in `symbols`, `calls`, `imports`, `file_manifest`.
2. UPDATE `file` in `pathway_steps`, `annotation_source_maps`, etc.

**If more than 5 files changed**, spawn indexing teammates (one per file or group of
related files) using the `feature-inventory:code-indexer` agent, then merge JSONL
output into SQLite.

## Step 3: Re-Hunt Affected Connections

Check if any changed files contain connection patterns:

```sql
-- Check if any deleted/modified symbols had indirect connections
SELECT * FROM connections WHERE details_json LIKE '%' || ? || '%';

-- Check if any changed files had connection hints
SELECT * FROM connection_hints WHERE file = ? AND resolved = 1;
```

If connections are affected:
1. Delete affected connection records from `connections` table.
2. Delete affected indirect `calls` entries (where `connection_type != 'direct'`).
3. Re-run connection hunting for affected connection types in the changed files.
4. Merge new connections into SQLite.
5. Re-enrich the call graph.

If no connections are affected, skip to Step 4.

## Step 4: Identify Affected Pathways

```sql
-- Find all pathways that pass through any changed/deleted symbol
SELECT DISTINCT ps.pathway_id
FROM pathway_steps ps
JOIN symbols s ON ps.symbol_id = s.id
WHERE s.file IN (?, ?, ...);  -- changed files

-- Also find pathways through deleted symbols (captured before deletion)
-- Use the list of deleted symbol IDs from Step 2
```

Record the set of affected pathway IDs.

If no pathways are affected (changes were in files not on any pathway — infrastructure
only), report this and skip to Step 7.

## Step 5: Re-Trace Affected Pathways

For each affected pathway:
1. Delete existing `pathway_steps` rows.
2. Re-trace from the pathway's entry point through the updated call graph.
3. If the pathway still reaches its original final outcome: update steps.
4. If the pathway reaches a DIFFERENT final outcome: flag as `pathway_changed`.
5. If the pathway is broken (entry point or final outcome deleted): flag as `pathway_broken`.
6. If new pathways are discoverable from the same entry point: flag as `pathway_added`.

**If more than 10 pathways are affected**, spawn graph builder teammates to re-trace
in parallel.

Update the `pathways` and `pathway_steps` tables. Update `graph_validation` for any
new orphans or gaps.

## Step 6: Re-Annotate Affected Pathways

For each affected pathway that is still valid:
1. Delete existing `pathway_annotations` and `annotation_source_maps` rows.
2. Re-annotate the pathway using the same logic as `pathway-dimension-annotator.md`.
3. INSERT updated annotations into SQLite.

**If more than 10 pathways need re-annotation**, spawn annotator teammates.

## Step 7: Flag Affected Features and Generate Change Notes

### Identify Affected Features

Map affected pathways to features using FEATURE-INDEX.json:

```python
# For each affected pathway, find which feature claims it
affected_features = set()
for pathway_id in affected_pathway_ids:
    feature = find_feature_for_pathway(pathway_id, feature_index)
    if feature:
        affected_features.add(feature)
```

### Classify Changes Per Feature

For each affected feature, classify the nature of the change:

| Change Type | Description |
|-------------|-------------|
| **behavior_modified** | A behavior's logic, validation, or error handling changed |
| **behavior_added** | A new pathway was discovered (new behavior in existing feature) |
| **behavior_removed** | A pathway was broken (behavior no longer exists) |
| **data_model_changed** | Entity fields, validations, or constraints changed |
| **api_changed** | Route, request/response schema, or auth changed |
| **side_effect_changed** | Events, jobs, integrations, or notifications changed |
| **config_changed** | Environment variables, feature flags, or constants changed |
| **infrastructure_only** | Changes in utility code used by this feature (no behavioral impact) |

### Generate Change Notes

Produce human-readable change notes that describe changes in FEATURE terms, not code terms:

```markdown
# Feature Inventory Change Notes
> Reindex: {commit_range}
> Date: {date}
> Files changed: {N}

## Features Affected: {N}

### F-001: Order Management
**Sub-features affected:** F-001.01 (Place an Order)

- **Modified:** F-001.01.02 (Calculate order total) — Volume discount thresholds changed:
  $5,000→$4,000 for 2% tier, $10,000→$8,000 for 5% tier
  - Source: src/services/pricing.ts (modified)
  - Previous: volume_discount = total > 10000 ? 0.05 : total > 5000 ? 0.02 : 0
  - Current: volume_discount = total > 8000 ? 0.05 : total > 4000 ? 0.02 : 0

- **Added:** F-001.01.09 (Apply loyalty points at checkout) — New pathway discovered:
  POST /api/orders now calls LoyaltyService.redeemPoints before payment processing
  - Source: src/services/loyalty.ts (added), src/services/order.ts (modified)

### F-003: Shipping
**No behavioral changes.** Infrastructure utility `formatCurrency` was updated but
does not affect shipping feature outcomes.

## Summary
| Change Type | Count |
|-------------|-------|
| Behaviors modified | 3 |
| Behaviors added | 1 |
| Behaviors removed | 0 |
| Infrastructure only | 2 |
```

Write change notes to `./docs/features/change-notes/{date}-{short_hash}.md`.

### Update Source Maps in Detail Files

For each affected feature, update the Source Maps section in its detail files to
reflect any changed line numbers or file paths.

## Step 8: Update Metadata

```sql
UPDATE metadata SET value = ? WHERE key = 'last_reindex_commit';
UPDATE metadata SET value = ? WHERE key = 'last_reindex_at';
INSERT INTO metadata (key, value) VALUES ('reindex_history',
  json_insert(COALESCE((SELECT value FROM metadata WHERE key = 'reindex_history'), '[]'),
    '$[#]', json_object('commit', ?, 'date', ?, 'files_changed', ?,
      'pathways_affected', ?, 'features_affected', ?)));
```

Present final summary:
```
Reindex Complete
=================
Files processed: {N} (Added: {A}, Modified: {M}, Deleted: {D})
Symbols updated: {N} (new: {N}, modified: {N}, removed: {N})
Connections re-hunted: {N}
Pathways re-traced: {N} (modified: {N}, added: {N}, broken: {N})
Features affected: {N}

Change notes: docs/features/change-notes/{date}-{short_hash}.md

Tip: Review the change notes and update any affected detail files
if the behavioral description needs revision.
```

## Resume Behavior

The reindex command is designed to be idempotent. If interrupted, re-running it with
the same `--since` argument will re-process all changes. The SQLite transactions ensure
partial updates don't leave the database in an inconsistent state.

No `.progress.json` is needed — the reindex is typically fast enough to complete in a
single session. For very large diffs (>100 files), consider running the full
`create` pipeline instead.

## Future: CI Integration

This command is the manual stepping stone toward automated CI integration. Once the
workflow is proven, the same logic can be extracted into a standalone script:

```yaml
# Example GitHub Actions workflow (future)
on:
  push:
    branches: [main]

jobs:
  reindex:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for git diff
      - name: Reindex feature inventory
        run: |
          claude-code --skill feature-inventory:reindex --since ${{ github.event.before }}
      - name: Commit updated inventory
        run: |
          git add docs/features/
          git commit -m "chore: reindex feature inventory" || true
          git push
```

The key design decision: the reindex command does NOT modify feature detail files
automatically (except source maps). It produces change notes and flags affected features.
A human or AI agent reviews the changes and decides whether the feature description
needs updating. This keeps the inventory under intentional control rather than drifting
with every code change.
