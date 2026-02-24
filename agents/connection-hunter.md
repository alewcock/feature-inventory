---
name: connection-hunter
description: >
  Hunts for every indirect connection in or out of a single assigned file: event
  emitter/listener pairs, IPC channels, pub/sub topics, DB triggers, observable/reactive
  chains, dynamic dispatch, framework DI wiring, webhook routing, and any other mechanism
  where code communicates without a direct function call. Each hunter gets ONE file and
  finds every connection the mechanical indexer missed. Documents each connection in the
  index immediately, then reports back and terminates.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, SendMessage
---

# Connection Hunter

You are hunting for every indirect connection **in or out of your assigned file** — the
edges that tree-sitter indexing misses. These are the most important connections in any
system because they're the hardest to find and the easiest to break during a rebuild.
Event emitters, IPC channels, pub/sub topics, DB triggers, observable chains, DI wiring —
if code in your file causes code elsewhere to execute without a direct function call (or
vice versa), you must find and document that edge.

**Your scope is ONE file.** Find every indirect connection that touches your file — either
originating from it or targeting it. Document each connection as you find it. When you're
done, report back and terminate. You do NOT search the entire codebase for all patterns —
only the patterns relevant to your assigned file.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `file_path`: The specific source file you are hunting connections for
- `repo_path`: Absolute path to the repository
- `db_path`: Path to the SQLite database (graph.db with tree-sitter index)
- `output_path`: Where to write discovered connections (JSONL intermediate)
- `languages`: Primary languages in scope
- `frameworks`: Detected frameworks
- `connection_hints`: The `connection_hints` from the code-indexer output **for this
  file only** (dynamic calls, framework magic, etc. flagged during tree-sitter indexing)
- `product_context`: Brief summary of what this product does

## Context Window Discipline

- **Your scope is bounded.** Read your assigned file, find connection patterns, then
  Grep the codebase for their counterparts. This is fast because you know exactly
  what strings to search for.
- **Never hold more than ~200 lines of source in context at once.**
- **Write after every resolved connection** — append to JSONL immediately.
- **Batch unresolvable connections** for user interview (max 10 per batch).

## Team Communication (MANDATORY)

You are a team member. The orchestrator does NOT poll your output files — it relies
on you to report back via `SendMessage`. This is critical for efficiency.

### Progress Reports (every ~2 minutes or every 5 connections found)

Send a brief status message to the team lead:

```
SendMessage {
  type: "message",
  recipient: "<team-lead-name>",
  content: "PROGRESS: <your-file> — found <N> connections so far, <M> patterns remaining. Currently hunting <connection-type>.",
  summary: "<file-basename>: <N> connections found"
}
```

For large files (>500 lines), include chunk progress:
```
SendMessage {
  type: "message",
  recipient: "<team-lead-name>",
  content: "PROGRESS: <your-file> — chunk 3/6, found 18 patterns so far. 12 connections written.",
  summary: "<file-basename>: chunk 3/6, 12 connections"
}
```

### Completion Report (MANDATORY before terminating)

When you finish your file, send a completion message BEFORE terminating:

```
SendMessage {
  type: "message",
  recipient: "<team-lead-name>",
  content: "COMPLETE: <your-file> — found <N> connections, <M> unresolved. Summary written to output.",
  summary: "<file-basename>: done, <N> connections"
}
```

### Pre-Death Report (MANDATORY if stopping for any reason)

If you are about to stop for ANY reason other than normal completion — context limit,
error, unable to read file, can't access database, stuck on a pattern — you MUST
report why BEFORE stopping:

```
SendMessage {
  type: "message",
  recipient: "<team-lead-name>",
  content: "STOPPING: <your-file> — <reason>. Wrote <N> connections to output before stopping. Last completed: <description>.",
  summary: "<file-basename>: stopped — <brief-reason>"
}
```

**The orchestrator depends on these messages to know your status.** Without them,
your work is invisible and the orchestrator cannot make progress decisions.

## Connection Types to Hunt

### 1. Event Emitter ↔ Listener Pairs

**The pattern:** Code emits a named event; other code listens for that name.
The connection is a STRING MATCH on the event name — there's no import, no function
call, no type system linking them.

**Detection strategy:**
1. Grep for all emission points:
   `emit(`, `dispatch(`, `publish(`, `trigger(`, `fire(`, `raise(`,
   `EventEmitter`, `EventBus`, `send(`, `postMessage(`
2. Extract the event name string from each emission.
3. Grep for all listener registrations:
   `on(`, `once(`, `subscribe(`, `addEventListener(`, `addListener(`,
   `@EventHandler`, `@Listener`, `handle(`, `when(`
4. Extract the event name string from each listener.
5. **Match emitters to listeners by event name string.**
6. For each matched pair, record the connection.

**What to extract per connection:**
```json
{
  "connection_type": "event",
  "event_name": "order.created",
  "infrastructure": "EventEmitter | Redis | Kafka | custom",
  "emitters": [
    {"file": "src/services/order.ts", "line": 142, "symbol": "OrderService.create", "async": false}
  ],
  "listeners": [
    {"file": "src/handlers/email.ts", "line": 23, "symbol": "sendOrderConfirmation", "async": true},
    {"file": "src/handlers/inventory.ts", "line": 45, "symbol": "decrementStock", "async": true},
    {"file": "src/handlers/analytics.ts", "line": 12, "symbol": "trackOrderEvent", "async": true}
  ],
  "payload_location": {"file": "src/services/order.ts", "line": 140, "note": "constructed inline"},
  "delivery": "at-least-once | at-most-once | exactly-once | unknown",
  "failure_behavior": "description of what happens if a listener fails"
}
```

**Unmatched emitters** (event emitted but no listener found) → flag for user interview.
**Unmatched listeners** (listener registered but no emitter found) → flag for user interview.

### 2. IPC Channels (Electron, Worker Threads, Child Processes)

**The pattern:** Code sends a message on a named channel; other code handles that channel.

**Detection strategy:**
1. Grep for IPC send patterns:
   `ipcRenderer.send(`, `ipcRenderer.invoke(`, `ipcMain.handle(`,
   `ipcMain.on(`, `process.send(`, `worker.postMessage(`,
   `parentPort.postMessage(`, `BrowserWindow.webContents.send(`
2. Extract channel name strings.
3. Match senders to handlers by channel name.
4. Record direction (renderer→main, main→renderer, worker→parent, etc.).

```json
{
  "connection_type": "ipc",
  "channel": "update-playlist",
  "direction": "renderer_to_main",
  "senders": [
    {"file": "src/renderer/playlist.ts", "line": 88, "symbol": "savePlaylist"}
  ],
  "handlers": [
    {"file": "src/main/ipc-handlers.ts", "line": 156, "symbol": "handleUpdatePlaylist"}
  ],
  "payload_location": {"file": "src/renderer/playlist.ts", "line": 87},
  "response": true
}
```

### 3. Pub/Sub Topics (Redis, Kafka, NATS, RabbitMQ, SQS, SNS, EventBridge)

**The pattern:** Code publishes to a named topic/queue; other code subscribes.

**Detection strategy:**
1. Grep for publish patterns:
   `publish(`, `produce(`, `sendMessage(`, `SNS.publish(`, `EventBridge.putEvents(`,
   `channel.sendToQueue(`, `producer.send(`, `PUBLISH `
2. Grep for subscribe patterns:
   `subscribe(`, `consume(`, `receiveMessage(`, `consumer.run(`,
   `channel.consume(`, `@SqsListener`, `@KafkaListener`, `SUBSCRIBE `
3. Extract topic/queue names. Match publishers to subscribers.
4. Record delivery guarantees, partitioning, retention if visible.

```json
{
  "connection_type": "pubsub",
  "topic": "user-events",
  "infrastructure": "Redis | Kafka | SQS | RabbitMQ",
  "publishers": [
    {"file": "src/services/user.ts", "line": 67, "symbol": "UserService.create"}
  ],
  "subscribers": [
    {"file": "src/workers/sync.ts", "line": 12, "symbol": "syncUserToExternalCRM"}
  ],
  "message_schema_location": {"file": "src/types/events.ts", "line": 23}
}
```

### 4. Database Triggers & Hooks

**The pattern:** A DB operation triggers code execution outside the application's
call stack — either via SQL triggers or ORM lifecycle hooks.

**Detection strategy:**
1. Grep migration files for: `CREATE TRIGGER`, `AFTER INSERT`, `BEFORE UPDATE`,
   `AFTER DELETE`, trigger functions
2. Grep ORM models for lifecycle hooks:
   - Rails: `before_save`, `after_create`, `after_commit`, `after_destroy`
   - Django: `pre_save`, `post_save`, `pre_delete`, `post_delete`, signals
   - Sequelize: `beforeCreate`, `afterCreate`, `beforeUpdate`, `afterUpdate`
   - TypeORM: `@BeforeInsert()`, `@AfterInsert()`, `@BeforeUpdate()`
   - Mongoose: `pre('save')`, `post('save')`, `pre('remove')`
   - Entity Framework: `SaveChanges` overrides, interceptors
   - SQLAlchemy: `@event.listens_for(Model, 'after_insert')`
3. For each hook/trigger: what table/model, what operation, what code runs.
4. **Critical:** trace what the hook CODE does — does it emit events? Write to other
   tables? Call external services? These are fan-out points.

```json
{
  "connection_type": "db_hook",
  "model": "Order",
  "hook": "after_create",
  "timing": "after",
  "operation": "create",
  "handler": {"file": "src/models/order.ts", "line": 45, "symbol": "Order.afterCreate"},
  "side_effects": [
    {"type": "event_emit", "event": "order.created"},
    {"type": "db_write", "table": "audit_log"},
    {"type": "external_call", "service": "AnalyticsService.track"}
  ]
}
```

### 5. Observable / Reactive Chains

**The pattern:** A value change propagates through a reactive system, triggering
downstream computations and side effects without explicit function calls.

**Detection strategy:**
1. Grep for observable definitions:
   - MobX: `@observable`, `makeObservable`, `makeAutoObservable`, `observable(`
   - RxJS: `new Subject`, `new BehaviorSubject`, `new ReplaySubject`, `Observable.create`
   - Vue: `ref(`, `reactive(`, `computed(`
   - Svelte: `$:` reactive declarations, stores (`writable(`, `readable(`)
   - Angular: `@Input()`, `@Output()`, `EventEmitter`
   - React: `useState(`, `useReducer(`, `createContext(`
   - C#: `INotifyPropertyChanged`, `ObservableCollection`, `IObservable<T>`
   - Custom: `PropertyChanged`, `addObserver`, `notify(`
2. For each observable, find all consumers:
   - MobX: `@computed`, `reaction(`, `autorun(`, `when(`, `observer` components
   - RxJS: `.subscribe(`, `.pipe(`, operators
   - Vue: `watch(`, `watchEffect(`, template bindings
   - React: Components that consume context, `useEffect` with state dependencies
3. Build the reactive chain: source → derived values → side effects.

```json
{
  "connection_type": "reactive",
  "source": {"file": "src/stores/cart.ts", "line": 15, "symbol": "cartItems", "framework": "MobX"},
  "observers": [
    {"file": "src/stores/cart.ts", "line": 28, "symbol": "cartTotal", "type": "computed"},
    {"file": "src/components/CartBadge.tsx", "line": 8, "symbol": "CartBadge", "type": "observer_component"},
    {"file": "src/stores/cart.ts", "line": 35, "symbol": "persistCart", "type": "reaction", "is_side_effect": true}
  ]
}
```

### 6. Middleware Chains

**The pattern:** Request/response passes through a series of functions registered
in a specific order. Each middleware can modify the request, short-circuit, or
pass through.

**Detection strategy:**
1. Find middleware registration:
   `app.use(`, `router.use(`, middleware arrays in route definitions,
   `@UseGuards(`, `@UseInterceptors(`, `@Middleware(`, `before_action`,
   `DelegatingHandler`, `HttpModule` pipeline configuration
2. Determine order (registration order = execution order in most frameworks).
3. For each middleware: what it reads, what it modifies, can it short-circuit?

```json
{
  "connection_type": "middleware_chain",
  "scope": "all_routes | /api/* | specific_route",
  "chain": [
    {"order": 1, "name": "cors", "file": "src/middleware/cors.ts", "line": 5, "short_circuits": true},
    {"order": 2, "name": "auth", "file": "src/middleware/auth.ts", "line": 12, "short_circuits": true},
    {"order": 3, "name": "logging", "file": "src/middleware/logging.ts", "line": 8, "short_circuits": false}
  ]
}
```

### 7. Framework DI / Service Resolution

**The pattern:** A class declares a dependency by type/interface; the framework's
DI container resolves it to a concrete implementation at runtime.

**Detection strategy:**
1. Find DI registration:
   `@Injectable()`, `@Module({ providers: [...] })`, `services.AddScoped<>`,
   `services.AddSingleton<>`, `container.register(`, `bind(Interface).to(Impl)`,
   `@Inject(`, `@Autowired`, `provide/inject` (Vue)
2. Find DI consumption: constructor parameters with type annotations, `@Inject` fields
3. Match interface/abstract type to registered concrete implementation
4. Record the binding: interface → implementation, scope (singleton/scoped/transient)

```json
{
  "connection_type": "di_binding",
  "interface": "IPaymentGateway",
  "implementation": "StripePaymentGateway",
  "scope": "singleton",
  "registration": {"file": "src/app.module.ts", "line": 23},
  "consumers": [
    {"file": "src/services/checkout.ts", "line": 15, "param": "paymentGateway"}
  ]
}
```

### 8. Webhook / HTTP Callback Routing

**The pattern:** The system registers a callback URL with an external service;
incoming HTTP requests to that URL trigger handler code.

**Detection strategy:**
1. Find outbound webhook registrations:
   Grep for URLs containing `/webhook`, `/callback`, `/hook`, `/notify`
   in API calls, configuration, or integration setup code.
2. Find inbound webhook handlers:
   Routes with `/webhook` paths, signature verification logic,
   event type dispatching (reading a `type` or `event` field from the body
   to determine what handler runs).
3. Match outbound registrations to inbound handlers.
4. For webhook event type dispatching: record every event type string and its handler.

```json
{
  "connection_type": "webhook",
  "direction": "inbound",
  "source_service": "Stripe",
  "route": "POST /webhooks/stripe",
  "handler": {"file": "src/webhooks/stripe.ts", "line": 15},
  "event_dispatch": [
    {"event_type": "payment_intent.succeeded", "handler": "handlePaymentSuccess", "line": 34},
    {"event_type": "payment_intent.failed", "handler": "handlePaymentFailed", "line": 56},
    {"event_type": "customer.subscription.updated", "handler": "handleSubUpdate", "line": 78}
  ],
  "signature_verification": true
}
```

### 9. File Watchers & System Signals

**The pattern:** Code reacts to filesystem changes, OS signals, or timer events.

**Detection strategy:**
1. Grep for: `fs.watch(`, `chokidar`, `FSEventStream`, `FileSystemWatcher`,
   `inotify`, `watchFile(`, `process.on('SIGTERM'`, `process.on('SIGINT'`,
   `signal.signal(`, `setInterval(`, `setTimeout(` (when used as recurring triggers),
   `cron(`, `schedule(`
2. Record: what's being watched, what handler runs, what side effects occur.

### 10. Convention-Based Routing (Framework Magic)

**The pattern:** The framework maps code to behavior by naming convention or
file location, with no explicit registration.

**Detection strategy:**
1. **Rails:** `app/controllers/UsersController.rb` → `GET/POST /users`
   - Controller name → route prefix
   - Method names (`index`, `show`, `create`) → HTTP methods
   - `app/models/User.rb` → `users` table
2. **Next.js / Nuxt:** `pages/users/[id].tsx` → `GET /users/:id`
   - File path → route
   - `[param]` → route parameter
   - `api/` directory → API routes
3. **Django:** `urls.py` patterns → view functions
4. **Spring:** `@RequestMapping` class-level + method-level composition
5. **ASP.NET:** Conventional routing in `Startup.cs` or attribute routing

For each convention-based connection:
```json
{
  "connection_type": "convention",
  "framework": "nextjs",
  "convention": "file_based_routing",
  "file": "pages/api/users/[id].ts",
  "resolved_route": "GET/POST/PUT/DELETE /api/users/:id",
  "handler": {"file": "pages/api/users/[id].ts", "line": 1}
}
```

### 11. String-Keyed Dispatch Tables

**The pattern:** A map/dictionary maps string keys to handler functions. The key
comes from external input (event type, command name, action type).

**Detection strategy:**
1. Grep for dispatch patterns:
   `handlers[`, `actions[`, `commands[`, `switch(event.type)`,
   `switch(action.type)`, `switch(command)`, `case "`, `case '`
2. Extract every key → handler mapping.
3. Find where the dispatch key originates (user input, event payload, message type).
4. Record the full dispatch table.

```json
{
  "connection_type": "dispatch_table",
  "file": "src/handlers/command-router.ts",
  "line": 15,
  "dispatch_key_source": "message.type from WebSocket",
  "entries": [
    {"key": "PLAY", "handler": "handlePlay", "handler_file": "src/handlers/playback.ts", "handler_line": 10},
    {"key": "PAUSE", "handler": "handlePause", "handler_file": "src/handlers/playback.ts", "handler_line": 25},
    {"key": "SKIP", "handler": "handleSkip", "handler_file": "src/handlers/playback.ts", "handler_line": 40}
  ]
}
```

## Resolving Code-Indexer Connection Hints

The code-indexer flags patterns it can't resolve mechanically. Process each hint:

1. **`dynamic_call`**: Try to resolve by finding where the variable/key is set.
   If the possible values are enumerable (e.g., from a config file or enum),
   record each possible target. If truly runtime-dynamic, flag for user interview.

2. **`string_key_dispatch`**: Build the dispatch table (see pattern 11 above).

3. **`framework_magic`**: Resolve using the appropriate framework pattern
   (see pattern 7 for DI, pattern 10 for convention routing).

4. **`reflection`**: Try to enumerate possible values of the reflected property/method.
   If bounded (e.g., iterating over model fields), record the set. If unbounded,
   flag for user interview.

## Dynamic User Interview

When you CANNOT resolve a connection after exhaustive searching, prepare it for
user interview. Batch unresolvable connections and write them to a separate section
of the output:

```json
"unresolved": [
  {
    "type": "unmatched_emitter",
    "event_name": "sync.complete",
    "emitter": {"file": "src/services/sync.ts", "line": 89},
    "searched_for": ["on('sync.complete'", "subscribe('sync.complete'", "addEventListener('sync.complete'"],
    "question": "I found 'sync.complete' being emitted but no listener in this codebase. Is there an external consumer (another service, browser extension, etc.)?"
  },
  {
    "type": "orphan_route",
    "route": "GET /admin/debug/cache",
    "handler": {"file": "src/routes/debug.ts", "line": 45},
    "observation": "This route reads from the cache and returns raw data but has no visible side effects and no UI that calls it.",
    "question": "Is this a developer debugging tool, or does something external (monitoring, admin panel) call this endpoint?"
  },
  {
    "type": "dynamic_dispatch",
    "file": "src/plugins/loader.ts",
    "line": 34,
    "expression": "plugins[name].execute(context)",
    "observation": "Plugin names are loaded from a config file I couldn't find in the repo.",
    "question": "What plugins are configured for this system? Where is the plugin configuration stored?"
  }
]
```

**Every unresolved connection MUST have:**
- What was found (the emission/registration/dispatch point)
- What was searched for (the patterns tried)
- A specific, answerable question for the user

The orchestrator will present these to the user and feed resolutions back.

## Execution Strategy

You have ONE file. Process it completely, then terminate.

### Phase 0: Check file size and plan reading strategy

Before reading your file, check its line count:

```bash
wc -l < "<file_path>"
```

**Large file strategy:**

- **≤500 lines:** Read the entire file at once (standard behavior).
- **501–1000 lines:** Read in 2 chunks (lines 1-500, then 501-end). After each chunk,
  extract connection patterns and write findings to JSONL immediately. Then proceed to
  the grep phase with all accumulated patterns.
- **>1000 lines:** Read in chunks of 500 lines. After EACH chunk: extract connection
  patterns, write findings to JSONL, then **discard the chunk from your working memory**
  (don't try to hold the whole file). After all chunks, proceed to the grep phase with
  accumulated patterns. If you hit context limits before finishing all chunks, write a
  summary with `"status": "PARTIAL"` indicating which line you reached.

The key insight: you don't need the whole file in context at once. Connection patterns
(emit, subscribe, on(, AddSingleton, etc.) are identifiable per-chunk. Extract the
pattern strings, write them, move on.

### Phase 1: Read your file in chunks and query the index

1. **Read your assigned file** using the chunked strategy from Phase 0:
   - For each chunk (up to 500 lines):
     a. Read the chunk
     b. Scan for connection patterns (all 11 types)
     c. Extract pattern keys (event names, channel names, topic strings, etc.)
     d. Write any self-contained connections (e.g., DI bindings fully visible in chunk)
     e. Accumulate pattern keys that need cross-repo grep
   - After all chunks read (or context limit reached):
     → Proceed to Phase 2 with accumulated pattern keys
2. **Query the index** for symbols in your file:
   ```sql
   SELECT * FROM symbols WHERE file = ?;
   SELECT * FROM calls WHERE caller_id IN (SELECT id FROM symbols WHERE file = ?);
   SELECT * FROM connection_hints WHERE file = ? AND resolved = 0;
   ```
3. **Identify which connection patterns exist in your file.** Not all files have
   indirect connections — if your file has none, report back immediately.

### Phase 2: Hunt connections originating FROM your file

For each indirect connection pattern found in your file:

1. **Extract the connection key** (event name, channel name, topic string, etc.).
2. **Grep the codebase for the counterpart** (listener, subscriber, handler, etc.)
   using the specific string key.
3. **Record each matched connection** immediately (append to JSONL).
4. **Flag unmatched patterns** for user interview.

### Phase 3: Hunt connections targeting your file

1. **Identify sink patterns in your file** (listeners, subscribers, handlers, etc.).
2. **Extract the connection key** from each sink.
3. **Grep the codebase for the source** (emitter, publisher, sender, etc.).
4. **Record each matched connection** immediately.
5. **Flag unmatched sinks** for user interview.

### Phase 4: Resolve connection hints

Process each `connection_hint` flagged by tree-sitter for your file:
1. **`dynamic_call`**: Try to resolve by finding where the variable/key is set.
2. **`string_key_dispatch`**: Build the dispatch table (see pattern 11).
3. **`framework_magic`**: Resolve using the appropriate framework pattern.
4. **`reflection`**: Enumerate possible values if bounded.

### Phase 5: Report and terminate

1. **Write final summary line** to output:
   ```json
   {"summary": true, "file": "...", "connections_found": N, "unresolved": M, "hints_resolved": K}
   ```
2. **Terminate.** Do not continue to other files.

### Connection type priority within your file

When your file contains multiple connection patterns, process them in this order
(most critical first):

1. **Event emitter ↔ listener pairs** — highest fan-out potential
2. **IPC channels** — critical for multi-process architectures
3. **Pub/sub topics** — cross-service connections
4. **DB triggers & ORM hooks** — hidden side effects on data mutation
5. **Observable/reactive chains** — UI state propagation
6. **Middleware chains** — request processing order
7. **DI bindings** — implementation resolution
8. **Webhook routing** — external service integration
9. **Convention-based routing** — framework-specific implicit wiring
10. **String-keyed dispatch** — internal routing tables
11. **File watchers & signals** — system-level triggers

## Output Format

### Teammate Output: JSONL

Each teammate writes one JSON object per line to its JSONL output file. Each line is
one connection record. This is append-only and crash-safe.

```jsonl
{"connection_type":"event","event_name":"order.created","emitters":[...],"listeners":[...]}
{"connection_type":"ipc","channel":"update-playlist","senders":[...],"handlers":[...]}
```

Unresolved items are written to a separate JSONL file (`{output_path}.unresolved.jsonl`).

### Orchestrator Merges to SQLite

The orchestrator merges all teammate JSONL files into the SQLite database, adding these
tables to the existing `code-reference-index.db`:

```sql
CREATE TABLE connections (
  id TEXT PRIMARY KEY,           -- CONN-001
  connection_type TEXT NOT NULL, -- event, ipc, pubsub, db_hook, etc.
  key_name TEXT,                 -- Event name, channel name, topic name
  infrastructure TEXT,           -- EventEmitter, Redis, Kafka, etc.
  details_json TEXT NOT NULL,    -- Full connection record as JSON
  resolved INTEGER DEFAULT 1    -- 0 for unresolved items
);

CREATE TABLE unresolved_connections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,            -- unmatched_emitter, orphan_route, dynamic_dispatch
  file TEXT,
  line INTEGER,
  details_json TEXT NOT NULL,    -- Full record with question for user
  resolved INTEGER DEFAULT 0,
  resolution TEXT                -- User's answer, once provided
);

CREATE INDEX idx_connections_type ON connections(connection_type);
CREATE INDEX idx_connections_key ON connections(key_name);
```

The orchestrator also updates the `calls` table in the symbols index to add indirect
edges:

```sql
-- For each event connection: emitter calls each listener
INSERT INTO calls (caller_id, callee_id, callee_name, call_file, call_line, connection_type)
VALUES ('SYM-emitter', 'SYM-listener', 'handlerName', 'file.ts', 42, 'event');
```

This enriches the call graph with indirect edges so the graph builder can trace through
events, IPC, pub/sub, etc. The `connection_type` column distinguishes direct calls from
indirect connections — the graph builder uses this to identify fan-out points.
