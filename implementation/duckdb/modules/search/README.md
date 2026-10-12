---
title: DuckDB Search Module Implementation
anchor: search
type: implementation
status: standard
version: 2.0
normative: true
implements: search
platform: duckdb
---

# DuckDB Search

Binding of [Search](../../../../design/modules/search.md). [schema.sql](schema.sql) stores only vectors, generic Domain ids, model provenance and temporal metadata. [functions.sql](functions.sql) implements the portable exact baseline.

**Provides:**

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Cosine ranking over current vectors; id breaks ties. |
| `Embed` | Demonstration SQL lexical encoder; production encoder is a host concern. |

The example uses FLOAT[3] and a model whose three axes indicate savings/payments/credit words. The query and source use the identical encoder; all vectors are finite and nonzero. This proves reproducibility and join-back, **not** semantic model quality. Register a production model with version/dimensions and deploy a separate fixed-array table for each dimension family. Compare vectors only within the same model space; do not silently pad or mix dimensions.

Searchable context is a view joining Product by id. No description or name is persisted in Search. Superseded vectors stay in SCD2 history. `C360-SEARCH-001`, join-back, allowlist and temporal checks verify dimensions, model identity, exact current resolution and history. Metadata and documentation are captured at deployment.

Optional acceleration uses `INSTALL vss; LOAD vss;` and HNSW in a separate, rebuildable in-memory working catalogue. Current DuckDB documentation labels [persistent HNSW experimental](https://duckdb.org/docs/current/core_extensions/vss#persistence). This implementation does not enable it or ship an untested index deployment script. The core build/tests use no VSS extension and no model/network download.
