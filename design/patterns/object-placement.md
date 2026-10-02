---
title: Object Placement Pattern
anchor: object-placement
type: pattern
status: standard
version: 2.0
normative: true
---

# Object Placement: Pattern

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Pattern (cross-cutting, platform-agnostic interface spec) |
| **Scope** | Any relational or cloud data platform: where objects live and who may reach them |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | Organisation profiles supplied for a build ([Organisation Profile Standard](../core/ORGANISATION_PROFILE.md)), one per organisation and platform. `implementation/{platform}/patterns/object-placement/` holds a binding's reference example of how it consumes resolved placement; it is not an organisation's implementation. |

This pattern is an **interface specification**: it defines what a conforming object-placement implementation must **declare**, not a fixed convention. An AI-native data product agent must not assume how an organisation structures its containers: it reads the placement resolved from a conforming implementation before generating any deployment artefact, placement decision, or access statement. It realises the `object-placement` concern that every module applies.

---

## 1. Purpose

Where an object lives determines who can reach it. This pattern makes container placement and its access consequences **explicit and machine-readable**, so agents place objects deterministically and never co-locate objects that must be separated for access control.

**This pattern provides no capability.** It imposes a contract on where objects are placed and how access follows from placement, rather than offering an operation a design can require. Every module applies it; none requires it.

---

## 2. Terminology

| Term | Meaning |
|------|---------|
| **Container** | Smallest named unit of object ownership. |
| **Namespace** | A hierarchical grouping of containers (implicit or explicit `catalog.schema`). |
| **Object** | A first-class artefact: table, view, procedure, function, index. |
| **Object role** | The kind of object a build creates; an organisation profile names and places each role ([Organisation Profile Standard](../core/ORGANISATION_PROFILE.md) §5). Implementations declare which roles they recognise and how they abbreviate them. |
| **Parent / Child container** | A parent allocates space or organises children but holds no objects; a child holds objects. |
| **Structural container** | Exists solely to organise administrative scope or namespace; holds no data objects. |
| **Access principal** | An identity that can be granted rights: a role, a user, a group, or a policy. |
| **Separation policy** | The rule governing whether object roles are co-located or separated. |
| **Derivation function** | The deterministic algorithm computing the target container and object name for an object. |
| **Implied grant** | A permission not granted to end users directly but required for the separation architecture to work (e.g. cross-container rights for a view to reference its source). |

**Illustrative platform terms (non-normative).** What a container and an access principal are called varies by platform. For example, a container is a DATABASE on Teradata, a SCHEMA on Snowflake and Databricks, and a DATASET on BigQuery; an access principal is a ROLE or USER on Teradata, a ROLE on Snowflake, and an IAM principal on a cloud provider. An organisation profile declares its platform's terms in its `Platform:` block; nothing in this pattern depends on them.

---

## 3. Agent Consumption

When generating any object:

1. **Locate** the organisation's conforming implementation (priority order below).
2. **Read placement from the build context.** Every object's container and physical name is resolved once, from the organisation profile's rules, before any template renders ([Platform Implementation Authoring Standard](../core/IMPLEMENTATION_AUTHORING.md) §3). An agent does not call the derivation function at generation time and never derives a container or name itself; it reads the resolved value.
3. **Generate** the object in its resolved container only: never in a structural or parent container, nor one for a different role.
4. **Provision implied grants** as part of the standard sequence, not as an afterthought. The binding computes them from the resolved placement.
5. **Validate** after each deployment phase; on failure, halt and report: do not proceed with dependent objects.
6. **Never assume** co-location or a flat structure. An object with no resolved placement is a missing fact: stop and report it, naming the input it should come from.

Where the implementation is in prose rather than an organisation profile, there is no build context to read. An agent then resolves every object's placement from it once, up front, and generates from that resolution, so each object is placed by the same reading of the rules.

**Priority order for locating an implementation:**

1. The organisation profile supplied for the build ([Organisation Profile Standard](../core/ORGANISATION_PROFILE.md)), resolved into the build context by `tooling/build/build_context.py`.
2. An organisation profile or other conforming implementation named by an explicit path in the current conversation or project instructions.
3. A conforming standard named in the product's Semantic module.
4. **If none exists:** STOP and ask the user for their object-placement standard (container structure, separation, naming) before generating objects.

`implementation/{platform}/patterns/object-placement/` is not on this list. It documents how a binding consumes resolved placement, with a reference example; it is never an organisation's implementation, and an agent does not build from it as one.

---

## 4. Required Sections

Every conforming implementation MUST include all eight, using these exact headings. An agent may reject an implementation that omits any required section.

The preferred conforming implementation is an [organisation profile](../core/ORGANISATION_PROFILE.md): it carries these eight sections as its first eight headings and states each section's rules in blocks the build-context resolver executes, so the derivation function is run rather than interpreted and its worked examples are re-checked on every build. A prose implementation still conforms, but an agent must then apply its rules by reading them. Where a section below says how a profile satisfies it, that is the profile's form of the same requirement, not an exception to it.

**Section 1. Platform Declaration.** Target platform and version; the platform's term for "container" and "access principal"; whether the namespace is hierarchical or flat; the maximum container-name length; reserved characters/words. In an organisation profile, the platform and version may be stated in its frontmatter (`platform`, `platform_version`), and the rest in its `Platform:` block.

**Section 2. Container Model.** Whether structural, parent, and/or child containers are used and what each may hold; the full hierarchy depth; the rule for which containers may hold data objects; whether physical system boundaries exist between lifecycle phases. In an organisation profile, a container line in `Containers:` ending `in <parent key>` places that container under a parent; a parent holds no objects and no placement rule may route to one.

**Section 3. Naming Pattern.** The complete pattern for each object role as an ordered sequence of segments, each with its source (a product, module, entity, kind or environment fact, or literal text), its format, whether it is mandatory or conditional, and the separator. A worked example. The ordering principle. Name templates with variables and filters, as an organisation profile writes them in `Naming:`, satisfy this: each placeholder is a segment, its filters are the segment's format, and the literal text between placeholders gives the separators. **Environment-agnostic rule:** object names must be stable across lifecycle phases, only the container changes between environments; environment markers (`_dev`, `_uat`) on object names are prohibited (`INV-MASTER-006`).

**Section 4. Object Placement Rules.** A table mapping each recognised object role to its container; the separation policy; abbreviations. Must address persistent tables and views (MUST), stored procedures and functions/UDFs (MUST when the binding emits them), and macros/indexes/temporary objects (SHOULD). In an organisation profile these are the object roles of the [Organisation Profile Standard](../core/ORGANISATION_PROFILE.md) §5, where procedures and functions are optional roles, placed by the `Placement:` block's rules; a rule written `<role> <class>` routes objects holding data of that classification to their own container. Must declare one of two mutually exclusive object-naming rules:
- **Rule A: container-discriminated** (`STRICT_SEPARATION`): the container is the sole role discriminator; object names are identical across container roles; type markers (`v_`, `_vw`) are prohibited.
- **Rule B: name-discriminated** (`CO_LOCATED`/`TYPE_GROUPED`): a declared, consistent, reversible disambiguation rule producing a unique name per `(logical_name × role)`, demonstrated with ≥2 examples.
For implementations with views, a **view-layer architecture** declaration: whether views are divided into tiers with different rules on which container roles each tier may reference, or an explicit statement that no tier architecture applies.

**Section 5. Separation Policy.** Exactly one of `STRICT_SEPARATION`, `TYPE_GROUPED`, `CO_LOCATED`, `CUSTOM`, with rationale, exceptions, and the access implication of the choice. An organisation profile states it, with its object-naming rule, in its `Separation:` block.

**Section 6. Derivation Function.** A deterministic algorithm computing the target container and object name for any object, with all input parameters, conditional branches, ≥3 worked examples, and parent-container derivation where applicable. Minimum signature, matching an organisation profile's derivation inputs:

```
derive_placement(
  object_role,     // table, base_view, consumer_view, procedure, function
  module,          // the module the object belongs to
  entity,          // the entity name, as the specification writes it
  kind,            // the entity kind, where a rule depends on it
  classification,  // the entity's class: its most sensitive attribute's
  environment      // the lifecycle phase being built
) -> container_name, object_name
```

The worked examples are executable: in an organisation profile they are the `Derivation:` block's examples, which the resolver re-derives on every build, rejecting the profile if any disagrees. The function is run once, when the build context is resolved; agents read its results (§3).

**Section 7. Access Model.** How access is granted (role/user/policy-based); container-level vs object-level and which is preferred; standard principal types; naming; prohibitions; how the separation policy interacts with access; and any **implied grants** the architecture requires, with when they must be provisioned in the standard sequence. In an organisation profile, the `Principals:` block declares the principal for each access tier, either one to create or an existing one to bind, and the grant level. The profile does not declare grants: the binding computes the implied grants from the resolved placement and provisions them at Phase 1.5a of the [access-layer pattern](access-layer.md).

This section declares what the *container structure* makes necessary. The consumer access model, which access tier reads which module and when, belongs to the [access-layer pattern](access-layer.md) and is not restated here: a placement implementation that reproduces it creates a second copy to keep in step, and the two will diverge. Where they already have, the access-layer grant matrix is authoritative.

**Section 8. Validation Procedure.** An agent-executable procedure confirming: objects are in their intended containers; not in containers for a different role; not in parent/structural containers; end-user principals granted at the correct level; all implied grants present. States passing/failing output and requires halt-and-report on failure: never silent auto-correct. In an organisation profile, this section states that the procedure is generated by the platform binding from the profile and run after each deployment phase; it needs no block.

---

## 5. Optional Sections

Implementations MAY include: environment lifecycle, container-retirement procedure, metadata/tagging, co-existence rules during migration, automation hooks. Agents read them if present. An organisation profile carries some of these as its own sections (`Environments`, `Adoption`).

---

## 6. Conformance Checklist

- [ ] Section 1 names the platform and version (or the profile's frontmatter does) and the container and access-principal terms.
- [ ] Section 2 describes the parent/child/flat structure.
- [ ] Section 3 fully specifies every naming segment, as segments or as name templates, and the environment-agnostic rule.
- [ ] Section 4 covers persistent tables and views, covers procedures and functions wherever the binding emits them, declares Rule A or Rule B, and declares a view-tier architecture or states none applies.
- [ ] Section 5 declares one of the four named policies.
- [ ] Section 6 produces an unambiguous container and object name for any valid input, and its worked examples execute.
- [ ] Section 7 specifies principal types and grant level, and how implied grants are provisioned (computed by the binding from resolved placement, for a profile).
- [ ] Section 8 is agent-executable without human input, or is generated by the binding.
- [ ] All section headings match exactly.

---

## 7. Non-Goals

This pattern does not prescribe a specific naming convention, SQL dialect, access-control technology, number of containers or environments, provisioning mechanism, or physical topology. Those belong to the organisation's implementation.

---

**End of Object Placement Pattern**
