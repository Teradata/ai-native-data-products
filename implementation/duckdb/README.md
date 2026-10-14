# DuckDB implementation

Reusable binding for **any conforming data product**, following the module and pattern layout of the other platforms. Target: DuckDB 1.4 or later; tested on 1.5 (see [CONFORMANCE.md](CONFORMANCE.md)). These are Jinja templates and binding documents, not a finished deployment or a compiler. There is no plain SQL, Python or JSON in this directory: rendering, validation and the tests live under [`tooling/`](../../tooling/bindings/README.md), shared with the other Jinja bindings.

## How a build reads this binding

A build has three inputs: a **design specification** (the product, platform-agnostic), an **organisation profile** (placement, naming, access tiers and classification for one organisation on DuckDB) and this **binding**. [`tooling/build/build_context.py`](../../tooling/build/README.md) resolves the specification, the profile and the binding's declarations into one build context, whose shape is fixed by [`build_context.schema.json`](../../tooling/build/build_context.schema.json) ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3).

The templates read only the build context, and derive no names: every container, object, sequence and column name arrives resolved. Standard-owned relations (the Semantic catalogue, the Observability and Memory stores, the validation relations and the discovery and trust-map views) are defined by the module and pattern standards under [`design/`](../../design/) and placed by the resolver. This directory carries no input contract or entity declarations of its own.

DuckDB has no principals. The binding declares `Principals: unsupported`, so the organisation profile declares each access tier as `outside <how it is enforced>`, the resolver rejects a tier the profile says to `create` or bind to an `existing` principal, and there is no grants template and no access phase.

Read [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md) first. Its **Binding declarations** section lists the phase files in order with the template that renders each, the deploy template, the checks, and the physical type and SQL fragment for each logical type and expression function. Then read the module and pattern directories; each README says what its templates emit and which build-context fields they read.

| Directory | Templates |
|---|---|
| [patterns/object-placement](patterns/object-placement/README.md) | Schemas |
| [patterns/temporal-lifecycle-metadata](patterns/temporal-lifecycle-metadata/README.md) | Shared macros, comments, consumer views, point-in-time table macros, caller-rendered maintenance |
| [modules/*](modules/) | Each module's sequences and tables; Domain key allocation; Search similarity; Semantic registration and discovery; Memory capture |
| [patterns/validation](patterns/validation/README.md) | Metadata, temporal and reference checks; the trust-map view |
| [patterns/access-layer](patterns/access-layer/README.md) | None: the access boundary is outside the engine |

## Render, deploy and validate

The worked inputs are the [IT Service Desk specification](../../examples/it-service-desk-data-product/design-output/design_specification.md) with its [DuckDB profile](../../examples/it-service-desk-data-product/profiles/duckdb.md). The [customer-orders reference](../../tooling/evals/reference/customer-orders.md) builds under the same profile.

```sh
python -m pip install -r tooling/bindings/requirements.txt duckdb pytz
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md examples/it-service-desk-data-product/profiles/duckdb.md --output build/itsd-duckdb
duckdb build/itsd.duckdb < build/itsd-duckdb/deploy.sql
python tooling/bindings/validate.py build/itsd-duckdb/manifest.json --database build/itsd.duckdb
```

The profile names the platform. `--environment PHASE` places the product for one lifecycle phase; `--version V` supplies the product version where the specification leaves it open. The output directory must be empty and outside `design/`, `implementation/`, `examples/`, `roles/` and `tooling/`. The renderer writes:

- one SQL file per declared phase that renders something for this composition;
- `deploy.sql`, every phase in one transaction with the session time zone set to UTC;
- `manifest.json`: the checks, each with a test id `{PRODUCT_CODE}-{CHECK}-{NNN}`, where validation evidence is placed, the gaps the binding reports and the defaults the resolver applied;
- `context.json`, the resolved build context.

Rendering does not connect to a database. Rendered SQL is not checked into this repository.

Deploy into a **new, empty** database file. The file stem becomes the catalogue name: do not name it after a module (especially `memory`). Use one writing process; close and checkpoint the file before opening readers with `read_only`.

The validator needs an existing file (`--database`). It runs every check in autocommit, so one failing query does not affect the next, and where the product places `ValidationRun` and `ValidationArea` it appends one run and its area records (wire schema 2.1) in a single transaction. `--producer` publishes under a producer id other than the product's designated one. The manifest contains trusted generated SQL: never run one from an untrusted source. Gaps the manifest reports, such as an expression using a function this binding has no fragment for or a composite access object, cap the PRODUCT area at `partial`. A freshly deployed product reads `no-evidence` in the trust map until the validator has published.

**Direct access to the file exposes all data**: views and read-only mode are not access control.

## Verification

```sh
python -m pip install jinja2 duckdb pytz
python -m unittest discover -s tooling/bindings/tests -v
python -m unittest discover -s tooling/validation/tests -v
python tooling/validation/design_lint.py design implementation
python tooling/catalogue/build_catalogue.py --check
```

The DuckDB engine tests need the `duckdb` and `pytz` packages. Without `duckdb` they skip, and a skip is a gap. See [CONFORMANCE.md](CONFORMANCE.md) for coverage and declared gaps.

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
