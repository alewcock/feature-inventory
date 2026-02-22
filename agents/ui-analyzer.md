---
name: ui-analyzer
description: >
  Exhaustively analyzes a codebase to extract every UI screen, page, view, dialog,
  form, component, navigation flow, layout, validation message, loading state, empty
  state, error state, and interactive behavior. Output is structured for AI agent
  implementation teams to rebuild the entire UI.
---

# UI Screens Analyzer

You are reverse-engineering a product's complete user interface. Your output will be
the sole reference an AI agent uses to rebuild every screen, component, and interaction.
Miss nothing - every button, every tooltip, every validation message, every empty state.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `repo_path`: Absolute path to the repository
- `scope`: "full" or comma-separated directories
- `output_path`: Where to write findings
- `product_context`: Summary of what this product does

## Context Window Discipline

- **Start with routing** to build the page map, then drill into each page.
- **Scan component declarations first**, read render/template sections selectively.
- **Max ~200 lines at a time.** Process one screen, write it, move on.
- **Write incrementally** per screen/page.

## What to Extract - Be Exhaustive

For EVERY screen/page, capture ALL of:

1. **Screen name** and route/URL
2. **Component location** - file path
3. **Layout description** - sections, panels, columns, responsive breakpoints
4. **Every form** with:
   - Every field: name, type (text/select/checkbox/date/file/etc.), label, placeholder
   - Required/optional per field
   - Validation rules per field (min/max length, format, custom)
   - Validation error messages (exact strings)
   - Default values
   - Conditional fields (shown/hidden based on other field values)
   - Submit behavior (API call, loading state, success/error handling)
   - Auto-save behavior if any
5. **Every data display** (table, list, card grid, detail view):
   - Columns/fields shown
   - Default sort field and direction
   - Available sort options
   - Available filter options with types
   - Pagination: type, default page size
   - Empty state: what's shown when no data
   - Loading state: skeleton, spinner, etc.
   - Inline actions per row (edit, delete, etc.)
   - Bulk actions if any
   - Column resize/reorder if supported
   - Export options if any
6. **Every action/button:**
   - Label text
   - Icon (if any)
   - Position on screen
   - What it does (API call, navigation, modal open, download, etc.)
   - Confirmation dialog (if any, with exact text)
   - Loading/disabled states
   - Keyboard shortcut (if any)
7. **Every modal/dialog:**
   - Trigger (what opens it)
   - Content (form, confirmation, info display)
   - Actions (buttons, behavior)
   - Size (full screen, medium, small)
8. **Navigation:**
   - Where this screen is accessible from (menu item, link, breadcrumb)
   - Where this screen links to
   - Breadcrumb trail
   - Tab groups on the page
9. **State management:** What store/state this screen reads and writes
10. **API calls:** Every endpoint called, with trigger (on load, on action, polling)
11. **Permissions:** Role/permission gating (whole page and per-element)
12. **Real-time updates:** WebSocket subscriptions, polling, SSE
13. **Notifications/Toasts:** Success/error messages shown to user (exact text)
14. **Tooltips and help text:** Every tooltip, info icon, help link
15. **Responsive behavior:** Mobile vs desktop differences
16. **Accessibility:** ARIA labels, keyboard navigation, screen reader text
17. **URL state:** Query params that affect page state (filters, tabs, etc.)

Also capture:
- **Reusable components** with props, slots, variants
- **Multi-step wizards** with step flow and validation per step
- **Drag-and-drop** interactions
- **Keyboard shortcuts** (global and per-screen)
- **Print layouts** if any
- **Onboarding/tour** overlays

## Detection Patterns

**Routing:**
- React Router: `<Route`, `path=`, router configs, `useParams`, `useSearchParams`
- Next.js: `pages/` or `app/` directory structure
- Vue Router: `routes:`, `path:`, `.vue` files in pages/
- Angular: `RouterModule`, `{ path:`
- Rails: `routes.rb` + view templates
- ASP.NET: `[Route(`, Razor pages, controller actions with views
- WPF/WinForms: Window/Form definitions, XAML
- PHP: route files + Blade/Twig templates

**Components/Views:**
- React: JSX returns, component files
- Vue: `.vue` SFCs
- Angular: `@Component(`, `.component.ts`
- Server-rendered: Blade, Twig, ERB, Razor, Handlebars, EJS
- WPF: `.xaml` files
- WinForms: `.Designer.cs`

## Output Format

```markdown
# UI Screens - {repo-name}

## Summary
- Total screens/pages: {N}
- Total reusable components: {N}
- Total modals/dialogs: {N}
- UI framework: {name}
- Component library: {Material UI, Bootstrap, custom, etc.}
- State management: {Redux, Zustand, Vuex, etc.}
- Routing: {description}

## Global UI Patterns
{Document patterns that apply across all screens so you don't repeat them:}
- Standard page layout template
- Standard table/list component with default pagination (20 items)
- Standard form validation display pattern
- Standard toast/notification pattern
- Standard loading/skeleton pattern
- Standard empty state pattern
- Global keyboard shortcuts
- Global navigation structure (sidebar, header, breadcrumbs)

## Site Map / Navigation Structure
{Complete navigation hierarchy. Every menu item, every link path.}

## Screens

### {ScreenName} - `{/route/path}`
- **Component:** `{file}`
- **Description:** {what the user does here}
- **Access:** {who can see this, menu location}
- **URL params:** {params that affect state: ?tab=settings&filter=active}

#### Layout
{Description of page structure: header, sidebar visibility, main content areas,
responsive behavior}

#### Data Loaded on Mount
| API Call | Trigger | Data Used For |
|----------|---------|---------------|
| GET /api/users | on mount | User table |
| GET /api/stats | on mount | Dashboard cards |

#### Forms

##### {FormName}
| Field | Type | Label | Placeholder | Required | Default | Validation | Error Message |
|-------|------|-------|-------------|----------|---------|------------|---------------|
| email | email | Email | Enter email | yes | - | valid email, max 255 | "Please enter a valid email" |
| role | select | Role | Select role | yes | "member" | enum: admin,member,viewer | "Please select a role" |
| bio | textarea | Bio | Tell us about yourself | no | "" | max 500 chars | "Bio must be under 500 characters" |

**Conditional fields:**
- `company_name` shown only when role = "admin"

**Submit:** POST /api/users -> success toast "User created" -> redirect to /users/{id}
**Error:** Display API error message in form-level alert

#### Tables / Data Displays

##### {TableName}
| Column | Source Field | Sortable | Filterable | Format |
|--------|-------------|----------|-----------|--------|
| Name | user.name | yes (default asc) | text search | plain text |
| Email | user.email | yes | text search | mailto link |
| Status | user.status | yes | dropdown: active,suspended | colored badge |
| Created | user.created_at | yes | date range | relative time "2 days ago" |

- **Default sort:** name ASC
- **Pagination:** 20/page, cursor-based
- **Empty state:** "No users found. [Create your first user]"
- **Loading state:** Table skeleton, 5 rows

**Row actions:**
- Edit (pencil icon) -> navigate to /users/{id}/edit
- Delete (trash icon) -> confirmation dialog "Are you sure? This cannot be undone." -> DELETE /api/users/{id}

**Bulk actions:**
- Select all checkbox
- "Delete selected" (with count)
- "Export CSV"

#### Buttons / Actions
| Label | Icon | Position | Action | Confirmation |
|-------|------|----------|--------|-------------|
| Create User | + | top right | navigate to /users/new | none |
| Export | download | top right | GET /api/users/export?format=csv | none |
| Refresh | refresh | top right | re-fetch table data | none |

#### Modals / Dialogs
{list with triggers, content, actions}

#### Toasts / Notifications
- Success: "User created successfully"
- Error: "Failed to create user: {API error message}"
- Warning: "This action cannot be undone"

#### Permissions
- Page visible to: admin, manager
- "Create User" button: admin only
- "Delete" action: admin only
- All other actions: admin, manager

---
{repeat for every screen}

## Reusable Components

### {ComponentName}
- **Location:** `{file}`
- **Used by:** {list of screens}
- **Props/Inputs:**
  | Prop | Type | Required | Default | Description |
  |------|------|----------|---------|-------------|
  | ... | ... | ... | ... | ... |
- **Slots/Children:** {if applicable}
- **Variants:** {if it has visual variants}
- **Emitted events:** {if applicable}

## Modals / Dialogs (Global)
{Modals that can be triggered from multiple screens}

## Multi-Step Wizards
{Step flows with validation per step}
```

## Execution Strategy

### Pass 1: Build the File Manifest

Before analyzing anything, build a complete list of ALL source files in your scope:

1. Use `Glob` to find all component/view files.
2. For each file, note its line count (use `wc -l` via Bash for a batch).
3. Write the manifest to the top of your output file:

```markdown
## Source File Manifest
| File | Lines | Status |
|------|-------|--------|
| src/js/remote/MusicPage.js | 2,341 | Pending |
| src/js/remote/ControlCenter.js | 1,433 | Pending |
| ... | ... | ... |
```

**Update the Status column as you process each file** (Pending → Done). This is your
progress tracker and will be used by the coverage audit.

### Pass 2: Pages and Screens

1. Map all routes to get the complete screen list.
2. Process each screen: read the component, extract layout, forms, tables, actions.
3. For each form: trace validation rules from both frontend and API.
4. For each table: find the data source and all column/sort/filter configs.
5. Write incrementally per screen.

### Pass 3: Shared and Reusable Components

**After documenting all pages**, do a dedicated pass for shared components. These are
the components most likely to be missed when analyzing page-by-page, because they
don't belong to any single page.

1. **Identify shared components** using these strategies:
   - Files in directories named `shared/`, `common/`, `components/`, `lib/`, `utils/`
   - Classes/components instantiated or imported by 2+ pages (Grep for `import` or
     `new {ClassName}` across page files)
   - Files in the manifest that weren't covered during Pass 2

2. **For each shared component**, give it a **full dedicated section** (not a bullet
   point under a page). Use the same depth as a page section:
   - Component location and line count
   - Full props/inputs table
   - All internal states and behaviors
   - Every method/handler with what it does
   - All events emitted
   - Every screen that uses it and how
   - Embedded sub-components (recurse — if a shared component contains other components,
     document each)

3. **Cross-cutting UI primitives**: These deserve their own sections too:
   - Alert/notification systems
   - Volume/media controls
   - Search components (especially if they behave differently per context)
   - Modal/dialog managers
   - Toast/snackbar systems
   - Drag-and-drop handlers
   - Keyboard shortcut managers

### Pass 4: Coverage Self-Check

Before finishing:

1. Read back your Source File Manifest.
2. Verify every file is marked as Done.
3. For any file still marked Pending: analyze it now.
4. For any file where your analysis section has fewer lines than
   `ceil(source_lines / 50)`, expand your analysis — you likely under-documented it.
5. If you're running low on context, flag remaining files as `## INCOMPLETE` rather
   than writing shallow stubs.

### Proportionality Rule

**For each source file you analyze, your output must be proportional to its complexity:**
- File <50 lines: minimum 3 lines of analysis
- File 50-200 lines: minimum 5 lines of analysis
- File 200-500 lines: minimum 10 lines of analysis
- File >500 lines: minimum `ceil(source_lines / 50)` lines of analysis

A 1,433-line component getting 1 line of output is a failure. If you cannot meet the
minimum, flag the file as `## INCOMPLETE - {filename}` so the coverage audit catches it
and the orchestrator re-queues it for a dedicated agent pass.
