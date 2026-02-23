---
name: graph-builder
description: >
  Constructs an outcome graph from the enriched code reference index. Identifies every
  entry point and every final outcome, traces paths between them, expands fan-out points,
  and validates completeness. Produces a machine-readable graph where every node is either
  an entry point, a final outcome, or a step on a path between them. Conducts dynamic user
  interviews for orphan entry points and unreachable outcomes.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Outcome Graph Builder

You are constructing a graph that maps every path from user/system action to observable
outcome. The graph answers one question for every piece of code: **does this trigger a
final outcome?** If yes, it's on a path. If no, it's infrastructure.

Your input is the enriched code reference index (symbols + indirect connections). Your
output is a graph where:
- **Entry points** are the left edge (where paths begin)
- **Final outcomes** are the right edge (where paths terminate)
- **Pathways** are the chains of symbols connecting entry to outcome
- **Fan-out points** are where one path splits into many

Every symbol in the index must either appear on at least one pathway or be classified
as infrastructure. Symbols with callers that appear on NO pathway are validation
failures — either the graph is incomplete or the code is dead.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `index_path`: Path to the enriched code-reference-index.json (with connections merged)
- `connections_path`: Path to the connections.json (from connection-hunter)
- `output_path`: Where to write the outcome graph
- `product_context`: Brief summary of what this product does
- `interview_answers`: Path to resolved interview answers (from prior runs, if any)

## Context Window Discipline

- **Process ONE entry point at a time.** Trace all its paths to outcomes, write them,
  move on.
- **Never load the full index into context.** Use Grep to find symbols by name, Read
  targeted entries.
- **Write after every completed entry point** (all its paths recorded).
- **Batch orphans for user interview** (max 10 per batch).

## Phase 1: Identify Entry Points

Entry points are where external input enters the system. They are the START of pathways.

### Entry Point Taxonomy

| Category | Detection Pattern | Example |
|----------|------------------|---------|
| **HTTP Route** | Route registrations (`app.get`, `@Get`, `[HttpGet]`) | `POST /api/orders` |
| **CLI Command** | Command definitions (`program.command(`, `@click.command`) | `cli migrate --run` |
| **Cron / Scheduled Job** | Schedule registrations (`cron(`, `@Scheduled`, `schedule.every`) | `0 2 * * *` (2am daily) |
| **UI Event Handler** | DOM event bindings (`onClick`, `@click`, `addEventListener`) | Button click, form submit |
| **Message Consumer** | Queue/topic consumers (`consume(`, `@SqsListener`, `consumer.run`) | Kafka consumer for `order-events` |
| **Webhook Receiver** | Inbound webhook routes (routes with `/webhook`, signature verification) | `POST /webhooks/stripe` |
| **IPC Handler** | IPC message handlers (`ipcMain.handle(`, `parentPort.on('message'`) | Electron main process handler |
| **Lifecycle Hook** | Application startup/shutdown hooks (`onModuleInit`, `ApplicationStarted`) | App initialization |
| **File Watcher** | Filesystem change handlers (`fs.watch`, `chokidar.on('change'`) | Config file reload |
| **System Signal** | OS signal handlers (`process.on('SIGTERM'`) | Graceful shutdown |
| **Timer / Interval** | Recurring timers (`setInterval`, `setTimeout` as trigger) | Heartbeat check every 30s |
| **WebSocket Handler** | WebSocket message handlers (`ws.on('message'`, `@SubscribeMessage`) | Real-time command processing |
| **Database Trigger** | DB-level triggers that invoke application code | `AFTER INSERT ON orders` |
| **Observable Source** | Root observables that originate from user/system input | User typing in search field |

**For each entry point, record:**
```json
{
  "id": "EP-001",
  "category": "http_route",
  "label": "POST /api/orders",
  "symbol": "OrderController.create",
  "file": "src/routes/orders.ts",
  "line": 34,
  "trigger": "User submits order via API",
  "authentication": "required | optional | none",
  "index_symbol_id": "ref to code-reference-index symbol"
}
```

### Detecting Entry Points from the Index

1. **Read the index statistics** to understand the codebase shape.
2. **Grep the index for route-type symbols** — these are explicit entry points.
3. **Grep the connections for listener/handler registrations** — IPC handlers,
   message consumers, webhook handlers, event listeners that are triggered externally.
4. **Grep the index for symbols with `called_by: []`** (nothing calls them internally)
   that are exported or registered. These MAY be entry points.
5. **Grep for framework-specific patterns** (cron decorators, lifecycle hooks, etc.).

## Phase 2: Identify Final Outcomes

Final outcomes are observable side effects — things the system does that are visible
outside the code boundary. They are the END of pathways.

### Final Outcome Taxonomy

| Category | Detection Pattern | Example |
|----------|------------------|---------|
| **Data Mutation** | DB write operations (`INSERT`, `UPDATE`, `DELETE`, `.save()`, `.create()`, `.update()`, `.destroy()`) | Order saved to database |
| **HTTP Response** | Response sent to client (`res.json(`, `res.send(`, `return Ok(`, `return Response(`) | 200 OK with order data |
| **Email / SMS / Push** | Notification dispatch (`sendEmail(`, `sendSMS(`, `pushNotification(`, `mailer.send(`) | Order confirmation email |
| **External API Call** | Outbound HTTP to third-party (`axios.post(`, `fetch(`, `httpClient.post(`, SDK method calls) | Stripe charge created |
| **File Written** | File system writes (`fs.writeFile(`, `File.write(`, `open(path, 'w')`) | Report exported to CSV |
| **Queue Message Published** | Message dispatched to queue/topic (`publish(`, `produce(`, `sendMessage(`) | Job enqueued for background processing |
| **WebSocket Message Sent** | Outbound WebSocket (`ws.send(`, `socket.emit(`, `io.to(room).emit(`) | Real-time update pushed to client |
| **Cache Mutation** | Cache write/invalidate (`cache.set(`, `cache.del(`, `Redis.set(`) | Session data cached |
| **Log Entry (Business)** | Business-meaningful logging (`auditLog.write(`, security event logging) | Audit trail entry recorded |
| **UI State Change** | DOM mutation, navigation, toast/modal display (`setState(`, `navigate(`, `toast(`, `render(`) | Search results displayed |
| **Process Control** | Process spawn/kill, service restart (`child_process.spawn(`, `process.exit(`) | Worker process restarted |
| **Event Emitted (Fan-out)** | Event emission that triggers other outcomes — NOT a final outcome itself but a FAN-OUT POINT | `emit('order.created')` → 4 listeners |

**Critical distinction on events:**
An `emit('order.created')` is NOT a final outcome. It's a **fan-out point** — the path
splits here into N paths (one per listener), and each listener's path continues until IT
reaches a final outcome. The graph must trace THROUGH the fan-out to each terminal outcome.

However, if an event is emitted to an EXTERNAL system (Kafka topic consumed by another
service, webhook to a third party), it IS a final outcome from this codebase's perspective,
because the outcome happens outside our code boundary.

**For each final outcome, record:**
```json
{
  "id": "FO-001",
  "category": "data_mutation",
  "label": "Order saved to database",
  "symbol": "OrderRepository.save",
  "file": "src/repositories/order.ts",
  "line": 67,
  "table_or_target": "orders",
  "operation": "INSERT",
  "index_symbol_id": "ref to code-reference-index symbol"
}
```

### Detecting Final Outcomes from the Index

1. **Grep the index for DB write symbols** — `.save()`, `.create()`, `.update()`,
   `.destroy()`, `.delete()`, raw SQL INSERT/UPDATE/DELETE.
2. **Grep for response-sending symbols** — `res.json`, `res.send`, `return Ok`.
3. **Grep for external call symbols** — HTTP client calls, SDK methods.
4. **Grep for notification symbols** — email, SMS, push notification.
5. **Grep for file write symbols** — `writeFile`, `createWriteStream`.
6. **Grep for message publish symbols** — queue/topic publishing.
7. **Grep the connections for event emissions** — classify each as fan-out
   (internal listeners exist) or final outcome (no internal listener = external).

## Phase 3: Trace Pathways

For each entry point, trace forward through the call graph to find all reachable
final outcomes. Each unique path from entry to outcome is a **pathway**.

### Tracing Algorithm

```
For each entry_point EP:
  Initialize: visited = {}, paths = []
  Call: trace(EP.symbol, [EP], visited, paths)

trace(current_symbol, path_so_far, visited, paths):
  If current_symbol is a final_outcome:
    Record path_so_far + [current_symbol] as a complete pathway
    Return

  If current_symbol in visited:
    Return (cycle detection)

  Mark current_symbol as visited

  For each symbol in current_symbol.calls:
    If symbol is a fan_out_point (event emission with internal listeners):
      For each listener of this event:
        trace(listener, path_so_far + [current_symbol, "FAN:" + event_name], visited.copy(), paths)
    Else:
      trace(symbol, path_so_far + [current_symbol], visited, paths)

  If current_symbol.calls is empty and current_symbol is NOT a final_outcome:
    Record current_symbol as a DEAD END (potential missing outcome or infrastructure)
```

### Path Recording

Each pathway is recorded as:
```json
{
  "id": "PW-001",
  "entry_point": "EP-001",
  "final_outcome": "FO-001",
  "steps": [
    {"symbol": "OrderController.create", "file": "src/routes/orders.ts", "line": 34, "type": "entry_point"},
    {"symbol": "authMiddleware", "file": "src/middleware/auth.ts", "line": 12, "type": "middleware"},
    {"symbol": "OrderService.processOrder", "file": "src/services/order.ts", "line": 89, "type": "logic"},
    {"symbol": "OrderValidator.validate", "file": "src/validators/order.ts", "line": 15, "type": "logic"},
    {"symbol": "PricingEngine.calculate", "file": "src/services/pricing.ts", "line": 42, "type": "logic"},
    {"symbol": "OrderRepository.save", "file": "src/repositories/order.ts", "line": 67, "type": "final_outcome"}
  ],
  "fan_outs": [],
  "source_maps": [
    {"step": 0, "index_ref": "symbol_id_123"},
    {"step": 1, "index_ref": "symbol_id_456"}
  ]
}
```

### Fan-Out Paths

When a path hits a fan-out point (event emission), it branches:
```json
{
  "id": "PW-002",
  "entry_point": "EP-001",
  "final_outcome": "FO-003",
  "steps": [
    {"symbol": "OrderController.create", "type": "entry_point"},
    {"symbol": "OrderService.processOrder", "type": "logic"},
    {"symbol": "emit('order.created')", "type": "fan_out", "event": "order.created"},
    {"symbol": "sendOrderConfirmation", "type": "listener", "event": "order.created"},
    {"symbol": "EmailService.send", "type": "final_outcome"}
  ],
  "fan_outs": [
    {"event": "order.created", "at_step": 2, "branch_count": 4, "this_branch": 1}
  ]
}
```

The same entry point (EP-001) produces MULTIPLE pathways — one for the direct DB save,
one for each event listener's outcome chain.

### Handling Infrastructure

Symbols that appear in the index but are NOT on any pathway:
- **Utility functions** (formatDate, parseInt, logger.debug): called from pathways but
  don't define the path structure. These are referenced BY paths but not path nodes.
- **Dead code**: symbols with callers=0 and not an entry point.
- **Internal helpers**: called only by other helpers, never reaching an outcome.

Record infrastructure separately:
```json
"infrastructure": [
  {
    "symbol": "formatCurrency",
    "file": "src/utils/format.ts",
    "line": 5,
    "caller_count": 23,
    "on_pathways": ["PW-001", "PW-005", "PW-012"],
    "classification": "utility"
  }
]
```

Infrastructure symbols appear in the `source_maps` of pathways that use them but are
NOT steps in the pathway itself. They're context for the reimplementor ("the legacy
system used this helper here") without being structural.

## Phase 4: Validate the Graph

### Validation Rules

1. **Every entry point must reach at least one final outcome.**
   - Entry points with no reachable outcome → flag as `orphan_entry_point`
   - These ALWAYS trigger a user interview (dead code or missing connection)

2. **Every final outcome must be reachable from at least one entry point.**
   - Outcomes with no incoming path → flag as `unreachable_outcome`
   - These ALWAYS trigger a user interview (dead code or missed entry point)

3. **Every indexed symbol with caller_count > 0 must appear on at least one pathway
   (as a step OR as infrastructure referenced by a pathway).**
   - Symbols with callers but no pathway → flag as `graph_gap`
   - Likely a missing indirect connection or undetected entry point

4. **No pathway should have more than 30 steps.**
   - Extremely long paths suggest the trace followed infrastructure chains
     (logging, error handling) rather than business logic. Review and prune.

5. **Fan-out points must have all branches traced.**
   - If an event has 4 listeners, there must be 4 fan-out paths (one per listener).
   - Missing branches → flag as `incomplete_fan_out`

### Validation Output

```json
"validation": {
  "entry_points_total": 45,
  "final_outcomes_total": 89,
  "pathways_total": 234,
  "infrastructure_symbols": 156,

  "orphan_entry_points": [
    {
      "id": "EP-023",
      "label": "GET /admin/debug/cache",
      "symbol": "DebugController.showCache",
      "observation": "Route exists but no final outcome is reachable. Handler reads cache and formats data but does not write, notify, or respond.",
      "question": "This route reads cache state but doesn't seem to produce an observable result. Is this a developer tool? Is there a response I missed? Or is this dead code?"
    }
  ],

  "unreachable_outcomes": [
    {
      "id": "FO-067",
      "label": "AuditLog INSERT",
      "symbol": "AuditLogger.write",
      "observation": "This writes to the audit_log table but no entry point traces to it. It's called from 3 places, but all callers are also unreachable.",
      "question": "The audit log write is disconnected from any user/system action I can trace. Is there an external trigger (cron job outside the repo, database trigger, external service) that initiates audit logging?"
    }
  ],

  "graph_gaps": [
    {
      "symbol": "NotificationRouter.dispatch",
      "caller_count": 5,
      "observation": "Called from 5 places but none of those callers are on any pathway.",
      "likely_cause": "Missing entry point — the callers may be triggered by an undetected event or scheduled job."
    }
  ],

  "coverage": {
    "symbols_on_pathways": 423,
    "symbols_as_infrastructure": 156,
    "symbols_unclassified": 12,
    "index_coverage_pct": 98.0
  }
}
```

## Phase 5: User Interview for Validation Failures

Every orphan entry point and unreachable outcome MUST be presented to the user.
Do not silently classify them as dead code.

**For orphan entry points:**
```
EP-023: GET /admin/debug/cache
This route reads from the cache and formats data, but I can't find any observable
outcome (no response sent, no data written, no notification).

Options:
  [Dead code]    — Not used, safe to exclude from rebuild
  [External]     — Something outside this codebase calls/uses this
  [Missing link] — Let me explain what this connects to
```

**For unreachable outcomes:**
```
FO-067: Audit log INSERT (AuditLogger.write)
This writes to audit_log but I can't trace any user action or system event that
triggers it. The 3 call sites are themselves unreachable.

Options:
  [Dead code]    — Legacy feature, not active
  [External trigger] — A cron job / external service / DB trigger initiates this
  [Missing link]     — Let me explain the trigger
```

**For graph gaps:**
```
NotificationRouter.dispatch is called from 5 places but none of them trace to
a user action. The callers are: [list].

Options:
  [Event-driven] — These are triggered by an event I should look for
  [Scheduled]    — A timer or cron job triggers this chain
  [External]     — An external service calls into this
  [Explain]      — Let me describe the trigger
```

After user responses, re-trace affected pathways and update the graph.

## Output Schema

```json
{
  "generated_at": "ISO-8601",
  "repo": "repo-name",
  "product": "product name from interview",

  "entry_points": [ ... ],
  "final_outcomes": [ ... ],
  "pathways": [ ... ],
  "fan_out_points": [
    {
      "event": "order.created",
      "location": {"file": "src/services/order.ts", "line": 142},
      "branch_count": 4,
      "pathway_ids": ["PW-002", "PW-003", "PW-004", "PW-005"]
    }
  ],
  "infrastructure": [ ... ],

  "validation": { ... },

  "statistics": {
    "entry_points": 45,
    "final_outcomes": 89,
    "pathways": 234,
    "fan_out_points": 12,
    "avg_pathway_length": 6.3,
    "max_pathway_length": 18,
    "infrastructure_symbols": 156,
    "dead_code_symbols": 8,
    "index_coverage_pct": 98.0
  }
}
```

## Source Map Integration

Every step in every pathway carries a reference back to the code-reference-index
symbol ID. This is the **source map** — a lightweight, updatable pointer from the
graph back to the exact code location.

When code changes:
1. Re-index changed files (update code-reference-index)
2. Find affected symbols in the index
3. Find pathways containing those symbols
4. Re-trace affected pathways only
5. Flag features (derived downstream) whose pathways changed

The graph never embeds code — it only references index entries. This is what makes
incremental updates possible without regenerating the entire inventory.
