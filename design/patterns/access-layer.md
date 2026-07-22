# Access Layer — Pattern

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

This pattern realises the mandatory Access Layer of [Master §9](../core/MASTER_DESIGN.md) and
`INV-MASTER-004`. Without it, a correctly deployed product is **operationally invisible** — every
consumer (agents, dashboards, reporting tools, analysts) is denied access no matter how completely
the module containers are deployed.

---

## 1. Core Principle

Consumers are granted access to the container(s) that expose a module's **public interface** — the
view layer. Under the standard `{ProductName}_{Module}` placement this is the module container; where
[object-placement](object-placement.md) separates tables and views into distinct containers,
consumers are granted the **view-layer container only**, never the base-table container. The term
**module access container** refers to whichever container(s) consumers should reach for a module.

---

## 2. Standard Roles

Three roles are created per product, named `{ProductName}_ROLE_{TIER}`:

| Role | Consumers | Scope |
|------|-----------|-------|
| `{ProductName}_ROLE_READ` | Analysts, BI tools, ad-hoc users | Read on the module access containers. |
| `{ProductName}_ROLE_AGENT` | AI agents, automated tools | Read on the module access containers, plus **write-back** (append) to Memory and Observability. |
| `{ProductName}_ROLE_ADMIN` | Product owner, data steward | Read on all containers, including any separate base-table containers. |

### 2.1 Why `ROLE_AGENT` is separate from `ROLE_READ`

They grant the same read scope by default but are kept distinct for:

1. **Independent lifecycle** — agent access can be suspended, extended, or revoked without affecting analyst access.
2. **Write-back permissions** — agents append to Memory (interactions, learned strategies, design decisions) and Observability (usage events, quality signals). `ROLE_READ` must never hold these — human analysts do not write agent state or telemetry.
3. **Boundary clarity** — granting write-back to `ROLE_AGENT` and not `ROLE_READ` makes the permission boundary explicit in the role model itself, not just in application logic.
4. **Audit clarity** — agent-originated queries are separately auditable when the connecting identity holds a distinct role.

---

## 3. Deployment Timing

The Access Layer deploys in two phases interleaved with the module sequence
([Master §10](../core/MASTER_DESIGN.md)):

| Phase | Timing | Action |
|-------|--------|--------|
| **1.5** | After Phase 1 (Memory + Semantic) | Create the roles; grant read on the Semantic and Memory access containers; grant Memory write-back to `ROLE_AGENT`. |
| **2.5** | After Phase 2 (Domain + Observability), then as further modules deploy | Extend read to Domain and Observability; grant Observability write-back to `ROLE_AGENT`; extend to Search and Prediction as each deploys. |

**Phase 1.5 is the minimum viable grant.** Once Semantic and Memory are readable, agents can discover
the product's structure, read the glossary, and use the query cookbook. Delaying all grants until
every module is deployed is an anti-pattern — consumers cannot validate the product during
incremental deployment. A composition deploys only the phases for the modules it includes (a Data
Asset runs Phase 1.5 for Memory and Phase 2.5 for Domain, with no Semantic/Observability grants).

---

## 4. Grant Matrix

Permissions per role, for whichever modules the composition includes:

| Module | `ROLE_READ` | `ROLE_AGENT` | `ROLE_ADMIN` |
|--------|-------------|--------------|--------------|
| Semantic — read | Phase 1.5 | Phase 1.5 | Phase 1.5 |
| Memory — read | Phase 1.5 | Phase 1.5 | Phase 1.5 |
| Memory — write-back | — | Phase 1.5 | Phase 1.5 |
| Domain — read | Phase 2.5 | Phase 2.5 | Phase 2.5 |
| Observability — read | Phase 2.5 | Phase 2.5 | Phase 2.5 |
| Observability — write-back | — | Phase 2.5 | Phase 2.5 |
| Search — read | when deployed | when deployed | when deployed |
| Prediction — read | when deployed | when deployed | when deployed |
| Domain / Semantic — write | — | — | ✔ |
| Base-table containers (if separate) | — | — | ✔ |

**Why agents do not write to Domain or Semantic.** Domain data originates from authoritative source
systems via governed pipelines — agent write-back would bypass data governance. Semantic metadata is
maintained by product designers; agents read the schema but do not define it.

---

## 5. Required Documentation Record

Deploying the Access Layer must produce a design-decision record `DD-ACCESS-001` in the product's
Memory documentation facet (the `DocumentationCapture` capture protocol,
[memory §5.2](../modules/memory.md)). This captures the accepted role model, permission boundary, and
rationale **inside the product**, so agents can read the access contract at runtime — not only in
this document. The record's category is `SECURITY`; its alternatives (single consumer role;
per-user grants) and rationale (independent lifecycle + write-back boundary) are recorded per the
capture contract.

---

## 6. Relationship to Other Standards

- **[Master Design](../core/MASTER_DESIGN.md)** — §9 mandates the Access Layer; this pattern is its
  full specification. `INV-MASTER-004` fails a consumable composition that omits it.
- **[Object-placement pattern](object-placement.md)** — owns container naming and the
  table/view separation this pattern grants against; the implied cross-container grant for the view
  layer is declared there.
- **[Temporal & lifecycle metadata pattern](temporal-lifecycle-metadata.md)** — its §8 exposure
  surfaces (governed full-contract vs default current) are the objects consumers are granted.
- **Modules** — each module defines *what* it contains and registers; the Access Layer defines *who*
  can read it. The roles are product artefacts created once; assigning users to them is an
  operational event outside these standards.

---

## 7. Checklist

- [ ] The three roles created, each with a descriptive comment.
- [ ] Phase 1.5 read grants applied (Semantic, Memory) immediately after Phase 1.
- [ ] Phase 1.5 Memory write-back granted to `ROLE_AGENT`.
- [ ] Phase 2.5 read grants applied (Domain, Observability) immediately after Phase 2.
- [ ] Phase 2.5 Observability write-back granted to `ROLE_AGENT`.
- [ ] Search and Prediction grants applied as each deploys.
- [ ] Consumers granted the view-layer container only, never base tables.
- [ ] `DD-ACCESS-001` recorded in the product's Memory documentation facet.

---

**End of Access Layer Pattern**
