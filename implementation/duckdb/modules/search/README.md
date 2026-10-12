---
title: DuckDB Search Implementation
anchor: search
type: implementation
status: draft
version: 2.0
normative: true
implements: search
platform: duckdb
---

# DuckDB: Search

Binding of [Search](../../../../design/modules/search.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`01-tables.sql.j2` consumes the design's embedding entity: identifiers, vectors and provenance, never source content. Declare the vector as `VECTOR(n)` in the helper input; it binds to a fixed-size `FLOAT[n]` array, with one dimension per model family. `02-similarity.sql.j2` emits a table macro per declared search. It takes the source entity, model and version, source facet, content projection and dimension; exact `list_cosine_similarity` ranking over current vectors joins back to the Domain consumer view, with ties broken by identifier and the result limit capped.

`Embed` requires a separately selected encoder and reproducible model provenance. No lexical toy is substituted for a real semantic model. Approximate indexing is optional and not emitted: the VSS extension and its HNSW index are excluded from the baseline, and its persistent form is documented by DuckDB as experimental. Tests assert the rendered product installs and loads no extension.

Tests exercise different dimensions, authoritative join-back after a Domain update, and a reopened read-only database file. Structural conformance does not establish encoder quality, model compatibility or retrieval recall; publish those as missing evidence until measured. The macro does not validate the query vector: validate shape, finite elements and nonzero norm at the encoder and query boundary.

## Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Table macro with exact cosine ranking over current vectors of the declared model, version and facet. |
| `EntityJoinBack` | Macro joins vectors to the Domain consumer view on the stable identifier; no content is persisted in Search. |
| `CurrentStateFilter` | Search reads the current consumer view of the embedding entity. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review declared embedding fields and model provenance; dimension contract checked at render time. |
| `INV-SEARCH-002,004` | Search template joins to the declared Domain current view; native join-back test. |
| `INV-SEARCH-005` | Shared temporal DDL and as-of surfaces; generic overlap checks. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal and lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
