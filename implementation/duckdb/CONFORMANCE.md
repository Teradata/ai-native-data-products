<!-- design-lint: ignore-file (implementation evidence scope) -->

# DuckDB conformance scope

Status: **draft, non-conforming**. This binding was converted from hand-written SQL and a bespoke Python compiler to Jinja templates driven by the shared tooling. It has declared gaps, listed below, and is not described as conforming until they are closed. The older fixed check inventory (hundreds of Customer360 checks) is no longer a coverage claim: checks are rendered from each product's declared entities and relationships.

Tests live in `tooling/bindings/tests` (`test_bindings.py`, `test_duckdb_binding.py`) and `tooling/validation/tests/test_binding_package.py`. They render into memory or temporary directories and execute on an actual DuckDB engine. They skip only when the `duckdb` driver is not installed, and a skip is a gap.

Engine evidence: DuckDB **1.5.6** through the Python driver, on Windows. No other DuckDB version, no JDBC or CLI client and no other operating system has been tested.

## Verified

| Contract | Evidence |
|---|---|
| Every template renders | A test records the templates loaded while rendering ITSD plus the standalone key-allocation and maintenance templates, and fails if any `.sql.j2` file is unrendered. |
| Template hygiene | No plain `.sql` and no Python under `implementation/duckdb`; no substitution convention other than Jinja; no product literals in templates or declarations. |
| Portability | ITSD and an unrelated laboratory product render from the same templates with different containers and entities; no output carries the other product's names or an unresolved expression. |
| Composition | Seven compositions (domain alone and with each module, and Semantic with Observability) deploy and execute with only their dependencies. |
| Engine execution | The complete ITSD product deploys on DuckDB, loads the four ITSD CSVs, and its consumer views return the source counts. |
| Temporal | Half-open as-of boundaries, hidden lifecycle columns on consumer views, two-axis bitemporal correction, effective-history replay, late change, deletion and restoration, rollback of a failed replacement, overlap detection by mutation. Replacement rows come from a test-only planner. |
| Keys | Permanent keymap, idempotent allocation, foreign-key rejection of an unallocated identity. |
| Metadata and discovery | Physical comment and inventory checks detect mutations; the manifest, relationship paths and lineage views are queried; runtime stores have no consumer view and are not agent consumable. |
| Search | Different vector dimensions; join-back to the authoritative Domain row after a source update; a persisted file closed, reopened read-only and queried; no extension is installed or loaded. |
| Validation evidence | Wire 2.1 run, area and check rows via the shared validator, including execution errors, failed-warning severity, the shared `trust_cases.json` producer cases consumed through the SQL trust map, latest evidence per area, expiry, designated producer and cautious fallback, and the command-line validator. |
| Tooling | The renderer refuses reserved or non-empty output directories and unsupported settings. |

## Declared gaps

| Gap | Detail |
|---|---|
| Build context | The renderer consumes the legacy `context.json` and `placement.json` inputs, not the shared build-context document from `tooling/build`. Cross-platform acceptance (one resolved context for every binding) is not shown. |
| Organisation profile | No profile setting is consumed. Naming rules, classification mapping, retention bounds and environment variation are not exercised. |
| Standard-owned names | Names such as the manifest, column catalogue, trust map and relationship views are fixed in the templates, not mapped from the build context. |
| Adoption of existing structures | Unsupported. A build that needs an adoption must report it as a gap. |
| Roles, grants and runtime privacy | Unsupported by the engine. The access-layer template emits a comment-only boundary record. The access-layer trust area has no evidence. |
| Temporal enforcement | No exclusion constraint or partial unique index: non-overlap and a single current row are detected by checks, not prevented by the engine. A direct SQL write can violate them. |
| Change planning and audit | The maintenance template is a transaction body. No planner is shipped (the test planner is a fixture), and no change event is emitted by it. |
| Concurrency | One writing connection is assumed. No concurrent-writer or crash-recovery test exists. |
| Coverage not carried over | The earlier reference's bespoke checks are not reproduced: point-in-time training function and retrospective-rewrite guard for Prediction, metric and synonym reference checks, content-duplication allowlists, cookbook query execution, per-module documentation minimums beyond `memory:coverage` and placement inventory checks. |
| Embedding, model and operations | No encoder, feature pipeline, trained model, retrieval quality, backup, durability or performance evidence. Strong structural evidence never substitutes for these. |
| Versions and clients | DuckDB versions other than 1.5.6, JDBC and CLI clients are untested. |

## Reading the evidence

The ITSD input is a design and build example, not a prebuilt product. Its seven captured decisions do not satisfy per-module documentation minimums, so the validator reports `memory:coverage` until the builder records the remaining real documentation. Embedding and scoring tables begin empty; no synthetic probability or model quality fills the gap. A passing structural check means only that check passed.
