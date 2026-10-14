---
title: DuckDB Domain Implementation
anchor: domain
type: implementation
status: draft
version: 2.0
normative: true
implements: domain
platform: duckdb
---

# DuckDB: Domain

Binding of [Domain](../../../../design/modules/domain.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`01-tables.sql.j2` calls `module_tables('domain')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). It emits one `CREATE TABLE` per persisted Domain relation in the context's `entities` and `relations`, keymaps first so references to them resolve, and skips any the context marks `adopted` or not `defined`. It reads each relation's `objects.table`, `objects.sequence`, `columns` (physical name and type, `required`, `unique`, `members`), `key_columns`, `version_columns`, `column_names`, `history`, `bitemporal`, `supports_deletion` and `identity.keymap`.

- A relation with an `objects.sequence` (a keymap, or an inline-keyed table such as a Reference entity) gets `CREATE SEQUENCE` with the name and schema the profile places, and its key column defaults to `nextval` of it.
- An entity with a keymap gets a foreign key from its key columns to the keymap's table.
- An Enum attribute gets a `CHECK` over its members.
- A history table's primary key is its version columns plus `valid_from_dts` (and `transaction_from_dts` when bitemporal). DuckDB has no partial unique indexes or exclusion constraints, so one open version per identity and non-overlapping intervals are proved by the `entity temporal` check, not enforced by the engine.

`02-key-allocation.sql.j2` is caller-rendered with `keymap` (a Keymap entity from the context) and `natural_value`. It inserts the natural value and returns the stable identifier; an existing natural value returns its existing identifier unchanged through `ON CONFLICT`. Only the first natural-key attribute (`identity.natural[0]`) is used. The caller opens the transaction on the single writing connection and retries a transaction conflict. An allocation that meets an existing mapping can still consume a sequence value, so identifiers are unique and never reused but not contiguous.

Comments, consumer views and point-in-time table macros come from the temporal pattern; registration from Semantic; checks from Validation.

## Capability bindings

| Capability | Binding |
|---|---|
| `SurrogateKeyAllocation` | Sequence default on each keymap or inline-keyed table; `02-key-allocation.sql.j2` returns the permanent identifier. Serial writer; administrative SQL can bypass it. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `PointInTimeReconstruction` | Table macro `(valid_at)` or `(valid_at, known_at)` per relation the context gives a `function` object. |
| `NaturalKeyLookup` | Unique natural key on each keymap; consumer views carry the stable identifier. |
| `EntityJoinBack` | Search and Prediction rows carry the Domain identifier; consumers join to the Domain consumer view. |
| `AccessView` | One consumer view per relation with a `consumer_view` object; an interface, not a security boundary. |
| `RichMetadata` | `COMMENT ON` for every table and column, plus Semantic registration. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-DOMAIN-001` | `entity metadata` check: every placed column exists and carries a comment in `duckdb_columns()`. |
| `INV-DOMAIN-002,006` | Current and point-in-time macros; `entity temporal` check; engine test of a bitemporal correction read at two knowledge times. |
| `INV-DOMAIN-003,004` | Permanent keymap with foreign key; allocation test. Retention is operational. |
| `INV-DOMAIN-005,007` | Review the specification's attributes and relationships; no generic duplication detector is claimed. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
