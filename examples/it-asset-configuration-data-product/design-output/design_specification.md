---
product: IT Asset Configuration
product_code: CMDB
composition: traditional-data-product
modules:
  - domain
  - semantic
  - observability
  - memory
facets:
  - memory:documentation
decisions:
  - id: DEC-TIMESTAMP-ZONE
    choice: zone-aware
  - id: DEC-TEMPORAL-PATTERN
    choice: scd2
    because: no model reads this product's history, so no feature needs transaction time; corrections to an item's record are rare and are made as new versions; business validity alone answers "what was this item's state on a date", which is the question asset and impact analysis asks
  - id: DEC-COLUMN-STRATEGY
    choice: offload
  - id: DEC-SURROGATE-ALLOCATION
    choice: keymap
  - id: DEC-DELETE-STRATEGY
    choice: soft-delete
  - id: DEC-QUALITY-STORAGE
    choice: observability
  - id: DEC-AUDIT-RETENTION
    choice: regulatory
---

# IT Asset Configuration: Design Specification

The design phase's output for the IT Asset Configuration example, produced from
[`CMDB_Reference_Brief.md`](../CMDB_Reference_Brief.md) and the source data in
[`data/`](../data/). It is the build input: every fact a builder needs is in the frontmatter
or a notation block defined by the
[Design Specification Standard](../../../design/core/DESIGN_SPECIFICATION.md), and it names no
platform, container or principal, so it builds on any conforming platform under any
organisation profile. Prose explains; it is never the only statement of a fact.

This is reference output, kept so implementations can be compared. Validate it with:

```bash
python tooling/evals/spec_lint.py examples/it-asset-configuration-data-product/design-output/design_specification.md
```

---

## Business purpose

```
Product: -
  Description:       The register of configuration items the service provider manages, how they depend on one another, and which service desk tickets affected them.
  Domain:            IT asset and configuration management
  Owner:             Infrastructure operations
  Technical contact: Configuration management team
  Trust producer:    the configuration register validation pipeline, run by the configuration manager
```

The configuration register for every item the service provider manages: customers' devices,
business applications and the servers they run on, and the shared platforms (identity, email,
host clusters, network) that many customers depend on at once. It answers what an item is,
where it is, who owns it, when it falls out of support, what depends on it, and which service
desk tickets it was involved in.

**Consumers:** infrastructure engineers (impact analysis before a change or during an outage);
asset managers (refresh planning, end-of-support exposure, asset cost); service desk agents and
AI agents (finding the item behind a ticket and what else it affects); analysts joining asset
age and criticality to ticket outcomes.

**Use cases:** list everything that depends, directly or transitively, on an item; find the
items past or near end of support, by customer and criticality; report asset cost and counts by
type, location and customer; find the items a ticket affected and the tickets an item was
involved in; monitor register quality (missing support dates, duplicate serial numbers,
dangling dependencies).

## Composition

The Traditional Data Product composition: Domain, Semantic, Observability and the Memory
documentation facet, with the access layer. No module hard-requires anything outside it.
Search and Prediction are absent, so the product has no similarity search and no model
features; Memory's runtime facet is absent, so agents keep no session state in the product.
Each is an absence by design, recorded in `DD-DOMAIN-006`.

---

## Domain

Six business entities. `ConfigurationItem` is the one `History` entity, on the `SCD2_HISTORY`
profile the product's `scd2` choice makes the default, with keymap allocation. `ItemType` and
`Location` are `Reference` entities on their kind's default profile, allocated inline.
`ItemDependency` and `AffectedItem` are `Relationship` entities.

Two references point outside the product. An item's owning customer and a ticket an item was
involved in are entities of the IT Service Desk product. The design language has no notation
for a reference to another product's entity, so both are held as that product's natural keys,
`customer_key` and `ticket_key`, in `ShortText` attributes the product does not enforce
(`DD-DOMAIN-004`).

```
Entity: ConfigurationItem         [kind: History] [profile: SCD2_HISTORY]
  configuration_item_id : Identifier                          // surrogate; stable across all versions
  item_type_id          : Reference [required] [-> ItemType]  // what kind of item this is
  location_id           : Reference [optional] [-> Location]  // where the item is; absent for an item with no fixed place
  name                  : ShortText [required]                // display name
  customer_key          : ShortText [optional]                // owning customer, as the IT Service Desk product's customer number (CUST-nnn); absent for a shared provider platform
  environment           : Enum{Production|Test|Development} [required]  // the environment the item serves
  lifecycle_status      : Enum{Planned|Live|Maintenance|Retired} [required]  // where the item is in its life
  criticality           : Enum{Critical|High|Medium|Low} [required]  // business impact if the item fails
  support_team          : ShortText [required]                // team that supports it: Infrastructure, Applications or Service Desk
  manufacturer          : ShortText [optional]                // vendor or publisher
  model_name            : ShortText [optional]                // product model or edition
  serial_number         : ShortText [optional]                // manufacturer serial number; hardware only
  purchase_date         : Date [optional]                     // date bought; hardware only
  warranty_end_date     : Date [optional]                     // last day of manufacturer warranty
  end_of_support_date   : Date [optional]                     // last day the vendor supports the item
  purchase_cost         : Decimal(12,2) [optional]            // purchase price, in Australian dollars
  last_discovered_dts   : Timestamp [required]                // when discovery last saw the item
  is_current            : Flag [current-flag]                 // current version marker
  is_deleted            : Flag [deleted-flag]                 // soft-delete marker

  Description: Anything the provider manages that a service depends on: a device, a server, a network device, an application or a platform service.

  Keys:
    surrogate: configuration_item_id

  Volume:
    initial: 235
    growth:  15 per month
    horizon: 5 years

  Synonyms: CI, asset, configuration item

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - SurrogateKeyAllocation
    - CurrentStateFilter
    - PointInTimeReconstruction
    - NaturalKeyLookup
    - EntityJoinBack
    - RichMetadata
```

```
Entity: ItemType                    [kind: Reference] [profile: SCD2_HISTORY] [allocation: inline]
  item_type_id        : Identifier                          // surrogate for the entry
  item_type_code      : Code [required] [unique]            // type code used by the register, CIT-*; the natural key
  short_description : ShortText [required]                // label for reports
  long_description  : Text [optional]                     // what items of this type are
  ci_class          : Enum{Hardware|Infrastructure|Network|Software|Service} [required]  // the broad class
  parent_item_type_id : Reference [optional] [-> ItemType]    // parent type; absent for a top-level type
  is_current        : Flag [current-flag]                 // marks the current version of the code

  Description: The two-level taxonomy configuration items are classified by.

  Keys:
    surrogate: item_type_id
    natural:   item_type_code

  Volume:
    initial: 17
    growth:  2 per year
    horizon: 5 years

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - CurrentStateFilter
    - PointInTimeReconstruction
    - RichMetadata
```

```
Entity: Location                  [kind: Reference] [profile: SCD2_HISTORY] [allocation: inline]
  location_id       : Identifier                          // surrogate for the entry
  location_code     : Code [required] [unique]            // site code, LOC-*; the natural key
  short_description : ShortText [required]                // site name
  city              : ShortText [required]                // city
  country           : ShortText [required]                // country
  region            : ShortText [required]                // trading region, as the service desk names it: ANZ or APAC
  location_type     : Enum{Datacentre|Office|Cloud} [required]  // what kind of site
  is_current        : Flag [current-flag]                 // marks the current version of the entry

  Description: A datacentre, cloud region or office where configuration items are.

  Keys:
    surrogate: location_id
    natural:   location_code

  Volume:
    initial: 11
    growth:  2 per year
    horizon: 5 years

  Synonyms: site

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - CurrentStateFilter
    - PointInTimeReconstruction
    - RichMetadata
```

```
Entity: ItemDependency            [kind: Relationship] [profile: ASSOCIATION_SCD2] [allocation: inline]
  item_dependency_id : Identifier                         // surrogate for the dependency
  dependent_item_id  : Reference [required] [-> ConfigurationItem] [join: dependent]  // the item that depends
  supporting_item_id : Reference [required] [-> ConfigurationItem] [join: supporting]  // the item it depends on
  dependency_type    : Enum{DependsOn|RunsOn|HostedOn|ConnectsThrough} [required]  // how it depends
  established_date   : Date [optional]                    // first day the dependency was in place
  is_current         : Flag [current-flag]                // current version marker
  is_deleted         : Flag [deleted-flag]                // soft-delete marker

  Description: One configuration item depending on another: an application on its server, a server on its host, a device on a gateway.

  Keys:
    surrogate: item_dependency_id
    natural:   dependent_item_id, supporting_item_id, dependency_type

  Volume:
    initial: 300
    growth:  20 per month
    horizon: 5 years

  Synonyms: dependency, CI relationship, upstream, downstream

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - CurrentStateFilter
    - EntityJoinBack
    - RichMetadata
```

```
Entity: AffectedItem              [kind: Relationship] [profile: ASSOCIATION_SCD2] [allocation: inline]
  affected_item_id      : Identifier                          // surrogate for the link
  configuration_item_id : Reference [required] [-> ConfigurationItem]  // the item the ticket affected
  ticket_key            : ShortText [required]                // the ticket, as the IT Service Desk product's ticket number (TKT-nnnnn)
  impact                : Enum{Primary|Secondary} [required]  // Primary for the item at fault, Secondary for an item affected through it
  linked_dts            : Timestamp [required]                // when the link was recorded
  is_current            : Flag [current-flag]                 // current version marker
  is_deleted            : Flag [deleted-flag]                 // soft-delete marker

  Description: A configuration item a service desk ticket affected, recorded by the agent working the ticket.

  Keys:
    surrogate: affected_item_id
    natural:   configuration_item_id, ticket_key

  Volume:
    initial: 161
    growth:  80 per month
    horizon: 5 years

  Synonyms: ticket item, impacted item

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - CurrentStateFilter
    - EntityJoinBack
    - RichMetadata
```

```
Entity: ConfigurationItemKeymap   [kind: Keymap] [profile: CURRENT_STATE] [allocates: ConfigurationItem]
  configuration_item_id  : Identifier                       // allocated once per natural key; never reused
  configuration_item_key : NaturalKey [required] [unique]   // the register's item number, CI-nnnnn
  source_system          : ShortText [optional]             // system that introduced the key

  Description: Allocates each configuration item's stable identifier from its item number, once.

  Keys:
    surrogate: configuration_item_id
    natural:   configuration_item_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - SurrogateKeyAllocation
    - RichMetadata
```

```
Decision: DD-DOMAIN-001
  Title:      ItemType allocates its surrogate inline
  Category:   SCHEMA
  Module:     domain
  Applies to: ItemType
  Context:    The product allocates surrogates through keymaps, and ConfigurationItem references ItemType.
  Rationale:  A type code is never re-keyed, and the entry's identity is its code; a keymap would add a table for no stability gain. The surrogate stays stable across versions because a version is keyed on the code.
  Alternatives: A ItemTypeKeymap, as for ConfigurationItem.
```

```
Decision: DD-DOMAIN-002
  Title:      Location allocates its surrogate inline
  Category:   SCHEMA
  Module:     domain
  Applies to: Location
  Context:    The product allocates surrogates through keymaps, and ConfigurationItem references Location.
  Rationale:  A site code is never re-keyed and the set is small; the same reasoning as ItemType.
  Alternatives: A LocationKeymap.
```

```
Decision: DD-DOMAIN-003
  Title:      Dependencies are a Relationship entity, not an attribute of the item
  Category:   ARCHITECTURE
  Module:     domain
  Applies to: ItemDependency
  Context:    An item depends on many items and many items depend on it, and a dependency starts and ends on its own dates.
  Rationale:  A many-to-many association with its own lifecycle is what a Relationship entity is for. Its identity is the two items and the kind of dependency, so the same pair may be related in two ways at once.
  Alternatives: A list of supporting items on ConfigurationItem, which cannot be versioned per dependency.
```

```
Decision: DD-DOMAIN-004
  Title:      References to the IT Service Desk product are held as its natural keys, unenforced
  Category:   INTEGRATION
  Module:     domain
  Applies to: ConfigurationItem
  Context:    An item's owning customer and the tickets it was involved in are entities of another product, which this product neither owns nor can reach by reference.
  Rationale:  The design language references only entities in the same product, and a product is self-contained, so the other product's natural keys are the only stable identifiers available. They are ShortText, not Reference, because nothing in this product can check them; a consumer resolves them through that product's own natural-key lookup.
  Alternatives: Copying the customer into this product, which duplicates another product's entity and drifts from it; omitting the owner, which loses the analysis the product exists for.
```

```
Decision: DD-DOMAIN-005
  Title:      Ticket links are a Relationship entity owned by this product
  Category:   INTEGRATION
  Module:     domain
  Applies to: AffectedItem
  Context:    The service desk records which items a ticket affected, but the service desk product holds no item, so the link has to live on one side.
  Rationale:  The link describes an item's history, and the configuration team owns its accuracy, so it lives here, keyed on the item and the ticket's natural key.
  Alternatives: A link entity in the service desk product, which would hold this product's natural keys instead.
```

```
Decision: DD-DOMAIN-006
  Title:      A Traditional Data Product: no Search, Prediction or runtime Memory
  Category:   ARCHITECTURE
  Module:     domain
  Context:    The composition is chosen from the use cases.
  Rationale:  Every use case is a lookup, a traversal or an aggregate over structured attributes; none needs similarity over text, a model score, or agent session state held in the product. The absent modules can be added later as extensions, since Domain is already present.
  Alternatives: The AI-Native composition, rejected as unused machinery.
```

The source columns map to these attributes on ingest: `configuration_item_id` in the source is
the keymap's `configuration_item_key`; `ci_type_code` and `location_code` resolve to the
references; `customer_id` becomes `customer_key`; `last_discovered_at` becomes
`last_discovered_dts`. In the dependency file `source_ci_id` is the dependent item and
`target_ci_id` the supporting one; in the ticket links `ticket_id` becomes `ticket_key` and
`linked_at` becomes `linked_dts`.

**Invariants:** `INV-DOMAIN-001`, `INV-DOMAIN-002`, `INV-DOMAIN-003`, `INV-DOMAIN-004`,
`INV-DOMAIN-005`, `INV-DOMAIN-006`, `INV-DOMAIN-007`.

---

## Semantic

Every entity registers on deploy with its declared temporal profile. The relationship
catalogue covers every reference above; the dependency graph is reachable through the
relationship paths over `ItemDependency`. The two references to the service desk product are
not relationships in this product's catalogue: they are attributes whose descriptions name the
other product.

```
Orientation: -
  Entrypoint:     access-layer
  Access mode:    VIEW
```

```
Metric: Live Items
  Description: Configuration items in service, counting each item once at its current version.
  Dataset:     ConfigurationItem
  Measure:     count_rows(ConfigurationItem)
  Filter:      ConfigurationItem.is_current = true and ConfigurationItem.is_deleted = false and ConfigurationItem.lifecycle_status = 'Live'
  Grain:       ConfigurationItem
  Unit:        count
  Additive:    yes
  Synonyms:    estate size, item count
```

```
Metric: Asset Cost
  Description: Purchase cost of current, non-retired items that record one.
  Dataset:     ConfigurationItem
  Measure:     sum(ConfigurationItem.purchase_cost)
  Filter:      ConfigurationItem.is_current = true and ConfigurationItem.is_deleted = false and ConfigurationItem.lifecycle_status <> 'Retired'
  Grain:       ConfigurationItem
  Unit:        Australian dollars
  Additive:    yes
  Synonyms:    estate cost, asset value
```

```
Metric: Critical Item Share
  Description: Share of live items whose failure has critical business impact. A ratio: never summed across groups.
  Dataset:     ConfigurationItem
  Measure:     ratio(sum(when(ConfigurationItem.criticality = 'Critical', 1, 0)), count_rows(ConfigurationItem))
  Filter:      ConfigurationItem.is_current = true and ConfigurationItem.is_deleted = false and ConfigurationItem.lifecycle_status = 'Live'
  Grain:       ConfigurationItem
  Unit:        percent
  Additive:    no
```

```
Metric: Dependencies
  Description: Current dependencies between items.
  Dataset:     ItemDependency
  Measure:     count_rows(ItemDependency)
  Filter:      ItemDependency.is_current = true and ItemDependency.is_deleted = false
  Grain:       ItemDependency
  Unit:        count
  Additive:    yes
  Synonyms:    edges, relationships
```

```
Decision: DD-SEM-001
  Title:      The entity model is custom, ITIL-aligned in its terms
  Category:   ARCHITECTURE
  Module:     semantic
  Context:    The Semantic module records the source of the entity model.
  Rationale:  ITIL names the concepts (configuration item, CI type, relationship) but publishes no data model; the CMDB vendors' models are proprietary. The entity names follow ITIL's vocabulary so the glossary maps onto it.
  Alternatives: A vendor CMDB schema, rejected as proprietary and far wider than the use cases.
```

```
Decision: DD-DISCOVERY-001
  Title:      Agents enter through the access layer, by view
  Category:   ARCHITECTURE
  Module:     semantic
  Applies to: Orientation
  Context:    The orientation layer requires the approved entrypoint and access mode to be settled and explained.
  Rationale:  The access layer is the only consumer-readable surface the role model grants. Agents orient through the product registry, read the trust map, then follow the catalogue resources; dependency traversal starts from the relationship paths.
```

```
Decision: DD-SEM-002
  Title:      One trust-authoritative producer
  Category:   ARCHITECTURE
  Module:     semantic
  Applies to: Orientation
  Context:    The manifest must name exactly one producer whose trust map is authoritative.
  Rationale:  The configuration register validation pipeline, run by the configuration manager, publishes the canonical validation evidence in Observability.
```

**Invariants:** `INV-SEMANTIC-001`, `INV-SEMANTIC-002`, `INV-SEMANTIC-003`,
`INV-SEMANTIC-004`, `INV-SEMANTIC-005`, `INV-SEMANTIC-006`, `INV-SEMANTIC-007`,
`INV-SEMANTIC-008`, `INV-SEMANTIC-009`, `INV-SEMANTIC-010`, `INV-SEMANTIC-011`,
`INV-SEMANTIC-012`, `INV-SEMANTIC-013`, `INV-SEMANTIC-014`, `INV-SEMANTIC-015`, `INV-SEMANTIC-016`, `INV-SEMANTIC-017`, `INV-SEMANTIC-018`, `INV-SEMANTIC-019`, `INV-SEMANTIC-020`.

---

## Observability

Change events, quality metrics and lineage for every module, at table level. Discovery runs
nightly, so the register is stale when the newest item seen is more than two days old. The
graph-lineage facet is not enabled, so `INV-OBS-007`, `INV-OBS-008` and `INV-OBS-009` apply
only if it is enabled later.

```
Quality: -
  Weights:
    completeness: 30%
    validity: 20%
    consistency: 30%
    accuracy: 10%
    timeliness: 10%
  Rules:
    - completeness(ConfigurationItem.end_of_support_date, ConfigurationItem.lifecycle_status = 'Live' and is_not_null(ConfigurationItem.purchase_date)): pass >= 0.95, warn >= 0.85
    - completeness(ConfigurationItem.location_id): pass >= 0.95, warn >= 0.90
    - validity(is_null(ConfigurationItem.warranty_end_date) or is_null(ConfigurationItem.purchase_date) or ConfigurationItem.warranty_end_date >= ConfigurationItem.purchase_date): pass >= 1.0, warn >= 0.99
    - consistency(ItemDependency.dependent_item_id <> ItemDependency.supporting_item_id): pass >= 1.0, warn >= 1.0
    - uniqueness(ConfigurationItem.serial_number): fail on any
    - integrity(ConfigurationItem.item_type_id): fail on any
    - integrity(ConfigurationItem.location_id): fail on any
    - integrity(ItemType.parent_item_type_id): fail on any
    - integrity(ItemDependency.dependent_item_id): fail on any
    - integrity(ItemDependency.supporting_item_id): fail on any
    - integrity(AffectedItem.configuration_item_id): fail on any
    - freshness(ConfigurationItem): warn after 2 days, fail after 7 days
  Frequency: on load, daily
```

```
Lineage: -
  Flows:
    - configuration_items.csv -> load_items -> ConfigurationItem
    - ci_types.csv -> load_ci_types -> ItemType
    - locations.csv -> load_locations -> Location
    - ci_relationships.csv -> load_dependencies -> ItemDependency
    - ticket_item_links.csv -> load_ticket_links -> AffectedItem
  Scope: Source files into Domain.
```

```
Retention: -
  ChangeEvent:       2 years queryable, 7 years archived
  DataQualityMetric: 2 years queryable, 7 years archived
  LineageRun:        2 years queryable, 7 years archived
  AgentOutcome:      2 years queryable, 7 years archived
  DataLineage:       life of product
```

Retention is `regulatory`: the register supports the fixed-asset register, whose records are
kept seven years, so audit and execution records are queryable for two years and archived for
seven. Definitional lineage is kept for the life of the product (`INV-OBS-004`).

```
Decision: DD-OBS-001
  Title:      Freshness is measured on discovery, at two and seven days
  Category:   OPERATIONAL
  Module:     observability
  Applies to: Quality
  Context:    Items change rarely, so the newest row's age says little; discovery sees every item nightly.
  Rationale:  last_discovered_dts moves every night for a healthy register, so a register no discovery run has touched for two days is stale and one untouched for a week is unreliable for impact analysis.
```

```
Decision: DD-OBS-002
  Title:      Cross-product references are not integrity-checked here
  Category:   INTEGRATION
  Module:     observability
  Applies to: Quality
  Context:    customer_key and ticket_key name entities in the IT Service Desk product.
  Rationale:  An integrity rule reads a reference this product declares; these are attributes, so no rule can check them in this product. Whether every customer and ticket key resolves is a question across products, recorded as an open gap rather than claimed as checked.
```

**Invariants:** `INV-OBS-001`, `INV-OBS-002`, `INV-OBS-003`, `INV-OBS-004`,
`INV-OBS-005`, `INV-OBS-006`, `INV-OBS-007`, `INV-OBS-008`, `INV-OBS-009`.

---

## Memory

The documentation facet only. All six documentation entities deploy and capture every decision
in this specification, catalogued and product, as a `DesignDecision`; the capture floor applies
per module. The runtime facet is absent (`DD-DOMAIN-006`): an engineer's or agent's impact
analysis is a set of reads, with no state to carry between them.

```
Decision: DD-MEM-001
  Title:      No runtime facet
  Category:   ARCHITECTURE
  Module:     memory
  Context:    Memory's runtime facet holds agent sessions, interactions and learned strategies.
  Rationale:  The product's consumers read and traverse; an agent investigating an outage keeps its session in the product it works from, the service desk product, which has the runtime facet.
  Alternatives: Both facets, as in the service desk product.
```

**Invariants:** `INV-MEMORY-001`, `INV-MEMORY-002`, `INV-MEMORY-003`, `INV-MEMORY-004`,
`INV-MEMORY-005`, `INV-MEMORY-006`.

---

## Glossary

The terms this product introduces, three per module for Memory's capture floor.

```
Glossary: Configuration item
  Definition: Anything the provider manages that a service depends on, recorded with its type, place, owner and lifecycle.
  Module:     domain
  Related:    ConfigurationItem
```

```
Glossary: End of support
  Definition: The last day the vendor supports an item; after it, faults may have no fix.
  Module:     domain
  Related:    ConfigurationItem
```

```
Glossary: Shared platform
  Definition: An item no single customer owns that many customers' items depend on, such as the identity platform or a host cluster.
  Module:     domain
  Related:    ConfigurationItem, ItemDependency
```

```
Glossary: Supporting item
  Definition: The item another depends on; the downstream side of a dependency.
  Module:     semantic
  Related:    ItemDependency
```

```
Glossary: Blast radius
  Definition: Every item that depends on a given item, directly or through other items.
  Module:     semantic
  Related:    ItemDependency, ConfigurationItem
```

```
Glossary: Criticality
  Definition: The business impact if an item fails: Critical, High, Medium or Low.
  Module:     semantic
  Related:    ConfigurationItem
```

```
Glossary: Discovery
  Definition: The nightly scan that confirms each item still exists and records when it was last seen.
  Module:     observability
  Related:    ConfigurationItem
```

```
Glossary: Dangling dependency
  Definition: A dependency whose dependent or supporting item does not exist; any one fails integrity.
  Module:     observability
  Related:    ItemDependency
```

```
Glossary: Duplicate serial
  Definition: Two current items recording the same manufacturer serial number, which means one record is wrong.
  Module:     observability
  Related:    ConfigurationItem
```

```
Glossary: Cross-product key
  Definition: Another product's natural key held as an attribute, such as a customer or ticket number, which this product records but cannot check.
  Module:     memory
  Related:    ConfigurationItem, AffectedItem
```

```
Glossary: Fixed-asset register
  Definition: The finance record of owned equipment, whose seven-year retention sets this product's audit retention.
  Module:     memory
  Related:    ConfigurationItem
```

```
Glossary: Impact
  Definition: Whether a ticket's item was the one at fault (Primary) or affected through it (Secondary).
  Module:     memory
  Related:    AffectedItem
```

## Access layer

The three standard tiers. Physical principals and containers come from the organisation
profile.

```
Decision: DD-ACCESS-001
  Title:      Three access tiers; the agent tier writes only Observability events
  Category:   SECURITY
  Module:     observability
  Context:    The access-layer pattern requires the role model to be recorded so agents can read the access contract from Memory.
  Rationale:  ROLE_READ serves engineers, asset managers and BI; ROLE_AGENT serves agents and automated tools with the same read scope plus append-only write-back of usage and quality events; ROLE_ADMIN serves the configuration manager. With no runtime facet, the agent tier has no Memory write-back.
```

---

## Sensitive attributes

None. The register holds no personal data: devices are recorded against the customer that owns
them, not the person using them, and `customer_key` is an organisation's number. The
organisation profile's classification default applies to every attribute.

## Settled decisions

Six of the seven catalogued decisions take the advocated option. `DEC-TEMPORAL-PATTERN` is
`scd2` rather than `bi-temporal`, with its reason in the frontmatter: a deliberate departure,
not an oversight. `ItemType` and `Location` allocate inline, each recorded above.
