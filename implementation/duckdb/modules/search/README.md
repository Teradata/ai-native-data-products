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

## Templates

`01-tables.sql.j2` calls `module_tables('search')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). The embedding store holds identifiers, vectors and provenance, never source content. A `Vector` column binds to a fixed-size `FLOAT[n]` array, which rejects a vector of the wrong dimension on insert.

`02-similarity.sql.j2` emits one table macro per `Embedding:` block in the context's `embeddings` that has an `objects.function`. It reads the block's `store` (through `named`), `vector_column`, `dimensions`, `similarity`, `threshold`, `name` and, where present, `model`. The macro `(query_vector, result_limit)`:

- casts the query vector to `FLOAT[n]` of the declared dimension, so a vector of another length is an error;
- reads the store's consumer view, so only current vectors are ranked, restricted to rows whose source attribute is the block's name (and to its model, where the block names one);
- scores by the declared similarity: `array_cosine_similarity`, `array_inner_product`, or `1 / (1 + distance)` for euclidean (`array_distance`) and manhattan;
- keeps scores at or above the declared threshold and returns `(entity_id, similarity)` ordered by score, then identifier, with the limit clamped to 0..1000.

The macro returns identifiers only. Join-back to Domain is the caller's: the cookbook's similarity recipes join the macro to the entity's consumer view.

Vectors come from the encoder the specification declares, outside the database; no encoder is substituted. The templates install and load no extension; the VSS extension and its HNSW index are not emitted, and DuckDB documents its persistent form as experimental. Validate query vectors for finite elements and nonzero norm at the encoder and query boundary.

## Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Exact ranking over current vectors by the declared similarity and threshold. |
| `EntityJoinBack` | Results carry the Domain identifier; recipes join to the Domain consumer view. |
| `CurrentStateFilter` | The macro reads the store's consumer view. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review the declared embedding and model provenance; engine test that the fixed-size array rejects the wrong dimension. |
| `INV-SEARCH-002,004` | Engine test that the macro ranks current vectors of its embedding and applies the threshold. |
| `INV-SEARCH-005` | Shared temporal macros and the `entity temporal` check. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
