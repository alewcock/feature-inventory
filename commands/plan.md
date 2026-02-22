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

**A "prompt is too long" error is CATASTROPHIC.** It kills the orchestrator session,
orphans any running teammates, and loses all context accumulated during the run. This
workflow spans many steps and can run for hours — the orchestrator MUST proactively
manage its context to prevent this.

### Core Rules

1. **Never load the full inventory into context.** Use the FEATURE-INDEX.json for
   structure, read detail files one at a time.
2. **Delegate per-feature plan writing to teammates.** Each teammate gets one major
   feature area.
3. **All teammates write plan files to disk immediately.** They do NOT return large
   payloads in conversation.
4. **Resume capability:** Check for existing plan output files before spawning
   agents. Skip completed areas.

### Mandatory Context Checkpoints

**This workflow has mandatory context checkpoints at every step boundary.** At each
checkpoint, the orchestrator MUST evaluate its context health and clear if needed.
See `references/context-management.md` § "Context Checkpoint Protocol" for the full
protocol.

Checkpoints are marked with `### Context Checkpoint` headers throughout this document.
**Do not skip them.** Each checkpoint is a safe resume point — all prior state is on
disk and the next step can start from those files.

**The orchestrator should expect to `/clear` at least 1-2 times during a full
plan generation run.** This is normal and by design.

## Inputs

The command accepts one optional argument:

1. **Inventory path** (optional): Path to the `docs/features/` directory.
   Defaults to `./docs/features/`. If it doesn't exist, tell the user to
   run `/feature-inventory:create` first.

## Step 0: Validate Inventory & Detect Existing Plans

### 0a: Validate Inventory

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

### 0b: Detect Existing Plan Docs

Check if `./docs/plans/` already exists. If it does, determine provenance —
were these docs produced by this plugin, or by something else?

**Check for our fingerprint:** Look for `plan-config.json` with our schema
(has `rebuild_scope`, `target_stack`, `project_tooling` keys). Also check
for `synthesis.md` or `planning-strategy.json`.

- **Our docs found** (at least `plan-config.json` with our schema):
  This is a resume. Report what exists and proceed with incremental updates:

  ```
  Existing plan docs found (from previous run)
  =============================================
  Interview: {exists / missing}
  Config: {exists / missing}
  Research: {exists / missing}
  Synthesis: {exists / missing}
  Feature plans: {N} found

  Resuming from where we left off...
  ```

- **Foreign docs found** (`docs/plans/` exists but no `plan-config.json` with
  our schema, or the schema doesn't match):
  These were created by another tool, manually, or by an older version.

  **Review then archive:** Read any `.md` and `.json` files in `docs/plans/` for context on
  the existing codebase — architectural decisions, tech stack choices, domain
  knowledge, and prior planning work are all valuable input. Then move the
  foreign docs to an archive folder so our plan output has a clean directory:

  ```bash
  mkdir -p ./docs/plans-archive-$(date +%Y%m%d-%H%M%S)
  mv ./docs/plans/* ./docs/plans-archive-*/
  ```

  Tell the user what was found and where it was archived:

  ```
  Foreign planning docs found in docs/plans/
  ===========================================
  Files: {list of .md and .json files found}
  Archived to: docs/plans-archive-{timestamp}/

  These docs will be reviewed for context on existing code and
  architectural decisions, then incorporated into synthesis.md.
  ```

  Include relevant context from the foreign docs in `synthesis.md` under an
  "External Planning Context" section during Step 2e.

  If **abort**: Stop immediately.

### 0c: Present Summary

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

### Interview Protocol

**Adaptive, not prescriptive.** The questions below are starting points, not a fixed
script. Follow the user's natural way of describing the rebuild. Stop asking when you
have enough to make informed planning decisions — don't force all categories if the
answers are already clear.

**Uncertainty mapping.** Pay attention to hesitation, qualifiers ("maybe", "probably",
"I'm not sure"), and vague areas. Flag these explicitly in the interview transcript
with `[UNCERTAIN]` tags. Uncertain areas get extra attention during research (Step 2)
and plan validation (Step 5).

Ask using `AskUserQuestion`. Be conversational — adapt follow-up questions based
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

### Context Checkpoint: After Strategic Interview

**MANDATORY.** Follow the Context Checkpoint Protocol in `references/context-management.md`.

All interview state is on disk (`interview.md`, `plan-config.json`). If the interview
was lengthy, evaluate context and clear if needed — Step 2 resumes from `research.md`
detection.

Preserved files: `interview.md`, `plan-config.json`

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

**Teammate 2 — Gap Analysis** (only if user has a new codebase):

First check if gap analysis already exists at `./docs/gap-analysis/GAP-ANALYSIS.json`.

- **If gap analysis exists:** Skip this teammate. The structured per-feature reports
  in `docs/gap-analysis/raw/` will be used directly by plan-writers.
- **If no gap analysis exists:** Run the gap analysis skill before proceeding.
  Tell the user:

  > **Existing code detected but no gap analysis found.**
  >
  > Running `/feature-inventory:gap-analysis {existing_code_path} {inventory_path}`
  > to determine per-feature implementation status before generating plans.
  > This ensures plans account for what's already built.

  Wait for gap analysis to complete. It produces structured output that plan-writers
  consume: `GAP-ANALYSIS.json` with per-feature DONE/PARTIAL/NOT_STARTED status,
  and `raw/{feature_id}.md` with detailed per-behavior analysis.

  Do NOT spawn an ad-hoc codebase analysis teammate — the gap-analysis skill
  is specifically designed for this comparison and produces better structured output.

After gap analysis completes (or was already present), spawn a teammate to summarize:
- Agent: use an analysis task
- Task: Read `GAP-ANALYSIS.json` and summarize implementation status
- Output: Write summary to `./docs/plans/research-codebase.md`

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

### 2e: Synthesize Planning Brief

Before planning individual features, synthesize the three input sources into a single
unified brief that plan-writers will use as their primary reference. This avoids each
plan-writer independently re-reading and reconciling the same three documents.

If `./docs/plans/synthesis.md` already exists, skip this step.

Combine:
1. **Interview decisions** (`interview.md`): Why rebuilding, tech stack, scope, architecture,
   priorities, constraints, `[UNCERTAIN]` areas
2. **Research findings** (`research.md`): Stack best practices, existing code status,
   inventory characterization, cross-cutting concerns
3. **Inventory overview** (`FEATURE-INDEX.json`): Feature hierarchy, dependency graph,
   build order, behavior counts

Into `./docs/plans/synthesis.md`:

```markdown
# Planning Brief

## Product Summary
{What this product does, from inventory interview}

## Rebuild Strategy
{Synthesized from interview: motivation, scope, architecture changes}

## Target Architecture
{Synthesized from interview + research: stack choices, patterns, project structure}

## Inventory Overview
{Feature count, behavior count, dependency clusters, complexity distribution}

## Cross-Cutting Concerns
{Merged from research + inventory: shared patterns that span features}

## Uncertain Areas
{Aggregated [UNCERTAIN] flags from interview + ambiguities from inventory.
Each area gets a note on how research addressed it, or "still uncertain —
plan-writer should flag for implementer."}

## Existing Code Status
{From research/gap analysis: what's built, what's partial, what's missing}

## Constraints & Priorities
{From interview: launch-critical features, hard deadlines, compliance,
performance targets}
```

This is the single document that captures ALL strategic context. Plan-writers
read `synthesis.md` + `plan-config.json` instead of separately reading interview,
research, and inventory overview files. This reduces context usage per teammate
and ensures consistent interpretation across all feature plans.

### Context Checkpoint: After Research & Synthesis

**MANDATORY.** Follow the Context Checkpoint Protocol in `references/context-management.md`.

Research involved monitoring teammates and merging their outputs. Synthesis involved
reading and reconciling multiple documents. All results are on disk (`research.md`,
`synthesis.md`). Evaluate context and clear if needed.

Preserved files: `interview.md`, `plan-config.json`, `research.md`, `synthesis.md`

## Step 3: Create Planning Strategy

Based on the synthesis, research, and inventory, create the planning approach.

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

### Context Checkpoint: Before Plan Generation

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Follow the Context Checkpoint Protocol
in `references/context-management.md`.

Steps 1-3 have accumulated interview interactions, research monitoring, document reads,
and strategy generation. Step 4 (plan generation) is the most context-intensive phase —
it monitors multiple batches of plan-writer teammates. **Clear here** to enter Step 4
with maximum headroom.

Preserved files: `interview.md`, `plan-config.json`, `research.md`, `synthesis.md`,
`planning-strategy.json`

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
   - The synthesis.md path (unified planning brief — primary context)
   - The interview.md path (for feature-specific grep if needed)
   - The research.md path (if it exists)
   - The gap analysis path (if it exists)
   - The product context (brief summary)
   - A pointer to read `references/context-management.md` before starting
   - A pointer to read `references/plan-output-format.md` for output structure
   - This instruction verbatim: **"Read synthesis.md first for strategic context,
     then read the inventory detail files for this feature. Write a self-contained
     implementation plan that an engineer or AI agent with NO prior context can
     pick up and start building from. Map every inventory behavior to a plan
     section. Include architecture mapping, data model translation, API design,
     TDD test stubs, system-wide impact analysis, and monitoring guidance. Plans
     are prose — no full code implementations. Flag any [UNCERTAIN] areas from
     synthesis.md that affect this feature. Write files to disk immediately as
     you complete each one."**
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

### Context Checkpoint: After Plan Generation

**MANDATORY — CLEAR STRONGLY RECOMMENDED.** Follow the Context Checkpoint Protocol
in `references/context-management.md`.

Step 4 involved monitoring multiple batches of plan-writer teammates, validating outputs,
and handling failures. This is the heaviest context consumer in the plan workflow.
**Clear here** before validation.

Preserved files: `interview.md`, `plan-config.json`, `research.md`, `synthesis.md`,
`planning-strategy.json`, `features/*/plan.md`, `features/*/plan-tdd.md`,
`features/*/sections/*`

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

### Context Checkpoint: After Validation

**MANDATORY.** Follow the Context Checkpoint Protocol in `references/context-management.md`.

Validation involved scanning plans for coverage, consistency, and section counts.
If inconsistencies were found and resolved, additional context was consumed. Evaluate
and clear if needed — Step 6 and beyond can resume from plan files on disk.

Preserved files: All plan files, `planning-strategy.json`, config files

## Step 6: External Review (Optional)

If the user has external LLM API keys configured, offer independent plan review
using a different model family. This catches blind spots that self-review misses —
a different model finds different issues.

### 6a: Check Availability

Check for API keys in environment variables:
- `GEMINI_API_KEY` or `GOOGLE_APPLICATION_CREDENTIALS` (for Gemini)
- `OPENAI_API_KEY` (for OpenAI)

If neither is available, skip this step entirely. If available, ask the user:

```
question: "Run external LLM review on the generated plans?"
header: "Review"
options:
  - label: "Yes, review plans"
    description: "Send plans to {available models} for independent critique (catches blind spots)"
  - label: "Skip review"
    description: "Proceed directly to index generation"
```

### 6b: Run Reviews

For each feature plan where review is requested:

1. Read the feature's `plan.md` (it's self-contained — no other files needed).
2. Send it to available external models with this prompt:

   > You are a senior software architect reviewing an implementation plan for
   > a legacy product rebuild. Identify: potential footguns and edge cases,
   > missing considerations, security vulnerabilities, performance issues,
   > architectural problems, unclear or ambiguous requirements, and gaps
   > between the plan's stated coverage and what would actually be needed
   > to implement this feature.

3. Write each review to `./docs/plans/features/{feature_id}/reviews/`:
   - `review-gemini.md` (if Gemini available)
   - `review-openai.md` (if OpenAI available)

If you have access to `Bash`, use it to call the external APIs:
```bash
# Example for OpenAI
curl -s https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]}'
```

For large plans, send only the plan.md (not sections) — it contains the full
architecture, section decomposition, and behaviors checklist.

### 6c: Incorporate Findings

Read the review files. For each finding:
- **Critical issues** (security, correctness, missing functionality): Update the
  affected plan.md and section files immediately.
- **Improvements** (performance, architecture suggestions): Note in the plan's
  Migration Notes section for the implementer to consider.
- **Style/preference**: Ignore — different models have different opinions.

Present a summary of changes made:
```
External Review Summary
========================
Reviews: {N} plans reviewed by {model names}
Critical findings: {N} (all addressed)
Improvements noted: {N} (added to Migration Notes)
Style suggestions: {N} (skipped)
```

### Context Checkpoint: After External Review

**MANDATORY.** Follow the Context Checkpoint Protocol in `references/context-management.md`.

If external review was run, it involved reading plans, making API calls, processing
responses, and applying fixes. If skipped, this checkpoint is still evaluated (it may
inherit context load from prior steps). Evaluate and clear if needed.

Preserved files: All plan files, review files (if generated), config files

## Step 7: Build Plan Index

### 7a: Write PLAN-INDEX.md

Read only the first 10-15 lines of each `plan.md` (the header with metadata) and
the `sections/index.md` files to build the master index. Do NOT re-read full plans.

Follow the template in `references/plan-output-format.md`.

### 7b: Write PLAN-INDEX.json

Build the machine-readable index from:
- `plan-config.json` for tech stack and strategy
- `planning-strategy.json` for phases and feature list
- Each feature's `sections/index.md` for section details
- FEATURE-INDEX.json for behavior counts

## Step 8: Present Summary

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

{If external review was run:}
External review:
  - Models used: {Gemini, OpenAI, ...}
  - Critical findings addressed: {N}
  - Improvements noted: {N}

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
- `synthesis.md` — expensive synthesis output
- `features/` — plans are updated incrementally, not rebuilt

Then apply these resume rules:
- Step 0: Always validate inventory (quick).
- Step 1: Skip if `interview.md` exists (load it for context).
- Step 2: Skip if `research.md` exists. Skip synthesis (2e) if `synthesis.md` exists.
- Step 3: Always re-run (planning-strategy.json was cleared).
- Context check: Always present (quick).
- Step 4: Run in **update** mode for features with existing plans, **create** mode
  for those without. Never skip.
- Step 5: Always re-run.
- Step 6: Skip if `reviews/` directories exist for all features. Re-run if new plans
  were generated or updated in Step 4.
- Step 7: Always re-run (indexes were cleared).
- Step 8: Always present.
