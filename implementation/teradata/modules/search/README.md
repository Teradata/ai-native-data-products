# Teradata — Search Module Implementation

Concrete Teradata binding of [`design/modules/search.md`](../../../../design/modules/search.md).
Read the design document first; this directory only adds Teradata specifics.

## Files

| File | Purpose |
|------|---------|
| `01-embedding.sql.j2` | `entity_embedding` table — native `VECTOR`, keys only, full column metadata. |
| `02-searchable-view.sql.j2` | `v_{entity}_searchable` — embedding joined to Domain content (`AccessView`). |
| `03-similarity.sql.j2` | Similarity search and RAG retrieval templates (`NearestNeighbors` binding). |
| `validation.sql` | Runnable checks for the module's invariants. |

The `.sql.j2` files are Jinja2 templates rendered by `tooling/compiler`.

## Capability bindings

| Capability (design) | Teradata binding |
|---------------------|------------------|
| `Embed(text, model)` | `ONNXEmbeddings` (in-database) in ClearScape Analytics, or an external embedding API — recorded per row in `computation_method`. |
| `NearestNeighbors(query, candidates, metric, k)` | `TD_VectorDistance` table operator with `DistanceMeasure` and `TopK`. |
| `ApproxIndex{IVF\|HNSW}` | `KMEANS` (IVF-style) or `HNSW` via the Enterprise Vector Store API. |
| `CurrentStateFilter` | `WHERE is_current = 1`. |
| `EntityJoinBack` | `INNER JOIN Domain.{Entity}_H ON entity_id`, current-filtered. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN`. |
| `AccessView` | `v_{entity}_searchable` with an explicit column contract. |
| `SemanticRegistration` *(soft)* | When the composition includes Semantic: on deploy, `INSERT` embedding entity/column rows into `{product}_Semantic`. Skipped if Semantic is absent. |
| `DocumentationCapture` *(soft)* | When the composition includes Memory's documentation facet: on deploy, `INSERT` design-decision/glossary/change-log rows into `{product}_Memory`. Skipped if absent. |
| `EntityJoinBack` *(hard → Domain)* | `INNER JOIN Domain.{Entity}_H ON entity_id`, current-filtered. Search cannot deploy without Domain. |

## Logical-type bindings used here

| Logical type (design) | Teradata type |
|-----------------------|---------------|
| `Identifier` | `INTEGER GENERATED ALWAYS AS IDENTITY` |
| `Reference -> E` | `BIGINT` |
| `Enum{…}` | `VARCHAR(n)` with a documented value set |
| `Vector[dim]` | native `VECTOR` (`FLOAT32(dim)`), Vantage 20.00.26.XX+ |
| `Integer` | `INTEGER` |
| `ShortText` | `VARCHAR(n)` |
| `Timestamp` | `TIMESTAMP(6) WITH TIME ZONE` |
| `Flag` | `BYTEINT` |

**Legacy note.** On Vantage versions below 20.00.26.XX, or where per-dimension analytics are
required, bind `Vector[dim]` to columnar `FLOAT` columns `emb_0 … emb_{dim-1}` and reference
them with `TD_VectorDistance` range notation `[emb_0:emb_{dim-1}]`. Prefer the native `VECTOR`
type otherwise.

## Invariants → checks

| Invariant | Check |
|-----------|-------|
| `INV-SEARCH-001` (keys only) | `validation.sql` §1 — no content-like column on the embedding table. |
| `INV-SEARCH-002` (references a current entity) | `validation.sql` §2 — every `entity_id` resolves to a current Domain row. |
| `INV-SEARCH-003` (model + dims recorded) | `validation.sql` §3 — no null `embedding_model` / `embedding_dimensions`. |
| `INV-SEARCH-004` (content by join-back) | Enforced by pattern: similarity templates join to Domain; embedding table has no content. |
| `INV-SEARCH-005` (history preserved) | Bi-temporal / `is_current` columns present; superseded rows retained. |
