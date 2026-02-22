---
allowed-tools: Bash, Read, Glob, Grep
description: >
  Check the current status of a feature inventory, gap analysis, plan generation, or
  marketing catalog run. Shows plugin version, interview status, which dimensions have
  been completed, coverage audit results, plan generation progress, marketing catalog
  progress, and whether indexes have been generated. Useful after a /clear or
  interruption to see where things stand before resuming.
---

# Feature Inventory Status

Check the progress of the current feature inventory analysis, gap analysis, plan generation,
and marketing catalog.

## Steps

1. **Plugin version:** Read the version from `.claude-plugin/plugin.json` in the
   plugin's root directory. If the plugin was installed, use `${CLAUDE_PLUGIN_ROOT}`
   to find it; otherwise check the current working directory or common plugin paths.

2. Check if `./docs/features/` exists. If not: "No inventory in progress."

3. **Interview status:**
   - `interview.md` exists? If not: "User interview not yet completed."
   - `user-feature-map.md` exists? Report feature areas the user listed.

4. **Discovery status:**
   - `discovery.json` exists? Report repos found.

5. **Plan status:**
   - `plan.json` exists? Report planned dimensions.

6. **Analysis progress:** For each planned repo+dimension, check if the raw output
   file exists at `./docs/features/raw/{repo-name}/{dimension}.md`:
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

12. **Gap analysis status:** Check if `./docs/gap-analysis/` exists. If so:
    - `plan.json` exists? Report feature areas planned.
    - For each planned feature area, check `./docs/gap-analysis/raw/{feature-id}.md`:
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

13. **Plan generation status:** Check if `./docs/plans/` exists. If so:
    - `interview.md` exists? Report strategic interview status.
    - `plan-config.json` exists? Report target stack and rebuild scope.
    - `research.md` exists? Report research status.
    - `planning-strategy.json` exists? Report features in scope and phases.
    - For each feature in scope, check `./docs/plans/features/{feature-id}/`:
      - `plan.md` exists and non-empty? DONE
      - `plan-tdd.md` exists? TDD stubs written
      - `sections/index.md` exists? Section index created
      - Count `sections/section-*.md` files for section progress
    - Check cross-cutting plan: `./docs/plans/features/cross-cutting/plan.md`
    - For each feature, check `reviews/` directory for external review files.
    - `PLAN-INDEX.md` exists? Report.
    - `PLAN-INDEX.json` exists? Report.
    - Present plan generation summary:

```
Plan Generation Status
======================

Strategic Interview: {complete / not started}
Target Stack: {language + framework / not configured}
Rebuild Scope: {1:1 / minimum + additions / selective / not decided}
Research: {complete / not started}
Planning Strategy: {created / not created}

Feature Plans:
| Feature | Plan | TDD | Sections | Review | Status |
|---------|------|-----|----------|--------|--------|
| cross-cutting | DONE | DONE | 3/3 | Gemini+OpenAI | Complete |
| F-001: User Management | DONE | DONE | 4/6 | - | In Progress |
| F-002: Billing | PENDING | - | - | - | Not Started |
| ... | ... | ... | ... | ... | ... |

Plans: {done}/{total} complete, {in_progress} in progress, {pending} pending
Sections: {done}/{total} written
External Reviews: {N}/{total} reviewed

Plan Index: {generated / not generated}

To resume: run /feature-inventory:plan
```

14. **Marketing catalog status:** Check if `./docs/marketing/` exists. If so:
    - `interview.md` exists? Report marketing interview status.
    - `catalog-config.json` exists? Report audience type, tone, and competitive position.
    - `catalog-state.json` exists? Report last run date and feature checksums.
    - Count entry files in `./docs/marketing/entries/`:
      - Feature entries: count files matching `F-*.md` (excluding `-composite` files)
      - Composite entries: count files matching `*-composite.md` and `COMPOSITE-*.md`
      - Archived entries: count files in `./docs/marketing/entries/archived/`
    - `MARKETING-CATALOG.md` exists? Report.
    - `MARKETING-CATALOG.json` exists? Report.
    - Present marketing catalog summary:

```
Marketing Catalog Status
=========================

Marketing Interview: {complete / not started}
Audience: {type — personas / not configured}
Tone: {tone / not configured}
Competitive Position: {position / not configured}
Last Run: {date / never}

Catalog Entries:
| Feature Area | Entry | Composites | Status |
|--------------|-------|------------|--------|
| F-001: User Management | DONE | 1 | Complete |
| F-002: Billing | DONE | 0 | Complete |
| F-003: Reporting | PENDING | - | Not Started |
| ... | ... | ... | ... |

Entries: {done}/{total} feature areas cataloged
  - Feature entries: {N}
  - Within-area composites: {N}
  - Cross-product composites: {N}
  - Archived: {N}

Master Catalog: {generated / not generated}

To resume: run /feature-inventory:marketing-catalog
```
