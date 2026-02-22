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

Skip dimensions that clearly don't apply.

### Splitting Strategy

Splitting is critical to prevent context exhaustion. A single agent cannot adequately
analyze thousands of lines of source code — it will triage and produce shallow stubs.
Apply these rules:

1. **Per-module split** (`split_by_module: true`): For repos with >500 source files OR
   any dimension where the relevant source directories total >2,000 lines, split into
   separate agent tasks per top-level module/directory.

2. **Per-file split**: After identifying the files each agent will analyze, check file
   sizes. Any individual source file >500 lines gets its own dedicated agent task:
   ```json
   {
     "dimension": "ui-screens",
     "scope": "src/js/remote/ControlCenter.js",
     "split_by_module": false,
     "reason": "Single file, 1433 lines"
   }
   ```

3. **Estimating scope**: During discovery (Step 1), collect line counts per directory.
   Use these to make splitting decisions. When in doubt, split more aggressively —
   two agents covering 500 lines each produce better output than one agent triaging
   1,000 lines.

4. **Minimum analysis depth**: Record the total source lines each agent will cover in
   `plan.json`. This is used by the coverage audit in Step 3.5.

```json
{
  "dimension": "ui-screens",
  "scope": "src/js/remote/pages",
  "split_by_module": false,
  "estimated_source_lines": 4200,
  "files": ["MusicPage.js", "PromotePage.js", "SettingsPage.js", "..."]
}
```

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

## Step 3.5: Source Coverage Audit (Mandatory — Blocks Step 4)

**This step is automated and mandatory.** Do NOT skip it. Do NOT proceed to Step 4
until every gap identified here is resolved.

The raw analysis may have covered some source files thoroughly and others barely at all.
This step catches the gaps before synthesis, when they're cheapest to fix.

### 3.5a: Build Source File Inventory

For each repo in the plan, enumerate all source files that should have been analyzed:

```bash
# Get all source files with line counts, sorted by size descending
find {repo_path} -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \
  -o -name "*.py" -o -name "*.rb" -o -name "*.cs" -o -name "*.java" -o -name "*.go" \
  -o -name "*.vue" -o -name "*.svelte" -o -name "*.php" -o -name "*.razor" \) \
  ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/dist/*" ! -path "*/build/*" \
  ! -path "*/vendor/*" ! -path "*/__pycache__/*" \
  | xargs wc -l | sort -rn
```

### 3.5b: Check Coverage Per File

For each source file >100 lines, check that it appears in the raw output with adequate
depth:

1. **Grep each filename** (just the basename) across all raw output files for its repo.
2. **Count the lines of analysis** that reference or describe that file.
3. **Apply the proportionality threshold:**
   - Required minimum analysis lines = `ceil(source_lines / 50)`
   - Example: a 1,433-line file needs at least 29 lines of analysis
4. **Flag files that fail:**
   - NO mentions in any raw file → `MISSING`
   - Mentioned but below threshold → `SHALLOW`
   - Contains `## INCOMPLETE` marker → `INCOMPLETE`

### 3.5c: Write Coverage Report

Write to `./feature-inventory-output/coverage-audit.json`:

```json
{
  "audit_date": "ISO-8601",
  "total_source_files": 156,
  "total_source_lines": 48230,
  "files_over_100_lines": 89,
  "coverage": {
    "adequate": 72,
    "shallow": 8,
    "missing": 5,
    "incomplete": 4
  },
  "gaps": [
    {
      "file": "src/js/remote/ControlCenter.js",
      "source_lines": 1433,
      "analysis_lines": 1,
      "required_lines": 29,
      "status": "SHALLOW",
      "relevant_dimensions": ["ui-screens"],
      "suggested_action": "Re-analyze as dedicated agent task"
    },
    {
      "file": "src/js/remote/PlaylistItemsUI.js",
      "source_lines": 2775,
      "analysis_lines": 4,
      "required_lines": 56,
      "status": "SHALLOW",
      "relevant_dimensions": ["ui-screens", "business-logic"],
      "suggested_action": "Re-analyze as dedicated agent task"
    }
  ]
}
```

### 3.5d: Re-Queue Gaps

**This is a hard gate.** If there are ANY gaps with status MISSING, SHALLOW, or
INCOMPLETE:

1. **Do NOT proceed to Step 4.**
2. For each gap, create a new agent task scoped to that specific file or small group of
   related files. Use the same dimension analyzer but with a narrow scope:
   ```
   scope: "src/js/remote/ControlCenter.js"
   output_path: "raw/{repo-name}/ui-screens--ControlCenter.md"
   ```
3. Spawn gap-filling teammates in batches of up to 5.
4. After gap-fill agents complete, **re-run the coverage audit** (go back to 3.5b).
5. Repeat until all files meet the proportionality threshold or are genuinely trivial
   (orchestrator judgment — a 150-line config file with only constant definitions may
   legitimately need only 3 lines of analysis).
6. Only proceed to Step 4 when the coverage report shows 0 gaps, or the orchestrator
   has reviewed and accepted each remaining gap as legitimate.

### 3.5e: Present Audit Summary

Show the user:

```
Source Coverage Audit
=====================
Total source files: {N} ({total lines})
Files >100 lines: {N}

Coverage: {adequate}/{total} files adequately analyzed ({%})

Gaps found: {N}
  - MISSING (not analyzed at all): {N}
  - SHALLOW (below proportionality threshold): {N}
  - INCOMPLETE (agent ran out of context): {N}

{If gaps > 0:}
Re-queuing {N} files for targeted re-analysis...
{list files and their dimensions}

{If gaps == 0:}
All source files adequately covered. Proceeding to synthesis.
```

## Step 4: Build Feature Hierarchy, Index, and Detail Files

This is the most important step and is **parallelized via Agent Teams** just like Step 3.
The raw dimension files are organized by dimension (API, data models, etc.) but the
output must be organized by feature. This cross-cutting pivot is too large for a single
context window — it requires reading from up to 9 dimension files per repo and producing
hundreds of detail files.

### 4a: Build the Feature Map (Orchestrator — lightweight scan)

**Do NOT read all raw files in full.** Instead, skim them to build a mapping of what
belongs to which feature area.

1. Read `user-feature-map.md` to get the starting skeleton of feature areas.
2. For each raw dimension file, read **only the section headers and summary** (first
   30-50 lines, plus any `## Summary` or `### {Group Name}` headers). Use Grep to
   extract section headers:
   ```
   Grep for: "^##" in each raw file to get all section headings
   ```
3. Map each section/group to a major feature area. Build a lightweight mapping:

Write to `./feature-inventory-output/synthesis-plan.json`:

```json
{
  "feature_areas": [
    {
      "id": "F-001",
      "name": "User Management",
      "sub_features": [
        {
          "name": "User Registration",
          "section_hints": {
            "api-surface": ["### Users", "POST /api/users", "POST /api/auth/register"],
            "data-models": ["### User", "### Account"],
            "ui-screens": ["### Registration", "### Signup"],
            "business-logic": ["### Registration", "### User creation"],
            "auth-and-permissions": ["### Registration", "### Public routes"],
            "events-and-hooks": ["### user.created", "### user.registered"],
            "background-jobs": ["### Welcome email"],
            "integrations": ["### Email provider"],
            "configuration": ["### Registration", "### SIGNUP_"]
          }
        }
      ]
    }
  ]
}
```

The `section_hints` are grep patterns / section headers that tell each synthesis
teammate WHERE to look in each raw file. This prevents teammates from reading entire
raw files — they can jump to the relevant sections.

4. Assign hierarchical IDs:
   - Major features: `F-001`, `F-002`, ...
   - Sub-features: `F-001.01`, `F-001.02`, ...
   - (Behavior IDs are assigned by the synthesis teammates during decomposition)

5. Add any major features discovered in the raw files that the user didn't mention.
   Cross-reference raw file sections against the user's feature map. Anything unclaimed
   gets a new feature area or gets assigned to an existing one.

**Context budget for 4a:** This step should use minimal context. You're reading headers,
not content. The synthesis-plan.json is the handoff to teammates.

### 4b: Synthesize Detail Files via Agent Teams (Parallel)

This mirrors the Step 3 pattern: spawn teammates to do the heavy lifting in parallel.
Each teammate runs in one of two modes depending on whether prior output exists.

1. **Determine mode for each feature area:**
   - If `./feature-inventory-output/details/{feature_id}.md` does NOT exist:
     **mode = "create"** — build from scratch.
   - If `./feature-inventory-output/details/{feature_id}.md` EXISTS:
     **mode = "verify"** — audit existing files against raw data and patch gaps.

   **Never skip a feature area.** Even if files exist, they may be incomplete. The
   verify mode checks them against the raw outputs and fills in what's missing.

2. **Create tasks** via `TaskCreate` for each feature area (all of them).

3. **Spawn teammates in batches of up to 5.** Each teammate gets ONE major feature area.
   Assign each the `feature-inventory:feature-synthesizer` agent.

4. **Each teammate receives** via its task description:
   - **`mode`**: `"create"` or `"verify"` (determined in step 1)
   - The feature ID, name, and sub-feature list from synthesis-plan.json
   - The section_hints for each sub-feature (so they know where to look in raw files)
   - The raw output path and list of repos
   - The detail file output path (`./feature-inventory-output/details/`)
   - The product context (brief summary from interview)
   - A pointer to read `references/context-management.md` before starting
   - For **create mode**, this instruction verbatim: **"For each sub-feature, read from
     ONE raw dimension file at a time using the section hints to find the right
     location. Extract what you need, then move to the next dimension. After gathering
     from all dimensions, write the sub-feature detail file and all its behavior detail
     files. Write each file IMMEDIATELY — do not accumulate. Decompose to atomic
     behaviors: every validation rule, every error path, every side effect, every
     default value is its own behavior. If the raw data describes 12 distinct things
     in a flow, that's 12 behaviors, not 1."**
   - For **verify mode**, this instruction verbatim: **"Existing detail files were
     produced by a previous run and may be incomplete. For each sub-feature: read the
     existing detail file, then cross-check it against EVERY raw dimension file using
     the section hints. Find gaps: missing entities, missing endpoints, missing business
     rules, missing events, missing config, missing behaviors. Patch the gaps using
     Edit — don't rewrite files from scratch, surgically add what's missing. Create
     new behavior files for any behaviors found in the raw data that have no
     corresponding detail file. Every validation rule, error path, side effect, and
     default value should have its own behavior file."**

5. **Wait for each batch to finish** before spawning the next.

6. **After each batch:** Verify detail files exist for the completed feature areas.
   If a teammate failed or produced partial output, re-queue.

### 4c: Build the Index (Orchestrator — after all teammates finish)

Once all synthesis teammates have completed:

1. **Enumerate all detail files** produced in `./feature-inventory-output/details/`.
   Use `Glob` to find `F-*.md` files.

2. **Build the hierarchy from filenames and file headers.** Read only the first 5-10
   lines of each detail file (the `# {ID}: {Name}` header and `## Parent` link) to
   reconstruct the tree. Do NOT re-read full file contents.

3. **Write `FEATURE-INDEX.md`** — table of contents only:

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

4. **Build the dependency graph.** Grep all detail files for `## Dependencies` sections
   to extract the `Requires` and `Required by` relationships. Build the graph and
   suggested build order from these.

5. **Write `FEATURE-INDEX.json`** with the full structured hierarchy for programmatic
   consumption by agent orchestrators. Build this from the enumerated detail files and
   dependency graph — do NOT re-read full file contents.

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
- Step 3.5: Always re-run (fast — scripted audit).
- Step 4a: Re-run unless `synthesis-plan.json` exists and all raw files are present.
- Step 4b: Run in **verify** mode for feature areas with existing detail files,
  **create** mode for those without. Never skip.
- Step 4c: Always re-run to regenerate index from all available detail files.
