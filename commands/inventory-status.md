---
allowed-tools: Bash, Read
description: >
  Check the current status of a feature inventory run. Shows interview status,
  which dimensions have been completed, and whether the index has been generated.
  Useful after a /clear or interruption to see where things stand before resuming.
---

# Feature Inventory Status

Check the progress of the current feature inventory analysis.

## Steps

1. Check if `./feature-inventory-output/` exists. If not: "No inventory in progress."

2. **Interview status:**
   - `interview.md` exists? If not: "User interview not yet completed."
   - `user-feature-map.md` exists? Report feature areas the user listed.

3. **Discovery status:**
   - `discovery.json` exists? Report repos found.

4. **Plan status:**
   - `plan.json` exists? Report planned dimensions.

5. **Analysis progress:** For each planned repo+dimension, check if the raw output
   file exists at `./feature-inventory-output/raw/{repo-name}/{dimension}.md`:
   - Non-empty file: DONE (report line count)
   - Empty file: FAILED
   - Missing file: PENDING
   - File contains `## INCOMPLETE`: PARTIAL (report where it stopped)

6. **Clarifications:** `clarifications.md` exists? Report count of resolved ambiguities.

7. **Index status:**
   - `FEATURE-INDEX.md` exists? Report.
   - `details/` directory exists? Report count of detail files.
   - `FEATURE-INDEX.json` exists? Report.

8. Present summary:

```
Feature Inventory Status
========================

Interview: {complete / not started}
User Feature Map: {N areas listed / not created}
Discovery: {N repos found / not run}
Plan: {created / not created}

Analysis Progress:
| Repo | Dimension | Status | Lines |
|------|-----------|--------|-------|
| backend | api-surface | DONE | 245 |
| backend | data-models | DONE | 189 |
| backend | business-logic | PARTIAL (stopped at src/billing) | 156 |
| frontend | ui-screens | PENDING | - |
| ... | ... | ... | ... |

Dimensions: {done}/{total} complete, {partial} partial, {pending} pending
Ambiguities resolved: {N}

Index: {generated with N detail files / not generated}

To resume: run /feature-inventory:work
```

9. **Gap analysis status:** Check if `./gap-analysis-output/` exists. If so:
   - `plan.json` exists? Report feature areas planned.
   - For each planned feature area, check `./gap-analysis-output/raw/{feature-id}.md`:
     - Non-empty file: DONE (report line count)
     - Empty file: FAILED
     - Missing file: PENDING
   - `GAP-ANALYSIS.md` exists? Report.
   - `GAP-ANALYSIS.json` exists? Report.
   - Present gap analysis summary:

```
Gap Analysis Status
===================

Plan: {created / not created}

Analysis Progress:
| Feature Area | Status | Lines |
|--------------|--------|-------|
| F-001: User Management | DONE | 312 |
| F-002: Billing | PENDING | - |
| ... | ... | ... |

Areas: {done}/{total} complete, {pending} pending
Report: {generated / not generated}

To resume: run /feature-inventory:gap-analysis
```
