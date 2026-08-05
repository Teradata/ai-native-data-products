# Examples

Worked data products that exercise the standards end to end, and double as a learning aid.

Each example supplies the **inputs** a full design → build → review cycle needs: a reference brief with every decision pre-settled, a conforming placement standard, and seed data. Running one produces a deployed product plus its design brief, DDL, and trust map. Those outputs go to a product repository of their own, not back into this directory: what lives here is the fixed starting point, so a run is repeatable and two runs are comparable.

| Example | Composition | Platform | What it exercises |
|---|---|---|---|
| [`it-service-desk-data-product/`](it-service-desk-data-product/) | AI-Native (all six modules, Memory both facets) | Teradata | The full pipeline, including a deliberate departure from an advocated option and a `STRICT_SEPARATION` placement standard. |

---

## Why these exist

**Testing the standards against themselves.** The corpus can be internally consistent and still be unbuildable. The linters catch what is decidable from the text — an unsettled decision, a prohibited column name, a comment over the platform's limit — and nothing at all about whether an agent handed these documents can actually produce a working product from them. A full run is the only thing that reports on that, and every defect it surfaces is one the standards permitted.

That is only meaningful if the input never moves. A reference brief pre-settles every decision precisely so the **skills are the sole variable between runs**; change an answer in the brief and the comparison against the previous run is worthless. Treat each brief as frozen, and if a revised standard introduces a decision the brief does not cover, answer it with the advocated option and record it in the run's decisions log rather than editing the brief mid-cycle.

**Teaching.** The standards are written as contracts, which is right for a normative corpus and hard going as a first read. An example is the same content as a worked case: a real entity model, real settled decisions with their reasons, and a departure you can see the consequences of.

---

## How this differs from the eval fixture

[`tooling/evals/reference/customer-orders.md`](../tooling/evals/reference/customer-orders.md) is also a fixture, and it is not this.

| | `customer-orders.md` | `examples/` |
|---|---|---|
| What it is | A minimal design brief, six entities | A complete product: brief, placement standard, seed data |
| What runs it | `brief_lint`, on every test run | A full agent-driven cycle, by hand |
| What it proves | A conforming design still passes after a change to `design/` | The standards produce a working product |
| Cost to run | Milliseconds | A working session per phase |
| When it fails | The build is broken | The standards permitted something they should not |

They cover different risks and neither substitutes for the other. `customer-orders.md` is a regression guard on the corpus; an example is an integration test of the whole pipeline including the agent.

---

## Adding an example

An example earns its place by covering something the existing ones do not: a different composition, a different platform, a decision taken the other way, a scale the reference volumes do not reach. A second full AI-Native product on Teradata that settles every decision the advocated way tests nothing the first one did not.

Supply at minimum:

- **A reference brief** with every catalogued decision answered, and a stated reason for any departure from the advocated option. The seven catalogued decisions are in [`design/core/ADVOCATED_STANDARDS.md`](../design/core/ADVOCATED_STANDARDS.md).
- **A placement standard** conforming to the [object-placement pattern](../design/patterns/object-placement.md), since the build starter refuses to invent containers.
- **Seed data** small enough to load quickly and varied enough to exercise the invariants — nulls where the model permits them, at least one entity with no children, referential edges worth validating.

Keep the brief's column names canonical. A brief is an input the design agent is told not to re-open, so a non-canonical name in it propagates into the product and the run reports a defect that the fixture introduced rather than one the standards permitted.
