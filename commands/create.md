---
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: >
  Systematically reverse-engineer every feature, behavior, and capability across one or
  more codebases. Produces a deeply decomposed, hierarchically structured reference
  designed for AI/agent teams to implement a complete rebuild. Interviews the user to
  resolve ambiguity. REQUIRES Agent Teams to be enabled. Run: /feature-inventory [path]
---

# Feature Inventory - Orchestrator

## PREREQUISITE: Agent Teams Required

**Before doing anything else**, verify that Agent Teams is available:

1. Run: `echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
2. If the value is NOT "1", **stop immediately** and tell the user:

   > **This plugin requires Claude Code Agent Teams.**
   >
   > Agent Teams enables parallel analysis across 9 dimensions of your codebase,
   > which is essential for completing the inventory in a reasonable time and
   > within context window limits.
   >
   > To enable, add to `~/.claude/settings.json`:
   > ```json
   > {
   >   "env": {
   >     "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
   >   }
   > }
   > ```
   > Then restart Claude Code and run `/feature-inventory` again.

   **Do not proceed. Do not fall back to sequential subagents.** The plugin is
   designed around Agent Teams' parallel execution, shared task lists, and
   inter-teammate messaging. Without it, dimension analysis would exhaust the
   context window before completing.

3. Also verify you have access to the `TeamCreate` tool. If you attempt to call it
   and it's not available, stop with the same error message above.

---

You are the orchestrator for a comprehensive product reverse-engineering effort. Your
purpose is to produce a specification so complete and deeply decomposed that an AI/agent
team could rebuild the entire product from your output alone, without access to the
original source code.

**Nothing is too small.** A tooltip, a default sort order, a 3-line validation rule, a
retry delay on a queue worker, a CSS breakpoint, an error message string, a pagination
default - everything matters. If the product exhibits it as behavior, it belongs in the
inventory.

**The output is for machines.** Every detail file you produce will be handed to an AI
agent as its implementation specification. Structure accordingly: precise, unambiguous,
with complete schemas, types, rules, and edge cases. No hand-waving.

## Important: Context Window Management

This is a large-scale analysis task. You MUST manage context carefully:

1. **Never load entire codebases into context.** Use `Grep`, `Glob`, and targeted `Read`
   to sample and scan. Delegate deep analysis to sub-agents.
2. **Each sub-agent gets ONE analysis dimension per repo (or per module for large repos).**
   Don't ask an agent to analyze more than one dimension at a time.
3. **If a repo is very large (>500 files), split the agent's work by directory/module.**
   Spawn multiple agents for the same dimension, each scoped to a subtree.
4. **All agents write their findings to disk immediately.** They do NOT return large
   payloads in conversation. They write to `./feature-inventory-output/raw/`.
5. **Resume capability:** The orchestrator checks for existing output files before
   spawning agents. If a dimension's output file already exists and is non-empty, skip
   that agent. This means the user can `/clear` and re-run `/feature-inventory` and it
   picks up where it left off.

## Step 0: User Interview

Before touching any code, interview the user. Legacy products carry decades of implicit
knowledge that is not in the code. This step captures it.

If `./feature-inventory-output/interview.md` already exists, read it, summarize what
you already know, and ask only if there are gaps. Don't re-interview.

Be conversational. Adapt follow-up questions based on their answers. When something is
ambiguous or surprising, dig in. The goal is to understand the product the way a senior
engineer who's worked on it for years would.

### Required Questions

1. **What does this product do?** One paragraph overview. What problem does it solve,
   who uses it, what's the core workflow?

2. **What are the major functional areas?** Ask them to list the top-level features
   as they think of them (e.g., "User management, billing, reporting, inventory
   tracking, notifications"). This becomes your initial feature map to validate against
   the code.

3. **What are the repositories / codebases involved?** Paths, what each one covers,
   how they relate. If they've provided a path already, confirm what's in it.

4. **What's the tech stack?** Languages, frameworks, databases, message queues,
   hosting. This helps agents know what patterns to look for.

5. **Are there any areas of the product that are:**
   - Particularly complex or subtle? (Business rules that took years to get right)
   - Deprecated but still running? (Features nobody uses but the code is still live)
   - Undocumented or only understood by specific people?
   - Known to be buggy or inconsistent? (So we capture intended behavior, not just
     what the code happens to do)

6. **What user roles exist?** Admins, regular users, API consumers, internal tools users,
   etc.

7. **Are there multiple tenants, organizations, or environments** that affect behavior?

8. **What external services does the product depend on?** Payment processors, email
   providers, analytics, CRMs, etc.

9. **Is there anything the code does that you'd want done differently in the rebuild?**
   (Not to change the inventory, but to annotate migration notes.)

10. **Is there anything NOT in the code that's important?** Manual processes,
    workarounds, tribal knowledge, external scripts, database jobs defined outside
    the codebase, etc.

Save answers to `./feature-inventory-output/interview.md` and the user-provided
feature map to `./feature-inventory-output/user-feature-map.md`.

### Handling Ambiguity During Analysis

Throughout Steps 3-4, agents will flag ambiguities with `[AMBIGUOUS]` tags.
The orchestrator should:
1. Collect these as they accumulate.
2. Present them to the user in batches of 5-10 at natural pause points.
3. Save resolved answers to `./feature-inventory-output/clarifications.md`.
4. Feed resolutions back to agents if re-running.

## Step 1: Discovery

Determine what you're working with:

1. If a path argument was provided, use it. Otherwise use the current working directory.
2. Identify all repositories/codebases:
   - If the path IS a repo (has .git, package.json, Cargo.toml, *.sln, etc.), treat it as a single repo.
   - If the path CONTAINS multiple repos, list them all.
3. For each repo, do a quick structural scan:
   - Count files by extension (use `find` + `wc`, don't enumerate)
   - Identify primary languages and frameworks
   - Identify the rough module/directory structure (top 2 levels)
   - Estimate size category: small (<100 files), medium (100-500), large (500-2000), massive (>2000)
4. Write discovery results to `./feature-inventory-output/discovery.json`
5. Cross-check discovery against the user's interview answers. If there are repos or
   components they didn't mention, ask about them.

## Step 2: Plan

Based on discovery AND the user interview, create an analysis plan.

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
        {"dimension": "api-surface", "scope": "full", "split_by_module": false},
        {"dimension": "data-models", "scope": "full", "split_by_module": false},
        {"dimension": "ui-screens", "scope": "full", "split_by_module": true},
        {"dimension": "business-logic", "scope": "src/services,src/domain", "split_by_module": true},
        {"dimension": "integrations", "scope": "full", "split_by_module": false},
        {"dimension": "background-jobs", "scope": "full", "split_by_module": false},
        {"dimension": "auth-and-permissions", "scope": "full", "split_by_module": false},
        {"dimension": "configuration", "scope": "full", "split_by_module": false},
        {"dimension": "events-and-hooks", "scope": "full", "split_by_module": false}
      ]
    }
  ]
}
```

Skip dimensions that clearly don't apply. For large repos where `split_by_module` is
true, spawn separate agents per module directory.

Write to `./feature-inventory-output/plan.json`.

## Step 3: Execute Analysis via Agent Teams

Create an Agent Team for the analysis. You (the lead) coordinate. Teammates do the
analysis in parallel.

### 3a: Create the Team

Use `TeamCreate` to create a team named "feature-inventory". Enable delegate mode
(Shift+Tab) so you focus on coordination, not direct analysis.

### 3b: Spawn Teammates in Batches

For each repo and each dimension in the plan:

1. **Check for existing output:** If `./feature-inventory-output/raw/{repo-name}/{dimension}.md`
   (or `{dimension}--{module}.md` for split analyses) exists and is non-empty, skip it.
2. **Create tasks** via `TaskCreate` for each pending dimension.
3. **Spawn teammates in batches of up to 5.** Each teammate gets ONE dimension for ONE
   repo (or one module chunk if split by module). Assign them the corresponding agent:
   - `feature-inventory:api-analyzer` - api-surface
   - `feature-inventory:data-model-analyzer` - data-models
   - `feature-inventory:ui-analyzer` - ui-screens
   - `feature-inventory:logic-analyzer` - business-logic
   - `feature-inventory:integration-analyzer` - integrations
   - `feature-inventory:jobs-analyzer` - background-jobs
   - `feature-inventory:auth-analyzer` - auth-and-permissions
   - `feature-inventory:config-analyzer` - configuration
   - `feature-inventory:events-analyzer` - events-and-hooks
4. **Each teammate receives** via its task description:
   - The repo path and scope
   - The output file path
   - The product context from `interview.md` (brief summary only)
   - A pointer to read `references/context-management.md` before starting
   - This instruction verbatim: **"Be exhaustive. No behavior is too small. Capture
     every default value, every edge case, every validation rule, every error message,
     every timeout, every sort order, every conditional branch. If you can see it in the
     code, document it. Flag anything ambiguous with [AMBIGUOUS]. This output will be
     the sole reference for an AI agent team rebuilding this feature from scratch."**
5. **Wait for the batch to finish** before spawning the next batch.

Use Sonnet for teammates where possible to manage token costs. The lead (Opus) handles
coordination and the final merge/index generation.

### 3c: Monitor and Collect Ambiguities

While teammates work:
1. Monitor progress via `TaskList`.
2. When teammates flag `[AMBIGUOUS]` items (via `SendMessage` or in their output files),
   collect them.
3. After each batch completes, verify output files exist and are non-empty.
4. Present ambiguities to the user in batches of 5-10 for resolution.
5. Save resolutions to `./feature-inventory-output/clarifications.md`.

### 3d: Handle Failures

If a teammate fails (empty output, error, or context exhaustion):
1. Log the failure.
2. Check if the output file has partial content (the teammate writes incrementally).
3. If partial content exists: note the `## INCOMPLETE` marker for a follow-up pass.
4. If empty: re-queue the dimension for the next batch.
5. After all batches complete, do a cleanup pass: re-spawn teammates for any
   failed/incomplete dimensions.

## Step 4: Build Feature Hierarchy, Index, and Detail Files

This is the most important step. The output must be structured so that an AI/agent team
can pick up any feature and implement it completely.

### 4a: Build the Feature Hierarchy

Read all raw output files. Organize every discovered item into a hierarchical tree:

```
Major Feature (e.g., "User Management")
├── Sub-Feature (e.g., "User Registration")
│   ├── Behavior (e.g., "Email format validation")
│   ├── Behavior (e.g., "Duplicate email check")
│   ├── Behavior (e.g., "Password strength requirements")
│   ├── Behavior (e.g., "Welcome email trigger")
│   ├── Behavior (e.g., "Default role assignment: 'member'")
│   ├── Behavior (e.g., "Registration rate limiting: 5/min per IP")
│   └── Behavior (e.g., "Redirect to onboarding after registration")
├── Sub-Feature (e.g., "User Profile")
│   ├── Behavior (e.g., "Avatar upload with 5MB limit, JPEG/PNG only")
│   ├── Behavior (e.g., "Avatar crop to 200x200")
│   └── ...
└── ...
```

Use the user's feature map from the interview as the starting skeleton. Fill in
everything the code reveals. Add new major features the user didn't mention.

**Assign hierarchical IDs:**
- Major features: `F-001`, `F-002`, ...
- Sub-features: `F-001.01`, `F-001.02`, ...
- Behaviors: `F-001.01.01`, `F-001.01.02`, ...
- Sub-behaviors (if needed): `F-001.01.01a`, `F-001.01.01b`, ...

### 4b: Write the Index (FEATURE-INDEX.md)

This file is the **table of contents only**. Feature/behavior names and links.
No inline details. An agent reading this file should be able to understand the
full scope of the product and navigate to any specific feature.

Write to `./feature-inventory-output/FEATURE-INDEX.md`:

```markdown
# Product Feature Index

> Reverse-engineered specification for AI/agent team implementation
> Generated: {date}
> Product: {name from interview}
> Source repos: {list}
> Total major features: {N}
> Total sub-features: {N}
> Total behaviors: {N}

## Purpose

This index is the master reference for a complete product rebuild. Each entry links
to a detailed specification file containing everything needed for implementation:
data schemas, API contracts, business rules, UI specs, edge cases, error states,
and cross-references to related features.

## How AI/Agent Teams Should Use This

1. Read this index to understand full product scope
2. Use the Dependency Graph to determine build order
3. Pick a feature, follow its link to the detail file
4. Implement from the detail spec (it contains everything needed)
5. Check cross-references for integration points with other features
6. Run the test specifications listed in each detail file

## Feature Hierarchy

### F-001: {Major Feature Name}
- [F-001.01: {Sub-Feature Name}](./details/F-001.01.md)
  - [F-001.01.01: {Behavior Name}](./details/F-001.01.01.md)
  - [F-001.01.02: {Behavior Name}](./details/F-001.01.02.md)
  - [F-001.01.03: {Behavior Name}](./details/F-001.01.03.md)
- [F-001.02: {Sub-Feature Name}](./details/F-001.02.md)
  - ...

### F-002: {Major Feature Name}
...

### F-0XX: Cross-Cutting Concerns
- [F-0XX.01: Error handling patterns](./details/F-0XX.01.md)
- [F-0XX.02: Logging & audit trail](./details/F-0XX.02.md)
- [F-0XX.03: Internationalization / localization](./details/F-0XX.03.md)
- [F-0XX.04: Caching patterns](./details/F-0XX.04.md)
- [F-0XX.05: Pagination patterns](./details/F-0XX.05.md)
- [F-0XX.06: Search patterns](./details/F-0XX.06.md)
- [F-0XX.07: File upload/download patterns](./details/F-0XX.07.md)

## Dependency Graph

| Feature | Depends On | Depended On By |
|---------|-----------|----------------|
| F-001.01 | F-003.01 (Email Service) | F-001.02, F-005.01 |
| ... | ... | ... |

## Suggested Build Order

{Topological sort of the dependency graph, grouped into implementation phases}

## Migration Notes

{From user interview and code analysis: complexity flags, improvement opportunities,
areas where original implementation was known to be problematic}
```

### 4c: Write Detail Files

Create `./feature-inventory-output/details/` directory. For each feature/behavior:

**Major Feature files (F-001.md):**

```markdown
# F-001: {Major Feature Name}

## Overview
{What this feature area covers, in plain language. Why it exists.}

## Sub-Features
| ID | Name | Complexity | Detail |
|----|------|-----------|--------|
| F-001.01 | {name} | {low/medium/high} | [spec](./F-001.01.md) |
| F-001.02 | {name} | {low/medium/high} | [spec](./F-001.02.md) |

## Cross-Cutting Dependencies
- Auth: {what auth/permissions this feature area requires}
- Data: {core entities}
- Integrations: {external services used}

## Implementation Notes for AI/Agent Teams
{High-level approach, suggested decomposition into tasks, known gotchas}
```

**Sub-Feature files (F-001.01.md):**

```markdown
# F-001.01: {Sub-Feature Name}

## Parent
[F-001: {Major Feature Name}](./F-001.md)

## Overview
{What this sub-feature does, why it exists, who uses it}

## Behaviors
| ID | Behavior | Detail |
|----|----------|--------|
| F-001.01.01 | {name} | [spec](./F-001.01.01.md) |
| F-001.01.02 | {name} | [spec](./F-001.01.02.md) |

## Data Model
{Full entity definitions with every field, type, constraint, default, index}
{Use actual schema notation the implementing agent can work from}

## API Contracts
{For each endpoint: method, path, request schema, response schema, status codes,
error response format, rate limits, pagination}

## UI Specification
{Screens involved, form fields, validation messages, loading states, empty states,
error states, responsive behavior, sort/filter options}

## Business Rules
{Every rule as a numbered list. Conditions, actions, edge cases.}

## Events
{Events emitted and consumed, with payload schemas}

## Dependencies
- Requires: {feature IDs}
- Required by: {feature IDs}
- External: {services}

## Configuration
{Env vars, feature flags, settings that affect behavior}

## Auth
{Required permissions, role checks}

## Original Source Locations
{File paths and line ranges in original codebase}

## Test Specification
{What an implementing agent should test: happy paths, edge cases, error conditions,
integration points}

## Implementation Notes for AI/Agent Teams
{Suggested approach, tricky parts, performance considerations, things the original
got wrong that the rebuild should fix (from user interview)}
```

**Behavior files (F-001.01.01.md):**

```markdown
# F-001.01.01: {Behavior Name}

## Parent
[F-001.01: {Sub-Feature Name}](./F-001.01.md)

## Behavior
{Precise, unambiguous description. An AI agent reading only this section should
know exactly what to implement.}

## Input
{Exact fields, types, constraints. Use TypeScript-style type notation or similar.}

## Logic
{Step-by-step. Pseudocode for anything non-trivial. Every conditional branch.}

## Output / Side Effects
{Return values, database writes, events fired, emails sent, cache updates}

## Edge Cases
{Every edge case found in the code, numbered}

## Error States
{Every error condition: what triggers it, error code/message, how it's surfaced}

## Defaults
{Every default value used}

## Original Source
`{file_path}:{line_start}-{line_end}`

## Test Cases
{Concrete test cases the implementing agent should write}
1. Given {input}, expect {output}
2. Given {edge case}, expect {behavior}
3. Given {error condition}, expect {error response}
```

### 4d: Write JSON version

Write `./feature-inventory-output/FEATURE-INDEX.json` with the full structured hierarchy
for programmatic consumption by agent orchestrators.

## Step 5: Validation & Summary

1. **Cross-check against user's feature map.** Every feature they mentioned should appear.
   Flag any missing.
2. **Count check.** Report totals by tier.
3. **Coverage check.** Any raw outputs that didn't map to features?
4. **Orphan check.** Any code that doesn't seem to belong to any feature?
5. **Present summary** with counts, coverage, unresolved ambiguities, and file locations.
6. **Ask the user** to review the index and flag anything missing or miscategorized.

## Resume Behavior

If re-run after `/clear` or interruption:
- Step 0: Skip if `interview.md` exists (load it for context).
- Step 1: Re-run unless `discovery.json` exists.
- Step 2: Re-run unless `plan.json` exists and discovery hasn't changed.
- Step 3: Skip completed dimensions (check raw output files).
- Step 4: Always re-run to regenerate from all available raw files.
