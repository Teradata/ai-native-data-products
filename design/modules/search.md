---
title: Search Module
anchor: search
type: module
status: standard
version: 2.0
normative: true
---

# Search Module: Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
| ------------------- | ------------------------------------------------------------------------------------------ |
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Search module: vector embeddings and similarity retrieval |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | `implementation/{platform}/modules/search/`, one per platform |

This document defines **what** the Search module must be and **why**, in platform-neutral terms. Vector storage formats, the functions that compute each metric, and index algorithms are platform specifics: they live in the implementation directory, bound to the capabilities named here.

---

## 1. Purpose

The Search module enables **semantic retrieval**: finding relevant content by meaning rather than exact keyword match, using vector embeddings.

| AI-native characteristic | Purpose |
| ------------------------ | --------------------------------------------------------------- |
| **Semantic search** | Find by meaning ("things like this"), not keywords. |
| **Similarity retrieval** | Rank entities by closeness in embedding space. |
| **RAG support** | Retrieve relevant context for language models. |
| **Autonomous discovery** | Agents find relevant data without human direction. |
| **Multi-modal** | Text, image, and structured-data embeddings under one contract. |

Similarity search, retrieval-augmented generation, content discovery, and multi-modal search all build on one entity: the embedding.

---

## 2. Scope and Boundaries

**In scope:**

- **Vector embeddings**: semantic representations of entities. A product may use several models; each embedding entity holds one dimensionality.
- **Entity references**: the `Identifier` of the Domain entity each embedding describes, plus its kind. **Never the content itself.**
- **Embedding metadata**: which model and version produced the vector, and when.
- **Similarity acceleration** (optional): an approximate index, whose algorithm is the binding's choice.

**Out of scope:**

| Concern | Owning module |
| ------------------------------------------ | ------------------------- |
| Source content (text, descriptions, names) | Domain: join back for it |
| Entity attributes | Domain |
| Engineered ML features | Prediction |
| Embedding-model definitions / metadata | Semantic |

---

## 3. Core Principle

The Search module stores **vectors and entity references only**. It never copies the content that produced the embedding. Content is obtained by joining back to Domain (`EntityJoinBack`). This is the single most important rule of the module:

- **Efficient**: storage is vectors plus ids, nothing more.
- **Single source of truth**: content lives once, in Domain.
- **Always current**: the join returns the latest content.
- **No drift**: there is no second copy to fall out of sync.

This principle is captured as `INV-SEARCH-001` and `INV-SEARCH-004`.

---

## 4. Entity Model

```
Entity: EntityEmbedding           [kind: History] [profile: SCD2_HISTORY] [allocation: inline]
  embedding_id: Identifier  // surrogate key for the embedding record
  entity_id: Reference [required] [-> <Entity1> | <Entity2>] [discriminator: entity_kind]  // Domain entity this embedding describes (id only)
  entity_kind: Enum{<ENTITY1>|<ENTITY2>} [required]  // which Domain entity (generic-reference discriminator)
  source_module: ShortText [optional]  // module the source entity resides in (usually Domain)
  source_attribute: ShortText [required]  // which embedding this is: the Embedding block's name
  embedding: Vector[dim] [required]  // the dense embedding; one dim for the whole entity
  embedding_dimensions: Integer [required]  // dimensionality recorded for reproducibility
  embedding_model: ShortText [required]  // model that produced the vector
  embedding_model_version: ShortText [optional]  // model version, for reproducibility
  generated_dts: Timestamp [required]  // when the embedding was generated
  is_current: Flag [current-flag]  // current embedding for this entity and source attribute
  computation_method: Enum{IN_DATABASE|EXTERNAL_API}  // how this platform produced the vector; filled by the binding, never by the design

  Keys:
    surrogate: embedding_id
    natural:   entity_kind, entity_id, source_attribute

  Volume:
    initial: <rows at first load>
    growth:  <count> per <day|month|year>
    horizon: <duration>

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - Embed
    - NearestNeighbors
    - ApproxIndex      (optional)
    - CurrentStateFilter
    - EntityJoinBack
    - RichMetadata
    - AccessView

  Invariants:
    - INV-SEARCH-001: contains no attribute owned by Domain (keys only).
    - INV-SEARCH-002: references exactly one current Domain entity.
    - INV-SEARCH-003: records the model and dimensionality that produced the vector.
```

`entity_id` + `entity_kind` is the **generic reference** pattern from the Domain module: one embedding table serves many entity kinds, and the discriminator's members are the target entity names in upper case.

**Identity.** An embedding has no business identifier of its own. Its identity is the entity it describes and the embedding it is (`entity_kind`, `entity_id`, `source_attribute`), declared as its natural key and allocated `inline`. A new model or new source content produces a new version of the same embedding, so superseded vectors stay reconstructable (`INV-SEARCH-005`). Embedding entities version on `SCD2_HISTORY`, which a History entity may declare whatever the product's `DEC-TEMPORAL-PATTERN` (see Decisions to settle).

**One dimensionality per entity.** `dim` is fixed for the embedding entity and must match the `Dimensions` of every `Embedding` block written into it. It is carried by the `Vector[dim]` type and recorded in `embedding_dimensions` for discovery and reproducibility. A model with a different dimension needs its own embedding entity, declared `[module: search]` where its name does not say so, and its own `Embedding` block.

**The `Embedding:` block.** What is embedded, how, and how often is stated once per embedded source in an `Embedding:` block ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.2). The block's name becomes the embedding's `source_attribute`.

```
Embedding: <source_attribute>
  Entity:     <EntityName>
  Source:     <expression giving the text to embed>
  Where:      <condition; rows failing it have no embedding>
  Dimensions: <dim>
  Model:      <published model name>
  Similarity: cosine
  Index:      exact
  Threshold:  <similarity at or above which two items count as similar>
  Refresh:    daily
```

`Similarity` is `cosine`, `euclidean`, `dot` or `manhattan`; `Index` is `exact` or `approximate`; `Refresh` takes the refresh vocabulary (`on load`, `on demand`, `hourly`, `daily`, `weekly`, `monthly`). `Where`, `Model` and `Threshold` are optional.

**No content columns.** There is deliberately no `name`, `description`, or `text` attribute here: those belong to Domain and are reached by join-back.

---

## 5. Applied Patterns

| Pattern | Contribution to Search |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `temporal-lifecycle-metadata` | Embedding versioning: superseded embeddings (from a model change or a content change) are retained and reconstructable. |
| `object-placement` | Where the embedding table and its views are placed, what they are called, and who may reach them: all from the organisation profile, never from the design. |
| `physical-storage` | (When the organisation profile places data in object storage) the path, file format, and partitioning for embedding data, from that profile. |
| `access-layer` | The searchable view that presents embeddings joined to Domain content under an explicit column contract. |
| `validation` | The conformance checks run before the module is declared done. |

---

## 6. Capabilities and Composition

Search is an **enhancement** module: it hard-depends on Domain (an embedding references a Domain entity and joins back for content), so it cannot be deployed alone, though it is valid as an add-on to an existing Domain. See the [composition mechanism](../core/DESIGN_LANGUAGE.md).

**Provides** (to agents and consumers):

| Capability | Made available to |
| ------------------------------------------------ | --------------------------------------------------------------------------- |
| `NearestNeighbors(query, candidates, metric, k)` | Similarity retrieval and RAG over the current embeddings of an entity kind. |
| `Embed(text, model)` | Producing a `Vector[dim]` for content or a query string. |
| `ApproxIndex` | *(Optional)* Accelerating `NearestNeighbors` on large candidate sets, where an `Embedding` block declares `Index: approximate`. Which approximate algorithm is used is the binding's choice. |

**Requires:**

| Capability | Strength | Provider | Why |
| ---------------------- | -------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `EntityJoinBack` | `[hard]` | `module:Domain` | An embedding stores an `Identifier` only and joins back to Domain for content. Without Domain, Search cannot be deployed. |
| `CurrentStateFilter` | `[hard]` | `self` | Restrict to current embeddings. |
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on the embedding table and every column. |
| `AccessView` | `[hard]` | `self` | Expose a searchable view (embedding + Domain content) with an explicit column contract. |
| `SemanticRegistration` | `[soft]` | `module:Semantic` | Register the embedding entity and its columns in the Semantic map when Semantic is present (`INV-MASTER-002`). |
| `DocumentationCapture` | `[soft]` | `module:Memory` | Record decisions, glossary, and change history when Memory's documentation facet is present (the Documentation Capture Requirements section, `INV-MASTER-002`). |

**Portability note.** `Embed` differs materially across platforms: some provide in-database embedding, others are external-API only. It is therefore treated as pluggable: the design names the model, the binding decides how the vector is produced and records it in `computation_method`, and `ApproxIndex` is optional. A design that assumed in-database embedding would silently encode one platform's capability; this module does not.

---

## 7. Similarity Retrieval and RAG

Both are expressed at the capability level. No platform query appears in this document.

**Similarity search:**

1. Obtain the query vector: either an existing embedding (`NaturalKeyLookup` on the source entity, then read its embedding) or a freshly produced one (`Embed(query, model)`).
2. `NearestNeighbors(query_vector, candidates, metric, k)` over the current embeddings of the relevant `entity_kind`, optionally accelerated by `ApproxIndex`.
3. `EntityJoinBack` on `entity_id` to attach content from Domain.

**RAG retrieval** is the same shape with `k` tuned for context assembly: embed the question, retrieve the top-`k` current embeddings for the relevant `entity_kind`, join back to Domain for the passages, and pass those passages to the language model.

The invariant is that **content always comes from the join-back, never from the embedding row** (`INV-SEARCH-004`).

---

## 8. Distance Metrics

Metric choice is semantic (mathematics), so it stays in design, as the `Embedding` block's `Similarity`. The binding of each metric to a platform function is an implementation detail.

| Metric | `Similarity` | Use when | Definition |
| ---------------------- | ----------- | ----------------------------------------- | --------------------- |
| **Cosine** *(default)* | `cosine` | Text embeddings, semantic similarity | 1 − (A·B) / (‖A‖ ‖B‖) |
| **Euclidean** | `euclidean` | Spatial or geographic similarity | √Σ(Aᵢ − Bᵢ)² |
| **Dot product** | `dot` | Models trained for inner-product similarity, usually over normalised vectors | A·B |
| **Manhattan** | `manhattan` | Grid-like or high-dimensional sparse data | Σ \|Aᵢ − Bᵢ\| |

**Default:** cosine similarity for text and most semantic use cases.

**Index selection**, the `Embedding` block's `Index`:

| `Index` | Use when |
| ------------- | ---------------------------------------------------------------------------------- |
| `exact` | Small candidate sets, or already narrowed by a filter; absolute accuracy required. |
| `approximate` | Large candidate sets where interactive latency matters more than exact recall. Binds to `ApproxIndex`; the algorithm, and how it is rebuilt, is the binding's choice. |

---

## 9. Integration with Other Modules

- **Domain**: the embedding references a Domain entity by `Identifier` and joins back for content (`EntityJoinBack`). The generic-reference pattern (`entity_id` + `entity_kind`) is used because one embedding table serves many entity kinds.
- **Semantic**: describes embedding strategy and model metadata (what a vector *means*); Search stores the actual vectors (instance data). The two are complementary and must not duplicate each other.

---

## 10. Invariants

- `INV-SEARCH-001`: an embedding record contains no attribute owned by the Domain module (keys only: no content duplication).
- `INV-SEARCH-002`: every embedding references exactly one current Domain entity.
- `INV-SEARCH-003`: every embedding records the model and dimensionality that produced it.
- `INV-SEARCH-004`: similarity and RAG results obtain content by join-back to Domain, never from attributes stored on the embedding.
- `INV-SEARCH-005`: superseded embeddings (from a model change or a content change) remain retrievable via the temporal pattern.

---

## 11. Designer Responsibilities

**Designers supply:**

| Element | Recorded as | Example |
| ----------------------- | ------------------------------------------ | ----------------------------------------------- |
| Entities to embed | `Embedding` block `Entity` | Party, Product, Document |
| Text to embed | `Embedding` block `Source`, and `Where` | description, notes, combined text |
| Embedding model | `Embedding` block `Model` and `Dimensions`, matching the embedding entity's `Vector[dim]` | the chosen model and its dimensionality |
| Similarity metric | `Embedding` block `Similarity` | `cosine` |
| Update strategy | `Embedding` block `Refresh` | `on load`, `daily`, `on demand` |
| Index strategy | `Embedding` block `Index` | `exact` or `approximate` |
| Volume | The embedding entity's `Volume:` section | rows at first load, growth, horizon |
| Expected query patterns | Prose in the specification, explaining the design; not a build fact | find similar products; semantic document search |

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] The embedding entity carries **no** Domain-owned content attribute (`INV-SEARCH-001`).
- [ ] Reference to Domain uses the generic-reference pattern (`entity_id` + `entity_kind`), listing its targets and naming its discriminator.
- [ ] Model and dimensionality are recorded (`INV-SEARCH-003`); each embedding entity has one dimensionality, and every `Embedding` block's `Dimensions` matches it.
- [ ] Every embedded source has an `Embedding` block, and its name is the `source_attribute` it writes.
- [ ] Similarity and RAG obtain content by join-back (`INV-SEARCH-004`).
- [ ] Embedding history is preserved via `temporal-lifecycle-metadata` (`INV-SEARCH-005`).
- [ ] A searchable view exists (`AccessView`).
- [ ] The embedding entity and its columns registered in the Semantic map when the composition includes Semantic (`SemanticRegistration`, `INV-MASTER-002`).
- [ ] Every invariant has a check in the implementation.
- [ ] Every settled decision recorded per *Capturing the Design* in the [Master Design](../core/MASTER_DESIGN.md).
- [ ] This document passes the design linter with no ignore directive.

**Embedding-model sourcing.** Prefer an established embedding model and record it by its published name in the `Embedding` block: text families (e.g. BGE, Sentence-Transformers) or multi-modal families (e.g. CLIP) with their dimensionality. The specific model and version are recorded per embedding (`INV-SEARCH-003`).

---

### 11.1 Decisions to settle

These are the catalogued decisions a Search module design must settle. The recommendation is this standard's default; the question is what shifts it. The design skill walks a designer through each one at design time and records the answer in the product's own design.


| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-TEMPORAL-PATTERN` | `bi-temporal` | This is one product-wide choice, settled for the product's History entities. Embedding entities declare `[profile: SCD2_HISTORY]` on their own definitions, which History allows under either option: an embedding is regenerated wholesale when its source content or model changes, so there is no late-arriving correction to a past embedding to represent. Declare `SCD2_BITEMPORAL` on the embedding entity instead if you need to reconstruct what the index believed at a past instant. |
| `DEC-DELETE-STRATEGY` | `soft-delete` | Does anything analyse which embeddings were withdrawn, or when? |
| `DEC-TIMESTAMP-ZONE` | `zone-aware` | Is the data genuinely single-zone and certain to stay so? |


Every settled decision is recorded as part of designing the product: see *Capturing the Design* in the [Master Design](../core/MASTER_DESIGN.md) for the destination and the record set. This module's decisions take the id prefix `DD-SEARCH-<NNN>` and typically fall under `ARCHITECTURE` (vector storage strategy), `PERFORMANCE` (exact or approximate index), `SCHEMA` (embedding dimensions and model selection), `INTEGRATION` (RAG pattern and join-back strategy), `OPERATIONAL` (embedding refresh strategy).

---

## 12. Implementation

Each platform binding provides the embedding table, the searchable view, the similarity and RAG query templates, and the invariant checks, in `implementation/{platform}/modules/search/`, and conforms to the [Platform Implementation Authoring Standard](../core/IMPLEMENTATION_AUTHORING.md). Adding a platform changes nothing in this document.

---

**End of Search Module Design Standard**
