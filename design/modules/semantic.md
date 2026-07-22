# Semantic Module — Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Semantic module — knowledge and meaning; the discovery map agents navigate |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/modules/semantic/`](../../implementation/teradata/modules/semantic/) |

Semantic is the module that **provides `SemanticRegistration`** and the discovery map every other
module and pattern points at: the entity/column catalogue, the relationship graph, the module and
primary-object registries, and the product orientation layer. It is the map that makes
[Master §6 agent discovery](../core/MASTER_DESIGN.md) possible.

---

## 1. Purpose

Semantic helps an agent generate correct queries by answering, from queryable metadata rather than
inference:

1. What products exist, and how do I orient to one?
2. What modules are deployed, and where?
3. What entities (tables) exist, and what attributes (columns) do they have?
4. How do entities relate — and how do I join A to B, including multi-hop?

**Key terminology:** an **entity** is a table, an **attribute** is a column, a **relationship** is
how tables join. The catalogue registers *objects*, never rows.

---

## 2. Scope and Boundaries

**In scope:** schema metadata — hundreds of rows describing entities, attributes, relationships,
naming standards, module locations, primary objects, and product orientation.

**Out of scope:** instance data (millions of rows → Domain and the other modules); business content;
individual records. Semantic stores *what exists and how it connects*, never the data itself
(`INV-SEMANTIC-001`).

**Boundary with Memory's documentation facet:** Semantic stores *what exists and how it connects*;
Memory's design memory stores *why it exists, how to use it, and what changed*. They must not
duplicate each other.

---

## 3. The Discovery Map — Entity Model

Semantic's entities are the discovery catalogue. All apply `object-placement` and `access-layer`;
those that are versioned apply `temporal-lifecycle-metadata`; all require `RichMetadata`.

### 3.1 Catalogue

```
Entity: EntityMetadata            [kind: Record]
  entity_metadata_id  : Identifier
  entity_name         : ShortText [required]              — business name (Party, Product)
  entity_description  : Text [required]                   — purpose and scope
  module_name         : Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [required]
  container_name      : ShortText [optional]              — where the table lives
  table_name          : ShortText [required]
  view_name           : ShortText [optional]              — the standard current view
  surrogate_key_column: ShortText [optional]
  natural_key_column  : ShortText [optional]
  temporal_pattern    : ShortText [required]              — the temporal-lifecycle profile (CURRENT_STATE, SCD2_HISTORY, EVENT_APPEND_ONLY, …)
  current_flag_column : ShortText [optional]              — names the current-flag (temporal §6)
  deleted_flag_column : ShortText [optional]
  industry_standard   : ShortText [optional]              — FIBO, HL7, CUSTOM, …
  is_active           : Flag

Entity: ColumnMetadata            [kind: Record]
  column_metadata_id  : Identifier
  container_name      : ShortText [required]
  table_name          : ShortText [required]
  column_name         : ShortText [required]
  business_description : Text [optional]                  — what the data represents
  is_pii              : Flag
  is_sensitive        : Flag
  data_classification : Enum{PUBLIC|INTERNAL|CONFIDENTIAL|RESTRICTED} [optional]
  is_required         : Flag
  declared_type       : ShortText [optional]              — the declared data type, as text
  allowed_values      : Json [optional]                   — permitted-value domain
  is_active           : Flag

Entity: NamingStandard            [kind: Record]
  naming_standard_id : Identifier
  standard_type      : Enum{SUFFIX|PREFIX|PATTERN|ABBREVIATION} [required]
  standard_value     : ShortText [required]               — e.g. _H, _id, is_, dts
  meaning            : Text [required]                    — what the element means
  applies_to         : Enum{TABLE|COLUMN|VIEW|ALL} [optional]
  is_active          : Flag

Entity: TableRelationship         [kind: Record]
  relationship_id     : Identifier
  relationship_name   : ShortText [required]
  source_container    : ShortText [optional]
  source_table        : ShortText [required]
  source_column       : ShortText [required]              — the referencing (foreign) key
  target_container    : ShortText [optional]
  target_table        : ShortText [required]
  target_column       : ShortText [required]              — the referenced key
  relationship_type   : Enum{FOREIGN_KEY|HIERARCHY|ASSOCIATIVE} [required]
  cardinality         : Enum{ONE_TO_ONE|ONE_TO_MANY|MANY_TO_ONE|MANY_TO_MANY} [optional]
  is_mandatory        : Flag
  is_active           : Flag
```

### 3.2 Registries and orientation

```
Entity: DataProductRegistry       [kind: Record]         — product-level orientation anchor
  product_id            : NaturalKey [required]           — stable product identifier
  product_name          : ShortText [required]
  product_version       : ShortText [required]
  product_status        : Enum{DRAFT|ACTIVE|DEPRECATED|RETIRED} [required]
  owner_team            : ShortText [optional]
  semantic_container    : ShortText [optional]            — where to look after registry discovery
  memory_container      : ShortText [optional]
  observability_container : ShortText [optional]
  manifest              : Json [optional]                 — machine-readable orientation manifest
  contract_uri          : ShortText [optional]
  policy_uri            : ShortText [optional]
  quality_uri           : ShortText [optional]
  lineage_uri           : ShortText [optional]
  approved_entrypoint   : ShortText [optional]            — approved first data-access surface
  approved_access_mode  : Enum{VIEW|MCP_TOOL|SEMANTIC_QUERY} [optional]
  is_active             : Flag
  is_deleted            : Flag [deleted-flag]

Entity: DataProductMap            [kind: Record]         — module registry
  module_id          : Identifier
  module_name        : Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [required]
  module_purpose     : Text [optional]
  container_name     : ShortText [required]               — where the module is deployed (critical for discovery)
  module_version     : ShortText [optional]
  deployment_status  : Enum{DEPLOYED|PLANNED|DEPRECATED} [required]
  is_active          : Flag

Entity: PrimaryObject             [kind: Record]         — one row per agent-facing object
  primary_object_id : Identifier
  module_id         : Reference [required] [-> DataProductMap]
  container_name    : ShortText [required]                — the object's exact deployed container
  object_name       : ShortText [required]                — exact deployed name; used verbatim, never derived
  object_type       : Enum{TABLE|VIEW|PROCEDURE|FUNCTION} [required]
  object_role       : Enum{AGENT_ENTRYPOINT|ANALYTICAL_QUERY|REFERENCE_LOOKUP|RELATIONSHIP_BRIDGE|LINEAGE_EVIDENCE|OPERATIONAL_METRIC|WRITE_TARGET|INTERNAL_SUPPORT} [required]
  usage_guidance    : Text [optional]
  is_active         : Flag
```

`ViewMetadata` (one row per base-table exposure, with a `view_type` and a single primary exposure per
base table) and `ViewColumnType` (curated types for view columns) complete the catalogue; both are
platform-detail-heavy and specified in the implementation.

---

## 4. Data Product Orientation Layer

Discovery is **product-first, not tables-first** (`INV-SEMANTIC-004`). A client must not begin by
guessing containers or listing tables; it orients to the product, then navigates.

**Metadata-first handshake:**

1. The client asks what products are available → reads `DataProductRegistry`.
2. It reads the selected product's **manifest**.
3. The manifest recommends navigation: contract → semantic model → policy → quality → lineage →
   approved data access.
4. It queries data **only** through the approved entrypoint.

Where the product is reached over MCP, the orientation layer is exposed as **resources first** (the
product list, per-product manifest, contract, semantic model, policy, quality, lineage, physical
map) and **tools second** (search products, describe a product, get the recommended entrypoint,
query approved data, explain an access path). The registry also designates the
**gate-authoritative producer** the [validation pattern](../patterns/validation.md) reads, and its
`manifest` records the entrypoints and recommended navigation.

---

## 5. Multi-Hop Path Discovery

`TableRelationship` is the machine-readable entity-relationship model. From it, a **path-discovery
surface** lets an agent find how to join any two entities — directly or through intermediate
entities, in either direction, up to a bounded number of hops — and returns the join conditions to
use. This is the single most important discovery capability: an agent cannot traverse a path it has
no record of.

**Completeness requirement (`INV-SEMANTIC-005`).** `TableRelationship` must register **every**
relationship an agent is expected to traverse — not only those with physical foreign keys:

| Category | Common omission |
|----------|-----------------|
| Intra-module keys (child → parent, entity → keymap) | Child-to-parent within an entity cluster |
| Reference lookups (entity → reference set) | Reference decodes, especially from append-only tables |
| Cross-module joins (Domain → Search / Prediction) | Joins between modules |
| Multi-hop semantic chains | Chains used in lineage and audit |
| Reverse directions | Bidirectional traversal needs |

An entity that appears in `EntityMetadata` but in no `TableRelationship` is either a *documented*
standalone (recorded as a design decision) or an omission that will cause agent navigation failures.

---

## 6. Agent Discovery

The discovery order realises [Master §6](../core/MASTER_DESIGN.md):

1. **Product** — read `DataProductRegistry` / the manifest (orientation).
2. **Module** — read `DataProductMap` for deployed modules and their containers.
3. **Object** — read `PrimaryObject` for each module's entrypoints by `object_role`, using the stored
   `container.object` **verbatim** — never deriving names from conventions.
4. **Entity / attribute** — read `EntityMetadata` / the column catalogue.
5. **Relationship** — read the path-discovery surface to join.

A live **column catalogue** joins the deployed structural facts to the curated `ColumnMetadata`,
carrying the **provenance** of every resolved value (declared-type source, description source,
documentation coverage) so consumers see a complete schema without the curated store copying
structural facts. Its construction is platform-specific (implementation).

---

## 7. Applied Patterns

| Pattern | Contribution to Semantic |
|---------|--------------------------|
| `object-placement` | Which container the catalogue and views live in, and who may reach them. |
| `access-layer` | Consumers read the Semantic container in Phase 1.5 — the minimum grant that makes a product discoverable. |
| `temporal-lifecycle-metadata` | Versioned catalogue entities follow a declared profile; `EntityMetadata.temporal_pattern` *carries* each entity's profile for the whole product. |
| `validation` | Its primary-object, view, and relationship-completeness checks are canonical STRUCTURAL/SEMANTIC validator checks. |

---

## 8. Capabilities and Composition

Semantic is **cross-cutting and soft**: nothing hard-depends on it (modules register *when it is
present*), and it hard-depends on nothing — it describes whatever modules are in the composition. It
is present in a traditional data product and an AI-native product, absent in a minimal Data Asset.
See the [composition mechanism](../core/DESIGN_LANGUAGE.md#62-provision-requirement-and-composition).

**Provides:**

| Capability | Made available to |
|------------|-------------------|
| `SemanticRegistration` | Every module — the target where entities, columns, relationships, and primary objects are registered on deploy. |
| Agent discovery (product / module / entity / relationship) | Agents, as the map they navigate. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on every catalogue object. |
| `DocumentationCapture` | `[soft]` | `module:Memory` | Record Semantic's own design decisions when Memory is present. |
| `EntityJoinBack` | `[soft]` | `module:Domain` | Describe Domain entities; catalogue reads reference them. |

---

## 9. Invariants

- `INV-SEMANTIC-001`: Semantic stores schema metadata only — entities, attributes, relationships, orientation; never instance data or business content.
- `INV-SEMANTIC-002`: the catalogue registers objects (entity = table, attribute = column, relationship = join), never rows.
- `INV-SEMANTIC-003`: every deployed module and its primary objects are registered; agents obtain objects by the stored fully-qualified identity, never by deriving names from conventions.
- `INV-SEMANTIC-004`: discovery is product-first — clients read the product registry/manifest before module maps or data (the orientation contract).
- `INV-SEMANTIC-005`: `TableRelationship` registers every relationship an agent is expected to traverse; an unrelated entity is a documented standalone or an omission.
- `INV-SEMANTIC-006`: every entity declares its temporal profile in `EntityMetadata.temporal_pattern`, so validators resolve temporal behaviour from metadata (temporal pattern §6).
- `INV-SEMANTIC-007`: primary-object roles come from the controlled vocabulary; at most one primary exposure per base table.

---

## 10. Designer Responsibilities

**Designers supply:** the entity/column/relationship catalogue for every module; naming standards;
the module map and primary objects with their roles; the product registry and manifest; the temporal
profile per entity.

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Entities, columns, relationships, and primary objects registered for every deployed module (`SemanticRegistration`).
- [ ] Each entity declares its temporal profile (`INV-SEMANTIC-006`).
- [ ] The product registry and manifest are populated; discovery is product-first (`INV-SEMANTIC-004`).
- [ ] `TableRelationship` completeness verified; no undocumented isolated entity (`INV-SEMANTIC-005`).
- [ ] Primary objects use verbatim identities and controlled roles (`INV-SEMANTIC-003`, `INV-SEMANTIC-007`).
- [ ] Documentation capture completed, including `DD-DISCOVERY-001` when the orientation layer is deployed, and the ERD recipe `QC-SEMANTIC-002`.
- [ ] This document passes the design linter with no ignore directive.

---

## 11. Implementation

The Teradata binding — the catalogue and registry tables, the recursive path-discovery view, the
live hybrid column catalogue, the orientation manifest / MCP resource shapes, and the validation
queries — lives in
[`implementation/teradata/modules/semantic/`](../../implementation/teradata/modules/semantic/).
Other platforms add sibling directories under `implementation/` without changing this document.

---

**End of Semantic Module Design Standard**
