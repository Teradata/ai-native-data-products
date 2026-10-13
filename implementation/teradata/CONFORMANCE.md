<!-- design-lint: ignore-file (implementation evidence scope) -->

# Teradata conformance scope

Status: **draft**. This file is maintained by hand until the generated conformance report the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §8.1 requires replaces it. It records what the tests show and what remains open; it is not a conformance claim.

The binding renders from the shared build context alone: [`render.py`](../../tooling/bindings/README.md) resolves a design specification and an organisation profile through [`tooling/build`](../../tooling/build/README.md) and renders the phases, deploy script and checks this binding declares. Checks are rendered from each product's entities and relationships, not from a fixed inventory.

Tests live in `tooling/bindings/tests/test_bindings.py`, `tooling/bindings/tests/test_teradata_dialect.py` and `tooling/validation/tests/test_binding_package.py`. They render into memory or temporary directories. The Teradata engine tests need `TERADATA_TEST_DSN` and `teradatasql`; they deploy each reference specification once under databases and roles prefixed `anptest_`, reset its rows between tests, and drop everything with that prefix before and after. Without them they skip, and a skip is a gap.

Engine evidence: Teradata **20.00.24** (a ClearScape Analytics system) through teradatasql 20.0. Teradata 17.20 is the declared minimum and has not been tested.

## Verified

| Contract | Evidence |
|---|---|
| Build context | Both reference specifications (IT Service Desk and customer-orders) resolve under both Teradata example profiles and render from the context alone. An invalid specification renders nothing. |
| Portability | Changing the profile's container templates changes every database name and no template; neither product's output carries the other's names. |
| Template hygiene | Jinja substitution only; no product literals; no plain SQL, Python or JSON in the binding directory; rendering is strict. |
| Dialect | Every statement rendered for both specifications under both profiles, and under a product name long enough to overflow any comment, keeps the PLATFORM_PROFILE §7 rules: no comment over 255 characters, no `ORDER BY` in a view, no zone-qualified literal in a `DEFAULT`, no FROM-less select or untyped `NULL` in a set operation, no `:name` inside a stored string, no text column without its character set, no other dialect's `CREATE INDEX`, no dictionary view or column that does not exist, no unrendered Jinja. Each rule is shown to catch the construct it names. |
| Engine execution | Both reference specifications deploy on the engine and every rendered check passes. The four IT Service Desk CSVs load through the binding's own key allocation, the consumer views return the source counts and every check still passes. |
| Temporal | A bitemporal correction through the maintenance template reads correctly at two knowledge times through the governed view. A second open version of an identity, which the schema cannot refuse, is found by the temporal check. |
| Keys | Allocation through `MERGE` on the keymap's natural-key primary index is permanent and idempotent. |
| Metadata and discovery | The metadata check finds a removed comment; the Semantic module check finds an unregistered table; the reference check finds a reference to a deleted target. Relationship paths follow the Semantic standard's bound. |
| Metrics and cookbook | Metric and cookbook recipes execute (parameterised recipes excepted). |
| Search | A vector of the wrong dimension is refused by the engine. |
| Validation evidence | Wire 2.1 run and area records; failures and errors never count as passes; latest evidence per area and staleness; designated producer, then cautious fallback; a legacy run graded on its counts and capped at `partial`; no evidence reads `unknown`; the shared `trust_cases.json` summaries; reported gaps cap the PRODUCT area at `partial`. |
| Access | The read role holds `SELECT` on the consumer views' database and no right on the database of the tables beneath them, read from `DBC.AllRoleRightsV`. Views compile only through the implied grants the binding derives from the placement. |
| Tooling | The renderer refuses reserved or non-empty output directories; the validator runs through the Teradata driver. |

## Declared gaps

| Gap | Detail |
|---|---|
| Similarity search | No similarity search object is emitted: `TD_VECTORDISTANCE` cannot sit in a view or SQL function, and a procedure returning it is not yet written. Each `Embedding:` block is reported. |
| Point-in-time for consumers | Teradata SQL has no table functions. History is read through the governed base views, which are not granted to consumers; every versioned relation with a consumer view is reported. Whether consumers should reach history at all is an open question across bindings. |
| Runtime scope | `Runtime scope: unsupported`: runtime Memory is not restricted to the requesting identity's scope. Reported in every build with runtime relations. |
| Graph lineage and catalogue interface | The templates under `modules/observability/04` to `10` and `patterns/catalogue-interface/` read the old flat context and no phase renders them. A specification or profile asking for either has it reported. Porting or retiring them is an open decision. |
| Composite access objects | Composite access objects (for example the IT Service Desk `TicketDetail`) are not rendered or registered; the manifest reports each one. |
| Unrendered expressions | An expression using a function the binding declares no fragment for (`as_of`, `integrity`, `freshness`) is carried unrendered and reported in the manifest. |
| Classification protection and object storage | A profile's `mask` or `exclude` protection, and object-storage placement, are not rendered; the manifest reports each. |
| Adoption | Templates skip adopted databases and relations; no test deploys over an adopted structure on this platform, and the canonical column names over an adopted entity's aliases are not presented. |
| Cross-row temporal rules | Teradata enforces neither one open version per identity nor non-overlapping intervals in its schema; the `entity temporal` check finds both after the fact. |
| Maintenance | Only the bitemporal path of the maintenance template is engine-tested; the SCD2 path is not. No planner is shipped, no change event is emitted, and no lock serialises concurrent writers. |
| Deployment | DDL commits per statement, so a failed deployment cannot be rolled back; it is cleared by dropping the product's databases. |
| Conformance report | This file is hand-maintained. The generated report is still to come. |
| Composition | Only the two reference compositions, each with all six modules, are engine-tested. Smaller compositions are not shown to deploy. |
| Historical references | The reference check covers current surfaces only. |
| Principals and membership | Roles carry rights only. Users, memberships and passwords are operator work. |
| Embedding, model and operations | No encoder, feature pipeline, trained model, retrieval quality, backup, durability or performance evidence. Structural evidence never substitutes for these. |

## Reading the evidence

The IT Service Desk input is a design and build example, not a prebuilt product. Embedding and prediction tables begin empty; no synthetic score or model quality fills them. A passing structural check means only that check passed.
