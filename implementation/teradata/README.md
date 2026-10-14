# Teradata implementation

Reusable binding for **any conforming data product** on Teradata Vantage. Target: Teradata 17.20 or later; tested on 20.00.24 (see [CONFORMANCE.md](CONFORMANCE.md)). These are Jinja templates and binding documents, not a finished deployment or a compiler.

## How a build reads this binding

A build has three inputs: a **design specification** (the product, platform-agnostic), an **organisation profile** (placement, naming, principals and classification for one organisation on Teradata) and this **binding**. [`tooling/build/build_context.py`](../../tooling/build/README.md) resolves the specification, the profile and the binding's declarations into one build context, whose shape is fixed by [`build_context.schema.json`](../../tooling/build/build_context.schema.json) ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3).

The templates read only the build context, and derive no names: every database, object, column and role name arrives resolved. Standard-owned relations (the Semantic catalogue, the Observability and Memory stores, the validation relations and the discovery and trust-map views) are defined by the module and pattern standards under [`design/`](../../design/) and placed by the resolver. This directory carries no input contract or entity declarations of its own.

Read [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md) first, and its §7 before writing any SQL by hand: it lists, by error code, the constructs Teradata rejects. Its **Binding declarations** section lists the phase files in order with the template that renders each, the deploy template, the checks, and the physical type and SQL fragment for each logical type and expression function. Then read the module and pattern directories; each README says what its templates emit and which build-context fields they read.

| Directory | Templates |
|---|---|
| [patterns/object-placement](patterns/object-placement/README.md) | Databases, parents first, with their permanent space |
| [patterns/access-layer](patterns/access-layer/README.md) | The implied grants between databases; roles and tier grants |
| [patterns/temporal-lifecycle-metadata](patterns/temporal-lifecycle-metadata/README.md) | Shared macros, comments, governed base views and consumer views, statistics, caller-rendered maintenance |
| [modules/*](modules/) | Each module's tables; Domain key allocation; Search similarity procedures; Semantic registration and discovery; Memory capture |
| [patterns/validation](patterns/validation/README.md) | Metadata, temporal and reference checks; the trust-map view |

Two sets of templates in this directory still read the old flat context and are not reached by any phase: the graph-lineage exposure (`modules/observability/04-openlineage.md` and `05-graph-tables` to `10-access.dcl`) and the [catalogue interface](patterns/catalogue-interface/README.md). Whether they are ported onto the build context or retired is an open decision. A specification or profile that asks for either has it reported as a gap.

## Render, deploy and validate

The worked inputs are the [IT Service Desk specification](../../examples/it-service-desk-data-product/design-output/design_specification.md) with either Teradata profile: [`teradata.md`](../../examples/it-service-desk-data-product/profiles/teradata.md) (a database per module, upper-case names, roles created per product) or [`teradata-type-grouped.md`](../../examples/it-service-desk-data-product/profiles/teradata-type-grouped.md) (type-grouped databases under a parent, snake-case names, an adopted entity, container-isolated environments). The [customer-orders reference](../../tooling/evals/reference/customer-orders.md) builds under both.

```sh
python -m pip install -r tooling/bindings/requirements.txt teradatasql
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md examples/it-service-desk-data-product/profiles/teradata.md --output build/itsd-teradata
TERADATA_DSN='{"host": "...", "user": "...", "password": "..."}' python tooling/bindings/validate.py build/itsd-teradata/manifest.json
```

The profile names the platform. `--environment PHASE` places the product for one lifecycle phase; `--version V` supplies the product version where the specification leaves it open. The output directory must be empty and outside `design/`, `implementation/`, `examples/`, `roles/` and `tooling/`. The renderer writes:

- one SQL file per declared phase that renders something for this composition;
- `deploy.sql`, the phases in order;
- `manifest.json`: the checks, each with a test id `{PRODUCT_CODE}-{CHECK}-{NNN}`, where validation evidence is placed, the gaps the binding reports and the defaults the resolver applied;
- `context.json`, the resolved build context.

Rendering does not connect to a database. Rendered SQL is not checked into this repository.

**Deploying.** Run `deploy.sql` with a client that stops at the first error and sends one statement per request, keeping each stored procedure whole through its closing `END;`. `tooling/bindings/engines.py` (`statements`) splits a rendered script that way for a driver such as teradatasql. BTEQ splits a script at every semicolon, so with BTEQ run the similarity procedures (`10-similarity.sql`) with `.COMPILE FILE` and the other phases as scripts. Teradata commits each DDL statement on its own, so a deployment cannot be rolled back: a failed one leaves what ran, and is cleared by dropping the product's databases before deploying again. Consecutive row writes and comments may be sent as one multi-statement request, which is much faster than one request each. The deploying user needs `CREATE DATABASE` with enough permanent space for the `Container space` setting per database, `CREATE ROLE` where the profile says `create`, and `CREATE PROCEDURE` on each database that holds a similarity procedure, which a database's creator is not granted: name the deploying user in the profile's `Deploying user` setting and the build grants it. Roles carry rights only; granting them to users is an operator step.

**Validating.** The validator connects with the teradatasql parameters in `TERADATA_DSN`, runs each check (each request commits or fails on its own) and, where the product places `ValidationRun` and `ValidationArea`, appends one run and its area records in one transaction (wire schema 2.1). `--producer` publishes under a producer id other than the product's designated one. The manifest contains trusted generated SQL: never run one from an untrusted source. Gaps the manifest reports cap the PRODUCT area at `partial`.

## Verification

```sh
python -m unittest discover -s tooling/bindings/tests -v
python -m unittest discover -s tooling/validation/tests -v
python tooling/validation/design_lint.py design implementation
python tooling/catalogue/build_catalogue.py --check
python tooling/skill/verify_skill.py
```

`tooling/bindings/tests/test_teradata_dialect.py` holds every rendered statement to the §7 rules, with no engine. The engine tests need `teradatasql` and `TERADATA_TEST_DSN`, the connection parameters as JSON, for a disposable system where the user may create databases and roles. They deploy each reference specification once, under databases and roles prefixed `anptest_`, reset the rows between tests, and drop everything with that prefix, and nothing else, before and after. Without the variable or the driver the Teradata engine tests skip, and a skip is a gap. See [CONFORMANCE.md](CONFORMANCE.md) for coverage and remaining gaps.

## Catalogue

<!-- catalogue:start -->

### Platform profile

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [Teradata Platform Profile](PLATFORM_PROFILE.md) *(advisory)* | `teradata` | draft | - | - | - |

### Bindings

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [Teradata Access Layer Pattern Implementation](patterns/access-layer/README.md) | `access-layer` | draft | - | - | - |
| [Teradata Enterprise Catalogue Interface Implementation](patterns/catalogue-interface/README.md) | `catalogue-interface` | draft | - | - | - |
| [Teradata Domain Module Implementation](modules/domain/README.md) | `domain` | draft | - | - | - |
| [Teradata Memory Module Implementation](modules/memory/README.md) | `memory` | draft | - | - | - |
| [Teradata Object Placement Pattern Implementation](patterns/object-placement/README.md) | `object-placement` | draft | - | - | - |
| [Teradata Observability Module Implementation](modules/observability/README.md) | `observability` | draft | - | - | - |
| [Teradata Physical Storage Pattern Implementation](patterns/physical-storage/README.md) | `physical-storage` | draft | - | - | - |
| [Teradata Prediction Module Implementation](modules/prediction/README.md) | `prediction` | draft | - | - | - |
| [Teradata Search Module Implementation](modules/search/README.md) | `search` | draft | - | - | - |
| [Teradata Semantic Module Implementation](modules/semantic/README.md) | `semantic` | draft | - | - | - |
| [Teradata Temporal Lifecycle Metadata Pattern Implementation](patterns/temporal-lifecycle-metadata/README.md) | `temporal-lifecycle-metadata` | draft | - | - | - |
| [Teradata Validation Pattern Implementation](patterns/validation/README.md) | `validation` | draft | - | - | - |

<!-- catalogue:end -->
