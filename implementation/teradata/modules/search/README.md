---
title: Teradata Search Module Implementation
anchor: search
type: implementation
status: draft
version: 3.0
normative: true
implements: search
platform: teradata
---

# Teradata: Search

Binding of [Search](../../../../design/modules/search.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`01-tables.sql.j2` calls `module_tables('search')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). The embedding store holds identifiers, vectors and provenance, never source content.

A `Vector[n]` binds to `VARBYTE(n × 8)`: its elements as little-endian 8-byte floats, with a `CHECK (BYTES(...) = n × 8)` so a vector of the wrong dimension is refused. That is the encoding `TD_VECTORDISTANCE` reads directly; 4-byte floats in the same column are misread without an error (PLATFORM_PROFILE §7, Vectors). A producer packs a vector as `numpy.asarray(v, dtype="<f8").tobytes()` or `struct.pack(f"<{n}d", *v)` and binds it as a `VARBYTE` parameter.

`02-similarity.sql.j2` emits one stored procedure per `Embedding:` block in the context's `embeddings` that has an `objects.procedure`. It reads the block's `store` (through `named`), `vector_column`, `dimensions`, `similarity`, `threshold`, `name` and, where present, `model`, and the `Deploying user` binding setting. The procedure `(query_vector VARBYTE(n × 8), result_limit INTEGER)`:

- reads the store's consumer view, so only current vectors are ranked, restricted to rows whose source attribute is the block's name (and to its model, where the block names one);
- scores through `TD_VECTORDISTANCE`, with the store as the target table and the query as a one-row dimension, by the declared similarity, as every binding scores it: cosine and dot as `1 - distance` (the function's distances are `1 - cosine` and `1 - dot`), euclidean and manhattan as `1 / (1 + distance)`;
- returns no rows unless the query vector is exactly `n × 8` bytes and the limit is positive;
- keeps scores at or above the declared threshold and returns one result set of `(entity_id, similarity)`, ordered by score, then identifier, with the limit clamped to 0..1000.

`TD_VECTORDISTANCE` is a table operator: it cannot sit in a view or a SQL function, and it takes no bind or macro parameter inside its `ON` clauses. So the procedure writes the query vector into the request as a hex literal, left-padded because `FROM_BYTES` drops leading zero digits, and runs it as dynamic SQL. Each procedure carries a `COMMENT ON PROCEDURE`. A database's creator is not granted `CREATE PROCEDURE` on it, so where the profile names the `Deploying user`, the phase grants it on each database that holds a procedure. The access layer grants the read and agent tiers `EXECUTE PROCEDURE`; the procedure returns identifiers only, and join-back to Domain is the caller's (the cookbook's similarity recipe calls it with a `?` vector).

Vectors come from the encoder the specification declares, outside the database or in it; no encoder is substituted. An in-database encoder's output must be converted to 8-byte floats first: `mldb.ONNXEmbeddings`' `VARBYTE` output is 4-byte floats. Validate query vectors for finite elements and nonzero norm at the encoder and query boundary.

## Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Exact ranking over current vectors through `TD_VECTORDISTANCE`, by the declared similarity and threshold. |
| `EntityJoinBack` | Results carry the Domain identifier; consumers join to the Domain consumer view. |
| `CurrentStateFilter` | The procedure reads the store's consumer view. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review the declared embedding and model provenance; the vector `CHECK` enforces the dimension, with an engine test that a wrong one is refused. |
| `INV-SEARCH-002,004` | Engine test that the procedure ranks current vectors of its embedding and applies the threshold. |
| `INV-SEARCH-005` | Shared temporal macros and the `entity temporal` check. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
