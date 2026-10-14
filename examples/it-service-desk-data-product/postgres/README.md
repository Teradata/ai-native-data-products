# IT Service Desk: PostgreSQL walkthrough

Use the [shared brief/input notes](../bindings/README.md) and original CSVs. The [placement input](placement.json) declares six module schemas, a separate access schema and three independent NOLOGIN group roles. Role names are cluster-wide: select unused names or arrange deliberate provisioning with the operator. Target PostgreSQL 16+; the `btree_gist` extension is required for temporal exclusion constraints.

```sh
python -m pip install -r tooling/bindings/requirements.txt
python -m pip install 'psycopg[binary]'
python tooling/bindings/render.py --platform postgres --context examples/it-service-desk-data-product/bindings/context.json --placement examples/it-service-desk-data-product/postgres/placement.json --output build/itsd-postgres
```

Review the generated phases. Set your ordinary PostgreSQL connection configuration to a **new dedicated database**, then execute:

```sh
psql -X -v ON_ERROR_STOP=1 -f build/itsd-postgres/deploy.sql
```

The deployment login needs schema/extension/role creation permissions. If role creation belongs to an operator, hand over the rendered access phase explicitly. The script never drops/replaces an existing product, provisions login accounts or selects a server. A service name only works if you have configured that service; for the Python validator use a direct connection such as `POSTGRES_DSN='host=localhost port=5432 dbname=itsd user=your_deployer'` or a real configured service. Supply credentials through your normal PostgreSQL configuration.

Load the four original CSVs with stable natural-key mappings and explicit effective/knowledge instants. Complete real documentation, feature engineering and model selection in the generated product workspace. PostgreSQL RLS uses authenticated session_user; shared application logins need a separately designed end-user identity boundary.

```sh
python tooling/bindings/validate.py build/itsd-postgres/manifest.json
```

Start discovery at `itsd_access.data_product_manifest`, then resolve the trust map and consumer objects. Native grants expose consumer views while full historical functions remain administrative. Compare the same source counts and two-axis history outcomes across platforms, and disclose platform capability gaps.

These are build inputs and a walkthrough, not a finished data product. Rendered SQL and evidence stay outside the skill corpus. See the [reusable binding](../../../implementation/postgres/README.md).
