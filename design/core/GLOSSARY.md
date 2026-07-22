# Glossary

## AI-Native Data Product Architecture — Shared Vocabulary

Terms used across the design standards. Notation terms (logical types, capabilities,
invariants) are defined in the [Design Language](DESIGN_LANGUAGE.md); this glossary covers the
architectural and domain vocabulary.

---

**Access Layer** — The mandatory access-control artefact of a data product. Creates the three
standard roles (`ROLE_READ`, `ROLE_AGENT`, `ROLE_ADMIN`) and grants them read access to module
containers, making the product discoverable and queryable. Deployed in two phases interleaved
with the module sequence. See the [access-layer pattern](../patterns/access-layer.md).

**Agent** — An autonomous software entity that perceives, reasons, and acts, consuming data
products to achieve goals without human mediation.

**Architecture Decision Record (ADR)** — A structured record of a significant design decision:
context, alternatives, rationale, consequences. Captured in the Memory module's design-decision
store.

**Attribute** — A field of an entity. For example, `party_key` is an attribute of the Party
entity. Typed with the [logical vocabulary](DESIGN_LANGUAGE.md#4-logical-type-vocabulary).

**Capability** — A named operation a design requires, declared abstractly and bound per
platform. See the [capability catalogue](DESIGN_LANGUAGE.md#61-standard-capability-catalogue).

**Co-location** — A platform's ability to store related data together so joins avoid data
movement. A physical optimisation; its availability and mechanism are platform-specific.

**Data Product** — A self-contained, well-defined data asset with clear ownership, interfaces,
and contracts — treated as a product, not a byproduct.

**Design / Implementation split** — The framework's core boundary: platform-agnostic standards
in `design/`, platform-specific bindings in `implementation/{platform}/`. See the
[Design Language](DESIGN_LANGUAGE.md#2-the-design--implementation-boundary).

**Documentation store** — The part of the Memory module that holds design memory (module
registry, design decisions, business glossary, query cookbook, implementation notes, change
log), co-located in the product's own Memory store so the product is self-contained.

**Embedding** — A dense vector representation of data (text, image, entity) in a
high-dimensional space where semantic similarity maps to geometric proximity. The logical type
is `Vector[dim]`.

**Entity** — A table-level object within the data product. `Party` is an entity; a specific
Party row is an *instance*.

**Feature Store** — A repository for storing, managing, and serving ML features with
consistency between training and inference. The role of the Prediction module.

**Identifier / Natural key** — `Identifier` is the internal, system-generated surrogate stable
across an entity's versions; a `NaturalKey` is the business identifier from the source system.
Every Domain entity carries both.

**Instance** — A single row within an entity. Party `CUST-123` is an instance of the Party
entity.

**Invariant** — A testable, platform-neutral rule a conforming implementation must satisfy.
Written `INV-<MODULE>-<NNN>`. See the [Design Language](DESIGN_LANGUAGE.md#7-invariants).

**Join-back** — The pattern by which a module obtains entity content: it stores an `Identifier`
and joins back to the Domain entity, rather than duplicating content. Realised by the
`EntityJoinBack` capability.

**Knowledge Store** — Design-time knowledge that guides *how* to build a product (modelling
standards, naming conventions, industry reference models) — distinct from the runtime knowledge
*about* a product, which lives in the Semantic module.

**Module** — A self-contained, independently deployable component responsible for a distinct
capability. The six standard modules are Domain, Search, Prediction, Observability, Semantic,
and Memory. Modules integrate through join-back and cross-module reference patterns.

**Point-in-Time (PIT)** — Reconstructing data as it existed at a specific past moment — critical
for reproducible ML features without leakage. Realised by the `PointInTimeReconstruction`
capability.

**RAG (Retrieval-Augmented Generation)** — A pattern where a language model retrieves relevant
context before generating a response; requires the Search module.

**Reference (relationship)** — An association between entities, expressed as a reference
attribute (`Reference -> <Entity>`), a hierarchy, or a semantic association.

**Semantic map** — The discovery metadata in the Semantic module (module registry, entity
catalogue, column dictionary, relationship graph, path finder, naming standards) that lets an
agent discover structure and generate valid queries autonomously.

**Temporal data** — Data that tracks change over time, distinguishing *valid time* (when true in
reality) from *transaction time* (when recorded). Governed by the
[temporal-lifecycle-metadata pattern](../patterns/temporal-lifecycle-metadata.md).

**Vector store** — A store optimised for holding and searching high-dimensional vectors by
similarity. On a given platform it may be a native capability or a specialist component; bound
by the `NearestNeighbors` / `ApproxIndex` capabilities.

---

**End of Glossary**
