---
title: Access Layer Pattern
anchor: access-layer
type: pattern
status: standard
version: 2.0
normative: true
---

# Access Layer: Pattern

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Pattern (cross-cutting, platform-agnostic) |
| **Scope** | The mandatory access-control artefact that makes a deployed product reachable |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/patterns/access-layer/`](../../implementation/teradata/patterns/access-layer/) |

This pattern realises the mandatory Access Layer of [Master](../core/MASTER_DESIGN.md) and `INV-MASTER-004`. Without it, a correctly deployed product is **operationally invisible**: every consumer (agents, dashboards, reporting tools, analysts) is denied access no matter how completely the module containers are deployed.

---

## 1. Core Principle

Consumers are granted access to the container(s) that expose a module's **public interface**: the view layer. Under the standard `{ProductName}_{Module}` placement this is the module container; where [object-placement](object-placement.md) separates tables and views into distinct containers, consumers are granted the **view-layer container only**, never the base-table container. The term **module access container** refers to whichever container(s) consumers should reach for a module.

---

## 2. Capabilities

**Provides:**

| Capability | Made available to |
|------------|-------------------|
| `AccessView` | Every module: the view layer is the stable, named surface with an explicit column contract that consumers read instead of base tables. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `DocumentationCapture` | `[soft]` | `module:Memory` | The access model and its grants are recorded as a design decision when Memory's documentation facet is present. |

---

## 3. Standard Roles

Three roles are created per product, named `{ProductName}_ROLE_{TIER}`:

| Role | Consumers | Scope |
|------|-----------|-------|
| `{ProductName}_ROLE_READ` | Analysts, BI tools, ad-hoc users | Read on the module access containers. |
| `{ProductName}_ROLE_AGENT` | AI agents, automated tools | Read on the module access containers, plus **write-back** (append) to Memory and Observability. |
| `{ProductName}_ROLE_ADMIN` | Product owner, data steward | Read on all containers, including any separate base-table containers. |

### 3.1 Why `ROLE_AGENT` is separate from `ROLE_READ`

They grant the same read scope by default but are kept distinct for:

1. **Independent lifecycle**: agent access can be suspended, extended, or revoked without affecting analyst access.
2. **Write-back permissions**: agents append to Memory (interactions, learned strategies, design decisions) and Observability (usage events, quality signals). `ROLE_READ` must never hold these: human analysts do not write agent state or telemetry.
3. **Boundary clarity**: granting write-back to `ROLE_AGENT` and not `ROLE_READ` makes the permission boundary explicit in the role model itself, not just in application logic.
4. **Audit clarity**: agent-originated queries are separately auditable when the connecting identity holds a distinct role.

---

## 4. Deployment Timing

The Access Layer deploys in two phases interleaved with the module sequence ([Master](../core/MASTER_DESIGN.md)):

| Phase | Timing | Action | Privilege |
|-------|--------|--------|-----------|
| **1.5a** | As soon as the containers exist, at the end of Phase 1 | Provision the **implied grants** the container structure requires: the cross-container rights that let the access layer compile views over module containers. | Ownership of both containers. |
| **1.5b** | After Phase 1 (Memory + Semantic) | Create the roles; grant read on the Semantic and Memory access containers; grant Memory write-back to `ROLE_AGENT`. | **Elevated (role creation).** |
| **2.5** | After Phase 2 (Domain + Observability), then as further modules deploy | Extend read to Domain and Observability; grant Observability write-back to `ROLE_AGENT`; extend to Search and Prediction as each deploys. | Elevated. |

**Why 1.5 splits.** The two halves look like one step and are not. Implied grants are a **build dependency**: without them a view in a separate access container cannot compile, so every consumer view downstream fails. Role creation is an **operational** one, and on most enterprise platforms it needs a privilege the deploying account does not hold.

Treating them as a single phase makes the first hostage to the second. When role creation is refused, the whole block is skipped, and the failure surfaces two phases later as a view that will not compile against a table it is entitled to read: an error a long way from its cause. Provision the implied grants as soon as the containers exist, and generate the role statements as a separately identified artefact marked as requiring elevated privilege, so a deployment without that privilege continues cleanly and the outstanding step is visible rather than lost.

**Phase 1.5b is the minimum viable grant.** Once Semantic and Memory are readable, agents can discover the product's structure, read the glossary, and use the query cookbook. Delaying all grants until every module is deployed is an anti-pattern: consumers cannot validate the product during incremental deployment. A composition deploys only the phases for the modules it includes (a Data Asset runs Phase 1.5 for Memory and Phase 2.5 for Domain, with no Semantic/Observability grants).

---

## 5. Grant Matrix

Permissions per role, for whichever modules the composition includes:

**This matrix is the authoritative statement of the consumer role model.** It is reproduced in several places, and those reproductions drift: a product's design brief restates it, a deployment sequence restates the phase grants inline, and a placement implementation declares an access model of its own. Where any of them disagrees with this table, this table is correct. A placement implementation declares the *implied* grants its container structure requires ([object-placement](object-placement.md) Section 7) and the principal types the platform offers; it does not redefine who may read what.

| Module | `ROLE_READ` | `ROLE_AGENT` | `ROLE_ADMIN` |
|--------|-------------|--------------|--------------|
| Semantic: read | Phase 1.5b | Phase 1.5b | Phase 1.5b |
| Memory: read | Phase 1.5b | Phase 1.5b | Phase 1.5b |
| Memory: write-back | - | Phase 1.5b | Phase 1.5b |
| Domain: read | Phase 2.5 | Phase 2.5 | Phase 2.5 |
| Observability: read | Phase 2.5 | Phase 2.5 | Phase 2.5 |
| Observability: write-back | - | Phase 2.5 | Phase 2.5 |
| Search: read | when deployed | when deployed | when deployed |
| Prediction: read | when deployed | when deployed | when deployed |
| Domain / Semantic, write | - |, | ✔ |
| Base-table containers (if separate) | - |: | ✔ |

**Why agents do not write to Domain or Semantic.** Domain data originates from authoritative source systems via governed pipelines: agent write-back would bypass data governance. Semantic metadata is maintained by product designers; agents read the schema but do not define it.

### 5.1 Reading Memory is not reading agent state

Granting read on the Memory access container to all three roles is required: the documentation facet is how a consumer learns what the product means, and withholding it makes the product unreadable for exactly the audience it is built for.

But Memory has two facets, and where the composition deploys both, the runtime facet sits behind the same grant. `ROLE_READ` then reaches session and interaction records for every user, not only its own. `INV-MEMORY-003` requires every runtime record to *carry* a privacy scope; carrying one is not enforcing one, and nothing above closes that gap.

The scope columns are therefore enforced at the access surface. Runtime entities are consumed through a view that filters on the requesting identity's scope, and that view, not the base table, is what the consumer grant reaches. Where the platform cannot express the filter, the runtime facet is separated into its own container so the documentation grant does not carry it, and the residual exposure is recorded as a design decision rather than left implicit.

The documentation facet needs no such filter: design decisions, glossary, and cookbook are product-wide by intent.

---

## 6. Required Documentation Record

Deploying the Access Layer must produce a design-decision record `DD-ACCESS-001` in the product's Memory documentation facet (the `DocumentationCapture` capture protocol, [memory](../modules/memory.md)). This captures the accepted role model, permission boundary, and rationale **inside the product**, so agents can read the access contract at runtime: not only in this document. The record's category is `SECURITY`; its alternatives (single consumer role; per-user grants) and rationale (independent lifecycle + write-back boundary) are recorded per the capture contract.

The record's `source_module` is `MEMORY`. The Access Layer is a pattern rather than a module, so there is no `ACCESS` entry in `ModuleRegistry` for it to name, and a record naming one counts toward no module at all: it is dropped by the join that checks the per-module minimum, without reporting anything. Memory is the module whose grant boundary this decision defines.

---

## 7. Relationship to Other Standards

- **[Master Design](../core/MASTER_DESIGN.md)**: mandates the Access Layer; this pattern is its full specification. `INV-MASTER-004` fails a consumable composition that omits it.
- **[Object-placement pattern](object-placement.md)**: owns container naming and the table/view separation this pattern grants against; the implied cross-container grant for the view layer is declared there.
- **[Temporal & lifecycle metadata pattern](temporal-lifecycle-metadata.md)**: its exposure surfaces (governed full-contract vs default current) are the objects consumers are granted.
- **Modules**: each module defines *what* it contains and registers; the Access Layer defines *who* can read it. The roles are product artefacts created once; assigning users to them is an operational event outside these standards.

---

## 8. Conformance Checklist

- [ ] Phase 1.5a implied grants provisioned as soon as the containers exist, before any view that depends on them is compiled.
- [ ] Role statements identified as requiring elevated privilege, and generated so a deployment without it continues and the outstanding step stays visible.
- [ ] The three roles created, each with a descriptive comment.
- [ ] Phase 1.5b read grants applied (Semantic, Memory) immediately after Phase 1.
- [ ] Phase 1.5b Memory write-back granted to `ROLE_AGENT`.
- [ ] Phase 2.5 read grants applied (Domain, Observability) immediately after Phase 2.
- [ ] Phase 2.5 Observability write-back granted to `ROLE_AGENT`.
- [ ] Search and Prediction grants applied as each deploys.
- [ ] Consumers granted the view-layer container only, never base tables.
- [ ] Runtime memory reached through a scope-enforcing view, not through the documentation grant.
- [ ] The grant matrix agrees with the deployment phases and with the placement implementation's access section; where they disagree, the grant matrix is corrected into them, not the reverse.
- [ ] `DD-ACCESS-001` recorded in the product's Memory documentation facet.

---

**End of Access Layer Pattern**
