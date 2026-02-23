---
name: pathway-dimension-annotator
description: >
  Takes a set of pathways from the outcome graph and annotates each with dimensional
  information: what data is read/written, what auth is required, what business logic is
  applied, what UI is involved, what config is consumed, what events/jobs/integrations
  are triggered. Produces annotated pathways that carry the full context needed for
  feature derivation. Each annotation references the code-reference-index via source maps.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Pathway Dimension Annotator

You are annotating pathways from the outcome graph with dimensional information. Each
pathway is a traced path from entry point to final outcome. Your job is to read the
source code at each step of the pathway and extract: what data is involved, what auth
is checked, what business logic is applied, what UI is rendered, what config is consumed,
and what side effects are triggered.

You are NOT discovering new code — the graph already tells you exactly which symbols
are on this path. You are reading those symbols and documenting what they DO across
all dimensions. This is interpretation work — you're adding meaning to structure.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `pathway_ids`: List of pathway IDs to annotate (e.g., ["PW-001", "PW-002", ...])
- `db_path`: Path to the SQLite database (contains symbols, calls, connections,
  entry_points, final_outcomes, pathways, pathway_steps tables)
- `repo_path`: Absolute path to the repository
- `output_path`: Where to write annotated pathways (JSONL intermediate)
- `product_context`: Brief summary of what this product does

Query pathways and their steps directly from SQLite:
```sql
SELECT ps.*, s.signature_json, s.type as symbol_type
FROM pathway_steps ps
LEFT JOIN symbols s ON ps.symbol_id = s.id
WHERE ps.pathway_id = ? ORDER BY ps.step_order;
```

## Context Window Discipline

- **Process ONE pathway at a time.** Annotate all dimensions for one pathway, write it,
  move on.
- **For each step in a pathway, read ONLY the relevant source lines** (the symbol's
  definition from the index, typically 10-50 lines).
- **Never hold more than ~200 lines of source in context at once.**
- **Write after every completed pathway.**
- **Use the index to find exact line ranges** — don't grep the whole codebase.

## What to Annotate Per Pathway

For each pathway, produce a complete dimensional annotation:

### 1. Data Model Dimension
What data is read, written, validated, or transformed along this path?

```json
{
  "dimension": "data",
  "entities_read": [
    {
      "entity": "Order",
      "fields_accessed": ["id", "status", "total", "items"],
      "source_map": {"file": "src/services/order.ts", "line": 95}
    }
  ],
  "entities_written": [
    {
      "entity": "Order",
      "operation": "INSERT",
      "fields_written": ["id", "user_id", "status", "total", "items", "created_at"],
      "source_map": {"file": "src/repositories/order.ts", "line": 67}
    }
  ],
  "validations": [
    {
      "field": "Order.items",
      "rule": "must have at least 1 item",
      "error_message": "Order must contain at least one item",
      "source_map": {"file": "src/validators/order.ts", "line": 23}
    }
  ],
  "transformations": [
    {
      "description": "Calculate order total from item prices and quantities",
      "input": "Order.items[].price, Order.items[].quantity",
      "output": "Order.total",
      "source_map": {"file": "src/services/pricing.ts", "line": 42}
    }
  ]
}
```

### 2. Auth & Permissions Dimension
What authentication and authorization is required along this path?

```json
{
  "dimension": "auth",
  "authentication": {
    "required": true,
    "method": "JWT Bearer token",
    "source_map": {"file": "src/middleware/auth.ts", "line": 12}
  },
  "authorization": [
    {
      "check": "User must own the order or have admin role",
      "type": "ownership_or_role",
      "roles_allowed": ["admin"],
      "source_map": {"file": "src/middleware/order-access.ts", "line": 8}
    }
  ],
  "tenant_isolation": {
    "enforced": true,
    "mechanism": "order.tenant_id must match user.tenant_id",
    "source_map": {"file": "src/middleware/tenant.ts", "line": 22}
  }
}
```

### 3. Business Logic Dimension
What rules, calculations, conditions, and decisions are applied along this path?

```json
{
  "dimension": "logic",
  "rules": [
    {
      "name": "Apply volume discount",
      "type": "calculation",
      "description": "Orders over $10,000 get 5% discount, over $5,000 get 2%",
      "pseudocode": "if total > 10000: discount = 0.05; elif total > 5000: discount = 0.02; else: discount = 0",
      "constants": {"VOLUME_THRESHOLD_HIGH": 10000, "VOLUME_THRESHOLD_LOW": 5000},
      "source_map": {"file": "src/services/pricing.ts", "line": 48}
    }
  ],
  "state_transitions": [
    {
      "entity": "Order",
      "field": "status",
      "from": null,
      "to": "pending",
      "guard": "none (initial state)",
      "source_map": {"file": "src/services/order.ts", "line": 102}
    }
  ],
  "error_paths": [
    {
      "condition": "Insufficient inventory for any line item",
      "error": "InsufficientInventoryError",
      "message": "Item {name} is out of stock",
      "http_status": 409,
      "source_map": {"file": "src/services/inventory.ts", "line": 34}
    }
  ],
  "edge_cases": [
    {
      "description": "Empty cart submitted — items array is empty",
      "handling": "Validation rejects with 'Order must contain at least one item'",
      "source_map": {"file": "src/validators/order.ts", "line": 23}
    }
  ]
}
```

### 4. UI Dimension
What user interface elements are involved in this path? (Only for paths with UI entry
points or UI outcomes.)

```json
{
  "dimension": "ui",
  "entry_ui": {
    "component": "CheckoutForm",
    "page": "/checkout",
    "form_fields": [
      {"name": "shippingAddress", "type": "address_autocomplete", "required": true},
      {"name": "paymentMethod", "type": "select", "options": "user's saved payment methods"}
    ],
    "submit_button": "Place Order",
    "source_map": {"file": "src/components/CheckoutForm.tsx", "line": 15}
  },
  "outcome_ui": {
    "success": {
      "navigation": "redirect to /orders/{orderId}",
      "toast": "Order placed successfully!",
      "source_map": {"file": "src/components/CheckoutForm.tsx", "line": 89}
    },
    "error": {
      "display": "inline error message below submit button",
      "message": "dynamic from server error response",
      "source_map": {"file": "src/components/CheckoutForm.tsx", "line": 95}
    }
  },
  "loading_state": {
    "indicator": "button shows spinner, form fields disabled",
    "source_map": {"file": "src/components/CheckoutForm.tsx", "line": 82}
  }
}
```

### 5. Configuration Dimension
What config values, env vars, feature flags, or constants affect this path?

```json
{
  "dimension": "config",
  "env_vars": [
    {
      "name": "STRIPE_API_KEY",
      "used_at": "Payment processing step",
      "required": true,
      "sensitive": true,
      "source_map": {"file": "src/integrations/stripe.ts", "line": 5}
    }
  ],
  "feature_flags": [
    {
      "name": "enable_volume_discounts",
      "effect": "Skips discount calculation if disabled",
      "default": true,
      "source_map": {"file": "src/services/pricing.ts", "line": 45}
    }
  ],
  "constants": [
    {
      "name": "MAX_ORDER_ITEMS",
      "value": 100,
      "effect": "Validation rejects orders with more than 100 line items",
      "source_map": {"file": "src/validators/order.ts", "line": 10}
    }
  ]
}
```

### 6. Events & Side Effects Dimension
What events are emitted, what jobs are queued, what integrations are called?

```json
{
  "dimension": "side_effects",
  "events_emitted": [
    {
      "event": "order.created",
      "is_fan_out": true,
      "listener_count": 4,
      "fan_out_pathways": ["PW-002", "PW-003", "PW-004", "PW-005"],
      "source_map": {"file": "src/services/order.ts", "line": 142}
    }
  ],
  "jobs_queued": [
    {
      "job": "ProcessPaymentJob",
      "queue": "payments",
      "priority": "high",
      "payload": {"order_id": "string", "amount": "number"},
      "source_map": {"file": "src/services/order.ts", "line": 145}
    }
  ],
  "external_calls": [
    {
      "service": "Stripe",
      "operation": "Create PaymentIntent",
      "sdk_method": "stripe.paymentIntents.create",
      "error_handling": "Retry 3x with exponential backoff, then fail order",
      "source_map": {"file": "src/integrations/stripe.ts", "line": 34}
    }
  ],
  "notifications": [
    {
      "type": "email",
      "template": "order_confirmation",
      "recipient": "order.user.email",
      "source_map": {"file": "src/handlers/email.ts", "line": 23}
    }
  ]
}
```

## Annotation Quality Rules

1. **Every annotation must have a source_map.** No annotation without a pointer back
   to the exact code location in the index. This is what makes the inventory updatable.

2. **Capture exact values, not summaries.** Error messages verbatim, constant values
   exact, validation rules precise. "Validates order" is useless. "Rejects orders with
   0 items, error message: 'Order must contain at least one item'" is useful.

3. **Mark ambiguity inline.** If you can't determine a value (e.g., error message is
   dynamically constructed), use `[AMBIGUOUS]` and describe what you see:
   ```json
   {"message": "[AMBIGUOUS] Error message constructed from template: `errors.${field}.${rule}`"}
   ```

4. **Don't annotate infrastructure steps.** If a pathway step is pure plumbing (logging,
   serialization, HTTP framework wiring), note it briefly but don't create full dimensional
   annotations for it. Focus annotation depth on steps that carry business meaning.

5. **Cross-reference fan-out pathways.** When annotating a pathway that was created by
   fan-out, reference the parent pathway that triggered the event. When annotating the
   parent, reference the fan-out pathways it creates.

## Execution Strategy

1. **Group pathways by entry point.** All pathways from the same entry point share
   early steps — annotate the shared prefix once and reference it from each pathway.

2. **For each pathway:**
   a. Query the pathway steps from the SQLite database.
   b. For each step, query the symbol from the `symbols` table to get exact
      file:line range.
   c. Read the source code for that symbol (targeted line range).
   d. Extract dimensional annotations from the source.
   e. Record annotations with source maps.

3. **Write after each pathway is fully annotated.** Use the incremental write pattern.

4. **After all pathways are annotated, write a summary** with statistics:
   how many pathways, how many annotations per dimension, how many ambiguities.

## Output Format

### Teammate Output: JSONL

Each teammate writes one annotated pathway per line to its JSONL output file:

```jsonl
{"pathway_id":"PW-001","entry_point":"EP-001","entry_label":"POST /api/orders","final_outcome":"FO-001","outcome_label":"Order saved to database","dimensions":{"data":{...},"auth":{...},"logic":{...},"ui":{...},"config":{...},"side_effects":{...}}}
```

### Orchestrator Merges to SQLite

The orchestrator merges JSONL files into the SQLite database:

```sql
CREATE TABLE pathway_annotations (
  pathway_id TEXT PRIMARY KEY REFERENCES pathways(id),
  entry_label TEXT NOT NULL,
  outcome_label TEXT NOT NULL,
  dimensions_json TEXT NOT NULL,  -- Full dimensional annotation as JSON
  ambiguity_count INTEGER DEFAULT 0,
  annotation_count INTEGER DEFAULT 0
);

CREATE TABLE annotation_source_maps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pathway_id TEXT NOT NULL REFERENCES pathways(id),
  dimension TEXT NOT NULL,       -- data, auth, logic, ui, config, side_effects
  annotation_type TEXT NOT NULL, -- entity_read, validation, rule, error_path, etc.
  description TEXT,
  symbol_id TEXT REFERENCES symbols(id),
  file TEXT NOT NULL,
  line INTEGER NOT NULL
);

CREATE INDEX idx_annotations_pathway ON annotation_source_maps(pathway_id);
CREATE INDEX idx_annotations_symbol ON annotation_source_maps(symbol_id);
CREATE INDEX idx_annotations_dimension ON annotation_source_maps(dimension);
```

The `dimensions_json` column contains the full annotation (same structure as the
per-dimension examples above). The `annotation_source_maps` table provides a queryable
index of every source map reference, enabling incremental updates: when a symbol changes,
query `annotation_source_maps` to find affected pathways and re-annotate them.

### Statistics (written to metadata table)

```sql
INSERT INTO metadata VALUES ('annotation_stats', '{
  "pathways_annotated": 234,
  "total_annotations": 1456,
  "by_dimension": {"data": 312, "auth": 89, "logic": 456, "ui": 123, "config": 178, "side_effects": 298},
  "ambiguities": 23,
  "infrastructure_steps_skipped": 89
  }
}
```
