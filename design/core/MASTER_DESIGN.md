# AI-Native Data Product — Master Design Standard

## AI-Native Data Product Architecture — Core Framework

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Core (Architectural Blueprint) |
| **Scope** | The whole framework — the modules, principles, capabilities, and integration contracts every data product follows |
| **Notation** | [Design Language](DESIGN_LANGUAGE.md) · [Glossary](GLOSSARY.md) |
| **Extended by** | The six module design standards under [`design/modules/`](../modules/) and the patterns under [`design/patterns/`](../patterns/) |

---

## 1. Purpose

This is the architectural blueprint for **AI-native data products** — data assets that agents
can discover, understand, and consume autonomously. It is a **reusable standard**, not a
specific product: it defines the modules, principles, capabilities, and integration contracts
that every data product follows, so products are repeatable, consistent, and interoperable.

It is deliberately **platform-agnostic**. Everything here holds on every deployment platform;
each platform's concrete binding lives under [`implementation/`](../../implementation/)
(Section 10). Module design standards extend this document with per-module detail; specific
data products (a Customer 360, a fraud-detection product) *apply* it with concrete entity names.

| This document defines (reusable) | A specific product supplies (varies) |
|----------------------------------|--------------------------------------|
| The six-module architecture | Which modules it implements |
| Integration and discovery patterns | Its actual entity names |
| Capabilities every product provides | Its database names |
| Principles and framework invariants | Its business-specific attributes |

---

## 2. Vision and Guiding Principles

**Vision.** Move from human-mediated data access to agent-native data platforms — products an
agent can navigate without human narration.

**Guiding principles:**

1. **Modularity first** — each module is independently deployable and composable.
2. **Progressive enhancement** — start from a traditional data model; add AI-native capabilities incrementally.
3. **Zero data duplication** — reference source data and join back to it; never copy it. Bound by `INV-MASTER-001`.
4. **Self-describing** — a product exposes its own semantics, contracts, and relationships as queryable metadata, not just prose.
5. **Agent-native design** — optimise for machine interpretation, not only human readability.
6. **Standards-driven** — consult design-time knowledge stores (Section 7 of the module docs; naming, industry models) for consistency and compliance.
7. **Platform-neutral by construction** — structural standards are platform-agnostic; all platform specifics live in `implementation/{platform}/`. This is no longer a principle to remember — the [design/implementation split](DESIGN_LANGUAGE.md#2-the-design--implementation-boundary) enforces it, and the linter checks it.

---

## 3. The Six Modules

```
            AI-Native Data Product
  ┌───────────────┬───────────────┬───────────────┐
  │    Domain     │    Search     │  Prediction   │
  │ authoritative │    vector     │   feature     │
  │   entities    │  embeddings   │    store      │
  ├───────────────┼───────────────┼───────────────┤
  │ Observability │   Semantic    │    Memory     │
  │  feedback &   │  knowledge &  │ agent state,  │
  │   events      │   meaning     │ learning, docs│
  └───────────────┴───────────────┴───────────────┘
        consumed autonomously by agents
```

| Module | Purpose | Design standard |
|--------|---------|-----------------|
| **Domain** | Authoritative source of truth for business entities, relationships, reference data, and their history. The base layer every other module joins back to. | [domain.md](../modules/domain.md) |
| **Search** | Semantic retrieval — vector embeddings and similarity search over Domain entities and content. | [search.md](../modules/search.md) |
| **Prediction** | Feature store — engineered features, model inputs/outputs, and training data derived from Domain, with point-in-time consistency. | [prediction.md](../modules/prediction.md) |
| **Observability** | Data-product operational data — quality metrics, agent interactions, outcomes, and events. Enables closed-loop learning. | [observability.md](../modules/observability.md) |
| **Semantic** | Knowledge and meaning — the queryable map of entities, columns, relationships, naming, and rules that lets agents discover and reason. | [semantic.md](../modules/semantic.md) |
| **Memory** | Agent state, learning, and the documentation store — design decisions, glossary, query cookbook, and change history for the product. | [memory.md](../modules/memory.md) |

Modules are composable: a product may implement any subset, integrating through the standard
patterns of Section 5. Domain is the foundation the others enhance.

---

## 4. Framework Capabilities

Every data product provides a common set of capabilities, defined abstractly in the
[capability catalogue](DESIGN_LANGUAGE.md#61-standard-capability-catalogue) and bound per
platform in `implementation/`. The guiding principles are realised as these capabilities:

| Principle | Realised as capability |
|-----------|------------------------|
| Zero data duplication | `EntityJoinBack` — a module holds an `Identifier` and joins back to Domain for content. |
| Temporal integrity | `CurrentStateFilter`, `PointInTimeReconstruction` — current-state and as-at retrieval. |
| Self-describing | `RichMetadata` — agent-readable metadata on every object and attribute. |
| Self-describing (discovery) | Module, entity, and relationship **discovery** via the Semantic map (Section 6). |
| Self-describing (provenance) | **Documentation capture** into Memory — every module records its own decisions, glossary, and change history. |
| Agent-native access | The **Access Layer** roles that make a deployed product reachable (Section 8). |

A module design standard names the capabilities it requires; the platform implementation binds
each one. No capability assumes a platform mechanism — where platforms genuinely differ (for
example in-database embedding), the capability is declared optional or pluggable.

---

## 5. Cross-Module Integration Patterns

1. **Join-back** — every module references Domain entities by `Identifier` and joins back for
   content. Single source of truth, no duplication (`EntityJoinBack`, `INV-MASTER-001`).
2. **Enhancement** — modules progressively enhance Domain: Search adds embeddings, Prediction
   adds features, Semantic adds relationship metadata. Each can deploy incrementally.
3. **Feedback loop** — Observability → Memory → Prediction: outcomes captured by Observability
   inform Memory and, in turn, future features and predictions. Closed-loop learning.

---

## 6. Agent Discovery

An agent must navigate a product with no human guidance. The **Semantic module is the map**
that makes this possible, through a three-tier discovery hierarchy:

1. **Module discovery** — which modules are deployed and where (the product's module registry).
2. **Entity discovery** — which entities exist in each module, and their keys and structure.
3. **Relationship discovery** — how entities relate, including multi-hop join paths.

**Bootstrap convention.** An agent is given only the product name. From it, the agent locates
the product's Semantic module by naming convention, reads the module registry to find every
module, then explores entities and relationships — and is autonomous from there. The concrete
discovery entities, and the naming convention that resolves a product name to its Semantic
location, are defined in the [Semantic module standard](../modules/semantic.md); the
platform queries that read them live in `implementation/`.

---

## 7. Self-Containment and Naming

Each data product is **fully self-contained and independently deployable**. Its discovery
metadata lives in its own Semantic store and its documentation in its own Memory store — there
is no shared cross-product database (`INV-MASTER-003`).

Because many products may share one platform, container names must be unique per product and
must signal the owning module. The *principle* — unique, module-signalling, product-scoped
names with clear module boundaries — is fixed here. The concrete container-naming scheme, and
whether modules occupy separate containers or share one, is governed by the
[object-placement pattern](../patterns/object-placement.md) and bound per platform in
`implementation/`. Object names themselves are **environment-agnostic**: promotion between
environments substitutes the container, never renames the object.

---

## 8. Access Layer

Every product **must** deploy an Access Layer alongside its module structure. Without it a
correctly deployed product is operationally invisible — every consumer is denied access no
matter how complete the modules are (`INV-MASTER-004`).

Three standard roles are created per product, named `{ProductName}_ROLE_{TIER}`:

| Role | Consumers | Purpose |
|------|-----------|---------|
| `{ProductName}_ROLE_READ` | Analysts, BI tools, ad-hoc users | Read access to module containers. |
| `{ProductName}_ROLE_AGENT` | AI agents, automated tools | Read access, kept separate for independent lifecycle management. |
| `{ProductName}_ROLE_ADMIN` | Product owner, data steward | Read access across all containers. |

The roles are product artefacts, created once and owned by the product team; assigning users to
them is an operational event, not a design concern. Where a product separates base tables from
views into distinct containers, consumers are granted the view layer only. The role model and
its grant timing are defined by the [access-layer pattern](../patterns/access-layer.md); the
grant syntax is platform-specific and lives in `implementation/`.

---

## 9. Module Dependencies and Deployment Sequence

Modules deploy in dependency order. Memory and Semantic come first because every other module
writes documentation and discovery metadata into them as it deploys.

| Phase | Deploy | Why |
|-------|--------|-----|
| **1 — Infrastructure** | Memory, then Semantic | Memory hosts the documentation store; Semantic hosts the discovery map. Both must exist before any other module. |
| **1.5 — Access (initial)** | Create the three roles; grant read on Semantic + Memory | The minimum grant for agents and tools to discover and read the product. |
| **2 — Foundation** | Domain, then Observability | Domain is the entity foundation; Observability begins monitoring immediately. |
| **2.5 — Access (extend)** | Extend grants to Domain + Observability | Consumers can now reach the foundation. |
| **3 — Enhancement** | Search, Prediction | Both require Domain entities to embed / featurise; grants extended as each deploys. |

```
Memory ───────→ hosts documentation for all modules
Semantic ─────→ hosts discovery metadata for all modules
   │  (both first)
Access 1.5 ───→ ROLE_READ / ROLE_AGENT / ROLE_ADMIN; read on Semantic + Memory
   │
Domain ──┬────→ Search
         ├────→ Prediction
         └────→ entity foundation for all modules
Observability → Memory (closed-loop feedback)
Access 2.5 ───→ read extended to Domain + Observability (then Search, Prediction)
```

---

## 10. Design Standards and Platform Implementation

The framework is split along one boundary, defined in full by the
[Design Language](DESIGN_LANGUAGE.md):

- **`design/`** — platform-agnostic. This document, the module standards, and the patterns.
  Written in logical types, capabilities, and invariants; no platform SQL (enforced by the linter).
- **`implementation/{platform}/`** — platform-specific. The concrete bindings — data types,
  DDL, queries, access grants — that satisfy the design. Teradata is the current reference; new
  platforms (Postgres, DuckDB) are added as sibling directories, changing no design document.

This replaces the earlier "Platform Profile" companion-document idea: a platform profile *is*
an `implementation/{platform}/` tree. Platform capabilities can evolve, and new platforms can be
added, without touching the structural standards.

---

## 11. Framework Invariants

Product-level rules every conforming data product satisfies:

- `INV-MASTER-001`: no module duplicates content owned by another; cross-module references are by `Identifier` with join-back.
- `INV-MASTER-002`: every deployed module registers itself in the product's Semantic map and records its documentation in the product's Memory store.
- `INV-MASTER-003`: a product is self-contained — its discovery metadata and documentation live in its own Semantic and Memory stores; there is no shared cross-product database.
- `INV-MASTER-004`: a product deploys an Access Layer (the three roles); without it the product is operationally invisible.
- `INV-MASTER-005`: structural standards are platform-neutral; every platform specific lives in `implementation/{platform}/` and changes no design document.
- `INV-MASTER-006`: object names are environment-agnostic — promotion substitutes the container, never renames the object.

---

## 12. Related Documents

- [Design Language](DESIGN_LANGUAGE.md) — the notation every design document is written in.
- [Glossary](GLOSSARY.md) — shared vocabulary.
- Module standards — [Domain](../modules/domain.md), [Search](../modules/search.md),
  [Prediction](../modules/prediction.md), [Observability](../modules/observability.md),
  [Semantic](../modules/semantic.md), [Memory](../modules/memory.md).
- Patterns — [object-placement](../patterns/object-placement.md),
  [physical-storage](../patterns/physical-storage.md),
  [temporal-lifecycle-metadata](../patterns/temporal-lifecycle-metadata.md),
  [validation](../patterns/validation.md), [access-layer](../patterns/access-layer.md).

---

**End of Master Design Standard** — *a living standard; module standards extend it and product implementations apply it.*
