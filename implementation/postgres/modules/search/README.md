---
title: PostgreSQL Search Implementation
anchor: search
type: implementation
status: draft
version: 2.0
normative: true
implements: search
platform: postgres
---

# PostgreSQL: Search

Binding of [Search](../../../../design/modules/search.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`01-tables.sql.j2` consumes the design's embedding entity: identifiers, vectors and provenance, never source content. Declare the vector as `VECTOR(n)` in the helper input; it binds to DuckDB FLOAT[n] or PostgreSQL DOUBLE PRECISION[] with shape/cardinality checks. `02-similarity.sql.j2` takes the declared source entity, model/version, source facet, content projection and dimension; exact cosine ranking joins back to Domain.

`Embed` requires a separately selected encoder and reproducible model provenance. No lexical toy is substituted for a real semantic model. Approximate indexing is optional and not emitted. DuckDB VSS and PostgreSQL pgvector require separately reviewed deployment choices.

Tests exercise different dimensions and authoritative join-back. Structural conformance does not establish encoder quality, model compatibility or retrieval recall; publish those as missing evidence until measured. Validate input vectors for shape, finite elements and nonzero norm at the encoder/query boundary.

## Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Templates and enforcement limits described above. |
| `EntityJoinBack` | Templates and enforcement limits described above. |
| `CurrentStateFilter` | Templates and enforcement limits described above. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review declared embedding fields and model provenance; dimension contract checked at render time. |
| `INV-SEARCH-002,004` | Search template joins to the declared Domain current view; native join-back test. |
| `INV-SEARCH-005` | Shared temporal DDL/as-of surfaces; generic overlap checks. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal/lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
