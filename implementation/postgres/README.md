# PostgreSQL implementation

Reusable bindings for **any conforming data product**, following the module/pattern layout of the Teradata reference. Target: PostgreSQL 16+. These are Jinja templates and binding documents, not a finished deployment.

Each module directory contains its binding document and `.sql.j2` templates. Semantic, Memory and Observability also carry `entities.json`: standard-owned metadata structures used by the table templates. Business entities, composition, placement, model dimensions and documentation are supplied by the product design. Temporal macros are shared within this platform.

Read [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md), [TEMPLATE_INPUTS.md](TEMPLATE_INPUTS.md), then the selected module/pattern directories. Render using a Jinja FileSystemLoader rooted here and StrictUndefined. The optional [rendering helper](../../tooling/bindings/README.md) validates inputs and supplies identifier/literal filters; it is not a mandatory product compiler.

## Shared example

Use the existing [IT Service Desk brief and CSVs](../../examples/it-service-desk-data-product/) with the [PostgreSQL walkthrough](../../examples/it-service-desk-data-product/postgres/README.md). The Teradata brief and implementation are unchanged. The new overlay distinguishes shared business requirements from the original workflow instructions.

```sh
python -m pip install -r tooling/bindings/requirements.txt
python tooling/bindings/render.py --platform postgres --context examples/it-service-desk-data-product/bindings/context.json --placement examples/it-service-desk-data-product/postgres/placement.json --output build/itsd-postgres
```

The helper generates into an empty user-selected output directory, never under design/, implementation/ or examples/. It does not connect to a database or execute DDL. Rendered SQL and manifests are not checked into this skill. Legacy Customer360 builders, generated SQL and product-specific validators have been removed; existing user databases are not migrated or deleted.

## Verification

```sh
python -m unittest discover -s tooling/bindings/tests -v
python tooling/validation/design_lint.py design implementation
python tooling/catalogue/build_catalogue.py --check
python tooling/skill/verify_skill.py
```

Install DuckDB for its native tests and Psycopg for PostgreSQL tests. Set POSTGRES_TEST_DSN to a disposable database with role/extension creation privileges. Missing engines are explicitly skipped. The same templates are tested with ITSD and an unrelated smaller laboratory product. See [CONFORMANCE.md](CONFORMANCE.md) for coverage and remaining obligations.

## Catalogue

<!-- catalogue:start -->

### Platform profile

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [PostgreSQL Platform Profile](PLATFORM_PROFILE.md) *(advisory)* | `postgres` | draft | - | - | - |

### Bindings

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [PostgreSQL Access Layer Implementation](patterns/access-layer/README.md) | `access-layer` | draft | - | - | - |
| [PostgreSQL Domain Implementation](modules/domain/README.md) | `domain` | draft | - | - | - |
| [PostgreSQL Memory Implementation](modules/memory/README.md) | `memory` | draft | - | - | - |
| [PostgreSQL Object Placement Implementation](patterns/object-placement/README.md) | `object-placement` | draft | - | - | - |
| [PostgreSQL Observability Implementation](modules/observability/README.md) | `observability` | draft | - | - | - |
| [PostgreSQL Physical Storage Implementation](patterns/physical-storage/README.md) | `physical-storage` | draft | - | - | - |
| [PostgreSQL Prediction Implementation](modules/prediction/README.md) | `prediction` | draft | - | - | - |
| [PostgreSQL Search Implementation](modules/search/README.md) | `search` | draft | - | - | - |
| [PostgreSQL Semantic Implementation](modules/semantic/README.md) | `semantic` | draft | - | - | - |
| [PostgreSQL Temporal Lifecycle Metadata Implementation](patterns/temporal-lifecycle-metadata/README.md) | `temporal-lifecycle-metadata` | draft | - | - | - |
| [PostgreSQL Validation Implementation](patterns/validation/README.md) | `validation` | draft | - | - | - |

<!-- catalogue:end -->
