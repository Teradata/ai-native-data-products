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

Binding of [Search](../../../../design/modules/search.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[schema.sql](schema.sql) persists vectors, model provenance and Domain identifiers only. [functions.sql](functions.sql) implements `Embed` as a deliberately limited three-axis lexical encoder and `NearestNeighbors` as exact cosine ranking, joined to authoritative Product content. Query and source use the same encoder. Zero, null and non-finite vectors do not produce ranked matches; storage requires one-dimensional, three-element arrays.

PostgreSQL array declarations do not enforce length: explicit checks enforce this example's dimension. `DOUBLE PRECISION[]` is the baseline. Approximate indexing is not supplied. Production pgvector requires a separately approved extension, dimension/model tables, index operator class and recall testing; it is not advertised as core PostgreSQL.

`SEARCH`, `BOUNDARY`, `JOIN` and temporal checks plus vector-shape and live join-back tests cover structural behavior. Semantic retrieval quality remains an explicit unknown `Embed` area. Store real model/version provenance before replacing the toy encoder; no external model calls occur.
