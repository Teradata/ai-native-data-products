---
title: Glossary
anchor: glossary
type: core
status: standard
version: 1.2
normative: false
---

# Glossary

## AI-Native Data Product Architecture: Shared Vocabulary

Terms used across the design standards. Notation terms (logical types, capabilities, invariants, and decisions) are defined authoritatively in the [Design Language](DESIGN_LANGUAGE.md); the entries here give the short definition and point at it. This glossary covers the architectural and domain vocabulary.

---

**Access Layer**: The mandatory access-control artefact of a data product. Establishes the three standard access tiers (`ROLE_READ`, `ROLE_AGENT`, `ROLE_ADMIN`), each realised by a principal the **organisation profile** names or creates, and grants them read access to module containers, so the product can be discovered and queried. Deployed in two phases interleaved with the module sequence. See the [access-layer pattern](../patterns/access-layer.md).

**Access tier**: One of the three standard levels of access a product grants: `ROLE_READ`, `ROLE_AGENT` and `ROLE_ADMIN`. Tier names are logical; the **organisation profile** names the principal that realises each, created for the product or bound to one the organisation already has. See the [access-layer pattern](../patterns/access-layer.md).

**Adoption**: Using a structure that already exists in the organisation (a container, an entity's table, an allocator) instead of creating one. Declared in the **organisation profile**; a binding honours it or reports it as unsupported, and never creates a duplicate.

**Advocated option**: The recommended answer to a **Decision**. Choosing it needs no justification; choosing another option requires a recorded reason. Advocacy is not mandate: what conformance requires is that the choice be *declared*, not that it match the recommendation. See the [decision catalogue](ADVOCATED_STANDARDS.md).

**Agent**: An autonomous software entity that perceives, reasons, and acts, consuming data products to achieve goals without human mediation.

**Anchor**: The short name that identifies a module or pattern across the corpus, declared in its **frontmatter** and matching the document's location. Anchors are how documents reference each other: a design document and its platform binding share one, so either path is computable from the other without a lookup table. Cross-references resolve by anchor, never by filename.

**Architecture Decision Record (ADR)**: A structured record of a significant design decision: context, alternatives, rationale, consequences. Captured in the Memory module's design-decision store. Distinct from a **Decision**: an ADR is a *product's* record of something it settled; a Decision is a *catalogued* choice the framework poses to every product.

**Attribute**: A field of an entity. For example, `party_key` is an attribute of the Party entity. Typed with the [logical vocabulary](DESIGN_LANGUAGE.md).

**Binding setting**: A physical choice a **platform binding** declares configurable, with its permitted values and default, in its **platform profile**. An organisation sets it in its **organisation profile**; a setting the binding does not declare fails the build.

**Build context**: The single resolved input every platform binding's templates read, produced by shared tooling from a **design specification** and an **organisation profile**. Its schema is the same for every platform. See the [Platform Implementation Authoring Standard](IMPLEMENTATION_AUTHORING.md).

**Capability**: A named operation a design requires, declared abstractly and bound per platform. See the [capability catalogue](DESIGN_LANGUAGE.md).

**Co-location**: A platform's ability to store related data together so joins avoid data movement. A physical optimisation; its availability and mechanism are platform-specific. Not to be confused with the `CO_LOCATED` separation policy, which is about containers.

**Composition**: A chosen set of modules (and **facets**) assembled into a data design pattern. The framework is a library rather than a fixed architecture. A composition is *valid* when every `[hard]` requirement in it is satisfied by a `Provides` within it. An unmet `[soft]` requirement disables that feature and leaves the rest working. Domain is the root; Search and Prediction hard-depend on it; Semantic, Observability, and Memory are cross-cutting and soft. An AI-Native Data Product is the fullest composition, and other combinations are equally valid. See the [Design Language](DESIGN_LANGUAGE.md) for the mechanism and the [Master Design](MASTER_DESIGN.md) for the standard presets.

**Conformance**: Whether an implementation satisfies what the design requires of it: that every **invariant** holds, every conformance rule passes, every required **capability** has a binding, and every applicable **Decision** is declared. Conformance is deliberately checkable rather than a judgement call. Each requirement has a corresponding query, linter rule, or test, so the answer is a test result. *Advisory* content sits outside it by definition. A platform binding's conformance status follows its generated conformance report, never a hand-maintained claim ([Platform Implementation Authoring Standard](IMPLEMENTATION_AUTHORING.md) §8.1).

**Container**: The smallest named unit of object ownership on a platform (a database, a schema, a dataset). Which containers a product uses, and their names, come from the **organisation profile**. See the [object-placement pattern](../patterns/object-placement.md).

**Data Product**: A self-contained, well-defined data asset with clear ownership, interfaces, and contracts. It is owned and maintained in its own right.

**Decision**: A named choice a design must settle explicitly, carrying an **advocated option** and stated criteria for departing from it. The third construct alongside capabilities and invariants: where an invariant states what must be true of every implementation, a decision states what legitimately varies between them. Written `DEC-<TOPIC>`, catalogued in the [decision catalogue](ADVOCATED_STANDARDS.md), raised under each module's Designer Responsibilities, and settled in a product's **design specification**. See the [Design Language](DESIGN_LANGUAGE.md).

**Design / Implementation split**: The framework's core boundary: platform-agnostic standards in `design/`, platform-specific bindings in `implementation/{platform}/`. See the [Design Language](DESIGN_LANGUAGE.md).

**Design brief**: The design agent's input: the intake of business purpose, consumers, use cases, data sources, volumes and sensitivity a design starts from. Not a build input; the design agent turns it into a **design specification**.

**Design specification**: The design agent's output and the product-specific input to a build: composition, entity models, settled decisions and module configuration, with no platform, container, principal or physical names. Distinct from the *design brief*, which is the design agent's input. See the [Design Specification Standard](DESIGN_SPECIFICATION.md).

**Documentation store**: The part of the Memory module that holds design memory (module registry, design decisions, business glossary, query cookbook, implementation notes, change log), co-located in the product's own Memory store so the product is self-contained.

**Embedding**: A dense vector representation of data (text, image, entity) in a high-dimensional space where semantic similarity maps to geometric proximity. The logical type is `Vector[dim]`.

**Entity**: A logical object in a product's design, realised as one or more physical objects (a table and its views) that the **organisation profile** places and names. `Party` is an entity; a specific Party row is an *instance*.

**Entity identity**: What versions of one entity share and versioning is keyed on: the stable surrogate where one is allocated, otherwise the declared natural key. See the [Design Specification Standard](DESIGN_SPECIFICATION.md) §3.3.

**Facet**: A named part of a module that can be enabled independently of the rest, so that a **composition** may take some of a module without taking all of it. Memory has two: the `documentation` facet (design memory: decisions, glossary, cookbook, change log) and the `runtime` facet (agent sessions, interactions, learned strategies). A capability provided by a facet becomes available when that facet is enabled.

**Feature Store**: A repository for storing, managing, and serving ML features with consistency between training and inference. The role of the Prediction module.

**Frontmatter**: The short YAML block opening every design document, declaring its identity: title, **anchor**, type, status, version, and normative classification. Identity only. What a document provides, requires, and asks a designer to settle lives in its body, where it can carry its reasoning. See the [Design Language](DESIGN_LANGUAGE.md).

**Graph consumer contract**: The published contract of the graph-native tooling a platform binding targets for the Observability module's `graph-lineage` facet. The binding names it and conforms to it; names the contract fixes are binding constants.

**Identifier / Natural key**: `Identifier` is the internal, system-generated surrogate stable across an entity's versions; a `NaturalKey` is the business identifier from the source system. Under keymap allocation the natural key is held only on the **keymap**, and the entity carries the `Identifier`; see the [Design Specification Standard](DESIGN_SPECIFICATION.md) §3.3.

**Instance**: A single row within an entity. Party `CUST-123` is an instance of the Party entity.

**Invariant**: A testable, platform-neutral rule a conforming implementation must satisfy. Written `INV-<MODULE>-<NNN>`. See the [Design Language](DESIGN_LANGUAGE.md).

**Join-back**: The pattern by which a module obtains entity content: it stores an `Identifier` and joins back to the Domain entity, rather than duplicating content. Realised by the `EntityJoinBack` capability.

**Keymap**: An entity kind whose sole job is allocating an `Identifier` for a natural key, once, so the surrogate stays stable across every version of the same real-world thing. Allocating identifiers on the versioned entity itself gives each version a different one, which makes any reference held elsewhere ambiguous. The advocated option of `DEC-SURROGATE-ALLOCATION`; entities that are never themselves referenced may allocate directly and omit it. It is the only place a keymap-allocated entity's natural key is held, so a natural key that is personal data is protected in one place.

**Knowledge Store**: Design-time knowledge that guides *how* to build a product (modelling standards, naming conventions, industry reference models). This is distinct from the runtime knowledge *about* a product, which lives in the Semantic module.

**Logical name**: A name the standards own (a standard-owned relation such as `ValidationRun`, a canonical attribute such as `created_dts`, an **access tier**). An organisation may map it to a physical name of its own in its **organisation profile**; the mapping is registered in the product's Semantic metadata, so consumers resolve through metadata rather than assume a name.

**Module**: A self-contained, independently deployable component responsible for a distinct capability. The six standard modules are Domain, Search, Prediction, Observability, Semantic, and Memory. Modules integrate through join-back and cross-module reference patterns.

**Normative / advisory**: A document's conformance weight, declared in its **frontmatter**. *Normative* content is required: violating it makes a product non-conformant. *Advisory* content is recommended but not required. Placement in the hierarchy is a navigation aid and never a substitute for the declaration.

**Organisation profile**: An organisation's machine-readable configuration of the standard for its own environment (placement, naming, access, classification, retention, environments and existing structures to adopt), reused by every product it builds on one platform. See the [Organisation Profile Standard](ORGANISATION_PROFILE.md).

**Placement**: Deciding which **container** an object lives in. Stated as rules in the **organisation profile** and executed once, when the **build context** is resolved.

**Platform binding**: A platform's implementation of the standards: the `implementation/{platform}/` tree of templates, binding documents and **platform profile**. It reads only the **build context**. See the [Platform Implementation Authoring Standard](IMPLEMENTATION_AUTHORING.md).

**Platform profile**: A platform binding's `PLATFORM_PROFILE.md`. It declares the engine versions the binding supports, its naming limits and the **binding settings** an organisation may set, which are normative for the binding; and it records physical-design defaults (key strategy, partitioning, indexing, compression, statistics), which a workload with different needs may depart from. Distinct from an **organisation profile**.

**Point-in-Time (PIT)**: Reconstructing data as it existed at a specific past moment. This is what makes ML features reproducible without leakage. Realised by the `PointInTimeReconstruction` capability.

**Product code**: The identifier-safe code a **design specification** gives its product. The **organisation profile** derives physical names from it.

**RAG (Retrieval-Augmented Generation)**: A pattern where a language model retrieves relevant context before generating a response; requires the Search module.

**Reference (relationship)**: An association between entities, expressed as a reference attribute (`Reference -> <Entity>`), a hierarchy, or a semantic association.

**Semantic map**: The discovery metadata in the Semantic module (module registry, entity catalogue, column dictionary, relationship graph, path finder, naming standards) that lets an agent discover structure and generate valid queries autonomously.

**Soft delete**: Recording a deletion by marking the instance rather than destroying it: it leaves the current set, stays reachable historically, and the deletion is itself an observable event. The advocated option of `DEC-DELETE-STRATEGY`, realised by the `SoftDelete` capability. A destructive delete cannot answer which instances were removed, or when, so deletion is treated as information in its own right.

**Standard-owned relation**: A relation a module or pattern defines and a build creates without the specification declaring it, such as Semantic's catalogue or `ValidationRun`. Its name is a **logical name**. The [Design Specification Standard](DESIGN_SPECIFICATION.md) §4.1 lists them per module.

**Temporal data**: Data that tracks change over time, distinguishing *valid time* (when true in reality) from *transaction time* (when recorded). Governed by the [temporal-lifecycle-metadata pattern](../patterns/temporal-lifecycle-metadata.md).

**Trust map**: The per-area picture of what a product's validation has proven: for each area (a module, entity, pattern, or capability), which checks exist, which ran, what they found, and how far the result supports use. It informs rather than permits — no entry withholds use of the product — and it bounds what a failure costs to the area it belongs to. Defined by the [validation pattern](../patterns/validation.md); published by a validator into Observability, and built by hand by a reviewer before one exists.

**Vector store**: A store optimised for holding and searching high-dimensional vectors by similarity. On a given platform it may be a native capability or a specialist component; bound by the `NearestNeighbors` / `ApproxIndex` capabilities.
