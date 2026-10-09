---
title: DuckDB Semantic Implementation
anchor: semantic
type: implementation
status: draft
version: 2.0
normative: true
implements: semantic
platform: duckdb
---

# DuckDB: Semantic

Binding of [Semantic](../../../../design/modules/semantic.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`entities.json` declares standard-owned catalogue entities; it is not a business model. `01-tables.sql.j2` uses the same physical and temporal macros as other modules. `02-registration.sql.j2` registers the supplied entities, keymaps, relationships, profiles, comments and consumer surfaces. `03-discovery.sql.j2` publishes a manifest, hybrid column catalogue and bounded relationship paths (a recursive view using DuckDB list functions).

Registration uses explicit placement and declared relationships, never name inference. Structural facts come from `information_schema` restricted to the product's database; business meanings come from authored metadata. Relationship paths describe base-entity joins and must be resolved through access_object before consumer SQL is issued. Object registries contain datasets, never business instances. Because DuckDB cannot comment on schemas, module descriptions live in Semantic rows rather than in catalogue comments.

`validation.sql.j2` detects unregistered persisted tables in the supplied module containers. Per-entity checks verify column existence and comments. Metric, synonym, primary-object and model registrations are standard-owned schemas ready for product capture; the helper does not invent their content or certify semantic completeness. The earlier DuckDB reference's fixed catalogue-consistency checks (for example metric and synonym reference checks) are not carried; see [conformance scope](../../CONFORMANCE.md).

## Capability bindings

| Capability | Binding |
|---|---|
| `SemanticRegistration` | Generated registration inserts for modules, entities, columns, access objects, relationships and orientation. No consumer-time DDL parsing. |
| `RichMetadata` | `COMMENT ON` for physical objects, plus curated column and entity metadata in explicit registries. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEMANTIC-001,002` | Standard-owned catalogue schema; no business-instance registration. |
| `INV-SEMANTIC-003,006` | Deployment registration plus unregistered-table check, mutation-tested. |
| `INV-SEMANTIC-004,011,012` | Derived manifest and explicit orientation; consumer workflow verification remains required. |
| `INV-SEMANTIC-005,007..010` | Declared relationships and access rows; completeness, standalone and composite review remains required. |
| `INV-SEMANTIC-013..015` | Schemas support metrics and synonyms; product registration and reference checks remain required. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal and lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
