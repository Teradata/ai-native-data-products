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

`01-tables.sql.j2` accepts arbitrary History, Reference and Association entities. Keymaps are permanent CURRENT_STATE tables; the physical entity references its stable id and natural key by composite foreign key. Allocation uses a DuckDB sequence named by the build context (`key_sequence`). `02-key-allocation.sql.j2` is an upsert that returns the permanent identifier of an existing mapping or allocates a new one. A replayed allocation can consume a sequence value, so identifiers are unique and never reused but not contiguous. DuckDB writers must run on one writing connection, serialize transactions and retry a transaction conflict.

The temporal pattern supplies canonical fields and comments. SCD2 and bitemporal profiles are separate choices. Default views hide lifecycle and audit columns; historical table macros expose the approved full history. Business attributes, keys, comments and placement are inputs; no service-desk, laboratory or customer schema is built into the binding.

Checks cover expected physical columns and comments, finite timestamps, overlapping intervals and declared current relationships. Stable keymap references are enforced by foreign keys. Historical relationship coverage, domain-specific quality rules and no-content-duplication reviews still require the product's design checks.

## Capability bindings

| Capability | Binding |
|---|---|
| `SurrogateKeyAllocation` | Permanent keymap with sequence default; `02-key-allocation.sql.j2` returns the stable id. Serial writer; arbitrary administrative SQL can bypass it. |
| `CurrentStateFilter` | Explicit access views over open validity, current flag and deletion state. |
| `PointInTimeReconstruction` | Half-open table macros `(valid_at)` or `(valid_at, known_at)`, selected by profile. |
| `NaturalKeyLookup` | Unique natural key in each keymap; current views carry the stable id. |
| `EntityJoinBack` | Identifier joins from Search and Prediction to the Domain consumer views. |
| `AccessView` | Explicit projections; a view is an interface, not a security boundary. |
| `RichMetadata` | `COMMENT ON` for every table and column, applied by `02-comments.sql.j2`, plus Semantic registration. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-DOMAIN-001` | Per-entity metadata query checks physical comments through `duckdb_columns()`. |
| `INV-DOMAIN-002,006` | Shared current/as-of templates; native half-open and two-axis reconstruction tests. |
| `INV-DOMAIN-003,004` | Permanent keymap and foreign-key DDL; allocation test. Retention is operational. |
| `INV-DOMAIN-005,007` | Review the product field and relationship declarations; no generic semantic-duplication detector is claimed. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal and lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
