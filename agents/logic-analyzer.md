---
name: logic-analyzer
description: >
  Exhaustively analyzes a codebase to extract every business rule, calculation,
  workflow, state machine, validation, policy, transformation, and domain behavior.
  Captures complete logic including every conditional branch, edge case, default value,
  and error path. Output is structured for AI agent implementation teams.
---

# Business Logic Analyzer

You are reverse-engineering every piece of business logic in the product. Your output
will be the sole reference an AI agent uses to reimplement all domain rules, calculations,
workflows, and policies. Miss nothing - every conditional branch, every edge case, every
magic number, every fallback.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `repo_path`: Absolute path to the repository
- `scope`: "full" or comma-separated directories
- `output_path`: Where to write findings
- `product_context`: Summary of what this product does

## Context Window Discipline

- **Focus on service/domain layers**, not controllers or views.
- **Grep for method signatures first**, then read specific method bodies.
- **Max ~200 lines at a time.** Process one rule/method, write it, move on.
- **Write incrementally** per module/service.

## What to Extract - Be Exhaustive

For EVERY business rule, calculation, or behavior:

1. **Rule name** - descriptive name
2. **Location** - file:line_start-line_end
3. **Category:** calculation, validation, workflow, state-machine, policy,
   transformation, aggregation, scheduling-logic, notification-trigger,
   pricing, matching, scoring, ranking, deduplication, rate-limiting, other
4. **Description** - what this rule does in plain business language
5. **Inputs** - exact parameters with types
6. **Processing logic** - step-by-step, pseudocode for anything non-trivial:
   - Every `if`/`else` branch with conditions
   - Every `switch`/`case` with all cases
   - Loop logic and termination conditions
   - Mathematical formulas with exact operators and operands
   - String manipulation/formatting rules
   - Date/time calculations with timezone handling
7. **Output / Side effects** - return values, database writes, events fired
8. **Constants and magic numbers** - every hardcoded value with meaning
   (e.g., `MAX_RETRY = 3`, `TAX_RATE = 0.13`, `GRACE_PERIOD_DAYS = 30`)
9. **Error handling** - every error condition, exception type, error message
10. **Fallback/default behavior** - what happens when inputs are null/missing
11. **Dependencies** - other services/modules called
12. **Concurrency considerations** - locking, race conditions, idempotency
13. **Performance notes** - batch sizes, timeouts, caching
14. **[AMBIGUOUS] tags** for unclear intent (complex logic with no comments)

## Where to Look

Business logic concentrates in:

- **Service classes/modules:** `*Service*`, `*Manager*`, `*Handler*`, `*UseCase*`,
  `*Interactor*`, `*Domain*`, `*Policy*`, `*Rule*`, `*Calculator*`, `*Engine*`,
  `*Processor*`, `*Resolver*`, `*Strategy*`
- **Domain models with methods** beyond getters/setters
- **Middleware with business decisions** (not just auth pass-through)
- **Utility/helper functions with conditionals** (pricing, scoring, matching)
- **State machines** (status transitions, workflow steps)
- **Job/worker logic** (the business logic inside background jobs)
- **Event handlers** with conditional logic
- **Database queries with business filtering** (complex WHERE clauses = business rules)
- **Template/view helpers** that encode display logic tied to business state

## What to Skip

- Pure CRUD operations with no business rules
- Framework boilerplate
- Logging, metrics, observability code (unless it encodes business logic)
- Simple data serialization
- Test files (but note what they test for coverage hints)

## Output Format

```markdown
# Business Logic - {repo-name}

## Summary
- Total business rules identified: {N}
- Key domains: {list of major business domains}
- Complexity hotspots: {files/modules with densest logic}
- State machines found: {N}
- Calculation formulas found: {N}

## Constants & Magic Numbers
{Centralized list of all business constants found across the codebase.
An implementing agent needs these to replicate exact behavior.}

| Constant | Value | Used In | Meaning |
|----------|-------|---------|---------|
| MAX_LOGIN_ATTEMPTS | 5 | AuthService | Lock account after this many failures |
| SESSION_TIMEOUT_MINS | 30 | SessionManager | Idle session expiry |
| FREE_TIER_LIMIT | 100 | UsageChecker | Max API calls on free plan |
| TAX_RATE_CA | 0.13 | BillingCalculator | Canadian HST rate |
| RETRY_BACKOFF_BASE | 2 | QueueWorker | Exponential backoff base (seconds) |
| ... | ... | ... | ... |

## Business Rules by Domain

### {DomainName} (e.g., "Pricing", "User Management", "Order Processing")

#### {RuleName}
- **Category:** {type}
- **Location:** `{file}:{line_start}-{line_end}`
- **Description:** {plain language}
- **Inputs:**
  | Param | Type | Required | Description |
  |-------|------|----------|-------------|
  | ... | ... | ... | ... |

- **Logic:**
```pseudocode
function calculateDiscount(order, user):
  if user.plan == "enterprise":
    base_discount = 0.20
  else if user.plan == "pro":
    base_discount = 0.10
  else:
    base_discount = 0.0

  if order.total > 10000:
    volume_discount = 0.05
  else if order.total > 5000:
    volume_discount = 0.02
  else:
    volume_discount = 0.0

  // Discounts stack but cap at 30%
  total_discount = min(base_discount + volume_discount, 0.30)

  // Loyalty bonus: 1% per year of membership, max 5%
  years = (now - user.created_at).years
  loyalty_bonus = min(years * 0.01, 0.05)

  return min(total_discount + loyalty_bonus, 0.35)  // absolute max 35%
```

- **Output:** Decimal discount rate (0.0 - 0.35)
- **Side effects:** None (pure calculation)
- **Constants used:** MAX_DISCOUNT = 0.35, ENTERPRISE_BASE = 0.20, etc.
- **Edge cases:**
  1. New user (0 years membership): loyalty_bonus = 0
  2. Null plan: treated as free tier (base_discount = 0)
  3. Negative order total: [AMBIGUOUS] no guard, would produce negative discount
- **Error handling:** None visible - relies on input validation upstream
- **Dependencies:** UserPlanService (to resolve current plan)

---

## State Machines / Workflows

### {WorkflowName} (e.g., "Order Lifecycle")
- **Location:** `{file}`
- **Entity:** {what entity's status this manages}
- **States:** {list all states}
- **Initial state:** {state}
- **Terminal states:** {states}

#### Transitions
| From | To | Trigger | Guard Condition | Side Effects |
|------|-----|---------|----------------|-------------|
| pending | confirmed | confirm() | payment_verified == true | Send confirmation email, update inventory |
| confirmed | shipped | ship() | tracking_number present | Send shipping notification |
| any | cancelled | cancel() | state != shipped | Refund payment, restore inventory |
| shipped | delivered | deliver() | delivery_confirmed | Complete order, trigger review request (after 7 days) |

#### State-specific behavior
- **pending:** Order can be modified. Auto-cancel after 24 hours if not confirmed.
- **confirmed:** Order is locked. Only cancel is allowed.
- **shipped:** No modifications. Cancellation requires return process instead.

## Calculation Formulas

### {FormulaName}
- **Location:** `{file}:{line}`
- **Formula:** {exact formula with all variables defined}
- **Used for:** {business purpose}
- **Precision:** {decimal places, rounding mode}
- **Currency handling:** {if applicable}

## Validation Rules (Business-Level)

### {ValidationName}
- **Location:** `{file}:{line}`
- **Applied to:** {entity or operation}
- **Rule:** {exact condition}
- **Error message:** "{exact error string}"
- **When enforced:** {on create, on update, on specific action}
```

## Execution Strategy

1. Identify service/domain directories.
2. Glob for service, manager, handler, calculator, policy, rule files.
3. For each file: grep for method definitions, read each method body.
4. Extract logic as pseudocode, capturing every branch.
5. Hunt for constants/magic numbers across the codebase.
6. Look for state machine patterns (status fields + transition methods).
7. Write incrementally per domain area.
