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
| **Implementations** | `implementation/{platform}/modules/semantic/`, one per platform |

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

Semantic's entities are the discovery catalogue. All apply `object-placement`, `access-layer` and `temporal-lifecycle-metadata`; all require `RichMetadata`. Every entity header states its temporal profile, because a `Record` has no default one. Semantic's entities hold today's meaning only and declare `CURRENT_STATE`; the audit columns that profile requires come from the temporal pattern and are not repeated below. All are standard-owned relations ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.1): the build creates them, and the organisation profile places and names them.

### 3.1 Catalogue

```
Entity: EntityMetadata            [kind: Record] [profile: CURRENT_STATE]
  entity_metadata_id: Identifier
  entity_name: ShortText [required]  // business name (Party, Product)
  logical_name: ShortText [required]  // the name the specification or owning standard writes (Ticket, ValidationRun)
  entity_description: Text [required]  // purpose and scope
  entity_kind: Enum{HISTORY|REFERENCE|RELATIONSHIP|KEYMAP|RECORD} [required]
  module_name: Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [required]
  container_name: ShortText [optional]  // where the table lives, from the build context
  table_name: ShortText [required]  // physical name
  view_name: ShortText [optional]  // physical name of the canonical consumable object
  surrogate_key_column: ShortText [optional]
  natural_key_column: ShortText [optional]
  temporal_pattern: Enum{CURRENT_STATE|EVENT_APPEND_ONLY|SCD2_HISTORY|SCD2_BITEMPORAL|ASSOCIATION_CURRENT|ASSOCIATION_SCD2|OPERATIONAL_LOG} [required]  // the declared temporal profile
  current_flag_column: ShortText [optional]  // physical name of the current flag
  deleted_flag_column: ShortText [optional]  // physical name of the deleted flag
  assumed_zone: ShortText [optional]  // IANA zone from the Product block; present only under zone-naive (TLM-18)
  industry_standard: ShortText [optional]  // FIBO, HL7, CUSTOM, …
  is_active: Flag

Entity: ColumnMetadata            [kind: Record] [profile: CURRENT_STATE]
  column_metadata_id: Identifier
  container_name: ShortText [required]
  table_name: ShortText [required]  // physical name of the relation the column belongs to: a table or a view
  column_name: ShortText [required]  // physical name
  logical_name: ShortText [required]  // the name the specification or owning standard writes (valid_from_dts)
  business_description: Text [optional]  // what the data represents
  is_pii: Flag  // set when sensitivity_marker is PII
  sensitivity_marker: Enum{PII|PII_INCIDENTAL} [optional]  // the specification's marker, absent when it carries none
  data_classification: ShortText [optional]  // the organisation's class, from the profile's Classification scheme
  is_required: Flag
  declared_type: ShortText [optional]  // the declared data type, as text
  allowed_values: Json [optional]  // permitted-value domain
  is_active: Flag

Entity: NamingStandard            [kind: Record] [profile: CURRENT_STATE]
  naming_standard_id: Identifier
  standard_type: Enum{TEMPLATE|STANDARD_NAME|ABBREVIATION|SUFFIX|PREFIX|PATTERN} [required]
  applies_to: Enum{TABLE|BASE_VIEW|CONSUMER_VIEW|PROCEDURE|FUNCTION|ATTRIBUTE|GRAPH_KEY|ALL} [optional]  // the object role or name a rule forms
  module_scope: Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [optional]  // the module a TEMPLATE is narrowed to, when it is
  kind_scope: Enum{HISTORY|REFERENCE|RELATIONSHIP|KEYMAP|RECORD} [optional]  // the entity kind a TEMPLATE is narrowed to, when it is
  name_template: ShortText [optional]  // the profile's template as written; present for TEMPLATE
  standard_value: ShortText [optional]  // the element a SUFFIX, PREFIX or PATTERN names, the logical name a STANDARD_NAME maps, or the module an ABBREVIATION shortens
  mapped_value: ShortText [optional]  // the physical name a STANDARD_NAME maps to, or the abbreviation
  meaning: Text [required]  // what the rule means
  is_active: Flag

Entity: TableRelationship         [kind: Record] [profile: CURRENT_STATE]
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

**Names are logical; the catalogue records both.** The specification and the standards name entities and attributes logically, and the organisation profile decides their physical names ([Organisation Profile Standard](../core/ORGANISATION_PROFILE.md) §6.3), including the physical name of any standard-owned logical name it maps. The build registers every relation and column under both: `logical_name` holds the name the specification or owning standard writes, and `table_name`, `view_name` and `column_name` hold the physical names. Canonical temporal and lifecycle columns and standard-owned relations are registered with their logical names, so a conformance rule written against a canonical name, such as the required columns of TLM-02, is judged by resolving that name through this metadata after the organisation's mapping, never by assuming the physical name.

**Naming rules are the organisation's.** `NamingStandard` is populated by the build from the organisation profile's `Naming:` block, never supplied by a designer. It records how the organisation forms names, its templates per object role, its standard-name mappings and its abbreviations, so a reader can understand a name. No agent derives a name from it: objects are read from the registry verbatim (`INV-SEMANTIC-003`).

**Sensitivity is recorded as the specification states it and as the organisation classes it.** `sensitivity_marker` holds the specification's `pii` or `pii-incidental` marker; `data_classification` holds the class the profile's `Classification:` block maps it to, or the profile's default class for an unmarked attribute.

### 3.2 Measures

An entity catalogue says what exists and a relationship catalogue says how it joins. Neither says what a number *means*: whether revenue is gross or net, whether a balance may be summed across time, which of four plausible readings of "active customer" the business settled on. A consumer that has to reconstruct that from a column name reconstructs it differently each time, and two consumers then disagree about a figure they both believe they took from the product.

Metrics are declared at model level rather than on an entity, because a metric may span several: a ratio over a fact and a dimension belongs to neither. `MetricDataset` records which entities a metric reads, so the entities a metric needs can be resolved without parsing its expression.

```
Entity: Metric                    [kind: Record] [profile: CURRENT_STATE]
  metric_id: Identifier
  metric_name: ShortText [required] [unique]  // business name (Total Sales, Churn Rate): the Metric block's name
  metric_description: Text [required]  // what it measures and what it excludes: the block's Description
  metric_definition: Text [required]  // the block's Measure, Filter and Joins, in the specification's expression vocabulary
  metric_datatype: Code [optional]  // declared result type
  aggregation_type: Enum{SUM|AVERAGE|COUNT|COUNT_DISTINCT|MIN|MAX|RATIO|DERIVED} [optional]  // the outermost aggregate of the Measure
  unit: ShortText [optional]  // currency code, percent, count, days: the block's Unit
  grain_description: Text [optional]  // the level the metric is defined at: the block's Grain
  is_additive: Flag  // may be summed across every dimension: the block's Additive
  is_active: Flag

Entity: MetricExpression          [kind: Record] [profile: CURRENT_STATE]
  metric_expression_id: Identifier
  metric_name: Reference [required] [-> Metric]
  sql_dialect: Code [required]  // the dialect this expression is written in
  expression_text: Text [required]  // the calculation, rendered by the binding
  is_active: Flag

Entity: MetricDataset             [kind: Record] [profile: CURRENT_STATE]
  metric_dataset_id: Identifier
  metric_name: Reference [required] [-> Metric]
  container_name: ShortText [optional]
  table_name: ShortText [required]  // an entity the expression reads: the block's Dataset or one of its Joins
  dataset_role: Enum{PRIMARY|JOINED} [required]  // PRIMARY for the Dataset, JOINED for each of the Joins
  is_active: Flag
```

**A metric is defined once, logically, and expressed once per dialect.** The design specification states each metric in a `Metric:` block ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.4), in the platform-neutral expression vocabulary of its §5, over declared entities and attributes: what is measured, how it aggregates, what it filters, and how component metrics combine. It never states SQL. Each platform binding renders that definition into its own dialect at build time and registers the result as a `MetricExpression`, and may register further dialects for consuming tools that push down their own SQL. The product's platform, a consuming tool and a catalogue that only displays the metric then share one definition rather than three that drift, and the same design builds on any platform.

**`is_additive` is a correctness flag, not documentation.** A consumer that sums a non-additive measure across time produces a number that is wrong rather than approximate, and nothing downstream can detect it. Declaring it is what lets a tool refuse.

### 3.3 Synonyms

```
Entity: SemanticSynonym           [kind: Record] [profile: CURRENT_STATE]
  synonym_id: Identifier
  synonym_object: Reference [required] [-> EntityMetadata | ColumnMetadata | Metric] [discriminator: object_kind]
  object_kind: Enum{ENTITYMETADATA|COLUMNMETADATA|METRIC} [required]  // which catalogue the synonym_object points into
  synonym_text: ShortText [required]  // the alternative term
  is_active: Flag
```

The terms a business uses are not the terms a schema uses, and the gap is where natural-language questions fail. A synonym set is separate from the glossary Memory holds: a glossary term is a definition a person reads, a synonym is an alias a resolver matches on. Synonyms come from the specification: an entity's `Synonyms:` section, an attribute's `[synonyms:]` qualifier and a metric's `Synonyms` field. Each points at the catalogue row it aliases, so a synonym resolves through metadata rather than by matching a name.

### 3.4 Registries and orientation

```
Entity: DataProductRegistry       [kind: Record] [profile: CURRENT_STATE]  // product-level orientation anchor
  product_id: NaturalKey [required]  // stable product identifier: the specification's product_code
  product_name: ShortText [required]  // the specification's product
  product_description: Text [required]  // Product block: Description
  product_domain: ShortText [required]  // Product block: Domain
  product_version: ShortText [required]  // recorded by the build, not the design
  product_status: Enum{DRAFT|ACTIVE|DEPRECATED|RETIRED} [required]  // recorded by the build, not the design
  owner_team: ShortText [required]  // Product block: Owner
  technical_contact: ShortText [optional]  // Product block: Technical contact
  trust_authoritative_producer: ShortText [required]  // Product block: Trust producer, read by the validation pattern
  manifest: Json [optional]  // machine-readable orientation manifest
  contract_uri: ShortText [optional]
  policy_uri: ShortText [optional]
  quality_uri: ShortText [optional]
  lineage_uri: ShortText [optional]
  approved_entrypoint: ShortText [required]  // Orientation block: Entrypoint, resolved by the build to the surface it names
  approved_access_mode: Enum{VIEW|MCP_TOOL|SEMANTIC_QUERY} [required]  // Orientation block: Access mode
  is_active: Flag
  is_deleted: Flag [deleted-flag]
  deleted_dts: Timestamp [optional]

Entity: DataProductMap            [kind: Record] [profile: CURRENT_STATE]  // module registry: one row per module and object type
  module_id: Identifier
  module_name: Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [required]
  object_type: Enum{TABLE|BASE_VIEW|CONSUMER_VIEW|PROCEDURE|FUNCTION} [required]  // the organisation profile's object role
  module_purpose: Text [optional]
  container_name: ShortText [required]  // where this module's objects of this type are placed, from the build context
  module_version: ShortText [optional]
  deployment_status: Enum{DEPLOYED|PLANNED|DEPRECATED} [required]
  graph_key: ShortText [optional]  // OBSERVABILITY rows only, when the graph-lineage facet is enabled; from the build context
  is_active: Flag

Entity: PrimaryObject             [kind: Record] [profile: CURRENT_STATE]  // one row per agent-facing object
  primary_object_id: Identifier
  module_id: Reference [required] [-> DataProductMap]  // the module and object-type row the object belongs to
  container_name: ShortText [required]  // the object's exact deployed container
  object_name: ShortText [required]  // exact deployed name; used verbatim, never derived
  object_type: Enum{TABLE|BASE_VIEW|CONSUMER_VIEW|PROCEDURE|FUNCTION} [required]  // the organisation profile's object role
  object_role: Enum{AGENT_ENTRYPOINT|ANALYTICAL_QUERY|REFERENCE_LOOKUP|RELATIONSHIP_BRIDGE|LINEAGE_EVIDENCE|OPERATIONAL_METRIC|WRITE_TARGET|INTERNAL_SUPPORT} [required]  // derived by the build
  usage_guidance: Text [optional]
  is_active: Flag

Entity: DataProductOrientation    [kind: Record] [profile: CURRENT_STATE]  // one ordered row per product resource
  orientation_id: Identifier
  product_id: NaturalKey [required]  // the product this resource belongs to (DataProductRegistry.product_id)
  resource_role: Enum{MANIFEST|TRUST_MAP|MODULE_MAP|OBJECT_CATALOGUE|ENTITY_CATALOGUE|COLUMN_CATALOGUE|RELATIONSHIP_CATALOGUE|RELATIONSHIP_PATHS|LINEAGE|QUERY_COOKBOOK|GLOSSARY|DESIGN_DECISIONS|POLICY|QUALITY} [required]  // open vocabulary; one role per row, never a list; TRUST_GATE is the legacy spelling of TRUST_MAP
  container_name: ShortText [optional]  // deployed container, for object-backed resources
  object_name: ShortText [optional]  // deployed object; used verbatim, never derived
  resource_uri: ShortText [optional]  // URI for an MCP or external resource, when not a database object
  usage_guidance: Text [optional]  // how a consumer should use this resource
  is_required: Flag  // a missing required resource is a conformance failure
  discovery_order: Integer [required]  // ascending processing order; the trust map precedes every analytical resource
  is_active: Flag
```

**Where registry facts come from.** The registry's descriptive facts come from the specification's `Product:` block ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.12): description, domain, owner, technical contact and trust producer. Its approved entrypoint and access mode come from the `Orientation:` block, which carries nothing else. Version and lifecycle status are the build's, never the design's.

**Containers are recorded per module and object type.** The organisation profile may route the object roles of one module to different containers, so a module may span several. `DataProductMap` holds one row per module and object type, and the build records each container from the build context. A consumer reads where an object lives from these rows or from the object's own registry row, never from a container name.

**Primary-object roles are derived.** The build assigns each `PrimaryObject.object_role` from the object's type and the kind of the entity behind it; a designer never assigns one. The first matching rule wins:

| Rule | Object | `object_role` |
|---|---|---|
| 1 | An object a tier is granted to append to under the [access-layer pattern](../patterns/access-layer.md) | `WRITE_TARGET` |
| 2 | Any other `TABLE`, `BASE_VIEW`, `PROCEDURE` or `FUNCTION` | `INTERNAL_SUPPORT` |
| 3 | The consumer view of the generated manifest, or of `DataProductRegistry` | `AGENT_ENTRYPOINT` |
| 4 | A consumer view over `DataLineage`, `LineageRun`, `LineageGraph` or `LineageRunLatest` | `LINEAGE_EVIDENCE` |
| 5 | A consumer view over any other Observability relation, including `ValidationRun` and `ValidationArea` | `OPERATIONAL_METRIC` |
| 6 | A consumer view over a `Reference` entity, or over a Semantic or Memory relation | `REFERENCE_LOOKUP` |
| 7 | A consumer view over a `Relationship` or `Keymap` entity | `RELATIONSHIP_BRIDGE` |
| 8 | Any other consumer view, including a composite access object | `ANALYTICAL_QUERY` |

Every relation the catalogue registers is defined in this standard or another; none is left to a platform. Which object exposes an entity, and of what type, is recorded by `AccessObject` (§3.5), so no separate view catalogue is needed.

### 3.5 Access-object layer

The catalogue above models entities and how they relate; it does not model the **access layer** — which objects a consumer actually queries. A platform security model may expose one entity through several objects (governed base, business, current views), and a product may publish composite ("enriched") objects that join several entities into one unit. `AccessObject` registers those facts so a consumer resolves any queryable object to its logical meaning **once, from metadata**, rather than reverse-engineering it from names or definitions. This is *access-layer metadata* — which objects represent what — distinct from the security [access-layer pattern](../patterns/access-layer.md), which governs who may read them.

```
Entity: AccessObject              [kind: Record] [profile: CURRENT_STATE]  // one row per consumable object
  access_object_id: Identifier
  container_name: ShortText [required]  // where the object is deployed
  object_name: ShortText [required]  // the queryable object
  object_type: Enum{TABLE|BASE_VIEW|CONSUMER_VIEW|PROCEDURE|FUNCTION} [required]  // the organisation profile's object role
  access_role: Enum{BASE|PASSTHROUGH|COMPOSITE} [required]  // open vocabulary; extensions add roles
  represents_entity: ShortText [optional]  // entity this exposes (EntityMetadata.entity_name); null for cross-entity composites
  object_grain: ShortText [optional]  // plain-language grain, e.g. one row per call
  is_agent_consumable: Flag  // whether an agent should query this object directly
  is_primary: Flag  // the canonical consumable object for its entity; at most one per entity
  resolves_to_object: ShortText [optional]  // for 1:1 passthroughs, the object it maps straight through to
  access_note: Text [optional]  // governance, filtering, or usage guidance
  is_active: Flag

Entity: AccessComposition         [kind: Record] [profile: CURRENT_STATE]  // one row per member of a COMPOSITE object
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

**Establishment and ownership (normative).** This metadata is **established once at deployment** by a registration step, defined here by responsibility rather than by tool. The step classifies objects from **verifiable structure** — the dependency graph and object definitions — not from names, and asserts the result in the registry; consumers read it and never recompute it. The concrete role vocabulary beyond the small open baseline, the physical realisation, and the population step are platform concerns (implementation). `AccessObject` is authoritative for object multiplicity per entity and is the module's view catalogue; `EntityMetadata.view_name` is retained as the denormalised pointer to the row marked `is_primary`. A composite comes from the specification's `AccessObject:` block; single-entity objects are registered without one.

---

## 4. Data Product Orientation Layer

Discovery is **product-first, not tables-first** (`INV-SEMANTIC-004`). A client must not begin by guessing containers or listing tables; it orients to the product, then navigates.

**Metadata-first handshake:**

1. The client locates the product through the organisation's catalogue ([catalogue-interface pattern](../patterns/catalogue-interface.md)), which points at the product's discovery entry point, and reads `DataProductRegistry` there. It never derives the entry point from a naming convention.
2. It reads the selected product's **manifest**.
3. The manifest recommends navigation: contract → semantic model → policy → quality → lineage → approved data access.
4. It queries data **only** through the approved entrypoint.

Where the product is reached over MCP, the orientation layer is exposed as **resources first** (the product list, per-product manifest, contract, semantic model, policy, quality, lineage, physical map) and **tools second** (search products, describe a product, get the recommended entrypoint, query approved data, explain an access path). The registry also designates the **trust-authoritative producer** the [validation pattern](../patterns/validation.md) reads, taken from the `Product:` block's `Trust producer`, and its `manifest` records the entrypoints and recommended navigation.

**The orientation relation (normative).** The handshake above is backed by a queryable, ordered relation, `DataProductOrientation` — one row per product resource, its `resource_role`, where it lives, whether it is required, and the `discovery_order` to process it — so a consumer reads the sequence rather than knowing repository conventions or inventing one, and a validator can *check* it. The baseline required roles a conformant product publishes, in canonical order, are: `MANIFEST`, `TRUST_MAP`, `MODULE_MAP`, `OBJECT_CATALOGUE`, `ENTITY_CATALOGUE`, `COLUMN_CATALOGUE`, `RELATIONSHIP_CATALOGUE`; `RELATIONSHIP_PATHS`, `LINEAGE`, `QUERY_COOKBOOK`, `GLOSSARY`, `DESIGN_DECISIONS` are optional, and `POLICY` / `QUALITY` are published where they apply. The vocabulary is open: an extension may add roles.

**Consumption contract (normative).** A consumer processes resources in ascending `discovery_order`; reads the `TRUST_MAP` resource **before** any analytical resource, and carries the confidence it found there into what it reports (the [validation pattern](../patterns/validation.md)); resolves every `is_required` resource, treating a missing one as a conformance failure; and uses the stored `container.object` (or `resource_uri`) **verbatim**, never deriving object names from conventions (`INV-SEMANTIC-011`).

**The manifest is generated, not authored (normative).** The machine-readable manifest is a **view derived** from `DataProductRegistry` and `DataProductOrientation` — it pivots the ordered resources into named entrypoint columns — so it cannot drift from the metadata it summarises (`INV-SEMANTIC-012`). The registry's serialised `manifest` remains the whole-document form for clients that want it in one read, regenerated from the same authoritative metadata rather than hand-authored to diverge.

**`DD-DISCOVERY-001`.** The specification's `Orientation:` block ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.6) settles one question: *how does an agent that knows only the product's name reach data it is allowed to use?* It states the approved entrypoint and access mode, and a `Decision:` block, `DD-DISCOVERY-001`, records why; the module part of a decision id names the module or concern it belongs to, here discovery. The record explains the choice of entrypoint and access mode and the navigation the manifest recommends. What makes it worth recording rather than inferring is that the answer is a set of choices the deployed metadata cannot explain about itself: an agent can read that an entrypoint is approved, not why that surface was chosen as the approved one, nor what an agent arriving without a product name is expected to do.

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

**Access-resolved paths.** The path-discovery surface is the logical, entity-level truth, and its joins are expressed against base tables. Where a platform exposes a separate consumable layer (§3.5), those joins point at objects an agent may not query, or at the wrong grain. An **access-resolved** surface rewrites each path endpoint to the entity's canonical consumable object — the agent-consumable `AccessObject`, collapsing any `resolves_to_object` chain — so an agent receives joins written against objects it can actually query. What it contains is normative; whether it is persisted as a view or a refreshed table is a platform decision (implementation). A path whose endpoint entity has no consumable object is omitted, not emitted against a base table.

---

## 6. Agent Discovery

The discovery order realises [Master](../core/MASTER_DESIGN.md):

1. **Product**: locate the product's discovery entry point through the organisation's catalogue ([catalogue-interface pattern](../patterns/catalogue-interface.md)), never by a naming convention; read `DataProductRegistry` / the manifest (orientation).
2. **Module**: read `DataProductMap` for deployed modules and the containers each of their object types occupies.
3. **Object**, read `PrimaryObject` for each module's entrypoints by `object_role`, using the stored `container.object` **verbatim**, never deriving names from conventions.
4. **Entity / attribute**: read `EntityMetadata` / the column catalogue.
5. **Relationship**: read the path-discovery surface to join.

A live **column catalogue** joins the deployed structural facts to the curated `ColumnMetadata`, carrying the **provenance** of every resolved value (declared-type source, description source, documentation coverage) so consumers see a complete schema without the curated store copying structural facts. Its construction is platform-specific (implementation).

Before emitting a query, an agent resolves the object to read through `AccessObject` (§3.5): it selects an agent-consumable object for the entity, expands any `COMPOSITE` from `AccessComposition`, and takes join targets from the access-resolved paths — so it queries the objects the product intends, at the right grain, without inferring anything from a name.

---

## 7. Applied Patterns

| Pattern | Contribution to Semantic |
|---------|--------------------------|
| `object-placement` | The organisation profile places the catalogue and its views; this module dictates no placement. |
| `access-layer` | Consumers are granted read on Semantic's objects in Phase 1.5b, at the grant level the organisation profile sets: the minimum grant that makes a product discoverable. |
| `temporal-lifecycle-metadata` | Every catalogue entity declares its profile in its header; `EntityMetadata.temporal_pattern` *carries* each entity's profile for the whole product, and `ColumnMetadata.logical_name` lets the pattern's rules resolve canonical columns through the organisation's name mapping. |
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

- **Every module → Semantic**: on deploy, each module registers its primary objects so agents can discover them. Soft in both directions: a composition without Semantic simply has no discovery map, so the organisation's catalogue entry points at the product's objects directly and discovery degrades to `RichMetadata` on them.
- **Domain → Semantic**. Semantic describes Domain entities and their relationships; it holds no copy of their content, and resolves a catalogue entry to its entity by joining back.
- **Observability → Semantic**: the lineage discovery views, logically `LineageGraph` and `LineageRunLatest`, are standard-owned relations placed by the organisation profile and registered here, so lineage is discoverable alongside the structure it describes. An organisation may route them alongside Semantic's relations so agents find them in one place; their names are logical and may be mapped.
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
- `INV-SEMANTIC-007`: primary-object roles come from the controlled vocabulary and are derived by the build by the rule in §3.4, never assigned by hand; at most one primary exposure per entity.
- `INV-SEMANTIC-008`: a consumer resolves the object to query through `AccessObject` (an agent-consumable object), never by inferring an object's role, layer, or entity from its name; the registry is the single source of truth and is established once at deployment from verifiable structure.
- `INV-SEMANTIC-009`: every `AccessObject.represents_entity` and every `AccessComposition.member_entity` resolves to a catalogued `EntityMetadata` entity; a non-`COMPOSITE` consumable object names the entity it represents.
- `INV-SEMANTIC-010`: a `COMPOSITE` object's structure is recorded in `AccessComposition` with exactly one `ANCHOR` member, and is expanded as a unit from that metadata, never by parsing the object's definition.
- `INV-SEMANTIC-011`: the orientation relation lists the required baseline resources, one row per role, in ascending `discovery_order` with the trust map ordered before every analytical resource; consumers use stored identities verbatim, and a missing required resource is a conformance failure.
- `INV-SEMANTIC-012`: the machine-readable manifest is generated from the registry and orientation relation (a derived view), never hand-authored, so it cannot drift from its sources.
- `INV-SEMANTIC-013`: every registered metric carries a platform-neutral definition and at least one expression derived from it, each in a declared dialect, and no two expressions of one metric declare the same dialect.
- `INV-SEMANTIC-014`: every dataset a metric names is an entity registered in the same product, and every metric names exactly one dataset in the primary role.
- `INV-SEMANTIC-015`: every synonym resolves to a registered entity, column or metric; a synonym is unique within the object it resolves to.

---

## 11. Designer Responsibilities

**Designers supply**, in the design specification: the entities, attributes and relationships of every module, from which the build registers the catalogue; the temporal profile per entity, in its header; the `Product:` block (description, domain, owner, technical contact, the trust-authoritative producer the [validation pattern](../patterns/validation.md) reads, and the assumed zone when timestamps are zone-naive); the `Orientation:` block (approved entrypoint and access mode); the metrics the product publishes, as `Metric:` blocks with an additivity declaration (dialect expressions are generated by the platform binding, never written by the designer); composite access objects, as `AccessObject:` blocks; synonyms for the terms consumers use.

**The build supplies**, never the designer: the product version and lifecycle status; every container, physical name and logical-to-physical name mapping, from the build context; `NamingStandard`, from the organisation profile's `Naming:` block; the module map; primary objects and their roles, by the derivation in §3.4; and the dialect expressions of every metric.

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] The specification carries the `Product:` and `Orientation:` blocks ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.1, §4.6, §4.12).
- [ ] Entities, columns, relationships, and primary objects registered for every deployed module (`SemanticRegistration`), each relation and column under its logical and physical names.
- [ ] Each entity declares its temporal profile (`INV-SEMANTIC-006`).
- [ ] The product registry and manifest are populated; discovery is product-first (`INV-SEMANTIC-004`).
- [ ] The `Product:` block names the trust producer, carried into the registry and manifest as `trust_authoritative_producer` per the [validation pattern](../patterns/validation.md). A product with one producer still names it.
- [ ] The orientation relation publishes the required baseline resources in `discovery_order` with the trust map first, and the manifest is a generated view over registry + orientation (`INV-SEMANTIC-011`, `INV-SEMANTIC-012`).
- [ ] `TableRelationship` completeness verified; no undocumented isolated entity (`INV-SEMANTIC-005`).
- [ ] Primary objects use verbatim identities and derived, controlled roles (`INV-SEMANTIC-003`, `INV-SEMANTIC-007`).
- [ ] Consumable objects registered in `AccessObject` and composites recorded in `AccessComposition`; consumers resolve through the registry, not object names (`INV-SEMANTIC-008` to `INV-SEMANTIC-010`).
- [ ] Every published metric carries a platform-neutral definition, a primary dataset, and an additivity declaration, with its dialect expressions generated from the definition (`INV-SEMANTIC-013`, `INV-SEMANTIC-014`).
- [ ] Synonyms resolve to registered objects (`INV-SEMANTIC-015`).
- [ ] Documentation capture completed, including `DD-DISCOVERY-001` when the orientation layer is deployed (see the orientation layer section for what it settles), and the ERD recipe `QC-SEMANTIC-002`.
- [ ] This document passes the design linter with no ignore directive.

---

### 11.1 Decisions to settle

These are the catalogued decisions a Semantic module design must settle. The recommendation is this standard's default; the question is what shifts it. The design skill walks a designer through each one at design time and records the answer in the design specification.


| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-TIMESTAMP-ZONE` | `zone-aware` | Is the catalogue read across regions? |

---

## 12. Implementation

Each platform binding provides the catalogue and registry tables, the path-discovery and access-resolved surfaces, the live hybrid column catalogue, the orientation manifest and MCP resource shapes, and the validation queries, in `implementation/{platform}/modules/semantic/`, and conforms to the [Platform Implementation Authoring Standard](../core/IMPLEMENTATION_AUTHORING.md). Adding a platform changes nothing in this document.

---

**End of Semantic Module Design Standard**
