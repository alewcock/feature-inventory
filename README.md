# feature-inventory

A Claude Code plugin that reverse-engineers every feature, behavior, and capability across one or more codebases using **Agent Teams** for parallel analysis. Produces a deeply decomposed, hierarchically structured specification designed for AI/agent teams to rebuild the entire product from scratch.

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

### As a plugin marketplace (recommended for teams)

Create your own marketplace or add this repo directly:

```bash
/plugin marketplace add alewcock/feature-inventory
/plugin install feature-inventory@alewcock
```

### From GitHub directly

```bash
claude plugin add github:alewcock/feature-inventory
```

### Local development

```bash
git clone https://github.com/alewcock/feature-inventory.git
claude --plugin-dir ./feature-inventory
```

## Purpose

When migrating a legacy product (10-20+ years) to new languages and platforms, you need a specification complete enough that an AI/agent team could implement the full rebuild without ever seeing the original source code. This plugin produces that specification.

It interviews the user to capture tribal knowledge, then systematically analyzes the codebase across 9 dimensions in parallel using Agent Teams, and produces a hierarchical feature index where every entry links to a detailed specification file.

**Nothing is too small.** A tooltip, a default sort order, a 3-line validation rule, a retry delay, a password complexity requirement, an error message string - if the product exhibits the behavior, it gets documented.

## What It Analyzes (9 Dimensions)

| Dimension | What It Captures |
|-----------|-----------------|
| **API Surface** | Every endpoint with full request/response schemas, auth, errors, pagination |
| **Data Models** | Every entity, field, type, constraint, relationship, index, enum |
| **UI Screens** | Every page, form field, table column, button, modal, validation message, empty state |
| **Business Logic** | Every rule, calculation, workflow, state machine, edge case, magic number |
| **Integrations** | Every third-party service, SDK operation, webhook, retry policy |
| **Background Jobs** | Every scheduled task, queue worker, retry config, dead letter policy |
| **Auth & Permissions** | Every role, permission, enforcement point, session config, password policy |
| **Configuration** | Every env var, config file key, feature flag, user-configurable setting |
| **Events & Hooks** | Every event with payload schema, every subscriber, every middleware |

## Usage

### Run the full inventory

```
/feature-inventory [path-to-repo-or-parent-directory]
```

The plugin will:
1. **Check** that Agent Teams is enabled (fails immediately if not)
2. **Interview you** about the product (captures tribal knowledge not in code)
3. **Discover** the repo structure and tech stack
4. **Analyze** all 9 dimensions in parallel via Agent Teams (batches of 5 teammates)
5. **Ask clarifying questions** when teammates encounter ambiguity
6. **Build the feature hierarchy** organized by your mental model
7. **Generate detail files** for every feature and behavior
8. **Validate** against your original feature map

### Check progress

```
/inventory-status
```

Shows which dimensions are complete, partial, pending, or failed.

### Resume after interruption

Just run `/feature-inventory` again. It detects completed work and picks up where it left off. All progress is persisted to disk.

## Output Structure

```
feature-inventory-output/
├── FEATURE-INDEX.md           # Master table of contents (names + links only)
├── FEATURE-INDEX.json         # Machine-readable for agent orchestrators
├── details/                   # One spec file per feature/behavior
│   ├── F-001.md              # Major feature overview
│   ├── F-001.01.md           # Sub-feature: full spec with data/API/UI/rules
│   ├── F-001.01.01.md        # Behavior: atomic implementable spec
│   └── ...
├── interview.md               # User interview answers
├── user-feature-map.md        # User's mental model of features
├── clarifications.md          # Resolved ambiguities
├── raw/                       # Per-dimension analysis (intermediate)
│   └── {repo-name}/
│       ├── api-surface.md
│       ├── data-models.md
│       └── ...
└── discovery.json, plan.json
```

### The Index

`FEATURE-INDEX.md` is a **table of contents only** - hierarchical feature/behavior names, each linking to its detail file. Also includes a dependency graph and suggested build order for implementing agent teams.

### Detail Files (3 Tiers)

- **Major Feature (F-001.md):** Overview, sub-feature list, cross-cutting dependencies
- **Sub-Feature (F-001.01.md):** Full spec: data model, API contracts, UI, business rules, auth, config, events, test spec
- **Behavior (F-001.01.01.md):** Atomic implementable unit: precise behavior, input/output types, complete logic as pseudocode, every edge case, every error state, every default, test cases

## How Agent Teams Are Used

The orchestrator (lead) runs in **delegate mode** - coordination only, no direct analysis.

Teammates are spawned in batches of 5, each assigned one dimension of one repo. They:
- Read `references/context-management.md` for context window discipline
- Use grep/glob for discovery, targeted reads only
- Write findings to disk incrementally (never accumulate in context)
- Flag ambiguities with `[AMBIGUOUS]` tags
- Communicate via the shared task list and messaging

This means:
- 9 dimensions can be analyzed in ~2 batches instead of sequentially
- Each teammate has a fresh context window (no accumulated bloat)
- Failures are isolated (one dimension failing doesn't affect others)
- Partial progress is always preserved on disk

## Customization

### Adding a new dimension

1. Create a new agent in `agents/{dimension-name}.md`
2. Update the orchestrator's Step 2 (plan) to include the new dimension
3. Update `references/output-format.md` with the new dimension abbreviation

### Adjusting scope

After Step 2, edit `./feature-inventory-output/plan.json` to remove dimensions or adjust directory scopes before continuing.

## Token Usage

Agent Teams is token-intensive. Each teammate is a full Claude Code session. For a medium-sized product (3 repos, all 9 dimensions), expect roughly:
- Interview: ~10k tokens
- Discovery + Planning: ~20k tokens
- Analysis (9 dimensions x ~50k each): ~450k tokens across teammates
- Index + Detail generation: ~100k tokens

Total: ~500k-600k tokens. Claude Max subscription recommended.
