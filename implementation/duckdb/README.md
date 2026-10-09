# DuckDB implementation

Reusable bindings for **any conforming data product**, following the module and pattern layout of the other platforms. Target: DuckDB 1.4 or later, tested on 1.5.6 (see [CONFORMANCE.md](CONFORMANCE.md)). These are Jinja templates and binding documents, not a finished deployment or a compiler.

Each module directory contains its binding document and `.sql.j2` templates. Semantic, Memory and Observability also carry `entities.json`: standard-owned metadata structures used by the table templates. Business entities, composition, placement, model dimensions and documentation are supplied by the product design. Temporal macros are shared within this platform. There is no plain SQL, Python compiler, checker or validator in this directory: rendering, validation and the tests live under [`tooling/bindings`](../../tooling/bindings/README.md), shared with the other Jinja bindings.

Read [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md), [TEMPLATE_INPUTS.md](TEMPLATE_INPUTS.md), then the selected module and pattern directories. Render using a Jinja FileSystemLoader rooted here and StrictUndefined. The optional [rendering helper](../../tooling/bindings/README.md) validates inputs and supplies identifier and literal filters; it is not a mandatory product compiler.

## Shared example

Use the existing [IT Service Desk brief and CSVs](../../examples/it-service-desk-data-product/) with the [DuckDB walkthrough](../../examples/it-service-desk-data-product/duckdb/README.md). The placement input declares only containers: DuckDB has no roles.

```sh
python -m pip install -r tooling/bindings/requirements.txt duckdb
python tooling/bindings/render.py --platform duckdb --context examples/it-service-desk-data-product/bindings/context.json --placement examples/it-service-desk-data-product/duckdb/placement.json --output build/itsd-duckdb
```

The helper generates into an empty user-selected output directory, never under design/, implementation/ or examples/. It does not connect to a database or execute DDL. Rendered SQL and manifests are not checked into this repository. The earlier hand-written DuckDB SQL, its Python model compiler, temporal writer and validator, and the generated Customer360 example have been removed; existing database files are not migrated or deleted.

To deploy, open a **new empty** database file and run `deploy.sql`. The file stem becomes the catalogue name: do not name it after a module (especially `memory`). Use one writing process; close and checkpoint the file before opening readers with `read_only`.

```sh
duckdb build/itsd.duckdb < build/itsd-duckdb/deploy.sql
python tooling/bindings/validate.py build/itsd-duckdb/manifest.json --database build/itsd.duckdb
```

A freshly deployed product reports no evidence for every trust area until the validator publishes wire-schema 2.1 evidence. **Direct access to the file exposes all data**: views and read-only mode are not access control.

## Verification

```sh
python -m pip install jinja2 duckdb
python -m unittest discover -s tooling/bindings/tests -v
python -m pytest tooling implementation -q
python tooling/validation/design_lint.py design implementation
python tooling/catalogue/build_catalogue.py --check
```

The same templates are tested with ITSD and an unrelated smaller laboratory product, in several module compositions, on an actual DuckDB engine. Tests skip only if the `duckdb` driver is missing, and a skip is a gap. See [CONFORMANCE.md](CONFORMANCE.md) for coverage and declared gaps.

## Catalogue

<!-- catalogue:start -->

### Platform profile

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [DuckDB Platform Profile](PLATFORM_PROFILE.md) *(advisory)* | `duckdb` | draft | - | - | - |

### Bindings

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [DuckDB Access Layer Implementation](patterns/access-layer/README.md) | `access-layer` | draft | - | - | - |
| [DuckDB Domain Implementation](modules/domain/README.md) | `domain` | draft | - | - | - |
| [DuckDB Memory Implementation](modules/memory/README.md) | `memory` | draft | - | - | - |
| [DuckDB Object Placement Implementation](patterns/object-placement/README.md) | `object-placement` | draft | - | - | - |
| [DuckDB Observability Implementation](modules/observability/README.md) | `observability` | draft | - | - | - |
| [DuckDB Physical Storage Implementation](patterns/physical-storage/README.md) | `physical-storage` | draft | - | - | - |
| [DuckDB Prediction Implementation](modules/prediction/README.md) | `prediction` | draft | - | - | - |
| [DuckDB Search Implementation](modules/search/README.md) | `search` | draft | - | - | - |
| [DuckDB Semantic Implementation](modules/semantic/README.md) | `semantic` | draft | - | - | - |
| [DuckDB Temporal Lifecycle Metadata Implementation](patterns/temporal-lifecycle-metadata/README.md) | `temporal-lifecycle-metadata` | draft | - | - | - |
| [DuckDB Validation Implementation](patterns/validation/README.md) | `validation` | draft | - | - | - |

<!-- catalogue:end -->
