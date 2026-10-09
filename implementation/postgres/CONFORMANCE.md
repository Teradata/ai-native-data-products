<!-- design-lint: ignore-file (implementation evidence scope) -->

# Conformance scope after template refactoring

The old product-specific check count is no longer a coverage claim. Checks are rendered from each product's declared entities and relationships. Tests live in tooling/bindings/tests and render into memory/temporary outputs rather than committing finished products.

| Contract | Evidence | Remaining obligation |
|---|---|---|
| Reusability | ITSD and unrelated laboratory contexts, renamed containers/entities, different compositions/dimensions | Additional product designs and workload-specific types |
| Physical metadata | Every declared field exists and carries a comment; keymaps registered | Full semantic meanings, metric/synonym coverage and domain quality |
| History | Half-open SCD2 and two-axis correction/reconstruction | Caller-planned replay, late changes, full temporal maintenance concurrency |
| Relationships | Shared ITSD source rows and current-surface reference checks | Historical referential completeness |
| Search / Prediction | Parameterised structures and source join-back | Encoder, feature pipeline, trained model and quality evidence |
| Memory | Actual authored decisions; minimum-capture check reports gaps | Complete glossary, cookbook and per-module capture at build time |
| Validation | Query errors retained; evidence append and explicit unknown/partial areas | Additional design-specific invariant checks |
| Access | Platform enforcement boundaries documented; native grants where supported | Deployment identity/membership and operational policy review |

Execution evidence for this refactor: DuckDB 1.4.3 and PostgreSQL 18.3 through PGlite 0.5.8/Psycopg. Native PostgreSQL 16 execution and concurrent-server testing are not claimed. All supported profiles render; execution tests cover current-state, event, SCD2 and bitemporal structures.

The shared ITSD input is a design/build example, not a prebuilt product. Its seven captured decisions alone do not satisfy per-module documentation minimums. The validator reports memory:coverage until builders capture the remaining real documentation. Embedding/scoring tables begin empty; no synthetic probability or claimed model quality fills that gap. Strong structural evidence never substitutes for semantic, ML or operational validation.
