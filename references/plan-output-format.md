# Plan Output Format

The plan output transforms a completed feature inventory into implementation-ready plans
organized by feature area. Plans are prose documents — blueprints, not code.

## Directory Structure

```
docs/plans/
├── interview.md                    # Strategic rebuild interview
├── research.md                     # Target tech stack research + existing code analysis
├── plan-config.json                # Planning configuration (tech stack, architecture decisions)
├── PLAN-INDEX.md                   # Master plan index (human-readable)
├── PLAN-INDEX.json                 # Machine-readable plan index
└── features/                       # One plan per major feature area
    ├── F-001/
    │   ├── plan.md                 # Full implementation plan
    │   ├── plan-tdd.md             # TDD test stubs mirroring plan structure
    │   └── sections/               # Implementable sections
    │       ├── index.md            # Section index with dependency graph
    │       ├── section-01-*.md     # Individual section files
    │       ├── section-02-*.md
    │       └── ...
    ├── F-002/
    │   └── ...
    └── cross-cutting/
        ├── plan.md                 # Shared infrastructure plan
        ├── plan-tdd.md
        └── sections/
            └── ...
```

## PLAN-INDEX.md

The master index summarizes all feature plans with links, dependencies, and suggested
implementation order. It is a TABLE OF CONTENTS — not the plans themselves.

```markdown
# Implementation Plan Index

> Product: {name from inventory}
> Target stack: {from interview/research}
> Generated: {date}
> Feature inventory: {inventory path}
> Total feature plans: {N}
> Total implementation sections: {N}

## Rebuild Strategy

{Summary of strategic decisions from interview: why rebuilding, scope, architecture changes}

## Target Architecture

{High-level architecture description based on interview and research}

## Feature Plans

### Phase 1: Foundation

| Feature | Plan | Sections | Depends On | Status |
|---------|------|----------|------------|--------|
| F-003: Infrastructure | [plan](./features/F-003/plan.md) | 4 | - | Ready |
| F-004: Data Layer | [plan](./features/F-004/plan.md) | 3 | F-003 | Ready |

### Phase 2: Core Features

| Feature | Plan | Sections | Depends On | Status |
|---------|------|----------|------------|--------|
| F-001: User Management | [plan](./features/F-001/plan.md) | 6 | F-003, F-004 | Ready |
| ... | ... | ... | ... | ... |

### Phase 3+: ...

## Cross-Cutting Concerns

| Concern | Plan | Sections |
|---------|------|----------|
| Error Handling | [plan](./features/cross-cutting/plan.md) | 2 |
| Logging & Monitoring | [plan](./features/cross-cutting/plan.md) | 1 |

## Tech Stack Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | {e.g., TypeScript} | {from interview/research} |
| Framework | {e.g., Next.js} | {from interview/research} |
| Database | {e.g., PostgreSQL} | {from interview/research} |
| ... | ... | ... |
```

## PLAN-INDEX.json

```json
{
  "generated_at": "ISO-8601",
  "product": {
    "name": "from inventory",
    "description": "from inventory"
  },
  "inventory_path": "./docs/features",
  "target_stack": {
    "languages": ["typescript"],
    "frameworks": ["next.js", "prisma"],
    "databases": ["postgresql"],
    "infrastructure": ["docker", "aws"],
    "testing": ["jest", "playwright"]
  },
  "rebuild_strategy": {
    "scope": "1:1 rebuild | minimum + additions | selective",
    "architecture_changes": ["description of changes"],
    "additional_features": ["if scope is not 1:1"]
  },
  "feature_plans": [
    {
      "feature_id": "F-001",
      "feature_name": "User Management",
      "plan_file": "features/F-001/plan.md",
      "tdd_file": "features/F-001/plan-tdd.md",
      "section_count": 6,
      "sections": [
        {
          "name": "section-01-data-models",
          "file": "features/F-001/sections/section-01-data-models.md",
          "depends_on": []
        }
      ],
      "depends_on": ["F-003", "F-004"],
      "phase": 2,
      "inventory_behaviors": 45,
      "existing_code_status": "not_started | partial | done"
    }
  ],
  "implementation_phases": [
    {
      "phase": 1,
      "name": "Foundation",
      "features": ["F-003", "F-004"]
    },
    {
      "phase": 2,
      "name": "Core Features",
      "features": ["F-001", "F-002"]
    }
  ],
  "statistics": {
    "total_feature_plans": 15,
    "total_sections": 72,
    "total_behaviors_covered": 432,
    "existing_code_coverage": "33% (from gap analysis if available)"
  }
}
```

## Feature Plan File (plan.md)

Each feature plan is a **prose document** describing how to implement the feature
in the target architecture. It is self-contained — an implementer should be able to
read this single file and understand everything needed.

### Structure

```markdown
---
title: "Implementation Plan: {Feature ID} — {Feature Name}"
type: feat
status: active
date: {YYYY-MM-DD}
feature_id: {Feature ID}
phase: {N}
depends_on: [{feature IDs}]
behaviors: {N}
sections: {N}
inventory: "{path to inventory detail file}"
---

# Implementation Plan: {Feature ID} — {Feature Name}

> Inventory spec: {link to inventory detail file}
> Behaviors to implement: {N}
> Estimated sections: {N}
> Depends on: {feature IDs}
> Phase: {N}

## Overview

{What this feature does in the target system. Written for someone who has never
seen the original product. Include the "why" — what problem it solves.}

## Existing Code Status

{If gap analysis exists: what's already built, what's partial, what's missing.
If no existing code: "Greenfield implementation."}

## Architecture

{How this feature fits into the target architecture. Key components, their
responsibilities, and how they interact. Include a component diagram if helpful.}

### Data Model

{Target data model — entities, fields, types, relationships. Show how it maps
from the original. Note any schema differences.}

### API Design

{Target API endpoints — paths, methods, request/response shapes. Note any
changes from the original API surface.}

### UI Components

{Target UI structure — pages, components, state management. Note any UX changes.}

## System-Wide Impact Analysis

{Trace the side effects and integration points of this feature across the system.
This section helps implementers and reviewers understand the full blast radius.}

### Interaction Graph

{What callbacks, middleware, observers, hooks, or event handlers fire when this
feature's operations execute? Trace at least 2 levels deep from each entry point.}

### Error & Failure Propagation

{How do errors from this feature flow across layers? What happens to callers when
this feature's operations fail? What are the retry, fallback, and degradation
strategies?}

### State Lifecycle Risks

{Can partial failure leave orphaned state? Database rows without matching records
in related tables? Stale cache entries? Unreleased locks or file handles? For each
risk, describe the mitigation strategy.}

### API Surface Parity

{What other interfaces (CLI, internal APIs, webhooks, event consumers) need to
expose or react to the same operations? Ensure feature changes propagate to all
entry points, not just the primary API/UI.}

## Implementation Sections

| # | Section | Focus | Depends On |
|---|---------|-------|------------|
| 1 | Data models & migrations | Schema, entities, relationships | - |
| 2 | Core business logic | Rules, calculations, workflows | 1 |
| 3 | API endpoints | Routes, handlers, validation | 1, 2 |
| 4 | UI components | Pages, forms, state | 3 |
| 5 | Background jobs | Queues, scheduled tasks | 1, 2 |
| 6 | Integration tests | End-to-end verification | 1-5 |

## Section Details

### Section 1: Data Models & Migrations

**Behaviors covered:** F-001.01.01 through F-001.01.05

{Prose description of what to build. Data model definitions with field types.
Migration strategy. Seed data requirements. Constraints and indexes.}

### Section 2: Core Business Logic

**Behaviors covered:** F-001.02.01 through F-001.02.12

{Prose description of business rules, calculations, state machines, workflows.
Edge cases and error handling strategy. Integration points with other features.}

{Continue for each section...}

## Monitoring & Observability

{Guidance for what to monitor when this feature is deployed. This section feeds
directly into post-deploy verification and PR descriptions.}

### Key Metrics

{What counters, gauges, or histograms should be emitted? E.g., request latency,
error rates per operation, queue depths, cache hit ratios.}

### Log Points

{What should be logged and at what level? Focus on operations that help diagnose
production issues: key state transitions, external API calls, authorization
decisions, data mutations.}

### Health Checks

{What endpoint or probe verifies this feature is working? What queries or
commands validate correct behavior after deployment?}

### Failure Signals & Rollback Triggers

{What metrics or log patterns indicate this feature is broken? What thresholds
should trigger investigation or rollback?}

## Migration Notes

{From inventory: complexity flags, known issues, things to do differently.
From interview: user's priorities and concerns for this feature.}

## Behaviors Checklist

Every behavior from the inventory that this plan covers:

- [ ] F-001.01.01: Email format validation → Section 1
- [ ] F-001.01.02: Duplicate email check → Section 2
- [ ] F-001.01.03: Password strength requirements → Section 2
{... every behavior mapped to its section}
```

## Feature TDD File (plan-tdd.md)

Mirrors the plan structure with test stubs for each section. Test stubs are prose
descriptions or minimal signatures — NOT full test implementations.

```markdown
---
title: "TDD Plan: {Feature ID} — {Feature Name}"
type: feat
status: active
date: {YYYY-MM-DD}
feature_id: {Feature ID}
---

# TDD Plan: {Feature ID} — {Feature Name}

## Testing Framework

{Framework choice and rationale. Test file locations. Naming conventions.}

## Section 1: Data Models & Migrations

### Tests to write BEFORE implementing:

- Test: User entity has all required fields (name, email, passwordHash, createdAt, updatedAt)
- Test: Email field has unique constraint
- Test: CreatedAt defaults to current timestamp
- Test: Migration creates users table with correct schema
- Test: Migration is reversible

## Section 2: Core Business Logic

### Tests to write BEFORE implementing:

- Test: Email validation rejects invalid formats (list specific cases)
- Test: Email validation accepts valid formats (list specific cases)
- Test: Password strength rejects passwords under 8 characters
- Test: Password strength requires at least one uppercase letter
{... test stubs for each section}
```

## Section Index (sections/index.md)

```markdown
<!-- PROJECT_CONFIG
runtime: {runtime environment, e.g., node, python-uv, go, rust-cargo}
test_command: {command to run tests, e.g., npm test, uv run pytest, go test ./...}
build_command: {command to build, e.g., npm run build, go build ./...}
lint_command: {command to lint, e.g., npm run lint, ruff check .}
END_PROJECT_CONFIG -->

<!-- SECTION_MANIFEST
section-01-data-models
section-02-business-logic
section-03-api-endpoints
section-04-ui-components
section-05-background-jobs
section-06-integration-tests
END_MANIFEST -->

# Implementation Sections: {Feature ID} — {Feature Name}

## Dependency Graph

| Section | Depends On | Blocks |
|---------|------------|--------|
| section-01-data-models | - | 02, 03, 05 |
| section-02-business-logic | 01 | 03, 05, 06 |
| section-03-api-endpoints | 01, 02 | 04, 06 |
| section-04-ui-components | 03 | 06 |
| section-05-background-jobs | 01, 02 | 06 |
| section-06-integration-tests | 01-05 | - |

## Execution Order

1. section-01-data-models (no dependencies)
2. section-02-business-logic (after 01)
3. section-03-api-endpoints, section-05-background-jobs (parallel, after 02)
4. section-04-ui-components (after 03)
5. section-06-integration-tests (after all)
```

## Section Files (section-*.md)

Each section file is **completely self-contained**. An implementer reads only this
file and can start building immediately.

```markdown
---
title: "Section: {section-name}"
type: feat
status: active
date: {YYYY-MM-DD}
feature_id: {Feature ID}
feature_name: {Feature Name}
section: {section-NN-name}
depends_on_sections: [{section dependencies}]
behaviors_covered: {count}
---

# Section: {section-name}

> Feature: {Feature ID} — {Feature Name}
> Target stack: {key technologies from plan-config}
> Depends on: {section dependencies, or "None"}
> Behaviors covered: {count} ({behavior ID range})

## Context

{What this section implements and why. How it fits into the feature.}

## Architecture

{How the components in this section fit together. Key design decisions and their
rationale. Interface contracts with other sections (what this section provides,
what it consumes).}

## What to Build

{Detailed prose description of everything in this section. Data models with
field types, API endpoints with request/response shapes, business rules with
edge cases, UI components with state management.}

## Data Model

{If this section involves data model work: entity definitions with field types,
constraints, relationships, indexes. Schema migration approach.
Omit this section if not applicable.}

## API Contracts

{If this section involves API work: endpoint definitions with paths, methods,
request/response shapes, auth requirements, error responses.
Omit this section if not applicable.}

## System-Wide Impact

{Side effects of this section's changes. What callbacks, middleware, or event
handlers fire? Can partial failure leave orphaned state? What other interfaces
need matching changes? Keep this focused on this section's scope.}

## Tests to Write First (TDD)

{Test stubs from plan-tdd.md for this section only.}

- Test: {description of what to test}
- Test: {description of what to test}
{... one stub per test}

## Existing Code

{If gap analysis detected partial implementation: what exists, what's missing,
where the existing code is located.
If no existing code: "Greenfield implementation — no existing code for these behaviors."}

## Monitoring & Observability

{What metrics, log points, and health checks should be added as part of this
section's implementation. What failure signals indicate problems with this
specific section's functionality.}

## Acceptance Criteria

{How to verify this section is complete. List every behavior ID and what
"done" looks like for each.}

- [ ] {behavior_id}: {behavior name} — {what constitutes completion}
- [ ] {behavior_id}: {behavior name} — {what constitutes completion}
{... one per behavior}

## Inventory References

{For precise specifications of each behavior (exact validation rules, error messages,
edge cases, field types), refer to the inventory detail files:}

{List of inventory detail file paths for behaviors in this section}
```

## How AI/Agent Teams Should Use This

1. Read `PLAN-INDEX.json` to understand full scope and implementation order
2. Follow the phase ordering (respects dependency graph from inventory)
3. For each feature in the current phase:
   a. Read the feature's `plan.md` for full context
   b. Read `plan-tdd.md` for the testing approach
   c. Follow `sections/index.md` for execution order within the feature
   d. Implement one section at a time, starting with its TDD stubs
4. Cross-cutting plans should be implemented before feature-specific work
5. Reference the original inventory detail files for precise behavior specs

## Compatibility with Implementation Tools

Plan output is designed to work with multiple implementation workflows:

### Compound Engineering (`/workflows:work`)

Each section file can be passed directly to `/workflows:work` as a plan file:
```
/workflows:work docs/plans/features/F-001/sections/section-01-data-models.md
```

The section files include YAML frontmatter, acceptance criteria with checkboxes,
TDD stubs, and monitoring guidance — all of which `/workflows:work` uses to
break the section into tasks, run continuous tests, and create PRs with
post-deploy monitoring sections.

After implementation, use `/workflows:review` to run multi-agent code review,
and `/workflows:compound` to document solutions for future reference.

### Deep-Implement (`/deep-implement`)

The `sections/index.md` includes `PROJECT_CONFIG` and `SECTION_MANIFEST` blocks
that `/deep-implement` parses to drive its sequential TDD implementation loop.
Point it at the sections directory:
```
/deep-implement @docs/plans/features/F-001/sections/.
```

### Direct Agent Usage

Each section file is self-contained — an AI agent reads only that file and can
start implementing immediately. No prior context needed. The YAML frontmatter
provides machine-readable metadata, and inventory references link to precise
behavior specifications.
