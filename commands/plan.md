---
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: >
  Transforms a completed feature inventory into fully decomposed, implementation-ready
  plans for every feature area. Interviews the user about rebuild strategy, researches
  the target tech stack, detects existing code, and produces section-level plans with
  TDD stubs that AI/agent teams can implement directly. REQUIRES Agent Teams enabled
  and a completed feature inventory. Run: /feature-inventory:plan [inventory-path]
---

# Plan Generation - Orchestrator

## PREREQUISITE: Agent Teams Required

**Before doing anything else**, verify that Agent Teams is available:

1. Run: `echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
2. If the value is NOT "1", **stop immediately** and tell the user:

   > **This command requires Claude Code Agent Teams.**
   >
   > To enable, add to `~/.claude/settings.json`:
   > ```json
   > {
   >   "env": {
   >     "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
   >   }
   > }
   > ```
   > Then restart Claude Code and run the command again.

   **Do not proceed. Do not fall back to sequential subagents.**

3. Also verify you have access to the `TeamCreate` tool.

---

You are the orchestrator for transforming a completed feature inventory into
implementation-ready plans. Your output is a set of fully decomposed plans that
AI/agent teams can pick up and start coding from immediately — each plan is a
self-contained blueprint that maps inventory specifications to the target architecture.

**Plans are prose documents, not code.** You describe what to build and how to
structure it. The implementer (human or AI agent) writes the actual code. Include
type definitions, function signatures, API contracts, and directory structures —
but no full function bodies.

## Important: Context Window Management

Plan generation reads from the feature inventory AND produces substantial output.
Manage context carefully:

1. **Never load the full inventory into context.** Use the FEATURE-INDEX.json for
   structure, read detail files one at a time.
2. **Delegate per-feature plan writing to teammates.** Each teammate gets one major
   feature area.
3. **All teammates write plan files to disk immediately.** They do NOT return large
   payloads in conversation.
4. **Resume capability:** Check for existing plan output files before spawning
   agents. Skip completed areas.

## Inputs

The command accepts one optional argument:

1. **Inventory path** (optional): Path to the `docs/features/` directory.
   Defaults to `./docs/features/`. If it doesn't exist, tell the user to
   run `/feature-inventory:create` first.

## Step 0: Validate Inventory

1. Verify `{inventory-path}/FEATURE-INDEX.json` exists. If not, stop and tell the
   user they need a completed feature inventory first:

   > **No feature inventory found.**
   >
   > Run `/feature-inventory:create` to analyze your codebase first.
   > The plan command transforms an inventory into implementation plans.

2. Read `FEATURE-INDEX.json` to get the full feature hierarchy.
3. Read `{inventory-path}/interview.md` for product context.
4. Verify detail files exist for the features listed. Warn if any are missing.
5. Count total features, sub-features, and behaviors.

Present a brief summary:

```
Feature Inventory Found
========================
Product: {name}
Features: {N} major, {N} sub-features, {N} behaviors
Source repos: {list}
Build order phases: {N}

Proceeding to strategic interview...
```

## Step 1: Strategic Interview

This interview is fundamentally different from the inventory interview. The inventory
interview captures WHAT the product does. This interview captures HOW and WHY you want
to rebuild it.

If `./docs/plans/interview.md` already exists, read it, summarize what you already know,
and ask only if there are gaps. Don't re-interview.

### Required Questions

Ask these using `AskUserQuestion`. Be conversational — adapt follow-up questions based
on answers. When something is surprising or reveals complexity, dig deeper.

#### 1. Rebuild Motivation

```
question: "Why are you rebuilding these features rather than maintaining/extending the existing system?"
header: "Motivation"
options:
  - label: "Tech debt / Legacy stack"
    description: "The current tech stack is outdated, hard to maintain, or can't support future needs"
  - label: "Architecture limitations"
    description: "The current architecture can't scale, perform, or adapt to new requirements"
  - label: "Team/hiring reasons"
    description: "Hard to find developers for the current stack, or the team wants to modernize skills"
  - label: "Product evolution"
    description: "The product needs to change so fundamentally that a rebuild is cheaper than incremental changes"
```

Follow up based on their answer to understand the specific pain points. These shape
architectural decisions.

#### 2. Target Tech Stack

```
question: "What tech stack do you want to build on?"
header: "Tech Stack"
options:
  - label: "I have a stack in mind"
    description: "I'll specify the languages, frameworks, and infrastructure I want to use"
  - label: "Research and suggest"
    description: "Analyze the feature inventory and recommend a stack based on what needs to be built"
  - label: "Keep similar, modernize"
    description: "Stay in the same ecosystem but use modern versions/frameworks"
```

If they have a stack in mind, ask for specifics:
- Primary language(s)
- Backend framework
- Frontend framework (if applicable)
- Database(s)
- Message queue / event system (if applicable)
- Hosting / infrastructure
- Testing framework preferences

Then ask about project tooling (these feed into section index `PROJECT_CONFIG` blocks
that implementation tools like `/workflows:work` and `/deep-implement` parse):
- Runtime environment (e.g., `node`, `python-uv`, `go`, `rust-cargo`, `bun`)
- Test command (e.g., `npm test`, `uv run pytest`, `go test ./...`)
- Build command (e.g., `npm run build`, `go build ./...`)
- Lint command (e.g., `npm run lint`, `ruff check .`)

If they don't know yet, leave these blank — they can be filled in when the project
is initialized.

If they want research, note this for Step 2.

#### 3. Rebuild Scope

```
question: "Is this a 1:1 feature rebuild, or are the inventoried features a minimum baseline?"
header: "Scope"
options:
  - label: "1:1 rebuild"
    description: "Recreate every feature exactly as documented in the inventory"
  - label: "Minimum baseline + additions"
    description: "The inventory is the floor — there are additional features needed beyond what exists today"
  - label: "Selective rebuild"
    description: "Only some features from the inventory will be rebuilt — others are being dropped or replaced"
```

If minimum baseline + additions: ask what additional features are needed and capture them.
If selective rebuild: ask which features to include/exclude.

#### 4. Architecture Changes

```
question: "How should the architecture change from the original?"
header: "Architecture"
options:
  - label: "Similar architecture, new stack"
    description: "Keep the same general structure (monolith, microservices, etc.) but in the new tech"
  - label: "Significant restructuring"
    description: "The architecture needs to change (e.g., monolith → microservices, or vice versa)"
  - label: "Let me describe"
    description: "I have specific architectural requirements to share"
```

Follow up to capture:
- Deployment model (containerized? serverless? traditional?)
- Service boundaries (if microservices)
- Data architecture (single DB? per-service? event sourcing?)
- API architecture (REST? GraphQL? gRPC? mix?)

#### 5. Existing Work

```
question: "Is there already a new codebase with some implementation started?"
header: "Existing Code"
options:
  - label: "Yes, partially built"
    description: "There's a new project with some features already implemented"
  - label: "Fresh start"
    description: "No new code exists yet — starting from scratch"
  - label: "Prototype exists"
    description: "There's a proof-of-concept or prototype that may inform the build"
```

If existing code: ask for the path. This triggers gap analysis integration in Step 3.

#### 6. Priorities and Constraints

Ask as open-ended follow-ups:
- "What features are most critical to launch with? What can come later?"
- "Are there hard deadlines, compliance requirements, or performance targets?"
- "Any integration points with other systems that constrain the architecture?"
- "Are there any features from the inventory that you know will be particularly
  challenging or that you have concerns about?"

### Save Interview

Write the interview transcript to `./docs/plans/interview.md` with full Q&A.
Write the strategic decisions to `./docs/plans/plan-config.json`:

```json
{
  "product_name": "from inventory",
  "inventory_path": "./docs/features",
  "rebuild_motivation": "summary of why",
  "target_stack": {
    "languages": ["typescript"],
    "backend_framework": "express",
    "frontend_framework": "react",
    "databases": ["postgresql"],
    "message_queue": "rabbitmq",
    "infrastructure": ["docker", "aws"],
    "testing": ["jest", "playwright"]
  },
  "project_tooling": {
    "runtime": "node",
    "test_command": "npm test",
    "build_command": "npm run build",
    "lint_command": "npm run lint"
  },
  "rebuild_scope": "1:1 | minimum_plus_additions | selective",
  "additional_features": ["list if scope is not 1:1"],
  "excluded_features": ["list if scope is selective"],
  "architecture": {
    "style": "monolith | microservices | modular_monolith | serverless",
    "deployment": "docker | kubernetes | serverless | traditional",
    "data_architecture": "single_db | per_service | event_sourcing",
    "api_style": "rest | graphql | grpc | mix"
  },
  "existing_code_path": null,
  "priorities": {
    "launch_critical": ["feature IDs"],
    "can_defer": ["feature IDs"],
    "constraints": ["list of hard constraints"]
  }
}
```

## Step 2: Create Agent Team & Execute Research

Create the Agent Team that will be used throughout the planning process. Then use
teammates for parallel research.

If `./docs/plans/research.md` already exists, skip the research but still create
the team (needed for Step 4).

### 2a: Create the Team

Use `TeamCreate` to create a team named "plan-generation". Enable delegate mode
(Shift+Tab) so you focus on coordination, not direct work.

This team is used for:
- Research (this step)
- Plan generation (Step 4)

### 2b: Launch Research Teammates (Parallel)

Spawn research teammates in a single batch. These run in parallel:

**Teammate 1 — Web Research** (always, unless user provided full stack details):
- Agent: use a generic research task
- Task: Research current best practices for the target tech stack
- Scope:
  - Best practices for the target framework/language combination
  - Recommended project structure patterns
  - Testing patterns and frameworks for the stack
  - Common pitfalls and performance considerations
  - If user asked for stack recommendations: research stacks that match the
    inventory's characteristics (API-heavy? UI-heavy? real-time? batch?)
- Output: Write findings to `./docs/plans/research-web.md`

**Teammate 2 — Existing Code Analysis** (only if user has a new codebase):
- Agent: use a codebase analysis task
- Task: Analyze the existing new project
- Scope:
  - Check if gap analysis exists at `./docs/gap-analysis/GAP-ANALYSIS.json`
    and read it if so
  - If no gap analysis: scan the new project structure, tech stack, which
    features appear to have implementation started, testing setup, architecture
    patterns in use
  - Determine per-feature implementation status (DONE, PARTIAL, NOT STARTED)
- Output: Write findings to `./docs/plans/research-codebase.md`

**Teammate 3 — Inventory Analysis** (always):
- Agent: use an analysis task
- Task: Analyze the feature inventory to characterize the build
- Scope:
  - Read FEATURE-INDEX.json for full feature hierarchy
  - Categorize features by type (API-heavy, UI-heavy, data-heavy, integration-heavy)
  - Identify dependency clusters and natural implementation phases
  - Identify cross-cutting concerns (error handling, auth, logging, caching, shared UI)
  - Calculate complexity estimates per feature area
- Output: Write findings to `./docs/plans/research-inventory.md`

Each teammate writes findings to disk immediately. Spawn all applicable teammates in
a single batch (up to 3 concurrent).

### 2c: Merge Research

After all research teammates complete, read their output files and merge into a single
`./docs/plans/research.md` with sections for:
- Target Stack Best Practices (from web research)
- Existing Code Status (from codebase analysis, if applicable)
- Inventory Characterization (from inventory analysis)
- Cross-Cutting Concerns Identified
- Recommended Implementation Approach

If the user asked for stack recommendations, present 2-3 options with trade-offs
and get user confirmation before proceeding. Update `plan-config.json` with the
chosen stack.

### 2d: Clean Up Research Intermediates

```bash
rm -f ./docs/plans/research-web.md
rm -f ./docs/plans/research-codebase.md
rm -f ./docs/plans/research-inventory.md
```

These were merged into `research.md` and are no longer needed.

## Step 3: Create Planning Strategy

Based on the interview, research, and inventory, create the planning approach.

### 3a: Determine Feature Scope

1. Read `FEATURE-INDEX.json` for the full feature list.
2. Apply scope decisions:
   - If **1:1 rebuild**: all features get plans.
   - If **selective**: only included features get plans.
   - If **minimum + additions**: all inventory features + plan stubs for additions.
3. If gap analysis exists, note status per feature (what's already built).

### 3b: Determine Build Order

Use the inventory's dependency graph and build order as a starting point, but adjust
based on:
- User's stated priorities (launch-critical features first)
- Architecture dependencies (infrastructure before features)
- Existing code (features that are partially built may need plans sooner)

### 3c: Identify Cross-Cutting Concerns

Scan the inventory for patterns that span multiple features:
- Error handling patterns
- Authentication/authorization infrastructure
- Logging and monitoring
- Caching patterns
- Shared UI components
- Common data access patterns

These become the "cross-cutting" plan that should be implemented before feature plans.

### 3d: Write Planning Strategy

Write `./docs/plans/planning-strategy.json`:

```json
{
  "features_in_scope": [
    {
      "id": "F-001",
      "name": "User Management",
      "sub_features": 8,
      "behaviors": 45,
      "phase": 2,
      "existing_status": "not_started | partial | done",
      "priority": "launch_critical | standard | deferred"
    }
  ],
  "cross_cutting_concerns": [
    "error-handling", "auth-infrastructure", "logging", "shared-ui"
  ],
  "implementation_phases": [
    {
      "phase": 1,
      "name": "Foundation & Infrastructure",
      "features": ["cross-cutting"],
      "rationale": "Shared patterns must exist before feature work"
    },
    {
      "phase": 2,
      "name": "Core Features",
      "features": ["F-001", "F-002"],
      "rationale": "Launch-critical features that other features depend on"
    }
  ],
  "total_features": 15,
  "total_plan_batches": 3
}
```

## Step 4: Generate Feature Plans via Agent Teams

Use the team created in Step 2. You (the lead) coordinate. Teammates write the
plans in parallel.

If the team was not created in Step 2 (because research was skipped via resume),
create it now using `TeamCreate` with the name "plan-generation" and delegate mode.

### 4b: Create Output Directories

```bash
mkdir -p ./docs/plans/features/cross-cutting/sections
```

For each feature in scope:
```bash
mkdir -p ./docs/plans/features/{feature_id}/sections
```

### 4c: Generate Cross-Cutting Plan First

Before feature plans, write the cross-cutting infrastructure plan. This can be
done by the orchestrator directly (it's typically smaller) or by a teammate.

If delegating, spawn a single teammate with the `feature-inventory:plan-writer` agent:
- Feature ID: "cross-cutting"
- Feature name: "Cross-Cutting Infrastructure"
- Sub-features: the cross-cutting concerns identified in Step 3
- Mode: "create" (or "update" if plan exists)

Wait for completion before spawning feature plan teammates.

### 4d: Spawn Feature Plan Teammates in Batches

For each feature in scope:

1. **Check for existing plan:** If `./docs/plans/features/{feature_id}/plan.md`
   exists and is non-empty, use **update** mode. Otherwise, use **create** mode.
2. **Create tasks** via `TaskCreate` for each pending feature.
3. **Spawn teammates in batches of up to 5.** Each teammate gets ONE major feature
   area. Assign them the `feature-inventory:plan-writer` agent.
4. **Each teammate receives** via its task description:
   - The feature ID, name, and sub-feature list from FEATURE-INDEX.json
   - The mode (create or update)
   - The inventory path
   - The output path (`./docs/plans/features/{feature_id}/`)
   - The plan-config.json path
   - The interview.md path
   - The research.md path (if it exists)
   - The gap analysis path (if it exists)
   - The product context (brief summary)
   - A pointer to read `references/context-management.md` before starting
   - A pointer to read `references/plan-output-format.md` for output structure
   - This instruction verbatim: **"Write a self-contained implementation plan
     that an engineer or AI agent with NO prior context can pick up and start
     building from. Map every inventory behavior to a plan section. Include
     architecture mapping, data model translation, API design, and TDD test
     stubs. Plans are prose — no full code implementations. Write files to disk
     immediately as you complete each one."**
5. **Wait for each batch to finish** before spawning the next.

Use Sonnet for teammates where possible to manage token costs. The lead (Opus)
handles coordination and the final index generation.

### 4e: Monitor and Validate

While teammates work:
1. Monitor progress via `TaskList`.
2. After each batch completes, verify plan files exist:
   - `plan.md` exists and is non-empty
   - `plan-tdd.md` exists
   - `sections/index.md` exists
   - At least 1 section file exists in `sections/`
3. If a teammate failed or produced partial output, re-queue.

### 4f: Handle Failures

If a teammate fails:
1. Check if partial plan files exist (teammate writes incrementally).
2. If `plan.md` exists but sections are missing: re-queue with "update" mode to
   complete the sections.
3. If nothing exists: re-queue with "create" mode.
4. After all batches, do a cleanup pass for any incomplete features.

## Step 5: Validate Plans

After all teammates complete:

### 5a: Behavior Coverage Check

For each feature plan, verify that the behaviors checklist covers every behavior
ID from the inventory. Use Grep to extract behavior IDs from each plan.md and
compare against FEATURE-INDEX.json.

If any behaviors are missing from plans, log them and either:
- Ask a teammate to update the plan, or
- Add them to the plan manually.

### 5b: Architecture Consistency Check

Scan across plans for potential inconsistencies:
- Do all plans reference the same tech stack from plan-config.json?
- Do cross-feature dependencies align? (e.g., if F-001 depends on F-003's
  auth service, does F-003's plan define that service?)
- Are shared data models consistent across feature plans?

Present any inconsistencies to the user for resolution.

### 5c: Section Count Check

Report total sections across all plans. If any feature has 0 sections or seems
disproportionately small/large relative to its behavior count, flag it.

## Step 6: Build Plan Index

### 6a: Write PLAN-INDEX.md

Read only the first 10-15 lines of each `plan.md` (the header with metadata) and
the `sections/index.md` files to build the master index. Do NOT re-read full plans.

Follow the template in `references/plan-output-format.md`.

### 6b: Write PLAN-INDEX.json

Build the machine-readable index from:
- `plan-config.json` for tech stack and strategy
- `planning-strategy.json` for phases and feature list
- Each feature's `sections/index.md` for section details
- FEATURE-INDEX.json for behavior counts

## Step 7: Present Summary

```
Plan Generation Complete
=========================

Product: {name}
Target stack: {language} + {framework} + {database}
Rebuild scope: {1:1 | minimum + additions | selective}

Feature plans: {N} generated
  - Cross-cutting: 1 plan, {N} sections
  - Feature-specific: {N} plans, {N} total sections
  - Behaviors covered: {N}/{total} ({%})

Implementation phases: {N}
  Phase 1 ({name}): {N} features, {N} sections
  Phase 2 ({name}): {N} features, {N} sections
  ...

{If existing code detected:}
Existing code status:
  - Done: {N} behaviors (plans adjusted)
  - Partial: {N} behaviors (plans include completion steps)
  - Not started: {N} behaviors (full plans generated)

Output:
  - Plan index: ./docs/plans/PLAN-INDEX.md
  - Machine-readable: ./docs/plans/PLAN-INDEX.json
  - Feature plans: ./docs/plans/features/
  - Planning config: ./docs/plans/plan-config.json

Next steps:
  1. Review PLAN-INDEX.md for implementation order
  2. Review individual feature plans in docs/plans/features/
  3. Start implementing from Phase 1 using section files
  4. Each section file is self-contained — pass it to:
     - /workflows:work (compound engineering) for task-based execution
     - /deep-implement for sequential TDD with code review
     - Any AI agent as a standalone blueprint
```

## Resume Behavior

On every run, **auto-clear derived artifacts** that are always regenerated:

```bash
rm -f ./docs/plans/planning-strategy.json
rm -f ./docs/plans/PLAN-INDEX.md
rm -f ./docs/plans/PLAN-INDEX.json
```

**Do NOT clear:**
- `interview.md` — user input
- `plan-config.json` — user decisions
- `research.md` — expensive research output
- `features/` — plans are updated incrementally, not rebuilt

Then apply these resume rules:
- Step 0: Always validate inventory (quick).
- Step 1: Skip if `interview.md` exists (load it for context).
- Step 2: Skip if `research.md` exists.
- Step 3: Always re-run (planning-strategy.json was cleared).
- Step 4: Run in **update** mode for features with existing plans, **create** mode
  for those without. Never skip.
- Step 5: Always re-run.
- Step 6: Always re-run (indexes were cleared).
