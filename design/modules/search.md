# Search Module — Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Search module — vector embeddings and similarity retrieval |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/modules/search/`](../../implementation/teradata/modules/search/) |

This document defines **what** the Search module must be and **why**, in platform-neutral
terms. Vector storage formats, distance functions, and index mechanisms are platform
specifics — they live in the implementation directory, bound to the capabilities named here.

---

## 1. Purpose

The Search module enables **semantic retrieval**: finding relevant content by meaning rather
than exact keyword match, using vector embeddings.

| AI-native characteristic | Purpose |
|--------------------------|---------|
| **Semantic search** | Find by meaning ("things like this"), not keywords. |
| **Similarity retrieval** | Rank entities by closeness in embedding space. |
| **RAG support** | Retrieve relevant context for language models. |
| **Autonomous discovery** | Agents find relevant data without human direction. |
| **Multi-modal** | Text, image, and structured-data embeddings under one contract. |

It enables similarity search, retrieval-augmented generation, similarity analysis, content
discovery, and multi-modal search — all built on one entity: the embedding.

---

## 2. Scope and Boundaries

**In scope:**

- **Vector embeddings** — semantic representations of entities; multiple models and
  dimensionalities supported.
- **Entity references** — the `Identifier` of the Domain entity each embedding describes, plus
  its kind. **Never the content itself.**
- **Embedding metadata** — which model and version produced the vector, and when.
- **Similarity acceleration** (optional) — approximate-nearest-neighbour indexes.

**Out of scope:**

| Concern | Owning module |
|---------|---------------|
| Source content (text, descriptions, names) | Domain — join back for it |
| Entity attributes | Domain |
| Engineered ML features | Prediction |
| Embedding-model definitions / metadata | Semantic |

---

## 3. Core Principle — Keys Only

The Search module stores **vectors and entity references only**. It never copies the content
that produced the embedding. Content is obtained by joining back to Domain
(`EntityJoinBack`). This is the single most important rule of the module:

- **Efficient** — storage is vectors plus ids, nothing more.
- **Single source of truth** — content lives once, in Domain.
- **Always current** — the join returns the latest content.
- **No drift** — there is no second copy to fall out of sync.

This principle is captured as `INV-SEARCH-001` and `INV-SEARCH-004`.

---

## 4. Entity Model

```
Entity: EntityEmbedding           [kind: History]
  embedding_id            : Identifier                        — surrogate key for the embedding record
  entity_id               : Reference [required]              — Domain entity this embedding describes (id only)
  entity_kind             : Enum{PARTY|PRODUCT|DOCUMENT}      — which Domain entity type (generic-reference discriminator)
  source_module           : ShortText [optional]             — module the source entity resides in (usually Domain)
  source_attribute        : ShortText [optional]             — which attribute was embedded (e.g. description)
  embedding               : Vector[dim] [required]           — the dense embedding; dim is model-dependent
  embedding_dimensions    : Integer [required]               — dimensionality recorded for reproducibility
  embedding_model         : ShortText [required]             — model that produced the vector
  embedding_model_version : ShortText [optional]             — model version, for reproducibility
  generated_at            : Timestamp [required]             — when the embedding was generated
  is_current              : Flag [current-flag]              — current embedding for this entity + model
  computation_method      : Enum{IN_DATABASE|EXTERNAL_API}   — how the vector was produced

  Keys:
    surrogate: embedding_id

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - Embed
    - NearestNeighbors
    - ApproxIndex{IVF|HNSW}      (optional)
    - CurrentStateFilter
    - EntityJoinBack
    - RichMetadata
    - AccessView

  Invariants:
    - INV-SEARCH-001: contains no attribute owned by Domain — keys only.
    - INV-SEARCH-002: references exactly one current Domain entity.
    - INV-SEARCH-003: records the model and dimensionality that produced the vector.
```

`entity_id` + `entity_kind` is the **generic reference** pattern from the Domain module
(§6) — one embedding table serves many entity kinds. The dimensionality `dim` is
model-dependent and varies per row; it is both carried by the `Vector[dim]` type and
recorded in `embedding_dimensions` for discovery and reproducibility.

**No content columns.** There is deliberately no `name`, `description`, or `text` attribute
here — those belong to Domain and are reached by join-back.

---

## 5. Applied Patterns

| Pattern | Contribution to Search |
|---------|------------------------|
| `temporal-lifecycle-metadata` | Embedding versioning — superseded embeddings (from a model change or a content change) are retained and reconstructable. |
| `object-placement` | Which container the embedding table and its views are created in, and who may reach them. |
| `physical-storage` | (When object storage is in use) physical path, file format, and partition strategy for embedding data. |
| `access-layer` | The searchable view that presents embeddings joined to Domain content under an explicit column contract. |
| `validation` | The conformance checks run before the module is declared done. |

---

## 6. Required Capabilities

| Capability | Why Search needs it |
|------------|---------------------|
| `Embed(text, model)` | Produce a `Vector[dim]` for content or for a query string. Optional in-database vs external — see note. |
| `NearestNeighbors(query, candidates, metric, k)` | Return the `k` closest candidates under a distance `metric`, as ranked `(id, distance)`. |
| `ApproxIndex{IVF\|HNSW}` | *(Optional)* Accelerate `NearestNeighbors` on large candidate sets. |
| `CurrentStateFilter` | Restrict to current embeddings. |
| `EntityJoinBack` | Obtain entity content from Domain for a similarity result. |
| `RichMetadata` | Agent-readable metadata on the embedding table and every column. |
| `AccessView` | Expose a searchable view (embedding + Domain content) with an explicit column contract. |

**Portability note.** `Embed` differs materially across platforms — some provide in-database
embedding, others are external-API only. It is therefore declared with a
`computation_method` and treated as pluggable, and `ApproxIndex` is optional. A design that
assumed in-database embedding would silently encode one platform's capability; this module
does not.

---

## 7. Similarity Retrieval and RAG

Both are expressed at the capability level. No platform query appears in this document.

**Similarity search:**

1. Obtain the query vector — either an existing embedding (`NaturalKeyLookup` on the source
   entity, then read its embedding) or a freshly produced one (`Embed(query, model)`).
2. `NearestNeighbors(query_vector, candidates, metric, k)` over the current embeddings of the
   relevant `entity_kind`, optionally accelerated by `ApproxIndex`.
3. `EntityJoinBack` on `entity_id` to attach content from Domain.

**RAG retrieval** is the same shape with `k` tuned for context assembly: embed the question,
retrieve the top-`k` current embeddings for the relevant `entity_kind`, join back to Domain
for the passages, and pass those passages to the language model.

The invariant is that **content always comes from the join-back, never from the embedding
row** (`INV-SEARCH-004`).

---

## 8. Distance Metrics

Metric choice is semantic (mathematics), so it stays in design. The binding of each metric to
a platform function is an implementation detail.

| Metric | Use when | Definition |
|--------|----------|------------|
| **Cosine** *(default)* | Text embeddings, semantic similarity | 1 − (A·B) / (‖A‖ ‖B‖) |
| **Euclidean** | Spatial or geographic similarity | √Σ(Aᵢ − Bᵢ)² |
| **Manhattan** | Grid-like or high-dimensional sparse data | Σ ‖Aᵢ − Bᵢ‖ |

**Default:** cosine similarity for text and most semantic use cases.

**Index selection** (all bind to the `ApproxIndex` capability):

| Approach | Use when |
|----------|----------|
| Exact (brute force) | Small candidate sets, or already narrowed by a filter; absolute accuracy required. |
| `IVF` (cluster/partition) | Large sets; periodic rebuild acceptable; batch-oriented search. |
| `HNSW` (graph) | Interactive/real-time search; frequent updates; higher accuracy required. |

---

## 9. Integration with Other Modules

- **Domain** — the embedding references a Domain entity by `Identifier` and joins back for
  content (`EntityJoinBack`). The generic-reference pattern (`entity_id` + `entity_kind`) is
  used because one embedding table serves many entity kinds.
- **Semantic** — describes embedding strategy and model metadata (what a vector *means*); Search
  stores the actual vectors (instance data). The two are complementary and must not duplicate
  each other.

---

## 10. Invariants

- `INV-SEARCH-001`: an embedding record contains no attribute owned by the Domain module (keys only — no content duplication).
- `INV-SEARCH-002`: every embedding references exactly one current Domain entity.
- `INV-SEARCH-003`: every embedding records the model and dimensionality that produced it.
- `INV-SEARCH-004`: similarity and RAG results obtain content by join-back to Domain, never from attributes stored on the embedding.
- `INV-SEARCH-005`: superseded embeddings (from a model change or a content change) remain retrievable via the temporal pattern.

---

## 11. Designer Responsibilities

**Designers supply:**

| Element | Example |
|---------|---------|
| Entities to embed | Party, Product, Document |
| Attribute(s) to embed | description, notes, combined text |
| Embedding model | the chosen model and its dimensionality |
| Update strategy | on insert, daily batch, on demand |
| Expected query patterns | find similar products; semantic document search |
| Index strategy | exact, `IVF`, or `HNSW` (bind to `ApproxIndex`) |

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] The embedding entity carries **no** Domain-owned content attribute (`INV-SEARCH-001`).
- [ ] Reference to Domain uses the generic-reference pattern (`entity_id` + `entity_kind`).
- [ ] Model and dimensionality are recorded (`INV-SEARCH-003`).
- [ ] Similarity and RAG obtain content by join-back (`INV-SEARCH-004`).
- [ ] Embedding history is preserved via `temporal-lifecycle-metadata` (`INV-SEARCH-005`).
- [ ] A searchable view exists (`AccessView`).
- [ ] Every invariant has a check in the implementation.
- [ ] This document passes the design linter with no ignore directive.

---

## 12. Implementation

The Teradata binding — the embedding table, the searchable view, the similarity and RAG
query templates, and the invariant checks — lives in
[`implementation/teradata/modules/search/`](../../implementation/teradata/modules/search/).
Other platforms add sibling directories under `implementation/` without changing this document.

---

**End of Search Module Design Standard**
