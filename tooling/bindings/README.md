# Reusable binding rendering and verification

Optional authoring tools for reusable Jinja bindings. Each platform with an IT Service Desk placement input (currently PostgreSQL and DuckDB) is driven by this tooling. SQL stays in `implementation/{platform}/`; this helper resolves input contracts and tests them. Teradata's existing tooling and implementation are unchanged.

```sh
python -m pip install -r tooling/bindings/requirements.txt
python tooling/bindings/render.py --platform postgres --context examples/it-service-desk-data-product/bindings/context.json --placement examples/it-service-desk-data-product/postgres/placement.json --output build/itsd-postgres
```

Use `--platform duckdb` with the `duckdb/placement.json` sibling for DuckDB. `--output` must be empty. Use an ignored `build/` directory or a separate product repository; output under the standards/example/tooling directories is rejected. Rendering neither installs a database nor executes SQL. `deploy.sql` wraps the rendered phases in a transaction; individual phase files are also supplied for review and staged deployment. Role provisioning may need a separate operator step.

The `implementation/{platform}/TEMPLATE_INPUTS.md` input contract defines product, composition, placement, entities and relationships. Standard-owned metadata declarations live beside each platform's module templates. Jinja uses StrictUndefined and explicit identifier/literal filters. Direct template rendering is supported; the helper is not required by the standard.

After deployment, install the relevant driver (`duckdb`, or `psycopg[binary]`) and validate the rendered product:

```sh
python tooling/bindings/validate.py build/itsd-duckdb/manifest.json --database /path/to/itsd.duckdb
# Set POSTGRES_DSN to a real connection string or an existing configured service.
python tooling/bindings/validate.py build/itsd-postgres/manifest.json
```

The manifest contains trusted generated SQL. Never execute manifests from untrusted sources. The runner reports failures/errors and appends validation wire 2.1 evidence when Observability is present; otherwise it returns check results without inventing an evidence store. It does not migrate old Customer360 databases. Missing real documentation or model/operational evidence remains visible.

## Tests

```sh
python -m pip install duckdb 'psycopg[binary]'
python -m unittest discover -s tooling/bindings/tests -v
```

Set `POSTGRES_TEST_DSN` to a disposable PostgreSQL database to enable PostgreSQL tests. It needs extension/schema/role creation privileges. Each test rolls back its deployment; none drops an existing schema. Do not use a production database. Without a PostgreSQL connection its tests explicitly skip. A missing DuckDB driver also skips native DuckDB tests (`test_bindings.py` and `test_duckdb_binding.py`); neither skip counts as engine verification.

Tests render ITSD and an unrelated laboratory product with the same templates, cover composition and naming changes, load the four original ITSD CSVs, and exercise bitemporal corrections, effective-history maintenance, the shared trust cases and validation errors. Every platform template must be rendered by at least one test. Fixture loading code lives only in tests. It is not a reusable ingestion pipeline or a completed product shipped with the skill.
