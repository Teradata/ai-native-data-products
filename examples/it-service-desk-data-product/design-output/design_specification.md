---
product: IT Service Desk
product_code: ITSD
composition: ai-native-data-product
modules:
  - domain
  - semantic
  - search
  - prediction
  - observability
  - memory
facets:
  - memory:documentation
  - memory:runtime
decisions:
  - id: DEC-TIMESTAMP-ZONE
    choice: zone-aware
  - id: DEC-TEMPORAL-PATTERN
    choice: bi-temporal
  - id: DEC-COLUMN-STRATEGY
    choice: offload
  - id: DEC-SURROGATE-ALLOCATION
    choice: keymap
  - id: DEC-DELETE-STRATEGY
    choice: soft-delete
  - id: DEC-QUALITY-STORAGE
    choice: observability
  - id: DEC-AUDIT-RETENTION
    choice: bounded
    because: IT service desk ticket data carries no statutory retention obligation in this deployment context; a 3-year uniform window covers operational investigation needs and pattern analysis depth; revisit if compliance scope changes
---

# IT Service Desk: Design Specification

The design phase's output for the IT Service Desk example, produced from
[`ITSD_Reference_Brief.md`](../ITSD_Reference_Brief.md) and the source data in
[`data/`](../data/). It is the build input: every fact a builder needs is in the frontmatter
or a notation block defined by the
[Design Specification Standard](../../../design/core/DESIGN_SPECIFICATION.md), and it names no
platform, container or principal, so it builds on any conforming platform under any
organisation profile. Prose explains; it is never the only statement of a fact.

This is reference output, kept so implementations can be compared. Validate it with:

```bash
python tooling/evals/spec_lint.py examples/it-service-desk-data-product/design-output/design_specification.md
```

---

## Business purpose

```
Product: -
  Description:       Central data product for IT service desk operations: SLA breach prediction, similar-ticket retrieval and ticket quality monitoring.
  Domain:            IT service management
  Owner:             Service desk operations
  Technical contact: Service desk data engineering
  Trust producer:    the IT Service Desk validation pipeline, run by the product owner or data steward
```

Central data product for IT service desk operations. Supports SLA breach prediction on open
tickets, semantic discovery of similar past tickets and their resolutions, and quality
monitoring across the full ticket lifecycle. Serves real-time triage (agent-driven) and
analytical review (manager and analyst-driven).

**Consumers:** AI agents (triage, similar-ticket retrieval, multi-step investigation with
session continuity); operations analysts (SLA performance and agent productivity); service
desk managers (quality monitoring, breach risk review); downstream ML pipelines (feature
consumption).

**Use cases:** predict SLA breach risk for an open ticket; find similar past tickets and
their resolutions; monitor ticket data quality; track agent and team SLA performance;
maintain agent session continuity across a multi-step investigation.

## Composition

All six modules; Memory with both facets. Every `[hard]` requirement is met inside the
composition: Search and Prediction hard-depend on Domain for `EntityJoinBack`, which Domain
provides. No soft requirement goes unmet, so no feature is disabled. The access layer deploys
in the standard two phases with the three standard tiers.

---

## Domain

Four business entities: three `History` entities on the bi-temporal profile with keymap
allocation, and `Category`, a `Reference` entity holding present values only. The temporal
and lifecycle columns come from the temporal pattern and are not restated.

Under keymap allocation each natural key lives on its keymap alone: `Ticket`, `Agent` and
`Customer` carry the stable surrogate, and the source identifiers (`ticket_id`,
`agent_id` and `customer_id` in the source files) arrive as the keymaps' natural keys.

```
Entity: Ticket                    [kind: History] [profile: SCD2_BITEMPORAL]
  ticket_id          : Identifier                          // surrogate; stable across all versions
  customer_id        : Reference [required] [-> Customer]  // the reporting customer
  assigned_agent_id  : Reference [optional] [-> Agent]     // assigned agent; absent while unassigned
  category_id        : Reference [required] [-> Category]  // ticket category
  priority           : Enum{P1|P2|P3|P4} [required]        // ticket priority
  status             : ShortText [required]                // Open, In Progress, Pending Customer, Resolved or Closed
  subject            : ShortText [required]                // one-line summary
  description        : Text [required] [pii-incidental]    // full description
  resolution_notes   : Text [optional] [pii-incidental]    // how the ticket was resolved
  sla_hours          : Integer [required]                  // contracted SLA in hours
  opened_dts         : Timestamp [required]                // when the ticket was raised
  first_response_dts : Timestamp [optional]                // first agent response
  resolved_dts       : Timestamp [optional]                // when resolved
  closed_dts         : Timestamp [optional]                // when closed
  sla_breached       : Flag [required]                     // whether the SLA was breached
  escalated          : Flag [required]                     // whether the ticket was escalated
  escalation_reason  : Text [optional]                     // why it was escalated
  satisfaction_score : Integer [optional]                  // customer rating, 1 to 5
  is_current         : Flag [current-flag]                 // current version marker
  is_deleted         : Flag [deleted-flag]                 // soft-delete marker

  Keys:
    surrogate: ticket_id

  Volume:
    initial: 150
    growth:  75 per month
    horizon: 3 years

  Synonyms: incident, case, request

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
Entity: Agent                     [kind: History] [profile: SCD2_BITEMPORAL]
  agent_id   : Identifier                          // surrogate; stable across all versions
  first_name : ShortText [required]                // given name
  last_name  : ShortText [required]                // family name
  email      : ShortText [required] [pii]          // work email
  team       : ShortText [required]                // Infrastructure, Applications or Service Desk
  level      : Enum{L1|L2|L3} [required]           // support tier
  hire_date  : Date [optional]                     // date joined the service desk
  is_active  : Flag [required]                     // currently taking tickets
  is_current : Flag [current-flag]                 // current version marker
  is_deleted : Flag [deleted-flag]                 // soft-delete marker

  Keys:
    surrogate: agent_id

  Volume:
    initial: 12
    growth:  3 per year
    horizon: 3 years

  Synonyms: technician, engineer

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - SurrogateKeyAllocation
    - CurrentStateFilter
    - PointInTimeReconstruction
    - NaturalKeyLookup
    - RichMetadata
```

```
Entity: Customer                  [kind: History] [profile: SCD2_BITEMPORAL]
  customer_id         : Identifier                                 // surrogate; stable across all versions
  company_name        : ShortText [required]                       // customer organisation
  contact_name        : ShortText [required] [pii]                 // primary contact
  contact_email       : ShortText [required] [pii]                 // primary contact email
  tier                : Enum{Platinum|Gold|Silver|Bronze} [required]  // service tier
  region              : ShortText [required]                       // trading region
  contract_start_date : Date [optional]                            // contract start
  is_current          : Flag [current-flag]                        // current version marker
  is_deleted          : Flag [deleted-flag]                        // soft-delete marker

  Keys:
    surrogate: customer_id

  Volume:
    initial: 20
    growth:  2 per month
    horizon: 3 years

  Synonyms: client, account

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - SurrogateKeyAllocation
    - CurrentStateFilter
    - PointInTimeReconstruction
    - NaturalKeyLookup
    - RichMetadata
```

```
Entity: Category                  [kind: Reference] [profile: CURRENT_STATE] [allocation: inline]
  category_id        : Identifier                           // surrogate; inline allocation
  category_code      : NaturalKey [required] [unique]       // source category code, CAT-001 to CAT-015
  name               : ShortText [required]                 // display name
  description        : Text [optional]                      // what the category covers
  parent_category_id : Reference [optional] [-> Category]   // parent; absent for a top-level category
  default_sla_hours  : Integer [optional]                   // SLA applied to new tickets in this category
  effective_date     : Date [optional]                      // first day the category may be assigned
  expiration_date    : Date [optional]                      // last day the category may be assigned

  Keys:
    surrogate: category_id
    natural:   category_code

  Volume:
    initial: 15
    growth:  0 per year
    horizon: 3 years

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - CurrentStateFilter
    - RichMetadata
```

```
Entity: TicketKeymap              [kind: Keymap] [profile: CURRENT_STATE] [allocates: Ticket]
  ticket_id     : Identifier                       // allocated once per natural key; never reused
  ticket_key    : NaturalKey [required] [unique]   // source ticket identifier
  source_system : ShortText [optional]             // system that introduced the key

  Keys:
    surrogate: ticket_id
    natural:   ticket_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - SurrogateKeyAllocation
    - RichMetadata
```

```
Entity: AgentKeymap               [kind: Keymap] [profile: CURRENT_STATE] [allocates: Agent]
  agent_id      : Identifier                       // allocated once per natural key; never reused
  agent_key     : NaturalKey [required] [unique]   // source agent identifier; the agent's email is not used as a key
  source_system : ShortText [optional]             // system that introduced the key

  Keys:
    surrogate: agent_id
    natural:   agent_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - SurrogateKeyAllocation
    - RichMetadata
```

```
Entity: CustomerKeymap            [kind: Keymap] [profile: CURRENT_STATE] [allocates: Customer]
  customer_id   : Identifier                       // allocated once per natural key; never reused
  customer_key  : NaturalKey [required] [unique]   // source customer identifier
  source_system : ShortText [optional]             // system that introduced the key

  Keys:
    surrogate: customer_id
    natural:   customer_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - SurrogateKeyAllocation
    - RichMetadata
```

```
Decision: DD-DOMAIN-001
  Title:      Category holds present values only
  Category:   ARCHITECTURE
  Module:     domain
  Applies to: Category
  Context:    The default profile for a Reference entity is SCD2_HISTORY, so a past record decodes against what its code meant then.
  Rationale:  Category is a small internal taxonomy whose labels are not reworded in service, and no ticket needs a category name as at its creation date. CURRENT_STATE suffices, and the declared profile is what licenses effective_date and expiration_date as day-grain availability dates.
  Alternatives: SCD2_HISTORY, the Reference default.
```

```
Decision: DD-DOMAIN-002
  Title:      Category allocates its surrogate inline
  Category:   SCHEMA
  Module:     domain
  Applies to: Category
  Context:    The product allocates surrogates through keymaps, because Ticket, Agent and Customer are referenced across modules.
  Rationale:  Category does not version, so its surrogate cannot drift between versions, and the keymap machinery would add a table for no stability gain.
  Alternatives: A CategoryKeymap, as for the History entities.
```

```
Decision: DD-DOMAIN-003
  Title:      No Relationship entities for ticket assignment, customer or category
  Category:   ARCHITECTURE
  Module:     domain
  Applies to: Ticket
  Context:    The standard offers Relationship entities for many-to-many or separately versioned associations.
  Rationale:  A ticket's agent, customer and category are point-in-time attributes of the ticket, versioned with it; none is a standalone association with its own lifecycle.
```

```
Decision: DD-DOMAIN-004
  Title:      Incidental personal data in ticket free text is a recorded risk
  Category:   SECURITY
  Module:     domain
  Applies to: Ticket
  Context:    Customers and agents write description and resolution_notes freely, so they may contain personal data the design does not intend.
  Rationale:  No runtime masking in this cycle; both attributes carry [pii-incidental] so the organisation profile can apply protection, and the risk is captured as an implementation note for production hardening.
```

`Ticket`, `Agent` and `Customer` relate through Ticket's references; Category is
hierarchical through `parent_category_id`. The source columns map to these attributes on
ingest: `created_at` becomes `opened_dts`, and the `*_at` event columns become `*_dts`.

**Invariants:** `INV-DOMAIN-001`, `INV-DOMAIN-002`, `INV-DOMAIN-003`, `INV-DOMAIN-004`,
`INV-DOMAIN-005`, `INV-DOMAIN-006`, `INV-DOMAIN-007`.

---

## Semantic

Every entity in every module registers on deploy, with its declared temporal profile; that
declaration is what licenses Category's `effective_date` and `expiration_date`. The
relationship catalogue covers every reference above and the cross-module joins from Search
and Prediction to Ticket. The entity model is custom: no industry standard covers generic
IT service desk data at this scope.

```
Orientation: -
  Entrypoint:     access-layer
  Access mode:    VIEW
```

```
AccessObject: TicketDetail
  Kind:    composite
  Anchor:  Ticket
  Members: Customer, Agent, Category
  Purpose: A ticket with its customer, assigned agent and category, for triage in one read.
```

The metrics come from the analytical use cases: SLA performance, responsiveness and
satisfaction, by agent, team, category and customer tier.

```
Metric: Tickets Opened
  Description: Tickets raised, counting each ticket once at its current version.
  Dataset:     Ticket
  Measure:     count_rows(Ticket)
  Filter:      Ticket.is_current = true and Ticket.is_deleted = false
  Grain:       Ticket
  Unit:        count
  Additive:    yes
  Synonyms:    ticket volume, incident count
```

```
Metric: SLA Breach Rate
  Description: Share of current tickets that breached their SLA. A ratio: never summed across groups.
  Dataset:     Ticket
  Measure:     ratio(sum(when(Ticket.sla_breached, 1, 0)), count_rows(Ticket))
  Filter:      Ticket.is_current = true and Ticket.is_deleted = false
  Grain:       Ticket
  Unit:        percent
  Additive:    no
  Synonyms:    breach rate
```

```
Metric: Mean Time to First Response
  Description: Average hours from a ticket being raised to its first agent response, over tickets that have one.
  Dataset:     Ticket
  Measure:     avg(hours_between(Ticket.opened_dts, Ticket.first_response_dts))
  Filter:      Ticket.is_current = true and is_not_null(Ticket.first_response_dts)
  Grain:       Ticket
  Unit:        hours
  Additive:    no
  Synonyms:    response time, MTTR
```

```
Metric: Average Satisfaction
  Description: Mean customer satisfaction score over tickets that were rated.
  Dataset:     Ticket
  Measure:     avg(Ticket.satisfaction_score)
  Filter:      Ticket.is_current = true and is_not_null(Ticket.satisfaction_score)
  Grain:       Ticket
  Unit:        score, 1 to 5
  Additive:    no
  Synonyms:    CSAT
```

```
Decision: DD-SEM-001
  Title:      The entity model is custom
  Category:   ARCHITECTURE
  Module:     semantic
  Context:    The Semantic module records the source of the entity model.
  Rationale:  No applicable industry standard exists for generic IT service desk data at this composition. ITIL is the candidate for future alignment.
```

```
Decision: DD-DISCOVERY-001
  Title:      Agents enter through the access layer, by view
  Category:   ARCHITECTURE
  Module:     semantic
  Applies to: Orientation
  Context:    The orientation layer requires the approved entrypoint and access mode to be settled and explained.
  Rationale:  The access layer is the only consumer-readable surface the role model grants, so it keeps agents off base relations. Agents orient through the product registry, read the trust map before any analytical resource, then follow the catalogue resources in discovery order.
```

```
Decision: DD-SEM-002
  Title:      One trust-authoritative producer
  Category:   ARCHITECTURE
  Module:     semantic
  Applies to: Orientation
  Context:    The manifest must name exactly one producer whose trust map is authoritative, or a validator reading the product has to guess.
  Rationale:  The IT Service Desk validation pipeline, run by the product owner or data steward, publishes the canonical validation evidence in Observability.
```

**Invariants:** `INV-SEMANTIC-001`, `INV-SEMANTIC-002`, `INV-SEMANTIC-003`,
`INV-SEMANTIC-004`, `INV-SEMANTIC-005`, `INV-SEMANTIC-006`, `INV-SEMANTIC-007`,
`INV-SEMANTIC-008`, `INV-SEMANTIC-009`, `INV-SEMANTIC-010`, `INV-SEMANTIC-011`,
`INV-SEMANTIC-012`, `INV-SEMANTIC-013`, `INV-SEMANTIC-014`, `INV-SEMANTIC-015`,
`INV-SEMANTIC-016`, `INV-SEMANTIC-017`.

---

## Search

One `EntityEmbedding` entity, as the Search module defines it, with two embeddings per
ticket discriminated by `source_attribute`. Absence is no row, never a null vector.

```
Entity: EntityEmbedding           [kind: History] [profile: SCD2_HISTORY] [allocation: inline]
  embedding_id            : Identifier                         // surrogate for the embedding record
  entity_id               : Reference [required] [-> Ticket]   // the embedded ticket; key only
  entity_kind             : Enum{TICKET} [required]            // always TICKET in this product
  source_attribute        : ShortText [required]               // which embedding: the Embedding block name
  embedding               : Vector[384] [required]             // dense text embedding
  embedding_dimensions    : Integer [required]                 // recorded for reproducibility
  embedding_model         : ShortText [required]               // model that produced the vector
  embedding_model_version : ShortText [optional]               // model version
  generated_dts           : Timestamp [required]               // when the vector was generated
  is_current              : Flag [current-flag]                // current embedding per ticket and source

  Keys:
    surrogate: embedding_id
    natural:   entity_id, source_attribute, embedding_model

  Volume:
    initial: 250
    growth:  140 per month
    horizon: 3 years

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - Embed
    - NearestNeighbors
    - CurrentStateFilter
    - EntityJoinBack
    - RichMetadata
    - AccessView
```

```
Embedding: subject_description
  Entity:     Ticket
  Source:     concat(Ticket.subject, Ticket.description)
  Dimensions: 384
  Similarity: cosine
  Index:      exact
  Threshold:  0.75
  Refresh:    on load
```

```
Embedding: resolution_notes
  Entity:     Ticket
  Source:     Ticket.resolution_notes
  Where:      is_not_null(Ticket.resolution_notes)
  Dimensions: 384
  Similarity: cosine
  Index:      exact
  Threshold:  0.75
  Refresh:    on load
```

```
Decision: DD-SEARCH-001
  Title:      Two embeddings per ticket in one entity
  Category:   ARCHITECTURE
  Module:     search
  Applies to: EntityEmbedding
  Context:    A ticket is embedded from its subject and description, and again from its resolution notes once resolved.
  Rationale:  Discriminating by source_attribute keeps one similarity query and one currency flag; two entities would fork both.
```

```
Decision: DD-SEARCH-002
  Title:      Exact similarity search at this volume
  Category:   PERFORMANCE
  Module:     search
  Applies to: subject_description
  Context:    Search supports an approximate index for large embedding sets.
  Rationale:  Around six thousand embeddings over three years scan exactly in milliseconds; an index would add maintenance for no gain. An approximate index is the upgrade path for production scale.
```

**Invariants:** `INV-SEARCH-001`, `INV-SEARCH-002`, `INV-SEARCH-003`, `INV-SEARCH-004`,
`INV-SEARCH-005`.

---

## Prediction

The target is the probability, 0 to 1, that an open ticket breaches its SLA before
resolution. Features are computed as at the observation instant; values unavailable at
prediction time (resolution, closure, satisfaction) are excluded. Agent and customer
attributes are read as at the ticket's opening.

```
Entity: TicketFeatureSet          [kind: History] [profile: SCD2_HISTORY] [module: prediction] [allocation: inline]
  feature_group_id      : Identifier                          // surrogate for the feature row
  entity_id             : Reference [required] [-> Ticket]    // the featurised ticket; key only
  entity_kind           : Enum{TICKET} [required]             // always TICKET
  f_priority_int        : Integer [optional] [derive: map(Ticket.priority, {P1: 1, P2: 2, P3: 3, P4: 4})]  // priority, 1 is highest
  f_sla_hours           : Integer [optional] [derive: Ticket.sla_hours]  // contracted SLA; a passthrough
  f_customer_tier_int   : Integer [optional] [derive: map(as_of(Customer.tier, Ticket.opened_dts), {Platinum: 1, Gold: 2, Silver: 3, Bronze: 4})]  // tier when the ticket was raised
  f_agent_team_int      : Integer [optional] [derive: map(as_of(Agent.team, Ticket.opened_dts), {Infrastructure: 1, Applications: 2, 'Service Desk': 3})]  // assigned team; absent while unassigned
  f_category_leaf_int   : Integer [optional] [derive: map(Category.category_code, {CAT-006: 1, CAT-007: 2, CAT-008: 3, CAT-009: 4, CAT-010: 5, CAT-011: 6, CAT-012: 7, CAT-013: 8, CAT-014: 9, CAT-015: 10})]  // leaf category
  f_created_hour        : Integer [optional] [derive: hour_of_day(Ticket.opened_dts)]  // hour raised, 0 to 23
  f_created_dow         : Integer [optional] [derive: day_of_week(Ticket.opened_dts)]  // weekday raised, 0 is Monday
  f_response_hours      : Decimal(10,4) [optional] [derive: hours_between(Ticket.opened_dts, Ticket.first_response_dts)]  // hours to first response
  f_subject_length      : Integer [optional] [derive: length(Ticket.subject)]  // subject length in characters
  f_is_escalated        : Flag [optional] [derive: Ticket.escalated]  // escalated so far
  observation_dts       : Timestamp [required]                // point-in-time anchor
  feature_group_name    : ShortText [required]                // this feature group
  feature_group_version : ShortText [optional]                // feature logic version
  is_current            : Flag [current-flag]                 // current feature row per ticket

  Keys:
    surrogate: feature_group_id
    natural:   entity_id

  Volume:
    initial: 150
    growth:  75 per month
    horizon: 3 years

  Features:
    subject: Ticket
    as of:   TicketFeatureSet.observation_dts
    storage: wide
    refresh: on load

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - EntityJoinBack
    - PointInTimeReconstruction
    - CurrentStateFilter
    - AccessView
    - RichMetadata
```

```
Entity: ModelPrediction           [kind: History] [profile: SCD2_HISTORY] [allocation: inline]
  prediction_id           : Identifier                        // surrogate for the prediction
  entity_id               : Reference [required] [-> Ticket]  // the scored ticket; key only
  entity_kind             : Enum{TICKET} [required]           // always TICKET
  model_key               : ShortText [required]              // the Model block name
  model_version           : ShortText [required]              // model version
  prediction_value        : Decimal(10,6) [optional]          // breach probability, 0 to 1
  prediction_class        : ShortText [optional]              // unused by this model
  prediction_json         : Json [optional]                   // unused by this model
  confidence_score        : Decimal(5,4) [optional]           // model confidence, 0 to 1
  prediction_dts          : Timestamp [required]              // when scored
  feature_observation_dts : Timestamp [optional]              // the feature row scored
  is_current              : Flag [current-flag]               // latest score per ticket

  Keys:
    surrogate: prediction_id
    natural:   entity_id, model_key

  Volume:
    initial: 150
    growth:  1500 per month
    horizon: 3 years

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - EntityJoinBack
    - PointInTimeReconstruction
    - CurrentStateFilter
    - AccessView
    - RichMetadata
```

```
Model: sla_breach
  Subject:  Ticket
  Features: TicketFeatureSet
  Target:   Whether an open ticket breaches its SLA before resolution; learned from Ticket.sla_breached on closed tickets.
  Output:   probability
  Scoring:  on load, on demand
```

```
Decision: DD-PRED-001
  Title:      f_sla_hours is a passthrough feature
  Category:   SCHEMA
  Module:     prediction
  Applies to: TicketFeatureSet
  Context:    Prediction features are engineered unless all three passthrough conditions hold.
  Rationale:  sla_hours is a contractual constant the business sets, not an observed value; it leaks nothing about the future; the model treats it as a bound, and transforming it would obscure what it is.
```

```
Decision: DD-PRED-002
  Title:      Agent team is read as at the ticket's opening
  Category:   SCHEMA
  Module:     prediction
  Applies to: TicketFeatureSet
  Context:    The brief asks for the agent's team at assignment time, but the source records no assignment instant.
  Rationale:  The opening instant is the latest point-in-time-safe anchor the data supports. If an assignment instant is added to the source, the feature should move to it.
  Alternatives: The team as it currently stands, which leaks later reassignments into training.
```

**Invariants:** `INV-PRED-001`, `INV-PRED-002`, `INV-PRED-003`, `INV-PRED-004`,
`INV-PRED-005`.

---

## Observability

Change events, quality metrics and lineage for every module, recorded at table level.
Lineage covers source files into Domain this cycle; Search and Prediction lineage is derived
from Domain. The graph-lineage facet is not enabled, so `INV-OBS-007`, `INV-OBS-008` and
`INV-OBS-009` apply only if it is enabled later.

```
Quality: -
  Weights:
    completeness: 35%
    validity: 25%
    consistency: 20%
    accuracy: 10%
    timeliness: 10%
  Rules:
    - completeness(Ticket.resolution_notes, Ticket.status = 'Resolved' or Ticket.status = 'Closed'): pass >= 0.90, warn >= 0.80
    - completeness(Ticket.assigned_agent_id, Ticket.status <> 'Open'): pass >= 0.90, warn >= 0.80
    - completeness(Ticket.satisfaction_score, Ticket.status = 'Closed'): pass >= 0.90, warn >= 0.0
    - validity(is_null(Ticket.satisfaction_score) or Ticket.satisfaction_score >= 1 and Ticket.satisfaction_score <= 5): pass >= 1.0, warn >= 0.99
    - consistency(is_null(Ticket.resolved_dts) or Ticket.resolved_dts >= Ticket.opened_dts): pass >= 1.0, warn >= 0.99
    - integrity(Ticket.customer_id): fail on any
    - integrity(Ticket.assigned_agent_id): fail on any
    - integrity(Ticket.category_id): fail on any
    - integrity(Category.parent_category_id): fail on any
    - freshness(Ticket): warn after 24 hours, fail after 48 hours
  Frequency: on load, on demand
```

```
Lineage: -
  Flows:
    - tickets.csv -> load_tickets -> Ticket
    - agents.csv -> load_agents -> Agent
    - customers.csv -> load_customers -> Customer
    - categories.csv -> load_categories -> Category
  Scope: Source files into Domain; Search and Prediction lineage is derived from Domain.
```

```
Retention: -
  ChangeEvent:       3 years
  DataQualityMetric: 3 years
  LineageRun:        3 years
  AgentOutcome:      3 years
  DataLineage:       life of product
  AgentSession:      7 days after close
  AgentInteraction:  90 days
  LearnedStrategy:   2 years
```

Retention is bounded at three years for all audit and execution records, per
`DEC-AUDIT-RETENTION`. Definitional lineage is kept for the life of the product
(`INV-OBS-004`).

**Invariants:** `INV-OBS-001`, `INV-OBS-002`, `INV-OBS-003`, `INV-OBS-004`,
`INV-OBS-005`, `INV-OBS-006`, `INV-OBS-007`, `INV-OBS-008`, `INV-OBS-009`.

---

## Memory

Both facets. The documentation facet deploys all six entities and captures every decision
in this specification, catalogued and product, as a `DesignDecision`; the capture floor
applies per module. The runtime facet deploys all five entities. A session's working state
(the ticket under investigation, the step reached, the last search) lives in its context;
tickets a search retrieved are recorded as a count and a table-level reference, never as a
list of ticket ids (`INV-MEMORY-001`). Retention is in the Observability section's
`Retention:` block.

```
Runtime: -
  Session timeout: 24 hours
```

```
Decision: DD-MEM-001
  Title:      Sessions expire after 24 hours of inactivity
  Category:   OPERATIONAL
  Module:     memory
  Applies to: Runtime
  Context:    Runtime sessions may be abandoned without being closed.
  Rationale:  A day of inactivity covers a multi-step investigation across shifts without accumulating stale state; expired sessions are kept 7 days for short-term audit, then purged.
```

**Invariants:** `INV-MEMORY-001`, `INV-MEMORY-002`, `INV-MEMORY-003`, `INV-MEMORY-004`,
`INV-MEMORY-005`, `INV-MEMORY-006`.

---

## Glossary

The terms this product introduces, three per module for Memory's capture floor.

```
Glossary: SLA breach
  Definition: A ticket not resolved within its contracted SLA hours.
  Module:     domain
  Related:    Ticket
```

```
Glossary: Escalation
  Definition: Moving a ticket to a higher support tier or team because it cannot be resolved at the current one.
  Module:     domain
  Related:    Ticket
```

```
Glossary: Customer tier
  Definition: The service level a customer has contracted: Platinum, Gold, Silver or Bronze.
  Module:     domain
  Related:    Customer
```

```
Glossary: Leaf category
  Definition: A category with no children; tickets are assigned to leaf categories.
  Module:     semantic
  Related:    Category
```

```
Glossary: First response
  Definition: The first reply an agent sends on a ticket, from which response time is measured.
  Module:     semantic
  Related:    Ticket
```

```
Glossary: CSAT
  Definition: The 1 to 5 satisfaction score a customer gives a closed ticket.
  Module:     semantic
  Related:    Ticket
```

```
Glossary: Similar ticket
  Definition: A past ticket whose subject and description, or resolution notes, are at least 0.75 cosine-similar to the one under investigation.
  Module:     search
  Related:    Ticket, EntityEmbedding
```

```
Glossary: Resolution embedding
  Definition: The embedding of a resolved ticket's resolution notes, used to retrieve how similar tickets were fixed.
  Module:     search
  Related:    EntityEmbedding
```

```
Glossary: Embedding source
  Definition: Which text of a ticket an embedding was produced from: subject and description, or resolution notes.
  Module:     search
  Related:    EntityEmbedding
```

```
Glossary: Breach risk
  Definition: The model's probability, 0 to 1, that an open ticket breaches its SLA before resolution.
  Module:     prediction
  Related:    Ticket, ModelPrediction
```

```
Glossary: Observation instant
  Definition: The point in time a feature row is computed as at, so training never sees later facts.
  Module:     prediction
  Related:    TicketFeatureSet
```

```
Glossary: Passthrough feature
  Definition: A feature copied unchanged from its source because it is a contractual constant, not an observation.
  Module:     prediction
  Related:    TicketFeatureSet
```

```
Glossary: Satisfaction coverage
  Definition: The share of closed tickets that carry a satisfaction score.
  Module:     observability
  Related:    Ticket
```

```
Glossary: Freshness
  Definition: The age of the newest ticket loaded; the timeliness check warns at 24 hours and fails at 48.
  Module:     observability
  Related:    Ticket
```

```
Glossary: Orphaned reference
  Definition: A reference to an agent, customer or category that does not exist; any one fails integrity.
  Module:     observability
  Related:    Ticket
```

```
Glossary: Investigation session
  Definition: An agent's multi-step piece of work on a ticket, carried across interactions until it ends or expires.
  Module:     memory
  Related:    AgentSession
```

```
Glossary: Session timeout
  Definition: Twenty-four hours without activity, after which a session is abandoned.
  Module:     memory
  Related:    AgentSession
```

```
Glossary: Learned strategy
  Definition: An approach an agent found effective, kept once validated so later sessions can reuse it.
  Module:     memory
  Related:    LearnedStrategy
```

## Access layer

The three standard tiers, no more. Physical principals and containers come from the
organisation profile.

```
Decision: DD-ACCESS-001
  Title:      Three access tiers, with agent write-back append-only
  Category:   SECURITY
  Module:     access-layer
  Context:    The access-layer pattern requires the role model to be recorded so agents can read the access contract from Memory.
  Rationale:  ROLE_READ serves analysts, managers and BI; ROLE_AGENT serves agents and automated tools with the same read scope plus append-only write-back to Memory's runtime entities and Observability's usage and quality events; ROLE_ADMIN serves the product owner and data steward. Analysts and read-only users need identical grants, and separating agent write-back keeps the agent lifecycle independently manageable.
  Alternatives: Two tiers (read and write), rejected because agent write-back must be manageable on its own; four tiers adding an analyst tier, rejected because analysts need no grant read-only users lack.
```

---

## Sensitive attributes

`Agent.email`, `Customer.contact_name` and `Customer.contact_email` are `[pii]`.
`Ticket.description` and `Ticket.resolution_notes` are `[pii-incidental]`. The organisation
profile maps both markers to its classification scheme and protection policy; the design
names the attributes and stops there.

## Settled decisions

Six of the seven catalogued decisions take the advocated option. `DEC-AUDIT-RETENTION` is
`bounded` rather than `regulatory`, with its reason in the frontmatter: a deliberate
departure, not an oversight. Category departs from the product's keymap allocation and from
the Reference default profile, each recorded above.
