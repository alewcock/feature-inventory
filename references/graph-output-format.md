# Graph-Based Pipeline Output Format

The graph-based pipeline produces a layered set of artifacts. Each layer builds on the
previous one, and all layers are designed for incremental updates when source code changes.

## Directory Structure

```
docs/features/
├── interview.md                          # User interview answers (unchanged)
├── user-feature-map.md                   # User's mental model of features (unchanged)
├── clarifications.md                     # Resolved ambiguities from graph building
├── discovery.json                        # Repo scan results (unchanged)
├── plan.json                             # Analysis plan (updated for graph pipeline)
│
├── index/                                # Layer 1: Code Reference Index
│   ├── code-reference-index.json         # Every symbol, call site, import, signature
│   └── code-reference-index-manifest.json # File processing manifest
│
├── connections/                           # Layer 2: Indirect Connections
│   ├── connections.json                   # All indirect edges (events, IPC, etc.)
│   └── unresolved-connections.json        # Items needing user interview
│
├── graph/                                 # Layer 3: Outcome Graph
│   ├── outcome-graph.json                 # Entry points, final outcomes, pathways
│   ├── validation-report.json             # Orphans, gaps, coverage stats
│   └── unresolved-graph.json              # Orphan entry points / unreachable outcomes
│
├── annotated/                             # Layer 4: Annotated Pathways
│   ├── annotated-pathways.json            # Pathways with dimensional annotations
│   └── annotation-stats.json              # Coverage and ambiguity counts
│
├── details/                               # Layer 5: Feature Detail Files (unchanged format)
│   ├── F-001.md                           # Major feature
│   ├── F-001.01.md                        # Sub-feature
│   ├── F-001.01.01.md                     # Behavior
│   └── ...
│
├── FEATURE-INDEX.md                       # Master table of contents
└── FEATURE-INDEX.json                     # Machine-readable index
```

## Layer 1: Code Reference Index

### code-reference-index.json

The complete mechanical index of every named symbol in the codebase.

```json
{
  "generated_at": "ISO-8601",
  "repo": "repo-name",
  "scope": "full",
  "languages": ["typescript", "csharp"],
  "files_indexed": 234,
  "total_symbols": 1847,

  "symbols": [
    {
      "id": "SYM-0001",
      "type": "function | class | method | route | constant | interface | enum | variable",
      "name": "calculateShippingCost",
      "qualified_name": "ShippingService.calculateShippingCost",
      "file": "src/services/shipping.ts",
      "line_start": 47,
      "line_end": 89,
      "signature": {
        "params": [{"name": "order", "type": "Order"}, {"name": "dest", "type": "Address"}],
        "return_type": "ShippingQuote"
      },
      "visibility": "public",
      "is_async": true,
      "calls": [
        {"symbol_id": "SYM-0045", "name": "getTaxRate", "line": 52},
        {"symbol_id": "SYM-0078", "name": "getCarrierRates", "line": 58}
      ],
      "called_by": [
        {"symbol_id": "SYM-0102", "name": "CheckoutController.submit", "file": "src/routes/checkout.ts", "line": 42}
      ],
      "exports": ["named"],
      "caller_count": 3
    }
  ],

  "imports": [
    {
      "file": "src/services/shipping.ts",
      "line": 1,
      "source": "./tax",
      "resolved_file": "src/services/tax.ts",
      "symbols": ["getTaxRate", "TaxConfig"]
    }
  ],

  "connection_hints": [
    {
      "type": "dynamic_call | string_key_dispatch | framework_magic | reflection",
      "file": "src/plugins/loader.ts",
      "line": 45,
      "expression": "plugins[name].init()",
      "note": "Description of what needs resolution"
    }
  ],

  "file_manifest": [
    {"file": "src/services/shipping.ts", "lines": 200, "symbols": 12, "status": "done"}
  ],

  "statistics": {
    "by_type": {"function": 423, "class": 67, "method": 312, "route": 45},
    "dynamic_calls": 23,
    "untyped_params": 156
  }
}
```

## Layer 2: Indirect Connections

### connections.json

Every indirect edge between code that doesn't involve a direct function call.

```json
{
  "generated_at": "ISO-8601",
  "repo": "repo-name",
  "total_connections": 156,

  "connections": [
    {
      "id": "CONN-001",
      "connection_type": "event | ipc | pubsub | db_hook | reactive | middleware_chain | di_binding | webhook | convention | dispatch_table | file_watcher | signal",
      "...": "type-specific fields (see connection-hunter.md for schemas)"
    }
  ],

  "unresolved": [
    {
      "type": "unmatched_emitter | orphan_route | dynamic_dispatch",
      "...": "details with question for user"
    }
  ],

  "statistics": {
    "by_type": {"event": 34, "ipc": 12, "pubsub": 8},
    "resolved_from_hints": 14,
    "unresolved_total": 7
  }
}
```

## Layer 3: Outcome Graph

### outcome-graph.json

The complete graph of paths from entry points to final outcomes.

```json
{
  "generated_at": "ISO-8601",
  "repo": "repo-name",
  "product": "product name",

  "entry_points": [
    {
      "id": "EP-001",
      "category": "http_route | cli_command | cron_job | ui_event | message_consumer | webhook | ipc_handler | lifecycle_hook | file_watcher | signal | timer | websocket | db_trigger | observable_source",
      "label": "POST /api/orders",
      "symbol": "OrderController.create",
      "symbol_id": "SYM-0102",
      "file": "src/routes/orders.ts",
      "line": 34,
      "trigger": "User submits order via API",
      "authentication": "required | optional | none"
    }
  ],

  "final_outcomes": [
    {
      "id": "FO-001",
      "category": "data_mutation | http_response | email | sms | push_notification | external_api_call | file_written | queue_published | websocket_sent | cache_mutation | business_log | ui_state_change | process_control",
      "label": "Order saved to database",
      "symbol": "OrderRepository.save",
      "symbol_id": "SYM-0678",
      "file": "src/repositories/order.ts",
      "line": 67,
      "target": "orders table",
      "operation": "INSERT"
    }
  ],

  "pathways": [
    {
      "id": "PW-001",
      "entry_point": "EP-001",
      "final_outcome": "FO-001",
      "steps": [
        {"symbol_id": "SYM-0102", "symbol": "OrderController.create", "file": "src/routes/orders.ts", "line": 34, "type": "entry_point"},
        {"symbol_id": "SYM-0200", "symbol": "authMiddleware", "file": "src/middleware/auth.ts", "line": 12, "type": "middleware"},
        {"symbol_id": "SYM-0305", "symbol": "OrderService.processOrder", "file": "src/services/order.ts", "line": 89, "type": "logic"},
        {"symbol_id": "SYM-0678", "symbol": "OrderRepository.save", "file": "src/repositories/order.ts", "line": 67, "type": "final_outcome"}
      ],
      "fan_outs": []
    }
  ],

  "fan_out_points": [
    {
      "event": "order.created",
      "location": {"file": "src/services/order.ts", "line": 142, "symbol_id": "SYM-0310"},
      "branch_count": 4,
      "pathway_ids": ["PW-002", "PW-003", "PW-004", "PW-005"]
    }
  ],

  "infrastructure": [
    {
      "symbol_id": "SYM-0900",
      "symbol": "formatCurrency",
      "file": "src/utils/format.ts",
      "line": 5,
      "caller_count": 23,
      "on_pathways": ["PW-001", "PW-005", "PW-012"],
      "classification": "utility"
    }
  ],

  "validation": {
    "entry_points_total": 45,
    "final_outcomes_total": 89,
    "pathways_total": 234,
    "orphan_entry_points": [],
    "unreachable_outcomes": [],
    "graph_gaps": [],
    "coverage": {
      "symbols_on_pathways": 423,
      "symbols_as_infrastructure": 156,
      "symbols_unclassified": 0,
      "index_coverage_pct": 100.0
    }
  },

  "statistics": {
    "entry_points": 45,
    "final_outcomes": 89,
    "pathways": 234,
    "fan_out_points": 12,
    "avg_pathway_length": 6.3,
    "max_pathway_length": 18,
    "infrastructure_symbols": 156,
    "dead_code_symbols": 8
  }
}
```

## Layer 4: Annotated Pathways

### annotated-pathways.json

Each pathway annotated with dimensional information from the source code.

```json
{
  "generated_at": "ISO-8601",
  "repo": "repo-name",
  "pathways_annotated": 234,

  "annotated_pathways": [
    {
      "pathway_id": "PW-001",
      "entry_point": "EP-001",
      "entry_label": "POST /api/orders",
      "final_outcome": "FO-001",
      "outcome_label": "Order saved to database",
      "steps": ["...from graph..."],
      "dimensions": {
        "data": {
          "entities_read": [],
          "entities_written": [],
          "validations": [],
          "transformations": []
        },
        "auth": {
          "authentication": {},
          "authorization": [],
          "tenant_isolation": {}
        },
        "logic": {
          "rules": [],
          "state_transitions": [],
          "error_paths": [],
          "edge_cases": []
        },
        "ui": {
          "entry_ui": {},
          "outcome_ui": {},
          "loading_state": {}
        },
        "config": {
          "env_vars": [],
          "feature_flags": [],
          "constants": []
        },
        "side_effects": {
          "events_emitted": [],
          "jobs_queued": [],
          "external_calls": [],
          "notifications": []
        }
      }
    }
  ]
}
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
2. Re-index changed files (update code-reference-index.json)
   ↓
3. Re-hunt connections in changed files (update connections.json)
   ↓
4. Find affected pathways (pathways containing updated symbols)
   ↓
5. Re-trace affected pathways (update outcome-graph.json)
   ↓
6. Re-annotate affected pathways (update annotated-pathways.json)
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
