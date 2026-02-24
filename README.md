# feature-inventory

**v11.0.0**

A Claude Code plugin that reverse-engineers every feature, behavior, and capability across one or more codebases using **Agent Teams** for parallel analysis. Builds a code reference index, hunts for every indirect connection (events, IPC, pub/sub, reactive chains), constructs an outcome graph, and derives features from what the code ACHIEVES — not how it's structured. Features describe outcomes, freeing re-implementors to build optimally without replicating legacy architecture.

Also transforms the inventory into fully decomposed, implementation-ready plans for your target architecture and marketing-ready product catalogs for go-to-market teams.

New in v11: **architecture consolidation** — removed the old dimension-based pipeline and its 11 exclusive agents. The graph pipeline is now the only `create` command (renamed from `create-graph`). Phase orchestrators (build-index, build-graph, annotate-pathways, derive-features) are now self-contained agents spawnable via Task, eliminating the fragile thin-wrapper indirection that broke Task agent spawning. Fixed agent/command name collisions. Plugin reduced from 26 agents to 13.

New in v10: **connection hunting batching and large file handling** — create now drives connection hunting in a loop, spawning 2 parallel build-index tasks per iteration (each with 20 files) instead of one monolithic build-index that blew its context window on large codebases (339+ files). Batch size increased from 5→10 hunters per build-index instance. Connection hunters now chunk-read large files (500-line chunks for files >500 lines, with PARTIAL status support for files >1000 lines). An exhaustiveness mandate prevents agents from declaring early completion based on coverage percentages. build-index returns explicit status codes (INDEXING_COMPLETE, HUNTING_BATCH_DONE, ENRICHED_INDEX_COMPLETE) so the orchestrator can drive the loop with hard stop checkpoints between iterations.

New in v9: **agent messaging and delegation model** — connection hunters now report progress, completion, and pre-death reasons via `SendMessage` instead of the orchestrator polling output files in sleep loops. The orchestrator stays unblocked and processes agent status as messages arrive. Phase commands (build-index, build-graph, annotate-pathways, derive-features) are now explicitly spawned as foreground Task agents with their own context windows, establishing clean team hierarchies where hunters message their direct team lead. Also recalibrates the context watchdog (780KB→1130KB capacity, fixes percentage formula that divided by BLOCK threshold instead of total capacity).

New in v8: **hardened graph pipeline indexing contract** — Phase 1 is now explicitly two-step: (1) deterministic tree-sitter mechanical indexing and (2) per-file connection hunting. Tree-sitter is enforced as a fail-fast prerequisite (no manual/regex fallback for graph Phase 1), connection hunters are explicitly instructed to cover all 11 connection types for in/out matching on their assigned file, and the Phase 1→Phase 2 handoff is defined as a unified code-index edge layer in SQLite (`graph.db`).

New in v7: **graph-based feature discovery** — a fundamentally new bottom-up pipeline (`/feature-inventory:create`) that mechanically indexes every symbol in the codebase, relentlessly hunts for indirect connections (events, IPC, pub/sub, observables, DB triggers, middleware, DI, convention routing), constructs an outcome graph tracing entry points through pathways to final outcomes, annotates each pathway with 6 dimensions (data, auth, logic, UI, config, side effects), and derives features from outcomes. Uses SQLite (`graph.db`) for the index/graph — queryable, incrementally updatable, scales to 50k+ symbols. Includes Rust, Swift, and Objective-C extraction patterns. Also adds `/feature-inventory:reindex` for incremental updates after code changes — identifies affected files, re-indexes symbols, re-traces pathways, flags features, and generates user-facing change notes in feature terms.

New in v6: **batch-level hard stops** — the orchestrator now performs a mandatory hard stop after every 2 completed agent batches during long-running steps. This prevents the catastrophic "prompt is too long" crash that occurred when the orchestrator ran for hours monitoring 100+ agents without ever yielding control. The VS Code context percentage UI does not update during a long-running turn, so without hard stops the user has zero visibility into context health. After each hard stop, the user can `/compact` or `/clear` and re-run — the command resumes from the progress file at the exact next batch.

New in v5: **context window protection** — mandatory context checkpoints at every step boundary, automated context watchdog (PostToolUse/PreToolUse hooks that track tool call count and transcript size, inject escalating warnings, and hard-block agent-spawning tools at critical levels), orchestrator progress files for precise batch-level resume, tighter task sizing (~5 min target per teammate, max 1,500 lines per task), and teammate disk write frequency rules (every 5-10 items or 3 minutes, max 3 minutes of work lost on crash).

New in v4.2: **marketing catalog generation** — transforms the feature inventory into a go-to-market product catalog with marketing names, user-value descriptions, and cross-feature value propositions. Interviews users to capture positioning context, audience insights, and competitive landscape. Supports incremental updates — dates new entries and tracks changes to existing ones. Output stored in `docs/marketing/`.

New in v4.1: **compound engineering compatibility** — plan output now includes YAML frontmatter, `PROJECT_CONFIG` blocks, System-Wide Impact Analysis, and Monitoring & Observability sections. Plans work directly with `/workflows:work` (compound engineering), `/deep-implement`, or any AI agent. Also adds spec synthesis (interview + research + inventory merged into a unified brief), adaptive analysis with uncertainty mapping, gap-analysis skill integration for existing code detection, and foreign planning doc detection with automatic archiving.

New in v4: **plan generation command** that interviews you about rebuild strategy (motivation, tech stack, architecture, scope), researches the target stack, and produces per-feature implementation plans with TDD stubs and self-contained section files that AI/agent teams can implement directly. All output now organized under `docs/` (`docs/features/`, `docs/gap-analysis/`, `docs/plans/`).

New in v3: user resolution interview phase that eliminates ambiguous, thin, and overlapping features from the inventory through targeted user questions — ensuring every feature is either fully specified, explicitly related, or honestly marked as unresolved.

New in v2: gap analysis command, improved synthesis with verify-and-improve mode, parallelized feature synthesis via Agent Teams, source coverage auditing, and automatic clearing of derived artifacts on re-run.

## Requirements

- **Claude Code** (latest version)
- **Agent Teams enabled** (the plugin will refuse to run without it)
- **Claude Max subscription** recommended (Agent Teams is token-heavy)

### Enable Agent Teams

Add to `~/.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Or export in your shell: `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

## Installation

### From GitHub directly

```bash
claude plugin add github:alewcock/feature-inventory
```

### As a plugin marketplace (recommended for teams)

Create your own marketplace or add this repo directly:

```bash
/plugin marketplace add alewcock/feature-inventory
/plugin install feature-inventory@alewcock
```

### Local development

```bash
git clone https://github.com/alewcock/feature-inventory.git
claude --plugin-dir ./feature-inventory
```

### Updating

To get the latest version, re-run the install command:

```bash
claude plugin add github:alewcock/feature-inventory
```

This overwrites the existing installation with the latest release.

## Purpose

When migrating a legacy product (10-20+ years) to new languages and platforms, you need a specification complete enough that an AI/agent team could implement the full rebuild without ever seeing the original source code. This plugin produces that specification.

**Nothing is too small.** A tooltip, a default sort order, a 3-line validation rule, a retry delay, a password complexity requirement, an error message string - if the product exhibits the behavior, it gets documented.

## Graph Pipeline Phases

```
Phase 1: Discovery + Index
├── Repo discovery (languages, frameworks, modules, size)
├── Mechanical indexing (tree-sitter AST parsing → symbols, calls, imports)
│   └── Fast, deterministic, no LLM calls — produces SQLite index
└── Connection hunting (per-file agents, all 11 connection types)
    ├── Each agent gets ONE file, hunts unresolved connections in/out of it
    ├── Agents write connections as they find them, then terminate
    ├── Merge deduplicates (same connection found from both ends)
    └── Dynamic user interview when connections can't be resolved

Phase 2: Graph Construction
├── Identify entry points (routes, cron, CLI, UI handlers, consumers, webhooks)
├── Identify final outcomes (DB writes, responses, emails, external calls, UI state)
├── Trace paths: entry point → [logic] → final outcome(s)
├── Expand fan-outs (events, observables, IPC, triggers)
└── Validation
    ├── Orphan entry points → ALWAYS user interview
    ├── Unreachable outcomes → ALWAYS user interview
    └── Symbols with callers but no path → ALWAYS user interview

Phase 3: Pathway Annotation
├── For each pathway in the graph:
│   ├── Data: what is read/written/validated/transformed
│   ├── Auth: what authentication and authorization is required
│   ├── Logic: what rules, calculations, state transitions apply
│   ├── UI: what interface elements are involved
│   ├── Config: what env vars, flags, constants affect the path
│   └── Side Effects: what events/jobs/integrations are triggered
└── Every annotation includes source maps → index entries

Phase 4: Feature Derivation
├── Cluster related pathways into features (using user's mental model)
├── Name each feature by what users ACHIEVE, not how code is structured
├── Describe the outcome, not the mechanism
├── Link to related features → build hierarchy
└── User resolution interview for thin/overlapping/ambiguous specs

Phase 5: Index Maintenance
├── /feature-inventory:reindex — manual incremental update after code changes
│   ├── Diff changed files via git
│   ├── Re-index affected symbols, re-hunt connections
│   ├── Re-trace affected pathways, re-annotate
│   ├── Flag features whose behaviors changed
│   └── Generate user-facing change notes (feature terms, not code terms)
└── (FUTURE) CI/deploy hook for automated reindex on push
```

## Commands

| Command | Description |
|---------|-------------|
| `/feature-inventory:create [path]` | Run the graph-based inventory pipeline (bottom-up, outcome-focused) |
| `/feature-inventory:reindex [--since commit] [--diff branch]` | Incrementally update the graph inventory after code changes |
| `/feature-inventory:gap-analysis [new-project] [inventory-path]` | Compare a new project against the inventory |
| `/feature-inventory:plan [inventory-path]` | Generate implementation plans from a completed inventory |
| `/feature-inventory:marketing-catalog [inventory-path]` | Generate a marketing-ready product catalog for go-to-market teams |
| `/feature-inventory:status` | Check progress of inventory, gap analysis, plan generation, or marketing catalog |

## What It Produces

The plugin indexes the codebase mechanically and discovers features from outcomes:

| Layer | What It Produces |
|-------|-----------------|
| **Code Reference Index (Mechanical)** | Tree-sitter extracted symbols/calls/imports/exports plus connection hints, written to `graph.db` |
| **Indirect Connections (Hunting)** | Per-file agents resolve events, IPC, pub/sub, observables, DB triggers, middleware chains, DI bindings, convention routing, dispatch tables, webhooks, file watchers into the same `graph.db` code-index layer |
| **Outcome Graph** | Entry points (HTTP routes, CLI commands, cron jobs, UI events, message consumers, etc.) → pathways → final outcomes (data mutations, HTTP responses, emails, external API calls, etc.) |
| **Pathway Annotations** | 6 dimensions per pathway: data model, auth, business logic, UI, configuration, side effects — each with source maps back to the index |
| **Feature Hierarchy** | Features named by outcome (what users achieve), not implementation (how code is structured) |

Supports: JavaScript/TypeScript, C#/.NET, Python, Ruby, Java/Kotlin, Go, PHP, Rust, Swift, Objective-C, C/C++, SQL/MySQL.

## Usage

### Create a feature inventory

```
/feature-inventory:create [path-to-repo-or-parent-directory]
```

The plugin discovers features bottom-up from what the code does:
1. **Interview you** about the product (reuses existing `interview.md` if present)
2. **Discover** the repo structure and tech stack
3. **Build enriched index** (Phase 1 — delegated to `build-index`):
   - Tree-sitter indexes every symbol into SQLite
   - Per-file agents hunt indirect connections (events, IPC, pub/sub, DB triggers, etc.)
   - Interview you to resolve connections that couldn't be traced automatically
   - Enrich call graph with indirect edges
4. **Build outcome graph** (Phase 2 — delegated to `build-graph`):
   - Identify entry points and final outcomes
   - Trace pathways between them
   - Interview you about orphan routes, unreachable outcomes, graph gaps
5. **Annotate pathways** (Phase 3 — delegated to `annotate-pathways`):
   - Annotate each pathway with 6 dimensions (data, auth, logic, UI, config, side effects)
   - Extract exact values from source code at each step
6. **Derive features, build index & validate** (Phase 4 — delegated to `derive-features`):
   - Cluster pathways into feature areas
   - Derive features named by what users achieve, not how code is structured
   - Interview you for quality resolution
   - Validate every pathway claimed by exactly one feature

All structured data (index, connections, graph, annotations) lives in a single SQLite database (`docs/features/graph.db`).

### Incrementally update after code changes

```
/feature-inventory:reindex [--since <commit|tag>] [--diff <branch>]
```

After code changes, updates the graph inventory without regenerating from scratch. Identifies changed files via git diff, re-indexes affected symbols, re-hunts connections, re-traces pathways, and generates user-facing change notes describing what changed in feature terms (not code terms). Output written to `docs/features/change-notes/`.

Requires a completed graph-based inventory (`docs/features/graph.db`).

### Run a gap analysis

```
/feature-inventory:gap-analysis [new-project-path] [inventory-path]
```

Compares a new or in-progress project against a completed feature inventory. For every sub-feature and behavior in the inventory, determines whether it is **DONE**, **PARTIAL**, or **NOT STARTED** in the new project. Produces a structured task list (Markdown and JSON) ordered by the inventory's suggested build order.

Requires a completed feature inventory (`FEATURE-INDEX.json` must exist).

### Generate implementation plans

```
/feature-inventory:plan [inventory-path]
```

Transforms a completed feature inventory into implementation-ready plans for your target architecture. Conducts a strategic interview (rebuild motivation, tech stack, architecture, scope), researches the target stack, detects existing code, and produces per-feature plans decomposed into self-contained section files with TDD test stubs.

Requires a completed feature inventory (`FEATURE-INDEX.json` must exist). Optionally integrates with gap analysis results to account for existing implementations.

The plan generation uses Agent Teams at every stage:
- **Research phase**: Parallel teammates for web research, codebase analysis, and inventory characterization
- **Plan generation**: Parallel teammates writing feature plans (batches of 5)
- **Section writing**: Parallel teammates writing implementation sections within each feature

### Generate a marketing catalog

```
/feature-inventory:marketing-catalog [inventory-path]
```

Transforms a completed feature inventory into a marketing-ready product capabilities catalog designed for go-to-market teams. Interviews you about target audience, competitive positioning, messaging tone, and value themes, then produces catalog entries with marketing names, user-value descriptions, and cross-feature value propositions.

Requires a completed feature inventory (`FEATURE-INDEX.json` must exist).

The marketing catalog:
- **Interviews you** about positioning, audience, and competitive context
- **Scans for existing marketing materials** in `docs/marketing/` to maintain consistency
- **Translates technical features** into plain-language, value-focused descriptions
- **Identifies cross-feature value propositions** — combinations of features that create compelling product stories
- **Interviews you per feature** to capture persona, differentiator, and sales context
- **Tracks changes over time** — dates new entries, dates updates, maintains a changelog
- **Supports incremental updates** — on re-run, detects inventory changes and updates only affected entries

### Check progress

```
/feature-inventory:status
```

Shows plugin version, interview status, which dimensions are complete, coverage audit results, synthesis progress, gap analysis status, plan generation status, and marketing catalog status. Useful after a `/clear` or interruption to see where things stand before resuming.

### Resume after interruption

Just run `/feature-inventory:create` again. It detects completed work and picks up where it left off. All progress is persisted to disk — the SQLite database (`graph.db`), intermediate JSONL files, and `.progress.json` enable precise batch-level resume.

## Output Structure

### Feature Inventory

```
docs/features/
├── FEATURE-INDEX.md           # Master table of contents (names + links only)
├── FEATURE-INDEX.json         # Machine-readable with pathway/source map metadata
├── details/                   # One spec file per feature/behavior
│   ├── F-001.md              # Major feature overview
│   ├── F-001.01.md           # Sub-feature with pathway references
│   ├── F-001.01.01.md        # Behavior with source maps to index
│   └── ...
├── graph.db                   # SQLite database (index, connections, graph, annotations)
├── intermediate/              # JSONL teammate output (deletable after merge)
│   ├── index--*.jsonl        # Indexer output per scope
│   ├── connections--*.jsonl  # Connection hunter output
│   └── annotations--*.jsonl  # Annotator output per pathway group
├── change-notes/              # User-facing change notes from reindex runs
│   └── {date}-{hash}.md
├── interview.md               # User interview answers
├── user-feature-map.md        # User's mental model of features
├── clarifications.md          # Resolved ambiguities (connections + graph)
├── clarifications-features.md # Resolved ambiguities (feature specs)
└── discovery.json, plan.json
```

### Gap Analysis

```
docs/gap-analysis/
├── GAP-ANALYSIS.md            # Human-readable report with task list
├── GAP-ANALYSIS.json          # Machine-readable for agent orchestrators
├── new-project-discovery.json # New project scan results
├── plan.json                  # Analysis plan
└── raw/                       # Per-feature-area gap reports
    ├── F-001.md
    ├── F-002.md
    └── ...
```

### Implementation Plans

```
docs/plans/
├── PLAN-INDEX.md               # Master plan index with implementation order
├── PLAN-INDEX.json             # Machine-readable for agent orchestrators
├── interview.md                # Strategic rebuild interview
├── plan-config.json            # Tech stack, architecture, scope decisions
├── research.md                 # Target stack research + existing code analysis
├── synthesis.md                # Unified brief: interview + research + inventory
├── planning-strategy.json      # Feature scope, phases, cross-cutting concerns
└── features/                   # One plan directory per major feature
    ├── F-001/
    │   ├── plan.md             # Full implementation plan (prose, not code)
    │   ├── plan-tdd.md         # TDD test stubs mirroring plan structure
    │   └── sections/           # Self-contained implementation sections
    │       ├── index.md        # Section index with dependency graph
    │       ├── section-01-*.md # Each section: standalone blueprint for an implementer
    │       └── ...
    ├── cross-cutting/          # Shared infrastructure plan
    │   └── ...
    └── ...
```

### Marketing Catalog

```
docs/marketing/
├── MARKETING-CATALOG.md            # Master catalog for go-to-market teams
├── MARKETING-CATALOG.json          # Machine-readable for CMS/API/tooling
├── interview.md                    # Marketing context interview answers
├── catalog-config.json             # Audience, tone, positioning decisions
├── catalog-state.json              # Change tracking for incremental updates
└── entries/                        # One file per marketing entry
    ├── F-001.md                    # Feature area entry (marketing name + description)
    ├── F-001-composite.md          # Within-area composite value proposition
    ├── COMPOSITE-001.md            # Cross-product value proposition
    └── archived/                   # Entries for deprecated features
```

### The Index

`FEATURE-INDEX.md` is a **table of contents only** - hierarchical feature/behavior names, each linking to its detail file. Also includes a dependency graph and suggested build order for implementing agent teams.

### Detail Files (3 Tiers)

- **Major Feature (F-001.md):** Overview, sub-feature list, cross-cutting dependencies
- **Sub-Feature (F-001.01.md):** Full spec: data model, API contracts, UI, business rules, auth, config, events, test spec
- **Behavior (F-001.01.01.md):** Atomic implementable unit: precise behavior, input/output types, complete logic as pseudocode, every edge case, every error state, every default, test cases

## How Agent Teams Are Used

The orchestrator runs in **delegate mode** — coordination only, no direct analysis. Each pipeline phase is spawned as a Task agent with its own context window and team hierarchy:

- **Phase 1 (build-index):** Spawns indexing teammates (batches of 5) and connection hunters (batches of 10). Each hunter gets one file and reports findings via SendMessage.
- **Phase 2 (build-graph):** Spawns graph builder agent(s) to trace entry points → pathways → final outcomes.
- **Phase 3 (annotate-pathways):** Spawns pathway annotators (batches of 5) grouped by entry point.
- **Phase 4 (derive-features):** Spawns feature derivers (batches of 5) per cluster. Includes user resolution interview for thin/overlapping/ambiguous features.

Each phase creates its own team, becoming the team lead. Teammates communicate via SendMessage to their team lead — messages don't propagate to the top-level orchestrator. This keeps context windows clean and team hierarchies simple.

### Plan Generation

Plan generation uses Agent Teams at three levels:

1. **Research Team**: Parallel teammates for web research, gap analysis (via `/feature-inventory:gap-analysis`), and inventory characterization (up to 3 concurrent)
2. **Plan Writers**: Parallel teammates producing feature plans (batches of 5). Each plan-writer maps inventory behaviors to the target architecture, decomposes into implementation sections, and writes TDD test stubs.
3. **Section Writers**: Within each plan-writer, parallel teammates writing individual section files (batches of 5). Each section is self-contained — an implementer reads only that file and can start building.

The orchestrator conducts an adaptive strategic interview first (motivation, tech stack, architecture, scope) with uncertainty mapping, then delegates the heavy lifting to teammates. After plans are generated, an optional **external LLM review** step sends plans to Gemini and/or OpenAI for independent critique — catching blind spots that self-review misses.

Plan output is designed to work with multiple implementation tools:
- **`/workflows:work`** (compound engineering) — task-based execution with multi-agent review
- **`/deep-implement`** — sequential TDD with code review gates
- **Any AI agent** — each section file is a standalone blueprint

## Agents

### Pipeline Agents

| Agent | Purpose |
|-------|---------|
| `code-indexer` | Uses tree-sitter to mechanically index every symbol: functions, classes, methods, routes, constants, types, variables, imports. Deterministic AST parsing — no LLM calls for basic extraction. LLM reviews only connection hints (dynamic dispatch, framework magic, reflection). Tree-sitter is required for Graph Pipeline Phase 1; indexing fails fast if unavailable |
| `connection-hunter` | Gets ONE file, hunts ALL 11 types of indirect connections in/out of it: events, IPC, pub/sub, observables, DB triggers, middleware, DI, convention routing, dispatch tables, webhooks, file watchers. Documents each connection immediately, then terminates. Connections discovered from both ends and deduplicated at merge |
| `graph-builder` | Constructs outcome graph: identifies entry points and final outcomes, traces pathways through the enriched call graph, detects fan-out points, classifies infrastructure, validates coverage |
| `pathway-dimension-annotator` | Annotates each pathway with 6 dimensions (data, auth, logic, UI, config, side effects). Every annotation includes source maps back to the code reference index |
| `feature-deriver` | Clusters annotated pathways into features named by outcome. Builds hierarchy (major → sub-feature → behavior) with links, source maps, and test cases |

### Shared Agents

| Agent | Purpose |
|-------|---------|
| `gap-analyzer` | Compares new project against inventory for one feature area |
| `plan-writer` | Produces implementation plans for one feature area (create/update modes) |
| `plan-section-writer` | Writes self-contained implementation section files in parallel |
| `marketing-catalog-writer` | Translates feature areas into marketing-ready catalog entries with user interviews |

## Token Usage

Agent Teams is token-intensive. Each teammate is a full Claude Code session.

### Feature Inventory (create)

For a medium-sized product (3 repos, ~50,000 lines):
- Interview: ~10k tokens (skipped if `interview.md` exists)
- Discovery + Planning: ~20k tokens
- Code indexing (parallel teammates): ~300k tokens across teammates
- SQLite merge + cross-referencing: ~30k tokens
- Connection hunting (parallel teammates): ~200k tokens across teammates
- User interview for unresolved connections: ~20-50k tokens
- Graph building: ~100k tokens
- User interview for orphans/unreachables: ~20-50k tokens
- Pathway annotation (parallel teammates): ~400k tokens across teammates
- Feature derivation (parallel teammates): ~200k tokens across teammates
- Validation + index: ~50k tokens

Subtotal: ~1.3M-1.5M tokens.

Subsequent `reindex` runs are much cheaper — typically 50k-200k tokens depending on change scope.

### Plan Generation (plan)

For a medium-sized inventory (15 major features, ~400 behaviors):
- Strategic interview: ~10k tokens
- Research (parallel teammates): ~100k tokens across teammates
- Plan generation (15 features x ~80k each): ~1.2M tokens across teammates
- Section writing (parallel within features): ~300k tokens across teammates
- Validation + index: ~50k tokens

Subtotal: ~1.6M-1.8M tokens.

### Marketing Catalog (marketing-catalog)

For a medium-sized inventory (15 major features):
- Marketing interview: ~15k tokens
- Existing materials scan: ~10k tokens
- Catalog generation (15 features x ~40k each): ~600k tokens across teammates
- Cross-product value proposition analysis: ~30k tokens
- User interviews per feature: ~50k tokens (depends on depth)
- Index + assembly: ~30k tokens

Subtotal: ~700k-800k tokens.

**Claude Max subscription strongly recommended.** The combined workflow (create + gap-analysis + plan + marketing-catalog) can exceed 4M tokens for medium products.
