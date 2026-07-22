# Teradata — Object Placement (conforming reference implementation)

A conforming Teradata implementation of the
[`object-placement`](../../../../design/patterns/object-placement.md) interface spec. This is a
**reference** — an organisation adapts the naming pattern and separation policy to its standards;
the eight sections below are what any conforming implementation must declare.

## Section 1 — Platform Declaration
Teradata (v17.20+). Container = `DATABASE`. Access principal = `ROLE` (and `USER`). Flat namespace
(`database.object`). Max container name 30 chars. Avoid reserved words and non-alphanumeric except `_`.

## Section 2 — Container Model
Parent + child. A parent database allocates `PERM` space and owns child databases but holds no data
objects; child databases hold objects. Two levels (parent → child). Development and production may be
separate systems; agents must not assume cross-system connectivity.

## Section 3 — Naming Pattern
`{{Product}}_{{Module}}` for base containers; `{{Product}}_{{Module}}_V` for the view layer under
`STRICT_SEPARATION`. Separator `_`. Example: `Customer360_Domain`, `Customer360_Domain_V`. Object
names are environment-agnostic — only the container changes between environments (`INV-MASTER-006`).

## Section 4 — Object Placement Rules
| Object type | Container |
|-------------|-----------|
| Persistent table | `{{Product}}_{{Module}}` |
| View | `{{Product}}_{{Module}}_V` |
| Stored procedure / function | `{{Product}}_{{Module}}` |
| Temporary/volatile | not persisted in a named container |

Rule A (container-discriminated): the container is the sole type discriminator; object names are
identical across the base and view containers; type markers (`v_`, `_vw`) are prohibited. View-tier
architecture: two tiers — a **governed** view (1:1 over its base table, may reference the base
container) and **access** views (reference the governed view only).

## Section 5 — Separation Policy
`STRICT_SEPARATION`. Tables and views live in separate databases so that consumers granted the view
database cannot reach the base tables. Exception: temporary/volatile objects.

## Section 6 — Derivation Function
```
derive_container(object_type, {product, module}, classification):
    base = product || '_' || module
    if object_type == VIEW: return base || '_V'
    else:                   return base
```
Examples: `derive_container(TABLE, {Customer360, Domain})` → `Customer360_Domain`;
`derive_container(VIEW, {Customer360, Domain})` → `Customer360_Domain_V`;
`derive_container(PROCEDURE, {Customer360, Memory})` → `Customer360_Memory`.

## Section 7 — Access Model
Role-based, granted at the container level. `{{Product}}_ROLE_READ` / `_AGENT` / `_ADMIN`
(see [access-layer](../access-layer/)). Consumers are granted the view database only. **Implied
grant:** the view-owning database requires cross-database rights on the base database before any view
compiles — provisioned before view creation, in the standard sequence.

## Section 8 — Validation Procedure
Agent-executable `DBC` checks (halt and report on any row returned):
- Objects exist in their intended databases (`DBC.TablesV` by `DatabaseName`/`TableKind`).
- No tables in `_V` databases; no views in base databases.
- No objects in parent databases.
- Consumer roles hold rights on `_V` databases only, not base databases (`DBC.AllRoleRightsV`).
- The implied cross-database grant is present.
