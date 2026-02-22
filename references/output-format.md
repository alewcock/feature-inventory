# Feature Index Output Format

The output is structured as a linked hierarchy designed for AI/agent team consumption.

## Directory Structure

```
docs/features/
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

## plan.json Schema

The analysis plan includes repo configuration, dimension assignments, and metadata
used by the coverage audit script.

```json
{
  "repos": [
    {
      "name": "repo-name",
      "path": "/absolute/path",
      "languages": ["typescript", "python"],
      "frameworks": ["express", "react"],
      "size": "medium",
      "modules": ["src/auth", "src/billing", "src/core"],
      "dimensions_to_analyze": [
        {
          "dimension": "api-surface",
          "scope": "full",
          "split_by_module": false
        },
        {
          "dimension": "ui-screens",
          "scope": "src/js/remote/pages",
          "split_by_module": false,
          "estimated_source_lines": 4200,
          "files": ["MusicPage.js", "PromotePage.js", "SettingsPage.js"]
        }
      ]
    }
  ],
  "exclude_patterns": [
    "node_modules", "cef_binary", "baseclasses", "FFDShowAPI",
    "NotifyIconWpf", ".Designer.cs", "Properties/Resources"
  ],
  "deduplicate_paths": [
    "Shared library copies that exist in multiple subprojects — only audit one copy"
  ],
  "file_assignments": {
    "src/js/remote/shared/programs.js": "ui-screens--shared",
    "src/js/remote/shared/content_button_group.js": "ui-screens--shared",
    "src/js/remote/shared/playlist_items_ui.js": "ui-screens--shared-large"
  }
}
```

### plan.json Fields

| Field | Required | Description |
|-------|----------|-------------|
| `repos` | Yes | Array of repository configurations |
| `repos[].name` | Yes | Repository name (used as directory name under `raw/`) |
| `repos[].path` | Yes | Absolute filesystem path to the repo |
| `repos[].dimensions_to_analyze` | Yes | Dimensions with scope and splitting config |
| `exclude_patterns` | No | Patterns for third-party/vendor/generated code to exclude from coverage audit |
| `deduplicate_paths` | No | Paths duplicated across subprojects (audit only one copy) |
| `file_assignments` | No | Mapping of every source file >100 lines to its agent task. Gaps here are audit gaps by definition |

The `exclude_patterns` array is consumed by `scripts/coverage-audit.py` to skip files
the product doesn't own. The orchestrator populates this during Step 2 based on
discovery of vendor directories, third-party libraries, and auto-generated code.

The `file_assignments` mapping ensures every significant source file is assigned to
exactly one agent task during planning. Files missing from this mapping will be caught
by the coverage audit.

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
