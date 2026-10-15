---
title: Teradata Semantic Module Implementation
anchor: semantic
type: implementation
status: draft
version: 3.0
normative: true
implements: semantic
platform: teradata
---

# Teradata: Semantic

Binding of [Semantic](../../../../design/modules/semantic.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`01-tables.sql.j2` calls `module_tables('semantic')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md) for the catalogue relations the Semantic standard defines and the resolver places.

`02-registration.sql.j2` writes the product's description of itself, each block only where its relation is placed:

- the product registry row from `product` (code, name, description, domain, version, owner, trust producer) and `orientation.access_mode`, with the manifest's consumer view as the approved entry point;
- the module map from `module_containers`, for object types the relation's vocabulary permits;
- the standard declaration: one `StandardDeclaration` row each for the standard, every deployed module and every applied pattern, from `standard.declarations`, with the platform and `standard.version`;
- entity and column metadata for every placed relation in `entities` and `relations`: the logical identity (`module.entity`, from `logical_id`, never a container or a prefix) as `entity_name`, placement, kind, profile, current and deleted flag columns, and per column the logical name, description, sensitivity marker, `classification`, `required`, declared type and Enum members;
- a `KeyDefinition` row for each of an entity's `key_defs` (surrogate, natural) and a `KeyColumn` row per ordered column, so a composite key is ordered rows and no delimited list;
- table relationships from `relationships`, between the logical identities of the source and target entities, and a `RelationshipColumn` row per ordered column pair (`pairs`). A nested `m.ref` is not supported inside a match, so the key of an entity is found by an explicit subselect (`key_ref`);
- access objects for every placed object of each relation, each with its `object_identity` (`module.entity:base`, `:governed` or `:current`; `module:object` for a similarity procedure), the logical `represents_entity` and `resolves_to_object`, with consumer views marked agent-consumable, and an `AccessColumn` row per column of each consumer view, from the same `view_columns` list the view selects;
- primary objects for every placed object with a `primary_role`;
- the orientation sequence from `orientation.resources`;
- metrics from `metrics`, with the rendered measure and filter as a Teradata expression and the dataset's consumer view;
- entity and column synonyms;
- naming standards from `naming`: each object template, the attribute template and each standard-name mapping.

Composite access objects (`access_objects`) are not registered; the manifest reports each as a gap.

`03-discovery.sql.j2` creates the standard-owned discovery views with `REPLACE VIEW` and `LOCKING ROW FOR ACCESS`, each only where the composition places it and the relations it reads:

- `ColumnCatalogue`: `DBC.ColumnsV` for the product's databases, left-joined to column metadata, with `description_source` `authored` or `missing`;
- `DataProductManifest`: the active registry row with one column per orientation resource role;
- `RelationshipPaths`: rows, one per step and key position, in the standard's column order (`path_id`, `origin_entity`, `destination_entity`, `hop_count`, `hop`, `key_ordinal`, `from_entity`, `from_column`, `to_entity`, `to_column`, `relationship_id`, `direction`). A leg is the relationship id followed by `>` (forward) or `<` (reverse) and `path_id` is the legs joined; the bound is `max_hops` (four) and a path never revisits an entity. Teradata views take no recursion or `WITH` clause and have no arrays, so each (path length, position) is its own branch of a `UNION ALL`, unrolled from the context's bound, with `path_id` built as text by concatenating each step's leg. Paths join the logical entities; resolve them through the access objects before issuing consumer SQL;
- `DataProductManifest` ends with `standard_version`, the version of the active `STANDARD` declaration row;
- `LineageGraph` and `LineageRunLatest` over Observability's active lineage definitions and their runs, the latest run chosen with `QUALIFY`.

Every text column a union produces is cast, because a union takes its column types from its first branch. Every view and every view column carries a comment.

`contract/` holds the five metadata-contract checks, declared as `contract <kind>` in the platform profile and rendered once for the Semantic module. Each returns one row per defect, as `object_identity` and `defect`:

| Check | Template | Returns |
|---|---|---|
| `contract-identity` | `contract/identity.sql.j2` | an entity identity outside the `module.entity` grammar (`REGEXP_SIMILAR`, case-sensitive) or outside its own module, a duplicate identity, an access identity that breaks the grammar or does not match its entity and surface (`INV-SEMANTIC-016`) |
| `contract-keys` | `contract/keys.sql.j2` | an entity with no key, a key with no columns, ordinals not running 1 to n, a key column absent from the entity (`INV-SEMANTIC-017`) |
| `contract-relationships` | `contract/relationships.sql.j2` | a relationship with no column pair, ordinals not running 1 to n, an unregistered entity, a pair column absent from its entity (`INV-SEMANTIC-018`) |
| `contract-access-columns` | `contract/access-columns.sql.j2` | a consumer view column with no mapping, a mapping naming no column or repeated, ordinals not running 1 to n, an absent non-derived source (`INV-SEMANTIC-019`) |
| `contract-composition` | `contract/composition.sql.j2` | a composite without exactly one anchor, members not ordered 1 to n, a member not joined to a prior member, an anchor carrying a join (`INV-SEMANTIC-020`) |

Columns of tables and views are read from `DBC.ColumnsV`; the shared macros are in `contract/00-macros.sql.j2`. The build does not execute Teradata, so these are verified by rendering, and by the shared engine tests when a system is attached.

`validation.sql.j2` is the `module semantic` check: every table in a database the product places objects in (`DBC.TablesV`, kinds `T` and `O`), keymaps included, is registered in entity metadata.

Registration uses the placement and relationships the context carries, never name inference. Structural facts come from the `DBC` dictionary views; meanings come from the specification.

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
| `INV-SEMANTIC-016..020` | The five `contract-*` checks, one mutation test each in the shared engine tests (skipped without a Teradata system). |
| `INV-SEMANTIC-013..015` | Metrics and synonyms registered from the specification; metric recipes execute in engine tests. Reference checks over the registrations remain to be written. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
