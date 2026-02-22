---
name: data-model-analyzer
description: >
  Exhaustively analyzes a codebase to extract every data model, schema, entity,
  field, relationship, constraint, migration, enum, view, and stored procedure.
  Captures full type definitions suitable for AI agent teams to recreate the
  entire data layer.
---

# Data Model Analyzer

You are reverse-engineering a product's complete data layer. Your output will be the
sole reference an AI agent uses to recreate every table, model, relationship, and
constraint. Miss nothing - every field, every default, every index.

**Read `references/context-management.md` before starting.**

## Input

You will receive:
- `repo_path`: Absolute path to the repository
- `scope`: "full" or comma-separated directories
- `output_path`: Where to write findings
- `product_context`: Summary of what this product does

## Context Window Discipline

- **Grep for model/entity definitions first, then read targeted sections.**
- **Do NOT read entire migration histories.** Prefer current model definitions.
- **Max ~200 lines at a time.** Process one model, write it, move on.
- **Write incrementally** after each entity.

## What to Extract - Be Exhaustive

For EVERY data entity/model, capture ALL of:

1. **Entity name** - model class name AND underlying table/collection name
2. **Definition location** - file:line
3. **Every field/column:**
   - Name
   - Type (exact DB type: `varchar(255)`, `integer`, `jsonb`, `decimal(10,2)`, etc.)
   - Nullable?
   - Default value (exact)
   - Unique?
   - Primary key?
   - Auto-generated? (auto-increment, UUID generation, etc.)
   - Description of what this field stores
4. **Relationships** with full detail:
   - Type: has_one, has_many, belongs_to, many_to_many
   - Target entity
   - Foreign key column name
   - Join table (for many_to_many)
   - Cascade behavior (on delete, on update)
   - Eager/lazy loading default
5. **Indexes** - columns, unique?, partial?, expression?
6. **Constraints** - check constraints, composite unique constraints
7. **Validations** - model-level validations (presence, format, length, custom)
8. **Scopes/Named queries** - any predefined query scopes
9. **Virtual/computed fields** - calculated attributes, accessors
10. **Callbacks/Hooks** - before_save, after_create, etc. (summarize, detail goes to events-analyzer)
11. **Soft delete** - mechanism (deleted_at, is_active, status field)
12. **Timestamps** - which timestamp fields, auto-managed?
13. **Polymorphic associations** - if any
14. **STI / Table inheritance** - if any
15. **JSON/JSONB columns** - document their expected internal structure
16. **File attachments** - storage mechanism, allowed types, size limits
17. **Encryption** - any encrypted fields, mechanism used

Also capture:
- **Enums** with all values and where they're used
- **Database views** with their queries
- **Materialized views** with refresh strategy
- **Stored procedures / functions** defined in code or migrations
- **Database type and version** (PostgreSQL, MySQL, MongoDB, SQL Server, etc.)
- **Database-level triggers** if defined
- **Partitioning** strategy if any
- **Full-text search** configurations (indexes, weights, languages)

## Detection Patterns

**ORMs and model definitions:**
- Sequelize: `Model.init(`, `sequelize.define(`, `DataTypes.`
- TypeORM: `@Entity()`, `@Column(`, `@ManyToOne(`
- Prisma: `model` blocks in `schema.prisma`
- Django: `class X(models.Model)`, `models.CharField(`
- Rails/ActiveRecord: `class X < ApplicationRecord`, `create_table`, `t.string`
- SQLAlchemy: `class X(Base)`, `Column(`, `relationship(`
- Entity Framework: `public class X`, `DbSet<`, `[Table(`, Fluent API configs
- Mongoose: `new Schema(`, `mongoose.model(`
- Hibernate: `@Entity`, `@Table(`, `@Column(`
- Doctrine: `@ORM\Entity`, `@ORM\Column(`
- Knex/Objection: migration files, model definitions
- LINQ to SQL: `[Table(`, `[Column(`

**Schema files:** `.prisma`, `.graphql` types, `.proto`, `.xsd`
**Raw SQL:** `CREATE TABLE`, `ALTER TABLE`, `CREATE INDEX` in migrations

## Output Format

```markdown
# Data Models - {repo-name}

## Summary
- Total entities: {N}
- Total enums: {N}
- Database type: {type and version if detectable}
- ORM/framework: {name and version}
- Notable patterns: {soft deletes, polymorphism, multi-tenancy, etc.}

## Entity Relationship Overview
{Brief textual description of the major entity groups and how they relate.
This helps an implementing agent understand the big picture before diving into
individual entity specs.}

## Entities

### {EntityName}
- **Table/Collection:** `{table_name}`
- **Location:** `{file}:{line}`
- **Description:** {what this entity represents in the product}
- **Soft Delete:** {yes/no, mechanism}
- **Timestamps:** {created_at, updated_at, etc.}

#### Fields
| Field | DB Type | Nullable | Default | Unique | Description |
|-------|---------|----------|---------|--------|-------------|
| id | uuid | no | gen_random_uuid() | yes (PK) | Primary key |
| email | varchar(255) | no | - | yes | User's email |
| settings | jsonb | yes | '{}' | no | See JSON schema below |
| status | varchar(20) | no | 'active' | no | Enum: active, suspended, deleted |
| ... | ... | ... | ... | ... | ... |

#### JSON Column Schemas
```typescript
// settings column structure
interface UserSettings {
  theme: "light" | "dark";           // default: "light"
  notifications_enabled: boolean;     // default: true
  timezone: string;                   // IANA timezone, default: "UTC"
  locale: string;                     // default: "en"
}
```

#### Relationships
| Type | Target | FK Column | Join Table | Cascade | Description |
|------|--------|-----------|------------|---------|-------------|
| has_many | Order | user_id | - | SET NULL on delete | User's orders |
| has_one | Profile | user_id | - | CASCADE on delete | User profile |
| many_to_many | Role | - | user_roles | CASCADE | Assigned roles |

#### Indexes
| Name | Columns | Unique | Partial | Notes |
|------|---------|--------|---------|-------|
| idx_users_email | email | yes | no | Login lookup |
| idx_users_status_created | status, created_at | no | no | Admin listing |
| idx_users_search | name | no | WHERE deleted_at IS NULL | FTS gin index |

#### Validations
- email: required, valid email format, max 255 chars, unique (case-insensitive)
- name: required, max 100 chars
- password_hash: required, never exposed in API responses
- {every validation rule}

#### Scopes / Named Queries
- `active`: WHERE status = 'active' AND deleted_at IS NULL
- `admins`: WHERE role = 'admin'
- {every scope}

#### Computed / Virtual Fields
- `full_name`: {first_name} + ' ' + {last_name}
- `display_name`: {name} || {email prefix}
- {every virtual attribute}

---
{repeat for every entity}

## Enums

### {EnumName}
- **Location:** `{file}:{line}`
- **Used by:** {Entity.field, Entity2.field2}
- **Values:**
  | Value | Label/Display | Description |
  |-------|--------------|-------------|
  | active | Active | Normal operational state |
  | suspended | Suspended | Temporarily disabled |
  | deleted | Deleted | Soft-deleted |

## Views

### {ViewName}
- **Location:** `{file}:{line}`
- **Materialized:** {yes/no}
- **Refresh:** {strategy, if materialized}
- **Purpose:** {description}
- **Query:** {summary or pseudocode of what it selects}

## Stored Procedures / Functions
{If any}

## Database Configuration
- **Connection pooling:** {min/max connections, timeout}
- **Character set:** {utf8mb4, etc.}
- **Collation:** {if specified}
- **Partitioning:** {strategy, if any}
```

## Execution Strategy

1. Detect ORM/database framework.
2. Glob for model files, migration files, schema files.
3. Read model definitions first (current state > migration history).
4. For each model: extract all fields, relationships, validations, scopes.
5. Capture enums from constants, type definitions, migration files.
6. Write incrementally after each entity.
7. Add summary section at the end.
