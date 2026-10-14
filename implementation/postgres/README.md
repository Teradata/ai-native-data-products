# PostgreSQL implementation

Reusable binding for **any conforming data product**, following the module and pattern layout of the Teradata reference. Target: PostgreSQL 16 or later; tested on 16.4 (see [CONFORMANCE.md](CONFORMANCE.md)). These are Jinja templates and binding documents, not a finished deployment or a compiler.

## How a build reads this binding

A build has three inputs: a **design specification** (the product, platform-agnostic), an **organisation profile** (placement, naming, principals and classification for one organisation on PostgreSQL) and this **binding**. [`tooling/build/build_context.py`](../../tooling/build/README.md) resolves the specification, the profile and the binding's declarations into one build context, whose shape is fixed by [`build_context.schema.json`](../../tooling/build/build_context.schema.json) ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3).

The templates read only the build context, and derive no names: every container, object, column and principal name arrives resolved. Standard-owned relations (the Semantic catalogue, the Observability and Memory stores, the validation relations and the discovery and trust-map views) are defined by the module and pattern standards under [`design/`](../../design/) and placed by the resolver. This directory carries no input contract or entity declarations of its own.

Read [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md) first. Its **Binding declarations** section lists the phase files in order with the template that renders each, the deploy template, the checks, and the physical type and SQL fragment for each logical type and expression function. Then read the module and pattern directories; each README says what its templates emit and which build-context fields they read.

| Directory | Templates |
|---|---|
| [patterns/object-placement](patterns/object-placement/README.md) | Schemas and the `btree_gist` extension |
| [patterns/temporal-lifecycle-metadata](patterns/temporal-lifecycle-metadata/README.md) | Shared macros, comments, consumer views, point-in-time functions, caller-rendered maintenance |
| [modules/*](modules/) | Each module's tables; Domain key allocation; Search similarity; Semantic registration and discovery; Memory capture |
| [patterns/validation](patterns/validation/README.md) | Metadata, temporal and reference checks; the trust-map view |
| [patterns/access-layer](patterns/access-layer/README.md) | Roles, grants and row-level security |

## Render, deploy and validate

The worked inputs are the [IT Service Desk specification](../../examples/it-service-desk-data-product/design-output/design_specification.md) with its [PostgreSQL profile](../../examples/it-service-desk-data-product/profiles/postgres.md). The [customer-orders reference](../../tooling/evals/reference/customer-orders.md) builds under the same profile.

```sh
python -m pip install -r tooling/bindings/requirements.txt "psycopg[binary]"
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md examples/it-service-desk-data-product/profiles/postgres.md --output build/itsd-postgres
psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -f build/itsd-postgres/deploy.sql
python tooling/bindings/validate.py build/itsd-postgres/manifest.json
```

The profile names the platform. `--environment PHASE` places the product for one lifecycle phase; `--version V` supplies the product version where the specification leaves it open. The output directory must be empty and outside `design/`, `implementation/`, `examples/`, `roles/` and `tooling/`. The renderer writes:

- one SQL file per declared phase that renders something for this composition;
- `deploy.sql`, every phase in one transaction;
- `manifest.json`: the checks, each with a test id `{PRODUCT_CODE}-{CHECK}-{NNN}`, where validation evidence is placed, the gaps the binding reports and the defaults the resolver applied;
- `context.json`, the resolved build context.

Rendering does not connect to a database. Rendered SQL is not checked into this repository. Deploying needs privileges to create schemas, the `btree_gist` extension and, where the profile says `create`, the roles. The roles are `NOLOGIN`; login users and memberships are an operator step.

The validator connects through `POSTGRES_DSN`, runs each check in its own savepoint and, where the product places `ValidationRun` and `ValidationArea`, appends one run and its area records (wire schema 2.1). `--producer` publishes under a producer id other than the product's designated one. The manifest contains trusted generated SQL: never run one from an untrusted source. Gaps the manifest reports, such as an expression using a function this binding has no fragment for or a composite access object, cap the PRODUCT area at `partial`.

## Verification

```sh
python -m unittest discover -s tooling/bindings/tests -v
python -m unittest discover -s tooling/validation/tests -v
python tooling/validation/design_lint.py design implementation
python tooling/catalogue/build_catalogue.py --check
python tooling/skill/verify_skill.py
```

Set `POSTGRES_TEST_DSN` to a disposable database where the test role may create schemas, roles and the `btree_gist` extension. Each PostgreSQL test runs in one transaction that is rolled back. Without the variable or the `psycopg` package the PostgreSQL engine tests skip, and a skip is a gap. See [CONFORMANCE.md](CONFORMANCE.md) for coverage and remaining gaps.

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
