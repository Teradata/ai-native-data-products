---
title: PostgreSQL Domain Implementation
anchor: domain
type: implementation
status: draft
version: 2.0
normative: true
implements: domain
platform: postgres
---

# PostgreSQL: Domain

Binding of [Domain](../../../../design/modules/domain.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`01-tables.sql.j2` accepts arbitrary History, Reference and Association entities. Keymaps are permanent CURRENT_STATE tables; the physical entity references its stable id and natural key. PostgreSQL uses identity allocation; DuckDB uses sequences. `02-key-allocation.sql.j2` returns the permanent id with atomic upsert. DuckDB writers must serialize and retry conflicting transactions.

The temporal pattern supplies canonical fields and comments. SCD2 and bitemporal profiles are separate choices. Default views hide lifecycle/audit columns; historical functions/macros expose approved full history. Business attributes, keys, comments and placement are inputs; no service-desk or customer schema is built into the binding.

Checks cover expected physical columns and comments, finite timestamps, overlapping intervals and declared current relationships. Stable keymap references are enforced by foreign keys. Historical relationship coverage, domain-specific quality rules and no-content-duplication reviews still require the product's design checks.

## Capability bindings

| Capability | Binding |
|---|---|
| `SurrogateKeyAllocation` | Templates and enforcement limits described above. |
| `CurrentStateFilter` | Templates and enforcement limits described above. |
| `PointInTimeReconstruction` | Templates and enforcement limits described above. |
| `NaturalKeyLookup` | Templates and enforcement limits described above. |
| `EntityJoinBack` | Templates and enforcement limits described above. |
| `AccessView` | Templates and enforcement limits described above. |
| `RichMetadata` | Templates and enforcement limits described above. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-DOMAIN-001` | Per-entity metadata query checks physical comments. |
| `INV-DOMAIN-002,006` | Shared current/as-of templates; native two-axis reconstruction tests. |
| `INV-DOMAIN-003,004` | Permanent keymap/FK DDL; supplied identity/natural-key declarations. Retention is operational. |
| `INV-DOMAIN-005,007` | Review the product field/relationship declarations; no generic semantic duplication detector is claimed. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal/lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
