<!-- design-lint: ignore-file (implementation evidence scope) -->

# PostgreSQL conformance scope

Status: **draft**. This file is maintained by hand until the generated conformance report the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §8.1 requires replaces it. It records what the tests show and what remains open; it is not a conformance claim.

The binding renders from the shared build context alone: [`render.py`](../../tooling/bindings/README.md) resolves a design specification and an organisation profile through [`tooling/build`](../../tooling/build/README.md) and renders the phases, deploy script and checks this binding declares. Checks are rendered from each product's entities and relationships, not from a fixed inventory.

Tests live in `tooling/bindings/tests/test_bindings.py` and `tooling/validation/tests/test_binding_package.py`. They render into memory or temporary directories. The PostgreSQL engine tests need `POSTGRES_TEST_DSN` and `psycopg`, and run each test in one transaction that is rolled back; without them they skip, and a skip is a gap.

Engine evidence: PostgreSQL **16.4** through Psycopg. No other server version has been tested.

## Verified

| Contract | Evidence |
|---|---|
| Build context | Both reference specifications (IT Service Desk and customer-orders) resolve under the example PostgreSQL profile and render from the context alone. An invalid specification renders nothing. |
| Portability | Changing the profile's container template changes every container name and no template; neither product's output carries the other's names. |
| Template hygiene | Jinja substitution only; no product literals; no plain SQL, Python or JSON in the binding directory; every template is reached by a declared phase, check or deploy template, or is caller-rendered; rendering is strict. |
| Engine execution | Both reference specifications deploy and every rendered check passes. The four IT Service Desk CSVs load, the consumer views return the source counts and every check still passes. |
| Temporal | A bitemporal correction through the maintenance template reads correctly at two knowledge times through the point-in-time function. A second open version of an identity is refused by the engine or found by the temporal check. |
| Keys | Allocation is permanent and idempotent. |
| Metadata and discovery | The metadata check finds a removed comment; the Semantic module check finds an unregistered table; the reference check finds a reference to a deleted target. Relationship paths follow the Semantic standard's bound. |
| Metrics, cookbook and search | Metric and cookbook recipes execute (parameterised recipes excepted); the similarity function ranks current vectors of its embedding and applies the declared threshold. |
| Validation evidence | Wire 2.1 run and area records; failures and errors never count as passes; latest evidence per area and staleness; designated producer, then cautious fallback; a legacy run graded on its counts and capped at `partial`; no evidence reads `unknown`; the shared `trust_cases.json` summaries; reported gaps cap the PRODUCT area at `partial`. |
| Access | The read tier reaches consumer views and point-in-time functions but not base tables; the agent tier cannot write runtime Memory scoped to another user. |
| Tooling | The renderer refuses reserved or non-empty output directories. |

## Declared gaps

| Gap | Detail |
|---|---|
| Composite access objects | Composite access objects (for example the IT Service Desk `TicketDetail`) are not rendered or registered; the manifest reports each one. |
| Unrendered expressions | An expression using a function the binding declares no fragment for (for example `as_of`, `integrity`, `freshness`) is carried unrendered and reported in the manifest. |
| Cookbook recipes | Cross-module recipes for module pairs with no relationship between them fall back to catalogue lookups over entity metadata rather than a working join. |
| Conformance report | This file is hand-maintained. The generated report is still to come. |
| Composition | Only the two reference compositions, each with all six modules, are engine-tested. Smaller compositions are not shown to deploy. |
| Adoption | Templates skip adopted containers and relations; no test exercises an adopted structure on this platform. |
| Maintenance | Only the bitemporal path of the maintenance template is engine-tested; the SCD2 path is not. No planner is shipped and no change event is emitted. |
| Concurrency | The maintenance template takes an advisory lock; no concurrent-writer test exists. |
| Historical references | The reference check covers current surfaces only. |
| Principals and membership | Roles are `NOLOGIN`. Login users, memberships and a shared-scope Memory policy are operator work. |
| Embedding, model and operations | No encoder, feature pipeline, trained model, retrieval quality, backup, durability or performance evidence. Structural evidence never substitutes for these. |

## Reading the evidence

The IT Service Desk input is a design and build example, not a prebuilt product. Embedding and prediction tables begin empty; no synthetic score or model quality fills them. A passing structural check means only that check passed.
