# Work left: multi-product examples

Handoff notes for `feat/multi-product-examples`, written 2026-11-09 to move to a new machine.
**Delete this file (and its line in `.gitattributes`) before raising a PR for this branch.** It is
separate from `REMAINING_WORK.md`, which belongs to the earlier `feat/portable-design-standards`
work.

## The goal

One example data product per supported platform, used alone and together, to explore:

1. Implementing a product on each platform (Teradata, PostgreSQL, DuckDB).
2. Managing several products together.
3. Consuming several products for analytics.
4. Building a knowledge graph from the products.

Steps 1 and 2 of the plan are done (below). We stopped before step 3, by agreement, to discuss it.
The agreed approach for steps 3 to 5: **don't solve them inside the design standards first**.
Survey the open-source frameworks that might already do the job, and only fill a gap where the
market leaves one and the homework shows it is worth the investment.

## Where things stand

The branch was cut from `feat/80-toml-and-generator` (to use PR #83's new implementation code) and
is pushed to `origin/feat/multi-product-examples`. Commits on top of that base:

| Commit | What |
|---|---|
| `38643af` | Two new example products, CMDB and CSA, beside ITSD: briefs, READMEs, seed data, reference specifications, the run report |
| `399ed9d` | `tooling/bindings/load.py` (seed loader, any binding), `tooling/bindings/seed.py` (seed generator, any specification), a `load.toml` per example, `tooling/examples/generate_seed.py`, `test_seed_load.py`, docs and a build-role pointer |
| this file | The handoff |

| Product | Code | Folder | Composition | Primary platform |
|---|---|---|---|---|
| IT Service Desk | `ITSD` | `examples/it-service-desk-data-product/` | AI-Native (all six modules) | Teradata |
| IT Asset Configuration | `CMDB` | `examples/it-asset-configuration-data-product/` | Traditional (Domain, Semantic, Observability, Memory documentation) | PostgreSQL |
| Customer Service Agreements | `CSA` | `examples/customer-service-agreements-data-product/` | AI-Native without runtime Memory (`composition: custom`) | DuckDB |

All three share one organisation profile (`config/`) and one set of customer numbers. CMDB holds
the items ITSD's tickets were about and a dependency network (the graph seed). CSA holds
contracts, service levels per tier and service credits, and is the system of record for tier.
The CMDB and CSA data are generated from ITSD's files, with deliberate disagreements planted (see
the CSA README's table).

**Verified (2026-10-28 to 2026-10-29):**

- `spec_lint` clean on both new specifications; both render on all three bindings.
- All three examples deploy, load through `load.toml` and pass every check on **DuckDB 2.0.0,
  PostgreSQL 16.11 and Teradata 20.00.24** (ITSD 127/127, CMDB 107/107, CSA 114/114).
- `seed.py` output for all four specifications (the three examples and `customer-orders.md`)
  loads and passes on DuckDB.
- `tooling/validation/tests`: 288 pass. `tooling/release/tests`: 18 pass.
  `conformance.py --check --trust-committed teradata`: passes (the `engines.py` change broke nothing).
- `verify_skill.py --package`: 109 files, budget 180.

The full record, with a trust map per product and every finding, is
[`docs/example-runs/2026-10-28-cmdb-csa.md`](docs/example-runs/2026-10-28-cmdb-csa.md).

## Settled decisions (don't re-open)

- Domains: CMDB and CSA. Platforms and compositions as in the table above.
- The ITSD brief and all three examples' data are frozen fixtures; regenerate CMDB/CSA data only
  with `tooling/examples/generate_seed.py`, between cycles.
- References to another product are held as that product's natural key in a `ShortText`
  attribute, unenforced, and recorded as an `INTEGRATION` decision. This is a deliberate
  stand-in until step 3 decides otherwise.
- `load.py` and `seed.py` live in `tooling/bindings/` and ship in the skill package (agents use
  them). `tooling/examples/` is export-ignored (maintainers only).
- Seed loading is not a product's production pipeline; the build role tells agents to say so.

## Before raising the PR

1. Wait for PR #83 to merge, then rebase onto `main`. Expect conflicts only in
   `release/v2.0.0/examples.json`: regenerate it (`python tooling/release/build_release.py`)
   rather than merging by hand.
2. Rerun: `python -m unittest discover -s tooling/validation/tests`,
   `python -m unittest discover -s tooling/release/tests`,
   `python tooling/catalogue/build_catalogue.py --check`, `python tooling/skill/verify_skill.py --package`,
   and `python tooling/bindings/conformance.py --check --trust-committed teradata` with
   `POSTGRES_TEST_DSN` set (see the environment section).
3. Decide T5 below (what `examples.json` should say about the new examples' platforms).
4. Delete this file and its `.gitattributes` line.

## Open work

### Step 3: managing several products (next, to discuss)

The run's findings X1 to X7 (run report, "What this means for step 3") are the inputs. The three
that matter most:

- **X1. No business keys reach consumers.** Every consumer view carries surrogates only and no
  consumer tier can read a keymap, on every binding, ITSD included. So CMDB's `CUST-007` cannot be
  joined to ITSD's customer by any consumer.
- **X2. No reference to another product's entity.** Cross-product keys are plain attributes, so
  they are absent from relationship catalogues, `RelationshipPaths` and lineage: a graph built from
  the Semantic stores is three islands.
- **X3/X5. Shared entities and cross-product trust.** `Customer` exists in ITSD and CSA and they
  disagree; system of record is prose only. Each product's trust map is clean while the products
  contradict each other. The one organisation-level store (catalogue registry) had its templates
  retired on 2026-10-23.

Homework first: candidate open-source frameworks to evaluate against these. **None of this has been
researched yet; check each exists and what it covers before relying on it.**

| Concern | Candidates to look at |
|---|---|
| Data product and contract descriptors | Bitol's Open Data Contract Standard (ODCS) and Open Data Product Standard (ODPS); Data Contract Specification and `datacontract-cli`; Open Data Mesh's Data Product Descriptor Specification (DPDS) |
| Catalogue and registry across products | OpenMetadata, DataHub, Unity Catalog (open source), Apache Atlas, Amundsen |
| Lineage across products | OpenLineage and Marquez |
| Cross-product references in transformation code | dbt Mesh (cross-project `ref`) |
| Shared metrics and semantics | dbt MetricFlow, Cube, the Open Semantic Interchange initiative |
| Federated query across the three engines | Trino, DuckDB's `postgres` extension and `ATTACH`, Arrow Flight SQL |
| Knowledge graph | W3C DCAT, SKOS, the EKGF Data Product Ontology (DPROD), RDF/OWL tooling; property graphs: Apache AGE, Neo4j, Kuzu, DuckPGQ, SQL/PGQ |

For each: does it address X1 to X7; does it fit the "one specification, any platform, any
organisation" principle; licence and maturity; what we would still have to build.

### Step 4: analytics across products

The four questions the three products exist to answer (in the README of each example and the
original plan):

1. Which customers are owed service credits? (ITSD actuals vs CSA contracted resolution hours.)
2. Do tickets on ageing or end-of-support items breach more? (ITSD + CMDB.)
3. Which renewals in the next 90 days are at risk? (all three.)
4. If a server fails, which items, customers and contracts are exposed? (graph walk across all three.)

Blocked on X1 (keys) and X6 (three engines, no shared query surface). The planted data gives each
question a findable answer.

### Step 5: knowledge graph

Two layers to explore: a **metadata graph** (products, entities, relationships, glossary,
cross-product links, from each Semantic store and registration) and an **instance graph**
(customers, items, tickets, contracts). `INV-OBS-008` (one product, one graph) means a graph across
products sits at organisation level.

### Findings from the run, not yet acted on

Standards:
- **S1.** Domain §3.3's Relationship template (`inline`, natural key only) contradicts the
  Specification Standard §3.3 and `spec_lint` (`inline` needs surrogate and natural). The examples
  added surrogates.
- **S2.** No "now" in the expression vocabulary, so "past end of support" and "ending in 90 days"
  cannot be metrics.
- **S3.** `composition` is unchecked free text.
- **S4.** `spec_lint` accepts a History entity with no current or deleted flag.

Bindings and tooling:
- **T1.** `integrity`, `freshness` and `uniqueness` quality functions are rendered by no binding.
- **T2.** `as_of`, `sum_related`, `count_related`, `days_since_last` are rendered by no binding (half
  of CSA's features).
- **T3.** A trust map shows `strong` over an empty module (CSA prediction has no rows).
- **T4.** `{entity|snake}` mangles acronyms (`CIType` -> `citype`; the example renamed it `ItemType`).
- **T5.** `release/v2.0.0/examples.json` lists no platforms for CMDB and CSA: `build_examples`
  credits the shared `config/` targets to ITSD only. Decide whether they should be credited, or
  only once they are in the conformance runs.
- **P2.** Nothing generates embeddings with the declared model, populates a feature group or scores
  a model. `load.py --embedder module:function` is the hook for real embeddings (bge-small-en-v1.5
  for ITSD and CSA); not yet written or tried.
- **F1.** ITSD's `tickets.csv` has a replacement character in TKT-00011's subject.

Also deferred: engine tests for `load.py` in `tooling/bindings/tests`. Adding them changes every
`CONFORMANCE.md`, including Teradata's, which needs a full live run (about 15 minutes); best done
after the rebase onto `main`.

## Setting up the new machine

Nothing below is in the repository except what is linked. The old machine's Claude memory files
(`~/.claude/projects/.../memory/`) and session scratchpads do not travel; the facts that matter are
here.

- **Python** 3.11+ (3.13 was used; CI uses 3.12). A venv with the engine drivers:
  `python -m pip install duckdb pytz "psycopg[binary]" teradatasql` (versions used: duckdb 2.0.0,
  psycopg 3.3.6, teradatasql 20.0.0.72). The linters and tests in `tooling/validation` need only the
  standard library.
- **PostgreSQL** 16 for the PostgreSQL runs. On Windows without an install, the EnterpriseDB binaries
  zip (`postgresql-16.x-windows-x64-binaries.zip`) is enough: `initdb -A trust -U postgres -D pgdata`,
  then `pg_ctl -D pgdata -o "-p 55432 -c listen_addresses=localhost" start`. Roles are cluster-wide:
  drop a test database's `<code>_role_*` roles with it, or the next deployment of that product fails.
- **Teradata**: the ClearScape connection parameters were in `c:\git\.teradata_test.json` on the old
  machine (user `DEMO_USER`, may create databases and roles). Move it by a secure route; never commit
  it. Pass it as `TERADATA_DSN="$(cat <file>)"` (or `TERADATA_TEST_DSN` for the tests). The binding
  tests own the `anptest_` prefix; use another prefix for anything else (`anpload` below). A killed
  client can leave a session holding locks: `SELECT SYSLIB.AbortSessions(1, 'DEMO_USER', <session>, 'Y', 'Y')`.
- The system `gh` on the old machine was a Python package, not the GitHub CLI.
- That machine set `PYTHONDONTWRITEBYTECODE=1`; CI does not. Before pushing a change to a test that
  lists directories, rerun with it unset.

## Reproducing the runs

DuckDB (any example; swap the folder and code):

```bash
python tooling/bindings/render.py examples/customer-service-agreements-data-product/design-output/design_specification.md config/implementation.example.toml --target duckdb --output build/csa-duckdb
python tooling/bindings/load.py build/csa-duckdb examples/customer-service-agreements-data-product/load.toml --database csa.duckdb --deploy --embeddings placeholder
python tooling/bindings/validate.py build/csa-duckdb/manifest.json --database csa.duckdb
```

PostgreSQL: create an empty database, set `POSTGRES_DSN`, render with `--target postgres`, then the
same `load.py --deploy` and `validate.py` without `--database`.

Any specification with no data: `python tooling/bindings/seed.py build/<x>-duckdb --output build/<x>-seed`,
then load `build/<x>-seed/load.toml`.

Teradata: the example configuration's `teradata` target names fixed databases (`ITSD_DOM` and so
on), so render under a prefix of your own. This is the script used on 2026-10-29 (it lived in a
session scratchpad): it renders each example under `anpload_`, deploys, loads, validates, and drops
every `anpload_` object afterwards, touching nothing else.

```python
import json, os, re, sys, tomllib
from pathlib import Path

REPO = Path(r"C:\git\ai-native-data-products")
for sub in ("tooling/build", "tooling/bindings"):
    sys.path.insert(0, str(REPO / sub))
import build_context, load as loader, validate
from org_profile import Configuration
from render import render_context
from engines import engine

PREFIX, DSN = "anpload", os.environ["TERADATA_DSN"]
con = engine("teradata").connect(DSN)

def drop_all():
    like = f"LIKE '{PREFIX}!_%' ESCAPE '!'"
    for (role,) in con.execute(f"LOCKING ROW FOR ACCESS SELECT TRIM(RoleName) FROM DBC.RoleInfoV WHERE RoleName {like}").fetchall():
        con.execute(f'DROP ROLE "{role}"')
    while True:
        leaves = con.execute(
            f"LOCKING ROW FOR ACCESS SELECT TRIM(d.DatabaseName) FROM DBC.DatabasesV d WHERE d.DatabaseName {like} "
            f"AND NOT EXISTS (SELECT 1 FROM DBC.DatabasesV c WHERE c.OwnerName = d.DatabaseName AND c.DatabaseName <> d.DatabaseName)").fetchall()
        if not leaves:
            break
        for (name,) in leaves:
            con.execute(f'DELETE DATABASE "{name}"')
            con.execute(f'DROP DATABASE "{name}"')

def configuration():
    data = tomllib.loads((REPO / "config" / "implementation.example.toml").read_text(encoding="utf-8"))
    target = data["targets"]["teradata"]
    data["environments"] = {"phases": [PREFIX], "isolation": "container", "container_template": "{environment}_{container}"}
    target["principals"] = {k: re.sub(r"^create (\S+)", rf"create {PREFIX}_\1", v) if isinstance(v, str) else v
                            for k, v in target["principals"].items()}
    target["settings"] = {"deploying_user": json.loads(DSN)["user"]}
    return Configuration(data, "teradata", REPO / "config" / "design.example.toml")

drop_all()
try:
    for name in sys.argv[1:] or ["it-service-desk", "it-asset-configuration", "customer-service-agreements"]:
        d = REPO / "examples" / f"{name}-data-product"
        ctx, findings = build_context.resolve(d / "design-output" / "design_specification.md", configuration(), PREFIX)
        assert not findings, [str(f) for f in findings]
        files = render_context(ctx)
        out = REPO / "build" / f"{name}-teradata-{PREFIX}"
        out.mkdir(parents=True, exist_ok=True)
        for fname, text in files.items():
            (out / fname).write_text(text, encoding="utf-8")
        print(name, loader.load(con, ctx, d / "load.toml", deploy=out, embedder=loader.placeholder))
        results = validate.validate(con, json.loads(files["manifest.json"]))
        print(sum(r["status"] == "PASSED" for r in results), "of", len(results), "checks passed")
finally:
    drop_all()
    con.close()
```

Each product takes about eight minutes on ClearScape, most of it DDL.
