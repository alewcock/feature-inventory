# Graph-Based Pipeline Output Format

The graph-based pipeline produces a layered set of artifacts. Each layer builds on the
previous one, and all layers are designed for incremental updates when source code changes.

## Storage Strategy

The pipeline uses three storage formats, each chosen for its strengths:

| Format | Used For | Why |
|--------|----------|-----|
| **SQLite** | Index, connections, graph, annotations | Queryable, incrementally updatable, relational. Agents query specific symbols/pathways instead of loading entire datasets |
| **JSONL** | Intermediate teammate output | Append-only, crash-safe. Each line is a valid record. Merged into SQLite by orchestrator |
| **Markdown** | Feature detail files, interview, indexes | Human-readable, agent-readable. The final output consumed by re-implementors |

## Directory Structure

```
docs/features/
├── interview.md                          # User interview answers (unchanged)
├── user-feature-map.md                   # User's mental model of features (unchanged)
├── clarifications.md                     # Resolved ambiguities from graph building
├── discovery.json                        # Repo scan results (unchanged)
├── plan.json                             # Analysis plan (updated for graph pipeline)
│
├── graph.db                              # SQLite database (Layers 1-4 combined)
│   ├── [symbols table]                   #   Layer 1: Code Reference Index
│   ├── [calls table]                     #   Layer 1: Call edges
│   ├── [imports table]                   #   Layer 1: Import relationships
│   ├── [file_manifest table]             #   Layer 1: Processing manifest
│   ├── [connection_hints table]          #   Layer 1: Hints for connection hunter
│   ├── [connections table]               #   Layer 2: Indirect connections
│   ├── [unresolved_connections table]    #   Layer 2: Needing user interview
│   ├── [entry_points table]              #   Layer 3: Graph entry points
│   ├── [final_outcomes table]            #   Layer 3: Graph outcomes
│   ├── [pathways table]                  #   Layer 3: Traced pathways
│   ├── [pathway_steps table]             #   Layer 3: Steps within pathways
│   ├── [fan_out_points table]            #   Layer 3: Fan-out locations
│   ├── [infrastructure table]            #   Layer 3: Non-pathway symbols
│   ├── [graph_validation table]          #   Layer 3: Validation issues
│   ├── [pathway_annotations table]       #   Layer 4: Dimensional annotations
│   ├── [annotation_source_maps table]    #   Layer 4: Source map index
│   └── [metadata table]                  #   Statistics and configuration
│
├── intermediate/                          # JSONL teammate output (can be deleted after merge)
│   ├── index--main.jsonl                  #   Indexer output for src/main scope
│   ├── index--renderer.jsonl              #   Indexer output for src/renderer scope
│   ├── connections--events-ipc.jsonl      #   Connection hunter output
│   ├── annotations--ep001-group.jsonl     #   Annotator output for EP-001 group
│   └── ...
│
├── details/                               # Layer 5: Feature Detail Files (markdown)
│   ├── F-001.md                           # Major feature
│   ├── F-001.01.md                        # Sub-feature
│   ├── F-001.01.01.md                     # Behavior
│   └── ...
│
├── FEATURE-INDEX.md                       # Master table of contents
└── FEATURE-INDEX.json                     # Machine-readable index (exported from SQLite)
```

## Why SQLite?

A 20-year-old codebase can easily produce 50,000+ symbols. At that scale:

- **JSON is unusable.** A 50MB JSON file can't be loaded into an agent's context window.
  Agents must query specific symbols, not load everything. SQLite enables
  `SELECT * FROM symbols WHERE file = 'src/orders.ts'` instead of parsing the whole index.

- **Incremental updates are cheap.** When code changes, UPDATE/INSERT only affected rows.
  JSON requires rewriting the entire file to change one symbol.

- **Relationships are natural.** Calls, connections, pathways, and annotations are
  relational data. SQLite JOINs express queries like "find all pathways that pass through
  this symbol" efficiently, without scanning every pathway.

- **Single file, no server.** SQLite is just a `.db` file. No database installation, no
  network, no configuration. It ships with Python and most language runtimes.

- **Agents can use it directly.** Bash tool runs `sqlite3 graph.db "SELECT ..."` or
  agents use Python's built-in `sqlite3` module. No special tooling required.

## Layers 1-4: SQLite Database (graph.db)

All structured data lives in a single SQLite database. See the individual agent specs
for complete table schemas:

- **Layer 1 (Code Reference Index):** `code-indexer.md` — tables: `symbols`, `calls`,
  `imports`, `file_manifest`, `connection_hints`, `metadata`
- **Layer 2 (Indirect Connections):** `connection-hunter.md` — tables: `connections`,
  `unresolved_connections` (plus enriched `calls` rows with `connection_type`)
- **Layer 3 (Outcome Graph):** `graph-builder.md` — tables: `entry_points`,
  `final_outcomes`, `pathways`, `pathway_steps`, `fan_out_points`, `fan_out_branches`,
  `infrastructure`, `infrastructure_pathway_refs`, `graph_validation`
- **Layer 4 (Annotated Pathways):** `pathway-dimension-annotator.md` — tables:
  `pathway_annotations`, `annotation_source_maps`

### Key Cross-Layer Queries

```sql
-- From a changed file, find all affected features:
-- Step 1: Find symbols in the changed file
SELECT id FROM symbols WHERE file = 'src/services/order.ts';

-- Step 2: Find pathways containing those symbols
SELECT DISTINCT pathway_id FROM pathway_steps WHERE symbol_id IN (
  SELECT id FROM symbols WHERE file = 'src/services/order.ts'
);

-- Step 3: Find features assigned to those pathways (from FEATURE-INDEX.json)
-- (Feature→pathway mapping is in the JSON index, not SQLite,
--  because features are markdown files, not database records)

-- Find all entry points that lead to a specific final outcome
SELECT DISTINCT ep.* FROM entry_points ep
JOIN pathways p ON p.entry_point_id = ep.id
WHERE p.final_outcome_id = 'FO-001';

-- Get full dimensional annotation for a pathway
SELECT dimensions_json FROM pathway_annotations WHERE pathway_id = 'PW-001';

-- Find all unresolved issues across all layers
SELECT 'connection' as layer, type, details_json FROM unresolved_connections WHERE resolved = 0
UNION ALL
SELECT 'graph' as layer, issue_type, observation FROM graph_validation WHERE resolved = 0;
```

## Layer 5: Feature Detail Files

Feature detail files use the same format as `output-format.md` (F-001.md, F-001.01.md,
F-001.01.01.md hierarchy) with these additions:

### Pathway References

Every sub-feature includes a **Pathways** section listing the graph pathways it was
derived from:

```markdown
## Pathways
- PW-001: POST /api/orders → Order saved to DB
- PW-002: POST /api/orders → order.created → Send confirmation email
```

### Source Maps

Every behavior file includes a **Source Maps** table linking back to the code reference
index:

```markdown
### Source Maps
| What | Location | Index Ref |
|------|----------|-----------|
| Entry point | src/routes/orders.ts:34 | SYM-0102 |
| Validation | src/validators/order.ts:23 | SYM-0456 |
| DB write | src/repositories/order.ts:67 | SYM-0678 |
```

### Outcome-Focused Descriptions

Feature and sub-feature descriptions focus on WHAT the system achieves (outcomes),
not HOW the legacy code implements it. The source maps let re-implementors reference
the legacy approach without being constrained by it.

## Incremental Update Flow

When source code changes:

```
1. Changed files identified (git diff)
   ↓
2. Re-index changed files (UPDATE/INSERT symbols, calls, imports in graph.db)
   ↓
3. Re-hunt connections in changed files (UPDATE connections in graph.db)
   ↓
4. Find affected pathways (pathways containing updated symbols)
   ↓
5. Re-trace affected pathways (UPDATE pathways, pathway_steps in graph.db)
   ↓
6. Re-annotate affected pathways (UPDATE pathway_annotations in graph.db)
   ↓
7. Flag features whose pathways changed (update detail files)
   ↓
8. Generate change notes (user-facing summary of what changed)
```

Each step only processes the DELTA — files/symbols/pathways that were affected by the
code change. The full pipeline only runs on initial creation.

## FEATURE-INDEX.json with Graph Metadata

The feature index JSON gains additional fields linking features to the graph:

```json
{
  "features": [
    {
      "id": "F-001",
      "name": "Order Management",
      "tier": "major",
      "detail_file": "details/F-001.md",
      "children": [
        {
          "id": "F-001.01",
          "name": "Place an Order",
          "tier": "sub-feature",
          "detail_file": "details/F-001.01.md",
          "pathways": ["PW-001", "PW-002", "PW-003", "PW-004", "PW-005"],
          "entry_points": ["EP-001"],
          "final_outcomes": ["FO-001", "FO-003", "FO-004", "FO-005", "FO-006"],
          "children": [
            {
              "id": "F-001.01.01",
              "name": "Validate order items have sufficient inventory",
              "tier": "behavior",
              "detail_file": "details/F-001.01.01.md",
              "pathway_source": "PW-001 step 4",
              "source_maps": [
                {"symbol_id": "SYM-0456", "file": "src/validators/order.ts", "line": 23}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```
