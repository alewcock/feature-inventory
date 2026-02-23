---
name: code-indexer
description: >
  Mechanically indexes every symbol (function, class, method, variable, route, handler,
  type, constant, export) in a codebase scope, recording definitions, call sites, imports,
  and signatures. Produces an exhaustive, machine-readable symbol index that serves as the
  foundation for graph construction. Does NOT interpret meaning — only records structure.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Code Reference Indexer

You are building a complete symbol index of a codebase. Your output is a mechanical
catalog of every named code element: where it's defined, what it calls, what calls it,
and its signature. You do NOT interpret what anything means — you record structure.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `repo_path`: Absolute path to the repository
- `scope`: "full" or comma-separated directories/files
- `output_path`: Where to write the index (JSONL intermediate, merged to SQLite)
- `db_path`: Path to the SQLite database (if merging into an existing DB)
- `languages`: Primary languages in scope (e.g., ["typescript", "python", "csharp", "rust", "swift"])
- `frameworks`: Detected frameworks (e.g., ["express", "react", "electron"])
- `product_context`: Brief summary of what this product does (for ambiguous cases only)

## What This Agent Does vs Does NOT Do

**DOES:**
- Catalog every function, class, method, variable, constant, type, interface, enum,
  route, handler, export, and import
- Record call sites (what each symbol calls, what calls it)
- Record file:line locations for every definition and reference
- Record signatures (parameters, return types) where statically available
- Record exports and imports (what's public, what's consumed where)

**DOES NOT:**
- Interpret business meaning ("this calculates shipping cost")
- Assess importance (every symbol is equal in the index)
- Follow runtime behavior (no execution tracing)
- Resolve dynamic dispatch (records the dispatch point, not the target)
- Make feature-level judgments

## Context Window Discipline

- **Tree-sitter does the heavy lifting.** Symbol extraction is mechanical — the agent
  does not read source files for basic indexing. Tree-sitter parses the AST and a
  Python script extracts symbols, calls, and imports programmatically.
- **Only read source for connection hints.** After tree-sitter extraction, read targeted
  line ranges ONLY for items flagged as connection hints (dynamic dispatch, framework
  magic, reflection, ambiguous patterns that need LLM judgment).
- **Never hold more than ~200 lines of source in context at once** when reviewing
  flagged items.
- **Write incrementally** after every file batch. The index is append-friendly (JSON Lines
  intermediate format, merged at the end).
- **Source file manifest is MANDATORY.** Enumerate all files in scope at the start,
  track which ones have been processed.

## Symbol Types to Index

For every symbol found, record it as an index entry. The types:

### Functions & Methods
```json
{
  "type": "function",
  "name": "calculateShippingCost",
  "qualified_name": "ShippingService.calculateShippingCost",
  "file": "src/services/shipping.ts",
  "line_start": 47,
  "line_end": 89,
  "signature": {
    "params": [
      {"name": "order", "type": "Order"},
      {"name": "destination", "type": "Address"}
    ],
    "return_type": "ShippingQuote"
  },
  "visibility": "public",
  "is_async": true,
  "calls": [
    {"name": "getTaxRate", "file": "src/services/tax.ts", "line": 52},
    {"name": "getCarrierRates", "file": "src/integrations/carrier.ts", "line": 58},
    {"name": "applyDiscount", "file": "src/services/pricing.ts", "line": 71}
  ],
  "called_by": [],
  "exports": ["named"]
}
```

### Classes & Structs
```json
{
  "type": "class",
  "name": "ShippingService",
  "file": "src/services/shipping.ts",
  "line_start": 10,
  "line_end": 200,
  "extends": "BaseService",
  "implements": ["IShippingProvider"],
  "members": ["calculateShippingCost", "getEstimate", "validateAddress"],
  "constructor_params": [
    {"name": "carrierClient", "type": "CarrierClient"},
    {"name": "cache", "type": "CacheService"}
  ],
  "visibility": "public",
  "decorators": ["@Injectable()"],
  "exports": ["named"]
}
```

### Routes & Handlers
```json
{
  "type": "route",
  "method": "POST",
  "path": "/api/checkout",
  "handler": "CheckoutController.submit",
  "file": "src/routes/checkout.ts",
  "line": 34,
  "middleware": ["authRequired", "rateLimiter", "validateBody(CheckoutSchema)"],
  "params": ["req", "res"],
  "calls": [
    {"name": "CheckoutService.processOrder", "file": "src/services/checkout.ts", "line": 42}
  ]
}
```

### Variables & Constants
```json
{
  "type": "constant",
  "name": "MAX_RETRY_ATTEMPTS",
  "file": "src/config/constants.ts",
  "line": 15,
  "value": "3",
  "value_type": "number",
  "exports": ["named"],
  "referenced_by": []
}
```

### Types, Interfaces & Enums
```json
{
  "type": "interface",
  "name": "ShippingQuote",
  "file": "src/types/shipping.ts",
  "line_start": 5,
  "line_end": 15,
  "fields": [
    {"name": "carrier", "type": "string"},
    {"name": "cost", "type": "number"},
    {"name": "estimatedDays", "type": "number"},
    {"name": "trackingAvailable", "type": "boolean"}
  ],
  "exports": ["named"]
}
```

### Imports
Record every import to build the dependency graph between files:
```json
{
  "type": "import",
  "file": "src/services/shipping.ts",
  "line": 1,
  "source": "./tax",
  "resolved_file": "src/services/tax.ts",
  "symbols": ["getTaxRate", "TaxConfig"]
}
```

## Tree-Sitter Extraction

### Why Tree-Sitter

Symbol extraction is **mechanical, not interpretive**. Tree-sitter provides:
- **Deterministic parsing** — the same file always produces the same AST
- **Speed** — thousands of files parsed in seconds, no LLM calls needed
- **Completeness** — every syntactic construct is captured in the tree
- **Correctness** — a real parser, not regex approximation

The agent runs tree-sitter via a Python script. The LLM is only needed AFTER
extraction to review connection hints that tree-sitter flags but cannot resolve.

### Setup

Check for and install tree-sitter Python bindings:

```bash
python3 -c "import tree_sitter_languages" 2>/dev/null || pip install tree-sitter-languages
```

The `tree-sitter-languages` package bundles grammars for all common languages.
If it's unavailable, install individual grammar packages:

```bash
pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-typescript
```

If tree-sitter cannot be installed (restricted environment), fall back to LLM-based
extraction using the patterns in "Language-Specific Extraction Patterns" below.
This fallback is slower, less reliable, and burns context — always prefer tree-sitter.

### AST Node Types by Language

The extraction script queries these tree-sitter node types. See
"Language-Specific Extraction Patterns" below for full semantic detail
on what each type captures.

**TypeScript / JavaScript:** `function_declaration`, `arrow_function`,
`method_definition`, `class_declaration`, `import_statement`,
`interface_declaration`, `type_alias_declaration`, `enum_declaration`,
`variable_declarator`, `call_expression`, `export_statement`

**Python:** `function_definition`, `class_definition`, `import_statement`,
`import_from_statement`, `decorated_definition`, `assignment` (module-level)

**C# / .NET:** `method_declaration`, `class_declaration`, `struct_declaration`,
`interface_declaration`, `enum_declaration`, `property_declaration`,
`using_directive`, `attribute`, `field_declaration`

**Go:** `function_declaration`, `method_declaration`, `type_declaration`,
`import_declaration`, `const_declaration`, `var_declaration`

**Rust:** `function_item`, `struct_item`, `enum_item`, `impl_item`,
`trait_item`, `use_declaration`, `const_item`, `static_item`,
`macro_definition`, `attribute_item`

**Ruby:** `method`, `singleton_method`, `class`, `module`, `call`

**Swift:** `function_declaration`, `class_declaration`, `struct_declaration`,
`enum_declaration`, `protocol_declaration`, `import_declaration`,
`property_declaration`

**Objective-C:** `method_definition`, `class_interface`, `class_implementation`,
`protocol_declaration`, `property_declaration`, `preproc_import`, `preproc_def`

**C / C++:** `function_definition`, `function_declaration`, `class_specifier`,
`struct_specifier`, `preproc_include`, `preproc_def`

**SQL / MySQL:** `create_table_statement`, `create_function_statement`,
`create_procedure_statement`, `create_trigger_statement`, `create_view_statement`,
`create_index_statement`, `column_definition`, `foreign_key_constraint`

### Extraction Approach

The extraction script is a single Python file that:

1. **Walks each source file's AST** and collects:
   - Symbol definitions (name, type, file, line range, visibility)
   - Signatures (parameters, return types from the AST)
   - Call expressions within each symbol's body (callee name, line)
   - Import statements (source, imported names)
   - Decorators/attributes on symbols

2. **Flags connection hints** that require LLM review:
   - Dynamic property access: `obj[variable]()` → `dynamic_call`
   - String literal dispatch: `handlers["key"]` → `string_key_dispatch`
   - Decorator/attribute patterns that imply framework wiring → `framework_magic`
   - Reflection patterns: `getattr()`, `eval()`, `Activator.CreateInstance()` → `reflection`

3. **Writes JSONL output** — one JSON object per symbol, matching the schema
   defined in "Symbol Types to Index" above.

The agent **writes this script at runtime** based on the detected languages,
then runs it via Bash. The script is disposable — it exists only to extract
symbols and is not committed to the repository.

### What Tree-Sitter Cannot Resolve

Tree-sitter extracts syntax, not semantics. These items require the agent's
LLM-based judgment after extraction:

- **Framework magic** — DI containers, decorator effects, convention-based routing
  (e.g., Next.js file-based routes are syntax, but NestJS `@Module()` providers
  require understanding the framework's DI resolution)
- **Dynamic dispatch** — `plugins[name].execute()` where `name` is a runtime value
- **Reflection** — `getattr(obj, field_name)` where `field_name` is dynamic
- **Macro-generated code** — Rust `derive` macros, C preprocessor macros that
  define functions
- **Template/convention patterns** — Rails resource routes, Django URL patterns
  that map to view classes by convention

These are flagged as `connection_hints` for the connection hunter.

## Language-Specific Extraction Patterns

> **With tree-sitter:** These patterns are implemented as AST node type queries in
> the extraction script. See "AST Node Types by Language" above for the tree-sitter
> equivalents.
>
> **Without tree-sitter (fallback):** Use these patterns with Grep to find symbol
> locations, then Read targeted line ranges to extract detail.

### JavaScript / TypeScript
- **Functions:** `function name(`, `const name = (`, `const name = function(`,
  `name(` as method in class body, arrow functions assigned to variables
- **Classes:** `class Name`, `class Name extends`, `class Name implements`
- **Routes:** `app.get(`, `app.post(`, `router.get(`, `@Get(`, `@Post(`,
  `@Controller(`, route arrays in configuration
- **Exports:** `export function`, `export class`, `export const`, `export default`,
  `module.exports`, `exports.name`
- **Imports:** `import { } from`, `require(`, `import(` (dynamic)
- **Types:** `interface Name`, `type Name =`, `enum Name`
- **Constants:** `const NAME =` (UPPER_CASE), `Object.freeze({`
- **React:** `function Component(`, `const Component = (`, `React.memo(`,
  `forwardRef(`, `createContext(`
- **Handlers:** `addEventListener(`, `.on(`, `.once(`, callback parameters
- **NOTE on missing types:** JavaScript has no static types. Record parameter names
  without types. If JSDoc `@param {Type}` or `@returns {Type}` exists, capture it.
  If not, record `"type": null`. Do NOT guess types.

### Python
- **Functions:** `def name(`, `async def name(`
- **Classes:** `class Name:`, `class Name(Base):`
- **Decorators:** `@route(`, `@app.route(`, `@blueprint.route(`, `@staticmethod`,
  `@classmethod`, `@property`
- **Imports:** `import module`, `from module import name`
- **Constants:** `NAME = value` at module level (UPPER_CASE convention)
- **Type hints:** Capture `param: Type` and `-> ReturnType` if present

### C# / .NET
- **Methods:** `public ReturnType Name(`, `private async Task<T> Name(`
- **Classes:** `class Name`, `class Name : Base, IInterface`
- **Properties:** `public Type Name { get; set; }`
- **Attributes:** `[HttpGet]`, `[Route("")]`, `[Authorize]`
- **Constants:** `const Type NAME =`, `static readonly`, `enum Name`
- **Events:** `event EventHandler<T> Name`, `delegate void Name(`

### C / C++
- **Functions:** `ReturnType Name(`, function declarations in headers
- **Classes/Structs:** `class Name`, `struct Name`, `typedef struct`
- **Macros:** `#define NAME`, preprocessor constants
- **Headers vs Implementation:** Record whether a symbol is in `.h`/`.hpp` (declaration)
  or `.c`/`.cpp` (definition). Link declaration to definition when both exist.

### Ruby
- **Methods:** `def name`, `def self.name`
- **Classes:** `class Name`, `class Name < Base`
- **Modules:** `module Name`
- **Routes:** `get '/'`, `post '/'`, `resources :name`, `namespace :name`
- **Constants:** `NAME = value` (capitalized)

### Go
- **Functions:** `func Name(`, `func (r *Receiver) Name(`
- **Structs:** `type Name struct {`
- **Interfaces:** `type Name interface {`
- **Constants:** `const Name =`, `const ( ... )`
- **Exports:** Capitalized names are exported

### Rust
- **Functions:** `fn name(`, `pub fn name(`, `async fn name(`
- **Structs:** `struct Name`, `pub struct Name`
- **Enums:** `enum Name`, `pub enum Name` (extract each variant as a constant-like entry)
- **Traits:** `trait Name`, `pub trait Name` (capture required methods as members)
- **Impl blocks:** `impl Name`, `impl Trait for Name` — link methods to their struct/trait
- **Macros:** `macro_rules! name`, `#[derive(...)]` (record derive macros on structs,
  these generate code the connection hunter must account for)
- **Modules:** `mod name`, `pub mod name`, `use crate::module::Symbol`
- **Constants:** `const NAME: Type =`, `static NAME: Type =`
- **Async:** `async fn`, `.await` call sites (record these as they affect call chains)
- **FFI:** `extern "C" fn`, `#[no_mangle]` (flag for connection hunter — may be called
  from C/C++ or other languages)
- **Attributes:** `#[test]`, `#[tokio::main]`, `#[actix_web::main]`, `#[get("/")]`,
  `#[post("/")]` (framework route attributes)
- **Closures:** Closures passed to `.map()`, `.filter()`, `.and_then()`, `spawn()`
  — record when they contain calls to other indexed symbols
- **NOTE on ownership:** Rust's borrow system doesn't affect the index (it's structural,
  not semantic). But `Arc<Mutex<T>>` and `Rc<RefCell<T>>` wrappers suggest shared
  mutable state — flag these for the connection hunter as potential reactive points.

### Swift
- **Functions:** `func name(`, `class func name(`, `static func name(`
- **Classes:** `class Name`, `class Name: Base, Protocol`
- **Structs:** `struct Name`, `struct Name: Protocol`
- **Enums:** `enum Name`, `enum Name: Type` (extract cases as members)
- **Protocols:** `protocol Name` (capture required methods/properties)
- **Extensions:** `extension Name`, `extension Name: Protocol` — link added methods
  to the extended type
- **Properties:** `var name: Type`, `let name: Type`, `@Published var name`,
  `@State var name`, `@Binding var name`
- **Initializers:** `init(`, `convenience init(`, `required init(`
- **Constants:** `let NAME =` at module scope, `static let`
- **Imports:** `import Module`, `@_implementationOnly import Module`
- **Closures:** Record closures passed to completion handlers, especially
  `completionHandler: @escaping (Result<T, Error>) -> Void` patterns
- **SwiftUI:** `var body: some View` (component definition), `@StateObject`,
  `@ObservedObject`, `@EnvironmentObject` (flag for connection hunter — these
  are reactive observation points)
- **Combine:** `Publisher`, `Subscriber`, `.sink(`, `.assign(`, `@Published`
  (flag for connection hunter as reactive chains)
- **Concurrency:** `async`, `await`, `Task {`, `actor Name` (structured concurrency
  entry points and actors as isolation boundaries)

### Objective-C
- **Methods:** `- (ReturnType)name:`, `+ (ReturnType)name:` (instance/class methods)
- **Classes:** `@interface Name : Base`, `@implementation Name`
- **Protocols:** `@protocol Name`, `<ProtocolName>` conformance
- **Properties:** `@property (nonatomic, strong) Type *name`
- **Categories:** `@interface Name (CategoryName)` — link added methods to base class
- **Constants:** `#define NAME`, `extern NSString *const Name`, `static const`
- **Imports:** `#import "Header.h"`, `#import <Framework/Header.h>`, `@import Module`
- **Blocks:** `^(Type param) { ... }` — record when passed as callbacks
- **Selectors:** `@selector(name:)`, `performSelector:` — flag for connection hunter,
  these are string-based dynamic dispatch
- **KVO:** `addObserver:forKeyPath:`, `observeValueForKeyPath:` — flag for connection
  hunter as reactive observation
- **Notifications:** `NSNotificationCenter` `addObserver:selector:name:`,
  `postNotificationName:` — flag for connection hunter as event emitter/listener
- **Delegate patterns:** `@property (weak) id<DelegateProtocol> delegate` — the
  delegate assignment is an indirect connection the connection hunter must trace
- **NOTE:** Objective-C's runtime dynamism (message passing, method swizzling,
  `respondsToSelector:`) means many connections are invisible to static indexing.
  Flag ALL `performSelector:`, `respondsToSelector:`, `NSClassFromString`,
  `NSSelectorFromString` for the connection hunter.

### SQL / MySQL
- **Tables:** `CREATE TABLE name`, `ALTER TABLE name` — record every column
  (name, type, nullability, default, constraints)
- **Views:** `CREATE VIEW name AS` — record as a derived symbol referencing its
  source tables
- **Stored Procedures:** `CREATE PROCEDURE name(`, `DELIMITER //` blocks — record
  parameters, body calls to other procedures, and DML operations (which tables are
  read/written)
- **Functions:** `CREATE FUNCTION name(` — record parameters, return type, determinism
  (`DETERMINISTIC` / `NOT DETERMINISTIC`)
- **Triggers:** `CREATE TRIGGER name BEFORE|AFTER INSERT|UPDATE|DELETE ON table` —
  record timing, event, table, and body operations. **Always flag as `connection_hint`
  type `db_hook`** — triggers are indirect connections invisible to application code
- **Indexes:** `CREATE INDEX name ON table(columns)`, `CREATE UNIQUE INDEX` — record
  index name, table, columns, uniqueness
- **Foreign Keys:** `FOREIGN KEY (col) REFERENCES other_table(col)` — record as a
  relationship between tables, with ON DELETE/ON UPDATE actions
- **Events:** `CREATE EVENT name ON SCHEDULE` — record as scheduled job entry points
  (flag for graph builder)
- **Constants:** `SET @variable =`, session/global variable assignments
- **Imports:** None (SQL has no import system). Cross-file references are implicit
  via table/procedure names — the cross-reference pass must match these by name.
- **NOTE:** SQL files may be migration files (versioned schema changes) or
  persistent definitions (stored procedures, views). Record both. For migration
  files, record the final state of each table after all migrations are applied
  if determinable; otherwise record each migration as a separate symbol with a
  `migration_order` field.

## Handling Untyped / Dynamic Languages

For JavaScript, Python, Ruby, and other dynamic languages:

1. **Record what's visible.** If there's no type annotation, record `"type": null`.
   Do NOT infer types from usage patterns — that's interpretation, not indexing.
2. **Capture JSDoc / docstrings / type comments** when present. These go in an
   optional `"doc_type"` field alongside the null `"type"`:
   ```json
   {"name": "userId", "type": null, "doc_type": "string (from @param)"}
   ```
3. **Record parameter names even without types.** The name itself is useful for
   graph matching (e.g., `userId` appearing as both a parameter and a property).
4. **Dynamic method calls** (`obj[methodName]()`, `getattr(obj, name)`) — record
   the call site as `{"name": "[dynamic]", "expression": "obj[methodName]"}`.
   These are flagged for the connection hunter to resolve.

## Execution Strategy

1. **Check tree-sitter availability.** Verify Python 3 and tree-sitter are installed:
   ```bash
   python3 -c "import tree_sitter_languages" 2>/dev/null && echo "ready"
   ```
   If not available, install:
   ```bash
   pip install tree-sitter-languages
   ```
   If installation fails, fall back to LLM-based extraction (see "Fallback" below).

2. **Build file manifest.** Glob for all source files in scope, excluding
   vendor/node_modules/generated directories. Write the manifest. Map each file
   to its tree-sitter language identifier.

3. **Write and run the extraction script.** Create a Python script that:
   a. Iterates over every file in the manifest.
   b. Parses each file with tree-sitter using the appropriate language grammar.
   c. Walks the AST to extract symbols: definitions, signatures, call sites,
      imports, exports, decorators/attributes.
   d. Flags connection hints: dynamic dispatch, reflection, framework magic,
      string-keyed dispatch patterns.
   e. Writes one JSONL line per symbol to the output file.
   f. Writes a summary line at the end with file counts and symbol counts.

   Run via Bash:
   ```bash
   python3 /tmp/extract_symbols.py \
     --scope "src/main,src/renderer" \
     --languages "typescript,javascript" \
     --output intermediate/index--main.jsonl \
     --manifest intermediate/manifest--main.json
   ```

   The script is disposable — written by the agent at runtime for the specific
   languages and frameworks detected, then discarded after extraction.

4. **Review connection hints (LLM pass).** After tree-sitter extraction, review
   ONLY the flagged connection hints. For each hint:
   a. Read the source code at the flagged location (targeted line range).
   b. Determine if it's a connection hint for the connection hunter, a framework
      convention, or a false positive.
   c. Update the hint record with classification and notes.

   This is the ONLY step where the agent reads source files. Basic symbol
   extraction is fully handled by tree-sitter.

5. **Cross-reference pass.** Either in the extraction script or as a post-processing
   step:
   - For each `calls` entry, find the matching definition and record the reverse
     `called_by` edge.
   - For each `import`, resolve the source path to an actual file.
   - For each `exports` entry, find all files that import it.

6. **Write the final output.** If `db_path` is provided, insert into the SQLite database
   (the orchestrator handles DB creation). Otherwise, write JSONL to `output_path`.

### Fallback: LLM-Based Extraction

If tree-sitter cannot be installed, fall back to manual extraction using the patterns
in "Language-Specific Extraction Patterns":

1. For each file: Grep for definition patterns to find symbol locations.
2. Read targeted line ranges to extract signatures and call sites.
3. Write JSONL output incrementally.

This fallback is **significantly slower**, **less reliable** (regex can't parse
nested structures), and **burns context window** reading every source file. Use it
only when tree-sitter is genuinely unavailable.

## Storage Format

### Intermediate: JSONL (teammate output)

Each teammate writes one JSON object per line to its `.jsonl` output file. This is
append-only and crash-safe — if the teammate dies mid-file, all previously written
lines are valid.

### Final: SQLite (orchestrator merges)

The orchestrator merges all JSONL files into a single SQLite database. SQLite is used
because:
- **Queryable:** Agents can `SELECT * FROM symbols WHERE file = 'src/services/order.ts'`
  instead of loading 50,000+ symbols into context
- **Incremental:** On code changes, UPDATE/INSERT only affected rows instead of
  rewriting the entire file
- **Relational:** Call edges, imports, and connections are naturally JOIN-able
- **Single file:** No external database server, just a `.db` file on disk

### SQLite Schema

```sql
CREATE TABLE metadata (
  key TEXT PRIMARY KEY,
  value TEXT
);
-- Keys: generated_at, repo, scope, languages, files_indexed, total_symbols

CREATE TABLE symbols (
  id TEXT PRIMARY KEY,          -- SYM-0001
  type TEXT NOT NULL,           -- function, class, method, route, constant, etc.
  name TEXT NOT NULL,
  qualified_name TEXT,
  file TEXT NOT NULL,
  line_start INTEGER NOT NULL,
  line_end INTEGER,
  signature_json TEXT,          -- JSON: {params: [...], return_type: "..."}
  visibility TEXT,              -- public, private, protected, internal
  is_async INTEGER DEFAULT 0,
  decorators_json TEXT,         -- JSON array of decorator strings
  exports_json TEXT,            -- JSON array: ["named"], ["default"], []
  caller_count INTEGER DEFAULT 0,
  extra_json TEXT               -- Any type-specific fields not in standard columns
);

CREATE TABLE calls (
  caller_id TEXT NOT NULL REFERENCES symbols(id),
  callee_id TEXT,               -- NULL if unresolved (dynamic dispatch)
  callee_name TEXT NOT NULL,    -- Always populated even if callee_id is NULL
  call_file TEXT,
  call_line INTEGER,
  connection_type TEXT DEFAULT 'direct',  -- direct, event, ipc, pubsub, etc.
  UNIQUE(caller_id, callee_name, call_line)
);

CREATE TABLE imports (
  file TEXT NOT NULL,
  line INTEGER,
  source TEXT NOT NULL,         -- Import specifier as written
  resolved_file TEXT,           -- Resolved absolute/relative path
  symbols_json TEXT             -- JSON array of imported symbol names
);

CREATE TABLE file_manifest (
  file TEXT PRIMARY KEY,
  lines INTEGER NOT NULL,
  symbols_count INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending' -- pending, done, incomplete, skipped
);

CREATE TABLE connection_hints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,           -- dynamic_call, string_key_dispatch, framework_magic, reflection
  file TEXT NOT NULL,
  line INTEGER NOT NULL,
  expression TEXT,
  note TEXT,
  resolved INTEGER DEFAULT 0   -- Set to 1 after connection hunter processes it
);

-- Indexes for common query patterns
CREATE INDEX idx_symbols_file ON symbols(file);
CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_symbols_type ON symbols(type);
CREATE INDEX idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX idx_calls_caller ON calls(caller_id);
CREATE INDEX idx_calls_callee ON calls(callee_id);
CREATE INDEX idx_calls_callee_name ON calls(callee_name);
CREATE INDEX idx_imports_file ON imports(file);
CREATE INDEX idx_imports_resolved ON imports(resolved_file);
```

### Querying the Index

Agents downstream of the indexer (connection hunter, graph builder, annotator) query
the SQLite database directly rather than loading the full index:

```sql
-- Find all symbols in a file
SELECT * FROM symbols WHERE file = 'src/services/order.ts';

-- Find all callers of a function
SELECT s.* FROM symbols s
JOIN calls c ON c.caller_id = s.id
WHERE c.callee_name = 'calculateShippingCost';

-- Find all symbols with no callers (potential entry points)
SELECT * FROM symbols WHERE caller_count = 0 AND type = 'route';

-- Find unresolved connection hints for a specific type
SELECT * FROM connection_hints WHERE type = 'dynamic_call' AND resolved = 0;

-- Find all symbols exported from a file
SELECT * FROM symbols WHERE file = 'src/services/order.ts' AND exports_json != '[]';
```

## What to Flag for Connection Hunter

Some patterns can't be resolved by mechanical indexing. Flag these in a
`"connection_hints"` array at the top level of the output:

```json
"connection_hints": [
  {
    "type": "dynamic_call",
    "file": "src/plugins/loader.ts",
    "line": 45,
    "expression": "plugins[name].init()",
    "note": "Dynamic dispatch — target depends on runtime plugin registry"
  },
  {
    "type": "string_key_dispatch",
    "file": "src/handlers/router.ts",
    "line": 78,
    "expression": "handlers[event.type](event)",
    "note": "String-keyed dispatch — need to match event.type values to handler keys"
  },
  {
    "type": "framework_magic",
    "file": "src/modules/auth.module.ts",
    "line": 12,
    "expression": "@Module({ providers: [AuthService, JwtService] })",
    "note": "DI container — AuthService is injected by framework, not by import"
  },
  {
    "type": "reflection",
    "file": "src/utils/serializer.py",
    "line": 30,
    "expression": "getattr(model, field_name)",
    "note": "Reflection — field_name determined at runtime"
  }
]
```

These hints are consumed by the connection hunter agent to resolve indirect edges.
