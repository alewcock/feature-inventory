# Feature Index Output Format

The output is structured as a linked hierarchy designed for AI/agent team consumption.

## Directory Structure

```
feature-inventory-output/
├── interview.md                    # User interview answers
├── user-feature-map.md             # User's mental model of features
├── clarifications.md               # Resolved ambiguities
├── discovery.json                  # Repo scan results
├── plan.json                       # Analysis plan
├── raw/                            # Raw dimension outputs (per repo)
│   ├── {repo-name}/
│   │   ├── api-surface.md
│   │   ├── data-models.md
│   │   ├── ui-screens.md
│   │   ├── business-logic.md
│   │   ├── integrations.md
│   │   ├── background-jobs.md
│   │   ├── auth-and-permissions.md
│   │   ├── configuration.md
│   │   └── events-and-hooks.md
│   └── ...
├── FEATURE-INDEX.md                # The master index (names + links only)
├── FEATURE-INDEX.json              # Machine-readable index
└── details/                        # One file per feature/behavior
    ├── F-001.md                    # Major feature overview
    ├── F-001.01.md                 # Sub-feature specification
    ├── F-001.01.01.md              # Individual behavior specification
    ├── F-001.01.02.md
    ├── F-001.02.md
    ├── F-002.md
    └── ...
```

## FEATURE-INDEX.md

This file is a TABLE OF CONTENTS ONLY. Feature/behavior names and links to detail files.
No inline details. An AI agent reading this should understand full product scope and
navigate to any feature.

## Detail File Tiers

### Major Feature (F-001.md)
- Overview of the feature area
- List of sub-features with links
- Cross-cutting dependencies (auth, data, integrations)
- Implementation notes for agent teams

### Sub-Feature (F-001.01.md)
- Full specification: data model, API contracts, UI spec, business rules
- List of individual behaviors with links
- Dependencies (requires / required by)
- Auth requirements
- Configuration that affects it
- Test specification

### Behavior (F-001.01.01.md)
- Atomic, implementable specification
- Precise behavior description
- Input/output with types
- Complete logic (pseudocode for complex cases)
- Every edge case
- Every error state with exact messages
- Every default value
- Original source location
- Test cases (given/expect)

## ID Format

Hierarchical IDs:
- `F-001` through `F-NNN` for major features
- `F-001.01` through `F-001.NN` for sub-features
- `F-001.01.01` through `F-001.01.NN` for behaviors
- `F-001.01.01a` for sub-behaviors (rare, only if needed)

## JSON Structure

```json
{
  "generated_at": "ISO-8601",
  "product": {
    "name": "from interview",
    "description": "from interview",
    "repos": ["list"]
  },
  "features": [
    {
      "id": "F-001",
      "name": "User Management",
      "tier": "major",
      "detail_file": "details/F-001.md",
      "children": [
        {
          "id": "F-001.01",
          "name": "User Registration",
          "tier": "sub-feature",
          "detail_file": "details/F-001.01.md",
          "children": [
            {
              "id": "F-001.01.01",
              "name": "Email format validation",
              "tier": "behavior",
              "detail_file": "details/F-001.01.01.md",
              "dependencies": ["F-003.01"],
              "depended_on_by": [],
              "complexity": "low",
              "original_locations": ["src/validators/email.ts:15-42"]
            }
          ],
          "dependencies": ["F-003.01", "F-004.02"],
          "depended_on_by": ["F-001.02", "F-005.01"]
        }
      ]
    }
  ],
  "dependency_graph": {
    "nodes": ["F-001.01", "F-003.01", ...],
    "edges": [
      {"from": "F-001.01", "to": "F-003.01", "type": "requires"}
    ]
  },
  "build_order": [
    {"phase": 1, "features": ["F-003.01", "F-004.01"]},
    {"phase": 2, "features": ["F-001.01", "F-001.02"]},
    ...
  ],
  "statistics": {
    "total_major_features": 15,
    "total_sub_features": 87,
    "total_behaviors": 432,
    "by_major_feature": {
      "F-001": {"sub_features": 8, "behaviors": 45},
      ...
    }
  }
}
```
