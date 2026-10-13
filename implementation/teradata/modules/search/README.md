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

A `Vector[n]` binds to `VARCHAR(32000) CHARACTER SET LATIN` holding a JSON array of numbers, with a `CHECK` (`REGEXP_SIMILAR`) that the text is an array of exactly `n` numbers. Teradata 17.20 and the 20.00 release tested here have no vector type, and a `JSON` column takes no `CHECK`, so the dimension is enforced on the text. A vector of the wrong dimension is refused by the engine; the engine tests show it.

No similarity search object is emitted. `TD_VECTORDISTANCE` is a table operator: it cannot sit in a view or a SQL function, and a stored procedure that returns it as a dynamic result set has not yet been written. Each `Embedding:` block is reported in the manifest as a gap, and the cookbook's Search recipe falls back to reading the store's consumer view.

Vectors come from the encoder the specification declares, outside the database; no encoder is substituted. Validate query vectors for finite elements and nonzero norm at the encoder and query boundary.

## Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Not rendered: a reported gap. |
| `EntityJoinBack` | Rows carry the Domain identifier; consumers join to the Domain consumer view. |
| `CurrentStateFilter` | Consumer view over current vectors. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review the declared embedding and model provenance; the vector `CHECK` enforces the dimension, with an engine test that a wrong one is refused. |
| `INV-SEARCH-002,004` | Not shown: no similarity search object is emitted. |
| `INV-SEARCH-005` | Shared temporal macros and the `entity temporal` check. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
