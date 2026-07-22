# Teradata — Semantic Module Implementation

Teradata binding of [`design/modules/semantic.md`](../../../../design/modules/semantic.md). Semantic
is the discovery map that provides `SemanticRegistration` and the product orientation layer. Read the
design document first. Replace `{{ product }}` with the product name; catalogue tables live in
`{{ product }}_Semantic`, the product registry in a shared `governance` container.

## Files

| File | Purpose |
|------|---------|
| `01-catalog-tables.sql` | `entity_metadata`, `column_metadata`, `naming_standard`, `table_relationship`. |
| `02-discovery-tables.sql` | `data_product_map`, `data_product_map_primary_objects`, `view_metadata`, `view_column_type`. |
| `03-registry.sql` | `governance.data_product_registry` — the orientation-layer anchor. |
| `04-path-discovery.sql` | `v_relationship_paths` — recursive multi-hop join-path discovery. |
| `05-column-catalogue.sql` | `column_catalogue` — live hybrid column catalogue with value provenance. |
| `06-orientation.md` | MCP resource/tool shapes and the discovery manifest (orientation layer). |
| `validation.sql` | Primary-object, view, and relationship-completeness checks (canonical validator sources). |

## Capability bindings

| Capability (design) | Teradata binding |
|---------------------|------------------|
| `SemanticRegistration` | On deploy, every module `INSERT`s its entity/column/relationship/primary-object rows into `{{ product }}_Semantic`. |
| Agent discovery | The catalogue tables + `v_relationship_paths` + `column_catalogue`; product-first via `governance.data_product_registry`. |
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

New catalogue tables use the canonical `created_dts`/`updated_dts` audit columns from the
[temporal-lifecycle pattern](../../patterns/temporal-lifecycle-metadata/); `temporal_pattern` on
`entity_metadata` carries each entity's temporal profile for the whole product.

## Invariants → checks

| Invariant | Check |
|-----------|-------|
| `INV-SEMANTIC-003` (registered primary objects, verbatim identity) | `validation.sql` — orphan modules, missing/kind-mismatched objects, invalid roles, duplicates. |
| `INV-SEMANTIC-005` (relationship completeness) | `validation.sql` — isolated entities; path existence per expected pair. |
| `INV-SEMANTIC-007` (one primary per base table) | `validation.sql` — more than one active primary exposure per base table. |
