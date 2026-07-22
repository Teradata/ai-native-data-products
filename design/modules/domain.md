# Domain Module — Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute           | Value                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------ |
| **Status**          | STANDARD                                                                                   |
| **Type**            | Module Design Standard (platform-agnostic)                                                 |
| **Scope**           | Domain / Subject data module — authoritative business entities                             |
| **Extends**         | [Master Design](../core/MASTER_DESIGN.md)                                                  |
| **Notation**        | [Design Language](../core/DESIGN_LANGUAGE.md)                                              |
| **Implementations** | [`implementation/teradata/modules/domain/`](../../implementation/teradata/modules/domain/) |

This document defines **what** a Domain module must be and **why**, in platform-neutral
terms. **How** a specific platform realises it lives in that platform's implementation
directory. Every capability named here has a binding there; every invariant named here
has a check there.

---

## 1. Purpose

The Domain module is the **authoritative source of truth** for a data product's core
business entities. It is AI-native not because of any one storage choice but because of
the guarantees it offers an autonomous agent:

| AI-native characteristic     | Purpose                                                         |
| ---------------------------- | --------------------------------------------------------------- |
| **Temporal integrity**       | Point-in-time state reconstruction for reproducible features.   |
| **Agent discoverability**    | Consistent patterns an agent learns once and reuses everywhere. |
| **Cross-module integration** | A stable reference every other module can join back to.         |
| **Complete lineage**         | Full traceability for explainability.                           |
| **Metadata richness**        | Self-documenting, so agents operate without human narration.    |

All other modules (Search, Prediction, Observability, Semantic, Memory) reference Domain entities and join back for their content.

---

## 2. Scope and Boundaries

**In scope** — anything that represents the business domain (what the business *is* and
*does*):

- Core business entities (party, product, location, agreement, …) and their history.
- Relationships between entities.
- Reference data and taxonomies.
- Domain events and transactions (customer transactions, product usage, agreement changes).
- Domain measurements (balances, amounts, usage metrics).

**Out of scope** — anything about the *data product's operation*:

| Concern                                 | Owning module |
| --------------------------------------- | ------------- |
| Derived ML features                     | Prediction    |
| Vector embeddings                       | Search        |
| Operational events, quality assessments | Observability |
| Ontologies, rules, naming standards     | Semantic      |
| Agent conversational state              | Memory        |

**Boundary test for events:** a *business* event (customer purchases a product) is Domain; a *data-product operational* event (a model made a prediction, a quality check ran) is Observability.

---

## 3. Entity Model

Domain entities are declared in the [entity notation](../core/DESIGN_LANGUAGE.md#5-entity-notation).
Four entity kinds recur. None of them fixes a physical shape — the temporal columns, the storage layout, and the index strategy come from the applied patterns and the platform implementation, not from here.

### 3.1 Core entity (History)

Every core business entity follows one shape, so an agent that learns one learns all.

```
Entity: <EntityName>              [kind: History]
  <entity>_id   : Identifier                     — surrogate key; stable across every version
  <entity>_key  : NaturalKey [required] [unique] — business identifier from the source system
  is_current    : Flag [current-flag]            — marks the current version of the entity
  is_deleted    : Flag [deleted-flag]            — soft-delete marker; row retained for audit
  <attribute>   : <LogicalType> [required|optional] [pii]  — designer-supplied business attributes

  Keys:
    surrogate: <entity>_id
    natural:   <entity>_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - SurrogateKeyAllocation
    - CurrentStateFilter
    - PointInTimeReconstruction
    - NaturalKeyLookup
    - RichMetadata
```

The `Identifier` / `NaturalKey` split is deliberate: `<entity>_id` is the internal,
join-facing surrogate; `<entity>_key` is the human- and report-facing business key from source. Every entity carries both, under the same names.

### 3.2 Reference data (Reference)

Controlled vocabularies and lookups, with temporal validity but simpler than a full
history entity.

```
Entity: <ReferenceName>           [kind: Reference]
  <reference>_id        : Identifier                       — surrogate key for the entry
  <reference>_code      : Code [required] [unique]         — code used by entities; unique within its effective period
  short_description     : ShortText [required]             — brief label for UI and reports
  long_description      : Text [optional]                  — full definition and usage guidance
  effective_date        : Date [required]                  — when the value becomes valid
  expiration_date       : Date [optional]                  — when the value expires
  is_current            : Flag [current-flag]              — currently valid indicator
  parent_<reference>_id : Reference [optional] [-> <ReferenceName>]  — optional hierarchy parent
  sort_order            : Integer [optional]               — optional display sequence

  Applies patterns:
    - object-placement
    - access-layer

  Requires capabilities:
    - RichMetadata
```

### 3.3 Relationship

An association between two entities, versioned like a history entity.

```
Entity: <Entity1><Entity2>        [kind: Relationship]
  <entity1>_<entity2>_id : Identifier                          — surrogate key for the association
  <entity1>_id           : Reference [required] [-> <Entity1>] — first entity in the relationship
  <entity2>_id           : Reference [required] [-> <Entity2>] — second entity in the relationship
  is_current             : Flag [current-flag]
  is_deleted             : Flag [deleted-flag]
  <attribute>            : <LogicalType> ...                   — relationship-specific attributes

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - CurrentStateFilter
    - RichMetadata
```

### 3.4 Surrogate-key allocation (Keymap)

For entities that are reference targets, the surrogate `Identifier` must stay the same
across every version of the entity. Allocation is therefore separated into a keymap, so
the surrogate is assigned once per natural key and reused across all versions.

```
Entity: <EntityName>Keymap        [kind: Keymap]
  <entity>_id   : Identifier                       — allocated once per natural key; never reused or recycled
  <entity>_key  : NaturalKey [required] [unique]   — natural key from source system
  source_system : ShortText [optional]             — system that first introduced this natural key
  created_at    : Timestamp [required]             — allocation time; immutable once set

  Requires capabilities:
    - SurrogateKeyAllocation
```

Reference entities and detail entities that are never reference targets may allocate their surrogate directly and omit the keymap. This decision — keymap vs direct allocation — is a per-entity designer choice recorded in the design decisions.

---

## 4. Applied Patterns

Domain does not restate cross-cutting concerns; it applies them. Each pattern is defined once under `design/patterns/` and bound per platform under `implementation/{platform}/patterns/`.

| Pattern                       | What it contributes to Domain                                                                                                                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `temporal-lifecycle-metadata` | The versioning columns and the rule for point-in-time reconstruction. The designer chooses an approach (bi-temporal, type-2, event-sourced); the pattern defines the contract it must meet. |
| `object-placement`            | Which container each entity, view, and procedure is created in, and the access principals that reach them.                                                                                  |
| `physical-storage`            | (When object storage is in use) the physical path, file format, and partition strategy beneath the logical container.                                                                       |
| `access-layer`                | The standard views (current, enriched) and their explicit column contracts.                                                                                                                 |
| `validation`                  | The conformance checks an implementation runs before it is declared done.                                                                                                                   |

---

## 5. Capabilities and Composition

Domain is the **composition root**: it has no hard dependency on any other module and can be deployed alone — for example as a Data Asset (Domain + Memory `documentation` facet + Access Layer). See the [composition mechanism](../core/DESIGN_LANGUAGE.md#62-provision-requirement-and-composition).

**Provides** (to other modules and to agents):

| Capability                                                                          | Made available to                                                                                                                                         |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `EntityJoinBack`                                                                    | Any module referencing a Domain entity obtains its content by joining back on `<entity>_id`. This is the capability Search and Prediction hard-depend on. |
| `CurrentStateFilter`, `PointInTimeReconstruction`, `NaturalKeyLookup`, `AccessView` | Agents and consumers, over Domain entities.                                                                                                               |

**Requires:**

| Capability               | Strength | Provider            | Why                                                                                                                         |
| ------------------------ | -------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `SurrogateKeyAllocation` | `[hard]` | `self` / `platform` | Keep `<entity>_id` stable across all versions of an entity.                                                                 |
| `RichMetadata`           | `[hard]` | `self` / `platform` | Attach agent-readable metadata to every object and attribute.                                                               |
| `MetadataCoverageCheck`  | `[hard]` | `self`              | Prove programmatically that every attribute carries metadata.                                                               |
| `SemanticRegistration`   | `[soft]` | `module:Semantic`   | Register entities, columns, and relationships in the Semantic map when Semantic is in the composition (`INV-MASTER-002`).   |
| `DocumentationCapture`   | `[soft]` | `module:Memory`     | Record decisions, glossary, and change history when Memory's documentation facet is present (Section 11, `INV-MASTER-002`). |

Every capability has a binding in the implementation. The two `[soft]` requirements are skipped — not failed — in a composition that omits Semantic or Memory.

---

## 6. Cross-Module Integration

Other modules reference Domain entities with **one** consistent pattern, chosen per module:

- **Generic reference** — a `Reference` plus an `Enum` entity-kind discriminator, used when a module points at *many* entity types (e.g. an embedding that may describe a party, a product, or a document).
- **Specific reference** — one `Reference [-> <Entity>]` per referenced entity, used when a module points at a *few* known types.

In both cases, **content is obtained by join-back, never duplicated** (`EntityJoinBack`).
A referencing module stores the `Identifier` and joins to the Domain entity for names, descriptions, and other attributes. This keeps Domain the single source of truth and avoids drift between copies.

---

## 7. Agent Discoverability Requirements

These are semantic requirements — true on every platform — that make the module usable by an autonomous agent. Each maps to a capability and is checked by the `validation` pattern.

1. **Consistent patterns.** Every entity presents the same identity shape (`Identifier` + `NaturalKey`), the same current/deleted flags, and the same temporal contract. An agent generalises from one entity to all.
2. **Rich metadata.** Every object and attribute carries a meaningful description of business meaning (not restated structure), including units, sensitivity, and source (`RichMetadata`).
3. **Descriptive references.** A reference attribute names the entity it points to; generic
   opaque foreign keys are prohibited.
4. **Standard views.** Every entity exposes at least a *current* view with an explicit column contract, so an agent reads the contract, not the query body (`AccessView`).
5. **Documented conventions.** Naming conventions and suffix signals are recorded in the Semantic module so an agent can look them up rather than infer them.
6. **Registered in the Semantic map** *(when the composition includes Semantic).* On deploy, every entity, its columns, and its relationships are registered in the product's Semantic map (`SemanticRegistration`), so an agent discovers them by querying the map rather than inspecting the catalogue directly. This is the discovery half of `INV-MASTER-002`; documentation capture (Section 11) is the other. In a composition without Semantic, discovery falls back to the platform catalogue plus `RichMetadata`.

**Discoverability test.** An agent that has never seen these entities can: discover what
entities exist; understand what each represents; retrieve current active records; navigate relationships; and generate valid queries — using metadata alone.

---

## 8. Invariants

Every conforming implementation must satisfy these. Each has a corresponding check in the implementation's `validation`.

- `INV-DOMAIN-001`: every attribute of every entity carries descriptive metadata.
- `INV-DOMAIN-002`: current, non-deleted records are retrievable by a single predictable filter over the current-flag and deleted-flag.
- `INV-DOMAIN-003`: a surrogate `Identifier` is stable across all versions of the same real-world entity — it never changes as the entity versions.
- `INV-DOMAIN-004`: every entity exposes the same identity shape — one surrogate `Identifier` and one `NaturalKey`.
- `INV-DOMAIN-005`: other modules reference Domain entities by `Identifier` only and obtain content by join-back; no Domain-owned attribute is duplicated outside Domain.
- `INV-DOMAIN-006`: the state of any entity is reconstructable as at any past `Timestamp`.
- `INV-DOMAIN-007`: every reference attribute names the entity it targets.

---

## 9. Design Flexibility

This standard defines **structure and patterns, not a specific implementation**. Within the invariants of Section 8, designers choose the approach that best fits their platform, data volumes, and governance. The flexible dimensions — and the constraint each must still honour:

| Dimension                   | Flexibility                                                                  | Constraint                                                                                                     |
| --------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Temporal strategy**       | Bi-temporal, Type-2 SCD, event sourcing, or another approach.                | Must satisfy the `temporal-lifecycle-metadata` contract and `INV-DOMAIN-006` (point-in-time reconstruction).   |
| **Column set** | Minimal core vs extended metadata. Operational metadata (audit who/when, source system, batch, lineage, quality) may be **offloaded to Observability** and joined back, keeping high-volume tables lean; low-volume tables may carry it inline. | Must carry the identity shape (`INV-DOMAIN-004`) and the current/deleted flags (`INV-DOMAIN-002`). Offloaded data is events/metrics, never a second copy of business content (`INV-OBS-001`). |
| **Key allocation**          | Keymap (separate allocation) vs direct allocation, chosen per entity.        | Surrogate must be stable across versions for reference-target entities (`INV-DOMAIN-003`).                     |
| **Deletion representation** | How a logical deletion is recorded.                                          | The audit trail must be preserved — deletion is soft, retained for audit (`INV-DOMAIN-002`, `INV-DOMAIN-005`). |
| **Storage optimisation**    | Normalisation vs denormalisation, partitioning, indexing.                    | A platform concern — lives entirely in `implementation/` and must not change the logical contract.             |

**Rule:** whatever is chosen must support the AI-native characteristics (Section 1) and
satisfy every invariant (Section 8). The choice for each flexible dimension is **recorded as
a design decision** (Section 11) so it is traceable rather than implicit.

---

## 10. Designer Responsibilities

### 10.1 What designers supply

Platform-neutral decisions the designer owns:

| Element                   | Source                                                              |
| ------------------------- | ------------------------------------------------------------------- |
| Entity model              | An established model where one exists (Section 10.2), or custom.    |
| Entity attributes         | Business requirements, typed with the logical vocabulary.           |
| Natural keys              | The source-system business identifier per entity.                   |
| Relationships             | Business-domain analysis.                                           |
| Reference data            | Industry or business-controlled vocabularies.                       |
| Temporal strategy         | The approach satisfying the `temporal-lifecycle-metadata` contract. |
| Key allocation per entity | Keymap vs direct allocation (Section 3.4).                          |
| Sensitivity               | Which attributes are `[pii]`.                                       |

### 10.2 Entity model sourcing

Source entities from an established model wherever one exists, and **document the choice** so agents and reviewers can trace it:

1. **Enterprise data model** — integrated logical data model (iLDM), common data model (CDM),
   or corporate data dictionary.
2. **Industry standards**, by domain:
   
   - Finance — FIBO, BIAN, ISO 20022
   
   - Healthcare — HL7 FHIR, SNOMED CT, LOINC
   
   - Retail — GS1, ARTS
   
   - Insurance — ACORD
   
   - Telecom — TM Forum (SID)
3. **Open standards** — Schema.org (common entities), Dublin Core (metadata), SKOS (taxonomies).
4. **Custom models** — when no standard fits; document the rationale and structure, and consider future standardisation.

**Best practice:** adopt the enterprise or industry standard, **document it in the Semantic module** so agents can reference it, and **apply it consistently** across every entity.
Consistency is what lets an agent generalise one entity's pattern to all (Section 8, Agent
Discoverability requirement 1).

### 10.3 Design review checklist

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Every entity has the identity shape (`Identifier` + `NaturalKey`).
- [ ] Entity model source identified and documented — enterprise, industry, or custom (Section 10.2).
- [ ] Flexible-dimension choices (temporal, key allocation, column set, deletion, storage) recorded as design decisions (Section 9, Section 11).
- [ ] Key-allocation approach chosen and recorded per entity (keymap vs direct).
- [ ] Temporal strategy chosen and satisfies the `temporal-lifecycle-metadata` contract.
- [ ] Reference patterns follow Section 6 (one pattern per referencing module).
- [ ] Every entity has at least a current view (`AccessView`).
- [ ] Every entity, column, and relationship registered in the Semantic map when the composition includes Semantic (`SemanticRegistration`, `INV-MASTER-002`).
- [ ] Every invariant in Section 8 has a check in the implementation.
- [ ] Documentation capture completed per Section 11.
- [ ] This document passes the design linter with no ignore directive.

---

## 11. Documentation Capture Requirements

Every Domain module records its own documentation as part of the design workflow, so the data product is **self-describing**. Capture is written into the **Memory module** — the data product's own documentation store; the record definitions, capture workflow, and templates are owned by the Memory module design and its implementation, not restated here.

**Minimum records:**

| Record type            | Minimum | Captures                                                                                      |
| ---------------------- | ------- | --------------------------------------------------------------------------------------------- |
| Module registry entry  | 1       | Registers this module with the data product and version.                                      |
| Design decision        | 3       | Key architectural and schema choices — including the flexible-dimension choices of Section 9. |
| Change-log entry       | 1       | Initial release entry.                                                                        |
| Business-glossary term | 3       | Domain terms and entity definitions introduced.                                               |
| Query-cookbook recipe  | 1       | A key query pattern (e.g. current-entity lookup, point-in-time reconstruction).               |

**Typical decision categories:** `ARCHITECTURE` (temporal strategy), `SCHEMA` (attribute set), `NAMING` (natural key and source alignment), `PERFORMANCE` (index and partitioning strategy), `SECURITY` (PII identification and access approach).

**Decision id prefix:** `DD-DOMAIN-<NNN>` (e.g. `DD-DOMAIN-001`).

The capture protocol and templates live with the Memory module — design in
[`design/modules/memory.md`](memory.md), binding in `implementation/{platform}/modules/memory/`.

---

## 12. Implementation

The Teradata binding of this module — concrete table and view templates, the capability binding table, and the invariant checks — lives in [`implementation/teradata/modules/domain/`](../../implementation/teradata/modules/domain/).
Additional platforms (Postgres, DuckDB) add sibling directories under `implementation/`
without any change to this document.

---

**End of Domain Module Design Standard**
