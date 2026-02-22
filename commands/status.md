---
allowed-tools: Bash, Read, Glob, Grep
description: >
  Check the current status of a feature inventory or gap analysis run. Shows plugin
  version, interview status, which dimensions have been completed, coverage audit
  results, and whether the index has been generated. Useful after a /clear or
  interruption to see where things stand before resuming.
---

# Feature Inventory Status

Check the progress of the current feature inventory analysis.

## Steps

1. **Plugin version:** Read the version from `.claude-plugin/plugin.json` in the
   plugin's root directory. If the plugin was installed, use `${CLAUDE_PLUGIN_ROOT}`
   to find it; otherwise check the current working directory or common plugin paths.

2. Check if `./feature-inventory-output/` exists. If not: "No inventory in progress."

3. **Interview status:**
   - `interview.md` exists? If not: "User interview not yet completed."
   - `user-feature-map.md` exists? Report feature areas the user listed.

4. **Discovery status:**
   - `discovery.json` exists? Report repos found.

5. **Plan status:**
   - `plan.json` exists? Report planned dimensions.

6. **Analysis progress:** For each planned repo+dimension, check if the raw output
   file exists at `./feature-inventory-output/raw/{repo-name}/{dimension}.md`:
   - Non-empty file: DONE (report line count)
   - Empty file: FAILED
   - Missing file: PENDING
   - File contains `## INCOMPLETE`: PARTIAL (report where it stopped)

7. **Coverage audit:**
   - `coverage-audit.json` exists? Report coverage stats and gap count.
   - If gaps > 0, list them.

8. **Synthesis status:**
   - `synthesis-plan.json` exists? Report feature areas planned.
   - `details/` directory exists? Report count of detail files by tier
     (count files matching `F-NNN.md`, `F-NNN.NN.md`, `F-NNN.NN.NN.md`).

9. **Clarifications:** `clarifications.md` exists? Report count of resolved ambiguities.

10. **Index status:**
    - `FEATURE-INDEX.md` exists? Report.
    - `FEATURE-INDEX.json` exists? Report.

11. Present summary:

```
feature-inventory v{version}
=============================

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

Coverage Audit: {passed — N/N files adequate / N gaps found / not run}

Synthesis: {N detail files (N major, N sub-features, N behaviors) / not started}
Ambiguities resolved: {N}

Index: {generated / not generated}

To resume: run /feature-inventory:create
```

12. **Gap analysis status:** Check if `./gap-analysis-output/` exists. If so:
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
