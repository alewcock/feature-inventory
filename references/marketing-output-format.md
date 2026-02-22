# Marketing Catalog Output Format

The output is structured for go-to-market team consumption — plain language, value-focused,
with traceability back to the technical feature inventory.

## Directory Structure

```
docs/marketing/
├── MARKETING-CATALOG.md            # Master catalog (table of contents + summaries)
├── MARKETING-CATALOG.json          # Machine-readable for CMS/API/tooling
├── interview.md                    # Marketing context interview answers
├── catalog-config.json             # Audience, tone, positioning decisions
├── catalog-state.json              # Change tracking state for incremental updates
├── existing-materials-summary.md   # Summary of pre-existing marketing docs (transient)
└── entries/                        # One file per marketing entry
    ├── F-001.md                    # Feature area entry (hero + supporting features)
    ├── F-001-composite.md          # Within-area composite value proposition
    ├── F-002.md                    # Another feature area entry
    ├── COMPOSITE-001.md            # Cross-product value proposition
    ├── COMPOSITE-002.md            # Another cross-product value proposition
    └── archived/                   # Entries removed due to feature deprecation
        └── F-003.md               # Archived entry (feature removed from inventory)
```

## Entry Types

### Feature Area Entry ({feature_id}.md)

Each major feature area gets one entry file containing:
- Marketing name (not the technical name)
- User-value description (plain language)
- Target audience / persona
- Problem it solves
- Key capabilities (benefit-oriented bullets)
- Differentiators (if any — omit rather than fabricate)
- Related capabilities (links to other entries)
- Feature reference table (maps to inventory IDs)
- Created and last-updated dates
- Changelog (for update runs)

Feature area entries group hero features and supporting features together. An entry
may cover multiple sub-features from the inventory if they form a coherent marketing
story.

### Composite Value Proposition (COMPOSITE-{NNN}.md or {feature_id}-composite.md)

Two types of composite entries:

1. **Within-area composites** (`{feature_id}-composite.md`): Sub-features within ONE
   major feature that together create a higher-value story.

2. **Cross-product composites** (`COMPOSITE-{NNN}.md`): Features from MULTIPLE major
   feature areas that together create a product-level value proposition. These are
   the strongest marketing stories.

Composite entries contain:
- Marketing name for the composite capability
- A narrative "story" (not just a list of features)
- Contributing capabilities table
- Target audience for the composite
- Competitive advantage (why the combination matters)
- Created and last-updated dates

## catalog-state.json Schema

Tracks state for incremental updates. The orchestrator uses this to detect which
features have changed since the last run and classify them as create/update/skip.

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

### Checksum Format

Feature checksums are lightweight change-detection strings, NOT cryptographic hashes.
Format: `{feature_id}:{sub_feature_count}:{behavior_count}:{newest_detail_file_date}`

If any component changes between runs, the feature is marked for update.

## catalog-config.json Schema

Stores marketing context decisions from the user interview:

```json
{
  "product_name": "Product Name",
  "inventory_path": "./docs/features",
  "audience": {
    "type": "b2b_enterprise | b2b_smb | b2c | b2b2c",
    "primary_personas": ["VP of Engineering", "DevOps Lead"],
    "buyer_vs_user": "same | different",
    "technical_level": "non_technical | semi_technical | technical"
  },
  "competitive_position": "leader | challenger | niche | new_category",
  "competitors": ["Competitor A", "Competitor B"],
  "key_differentiator": "Summary of primary differentiation",
  "tone": "professional | modern | technical | bold",
  "value_themes": ["efficiency", "reliability", "flexibility"],
  "existing_feature_names": {
    "F-001": "Existing Marketing Name"
  },
  "proof_points": ["50% faster onboarding", "99.9% uptime"]
}
```

## Writing Guidelines

### Language

- **DO**: "Track every customer interaction in one place"
- **DON'T**: "CRUD operations on the CustomerInteraction entity with full audit logging"

- **DO**: "Get notified the moment something needs your attention"
- **DON'T**: "WebSocket-based real-time event push with configurable subscription filters"

- **DO**: "Works with the tools you already use"
- **DON'T**: "REST API with OAuth 2.0 bearer token authentication supporting 47 endpoints"

### Naming Features

Marketing names should:
- Be action-oriented or benefit-oriented ("Smart Scheduling" not "Schedule Manager")
- Be memorable and distinct (avoid generic names like "Dashboard" or "Settings")
- Reflect what the user accomplishes, not the technical implementation
- Be consistent in structure across the catalog (all noun phrases, or all verb phrases)

### Describing Capabilities

Each capability bullet should follow the pattern:
**What you can do** — **why it matters**

Example:
- "Set up automated reports that land in your inbox every Monday — so you start the week
  with the numbers that matter, without lifting a finger."

NOT:
- "Scheduled report generation with email delivery via SMTP integration"

### Handling Infrastructure Features

Features that are purely technical (caching, event bus, retry logic, database indexing)
should NOT get their own catalog entries. They should be:
- Mentioned as evidence supporting hero features ("blazing fast search powered by...")
- Referenced in differentiators ("enterprise-grade reliability with...")
- Omitted entirely if they don't contribute to a user-visible value story

### Dates and Changelog

Every entry must track:
- `Created: YYYY-MM-DD` — when the entry was first generated
- `Last updated: YYYY-MM-DD` — when the entry was last modified

Update runs add changelog entries:
```markdown
## Changelog
- 2024-03-15: Initial entry created
- 2024-04-22: Updated key capabilities — new bulk import feature added (F-001.08)
- 2024-05-10: Added "Enterprise Data Pipeline" composite value proposition
```

This makes it easy for the go-to-market team to see what's changed and when.
