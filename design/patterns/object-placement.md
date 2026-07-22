# Object Placement — Pattern

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Pattern (cross-cutting, platform-agnostic interface spec) |
| **Scope** | Any relational or cloud data platform — where objects live and who may reach them |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/patterns/object-placement/`](../../implementation/teradata/patterns/object-placement/) |

This pattern is an **interface specification**: it defines what a conforming object-placement
implementation must **declare**, not a fixed convention. An AI-native data product agent must not
assume how an organisation structures its containers — it must read a conforming implementation
before generating any DDL, placement decision, or access statement. It realises the
`object-placement` concern that every module applies.

---

## 1. Purpose

Where an object lives determines who can reach it. This pattern makes container placement and its
access consequences **explicit and machine-readable**, so agents place objects deterministically
and never co-locate objects that must be separated for access control.

---

## 2. Terminology

| Term | Meaning |
|------|---------|
| **Container** | Smallest named unit of object ownership. Maps to: Teradata DATABASE, Snowflake SCHEMA, BigQuery DATASET, Databricks SCHEMA. |
| **Namespace** | A hierarchical grouping of containers (implicit or explicit `catalog.schema`). |
| **Object** | A first-class artefact: table, view, procedure, function, index. |
| **Object type** | The kind of object; implementations declare which types they recognise and how they abbreviate them. |
| **Parent / Child container** | A parent allocates space or organises children but holds no objects; a child holds objects. |
| **Structural container** | Exists solely to organise administrative scope or namespace; holds no data objects. |
| **Access principal** | An identity that can be granted rights (Teradata ROLE/USER, Snowflake ROLE, IAM principal). |
| **Separation policy** | The rule governing whether object types are co-located or separated. |
| **Derivation function** | The deterministic algorithm computing the target container for an object. |
| **Implied grant** | A permission not granted to end users directly but required for the separation architecture to work (e.g. cross-container rights for a view to reference its source). |

---

## 3. Agent Consumption

When generating any object:

1. **Locate** a conforming implementation (priority order below).
2. **Read all required sections** before generating any DDL, grant, or revocation.
3. **For each object**, call the derivation function with its type and context to find its container.
4. **Generate** the object in that container only — never in a structural or parent container, nor one for a different type.
5. **Provision implied grants** as part of the standard sequence, not as an afterthought.
6. **Validate** after generation; on failure, halt and report — do not proceed with dependent objects.
7. **Never assume** co-location or a flat structure. If uncertain, ask.

**Priority order for locating an implementation:**

1. An explicit path in the current conversation or project instructions.
2. `implementation/{platform}/patterns/object-placement/` in the product repository.
3. A conforming standard named in the product's Semantic module.
4. **If none exists:** STOP and ask the user for their object-placement standard (container structure, separation, naming) before generating objects.

---

## 4. Required Sections

Every conforming implementation MUST include all eight, using these exact headings. An agent may
reject an implementation that omits any required section.

**Section 1 — Platform Declaration.** Target platform and version; the platform's term for
"container" and "access principal"; whether the namespace is hierarchical or flat; the maximum
container-name length; reserved characters/words.

**Section 2 — Container Model.** Whether structural, parent, and/or child containers are used and
what each may hold; the full hierarchy depth; the rule for which containers may hold data objects;
whether physical system boundaries exist between lifecycle phases.

**Section 3 — Naming Pattern.** The complete pattern as an ordered sequence of `{{Segment}}`
segments, each with position, data type, permitted values/derivation, whether mandatory or
conditional, and the separator. A worked example. The ordering principle. **Environment-agnostic
rule:** object names must be stable across lifecycle phases — only the container changes between
environments; environment markers (`_dev`, `_uat`) on object names are prohibited (`INV-MASTER-006`).

**Section 4 — Object Placement Rules.** A table mapping each recognised object type to its
container; the separation policy; abbreviations. Must address persistent tables, views, stored
procedures, and functions/UDFs (MUST), and macros/indexes/temporary objects (SHOULD). Must declare
one of two mutually exclusive object-naming rules:
- **Rule A — container-discriminated** (`STRICT_SEPARATION`): the container is the sole type
  discriminator; object names are identical across container types; type markers (`v_`, `_vw`) are
  prohibited.
- **Rule B — name-discriminated** (`CO_LOCATED`/`TYPE_GROUPED`): a declared, consistent, reversible
  disambiguation rule producing a unique name per `(logical_name × type)`, demonstrated with ≥2
  examples.
For implementations with views, a **view-layer architecture** declaration: whether views are
divided into tiers with different rules on which container types each tier may reference, or an
explicit statement that no tier architecture applies.

**Section 5 — Separation Policy.** Exactly one of `STRICT_SEPARATION`, `TYPE_GROUPED`,
`CO_LOCATED`, `CUSTOM`, with rationale, exceptions, and the access implication of the choice.

**Section 6 — Derivation Function.** A deterministic algorithm computing the target container for
any object, executable by an agent, with all input parameters, conditional branches, ≥3 worked
examples, and parent-container derivation where applicable. Minimum signature:

```
derive_container(
  object_type,        // the type of object to be placed
  environment_inputs, // platform-specific environment identifiers
  classification      // security/access classification, if applicable
) -> container_name
```

**Section 7 — Access Model.** How access is granted (role/user/policy-based); container-level vs
object-level and which is preferred; standard principal types; naming; prohibitions; how the
separation policy interacts with access; and any **implied grants** the architecture requires —
declared explicitly, with when they must be provisioned, in the standard sequence.

**Section 8 — Validation Procedure.** An agent-executable procedure confirming: objects are in
their intended containers; not in containers for a different type; not in parent/structural
containers; end-user principals granted at the correct level; all implied grants present. States
passing/failing output and requires halt-and-report on failure — never silent auto-correct.

---

## 5. Optional Sections

Implementations MAY include: environment lifecycle, container-retirement procedure,
metadata/tagging, co-existence rules during migration, automation hooks. Agents read them if present.

---

## 6. Conformance Checklist

- [ ] Section 1 names the container and access-principal terms.
- [ ] Section 2 describes the parent/child/flat structure.
- [ ] Section 3 fully specifies every naming segment and the environment-agnostic rule.
- [ ] Section 4 covers the four mandatory object types and declares a view-tier architecture or states none applies.
- [ ] Section 5 declares one of the four named policies.
- [ ] Section 6 produces an unambiguous container for any valid input.
- [ ] Section 7 specifies principal types, grant level, and any implied grants.
- [ ] Section 8 is agent-executable without human input.
- [ ] All section headings match exactly.

---

## 7. Non-Goals

This pattern does not prescribe a specific naming convention, SQL dialect, access-control
technology, number of containers or environments, provisioning mechanism, or physical topology.
Those belong to the organisation's implementation.

---

**End of Object Placement Pattern**
