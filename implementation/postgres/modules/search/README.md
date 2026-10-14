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

## Templates

`01-tables.sql.j2` calls `module_tables('search')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). The embedding store holds identifiers, vectors and provenance, never source content. A `Vector` column binds to `DOUBLE PRECISION[]` with a `CHECK` that it has one dimension, the declared cardinality and no null elements.

`02-similarity.sql.j2` emits one SQL function per `Embedding:` block in the context's `embeddings` that has an `objects.function`. It reads the block's `store` (through `named`), `vector_column`, `dimensions`, `similarity`, `threshold`, `name` and, where present, `model`. The function `(query_vector DOUBLE PRECISION[], result_limit INTEGER)`:

- reads the store's consumer view, so only current vectors are ranked, restricted to rows whose source attribute is the block's name (and to its model, where the block names one);
- scores by the declared similarity: cosine, dot product, or `1 / (1 + distance)` for euclidean and manhattan;
- returns no rows unless the query vector is one-dimensional, of the declared length and free of nulls;
- keeps scores at or above the declared threshold and returns `(entity_id, similarity)` ordered by score, then identifier, with the limit clamped to 0..1000.

The function returns identifiers only. Join-back to Domain is the caller's: the cookbook's similarity recipes join the function to the entity's consumer view. It runs with invoker rights; the read and agent tiers reach it through `EXECUTE` and their `SELECT` on the store's consumer view.

Vectors come from the encoder the specification declares, outside the database; no encoder is substituted. Approximate indexing (for example pgvector) is not emitted. Validate query vectors for finite elements and nonzero norm at the encoder and query boundary.

## Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Exact ranking over current vectors by the declared similarity and threshold. |
| `EntityJoinBack` | Results carry the Domain identifier; recipes join to the Domain consumer view. |
| `CurrentStateFilter` | The function reads the store's consumer view. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review the declared embedding and model provenance; the vector `CHECK` enforces the dimension. |
| `INV-SEARCH-002,004` | Engine test that the function ranks current vectors of its embedding and applies the threshold. |
| `INV-SEARCH-005` | Shared temporal macros and the `entity temporal` check. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
