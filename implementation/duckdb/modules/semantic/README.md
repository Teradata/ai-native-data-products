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

## Templates

`01-tables.sql.j2` calls `module_tables('semantic')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md) for the catalogue relations the Semantic standard defines and the resolver places.

`02-registration.sql.j2` writes the product's description of itself, each block only where its relation is placed:

- the product registry row from `product` (code, name, description, domain, version, owner, trust producer) and `orientation.access_mode`, with the manifest's consumer view as the approved entry point;
- the module map from `module_containers`, for object types the relation's vocabulary permits;
- entity and column metadata for every placed relation in `entities` and `relations`: placement, kind, profile, surrogate and natural columns, current and deleted flag columns, and per column the logical name, description, sensitivity marker, `classification`, `required`, declared type and Enum members;
- table relationships from `relationships`, by base table;
- access objects for every placed object of each relation and for each similarity macro in `embeddings`, with consumer views and macros marked agent-consumable;
- primary objects for every placed object with a `primary_role`;
- the orientation sequence from `orientation.resources`;
- metrics from `metrics`, with the rendered measure and filter as a DuckDB expression and the dataset's consumer view;
- entity and column synonyms;
- naming standards from `naming`: each object template, the attribute template and each standard-name mapping.

Composite access objects (`access_objects`) are not registered; the manifest reports each as a gap. DuckDB cannot comment on schemas, so module descriptions live in Semantic rows.

`03-discovery.sql.j2` creates the standard-owned discovery views, each only where the composition places it and the relations it reads:

- `ColumnCatalogue`: `information_schema.columns` for the product's schemas, left-joined to column metadata, with `description_source` `authored` or `missing`;
- `DataProductManifest`: the active registry row with one column per orientation resource role;
- `RelationshipPaths`: a recursive view, using DuckDB list functions, over active table relationships in both directions, up to the Semantic standard's bound of four hops (the context's `max_hops`) without revisiting a table. Paths join base tables; resolve them through the access objects before issuing consumer SQL;
- `LineageGraph` and `LineageRunLatest` over Observability's active lineage definitions and their runs.

`validation.sql.j2` is the `module semantic` check: every base table in a schema the product places objects in, keymaps included, is registered in entity metadata.

**The metadata contract (release 2.0.0).** Registration writes the logical identity of each entity (`module.entity`) and, beside it, its location; the key definitions and their ordered key columns; one relationship column pair per join column; one access object per placed object, identified by entity and surface; one access-column mapping row per output column of each consumer view over an entity (the context's `view_columns`, which the view itself selects); and the `StandardDeclaration` rows from `standard`. `RelationshipPaths` returns one row per path step and key position, bounded to four hops. The manifest's last column is `standard_version`. The five checks under [`contract/`](contract/) test `INV-SEMANTIC-016` to `020`; they are declared as `contract` checks and read only registered metadata and the catalogue.

Registration uses the placement and relationships the context carries, never name inference. Structural facts come from `information_schema`, filtered by schema name only, not by `current_database()`; meanings come from the specification.

## Capability bindings

| Capability | Binding |
|---|---|
| `SemanticRegistration` | Registration inserts for the product, modules, entities, columns, relationships, access and primary objects, orientation, metrics, synonyms and naming standards. |
| `RichMetadata` | `COMMENT ON` for physical objects, plus authored entity and column metadata and the hybrid column catalogue. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEMANTIC-001,002` | Standard-owned catalogue structures; registries hold datasets, never business instances. |
| `INV-SEMANTIC-003,006` | Registration at deployment; `module semantic` check, with an engine test that an unregistered table is found. |
| `INV-SEMANTIC-004,011,012` | Manifest view over the registry and orientation sequence; consumer workflow verification remains required. |
| `INV-SEMANTIC-005,007..010` | Declared relationships and access objects; composite access objects are not rendered. |
| `INV-SEMANTIC-013..015` | Metrics and synonyms registered from the specification; metric recipes execute in engine tests. Reference checks over the registrations remain to be written. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
