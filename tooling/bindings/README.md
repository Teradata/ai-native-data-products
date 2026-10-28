# Rendering and validating bindings

Tools for the platform bindings, each a `binding.toml` and a `dialect.py` (currently
PostgreSQL, DuckDB and Teradata). A build has three inputs: a design specification, an organisation
profile and the platform binding. [`tooling/build`](../build/) resolves the first two and the
binding's declarations into one build context; `render.py` asks the binding's dialect for each
phase, the deploy script and each check from that context alone. [`dialect.py`](dialect.py) loads
the dialects and holds no SQL: SQL stays in `implementation/{platform}/dialect.py` and the
portable defaults every platform extends, `implementation/portable/dialect.py`. Everything here
is standard-library Python 3.11 or later.

<!-- index:start -->
| Line | Section | Covers |
|---:|---|---|
| 22 | [Rendering](#rendering) | `render.py`: a specification and configuration into phases, checks, context and manifest |
| 41 | [Seed data: generating and loading](#seed-data-generating-and-loading) | `load.py` and the `load.toml` mapping; `seed.py` for any specification; embeddings |
| 79 | [Validation](#validation) | `validate.py`: running the checks and publishing evidence |
| 95 | [Conformance reports](#conformance-reports) | Generating and checking each binding's `CONFORMANCE.md` |
| 117 | [Tests](#tests) | The engine tests, their drivers and connections |
<!-- index:end -->

## Rendering

```sh
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md config/implementation.example.toml --target postgres --output build/itsd-postgres
```

The target names the platform, so the same specification with `--target duckdb` renders the
DuckDB binding, and with `--target teradata` the Teradata one. An invalid specification or
configuration renders nothing and reports why.
`--output` must be empty and outside the skill corpus; use an ignored `build/` directory or a
separate product repository. Rendering neither connects to a database nor executes SQL.

The output holds one file per phase that renders anything for the composition, `deploy.sql`
(the phases joined by the dialect's `deploy`, in one transaction where the engine can
roll DDL back), `context.json` (the resolved build context) and `manifest.json`: the checks with their test ids
(`{PRODUCT_CODE}-{CHECK}-{NNN}`) and scopes, where evidence is published, and every **gap**,
meaning something the specification asks for that this binding does not render. Gaps are
printed when rendering and never hidden.

## Seed data: generating and loading

Loading needs the engine's driver, as validation does. A product's own pipelines load its data. To stand a product up before they exist (to see a
build work, review it, or try a query), `load.py` deploys a build and loads seed files into it
on any binding, and `seed.py` writes seed files for any specification that has none.

```sh
# an example's own data, through its load mapping
python tooling/bindings/load.py build/cmdb-postgres examples/it-asset-configuration-data-product/load.toml --deploy
python tooling/bindings/load.py build/csa-duckdb examples/customer-service-agreements-data-product/load.toml --database csa.duckdb --deploy --embeddings placeholder

# any specification: generate structurally valid rows and their mapping, then load them
python tooling/bindings/seed.py build/myproduct-duckdb --output build/myproduct-seed
python tooling/bindings/load.py build/myproduct-duckdb build/myproduct-seed/load.toml --database myproduct.duckdb --deploy
```

A **load mapping** (`load.toml`) lists, in load order, each source file, the entity it fills,
the source column of its natural key, where validity starts, and any column whose name differs
from the attribute's; [`load.py`](load.py)'s docstring defines it, and each example carries
one. Everything else comes from the build: names and placement from `context.json`, key
allocation from the binding's dialect, and how a flag, an open interval end or a vector is
passed from the engine (`engines.py`). A reference's source value is its target's natural key;
history versions are closed by the next version's start; validity is backfilled, so a version
is known from when it became valid. `--deploy` applies the build's phases first.

Embeddings are not seed data. `--embeddings placeholder` writes deterministic feature-hashing
vectors under the model name `feature-hashing placeholder`, so the similarity function, which
reads only the declared model's vectors, never returns them; they exercise storage, not search.
`--embedder module:function` writes real ones from a function taking a list of texts and the
declared model's name.

[`seed.py`](seed.py) writes one CSV per Domain entity and the matching mapping: each value of
its attribute's logical type, enum members, required attributes always present, unique natural
keys, references to generated rows of their target, and `Volume:`'s initial rows (capped by
`--max-rows`). Business rules beyond the types do not hold, so quality rules may fail on it;
the build's checks pass. The examples' own data is realistic and frozen: the two that accompany
the IT Service Desk are rebuilt only by `tooling/examples/generate_seed.py`.

## Validation

After deployment and loading, install the driver (`duckdb` and `pytz`, `psycopg[binary]`, or `teradatasql`) and validate:

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
binding declares in the `gaps` of its `binding.toml`. A binding is `standard` only when
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
isolated, how evidence is written in one transaction, how a rendered phase is applied, and how a
flag, an open interval end and a vector are passed as parameters. Drivers differ; the SQL each runs is
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
never a pass. The tests load ITSD's files with their own fixture loader; `load.py` is the
loader for everyone else, and it is not a product's production pipeline either.
