# Gap Analysis Output Format

The gap analysis output compares a new/in-progress project against a feature inventory,
producing a structured task list for both human and AI/agent consumption.

## Directory Structure

```
gap-analysis-output/
├── new-project-discovery.json     # New project scan results
├── plan.json                      # Analysis plan (feature area assignments)
├── raw/                           # Per-feature-area gap reports
│   ├── F-001.md                   # Gap report for feature area F-001
│   ├── F-002.md
│   └── ...
├── GAP-ANALYSIS.md                # Consolidated gap analysis (human-readable)
└── GAP-ANALYSIS.json              # Consolidated gap analysis (machine-readable)
```

## Status Values

Each behavior from the feature inventory gets one of three statuses:

- **DONE** - Fully implemented. All aspects match the spec. Minor cosmetic differences
  acceptable. Functional equivalence in a different architecture counts as DONE.
- **PARTIAL** - Some implementation exists but incomplete. The report specifies exactly
  what exists and what's missing.
- **NOT STARTED** - No meaningful implementation found.

## GAP-ANALYSIS.md

The human-readable output contains:

1. **Summary table** - Counts and percentages by status
2. **Coverage by feature area** - Per-major-feature breakdown
3. **Implementation status detail** - Per-feature-area sections with:
   - Checklist of DONE items
   - PARTIAL items with implemented/missing details
   - NOT STARTED items with spec links
4. **Task list** - Ordered by implementation phases (from inventory's dependency graph),
   each task referencing the inventory detail file as its spec
5. **Cross-cutting gaps** - Patterns missing across the entire project
6. **Notes** - Architectural observations and differences

## GAP-ANALYSIS.json

The machine-readable output for AI/agent orchestrators. Contains:

- `summary` - Aggregate counts and coverage percentage
- `feature_areas[]` - Per-feature-area with items and their statuses
- `tasks[]` - Ordered task list with phase, dependencies, complexity, spec references
- `cross_cutting_gaps[]` - System-wide missing patterns

### Task Entry Structure

```json
{
  "number": 1,
  "phase": 1,
  "feature_id": "F-001.01.03",
  "name": "Implement password strength validation",
  "type": "not_started",
  "complexity": "low",
  "detail_file": "details/F-001.01.03.md",
  "depends_on": ["F-001.01.01"],
  "description": "Full implementation needed. See spec for complete requirements."
}
```

For PARTIAL items, tasks also include:

```json
{
  "implemented": "Description of what exists",
  "missing": "Description of what's missing"
}
```

## How AI/Agent Teams Should Use This

1. Read `GAP-ANALYSIS.json` to understand full scope of remaining work
2. Follow the phase ordering (respects dependency graph from the inventory)
3. For each task, read the referenced `detail_file` for full implementation spec
4. PARTIAL tasks include context about existing code to avoid rework
5. Cross-cutting gaps should be addressed as infrastructure before feature tasks
