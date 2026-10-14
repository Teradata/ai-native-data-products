# Worked example: the enterprise catalogue interface

Three registered data products under three unrelated naming schemes, and the full life of one of them from `DRAFT` to `RETIRED`. Companion to the [catalogue-interface pattern](../../design/patterns/catalogue-interface.md) and its [Teradata binding](../../implementation/teradata/patterns/catalogue-interface/).

## Run order

| Step | File | What it does |
|---|---|---|
| 1 | [`01-seed-registry.sql`](01-seed-registry.sql) | Registers three products. `CustExp` as `DRAFT`, `CredExp` and `ITSD` as `ACTIVE` with their consumer surfaces. |
| 2 | [`02-lifecycle-walk.sql`](02-lifecycle-walk.sql) | Takes `CustExp` through four transitions: publication, a `1.1.0` release, deprecation, retirement. |
| 3 | [`03-verification-queries.sql`](03-verification-queries.sql) | The reads, each with its expected result. |
| 4 | `conformance-queries.sql` (in the binding) | Every invariant, expected to return zero rows. |

You need the amended registry from [`modules/semantic/03-registry.sql`](../../implementation/teradata/modules/semantic/03-registry.sql), the two feed tables, and the five views. Step 2 also writes to `CustExp_SEM_STD_T` and `CustExp_OBS_STD_T`, which needs the product's own tables to exist; skip those statements if they don't, and nothing else is affected.

Every instant is a literal, so results are identical between runs and the verification queries can state exact row counts.

## The three products

| Product | Scheme | Consumer surface |
|---|---|---|
| `retail.customer_experience` | `{Product}_{MOD}_{LAYER}` — `CustExp_DOM_ACL_V`, `CustExp_DOM_BUS_V` | two access views, two business views, the column catalogue |
| `risk.credit_exposure` | a group risk hierarchy — `GRPRISK_AU_CREDEXP_PUB` | four views, all in one container, no business layer |
| `ops.it_service_desk` | `{ProductCode}_{ModuleAbbrev}` — `ITSD_ACC` | five views, one access container for every module |

`risk.credit_exposure` is the one to look at. Its containers are named for a programme and a jurisdiction. Nothing in them says which module or layer they hold, nothing says `CredExp`, and the word `dataproducts` appears nowhere. Every query in step 3 returns correct results for it, because its modules and layers are declared in `governance.data_product_container` rather than read out of a name.

`ops.it_service_desk` has no business owner recorded, only a technical contact. It shows what contact resolution does when the preferred contact is missing: the feed falls back to the technical contact so the catalogue gets a working address, and `contact_source` shows which one it used.

## The lifecycle

| Instant (UTC) | Transition | What a catalogue reads |
|---|---|---|
| 2025-01-15 09:00 | `DRAFT 1.0.0` registered | the product exists, `is_active = 0`: visible to its builders, not offered to consumers |
| 2025-02-03 14:30 | `ACTIVE 1.0.0` | `STATUS_CHANGE`, and four consumer objects appear in the interface feed |
| 2025-06-10 11:15 | `1.1.0` released | `VERSION_RELEASE`: a column added, a business definition reworded, a relationship added, a fifth consumer object |
| 2026-01-19 08:45 | `DEPRECATED` | `STATUS_CHANGE`, still `is_active = 1`, replacement named in the description |
| 2026-06-15 17:00 | `RETIRED` | `RETIRED`, `is_deleted = 1`, consumer surface withdrawn, earlier instants still queryable |

Five registry versions, no gap and no overlap, one current. Three interface generations. Nothing deleted.

`is_active` stays 1 through deprecation. A deprecated product that dropped out of discovery would break every consumer still using it.

## What the database doesn't keep

The `1.1.0` release reworded the definition of `satisfaction_score`: an unanswered survey used to be recorded as the neutral value 3 and is now recorded as unknown, so averages either side of the change aren't comparable.

The previous wording is not in the database. The Semantic column catalogue is `CURRENT_STATE` — audit columns, no validity pair — so the update overwrote it, and no query recovers it. Section 8 of the verification file shows this directly.

Three things together make the change reconstructable:

1. The product version moves at the same instant, so the transition is on the lifecycle feed.
2. A `change_event` row records that the definition changed, under which release, and why — including the comparability warning.
3. The release exports a full detail snapshot stamped `1.1.0`, and the catalogue still holds the one stamped `1.0.0`.

A site wanting definition-level history inside the database is choosing `DEC-TEMPORAL-PATTERN` differently for its Semantic module, and records that choice. The interface is the same either way, since it reads the export.

## Mapping to the Alation bundle

A catalogue exporter renders an eleven-file bundle from a neutral product-metadata model. Sources once this interface is in place:

| Alation field | Source |
|---|---|
| `product_id`, `product_name`, `version`, `description` | `governance.data_product_catalogue` |
| `domain` | `product_domain` — new in registry 2.0; previously had no source and exported empty |
| `status` | `product_status` |
| `contactName` | `contact_name`: `owner_name`, falling back to `technical_contact_name` |
| `contactEmail` | `contact_email`: `owner_email`, falling back to `technical_contact_email` |
| `business_owner` / `technical_owner` | `owner_name` / `technical_contact_name`, unreduced |
| `logical_interfaces.json` | `governance.data_product_consumer_interface` — the table and view list |
| `physical_mappings.json` | `governance.data_product_container_current` joined to the interface feed |
| `column_metadata.json` | the product's Semantic column catalogue, per version |
| `glossary_terms.json` | the product's Memory glossary |
| `lineage.json`, `quality_and_trust.json` | the product's Observability module |
| `access_model.json` | the product's access layer declaration |
| `provenance.json` | the build manifest |

Two of these are why the work was needed. `contactName` and `contactEmail` had no source: the registry held `owner_team`, a team name with no address, and the extractor emitted a warning rather than a value. `logical_interfaces.json` was derived by classifying object types out of a dependency graph, which says what kind of object something is but not whether a consumer may query it — a question only the product's own access declaration answers.

## Known divergence in automated registration

A registration generator written against the version 1.0 registry emits a `MERGE` keyed on `product_id` alone, writes `updated_at`, and may derive per-module container columns by matching container names against a naming pattern. All three are incompatible with this interface; the binding's [README](../../implementation/teradata/patterns/catalogue-interface/README.md) sets out what each should become. Until it is updated, take the registration statements from `02-lifecycle-dml.sql` and treat the generated script as a template.
