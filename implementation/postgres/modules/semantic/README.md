---
title: PostgreSQL Semantic Implementation
anchor: semantic
type: implementation
status: draft
version: 2.0
normative: true
implements: semantic
platform: postgres
---

# PostgreSQL: Semantic

Binding of [Semantic](../../../../design/modules/semantic.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`entities.json` declares standard-owned catalogue entities; it is not a business model. `01-tables.sql.j2` uses the same physical and temporal macros as other modules. `02-registration.sql.j2` registers the supplied entities, keymaps, relationships, profiles, comments and consumer surfaces. `03-discovery.sql.j2` publishes a manifest, hybrid column catalogue and bounded relationship paths.

Registration uses explicit placement and declared relationships, never name inference. Structural facts come from information_schema; business meanings come from authored metadata. Relationship paths describe base-entity joins and must be resolved through access_object before consumer SQL is issued. Object registries contain datasets, never business instances.

`validation.sql.j2` detects unregistered persisted tables in the supplied module containers. Per-entity checks verify column existence and comments. Metric, synonym, primary-object and model registrations are standard-owned schemas ready for product capture; the helper does not invent their content or certify semantic completeness.

## Capability bindings

| Capability | Binding |
|---|---|
| `SemanticRegistration` | Templates and enforcement limits described above. |
| `RichMetadata` | Templates and enforcement limits described above. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEMANTIC-001,002` | Standard-owned catalogue schema; no business-instance registration. |
| `INV-SEMANTIC-003,006` | Deployment registration plus unregistered-table check. |
| `INV-SEMANTIC-004,011,012` | Derived manifest and explicit orientation; consumer workflow verification remains required. |
| `INV-SEMANTIC-005,007..010` | Declared relationships and access rows; completeness/standalone/composite review remains required. |
| `INV-SEMANTIC-013..015` | Schemas support metrics/synonyms; product registration and reference checks remain required. |
| `INV-SEMANTIC-016,017` | `validation-layout.sql.j2` (check `semantic:layout`): registry without platform or standard version (`LAYOUT_NOT_DECLARED`); consumer view without audience; audience on another object type. The check of two consumer views sharing an audience and semantics is an outstanding gap: this binding registers one consumer view per entity. |

This binding has no `ACCESS` layer object: its layer roles are `STORAGE` (`object_type` `TABLE`, `access_role` `BASE`) and `CONSUMER` (`CONSUMER_VIEW`, `PASSTHROUGH`). `data_product_registry.platform_profile` is `postgres` and `standard_version` is read from the Master Design by the renderer.

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal/lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
