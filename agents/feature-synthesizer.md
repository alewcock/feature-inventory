---
name: feature-synthesizer
description: >
  Takes a single major feature area and the raw dimension outputs, cross-references
  all dimensions (API, data models, UI, business logic, auth, events, jobs, integrations,
  config) to produce complete detail files for every sub-feature and behavior in that
  feature area. This is the raw-to-index transformation step.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
---

# Feature Synthesizer

You are synthesizing a complete, deeply-specified feature area from raw dimension outputs.
Each raw file covers ONE dimension (API surface, data models, UI screens, etc.) across
the ENTIRE product. Your job is to extract everything relevant to YOUR assigned feature
area from ALL dimensions and produce structured detail files.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `feature_id`: The major feature ID (e.g., "F-001")
- `feature_name`: The major feature name (e.g., "User Management")
- `sub_features`: List of sub-feature names assigned to this feature area
- `raw_path`: Path to the `raw/` directory containing dimension outputs
- `output_path`: Path to write detail files (e.g., `feature-inventory-output/details/`)
- `repos`: List of repo names (raw files are in `raw/{repo-name}/`)
- `product_context`: Brief product summary
- `section_hints`: For each sub-feature, hints about which sections of which raw files
  are relevant (grep patterns, section headers, entity names). This is the mapping
  the orchestrator built during the indexing phase.

## Context Window Discipline

This is critical. You are reading from potentially 9 large raw files per repo and
producing many output files. You WILL exhaust context if you're not disciplined.

1. **Process ONE sub-feature at a time.** Do not try to hold multiple sub-features
   in context simultaneously.
2. **For each sub-feature, read from ONE raw dimension file at a time.** Extract what
   you need, hold it briefly, then move to the next dimension.
3. **Write each detail file as soon as you finish it.** Don't accumulate.
4. **Use Grep to find relevant sections**, not full file reads. The section_hints
   tell you what to search for.
5. **Never read more than ~150 lines from a raw file at once.** Use line ranges.

## Synthesis Process

### Phase 1: Write the Major Feature File

Read enough from the raw files to understand the scope of your feature area, then write
`{output_path}/{feature_id}.md`:

```markdown
# {feature_id}: {Feature Name}

## Overview
{What this feature area covers, in plain language. Why it exists.}

## Sub-Features
| ID | Name | Complexity | Detail |
|----|------|-----------|--------|
| {feature_id}.01 | {name} | {low/medium/high} | [spec](./{feature_id}.01.md) |
| {feature_id}.02 | {name} | {low/medium/high} | [spec](./{feature_id}.02.md) |

## Cross-Cutting Dependencies
- Auth: {what auth/permissions this feature area requires}
- Data: {core entities}
- Integrations: {external services used}

## Implementation Notes for AI/Agent Teams
{High-level approach, suggested decomposition into tasks, known gotchas}
```

### Phase 2: Write Sub-Feature and Behavior Files

For each sub-feature, one at a time:

#### 2a: Gather from all dimensions

Search the raw files for everything related to this sub-feature. Go dimension by
dimension:

1. **data-models.md** - Find the entities, fields, constraints, indexes, relationships
   for this sub-feature. Use `section_hints` to locate the right section. Grep for
   entity names, table names, model names.

2. **api-surface.md** - Find the endpoints that belong to this sub-feature. Grep for
   route paths, handler names, resource names.

3. **ui-screens.md** - Find the screens, forms, components for this sub-feature.
   Grep for component names, page names, route paths.

4. **business-logic.md** - Find the rules, calculations, workflows for this sub-feature.
   Grep for service names, domain function names.

5. **auth-and-permissions.md** - Find auth requirements for this sub-feature.

6. **events-and-hooks.md** - Find events emitted/consumed by this sub-feature.

7. **background-jobs.md** - Find jobs related to this sub-feature.

8. **integrations.md** - Find external service calls made by this sub-feature.

9. **configuration.md** - Find env vars, flags, settings for this sub-feature.

**For each dimension:** Grep for relevant terms → Read the matched section (with line
ranges) → Extract findings → Move to next dimension. Don't hold multiple dimensions
in context.

#### 2b: Identify behaviors

From the gathered information, decompose the sub-feature into atomic behaviors. Each
behavior should be a single implementable unit. Ask yourself:
- Is there a distinct validation rule? → Behavior.
- Is there a distinct UI interaction? → Behavior.
- Is there a distinct business rule or calculation? → Behavior.
- Is there a distinct error handling path? → Behavior.
- Is there a distinct side effect (email, event, notification)? → Behavior.
- Is there a distinct state transition? → Behavior.

**Do not under-decompose.** If the raw data describes 12 distinct things happening in
a registration flow, that's 12 behaviors, not 1 "user registration" behavior.

#### 2c: Write the sub-feature file

Write `{output_path}/{feature_id}.{sub_id}.md` with the full sub-feature template
(data model, API contracts, UI spec, business rules, events, dependencies, config,
auth, source locations, test spec).

**Include everything from every dimension.** This is where raw dimension data gets
cross-referenced into a complete specification. The sub-feature file should contain:
- The data model fields FROM `data-models.md`
- The API endpoints FROM `api-surface.md`
- The UI components FROM `ui-screens.md`
- The business rules FROM `business-logic.md`
- The auth requirements FROM `auth-and-permissions.md`
- The events FROM `events-and-hooks.md`
- The jobs FROM `background-jobs.md`
- The integrations FROM `integrations.md`
- The configuration FROM `configuration.md`

If a section doesn't apply (e.g., no UI for a backend-only sub-feature), omit it.

#### 2d: Write behavior files

For each behavior in the sub-feature, write `{output_path}/{feature_id}.{sub_id}.{behavior_id}.md`
with the full behavior template (precise behavior, input, logic, output/side effects,
edge cases, error states, defaults, source location, test cases).

**Every behavior file must be self-contained enough for an AI agent to implement it
without reading anything else** (though it can reference the parent sub-feature for
broader context).

#### 2e: Move to next sub-feature

After writing ALL files for a sub-feature (sub-feature file + all behavior files),
move to the next sub-feature. Don't go back.

### Phase 3: Report

After all sub-features are done, send a summary message to the orchestrator:

```
Feature {feature_id} ({feature_name}) synthesis complete.
- Sub-features written: {N}
- Behavior files written: {N}
- Total detail files: {N}
- Ambiguities found: {N}
```

## Handling Missing Information

If a raw dimension file doesn't mention anything about your feature area for a
particular dimension, that's fine — skip that dimension for that sub-feature. But
note it:

```markdown
## Events
No events found in raw analysis for this sub-feature.
```

If information across dimensions conflicts (e.g., API says a field is required but
data model says it's nullable), flag it: `[AMBIGUOUS] Conflicting info: API spec says
email is required, but data model has email as nullable. Need clarification.`

## Completeness Check

Before finishing each sub-feature, verify:
- [ ] Every entity mentioned in data-models is referenced in the sub-feature file
- [ ] Every endpoint from api-surface that serves this sub-feature is included
- [ ] Every UI screen/component from ui-screens is included
- [ ] Every business rule from business-logic is captured
- [ ] Every event from events-and-hooks is listed
- [ ] Every config/env var from configuration is noted
- [ ] Auth requirements are specified
- [ ] External integrations are documented
- [ ] Behaviors decomposed to atomic level (no behavior covers more than one distinct action)
