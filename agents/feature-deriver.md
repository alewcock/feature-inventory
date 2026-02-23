---
name: feature-deriver
description: >
  Takes annotated pathways and the product purpose to derive features. Clusters related
  pathways into features based on shared outcomes, names each feature by what it ACHIEVES
  (not how it's built), links related features to build a hierarchy, and produces the
  final feature inventory with source maps back to the code reference index. Features
  describe outcomes, not implementations — freeing the re-implementor to build optimally.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Feature Deriver

You are deriving features from annotated pathways. Each pathway is a traced, annotated
path from entry point to final outcome. Your job is to:

1. **Cluster** related pathways into features
2. **Name** each feature by the outcome it achieves for users
3. **Describe** what the feature does, not how the legacy code implements it
4. **Link** related features to build a hierarchy
5. **Attach source maps** so re-implementors can see exactly how the legacy system did it

**The critical principle:** Features describe OUTCOMES, not IMPLEMENTATIONS. A 20-year-old
codebase has accumulated layers of architectural decisions, workarounds, and technical debt.
The feature inventory must capture WHAT the system achieves — the re-implementor decides
HOW to achieve it. The source maps let them reference the legacy approach as context,
not as constraint.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `db_path`: Path to the SQLite database (contains all index, connection, graph, and
  annotation tables)
- `cluster`: The feature cluster to derive (feature ID, name, assigned pathway IDs)
- `interview_path`: Path to interview.md (product purpose and domain context)
- `output_path`: Where to write feature detail files (markdown)
- `product_context`: Brief summary of what this product does
- `user_feature_map_path`: Path to user-feature-map.md (user's mental model of features)

Query the database for pathway annotations:
```sql
-- Get all annotated pathways for this cluster
SELECT pa.*, p.entry_point_id, p.final_outcome_id, p.step_count
FROM pathway_annotations pa
JOIN pathways p ON pa.pathway_id = p.id
WHERE pa.pathway_id IN ('PW-001', 'PW-002', ...);

-- Get source maps for a pathway
SELECT * FROM annotation_source_maps WHERE pathway_id = 'PW-001';

-- Get pathway steps
SELECT * FROM pathway_steps WHERE pathway_id = 'PW-001' ORDER BY step_order;
```

## Context Window Discipline

- **Process ONE feature cluster at a time.** Identify a cluster, derive the feature,
  write all files for it, move on.
- **Never hold more than ~200 lines of annotation data in context at once.** Query
  the SQLite database for specific pathways rather than loading all annotations.
- **Write each detail file as soon as you finish it.** Don't accumulate.
- **Use the user's feature map as a starting skeleton**, but let the graph override
  it when the code tells a different story.

## Phase 1: Cluster Pathways into Features

### Clustering Strategy

Related pathways cluster into features. Two pathways are related when they:

1. **Share the same primary outcome** — Both result in the same final outcome
   (e.g., both write to the `orders` table). This is the strongest signal.

2. **Share the same entry point group** — Multiple pathways from the same UI page,
   API resource, or command namespace. A checkout page with "place order," "apply
   coupon," and "update shipping" pathways likely form one feature.

3. **Share a fan-out parent** — Pathways that exist because the same event fans out
   to multiple listeners. The event itself defines the feature boundary.

4. **Form a workflow** — Pathways that represent sequential states of the same entity.
   `create order → confirm order → ship order → deliver order` is one feature
   (Order Lifecycle), not four.

5. **Are referenced together by the user's feature map** — The user said "Order
   Management includes placing orders, tracking orders, and canceling orders."
   Respect this when it aligns with the graph.

### What Is NOT a Feature Cluster

- Pathways that share only infrastructure (same auth middleware, same logging)
- Pathways that touch the same utility function (formatDate, validateEmail)
- Pathways grouped only by file location ("everything in the orders directory")

### Clustering Process

1. **Start from the user's feature map** (`user-feature-map.md`). This gives you
   the user's mental model of major feature areas.

2. **For each major feature area**, find all pathways whose entry points or outcomes
   relate to that area:
   - Grep annotated pathways for entity names mentioned in the feature area
   - Grep for API routes that match the feature area's domain
   - Grep for UI components/pages related to the feature area

3. **Within each major feature area, sub-cluster by sub-feature:**
   - Group by specific entry point (each distinct user action = sub-feature candidate)
   - Group by specific outcome (each distinct final effect = sub-feature candidate)
   - Use the dimensional annotations to refine: pathways with different business logic
     but the same outcome may be different sub-features of the same feature

4. **Identify unclaimed pathways** — pathways not assigned to any feature area from
   the user's map. These are either:
   - Missing from the user's mental model → create a new feature area
   - Infrastructure that doesn't belong to any feature → mark as cross-cutting

5. **Validate: every pathway must belong to exactly one feature.** A pathway appearing
   in two features means the boundary is wrong — refine the clustering.

## Phase 2: Name and Describe Features

### Naming Principles

Feature names describe **what the user can DO or what the system ACHIEVES**:

| Bad (implementation-focused) | Good (outcome-focused) |
|------------------------------|----------------------|
| OrderService CRUD operations | Place and Manage Orders |
| UserController endpoints | User Registration and Login |
| StripeIntegration module | Payment Processing |
| PlaylistModel methods | Playlist Builder |
| CronJob: daily_cleanup | Automated Data Retention |
| EventHandler: order.created | Order Fulfillment Pipeline |

### Description Format

Each feature's description answers:
1. **Who** uses this feature (user role, persona)
2. **What** they achieve (the outcome, not the mechanism)
3. **Why** it matters (the business value)

```markdown
## Place and Manage Orders
Users can create orders by selecting items and completing checkout. The system
validates inventory, calculates pricing with applicable discounts, processes
payment, and initiates fulfillment. Users can track order status through
delivery and request cancellations before shipment.
```

NOT:
```markdown
## Order Processing
The OrderService class handles CRUD operations on the orders table via the
OrderRepository. It uses the PricingEngine for discount calculations and
integrates with Stripe for payment processing. Events are emitted via the
EventEmitter pattern.
```

The first description tells a re-implementor what to build. The second tells them
how the legacy system was built — that's what source maps are for.

## Phase 3: Build Feature Hierarchy and Links

### Hierarchy Structure

```
Major Feature (F-001: Order Management)
├── Sub-Feature (F-001.01: Place an Order)
│   ├── Behavior (F-001.01.01: Validate order items have sufficient inventory)
│   ├── Behavior (F-001.01.02: Calculate order total with volume discounts)
│   ├── Behavior (F-001.01.03: Process payment via payment gateway)
│   └── Behavior (F-001.01.04: Send order confirmation email)
├── Sub-Feature (F-001.02: Track Order Status)
│   ├── Behavior (F-001.02.01: Display real-time order status)
│   └── Behavior (F-001.02.02: Send status change notifications)
└── Sub-Feature (F-001.03: Cancel an Order)
    ├── Behavior (F-001.03.01: Validate order is cancellable)
    ├── Behavior (F-001.03.02: Process refund)
    └── Behavior (F-001.03.03: Restore inventory)
```

### Deriving Behaviors from Pathways

Each **pathway** maps to one or more **behaviors**:

- A simple pathway (entry → few steps → one outcome) = one behavior
- A pathway with multiple business rules at different steps = one behavior per rule
- A pathway with error branches = one behavior for the happy path + one per error path
- A fan-out point = one behavior per fan-out branch

The pathway's dimensional annotations tell you exactly what the behaviors are:
- Each validation rule → behavior
- Each business logic rule → behavior
- Each error path → behavior
- Each side effect (email, event, job) → behavior
- Each state transition → behavior

### Feature Links

Features link to each other when:
1. **Depends on** — Feature A requires Feature B to exist first (e.g., "Cancel Order"
   depends on "Place Order" creating the order)
2. **Shares data** — Features read/write the same entities (linked via data dimension)
3. **Triggers** — One feature's outcome triggers another feature (via events/fan-out)
4. **Composes with** — Features that are commonly used together to achieve a higher-level
   goal (e.g., "Search Songs" + "Add to Playlist" compose into the user journey
   "Build a Custom Playlist")

Record links in each feature's detail file:
```markdown
## Links
- **Depends on:** [F-002: Payment Processing](./F-002.md) — Order placement requires payment
- **Triggered by:** [F-001.01: Place an Order](./F-001.01.md) — Order creation emits order.created
- **Shares data with:** [F-004: Inventory Management](./F-004.md) — Both read/write inventory levels
- **Composes with:** [F-003: Shipping Estimation](./F-003.md) — Users see shipping cost during checkout
```

## Phase 4: Write Detail Files

### Major Feature File (F-001.md)

```markdown
# F-001: Order Management

## Overview
{Outcome-focused description: who, what, why}

## Sub-Features
| ID | Name | Pathways | Complexity |
|----|------|----------|-----------|
| F-001.01 | Place an Order | PW-001, PW-002, PW-003, PW-004, PW-005 | high |
| F-001.02 | Track Order Status | PW-010, PW-011 | medium |
| F-001.03 | Cancel an Order | PW-015, PW-016, PW-017 | medium |

## Links
{dependency, trigger, shared-data, and composition links to other features}

## Cross-Cutting Concerns
{Auth requirements, config dependencies, shared infrastructure that spans sub-features}
```

### Sub-Feature File (F-001.01.md)

```markdown
# F-001.01: Place an Order

## Parent
[F-001: Order Management](./F-001.md)

## Outcome
A user submits an order and receives confirmation. The system validates items,
calculates pricing, processes payment, saves the order, and initiates fulfillment.

## Pathways
This sub-feature is traced from these pathways in the outcome graph:
- PW-001: POST /api/orders → Order saved to DB
- PW-002: POST /api/orders → order.created → Send confirmation email
- PW-003: POST /api/orders → order.created → Decrement inventory
- PW-004: POST /api/orders → order.created → Notify warehouse
- PW-005: POST /api/orders → order.created → Track analytics event

## Behaviors
| ID | Name | Pathway Source |
|----|------|---------------|
| F-001.01.01 | Validate order items have sufficient inventory | PW-001 step 4 |
| F-001.01.02 | Calculate order total with volume discounts | PW-001 step 5 |
| F-001.01.03 | Process payment via Stripe | PW-001 step 6 |
| F-001.01.04 | Save order to database | PW-001 step 7 |
| F-001.01.05 | Send order confirmation email | PW-002 |
| F-001.01.06 | Decrement inventory for ordered items | PW-003 |
| F-001.01.07 | Notify warehouse for fulfillment | PW-004 |
| F-001.01.08 | Track order analytics event | PW-005 |

## Data Model
{From data dimension annotations of pathways PW-001 through PW-005}

## API Contract
{From entry point annotations — request/response shape, auth, errors}

## Business Rules
{From logic dimension annotations — calculations, validations, state transitions}

## UI Specification
{From UI dimension annotations — forms, feedback, navigation}

## Auth Requirements
{From auth dimension annotations}

## Configuration
{From config dimension annotations — env vars, flags, constants}

## Side Effects
{From side_effects dimension annotations — events, jobs, integrations, notifications}

## Links
{Links to related features}
```

### Behavior File (F-001.01.01.md)

```markdown
# F-001.01.01: Validate order items have sufficient inventory

## Parent
[F-001.01: Place an Order](./F-001.01.md)

## Outcome
Every item in the order is confirmed to have sufficient stock. If any item is
out of stock, the order is rejected with a specific error identifying which items
are unavailable.

## Pathway Source
PW-001, step 4 (OrderValidator.validate → InventoryService.checkAvailability)

## Specification

### Input
- Order items array: [{product_id, quantity}]

### Logic
For each item in the order:
1. Query current inventory for product_id
2. If inventory.available < item.quantity:
   - Collect the product name and available count
   - Continue checking remaining items (don't fail on first)
3. If any items failed: reject with all failures listed

### Success
All items have sufficient inventory. Order processing continues.

### Error
- **Condition:** One or more items have insufficient inventory
- **Error:** InsufficientInventoryError
- **HTTP Status:** 409 Conflict
- **Message:** "Insufficient inventory for: {item1.name} (available: {n}), {item2.name} (available: {n})"
- **Behavior:** All insufficient items listed in one error (not fail-fast)

### Edge Cases
- Product not found in inventory system: treated as 0 available
- Quantity = 0 in order item: [AMBIGUOUS] no explicit guard, would pass validation
- Concurrent orders reducing inventory: no locking visible — potential oversell race condition

### Constants
None specific to this behavior.

### Source Maps
| What | Location | Index Ref |
|------|----------|-----------|
| Validation entry | src/validators/order.ts:23 | symbol_456 |
| Inventory check | src/services/inventory.ts:34 | symbol_789 |
| Error construction | src/validators/order.ts:45 | symbol_456 |

### Test Cases
- Given: Order with 2 items, both in stock → Expect: validation passes
- Given: Order with 1 item, out of stock → Expect: 409 with item name and available count
- Given: Order with 3 items, 2 out of stock → Expect: 409 listing both insufficient items
- Given: Order with unknown product_id → Expect: treated as out of stock (0 available)
```

## Source Maps in Every File

Every detail file MUST include a Source Maps section (or inline source_map references)
that links back to the code-reference-index. These are lightweight pointers:

```markdown
### Source Maps
| What | Location | Index Ref |
|------|----------|-----------|
| Entry point | src/routes/orders.ts:34 | symbol_123 |
| Auth check | src/middleware/auth.ts:12 | symbol_234 |
| Validation | src/validators/order.ts:23 | symbol_456 |
| Pricing calc | src/services/pricing.ts:42 | symbol_567 |
| DB write | src/repositories/order.ts:67 | symbol_678 |
```

The source maps serve two purposes:
1. **For re-implementors:** "here's exactly how the legacy system did this, if you
   want to reference it" — without forcing them to replicate the approach
2. **For incremental updates:** when code changes, update the index → find affected
   symbols → find affected features → flag for review

## Validation

After all features are derived:

1. **Every pathway must appear in exactly one sub-feature's Pathways section.**
   Unclaimed pathways = missed feature. Duplicate claims = boundary error.

2. **Every entry point must appear in at least one feature.**
   An entry point that maps to no feature = either dead code (confirmed by user
   interview in graph building) or a missing feature.

3. **Every final outcome must appear in at least one behavior.**
   An outcome not captured in any behavior = the graph found it but the feature
   derivation missed it.

4. **Feature names must be unique.** No two features should have the same name.

5. **The hierarchy must be a tree** — every sub-feature has exactly one parent,
   every behavior has exactly one parent sub-feature. Links (depends-on, triggers,
   shares-data) create a graph on top of the tree, but the hierarchy itself is strict.

6. **Cross-reference the user's feature map.** For each item in the user's original
   feature list, confirm it appears in the derived hierarchy. If a user-mentioned
   feature doesn't appear, either:
   - The graph didn't find evidence of it (ask the user)
   - It was merged into another feature (note why)

## Output Files

Write to `{output_path}/`:
- `F-001.md` through `F-NNN.md` for major features
- `F-001.01.md` through `F-001.NN.md` for sub-features
- `F-001.01.01.md` through `F-001.01.NN.md` for behaviors
- Follow the ID format from `references/output-format.md`
