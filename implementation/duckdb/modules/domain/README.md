---
title: DuckDB Domain Module Implementation
anchor: domain
type: implementation
status: standard
version: 2.0
normative: true
implements: domain
platform: duckdb
---

# DuckDB Domain

Binding of [Domain](../../../../design/modules/domain.md). [schema.sql](schema.sql) is generated from [model.py](../../model.py). The reusable entity compiler produces permanent keymaps, SCD2 tables, explicit current views, column comments and as-of table macros. The example instantiates Customer, Account, Transaction and the versioned Product reference set; Account carries the Customer-to-Product association.

**Provides:**

| Capability | Binding |
|---|---|
| `EntityJoinBack` | Stable ids referenced by Search/Prediction; live content joins. |
| `CurrentStateFilter` | `v_customer`, `v_account`, `v_transaction`, `v_product`. |
| `PointInTimeReconstruction` | `at_customer(t)` and corresponding macros. |
| `NaturalKeyLookup` | Unique natural key in each permanent keymap. |
| `SoftDelete` | Versioned tombstone retained in full table. |
| `AccessView` | Explicit current projections hide lifecycle/audit fields. |

**Requires:**

| Capability | Strength | Provider | Binding |
|---|---|---|---|
| `SurrogateKeyAllocation` | hard | self | Transactional keymap allocator in temporal.py. |
| `RichMetadata` | hard | platform | Comments before dependent objects. |
| `MetadataCoverageCheck` | hard | self | Catalogue/curated metadata anti-joins. |
| `SemanticRegistration` | soft | Semantic | Complete generated deployment registration. |
| `DocumentationCapture` | soft | Memory | Decisions, glossary, recipes and release records. |

The [temporal writer](../../temporal.py) is the maintenance interface. Stable allocation is separate from version insertion; a changed natural key is rejected. Foreign references to a history table are checked on current/as-of surfaces rather than pretending a nonunique history id can be a SQL foreign key. `C360-DOM-KEY-*`, `JOIN-*`, `META-*` and temporal checks exercise the invariants. Cross-module allowlists and search/prediction tests guard content ownership. Real audit event capture remains a writer obligation; a SQL admin can bypass the maintenance interface.
