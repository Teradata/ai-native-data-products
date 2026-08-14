---
title: Semantic Module
anchor: semantic
type: module
status: standard
version: 2.0
normative: true
---

# Semantic Module: Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Semantic module: knowledge and meaning; the discovery map agents navigate |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/modules/semantic/`](../../implementation/teradata/modules/semantic/) |

Semantic is the module that **provides `SemanticRegistration`** and the discovery map every other module and pattern points at: the entity/column catalogue, the relationship graph, the module and primary-object registries, and the product orientation layer. It is the map that makes [Master agent discovery](../core/MASTER_DESIGN.md) possible.

---

## 1. Purpose

Semantic helps an agent generate correct queries by answering, from queryable metadata rather than inference:

1. What products exist, and how do I orient to one?
2. What modules are deployed, and where?
3. What entities (tables) exist, and what attributes (columns) do they have?
4. How do entities relate: and how do I join A to B, including multi-hop?

**Key terminology:** an **entity** is a table, an **attribute** is a column, a **relationship** is how tables join. The catalogue registers *objects*, never rows.

---

## 2. Scope and Boundaries

**In scope:** schema metadata, hundreds of rows describing entities, attributes, relationships, naming standards, module locations, primary objects, and product orientation.

**Out of scope:** instance data (millions of rows → Domain and the other modules); business content; individual records. Semantic stores *what exists and how it connects*, never the data itself (`INV-SEMANTIC-001`).

**Boundary with Memory's documentation facet:** Semantic stores *what exists and how it connects*; Memory's design memory stores *why it exists, how to use it, and what changed*. They must not duplicate each other.

---

## 3. Entity Model: The Discovery Map

Semantic's entities are the discovery catalogue. All apply `object-placement` and `access-layer`; those that are versioned apply `temporal-lifecycle-metadata`; all require `RichMetadata`.

### 3.1 Catalogue

```
Entity: EntityMetadata            [kind: Record]
  entity_metadata_id: Identifier
  entity_name: ShortText [required]  // business name (Party, Product)
  entity_description: Text [required]  // purpose and scope
  module_name: Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [required]
  container_name: ShortText [optional]  // where the table lives
  table_name: ShortText [required]
  view_name: ShortText [optional]  // the standard current view
  surrogate_key_column: ShortText [optional]
  natural_key_column: ShortText [optional]
  temporal_pattern: ShortText [required]  // the temporal-lifecycle profile (CURRENT_STATE, SCD2_HISTORY, EVENT_APPEND_ONLY, …)
  current_flag_column: ShortText [optional]  // names the current-flag (temporal)
  deleted_flag_column: ShortText [optional]
  industry_standard: ShortText [optional]  // FIBO, HL7, CUSTOM, …
  is_active: Flag

Entity: ColumnMetadata            [kind: Record]
  column_metadata_id: Identifier
  container_name: ShortText [required]
  table_name: ShortText [required]
  column_name: ShortText [required]
  business_description: Text [optional]  // what the data represents
  is_pii: Flag
  is_sensitive: Flag
  data_classification: Enum{PUBLIC|INTERNAL|CONFIDENTIAL|RESTRICTED} [optional]
  is_required: Flag
  declared_type: ShortText [optional]  // the declared data type, as text
  allowed_values: Json [optional]  // permitted-value domain
  is_active: Flag

Entity: NamingStandard            [kind: Record]
  naming_standard_id: Identifier
  standard_type: Enum{SUFFIX|PREFIX|PATTERN|ABBREVIATION} [required]
  standard_value: ShortText [required]  // e.g. _H, _id, is_, dts
  meaning: Text [required]  // what the element means
  applies_to: Enum{TABLE|COLUMN|VIEW|ALL} [optional]
  is_active: Flag

Entity: TableRelationship         [kind: Record]
  relationship_id: Identifier
  relationship_name: ShortText [required]
  source_container: ShortText [optional]
  source_table: ShortText [required]
  source_column: ShortText [required]  // the referencing (foreign) key
  target_container: ShortText [optional]
  target_table: ShortText [required]
  target_column: ShortText [required]  // the referenced key
  relationship_type: Enum{FOREIGN_KEY|HIERARCHY|ASSOCIATIVE} [required]
  cardinality: Enum{ONE_TO_ONE|ONE_TO_MANY|MANY_TO_ONE|MANY_TO_MANY} [optional]
  is_mandatory: Flag
  is_active: Flag
```

### 3.2 Registries and orientation

```
Entity: DataProductRegistry       [kind: Record]  // product-level orientation anchor
  product_id: NaturalKey [required]  // stable product identifier
  product_name: ShortText [required]
  product_version: ShortText [required]
  product_status: Enum{DRAFT|ACTIVE|DEPRECATED|RETIRED} [required]
  owner_team: ShortText [optional]
  semantic_container: ShortText [optional]  // where to look after registry discovery
  memory_container: ShortText [optional]
  observability_container: ShortText [optional]
  manifest: Json [optional]  // machine-readable orientation manifest
  contract_uri: ShortText [optional]
  policy_uri: ShortText [optional]
  quality_uri: ShortText [optional]
  lineage_uri: ShortText [optional]
  approved_entrypoint: ShortText [optional]  // approved first data-access surface
  approved_access_mode: Enum{VIEW|MCP_TOOL|SEMANTIC_QUERY} [optional]
  is_active: Flag
  is_deleted: Flag [deleted-flag]

Entity: DataProductMap            [kind: Record]  // module registry
  module_id: Identifier
  module_name: Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [required]
  module_purpose: Text [optional]
  container_name: ShortText [required]  // where the module is deployed (critical for discovery)
  module_version: ShortText [optional]
  deployment_status: Enum{DEPLOYED|PLANNED|DEPRECATED} [required]
  is_active: Flag

Entity: PrimaryObject             [kind: Record]  // one row per agent-facing object
  primary_object_id: Identifier
  module_id: Reference [required] [-> DataProductMap]
  container_name: ShortText [required]  // the object's exact deployed container
  object_name: ShortText [required]  // exact deployed name; used verbatim, never derived
  object_type: Enum{TABLE|VIEW|PROCEDURE|FUNCTION} [required]
  object_role: Enum{AGENT_ENTRYPOINT|ANALYTICAL_QUERY|REFERENCE_LOOKUP|RELATIONSHIP_BRIDGE|LINEAGE_EVIDENCE|OPERATIONAL_METRIC|WRITE_TARGET|INTERNAL_SUPPORT} [required]
  usage_guidance: Text [optional]
  is_active: Flag

Entity: DataProductOrientation    [kind: Record]  // one ordered row per product resource
  orientation_id: Identifier
  product_id: NaturalKey [required]  // the product this resource belongs to (DataProductRegistry.product_id)
  resource_role: Enum{MANIFEST|TRUST_GATE|MODULE_MAP|OBJECT_CATALOGUE|ENTITY_CATALOGUE|COLUMN_CATALOGUE|RELATIONSHIP_CATALOGUE|RELATIONSHIP_PATHS|LINEAGE|QUERY_COOKBOOK|GLOSSARY|DESIGN_DECISIONS|POLICY|QUALITY} [required]  // open vocabulary; one role per row, never a list
  container_name: ShortText [optional]  // deployed container, for object-backed resources
  object_name: ShortText [optional]  // deployed object; used verbatim, never derived
  resource_uri: ShortText [optional]  // URI for an MCP or external resource, when not a database object
  usage_guidance: Text [optional]  // how a consumer should use this resource
  is_required: Flag  // a missing required resource is a conformance failure
  discovery_order: Integer [required]  // ascending processing order; the trust gate precedes every analytical resource
  is_active: Flag
```

`ViewMetadata` (one row per base-table exposure, with a `view_type` and a single primary exposure per base table) and `ViewColumnType` (curated types for view columns) complete the catalogue; both are platform-detail-heavy and specified in the implementation.

### 3.3 Access-object layer

The catalogue above models entities and how they relate; it does not model the **access layer** — which objects a consumer actually queries. A platform security model may expose one entity through several objects (locking, business, current views), and a product may publish composite ("enriched") objects that join several entities into one unit. `AccessObject` registers those facts so a consumer resolves any queryable object to its logical meaning **once, from metadata**, rather than reverse-engineering it from names or definitions. This is *access-layer metadata* — which objects represent what — distinct from the security [access-layer pattern](../patterns/access-layer.md), which governs who may read them.

```
Entity: AccessObject              [kind: Record]  // one row per consumable object
  access_object_id: Identifier
  container_name: ShortText [required]  // where the object is deployed
  object_name: ShortText [required]  // the queryable object
  access_role: Enum{BASE|PASSTHROUGH|COMPOSITE} [required]  // open vocabulary; extensions add roles
  represents_entity: ShortText [optional]  // entity this exposes (EntityMetadata.entity_name); null for cross-entity composites
  object_grain: ShortText [optional]  // plain-language grain, e.g. one row per call
  is_agent_consumable: Flag  // whether an agent should query this object directly
  resolves_to_object: ShortText [optional]  // for 1:1 passthroughs, the object it maps straight through to
  access_note: Text [optional]  // locking, filtering, or usage guidance
  is_active: Flag

Entity: AccessComposition         [kind: Record]  // one row per member of a COMPOSITE object
  access_composition_id: Identifier
  composite_container: ShortText [required]
  composite_object: ShortText [required]  // the composite being described
  member_seq: Integer [required]  // ordering of the member within the composite
  member_entity: ShortText [required]  // entity the member represents (EntityMetadata.entity_name)
  member_role: Enum{ANCHOR|INNER|LEFT|RIGHT|FULL} [required]  // join role within the composite
  join_path: Text [optional]  // entity-level join condition, same form as the path-discovery joins
  is_grain_contributor: Flag  // whether this member changes the composite's grain
  member_note: Text [optional]
  is_active: Flag
```

**Consumption contract (normative).** A consumer selecting data resolves through `AccessObject` — it chooses objects marked agent-consumable and reads `represents_entity` — rather than querying base tables directly. A `COMPOSITE` object is presented as a single unit; its internal structure is read from `AccessComposition`, never by parsing a definition or recomputing column lineage at consumption time. Emitted joins target consumable objects (access-resolved, §5), not base tables. **Object names are not a contract:** no consumer infers an object's role, layer, entity, or purpose from its name; the registry is the single source of truth (`INV-SEMANTIC-008`).

**Establishment and ownership (normative).** This metadata is **established once at deployment** by a registration step, defined here by responsibility rather than by tool. The step classifies objects from **verifiable structure** — the dependency graph and object definitions — not from names, and asserts the result in the registry; consumers read it and never recompute it. The concrete role vocabulary beyond the small open baseline, the physical realisation, and the population step are platform concerns (implementation). `AccessObject` is authoritative for object multiplicity per entity; `EntityMetadata.view_name` is retained as the denormalised "canonical consumable object" pointer, and `BASE`/`PASSTHROUGH` rows may be backfilled from `ViewMetadata`.

---

## 4. Data Product Orientation Layer

Discovery is **product-first, not tables-first** (`INV-SEMANTIC-004`). A client must not begin by guessing containers or listing tables; it orients to the product, then navigates.

**Metadata-first handshake:**

1. The client asks what products are available → reads `DataProductRegistry`.
2. It reads the selected product's **manifest**.
3. The manifest recommends navigation: contract → semantic model → policy → quality → lineage → approved data access.
4. It queries data **only** through the approved entrypoint.

Where the product is reached over MCP, the orientation layer is exposed as **resources first** (the product list, per-product manifest, contract, semantic model, policy, quality, lineage, physical map) and **tools second** (search products, describe a product, get the recommended entrypoint, query approved data, explain an access path). The registry also designates the **gate-authoritative producer** the [validation pattern](../patterns/validation.md) reads, and its `manifest` records the entrypoints and recommended navigation.

**The orientation relation (normative).** The handshake above is backed by a queryable, ordered relation, `DataProductOrientation` — one row per product resource, its `resource_role`, where it lives, whether it is required, and the `discovery_order` to process it — so a consumer reads the sequence rather than knowing repository conventions or inventing one, and a validator can *check* it. The baseline required roles a conformant product publishes, in canonical order, are: `MANIFEST`, `TRUST_GATE`, `MODULE_MAP`, `OBJECT_CATALOGUE`, `ENTITY_CATALOGUE`, `COLUMN_CATALOGUE`, `RELATIONSHIP_CATALOGUE`; `RELATIONSHIP_PATHS`, `LINEAGE`, `QUERY_COOKBOOK`, `GLOSSARY`, `DESIGN_DECISIONS` are optional, and `POLICY` / `QUALITY` are published where they apply. The vocabulary is open: an extension may add roles.

**Consumption contract (normative).** A consumer processes resources in ascending `discovery_order`; evaluates the `TRUST_GATE` resource **before** any analytical resource, and a blocked gate stops autonomous use (the [validation pattern](../patterns/validation.md)); resolves every `is_required` resource, treating a missing one as a conformance failure; and uses the stored `container.object` (or `resource_uri`) **verbatim**, never deriving object names from conventions (`INV-SEMANTIC-011`).

**The manifest is generated, not authored (normative).** The machine-readable manifest is a **view derived** from `DataProductRegistry` and `DataProductOrientation` — it pivots the ordered resources into named entrypoint columns — so it cannot drift from the metadata it summarises (`INV-SEMANTIC-012`). The registry's serialised `manifest` remains the whole-document form for clients that want it in one read, regenerated from the same authoritative metadata rather than hand-authored to diverge.

**`DD-DISCOVERY-001`.** Deploying the orientation layer settles one decision and records it: *how does an agent that knows only the product's name reach data it is allowed to use?* The record names which manifest fields are populated and why, the approved entrypoint and access mode, and the navigation the manifest recommends. What makes it worth recording rather than inferring is that the answer is a set of choices the deployed metadata cannot explain about itself: an agent can read that an entrypoint is approved, not why that surface was chosen as the approved one, nor what an agent arriving without a product name is expected to do.

This decision is bounded by the product. Discovery *across* products depends on an organisational registry outside any one product's control, and `INV-MASTER-003` keeps a product self-contained; where such a registry exists, registering into it is an operational step, not a property of the product's design.

---

## 5. Multi-Hop Path Discovery

`TableRelationship` is the machine-readable entity-relationship model. From it, a **path-discovery surface** lets an agent find how to join any two entities, directly or through intermediate entities, in either direction, up to a bounded number of hops, and returns the join conditions to use. This is the single most important discovery capability: an agent cannot traverse a path it has no record of.

**Completeness requirement (`INV-SEMANTIC-005`).** `TableRelationship` must register **every** relationship an agent is expected to traverse: not only those with physical foreign keys:

| Category | Common omission |
|----------|-----------------|
| Intra-module keys (child → parent, entity → keymap) | Child-to-parent within an entity cluster |
| Reference lookups (entity → reference set) | Reference decodes, especially from append-only tables |
| Cross-module joins (Domain → Search / Prediction) | Joins between modules |
| Multi-hop semantic chains | Chains used in lineage and audit |
| Reverse directions | Bidirectional traversal needs |

An entity that appears in `EntityMetadata` but in no `TableRelationship` is either a *documented* standalone (recorded as a design decision) or an omission that will cause agent navigation failures.

**Derived relationships are registered without exception.** Some relationships in the table above are chosen; others follow mechanically from a modelling decision already taken, and those are the ones that go missing. Where `DEC-SURROGATE-ALLOCATION` is settled as `keymap`, every entity allocated that way has an entity-to-keymap relationship, for every such entity, not for the first one. The characteristic failure is registering one instance of a derived shape and treating the rest as covered: three entities share the pattern, one gets a row, and the other two appear as isolated entities that no agent can traverse to. Anything derivable this way is generated from the model rather than enumerated by hand, because a list maintained by hand is a list that ends after the first entry.

**Access-resolved paths.** The path-discovery surface is the logical, entity-level truth, and its joins are expressed against base tables. Where a platform exposes a separate consumable layer (§3.3), those joins point at objects an agent may not query, or at the wrong grain. An **access-resolved** surface rewrites each path endpoint to the entity's canonical consumable object — the agent-consumable `AccessObject`, collapsing any `resolves_to_object` chain — so an agent receives joins written against objects it can actually query. What it contains is normative; whether it is persisted as a view or a refreshed table is a platform decision (implementation). A path whose endpoint entity has no consumable object is omitted, not emitted against a base table.

---

## 6. Agent Discovery

The discovery order realises [Master](../core/MASTER_DESIGN.md):

1. **Product**: read `DataProductRegistry` / the manifest (orientation).
2. **Module**: read `DataProductMap` for deployed modules and their containers.
3. **Object**, read `PrimaryObject` for each module's entrypoints by `object_role`, using the stored `container.object` **verbatim**, never deriving names from conventions.
4. **Entity / attribute**: read `EntityMetadata` / the column catalogue.
5. **Relationship**: read the path-discovery surface to join.

A live **column catalogue** joins the deployed structural facts to the curated `ColumnMetadata`, carrying the **provenance** of every resolved value (declared-type source, description source, documentation coverage) so consumers see a complete schema without the curated store copying structural facts. Its construction is platform-specific (implementation).

Before emitting a query, an agent resolves the object to read through `AccessObject` (§3.3): it selects an agent-consumable object for the entity, expands any `COMPOSITE` from `AccessComposition`, and takes join targets from the access-resolved paths — so it queries the objects the product intends, at the right grain, without inferring anything from a name.

---

## 7. Applied Patterns

| Pattern | Contribution to Semantic |
|---------|--------------------------|
| `object-placement` | Which container the catalogue and views live in, and who may reach them. |
| `access-layer` | Consumers read the Semantic container in Phase 1.5: the minimum grant that makes a product discoverable. |
| `temporal-lifecycle-metadata` | Versioned catalogue entities follow a declared profile; `EntityMetadata.temporal_pattern` *carries* each entity's profile for the whole product. |
| `validation` | Its primary-object, view, and relationship-completeness checks are canonical STRUCTURAL/SEMANTIC validator checks. |

---

## 8. Capabilities and Composition

Semantic is **cross-cutting and soft**: nothing hard-depends on it (modules register *when it is present*), and it hard-depends on nothing, so it describes whatever modules are in the composition. It appears in a traditional data product and an AI-native product, and is absent from a minimal Data Asset. See the [composition mechanism](../core/DESIGN_LANGUAGE.md).

**Provides:**

| Capability | Made available to |
|------------|-------------------|
| `SemanticRegistration` | Every module: the target where entities, columns, relationships, and primary objects are registered on deploy. |
| Agent discovery (product / module / entity / relationship) | Agents, as the map they navigate. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on every catalogue object. |
| `DocumentationCapture` | `[soft]` | `module:Memory` | Record Semantic's own design decisions when Memory is present. |
| `EntityJoinBack` | `[soft]` | `module:Domain` | Describe Domain entities; catalogue reads reference them. |

---

## 9. Integration with Other Modules

Semantic is the map every other module registers itself in. The relationship is uniform: a module deploys, then registers its entities, attributes, and relationships through `SemanticRegistration`.

- **Every module → Semantic**: on deploy, each module registers its primary objects so agents can discover them. Soft in both directions: a composition without Semantic simply has no discovery map, and agents fall back to the platform catalogue plus `RichMetadata`.
- **Domain → Semantic**. Semantic describes Domain entities and their relationships; it holds no copy of their content, and resolves a catalogue entry to its entity by joining back.
- **Observability → Semantic**: the lineage views are deployed into the Semantic container, so lineage is discoverable alongside the structure it describes.
- **Temporal profiles**: a table declares its temporal profile in Semantic's entity metadata, which is where validators read it rather than inferring behaviour from column names.

Semantic never becomes a dependency of the modules it describes: it observes and indexes them.

---

## 10. Invariants

- `INV-SEMANTIC-001`: Semantic stores schema metadata only: entities, attributes, relationships, orientation; never instance data or business content.
- `INV-SEMANTIC-002`: the catalogue registers objects (entity = table, attribute = column, relationship = join), never rows.
- `INV-SEMANTIC-003`: every deployed module and its primary objects are registered; agents obtain objects by the stored fully-qualified identity, never by deriving names from conventions.
- `INV-SEMANTIC-004`: discovery is product-first; clients read the product registry or manifest before module maps or data, per the orientation contract.
- `INV-SEMANTIC-005`: `TableRelationship` registers every relationship an agent is expected to traverse; an unrelated entity is a documented standalone or an omission.
- `INV-SEMANTIC-006`: every entity declares its temporal profile in `EntityMetadata.temporal_pattern`, so validators resolve temporal behaviour from metadata (the `temporal-lifecycle-metadata` pattern).
- `INV-SEMANTIC-007`: primary-object roles come from the controlled vocabulary; at most one primary exposure per base table.
- `INV-SEMANTIC-008`: a consumer resolves the object to query through `AccessObject` (an agent-consumable object), never by inferring an object's role, layer, or entity from its name; the registry is the single source of truth and is established once at deployment from verifiable structure.
- `INV-SEMANTIC-009`: every `AccessObject.represents_entity` and every `AccessComposition.member_entity` resolves to a catalogued `EntityMetadata` entity; a non-`COMPOSITE` consumable object names the entity it represents.
- `INV-SEMANTIC-010`: a `COMPOSITE` object's structure is recorded in `AccessComposition` with exactly one `ANCHOR` member, and is expanded as a unit from that metadata, never by parsing the object's definition.
- `INV-SEMANTIC-011`: the orientation relation lists the required baseline resources, one row per role, in ascending `discovery_order` with the trust gate ordered before every analytical resource; consumers use stored identities verbatim, and a missing required resource is a conformance failure.
- `INV-SEMANTIC-012`: the machine-readable manifest is generated from the registry and orientation relation (a derived view), never hand-authored, so it cannot drift from its sources.

---

## 11. Designer Responsibilities

**Designers supply:** the entity/column/relationship catalogue for every module; naming standards; the module map and primary objects with their roles; the product registry and manifest, including the gate-authoritative producer the [validation pattern](../patterns/validation.md) reads; the temporal profile per entity.

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Entities, columns, relationships, and primary objects registered for every deployed module (`SemanticRegistration`).
- [ ] Each entity declares its temporal profile (`INV-SEMANTIC-006`).
- [ ] The product registry and manifest are populated; discovery is product-first (`INV-SEMANTIC-004`).
- [ ] The manifest names the `gate_authoritative_producer`, settled as a design decision per the [validation pattern](../patterns/validation.md). One producer still needs naming.
- [ ] The orientation relation publishes the required baseline resources in `discovery_order` with the trust gate first, and the manifest is a generated view over registry + orientation (`INV-SEMANTIC-011`, `INV-SEMANTIC-012`).
- [ ] `TableRelationship` completeness verified; no undocumented isolated entity (`INV-SEMANTIC-005`).
- [ ] Primary objects use verbatim identities and controlled roles (`INV-SEMANTIC-003`, `INV-SEMANTIC-007`).
- [ ] Consumable objects registered in `AccessObject` and composites recorded in `AccessComposition`; consumers resolve through the registry, not object names (`INV-SEMANTIC-008` to `INV-SEMANTIC-010`).
- [ ] Documentation capture completed, including `DD-DISCOVERY-001` when the orientation layer is deployed (see the orientation layer section for what it settles), and the ERD recipe `QC-SEMANTIC-002`.
- [ ] This document passes the design linter with no ignore directive.

---

### 11.1 Decisions to settle

These are the catalogued decisions a Semantic module design must settle. The recommendation is this standard's default; the question is what shifts it. The design skill walks a designer through each one at design time and records the answer in the product's own design.


| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-TIMESTAMP-ZONE` | `zone-aware` | Is the catalogue read across regions? |

---

## 12. Implementation

The Teradata binding (the catalogue and registry tables, the recursive path-discovery view, the live hybrid column catalogue, the orientation manifest and MCP resource shapes, and the validation queries) lives in [`implementation/teradata/modules/semantic/`](../../implementation/teradata/modules/semantic/). Other platforms add sibling directories under `implementation/` without changing this document.

---

**End of Semantic Module Design Standard**
