# Teradata — Domain Module Implementation

Concrete Teradata binding of [`design/modules/domain.md`](../../../../design/modules/domain.md).
The design document owns *what* and *why*; the files here own *how* on Teradata. Read the
design document first — this directory only adds platform specifics.

## Files

| File | Purpose |
|------|---------|
| `01-keymap.sql.j2` | Surrogate-key allocation table (`SurrogateKeyAllocation` binding). |
| `02-entity.sql.j2` | Core History entity table — bi-temporal columns, current/deleted flags, full column metadata. |
| `03-reference.sql.j2` | Reference data table (controlled vocabularies). |
| `04-relationship.sql.j2` | Associative relationship table. |
| `05-views.sql.j2` | Standard `_Current` / `_Enriched` views (`AccessView` binding). |
| `validation.sql` | Runnable checks for the module's invariants (`MetadataCoverageCheck` and others). |

The `.sql.j2` files are Jinja2 templates rendered by `tooling/compiler`. Each declares its
template variables in a header comment.

## Capability bindings

Every capability required by the design document is bound here:

| Capability (design) | Teradata binding |
|---------------------|------------------|
| `SurrogateKeyAllocation` | `_Keymap` table with `GENERATED ALWAYS AS IDENTITY`; the stable `{entity}_id` is looked up from the keymap on load, never generated on the `_H` table. |
| `CurrentStateFilter` | `WHERE is_current = 1 AND is_deleted = 0`. |
| `PointInTimeReconstruction` | Bi-temporal predicate on `valid_from_dts` / `valid_to_dts` (period containment). |
| `NaturalKeyLookup` | Equality predicate on `{entity}_key`, current-filtered. |
| `EntityJoinBack` | `INNER JOIN Domain.{Entity}_H ON {entity}_id`, current-filtered. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN` for every object and column. |
| `AccessView` | `{Entity}_Current` and `{Entity}_Enriched` views with explicit column lists. |
| `MetadataCoverageCheck` | Catalogue query over `DBC.ColumnsV` (see `validation.sql`). |

## Logical-type bindings used here

| Logical type (design) | Teradata type |
|-----------------------|---------------|
| `Identifier` | `BIGINT` (allocated via keymap) |
| `NaturalKey` | `VARCHAR(n)` |
| `Reference -> E` | `BIGINT` |
| `Code` | `VARCHAR(n)` |
| `ShortText` / `Text` / `LongText` | `VARCHAR(n)` |
| `Integer` | `INTEGER` |
| `Timestamp` | `TIMESTAMP(6) WITH TIME ZONE` |
| `Date` | `DATE` |
| `Flag` | `BYTEINT` |

## Invariants → checks

| Invariant | Check |
|-----------|-------|
| `INV-DOMAIN-001` (every attribute has metadata) | `validation.sql` §1 — zero uncommented columns. |
| `INV-DOMAIN-002` (current filter) | `_Current` views exist and apply the flag filter. |
| `INV-DOMAIN-003` (stable surrogate) | Keymap allocation; `{entity}_id` not `GENERATED` on `_H`. |
| `INV-DOMAIN-004` (identity shape) | `validation.sql` §2 — every `_H` table has `{entity}_id` + `{entity}_key`. |
| `INV-DOMAIN-005` (no duplicated content) | Reviewed at design time; other modules store `{entity}_id` only. |
| `INV-DOMAIN-006` (point-in-time) | Bi-temporal columns present on `_H` tables. |
| `INV-DOMAIN-007` (named references) | Reference columns named `{target}_id`, not `fk1`/`fk2`. |
