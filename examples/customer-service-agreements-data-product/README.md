# Customer Service Agreements: a worked example

Domain, Semantic, Search, Prediction, Observability and Memory's documentation facet: the AI-Native composition without runtime Memory, built on DuckDB. It is the commercial record behind the [IT Service Desk](../it-service-desk-data-product/) example: who each customer is, which contract they are on, what it promises per ticket priority, and the service credits paid when those promises are missed.

Everything in this directory is input, apart from the reference design specification in [`design-output/`](design-output/), which is the design phase's expected output and the build input. Running the example produces DDL, a database file and a trust map, and those belong in a product repository of their own.

## What the product does

It lists renewals, scores each active contract's risk of not renewing, finds contracts with a given clause, and reports contract value and credits paid. Contracts chain: each renewal references the contract it renewed.

Six entities: `Customer` and `Contract` (History, bi-temporal, keymap), `ServiceLevelTerm` (History, inline), `ServiceCredit` (Record, `EVENT_APPEND_ONLY`), and the two keymaps. Search embeds each contract's terms; Prediction holds `ContractFeatureSet` and the renewal-risk scores.

## What is supplied

| File | What it is |
|---|---|
| [`CSA_Reference_Brief.md`](CSA_Reference_Brief.md) | The fixed input: intake blocks for each phase, every catalogued decision pre-settled. |
| [`load.toml`](load.toml) | How the source files load into the entities, for `tooling/bindings/load.py`. |
| [`design-output/design_specification.md`](design-output/design_specification.md) | The reference design specification, validated by `spec_lint`. |
| [`config/`](../../config/) | The organisation profile, shared with the IT Service Desk. Target `duckdb` places a schema per module in one file, with access enforced outside it. |
| `data/customers.csv` | 21 customers in 23 versions: one row per version from its `valid_from`. |
| `data/contracts.csv` | 48 contracts: renewal chains from each customer's first contract to the active one, plus one lapsed and one terminated project. Terms are assembled from standard clauses (coverage hours, credit cap, termination, data residency, price). |
| `data/service_level_terms.csv` | 184 terms: response and resolution hours and credit percent per contract and priority, by tier. |
| `data/service_credits.csv` | 9 credits issued in 2026 for tickets that exceeded their contract's resolution time. |

## Where it disagrees with the service desk

The data is generated from the service desk's files and shares its customer numbers, and it disagrees with them on purpose. These are the cases a consumer of both products has to find:

| Case | Service desk says | This product says |
|---|---|---|
| CUST-007 tier | Gold | Platinum from 2026-04-01 |
| CUST-016 tier | Silver | Bronze from 2026-05-01 |
| CUST-012 contract start | 2021-05-10 | 2021-05-01 |
| CUST-021 | does not exist | signed 2026-06-15, no tickets yet |
| What breached | a flat target per priority (2, 8, 24, 72 hours) | resolution hours by tier and priority |
| Credit SC-0002 | TKT-00003 did not breach | a goodwill credit |
| Credit SC-0007 | TKT-00999 does not exist | a credit for it |

Some tickets exceeded their contracted resolution time and received no credit: the credits owed.

## What it deliberately exercises

- **A free composition**: the full module set without the runtime facet.
- **A `Record` entity** on the append-only profile, and a self-referencing `History` entity.
- **Features over related records** (`sum_related`, `count_related`, `days_since_last`) and a feature read as at its own observation instant.
- **A product that is the system of record** for an attribute another product also holds.

## Running it

```bash
python tooling/evals/spec_lint.py examples/customer-service-agreements-data-product/design-output/design_specification.md
python tooling/bindings/render.py examples/customer-service-agreements-data-product/design-output/design_specification.md config/implementation.example.toml --target duckdb --output build/csa-duckdb
```

Then deploy into a new database file, load the four source files through [`load.toml`](load.toml), and run the checks:

```bash
python tooling/bindings/load.py build/csa-duckdb examples/customer-service-agreements-data-product/load.toml --database csa.duckdb --deploy --embedder mymodule:embed
python tooling/bindings/validate.py build/csa-duckdb/manifest.json --database csa.duckdb
```

`--embedder` takes a function that embeds texts with the declared model. Without one, `--embeddings placeholder` stores stand-in vectors that the similarity function ignores. Nothing populates the feature set or scores the model: those are the product's own pipelines. The data is rebuilt from the service desk's files by `tooling/examples/generate_seed.py`, as a frozen fixture.
