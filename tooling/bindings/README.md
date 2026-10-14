# Rendering and validating Jinja bindings

Tools for the platform bindings whose `PLATFORM_PROFILE.md` declares its phases (currently
PostgreSQL, DuckDB and Teradata). A build has three inputs: a design specification, an organisation
profile and the platform binding. [`tooling/build`](../build/) resolves the first two and the
binding's declarations into one build context; `render.py` renders the binding's declared
phases, deploy script and checks from that context alone. SQL stays in
`implementation/{platform}/`.

```sh
python -m pip install -r tooling/bindings/requirements.txt
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md examples/it-service-desk-data-product/profiles/postgres.md --output build/itsd-postgres
```

The profile names the platform, so the same specification with
[`profiles/duckdb.md`](../../examples/it-service-desk-data-product/profiles/duckdb.md) renders the
DuckDB binding, and with [`profiles/teradata.md`](../../examples/it-service-desk-data-product/profiles/teradata.md) the Teradata one. An invalid specification or profile renders nothing and reports why.
`--output` must be empty and outside the skill corpus; use an ignored `build/` directory or a
separate product repository. Rendering neither connects to a database nor executes SQL.

The output holds one file per phase that renders anything for the composition, `deploy.sql`
(the phases joined by the binding's `Deploy` template, in one transaction where the engine can
roll DDL back), `context.json` (the resolved build context) and `manifest.json`: the checks with their test ids
(`{PRODUCT_CODE}-{CHECK}-{NNN}`) and scopes, where evidence is published, and every **gap**,
meaning something the specification asks for that this binding does not render. Gaps are
printed when rendering and never hidden.

After deployment, install the driver (`duckdb` and `pytz`, `psycopg[binary]`, or `teradatasql`) and validate:

```sh
python tooling/bindings/validate.py build/itsd-duckdb/manifest.json --database /path/to/itsd.duckdb
# PostgreSQL reads POSTGRES_DSN; Teradata reads TERADATA_DSN, the teradatasql connection parameters as JSON.
python tooling/bindings/validate.py build/itsd-postgres/manifest.json
```

The manifest contains trusted generated SQL; never run one from an untrusted source. Each
check returns its defects, so it passes when it returns no rows; a check that errors is
recorded as an error, never as a pass. Where the product places `ValidationRun` and
`ValidationArea`, one run and its area records are appended (wire schema 2.1), named as the
build context placed them. Reported gaps cap the product-level area at `partial`.

## Conformance reports

```sh
python tooling/bindings/conformance.py            # regenerate implementation/*/CONFORMANCE.md
python tooling/bindings/conformance.py --check    # fail if a committed report is out of date
```

Each binding's `CONFORMANCE.md` is generated, never edited ([Platform Implementation
Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §8.1). The generator runs
these tests and the package tests once, records every outcome against the binding it is
evidence for (an engine class's `platform`, or a subtest's `platform` parameter), renders both
reference specifications under every example profile for the platform, and writes: the
outcomes, each failure and skip, every gap the builds' manifests report, and the gaps the
binding declares in its `PLATFORM_PROFILE.md` `Gaps` field. A binding is `standard` only when
its report shows no failure, no skip and no gap.

`--check` writes nothing in place and fails when a regenerated report differs from the
committed one, naming any gap the committed report does not carry, so a change never adds a
gap unseen. It also fails on any failing or skipped test. CI runs it with every engine and
uploads the regenerated reports; commit them when they change. Engine-version lines are
compared loosely, since they depend on where the tests ran.

## Tests

```sh
python -m pip install duckdb pytz 'psycopg[binary]' teradatasql
python -m unittest discover -s tooling/bindings/tests -v
```

The tests discover every binding that declares its phases, render both reference
specifications (IT Service Desk and the unrelated Customer Orders) through the example
organisation's profile for that platform, and run them on the engine: deployment, every
check, the four ITSD source files loaded through the binding's own key allocation, metrics
and cookbook recipes, similarity search, bitemporal maintenance, detected mutations, evidence
publication, staleness, designated-producer and cautious-fallback trust maps.

`engines.py` holds each engine's driver: how to connect, its parameter marker, how one check is
isolated and how evidence is written in one transaction. Drivers differ; the SQL each runs is
the binding's own.

Set `TERADATA_TEST_DSN` to the teradatasql connection parameters, as JSON, for a disposable
Teradata system where the user may create databases and roles. Teradata commits each DDL
statement, so the tests deploy each specification once, under databases and roles prefixed
`anptest_`, reset the rows between tests, and drop everything with that prefix, and nothing
else, before and after. `test_teradata_dialect.py` checks every statement the Teradata binding
renders against its platform profile's dialect rules, with no engine.

Set `POSTGRES_TEST_DSN` to a disposable PostgreSQL database whose role may create roles and
schemas. Each PostgreSQL test runs in one transaction that is rolled back, so nothing is left
behind and nothing existing is dropped. Without a connection the PostgreSQL or Teradata tests
skip, and without the DuckDB driver the DuckDB tests skip; a skip is a gap in engine coverage,
never a pass. Fixture loading lives only in the tests; it is not a product loader.
