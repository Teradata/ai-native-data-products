# PostgreSQL implementation

A sibling of [Teradata](../teradata/) and [DuckDB](../duckdb/), binding all six modules and five patterns without changing the platform-neutral design. PostgreSQL **16+** is the target; execution has been verified on **PostgreSQL 18.3 via PGlite 0.5.8**, including the Psycopg wire-protocol client. Native server concurrency, authentication configuration and recovery have not been tested here. Bindings remain draft pending that operational review.

The [Customer360 example](../../examples/customer360-postgres/) contains synthetic histories, discovery metadata, exact vector search, engineered features, documentation and validation evidence. Python **3.10+** is needed for generation and validation. PostgreSQL's supplied `btree_gist` extension enforces non-overlapping history. No pgvector or model service is required.

Use a **new dedicated database**, with a deployment login allowed to create schemas and cluster roles and install `btree_gist`. The fixed `customer360_role_read`, `customer360_role_agent` and `customer360_role_admin` names must be unused in the cluster. Roles are deliberately not silently reused. Keep credentials in PostgreSQL service/password files or environment configuration, not checked-in scripts.

```sh
python -m pip install -r examples/customer360-postgres/requirements.txt
# Set POSTGRES_DSN to the dedicated database connection string.
python examples/customer360-postgres/build.py
python implementation/postgres/validate.py
```

In PowerShell, set `$env:POSTGRES_DSN='service=customer360'`; in a POSIX shell use `export POSTGRES_DSN='service=customer360'`, with the service defined in your PostgreSQL connection configuration. The builder creates and validates inside one transaction; any failure rolls back. It never drops or replaces an existing product. Run the validator as the deployment maintainer or ADMIN, not an analytical reader.

For SQL-only deployment to an empty target, using psql's normal connection environment:

```sh
psql -X -v ON_ERROR_STOP=1 -f examples/customer360-postgres/build.sql
psql -X -v ON_ERROR_STOP=1 -f implementation/postgres/patterns/validation/conformance.sql
psql -X -v ON_ERROR_STOP=1 -f examples/customer360-postgres/agent_demo.sql
```

SQL-only deployment initially reports no-evidence/unknown. Conformance SQL returns counts; only the Python validator publishes error-aware evidence. Grant the NOLOGIN group roles to authenticated logins separately. READ and AGENT query approved views; AGENT runtime rows are restricted to its authenticated USER identity. Owners and superusers remain privileged. See [access-layer](patterns/access-layer/README.md).

| Schema | Binding |
|---|---|
| domain | Identity keymaps, SCD2 histories, current views and historical functions |
| semantic | Authored catalogue, live PostgreSQL facts, orientation and bounded join paths |
| search | Three-dimensional arrays, exact cosine retrieval and content join-back |
| prediction | Engineered feature history, availability cutoffs and toy scores |
| observability | Quality, lineage, executions and validation wire schema 2.1 |
| memory | Versioned design documentation and runtime process state protected by RLS |

Edit `model.py`, `render.py`, `checks.py` and authored SQL fragments, then regenerate. The deployment model is intentionally independent of DuckDB so each binding can evolve without importing another platform's compiler.

```sh
python implementation/postgres/render.py
python implementation/postgres/render.py --check
python tooling/catalogue/build_catalogue.py
python tooling/validation/design_lint.py design implementation
python -m unittest discover -s tooling/validation/tests
# POSTGRES_TEST_DSN must point to ANOTHER fresh disposable database/cluster namespace.
python -m unittest discover -s implementation/postgres/tests -v
```

Without POSTGRES_TEST_DSN, only generated-file checks run and database tests explicitly skip. The integration suite creates a product and leaves it in the disposable database; mutations roll back individually. It needs a superuser to simulate authenticated users and check RLS. Do not point it at an existing product. The fixture is not a migration engine.

See [platform profile](PLATFORM_PROFILE.md) and [conformance scope](CONFORMANCE.md).

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
