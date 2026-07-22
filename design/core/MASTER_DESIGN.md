# AI-Native Data Product — Master Design Standard

## AI-Native Data Product Architecture — Core Framework

---

## Document Control

| Attribute       | Value                                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Status**      | STANDARD                                                                                                                       |
| **Type**        | Core (Architectural Blueprint)                                                                                                 |
| **Scope**       | The whole framework — the modules, how they compose, and the principles, capabilities, and contracts every composition follows |
| **Notation**    | [Design Language](DESIGN_LANGUAGE.md) · [Glossary](GLOSSARY.md)                                                                |
| **Extended by** | The module design standards under [`design/modules/`](../modules/) and the patterns under [`design/patterns/`](../patterns/)   |

---

## 1. Purpose

This is the architectural blueprint for a **modular library of data design patterns**. The
library is a set of independent, composable modules; assembling a chosen subset produces a particular kind of data asset — a minimal governed data asset, a traditional data product, a full AI-native data product, or an extension bolted onto something that already exists. There is no single fixed architecture: an **AI-Native Data Product is the fullest composition**, not the only one.

The standards are **platform-agnostic**. Everything here holds on every deployment platform; each platform's concrete binding lives under [`implementation/`](../../implementation/)
(Section 11). Module design standards extend this document with per-module detail; a specific data product (a Customer 360, a fraud-detection product) *applies* a composition with concrete entity names.

| This document defines (reusable)         | A specific product supplies (varies) |
| ---------------------------------------- | ------------------------------------ |
| The module library and how it composes   | Which composition it uses            |
| Integration and discovery patterns       | Its actual entity names              |
| Capabilities modules provide and require | Its database names                   |
| Principles and framework invariants      | Its business-specific attributes     |

---

## 2. Vision and Guiding Principles

**Vision.** Move from human-mediated data access to agent-native data platforms — products an agent can navigate without human narration.

**Guiding principles:**

1. **Modularity first** — each module is independently deployable and composes freely with others.
2. **Progressive enhancement** — start from a traditional data model; add capabilities incrementally by adding modules.
3. **Zero data duplication** — reference source data and join back to it; never copy it. Bound by `INV-MASTER-001`.
4. **Self-describing** — a product exposes its own semantics, contracts, and relationships as queryable metadata, not just prose.
5. **Agent-native design** — optimise for machine interpretation, not only human readability.
6. **Standards-driven** — consult design-time knowledge stores (naming, industry models) for consistency and compliance.
7. **Platform-neutral by construction** — structural standards are platform-agnostic; all platform specifics live in `implementation/{platform}/`. Enforced by the [design/implementation split](DESIGN_LANGUAGE.md#2-the-design--implementation-boundary) and the linter, not left as a principle to remember.

---

## 3. The Modules

```
                     Module Library
  ┌───────────────┬───────────────┬───────────────┐
  │    Domain     │    Search     │  Prediction   │
  │ authoritative │    vector     │   feature     │
  │   entities    │  embeddings   │    store      │
  ├───────────────┼───────────────┼───────────────┤
  │ Observability │   Semantic    │    Memory     │
  │  feedback &   │  knowledge &  │ agent state + │
  │   events      │   meaning     │ documentation │
  └───────────────┴───────────────┴───────────────┘
        assemble a subset → a data design pattern
```

| Module            | Purpose                                                                                                                                                                      | Design standard                                 |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **Domain**        | Authoritative source of truth for business entities, relationships, reference data, and history. The composition root every other module builds on.                          | [domain.md](../modules/domain.md)               |
| **Search**        | Semantic retrieval — vector embeddings and similarity search over Domain entities and content.                                                                               | [search.md](../modules/search.md)               |
| **Prediction**    | Feature store — engineered features and model inputs/outputs derived from Domain, with point-in-time consistency.                                                            | [prediction.md](../modules/prediction.md)       |
| **Observability** | Data-product operational data — quality metrics, agent interactions, outcomes, and events.                                                                                   | [observability.md](../modules/observability.md) |
| **Semantic**      | Knowledge and meaning — the queryable map of entities, columns, relationships, naming, and rules that lets agents discover and reason.                                       | [semantic.md](../modules/semantic.md)           |
| **Memory**        | Two facets: the **documentation** store (design decisions, glossary, change history) and the **runtime** store (agent state and learning). Facets are enabled independently. | [memory.md](../modules/memory.md)               |

---

## 4. Compositions

A **composition** assembles a subset of the module library into a data design pattern. The mechanism — how modules declare what they **Provide** and **Require** (`[hard]`/`[soft]`,`self`/`module`/`platform`), and the rule that a composition is valid if every `[hard]` requirement is met within it — is defined in the [Design Language](DESIGN_LANGUAGE.md#62-provision-requirement-and-composition).

**Dependency structure.** Domain is the root. Search and Prediction **hard-depend** on Domain (they reference Domain entities and join back for content). Semantic, Observability, and Memory are cross-cutting and **soft** — they describe, observe, or document whatever modules are present. So the missing or disabled capabilities in any composition follow directly from which modules it includes.

**Standard compositions** (illustrative presets — free composition is allowed whenever hard dependencies are met):

| Composition                  | Modules (+ facets)                                                                                         | Disabled / absent                                                                                          |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Data Asset**               | Domain + Memory[`documentation`] + Access Layer                                                            | No discovery map (agents fall back to catalogue + `RichMetadata`); no similarity, features, or monitoring. |
| **Traditional Data Product** | Domain + Semantic + Observability (+ optional Memory[`documentation`]) + Access Layer                      | No vectors, no features, no agent runtime state.                                                           |
| **AI-Native Data Product**   | Domain + Semantic + Search + Prediction + Observability + Memory[`documentation`+`runtime`] + Access Layer | Nothing — the maximal composition.                                                                         |
| **Search extension**         | Search added onto an existing Domain                                                                       | Valid because Domain (the hard dependency) is already present.                                             |

Where a pattern wants documentation but deploys no Memory module, its documentation lives in an external store — that is outside the scope of these standards (`DocumentationCapture` is then simply absent, and modules that soft-require it skip capture). Enabling or disabling a capability is never a code change to a module — it follows from the composition.

---

## 5. Framework Capabilities

Every module provides and requires capabilities from the
[capability catalogue](DESIGN_LANGUAGE.md#61-standard-capability-catalogue), bound per platform in `implementation/`. The guiding principles are realised as these capabilities:

| Principle                    | Realised as capability                                                                  | Availability                                                |
| ---------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Zero data duplication        | `EntityJoinBack` — a module holds an `Identifier` and joins back to Domain for content. | Whenever Domain is present.                                 |
| Temporal integrity           | `CurrentStateFilter`, `PointInTimeReconstruction`.                                      | Intrinsic to entity-bearing modules.                        |
| Self-describing              | `RichMetadata` — agent-readable metadata on every object and attribute.                 | Always.                                                     |
| Self-describing (discovery)  | `SemanticRegistration` — modules register in the Semantic map.                          | Only when Semantic is in the composition (soft).            |
| Self-describing (provenance) | `DocumentationCapture` — modules record decisions, glossary, and change history.        | Only when Memory's `documentation` facet is present (soft). |
| Agent-native access          | The **Access Layer** roles that make a deployed composition reachable (Section 9).      | When deployed for consumption.                              |

A module names the capabilities it provides and requires; the platform implementation binds each
one. No capability assumes a platform mechanism, and cross-module capabilities are conditional on
the composition (Section 4).

---

## 6. Cross-Module Integration Patterns

1. **Join-back** — every module references Domain entities by `Identifier` and joins back for content. Single source of truth, no duplication (`EntityJoinBack`, `INV-MASTER-001`).
2. **Enhancement** — modules progressively enhance Domain: Search adds embeddings, Prediction adds features, Semantic adds relationship metadata. Each can deploy incrementally.
3. **Feedback loop** — Observability → Memory → Prediction: outcomes captured by Observability inform Memory and, in turn, future features and predictions. Present only when those modules are.

---

## 7. Agent Discovery

When a composition includes the Semantic module, it is the **map** an agent uses to navigate with no human guidance, through a three-tier discovery hierarchy:

1. **Module discovery** — which modules are deployed and where.
2. **Entity discovery** — which entities exist in each module, and their keys and structure.
3. **Relationship discovery** — how entities relate, including multi-hop join paths.

**Bootstrap convention.** An agent is given only the product name, locates the Semantic module by naming convention, reads the module registry, then explores entities and relationships — and is autonomous from there. The discovery entities and the naming convention are defined in the [Semantic module standard](../modules/semantic.md); the platform queries live in `implementation/`.
In a composition without Semantic (e.g. a Data Asset), discovery degrades to the platform catalogue plus `RichMetadata`.

---

## 8. Self-Containment and Naming

Each data product is **self-contained and independently deployable**. Whatever stores it includes live within the product — discovery metadata in its own Semantic store, documentation in its own Memory store — with no shared cross-product database (`INV-MASTER-003`).

Because many products may share one platform, container names must be unique per product and must signal the owning module. The *principle* — unique, module-signalling, product-scoped names with clear module boundaries — is fixed here. The concrete naming scheme, and whether modules occupy separate containers or share one, is governed by the [object-placement pattern](../patterns/object-placement.md) and bound per platform. Object names are **environment-agnostic**: promotion substitutes the container, never renames the object (`INV-MASTER-006`).

---

## 9. Access Layer

A composition deployed for consumption **must** include an Access Layer. Without it a correctly deployed product is operationally invisible — every consumer is denied access no matter how complete the modules are (`INV-MASTER-004`).

Three standard roles are created per product, named `{ProductName}_ROLE_{TIER}`:

| Role                       | Consumers                        | Purpose                                                          |
| -------------------------- | -------------------------------- | ---------------------------------------------------------------- |
| `{ProductName}_ROLE_READ`  | Analysts, BI tools, ad-hoc users | Read access to module containers.                                |
| `{ProductName}_ROLE_AGENT` | AI agents, automated tools       | Read access, kept separate for independent lifecycle management. |
| `{ProductName}_ROLE_ADMIN` | Product owner, data steward      | Read access across all containers.                               |

The roles are product artefacts owned by the product team; assigning users is an operational event. Where a product separates base tables from views, consumers are granted the view layer only. The role model and grant timing are defined by the
[access-layer pattern](../patterns/access-layer.md); the grant syntax lives in `implementation/`.

---

## 10. Deployment Sequence

Modules deploy in dependency order — but only those the composition includes. When Memory and Semantic are present they come first, because every other module writes documentation and discovery metadata into them as it deploys.

| Phase                      | Deploy (if in composition)                                               | Why                                                                                                      |
| -------------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| **1 — Infrastructure**     | Memory, then Semantic                                                    | Memory hosts documentation; Semantic hosts the discovery map. Both, when present, precede other modules. |
| **1.5 — Access (initial)** | Create the three roles; grant read on the deployed infrastructure stores | Minimum grant for agents and tools to discover and read.                                                 |
| **2 — Foundation**         | Domain, then Observability                                               | Domain is the entity foundation; Observability begins monitoring immediately.                            |
| **2.5 — Access (extend)**  | Extend grants to Domain + Observability                                  | Consumers can now reach the foundation.                                                                  |
| **3 — Enhancement**        | Search, Prediction                                                       | Both hard-require Domain to embed / featurise; grants extended as each deploys.                          |

A composition that omits a module simply omits its phase. A Data Asset runs Phase 1 (Memory documentation facet), 1.5, 2 (Domain), and Access — no Semantic, Search, Prediction, or Observability.

---

## 11. Design Standards and Platform Implementation

The framework is split along one boundary, defined by the [Design Language](DESIGN_LANGUAGE.md):

- **`design/`** — platform-agnostic. This document, the module standards, and the patterns. Written in logical types, capabilities, and invariants; no platform SQL (enforced by the linter).
- **`implementation/{platform}/`** — platform-specific. The concrete bindings — data types, DDL, queries, access grants — that satisfy the design. Teradata is the current reference; new platforms (Postgres, DuckDB) are added as sibling directories, changing no design document.

A platform "profile" *is* an `implementation/{platform}/` tree: platform capabilities can evolve, and new platforms can be added, without touching the structural standards.

---

## 12. Framework Invariants

Product-level rules every conforming composition satisfies. Several are **conditional** on which modules the composition includes.

- `INV-MASTER-001`: no module duplicates content owned by another; cross-module references are by `Identifier` with join-back.
- `INV-MASTER-002`: *when a Semantic module is present*, every other deployed module registers its entities, columns, and relationships in it; *when Memory's documentation facet is present*, every module records its documentation there.
- `INV-MASTER-003`: a product is self-contained — whatever discovery and documentation stores it includes live within the product; there is no shared cross-product database.
- `INV-MASTER-004`: a composition deployed for consumption includes an Access Layer (the three roles); without it the product is operationally invisible.
- `INV-MASTER-005`: structural standards are platform-neutral; every platform specific lives in `implementation/{platform}/` and changes no design document.
- `INV-MASTER-006`: object names are environment-agnostic — promotion substitutes the container, never renames the object.
- `INV-MASTER-007`: a composition is valid only if every `[hard]` capability requirement is satisfied within it (or by the platform); unmet `[soft]` requirements disable dependent features but do not invalidate the composition.

---

## 13. Related Documents

- [Design Language](DESIGN_LANGUAGE.md) — the notation every design document is written in, including the composition mechanism (§6.2).
- [Glossary](GLOSSARY.md) — shared vocabulary.
- Module standards — [Domain](../modules/domain.md), [Search](../modules/search.md),
  [Prediction](../modules/prediction.md), [Observability](../modules/observability.md),
  [Semantic](../modules/semantic.md), [Memory](../modules/memory.md).
- Patterns — [object-placement](../patterns/object-placement.md),
  [physical-storage](../patterns/physical-storage.md),
  [temporal-lifecycle-metadata](../patterns/temporal-lifecycle-metadata.md),
  [validation](../patterns/validation.md), [access-layer](../patterns/access-layer.md).

---

**End of Master Design Standard** — *a living standard; modules compose into patterns, and product implementations apply them.*
