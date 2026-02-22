---
name: feature-synthesizer
description: >
  Takes a single major feature area and the raw dimension outputs, cross-references
  all dimensions (API, data models, UI, business logic, auth, events, jobs, integrations,
  config) to produce complete detail files for every sub-feature and behavior in that
  feature area. Supports two modes: "create" for new synthesis and "verify" for checking
  existing detail files against raw outputs and patching gaps.
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
- `mode`: Either `"create"` or `"verify"`
  - **create**: No existing detail files. Build everything from scratch.
  - **verify**: Existing detail files from a previous run. Check them against the raw
    outputs, find gaps, and patch missing information.
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

## Mode Selection

Check your `mode` input and follow the appropriate workflow:

- **`create` mode**: Follow the **Synthesis Process** below (build from scratch).
- **`verify` mode**: Follow the **Verify and Improve Process** below (audit existing
  files and patch gaps).

---

## Synthesis Process (create mode)

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

Before finishing each sub-feature (in either mode), verify:
- [ ] Every entity mentioned in data-models is referenced in the sub-feature file
- [ ] Every endpoint from api-surface that serves this sub-feature is included
- [ ] Every UI screen/component from ui-screens is included
- [ ] Every business rule from business-logic is captured
- [ ] Every event from events-and-hooks is listed
- [ ] Every config/env var from configuration is noted
- [ ] Auth requirements are specified
- [ ] External integrations are documented
- [ ] Behaviors decomposed to atomic level (no behavior covers more than one distinct action)

---

## Verify and Improve Process (verify mode)

Existing detail files were produced by a previous run but may be incomplete — missing
information that IS in the raw dimension outputs. Your job is to audit every existing
file against the raw data and patch whatever's missing.

### Phase 1: Inventory Existing Files

1. Use `Glob` to find all existing detail files for your feature area:
   ```
   Glob: {output_path}/{feature_id}*.md
   ```
2. Build a list of what exists:
   - Major feature file: `{feature_id}.md`
   - Sub-feature files: `{feature_id}.01.md`, `{feature_id}.02.md`, etc.
   - Behavior files: `{feature_id}.01.01.md`, `{feature_id}.01.02.md`, etc.
3. Note any sub-features from the `sub_features` input that have NO corresponding file
   (these need full creation, not just verification).

### Phase 2: Verify and Patch Each Sub-Feature

For each sub-feature, one at a time:

#### 2a: Read the existing sub-feature file

Read the existing `{feature_id}.{sub_id}.md` file. Note what sections it has and
roughly what content is in each:
- Does it have a Data Model section? How many entities/fields?
- Does it have API Contracts? How many endpoints?
- Does it have UI Specification? How detailed?
- Does it have Business Rules? How many rules?
- Does it have Events, Dependencies, Configuration, Auth sections?
- How many behaviors are listed in the Behaviors table?

#### 2b: Cross-check against each raw dimension

Go dimension by dimension, just like create mode. For each dimension:

1. **Grep the raw file** using section_hints to find the relevant section.
2. **Read that section** (with line ranges, max ~150 lines).
3. **Compare against what's in the existing detail file:**
   - Are there entities/fields in the raw that are missing from the detail file?
   - Are there endpoints in the raw that aren't listed in the detail file?
   - Are there business rules in the raw that aren't captured?
   - Are there events, config vars, auth details in the raw but not the detail file?
4. **Track all gaps** found for this sub-feature.

#### 2c: Check behavior coverage

1. List the behaviors in the existing sub-feature file's Behaviors table.
2. Compare against what the raw data describes. Look for:
   - **Missing behaviors**: Things in the raw data with no corresponding behavior file.
     Common misses: individual validation rules, specific error paths, side effects
     (emails, events), default value assignments, rate limits, edge cases that are
     distinct enough to be their own behavior.
   - **Under-specified behaviors**: Behavior files that exist but are thin — missing
     edge cases, error states, defaults, or test cases that the raw data documents.
   - **Missing behavior files**: Behaviors listed in the sub-feature table but with
     no corresponding `.md` file in the details directory.

#### 2d: Patch the gaps

For each gap found:

- **Missing section content** (e.g., no events section, or data model is incomplete):
  Use `Edit` to add the missing information to the existing sub-feature file. Don't
  rewrite the whole file — surgically add what's missing.

- **Missing behaviors**: Create new behavior files. Assign the next available behavior
  ID (e.g., if `F-001.01.05` is the last existing behavior, new ones start at
  `F-001.01.06`). Also update the sub-feature file's Behaviors table to include them.

- **Under-specified behavior files**: Use `Edit` to add missing edge cases, error
  states, defaults, or test cases to existing behavior files.

- **Entirely missing sub-feature**: If a sub-feature has no file at all, fall back to
  the full create-mode workflow (Phase 2 of the Synthesis Process) for that sub-feature.

#### 2e: Move to next sub-feature

After patching all gaps for a sub-feature, move to the next. Don't revisit.

### Phase 3: Verify the Major Feature File

1. Read the existing `{feature_id}.md`.
2. Check that its Sub-Features table lists ALL sub-features (including any new ones
   created during patching).
3. Check that Cross-Cutting Dependencies are accurate and complete.
4. Patch if needed using `Edit`.

### Phase 4: Report

After all sub-features are verified and patched:

```
Feature {feature_id} ({feature_name}) verification complete.
- Sub-features verified: {N}
- Sub-features created (were missing): {N}
- Behaviors added: {N}
- Behaviors improved: {N}
- Sections patched: {N}
- Total detail files now: {N}
- Ambiguities found: {N}
```
