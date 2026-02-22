---
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Agent, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: >
  Transforms a completed feature inventory into a marketing-ready catalog of user
  features with marketing names, value descriptions, and cross-feature value
  propositions. Designed for go-to-market teams. Interviews the user to capture
  positioning context, audience insights, and competitive landscape. Supports
  incremental updates — dates new entries and tracks changes to existing ones.
  REQUIRES Agent Teams enabled and a completed feature inventory.
  Run: /feature-inventory:marketing-catalog [inventory-path]
---

# Marketing Catalog - Orchestrator

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

You are the orchestrator for transforming a completed feature inventory into a
marketing-ready product catalog. Your output is a living document designed to be
handed directly to a go-to-market team — product marketing, sales engineering,
content, and demand generation.

**The audience is non-technical.** Every description must be written in plain language
that focuses on user value, not system internals. A marketing manager, sales rep, or
content writer should be able to read any entry and immediately understand what the
product does and why it matters to users.

**This is a living document.** It tracks when entries were created and updated, detects
changes in the underlying feature inventory, and supports incremental refresh runs.
The goal is that whenever the product changes, the marketing catalog stays current.

## Important: Context Window Management

Marketing catalog generation reads from the feature inventory AND conducts user
interviews. Manage context carefully:

1. **Load the feature index (JSON), not all detail files at once.** Use the index to
   understand scope, then read detail files only when processing specific features.
2. **Delegate per-feature-area catalog writing to teammates.** Each teammate gets one
   major feature area.
3. **All teammates write catalog entries to disk immediately.** They do NOT return large
   payloads in conversation.
4. **Resume capability:** Check for existing marketing output files before spawning
   agents. Skip completed areas on create; use update mode for changed areas.

## Inputs

The command accepts one optional argument:

1. **Inventory path** (optional): Path to the `docs/features/` directory.
   Defaults to `./docs/features/`. If it doesn't exist, tell the user to
   run `/feature-inventory:create` first.

## Step 0: Validate Inventory & Detect Existing Catalog

### 0a: Validate Inventory

1. Verify `{inventory-path}/FEATURE-INDEX.json` exists. If not, stop and tell the user:

   > **No feature inventory found.**
   >
   > Run `/feature-inventory:create` to analyze your codebase first.
   > The marketing catalog transforms an inventory into go-to-market documentation.

2. Read `FEATURE-INDEX.json` to get the full feature hierarchy.
3. Read `{inventory-path}/interview.md` for product context.
4. Count total features, sub-features, and behaviors.

### 0b: Scan for Existing Marketing Artifacts

Check `./docs/marketing/` for any existing content:

1. **Check for our catalog:** Look for `catalog-state.json` with our schema (has
   `last_run_date`, `feature_checksums`, `entries` keys).

   - **Our catalog found**: This is a resume/update run. Report what exists:
     ```
     Existing marketing catalog found (from previous run)
     ====================================================
     Last run: {date}
     Entries: {N} features cataloged
     Composites: {N} value propositions

     Checking for inventory changes since last run...
     ```

   - **No catalog but other marketing docs found**: Read any `.md`, `.pdf`, `.docx`
     files in `docs/marketing/` for context. These are existing marketing materials
     that should inform the catalog's tone, terminology, and positioning.

     ```
     Existing marketing materials found in docs/marketing/
     =====================================================
     Files: {list of files found}

     These will be reviewed for tone, terminology, and positioning context.
     ```

   - **Empty or missing**: Fresh run.

2. **If existing materials found**, read them and extract:
   - Product positioning and messaging themes
   - Target audience descriptions
   - Terminology and naming conventions
   - Competitive positioning language
   - Any existing feature descriptions that should be preserved or evolved

   Save findings to `./docs/marketing/existing-materials-summary.md`.

### 0c: Present Summary

```
Feature Inventory Found
========================
Product: {name}
Features: {N} major, {N} sub-features, {N} behaviors
{If existing catalog:} Previous catalog: {N} entries, last updated {date}
{If existing materials:} Existing marketing materials: {N} files reviewed

Proceeding to marketing interview...
```

## Step 1: Marketing Context Interview

This interview captures the go-to-market context that technical specifications don't
contain. It's different from the inventory interview (which captured WHAT the product
does) — this captures WHO it's for, HOW to position it, and WHAT language resonates.

If `./docs/marketing/interview.md` already exists, read it, summarize what you already
know, and ask only if there are gaps. Don't re-interview.

### Interview Protocol

**Conversational and adaptive.** Follow the user's natural way of describing their
market. Stop when you have enough context. Don't force all questions if answers are
already clear from previous interviews or existing materials.

Use `AskUserQuestion` throughout. Be conversational — adapt follow-ups based on answers.

#### 1. Target Audience

```
question: "Who is the primary buyer and user of this product?"
header: "Audience"
options:
  - label: "B2B — Enterprise"
    description: "Large organizations with complex procurement, multiple stakeholders"
  - label: "B2B — SMB"
    description: "Small/medium businesses, often owner or small team making decisions"
  - label: "B2C — Consumer"
    description: "Individual users, direct purchase or freemium"
  - label: "B2B2C / Platform"
    description: "Businesses who serve end consumers through your platform"
```

Follow up to understand:
- Primary personas (job titles, day-to-day responsibilities)
- Decision makers vs. end users (are they different people?)
- How technical is the typical user?
- What industry verticals matter most?

#### 2. Competitive Landscape

```
question: "How do you typically position this product against alternatives?"
header: "Competition"
options:
  - label: "Category leader"
    description: "We're the established solution — competitors are catching up"
  - label: "Challenger / disruptor"
    description: "We're taking on incumbents with a better approach"
  - label: "Niche specialist"
    description: "We serve a specific segment better than generalist tools"
  - label: "New category"
    description: "We're creating a category that doesn't have direct competitors yet"
```

Follow up:
- "Who are the top 2-3 alternatives prospects typically evaluate alongside you?"
- "What's the #1 reason someone picks your product over the alternative?"
- "What's the #1 objection your sales team hears?"

#### 3. Messaging Tone

```
question: "What tone should the marketing catalog use?"
header: "Tone"
options:
  - label: "Professional / Enterprise"
    description: "Formal, authoritative, emphasizes reliability and compliance"
  - label: "Modern / Approachable"
    description: "Friendly but competent, avoids jargon, conversational"
  - label: "Technical / Developer-focused"
    description: "Precise, respects the reader's technical knowledge, minimal fluff"
  - label: "Bold / Aspirational"
    description: "Energetic, future-focused, emphasizes transformation and innovation"
```

#### 4. Key Value Themes

```
question: "What are the top 3 themes your marketing emphasizes? (Select all that apply)"
header: "Themes"
options:
  - label: "Efficiency / Productivity"
    description: "Save time, do more with less, streamline workflows"
  - label: "Reliability / Trust"
    description: "Always works, secure, compliant, enterprise-grade"
  - label: "Flexibility / Customization"
    description: "Adapts to your needs, configurable, extensible"
  - label: "Simplicity / Ease of Use"
    description: "Easy to learn, intuitive, reduces complexity"
multiSelect: true
```

Follow up: "Are there specific proof points or metrics you use to back these up?
For example, '50% faster onboarding' or '99.9% uptime.'"

#### 5. Existing Documentation

```
question: "Do you have existing marketing materials, sales decks, or product descriptions
that should inform the catalog's language and positioning?"
header: "Materials"
options:
  - label: "Yes, I'll share them"
    description: "I have materials to provide as context (paste content or point to files)"
  - label: "Check docs/marketing/"
    description: "There should be materials in the docs/marketing/ folder already"
  - label: "No existing materials"
    description: "This is the first marketing documentation for this product"
```

If the user has materials, collect them and extract key terminology, positioning
statements, and feature descriptions to maintain consistency.

#### 6. Naming Conventions

```
question: "Do you have preferences for how features are named in marketing materials?"
header: "Naming"
options:
  - label: "Use existing product names"
    description: "We already have marketing names for features — I'll provide them"
  - label: "Create new names"
    description: "Generate marketing-friendly names based on what the features do"
  - label: "Mix — some exist, create the rest"
    description: "Some features have established names, others need new ones"
```

If they have existing names, collect them and map to feature IDs.

### Save Interview

Write the interview to `./docs/marketing/interview.md` with full Q&A.

Write key decisions to `./docs/marketing/catalog-config.json`:

```json
{
  "product_name": "from inventory",
  "inventory_path": "./docs/features",
  "audience": {
    "type": "b2b_enterprise | b2b_smb | b2c | b2b2c",
    "primary_personas": ["list of personas"],
    "buyer_vs_user": "same | different",
    "technical_level": "non_technical | semi_technical | technical"
  },
  "competitive_position": "leader | challenger | niche | new_category",
  "competitors": ["list"],
  "key_differentiator": "summary",
  "tone": "professional | modern | technical | bold",
  "value_themes": ["list"],
  "existing_feature_names": {
    "F-001": "Existing Marketing Name",
    "F-002.03": "Another Existing Name"
  },
  "proof_points": ["list of metrics or evidence"]
}
```

## Step 2: Determine Run Mode (Create vs. Update)

### 2a: Check for Existing Catalog State

Read `./docs/marketing/catalog-state.json` if it exists.

### 2b: Compute Feature Checksums

For each major feature in the inventory, compute a lightweight checksum of its state:
- Read the first 10 lines of `details/{feature_id}.md` (header, sub-feature count)
- Count behavior files matching `details/{feature_id}.*md`
- Concatenate: `{feature_id}:{sub_feature_count}:{behavior_count}:{last_modified_date}`
- This is the "checksum" — not cryptographic, just a change detection signal.

### 2c: Classify Each Feature Area

For each major feature:

- **No existing entry** → mode = `"create"`
- **Existing entry, checksum unchanged** → mode = `"skip"` (no changes detected)
- **Existing entry, checksum changed** → mode = `"update"` (feature has changed)

Present the classification to the user:

```
Catalog Run Plan
=================

Feature areas: {N} total

  CREATE (new): {N}
    {list feature IDs and names}

  UPDATE (changed since last pass): {N}
    {list feature IDs, names, and what changed}

  SKIP (unchanged): {N}
    {list feature IDs and names}

Proceeding with {N} feature areas...
```

## Step 3: Execute Catalog Generation via Agent Teams

### 3a: Create the Team

Use `TeamCreate` to create a team named "marketing-catalog". Enable delegate mode
(Shift+Tab) so you focus on coordination, not direct writing.

### 3b: Create Output Directories

```bash
mkdir -p ./docs/marketing/entries
mkdir -p ./docs/marketing/entries/archived
```

### 3c: Spawn Teammates in Batches

For each major feature area that is NOT "skip" mode:

1. **Create tasks** via `TaskCreate` for each pending feature area.
2. **Spawn teammates in batches of up to 5.** Each teammate gets ONE major feature
   area. Assign each the `feature-inventory:marketing-catalog-writer` agent.
3. **Each teammate receives** via its task description:
   - The feature ID, name, and sub-feature list
   - The mode (create or update)
   - The inventory path
   - The output path (`./docs/marketing/entries/`)
   - The product context from interview.md (summary)
   - The marketing context from catalog-config.json
   - Existing marketing materials summary (if found in Step 0)
   - The catalog-state.json path
   - For **update mode**: the existing entries and what changed
   - A pointer to read `references/context-management.md` before starting
   - This instruction verbatim: **"You are writing for a go-to-market team, not
     engineers. Every description must answer: What can users DO with this? Why
     should they CARE? What PROBLEM does it solve? Use plain language. Interview
     the user for each hero feature to understand positioning and audience.
     Date every entry with created and last-updated timestamps. Reference
     inventory feature IDs for traceability. Look for cross-feature value
     propositions that create compound marketing stories."**
4. **Wait for each batch to finish** before spawning the next batch.

Use Sonnet for teammates where possible. The lead (Opus) handles coordination, the
user-facing interview aggregation, and the final catalog assembly.

### 3d: Monitor Progress

While teammates work:
1. Monitor progress via `TaskList`.
2. After each batch completes, verify entry files exist and are non-empty.
3. If a teammate failed, re-queue the feature area for the next batch.

## Step 4: Identify Cross-Product Value Propositions

After all teammates complete, look ACROSS feature areas for high-value combinations
that span multiple major features. These are the product's most compelling stories —
where multiple capabilities combine to create something greater than the sum.

### 4a: Read All Entry Headers

Read the first 20 lines of each entry file to understand what marketing capabilities
exist. Also read any composite entries that teammates already created within individual
feature areas.

### 4b: Identify Cross-Feature Composites

Look for patterns:

- **Workflow chains**: Feature A's output feeds Feature B's input (e.g., data import →
  validation → reporting = "End-to-End Data Pipeline")
- **Persona stories**: Multiple features that serve the same persona create a cohesive
  experience (e.g., dashboard + alerts + reports = "Executive Command Center")
- **Platform plays**: Features that together create a platform value prop (e.g.,
  API + webhooks + SSO + role management = "Enterprise Integration Platform")
- **Competitive moats**: Combinations that competitors would struggle to replicate
  because they require deep integration across the product.

### 4c: Interview User on Cross-Product Composites

For each proposed composite, present it to the user:

```
question: "I've identified a potential high-value marketing story that combines
multiple features: {proposed name}. This brings together {Feature A}, {Feature B},
and {Feature C} to deliver {value proposition}. Does this resonate with how you
position the product?"
header: "Composite"
options:
  - label: "Yes, use this"
    description: "This is a real value story we tell or should tell"
  - label: "Modify it"
    description: "The concept is right but the framing needs adjustment"
  - label: "Not relevant"
    description: "These features aren't positioned together in our go-to-market"
```

### 4d: Write Cross-Product Composite Entries

For approved composites, write to `./docs/marketing/entries/COMPOSITE-{NNN}.md`:

```markdown
# {Marketing Name}

> Type: Cross-Product Value Proposition
> Contributing features: {list of feature IDs}
> Created: {YYYY-MM-DD}
> Last updated: {YYYY-MM-DD}

## The Story

{2-3 paragraphs describing the combined value. This is the narrative a salesperson
would tell or a marketing page would lead with. It's not a list of features — it's
a story about how these capabilities work together to solve a meaningful problem.}

## Contributing Capabilities

| Marketing Name | Feature ID | Role in This Story |
|---------------|-----------|-------------------|
| {name} | {F-001} | {what this feature contributes to the composite value} |
| {name} | {F-003} | {what this feature contributes} |

## Target Audience

{Who cares most about this composite story? May be different from the individual
features' audiences.}

## Competitive Advantage

{Why is this combination hard to replicate? What would a competitor need to build
to match this?}

---
```

## Step 5: Build the Master Catalog

### 5a: Write MARKETING-CATALOG.md

Read all entry files and composite files to build the master catalog. Read only
headers and key sections — don't re-read full entries.

```markdown
# {Product Name} — Product Capabilities Catalog

> For: Go-to-Market Teams (Product Marketing, Sales, Content, Demand Gen)
> Generated: {YYYY-MM-DD}
> Last updated: {YYYY-MM-DD}
> Source: Feature inventory with {N} features across {N} areas
> Entries: {N} feature entries, {N} value propositions

## How to Use This Catalog

This document describes every user-facing capability in {product name}, written
for non-technical audiences. Each entry explains what the feature does, who it's
for, and why it matters — in language suitable for marketing materials, sales
conversations, and product pages.

**For sales teams:** Use the "Key Capabilities" bullets as talk tracks. The "Problem
It Solves" section frames the conversation around customer pain points.

**For content/marketing:** Use entries as source material for web pages, data sheets,
blog posts, and campaign messaging. The tone and terminology are ready to use.

**For product marketing:** The "Value Propositions" section at the top highlights
the strongest cross-feature stories for positioning and competitive differentiation.

## Top Value Propositions

{List the cross-product composite entries prominently — these are the lead stories}

### {Composite Marketing Name}
{Brief summary — the elevator pitch version}
Contributing capabilities: {list}
[Full story →](./entries/COMPOSITE-001.md)

{Repeat for each composite}

## Feature Catalog

### {Major Feature Area Marketing Name}

#### {Hero Feature Marketing Name}
{One-sentence summary}
Who it's for: {persona}
[Full entry →](./entries/{feature_id}.md)

#### {Supporting Feature Marketing Name}
{One-sentence summary}
[Full entry →](./entries/{feature_id}.md)

{Repeat for each feature area}

## Changelog

| Date | Change | Affected Entries |
|------|--------|-----------------|
| {YYYY-MM-DD} | Initial catalog generation | All |
| {YYYY-MM-DD} | Updated {feature name} — {what changed} | {entry files} |

## Feature Reference Index

| Marketing Name | Feature ID(s) | Category | Entry |
|---------------|---------------|----------|-------|
| {name} | F-001, F-001.01-F-001.05 | {Hero/Supporting/Composite} | [link](./entries/...) |

---

*This catalog is auto-generated from the product's feature inventory and updated
whenever the underlying features change. Technical specifications are maintained
in the feature inventory at `{inventory-path}/`.*
```

### 5b: Write MARKETING-CATALOG.json

Machine-readable version for tooling, CMS integration, or API consumption:

```json
{
  "generated_at": "ISO-8601",
  "last_updated": "ISO-8601",
  "product": {
    "name": "from interview",
    "audience": "from catalog-config",
    "competitive_position": "from catalog-config"
  },
  "entries": [
    {
      "marketing_name": "Smart User Onboarding",
      "type": "hero",
      "feature_area": "F-001",
      "feature_ids": ["F-001.01", "F-001.01.01", "F-001.01.02"],
      "summary": "Plain-language one-liner",
      "audience": "Target persona",
      "problem_solved": "Pain point summary",
      "key_capabilities": ["bullet 1", "bullet 2"],
      "differentiators": ["if any"],
      "entry_file": "entries/F-001.md",
      "created": "YYYY-MM-DD",
      "last_updated": "YYYY-MM-DD"
    }
  ],
  "composites": [
    {
      "marketing_name": "Enterprise Integration Platform",
      "type": "composite",
      "contributing_features": ["F-003", "F-007", "F-012"],
      "summary": "Elevator pitch",
      "target_audience": "Who cares",
      "competitive_advantage": "Why it's hard to replicate",
      "entry_file": "entries/COMPOSITE-001.md",
      "created": "YYYY-MM-DD",
      "last_updated": "YYYY-MM-DD"
    }
  ],
  "changelog": [
    {
      "date": "YYYY-MM-DD",
      "action": "created | updated | archived",
      "entries_affected": ["list"],
      "description": "What changed"
    }
  ],
  "statistics": {
    "total_entries": 0,
    "hero_features": 0,
    "supporting_features": 0,
    "composites": 0,
    "feature_areas_covered": 0,
    "inventory_behaviors_mapped": 0
  }
}
```

### 5c: Update Catalog State

Write/update `./docs/marketing/catalog-state.json`:

```json
{
  "last_run_date": "ISO-8601",
  "inventory_path": "./docs/features",
  "feature_checksums": {
    "F-001": "F-001:8:45:2024-01-15",
    "F-002": "F-002:5:30:2024-01-15"
  },
  "entries": {
    "F-001": {
      "entry_file": "entries/F-001.md",
      "mode": "create",
      "created": "YYYY-MM-DD",
      "last_updated": "YYYY-MM-DD",
      "hero_count": 3,
      "supporting_count": 5,
      "composite_count": 1
    }
  },
  "composites": {
    "COMPOSITE-001": {
      "entry_file": "entries/COMPOSITE-001.md",
      "contributing_features": ["F-001", "F-003"],
      "created": "YYYY-MM-DD",
      "last_updated": "YYYY-MM-DD"
    }
  }
}
```

## Step 6: Present Summary

```
Marketing Catalog Complete
============================

Product: {name}
Audience: {type} — {primary personas}
Tone: {tone}

Catalog entries: {N}
  - Hero features: {N}
  - Supporting features: {N}
  - Cross-product value propositions: {N}

Coverage: {N}/{total} inventory feature areas cataloged
Inventory behaviors mapped: {N}

{If update run:}
Changes this run:
  - New entries: {N}
  - Updated entries: {N}
  - Archived entries: {N}
  - New composites: {N}

Output:
  - Master catalog:    ./docs/marketing/MARKETING-CATALOG.md
  - Machine-readable:  ./docs/marketing/MARKETING-CATALOG.json
  - Individual entries: ./docs/marketing/entries/
  - Catalog state:     ./docs/marketing/catalog-state.json

The catalog is ready to hand to your go-to-market team.
To update after feature changes, run this command again — it will
detect changes and update only affected entries.
```

## Resume Behavior

On every run, **auto-clear derived artifacts** that are always regenerated:

```bash
rm -f ./docs/marketing/MARKETING-CATALOG.md
rm -f ./docs/marketing/MARKETING-CATALOG.json
rm -f ./docs/marketing/existing-materials-summary.md
```

**Do NOT clear:**
- `interview.md` — user input
- `catalog-config.json` — user decisions
- `catalog-state.json` — change tracking state
- `entries/` — entries are updated incrementally, not rebuilt
- `entries/archived/` — archived entries are preserved

Then apply these resume rules:
- Step 0: Always validate inventory (quick). Always scan for existing materials.
- Step 1: Skip if `interview.md` AND `catalog-config.json` exist (load for context).
- Step 2: Always re-run (computes fresh checksums against current inventory state).
- Step 3: Skip features classified as "skip". Use "create" or "update" as classified.
- Step 4: Always re-run (cross-product analysis depends on all entries being current).
- Step 5: Always re-run (master catalog and JSON are cleared on each run).
- Step 6: Always present.
