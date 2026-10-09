# IT Service Desk: DuckDB walkthrough

Use the [shared brief/input notes](../bindings/README.md) and original CSVs. The [placement input](placement.json) declares six module schemas and a separate access schema. DuckDB has no roles, so there is no role input, and supplying one fails the build. Target DuckDB 1.4 or later; the suite has run on 1.5.6.

```sh
python -m pip install -r tooling/bindings/requirements.txt duckdb
python tooling/bindings/render.py --platform duckdb --context examples/it-service-desk-data-product/bindings/context.json --placement examples/it-service-desk-data-product/duckdb/placement.json --output build/itsd-duckdb
```

Review the generated phases. Create a **new, empty** database file whose name is not a module name (not `memory`), then execute the deployment script on a single writing connection:

```sh
duckdb build/itsd.duckdb < build/itsd-duckdb/deploy.sql
```

The script never drops or replaces an existing product, installs an extension or selects a location. Load the four original CSVs with stable natural-key mappings and explicit effective and knowledge instants. Complete real documentation, feature engineering and model selection in the generated product workspace. Open readers with `read_only` after the writer has closed and checkpointed.

```sh
python tooling/bindings/validate.py build/itsd-duckdb/manifest.json --database build/itsd.duckdb
```

The validator exits non-zero while `memory:coverage` reports the documentation still to be written, and it publishes wire-schema 2.1 evidence. Start discovery at `itsd_access.data_product_manifest`, then resolve the trust map and consumer objects. DuckDB cannot grant or hide anything: anyone who can open the file sees the base tables, the historical macros and the runtime memory, so serving the product to agents needs an authenticated application in front of it. Compare the same source counts and two-axis history outcomes across platforms, and disclose platform capability gaps.

These are build inputs and a walkthrough, not a finished data product. Rendered SQL, database files and evidence stay outside this repository. See the [reusable binding](../../../implementation/duckdb/README.md).
