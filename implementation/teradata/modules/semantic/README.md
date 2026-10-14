---
title: Teradata Semantic Module Implementation
anchor: semantic
type: implementation
status: standard
version: 2.0
normative: true
implements: semantic
platform: teradata
---

# Teradata: Semantic Module Implementation

Teradata binding of [`design/modules/semantic.md`](../../../../design/modules/semantic.md). Semantic is the discovery map that provides `SemanticRegistration` and the product orientation layer. Read the design document first. Replace `{{ product }}` with the product name; catalogue tables live in `{{ product }}_Semantic`, the product registry in a shared `governance` container.

## Files

| File | Purpose |
|------|---------|
| `01-catalog-tables.sql.j2` | `entity_metadata`, `key_definition`, `key_column`, `column_metadata`, `naming_standard`, `table_relationship`, `relationship_column`. |
| `02-discovery-tables.sql.j2` | `data_product_map`, `data_product_map_primary_objects`, `view_metadata`, `view_column_type`, `standard_declaration`. |
| `03-registry.sql.j2` | `governance.data_product_registry`: the orientation-layer anchor. |
| `04-path-discovery.sql.j2` | `relationship_edges` (one row per direction per key position) and `relationship_paths` (bounded, cycle-free multi-hop paths as rows). |
| `05-column-catalogue.sql.j2` | `column_catalogue`: live hybrid column catalogue with value provenance. |
| `06-orientation.md` | MCP resource/tool shapes and the discovery manifest (orientation layer). |
| `07-access-object.sql.j2` | `access_object`, `access_composition`, `access_column`: the access-object layer (which object a consumer queries, what composites encapsulate, where each output column comes from). |
| `07-metric-tables.sql.j2` | `metric_metadata`, `metric_expression`, `metric_dataset`, `semantic_synonym`. |
| `08-access-relationship-paths.sql.j2` | `access_relationship_paths`: `relationship_paths` rows with each step endpoint resolved to a consumable object. |
| `09-orientation-manifest.sql.j2` | `data_product_orientation` (ordered resource relation) and `data_product_manifest` (generated view over registry, orientation and the `STANDARD` declaration; `standard_version` is its last column). |
| `validation.sql.j2` | Canonical validator sources: primary-object, view, relationship, access-object, orientation, metric, synonym, identity, key, relationship-column, access-column and composition checks. |

## Metadata contract 2.0.0

| Change | Teradata shape |
|--------|----------------|
| Logical identities | `entity_metadata.entity_name` is `module.entity` (lower case, no container). `access_object.object_identity` is `module.entity:surface`, `module:object` or `composite:name`; its location stays in `database_name` and `object_name`. `data_product_map_primary_objects` gains `object_identity` beside its verbatim location. Every identity-bearing reference (`source_entity`, `target_entity`, `member_entity`, `represents_entity`, `resolves_to_object`, `metric_dataset.entity_name`, `semantic_synonym.object_name`, `composite_object`) holds the logical identity. |
| Grouped keys | `key_definition` (`entity_name#role`) and `key_column` (ordered). The single-column key columns of `entity_metadata` are gone. |
| Join groups | `table_relationship` names the two entities; `relationship_column` holds the ordered column pairs. |
| Paths as rows | `relationship_paths` columns, in order: `path_id`, `origin_entity`, `destination_entity`, `hop_count`, `hop`, `key_ordinal`, `from_entity`, `from_column`, `to_entity`, `to_column`, `relationship_id`, `direction`. `path_id` is the legs of the path, each a relationship id and `>` (FORWARD) or `<` (REVERSE), such as `12>7<`. Four hops at most; no entity is revisited. No concatenated join string exists. |
| Composites | `access_composition.via_relationship_id` and `via_direction` replace `join_path`; `member_seq` runs from 1. |
| Column mappings | `access_column`: one row per output column, `mapping_kind` of `PASSTHROUGH`, `RENAMED` or `DERIVED`. |
| Declaration | `standard_declaration` (component kind `STANDARD`, `MODULE` or `PATTERN`); the manifest reads the `STANDARD` row. Registration, a builder step, writes the rows. |

Renamed views: `v_relationship_paths` is `relationship_paths` and `v_access_relationship_paths` is `access_relationship_paths`.

## Capability bindings

| Capability (design) | Teradata binding |
|---------------------|------------------|
| `SemanticRegistration` | On deploy, every module `INSERT`s its entity/column/relationship/primary-object rows into `{{ product }}_Semantic`. |
| Agent discovery | The catalogue tables + `relationship_paths` + `column_catalogue`; product-first via `governance.data_product_registry`. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN` on every catalogue object. |

## Logical-type bindings used here

| Logical type | Teradata type |
|--------------|---------------|
| `Identifier` | `INTEGER GENERATED ALWAYS AS IDENTITY` |
| `NaturalKey` / `ShortText` / `Text` | `VARCHAR(n)` |
| `LongText` | `CLOB` |
| `Json` | `JSON` |
| `Enum{…}` | `VARCHAR(n)` with a documented value set |
| `Flag` | `BYTEINT` with `CHECK (col IN (0,1))` |
| `Timestamp` | `TIMESTAMP(6) WITH TIME ZONE` |

New catalogue tables use the canonical `created_dts`/`updated_dts` audit columns from the [temporal-lifecycle pattern](../../patterns/temporal-lifecycle-metadata/); `temporal_pattern` on `entity_metadata` carries each entity's temporal profile for the whole product.

## Invariants → checks

| Invariant | Check |
|-----------|-------|
| `INV-SEMANTIC-003` (registered primary objects, verbatim identity) | `validation.sql.j2`: orphan modules, missing/kind-mismatched objects, invalid roles, duplicates. |
| `INV-SEMANTIC-005` (relationship completeness) | `validation.sql.j2`: isolated entities; path existence per expected pair. |
| `INV-SEMANTIC-007` (one primary per base table) | `validation.sql.j2`: more than one active primary exposure per base table. |
| `INV-SEMANTIC-008` (resolve through the registry) | `validation.sql.j2`: registered access object not deployed. |
| `INV-SEMANTIC-009` (consumable objects resolve to a catalogued entity) | `validation.sql.j2`: non-composite with no entity; `represents_entity` / `member_entity` not catalogued. |
| `INV-SEMANTIC-010` (composite structure recorded, one anchor) | `validation.sql.j2`: COMPOSITE without a composition; composition without exactly one `ANCHOR`. |
| `INV-SEMANTIC-011` (ordered orientation, trust map first) | `validation.sql.j2`: missing required role, duplicate role, duplicate order, undeployed object, unordered trust map. Also `VAL-13`: the registry names the trust-authoritative producer. |
| `INV-SEMANTIC-012` (manifest generated, cannot drift) | `validation.sql.j2`: a manifest entrypoint with no backing active orientation row. |
| `INV-SEMANTIC-016` (identity grammar, no container, unique) | `validation.sql.j2`: malformed entity or access identity, identity containing a container name, duplicate entity identity. |
| `INV-SEMANTIC-017` (keys) | `validation.sql.j2`: entity with no `SURROGATE` key, key with no columns or ordinal gaps, key column missing from the entity table. |
| `INV-SEMANTIC-018` (relationship columns) | `validation.sql.j2`: relationship with no column pair or ordinal gaps, column missing from its entity table. |
| `INV-SEMANTIC-019` (access columns) | `validation.sql.j2`: output column with no mapping, duplicate or orphan mapping, non-derived source missing. |
| `INV-SEMANTIC-020` (composite structure) | `validation.sql.j2`: not exactly one `ANCHOR`, `member_seq` gaps, `via_relationship_id` that does not join the member to a prior member. |

The checks read `DBC.ColumnsV` for physical columns and use `REGEXP_SIMILAR` for the identity grammar. Each returns zero rows for a conforming deployment. Rendering is verified by `tooling/validation/tests`; execution on Teradata has not been run.
