---
title: Teradata Enterprise Catalogue Interface Implementation
anchor: catalogue-interface
type: implementation
status: draft
version: 1.0
normative: true
implements: catalogue-interface
platform: teradata
---

# Teradata: Enterprise Catalogue Interface

Teradata binding of [`design/patterns/catalogue-interface.md`](../../../../design/patterns/catalogue-interface.md). Read the pattern first. Targets Teradata v17.20+; the dictionary check uses `DBC.TablesV`.

## Files

| File | Purpose |
|------|---------|
| `01-container-interface-tables.sql` | The two child feeds: `data_product_container` (where the product is deployed) and `data_product_interface` (what a consumer may query). |
| `02-lifecycle-dml.sql` | One parameterised transition covering every lifecycle event, plus first registration and the two feed refreshes. |
| `03-catalogue-views.sql` | The five surfaces a catalogue reads. |
| `04-resolution-queries.sql` | Orientation, the consumer object list from both the feed and the product's Semantic catalogue, the projection that populates the feed, the change query, and point-in-time. |
| `05-semantic-model-export.sql` | The six extractions that make up a product's semantic model, plus the product descriptor reads. |
| `EMITTERS.md` | What the two YAML renderers must produce from those extractions, and how they behave when something is missing. |
| `conformance-queries.sql` | One check per invariant; every query is expected to return zero rows. |

The registry table is defined by the Semantic module at [`modules/semantic/03-registry.sql`](../../modules/semantic/03-registry.sql), since the orientation layer owns it. This pattern amended that file rather than declaring a second copy.

## Registry 2.0

| Change | Reason |
|---|---|
| `SCD2_HISTORY` profile with logical deletion | A status transition previously overwrote the row, leaving only the latest state and an `updated_dts`. Nothing downstream could tell a retired product from one never registered, or answer what was published last quarter. |
| `owner_name`, `owner_email`, `technical_contact_name`, `technical_contact_email` | `owner_team` was the only ownership field. An enterprise catalogue needs a contact name and address, and there was nowhere to read them from. |
| `product_domain` | The catalogue renderer emits a `domain` and the registry had no column to supply it. |
| `data_product_container` | The three `*_database` columns covered three of six modules and one of several layers. Sites place containers where their standards say, which a fixed column per module cannot describe. |

**Migration.** The temporal columns are additions. Migrate an existing registry by adding them and stamping the surviving row as the first version: `valid_from_dts` from `created_dts`, `valid_to_dts` the open-end sentinel, `is_current` 1. History before the migration is not reconstructable, and the migrated row states its start as the instant the row was created.

**Clients must now filter on `is_current`.** A client filtering on `is_active = 1 AND is_deleted = 0` will match every historical version of every product. Read `governance.data_product_current` instead, which applies the predicate.

## Binding table

| Pattern concept | Teradata binding |
|-----------------|------------------|
| Product feed | `governance.data_product_catalogue` over the registry, current versions including retired. |
| Lifecycle feed | `governance.data_product_lifecycle`, predecessor state derived with `LAG`. |
| Interface feed | `governance.data_product_interface`, projected from the product's Semantic view and primary-object catalogues. |
| Container feed | `governance.data_product_container`, one row per (product, module, layer). |
| Detail pointers | The `*_uri` columns on the registry, carried forward by every transition. |
| Versioning and deletion | `SCD2_HISTORY` with `supports_deletion`, from the `temporal-lifecycle-metadata` pattern. |
| Single resolved contact | `contact_name` / `contact_email` on the product feed: business owner, technical contact as fallback. |

Both feed tables spell their temporal block out instead of importing `00-temporal-macros.sql.j2`. They live in the shared governance container and take no product variable, so they are plain `.sql` for the same reason the registry is; the temporal pattern's binding lists this case. The `tlm-04` check in `tooling/validation/design_lint.py` covers them, and the block matches what the macros emit for `columns('SCD2_HISTORY', supports_deletion=true)`.

## Resolving the consumer surface

Two routes to the same list.

**From the governance container**, for any product, without reaching into it: `governance.data_product_consumer_interface` returns fully qualified object names assembled from declared containers. This is what a catalogue publishes.

**From inside the product**, authoritatively: the Semantic module's `view_metadata` joined to `entity_metadata` and `data_product_map_primary_objects`, with `view_type <> 'LOCKING'`. `view_metadata` says which view exposes which base table and which exposure is primary; the primary-object registry says how an agent should use an object. An object in neither is not a consumer surface.

Neither route resolves anything from a name. `view_type`, `object_role` and `interface_layer` carry as data what a suffix would otherwise carry by convention, so a site using layer-named containers and a site using cost-centre names return identical results.

## Known divergence: automated registration

Release packaging tooling that generates a product's registration script against the version 1.0 registry needs updating. Three behaviours no longer match:

1. **It upserts on `product_id` alone.** `MERGE … ON (tgt.product_id = src.product_id)` against a versioned registry matches every version of the product. Registration should call the first-registration statement once and the transition statement thereafter (`02-lifecycle-dml.sql`, sections 2 and 1).
2. **It writes `updated_at`.** The canonical audit names are `created_dts` / `updated_dts`; `created_at` and `updated_at` are prohibited by TLM-04. A generator emitting them is usually copying a reference DDL that carries the prohibited names, so that reference needs correcting at the same time.
3. **It writes `{module}_table_database`, `{module}_view_database`, `{module}_database` and `staging_table_database`.** Nineteen columns that exist in no registry DDL, derived by matching container names against a `{Product}_{Module}_{Layer}` regular expression. The derivation only holds at sites using that naming. The same facts belong in `data_product_container`, declared rather than parsed.

Until the generator is updated, treat its output as a template and take the statements from `02-lifecycle-dml.sql`.

## Conformance rules → checks

| Rule | Check |
|------|-------|
| `INV-CATALOGUE-001` | State vocabulary. |
| `INV-CATALOGUE-002` | One current version per product, plus flag/sentinel agreement. |
| `INV-CATALOGUE-003` | No gap or overlap between consecutive versions. |
| `INV-CATALOGUE-004` | Retirement carries the deletion flag and its instant. |
| `INV-CATALOGUE-005` | Every interface container is declared, and every declared object exists in `DBC.TablesV` as the kind declared. |
| `INV-CATALOGUE-006` | The interface feed and the Semantic view catalogue agree, in both directions. |
| `INV-CATALOGUE-007` | An active product carries a contact address. |
| `INV-CATALOGUE-008` | No product has lost a detail pointer it previously held. |
| `INV-CATALOGUE-009` | No duplicate version start instants; no inverted validity period. |
| `INV-CATALOGUE-010` | Not machine-checkable. Enforced at the source: the extractor warns rather than defaults, and the projection in `04-resolution-queries.sql` selects declared values only. |
| `INV-CATALOGUE-011` | Emitter-enforced: `05-semantic-model-export.sql` selects registered rows only, and the emitter adds nothing to them. |
| `INV-CATALOGUE-012` | Emitter-enforced: the export is stamped from `product_version` on the product feed and renders the whole model. |
| `INV-CATALOGUE-013` | Emitter-enforced: query 3 returns `emit_direction`, and a `REPORT` row is warned and omitted rather than reshaped. |

The metric and synonym invariants the export depends on (`INV-SEMANTIC-013` to `INV-SEMANTIC-015`) are checked by the Semantic module's own `validation.sql.j2`, since that is where the catalogue they constrain lives.

## Semantic model export

The five feeds cover product, object and container grain. A catalogue that masters semantic models also wants the model itself: datasets, fields, relationships, metrics and synonyms. That comes out of the product's Semantic module as a version-stamped export rather than through a feed, because it is scoped to a release and its shape belongs to the consuming format.

`05-semantic-model-export.sql` is the extraction. [`EMITTERS.md`](EMITTERS.md) specifies the two renderers that turn it into YAML: a semantic model, and a product descriptor. Both belong beside the existing catalogue renderers in the release packager.

Metrics and synonyms come from the Semantic module's measure catalogue (`modules/semantic/07-metric-tables.sql.j2`). A product that registers no metrics exports a model with no metrics, which a catalogue accepts; it is a thinner model, not an invalid one.

A worked example — three registered products, one outside the default hierarchy, and the full lifecycle — is in [`examples/alation-interface/`](../../../../examples/alation-interface/).
