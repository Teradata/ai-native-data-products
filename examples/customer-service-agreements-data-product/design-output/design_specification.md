---
product: Customer Service Agreements
product_code: CSA
composition: custom
modules:
  - domain
  - semantic
  - search
  - prediction
  - observability
  - memory
facets:
  - memory:documentation
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
    choice: regulatory
---

# Customer Service Agreements: Design Specification

The design phase's output for the Customer Service Agreements example, produced from
[`CSA_Reference_Brief.md`](../CSA_Reference_Brief.md) and the source data in
[`data/`](../data/). It is the build input: every fact a builder needs is in the frontmatter
or a notation block defined by the
[Design Specification Standard](../../../design/core/DESIGN_SPECIFICATION.md), and it names no
platform, container or principal, so it builds on any conforming platform under any
organisation profile. Prose explains; it is never the only statement of a fact.

This is reference output, kept so implementations can be compared. Validate it with:

```bash
python tooling/evals/spec_lint.py examples/customer-service-agreements-data-product/design-output/design_specification.md
```

---

## Business purpose

```
Product: -
  Description:       The provider's customers, their service contracts and contracted service levels, and the service credits paid when those levels are missed.
  Domain:            Customer contracts and commercial management
  Owner:             Commercial operations
  Technical contact: Commercial systems team
  Trust producer:    the agreements validation pipeline, run by the commercial data steward
```

The commercial record of every customer the provider serves: who they are, which contract
they are on, what service levels and credits that contract promises per priority, and which
credits have been paid. It is the system of record for a customer's tier, which the service
desk reads.

**Consumers:** account managers (renewal pipeline, contract terms); finance (contract value,
credits paid); commercial analysts (renewal risk, credit exposure); AI agents answering
"which contracts say X" over the contract text.

**Use cases:** list contracts up for renewal, with their value and notice period; score each
active contract's risk of not renewing; find contracts whose terms contain a given clause or
something like it; report contract value and credits paid by tier, region and month; trace a
contract back through the contracts it renewed.

## Composition

Domain, Semantic, Search, Prediction, Observability and the Memory documentation facet, with
the access layer: the AI-Native composition without Memory's runtime facet, so a free
composition rather than a named one. Every `[hard]` requirement is met inside it: Search and
Prediction hard-depend on Domain for `EntityJoinBack`, which Domain provides. The runtime facet
is absent by design (`DD-MEM-001`): agents query this product statelessly, so no session state
is kept.

---

## Domain

Four business entities. `Customer` and `Contract` are `History` entities on the bi-temporal
profile with keymap allocation: a tier change or a contract amendment is often agreed after the
date it takes effect, and the renewal model must not see it before it was recorded.
`ServiceLevelTerm` is a `History` detail of a contract, allocated inline. `ServiceCredit` is a
`Record`: a credit, once paid, is never amended, only reversed by another.

This product is the system of record for `Customer`. The IT Service Desk product holds its own
`Customer` with the same customer numbers (CUST-nnn); the two are not linked by the design,
because the design language has no reference to another product's entity, and they are known to
disagree for some customers on tier, name and start date. A credit's ticket is that product's
ticket number, held unenforced in `ticket_key` (`DD-DOMAIN-004`).

```
Entity: Customer                  [kind: History] [profile: SCD2_BITEMPORAL]
  customer_id           : Identifier                                 // surrogate; stable across all versions
  legal_name            : ShortText [required]                       // registered legal name
  trading_name          : ShortText [required]                       // name the customer trades and is known by
  industry              : ShortText [required]                       // industry sector
  tier                  : Enum{Platinum|Gold|Silver|Bronze} [required]  // contracted service tier; this product is its system of record
  region                : ShortText [required]                       // trading region: ANZ or APAC
  billing_country       : ShortText [required]                       // country invoices are issued to
  billing_contact_email : ShortText [optional] [pii]                 // accounts-payable address
  account_manager       : ShortText [required]                       // account team that owns the relationship
  customer_since        : Date [required]                            // first day of the customer's first contract
  is_current            : Flag [current-flag]                        // current version marker
  is_deleted            : Flag [deleted-flag]                        // soft-delete marker

  Description: An organisation the provider has contracted to serve.

  Keys:
    surrogate: customer_id

  Volume:
    initial: 21
    growth:  2 per month
    horizon: 7 years

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
    - EntityJoinBack
    - RichMetadata
```

```
Entity: Contract                  [kind: History] [profile: SCD2_BITEMPORAL]
  contract_id            : Identifier                                // surrogate; stable across all versions
  customer_id            : Reference [required] [-> Customer]        // the contracting customer
  renewal_of_contract_id : Reference [optional] [-> Contract]        // the contract this one renewed; absent for a first contract
  contract_type          : Enum{Managed service|Support only|Project} [required]  // what the contract buys
  start_date             : Date [required]                           // first day of the term
  end_date               : Date [required]                           // last day of the term
  status                 : Enum{Draft|Active|Renewed|Expired|Terminated} [required]  // where the contract is in its life
  annual_value           : Decimal(12,2) [required]                  // annual contract value
  currency               : ShortText [required]                      // ISO currency of the value
  auto_renew             : Flag [required]                           // renews unless notice is given
  notice_period_days     : Integer [required]                        // days' notice needed not to renew
  signed_dts             : Timestamp [required]                      // when the contract was signed
  terms_text             : Text [required]                           // the contract's service terms, as written
  is_current             : Flag [current-flag]                       // current version marker
  is_deleted             : Flag [deleted-flag]                       // soft-delete marker

  Description: A service contract between the provider and a customer, for one term.

  Keys:
    surrogate: contract_id

  Volume:
    initial: 48
    growth:  2 per month
    horizon: 7 years

  Synonyms: agreement, SLA, MSA

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
Entity: ServiceLevelTerm          [kind: History] [profile: SCD2_BITEMPORAL] [allocation: inline]
  service_level_term_id : Identifier                          // surrogate for the term
  contract_id           : Reference [required] [-> Contract]  // the contract the term belongs to
  priority              : Enum{P1|P2|P3|P4} [required]        // ticket priority the term applies to
  response_hours        : Integer [required]                  // hours to first response
  resolution_hours      : Integer [required]                  // hours to resolution
  credit_percent        : Decimal(5,2) [required]             // share of the monthly fee credited per breached ticket
  is_current            : Flag [current-flag]                 // current version marker
  is_deleted            : Flag [deleted-flag]                 // soft-delete marker

  Description: The response time, resolution time and service credit one contract promises for one ticket priority.

  Keys:
    surrogate: service_level_term_id
    natural:   contract_id, priority

  Volume:
    initial: 184
    growth:  8 per month
    horizon: 7 years

  Synonyms: service level, SLA target

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - CurrentStateFilter
    - PointInTimeReconstruction
    - EntityJoinBack
    - RichMetadata
```

```
Entity: ServiceCredit             [kind: Record] [profile: EVENT_APPEND_ONLY] [allocation: inline]
  service_credit_id   : Identifier                          // surrogate for the credit
  service_credit_code : NaturalKey [required] [unique]      // credit note number, SC-nnnn
  contract_id         : Reference [required] [-> Contract]  // the contract credited
  ticket_key          : ShortText [optional]                // the breached ticket, as the IT Service Desk product's ticket number; absent for a credit not tied to one ticket
  service_month       : Date [required]                     // first day of the month the credit applies to
  credit_amount       : Decimal(12,2) [required]            // amount credited, in the contract's currency
  reason              : Text [required]                     // why the credit was paid
  issued_dts          : Timestamp [required]                // when the credit note was issued

  Description: A service credit paid to a customer, once, against one contract.

  Keys:
    surrogate: service_credit_id
    natural:   service_credit_code

  Volume:
    initial: 9
    growth:  4 per month
    horizon: 7 years

  Synonyms: credit note, SLA credit, penalty

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
Entity: CustomerKeymap            [kind: Keymap] [profile: CURRENT_STATE] [allocates: Customer]
  customer_id   : Identifier                       // allocated once per natural key; never reused
  customer_key  : NaturalKey [required] [unique]   // customer number, CUST-nnn, shared with the service desk
  source_system : ShortText [optional]             // system that introduced the key

  Description: Allocates each customer's stable identifier from its customer number, once.

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
Entity: ContractKeymap            [kind: Keymap] [profile: CURRENT_STATE] [allocates: Contract]
  contract_id   : Identifier                       // allocated once per natural key; never reused
  contract_key  : NaturalKey [required] [unique]   // contract number, CTR-nnnn
  source_system : ShortText [optional]             // system that introduced the key

  Description: Allocates each contract's stable identifier from its contract number, once.

  Keys:
    surrogate: contract_id
    natural:   contract_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - SurrogateKeyAllocation
    - RichMetadata
```

```
Decision: DD-DOMAIN-001
  Title:      Service level terms allocate inline
  Category:   SCHEMA
  Module:     domain
  Applies to: ServiceLevelTerm
  Context:    The product allocates surrogates through keymaps.
  Rationale:  A term has no business identifier of its own; its identity is its contract and priority, and nothing references it. A keymap would allocate from a key that is already the entity's natural key.
  Alternatives: A ServiceLevelTermKeymap keyed on contract and priority.
```

```
Decision: DD-DOMAIN-002
  Title:      Service credits are append-only records
  Category:   ARCHITECTURE
  Module:     domain
  Applies to: ServiceCredit
  Context:    A credit note is a financial document: once issued it is never edited, and a mistake is corrected by a reversing note.
  Rationale:  The Record kind on the EVENT_APPEND_ONLY profile states that, so no consumer looks for versions; the credit's number is its natural key and is allocated inline because nothing references a credit.
  Alternatives: A History entity, which would permit an issued credit to be versioned.
```

```
Decision: DD-DOMAIN-003
  Title:      Renewals are a self-reference on Contract
  Category:   ARCHITECTURE
  Module:     domain
  Applies to: Contract
  Context:    A customer's contracts form a chain, each renewing the one before.
  Rationale:  Each contract renews at most one other, so a single optional reference carries the chain; walking it gives a customer's contract history and its renewal count.
  Alternatives: A ContractRenewal Relationship entity, unnecessary while a renewal joins exactly two contracts.
```

```
Decision: DD-DOMAIN-004
  Title:      Ticket numbers from the service desk are held unenforced
  Category:   INTEGRATION
  Module:     domain
  Applies to: ServiceCredit
  Context:    A credit is paid for a breached ticket, and tickets belong to the IT Service Desk product.
  Rationale:  The design language references only entities in the same product, so the ticket's number is kept as ShortText. Nothing in this product can check it; a consumer resolves it through the service desk product.
  Alternatives: No ticket on the credit, which loses the audit trail from credit to incident.
```

```
Decision: DD-DOMAIN-005
  Title:      This product is the system of record for a customer's tier
  Category:   INTEGRATION
  Module:     domain
  Applies to: Customer
  Context:    The service desk product holds a Customer with a tier too, and the two can disagree.
  Rationale:  A tier is what a contract buys, so the commercial record is authoritative. The service desk's copy is a consumer's copy; reconciling it is a question across products that this design records but cannot settle.
  Alternatives: Leaving ownership unstated, which leaves a consumer to guess which tier to trust.
```

The source columns map to these attributes on ingest: `customer_id` and `contract_id` in the
source are the keymaps' natural keys; `signed_at` and `issued_at` become `signed_dts` and
`issued_dts`; a credit's `service_credit_id` becomes `service_credit_code` and its `ticket_id`
becomes `ticket_key`. The customer file carries one row per version, from its `valid_from`.

**Invariants:** `INV-DOMAIN-001`, `INV-DOMAIN-002`, `INV-DOMAIN-003`, `INV-DOMAIN-004`,
`INV-DOMAIN-005`, `INV-DOMAIN-006`, `INV-DOMAIN-007`.

---

## Semantic

Every entity in every module registers on deploy with its declared temporal profile. The
relationship catalogue covers every reference above, including the renewal chain, and the
joins from Search and Prediction back to Contract.

```
Orientation: -
  Entrypoint:     access-layer
  Access mode:    VIEW
```

```
Metric: Active Contracts
  Description: Contracts in their term, counting each once at its current version.
  Dataset:     Contract
  Measure:     count_rows(Contract)
  Filter:      Contract.is_current = true and Contract.is_deleted = false and Contract.status = 'Active'
  Grain:       Contract
  Unit:        count
  Additive:    yes
```

```
Metric: Annual Contract Value
  Description: Annual value of active contracts.
  Dataset:     Contract
  Measure:     sum(Contract.annual_value)
  Filter:      Contract.is_current = true and Contract.is_deleted = false and Contract.status = 'Active'
  Grain:       Contract
  Unit:        Australian dollars
  Additive:    yes
  Synonyms:    ACV, contract value
```

```
Metric: Service Credits Paid
  Description: Total of service credits issued.
  Dataset:     ServiceCredit
  Measure:     sum(ServiceCredit.credit_amount)
  Grain:       ServiceCredit
  Unit:        Australian dollars
  Additive:    yes
  Synonyms:    SLA credits, penalties paid
```

```
Metric: Auto-renew Share
  Description: Share of active contracts that renew unless notice is given. A ratio: never summed across groups.
  Dataset:     Contract
  Measure:     ratio(sum(when(Contract.auto_renew, 1, 0)), count_rows(Contract))
  Filter:      Contract.is_current = true and Contract.is_deleted = false and Contract.status = 'Active'
  Grain:       Contract
  Unit:        percent
  Additive:    no
```

```
Decision: DD-SEM-001
  Title:      The entity model is custom
  Category:   ARCHITECTURE
  Module:     semantic
  Context:    The Semantic module records the source of the entity model.
  Rationale:  No open standard covers service contracts at this scope. Customer follows the organisation fields of Schema.org's Organization where they overlap; the rest is custom.
```

```
Decision: DD-DISCOVERY-001
  Title:      Agents enter through the access layer, by view
  Category:   ARCHITECTURE
  Module:     semantic
  Applies to: Orientation
  Context:    The orientation layer requires the approved entrypoint and access mode to be settled and explained.
  Rationale:  The access layer is the only consumer-readable surface the role model grants. Agents orient through the product registry, read the trust map, then follow the catalogue resources; clause search starts from the similarity function.
```

```
Decision: DD-SEM-002
  Title:      One trust-authoritative producer
  Category:   ARCHITECTURE
  Module:     semantic
  Applies to: Orientation
  Context:    The manifest must name exactly one producer whose trust map is authoritative.
  Rationale:  The agreements validation pipeline, run by the commercial data steward, publishes the canonical validation evidence in Observability.
```

**Invariants:** `INV-SEMANTIC-001`, `INV-SEMANTIC-002`, `INV-SEMANTIC-003`,
`INV-SEMANTIC-004`, `INV-SEMANTIC-005`, `INV-SEMANTIC-006`, `INV-SEMANTIC-007`,
`INV-SEMANTIC-008`, `INV-SEMANTIC-009`, `INV-SEMANTIC-010`, `INV-SEMANTIC-011`,
`INV-SEMANTIC-012`, `INV-SEMANTIC-013`, `INV-SEMANTIC-014`, `INV-SEMANTIC-015`, `INV-SEMANTIC-016`, `INV-SEMANTIC-017`, `INV-SEMANTIC-018`, `INV-SEMANTIC-019`, `INV-SEMANTIC-020`.

---

## Search

One `EntityEmbedding` entity, as the Search module defines it, with one embedding per contract
of its service terms. Absence is no row, never a null vector.

```
Entity: EntityEmbedding           [kind: History] [profile: SCD2_HISTORY] [allocation: inline]
  embedding_id            : Identifier                           // surrogate for the embedding record
  entity_id               : Reference [required] [-> Contract] [discriminator: entity_kind]  // the embedded contract; key only
  entity_kind             : Enum{CONTRACT} [required]            // always CONTRACT in this product
  source_attribute        : ShortText [required]                 // which embedding: the Embedding block name
  embedding               : Vector[384] [required]               // dense text embedding
  embedding_dimensions    : Integer [required]                   // recorded for reproducibility
  embedding_model         : ShortText [required]                 // model that produced the vector
  embedding_model_version : ShortText [optional]                 // model version
  generated_dts           : Timestamp [required]                 // when the vector was generated
  is_current              : Flag [current-flag]                  // current embedding per contract and source

  Description: Vector embeddings of contract terms, one per contract.

  Keys:
    surrogate: embedding_id
    natural:   entity_kind, entity_id, source_attribute

  Volume:
    initial: 48
    growth:  2 per month
    horizon: 7 years

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
Embedding: contract_terms
  Entity:     Contract
  Source:     Contract.terms_text
  Dimensions: 384
  Model:      bge-small-en-v1.5
  Similarity: cosine
  Index:      exact
  Threshold:  0.70
  Refresh:    on load
```

```
Decision: DD-SEARCH-001
  Title:      Contracts are embedded whole, not clause by clause
  Category:   ARCHITECTURE
  Module:     search
  Applies to: contract_terms
  Context:    A question about a clause could be answered from an embedding per clause.
  Rationale:  The source holds the terms as one text, and the contracts are short; one embedding per contract answers "which contracts are like this one" and finds a clause well enough at this size. Clause-level embedding needs the terms split at source, recorded as the upgrade path.
  Alternatives: An embedding per clause, discriminated by source_attribute.
```

```
Decision: DD-SEARCH-002
  Title:      Exact similarity search at this volume
  Category:   PERFORMANCE
  Module:     search
  Applies to: contract_terms
  Context:    Search supports an approximate index for large embedding sets.
  Rationale:  A few hundred contracts over seven years scan exactly in milliseconds.
```

```
Decision: DD-SEARCH-003
  Title:      A lower similarity threshold than the service desk's
  Category:   OPERATIONAL
  Module:     search
  Applies to: contract_terms
  Context:    Contract terms are assembled from a small set of standard clauses, so contracts are more alike than tickets are.
  Rationale:  At 0.70 a search returns contracts sharing most of their clauses; a higher threshold returns only near-identical ones.
```

**Invariants:** `INV-SEARCH-001`, `INV-SEARCH-002`, `INV-SEARCH-003`, `INV-SEARCH-004`,
`INV-SEARCH-005`.

---

## Prediction

The target is the probability, 0 to 1, that an active contract is not renewed at the end of
its term. Features are computed as at the observation instant, and the customer's tier is read
as it stood then. A contract's renewal is learned from the contracts that ended before it: one
with a successor that renews it was renewed, one marked `Expired` or `Terminated` was not.

The service desk's breach history would be the strongest feature, and this product cannot
reach it (`DD-PRED-002`); the credits this product pays stand in for it.

```
Entity: ContractFeatureSet        [kind: History] [profile: SCD2_HISTORY] [module: prediction] [allocation: inline]
  feature_group_id      : Identifier                             // surrogate for the feature row
  entity_id             : Reference [required] [-> Contract]     // the featurised contract; key only
  entity_kind           : Enum{CONTRACT} [required]              // always CONTRACT
  f_contract_type_int   : Integer [optional] [derive: map(Contract.contract_type, {'Managed service': 1, 'Support only': 2, Project: 3})]  // contract type
  f_customer_tier_int   : Integer [optional] [derive: map(as_of(Customer.tier, ContractFeatureSet.observation_dts), {Platinum: 1, Gold: 2, Silver: 3, Bronze: 4})]  // tier as it stood at observation
  f_term_days           : Decimal(10,2) [optional] [derive: days_between(Contract.start_date, Contract.end_date)]  // length of the term in days
  f_notice_period_days  : Integer [optional] [derive: Contract.notice_period_days]  // notice needed not to renew
  f_auto_renew          : Flag [optional] [derive: Contract.auto_renew]  // renews unless notice is given
  f_credits_365d        : Decimal(12,2) [optional] [derive: sum_related(ServiceCredit.credit_amount, ServiceCredit.issued_dts, 365 days)]  // credits paid in the last year
  f_credit_count_90d    : Integer [optional] [derive: count_related(ServiceCredit, ServiceCredit.issued_dts, 90 days)]  // credits paid in the last 90 days
  f_days_since_credit   : Decimal(10,2) [optional] [derive: days_since_last(ServiceCredit, ServiceCredit.issued_dts)]  // days since the last credit; absent if none
  observation_dts       : Timestamp [required]                   // point-in-time anchor
  feature_group_name    : ShortText [required]                   // this feature group
  feature_group_version : ShortText [optional]                   // feature logic version
  is_current            : Flag [current-flag]                    // current feature row per contract

  Description: Engineered features about a contract, as at an observation instant, for renewal-risk prediction.

  Keys:
    surrogate: feature_group_id
    natural:   entity_id

  Volume:
    initial: 21
    growth:  2 per month
    horizon: 7 years

  Features:
    subject: Contract
    as of:   ContractFeatureSet.observation_dts
    storage: wide
    refresh: monthly

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
  prediction_id           : Identifier                          // surrogate for the prediction
  entity_id               : Reference [required] [-> Contract]  // the scored contract; key only
  entity_kind             : Enum{CONTRACT} [required]           // always CONTRACT
  model_key               : ShortText [required]                // the Model block name
  model_version           : ShortText [required]                // model version
  prediction_value        : Decimal(10,6) [optional]            // probability of not renewing, 0 to 1
  prediction_class        : ShortText [optional]                // unused by this model
  prediction_json         : Json [optional]                     // unused by this model
  confidence_score        : Decimal(5,4) [optional]             // model confidence, 0 to 1
  prediction_dts          : Timestamp [required]                // when scored
  feature_observation_dts : Timestamp [optional]                // the feature row scored
  is_current              : Flag [current-flag]                 // latest score per contract

  Description: Scores the renewal-risk model produces for contracts, one version per scoring event.

  Keys:
    surrogate: prediction_id
    natural:   entity_id, model_key

  Volume:
    initial: 21
    growth:  25 per month
    horizon: 7 years

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
Model: renewal_risk
  Subject:  Contract
  Features: ContractFeatureSet
  Target:   Whether an active contract is not renewed at the end of its term; learned from contracts whose term has ended.
  Output:   probability
  Scoring:  monthly, on demand
```

```
Decision: DD-PRED-001
  Title:      Notice period and auto-renew are passthrough features
  Category:   SCHEMA
  Module:     prediction
  Applies to: ContractFeatureSet
  Context:    Prediction features are engineered unless all three passthrough conditions hold.
  Rationale:  Both are contractual terms the parties set, not observations; neither leaks the outcome; the model reads them as stated, and transforming them would obscure what they are.
```

```
Decision: DD-PRED-002
  Title:      Service desk breach history is not a feature in this cycle
  Category:   INTEGRATION
  Module:     prediction
  Applies to: ContractFeatureSet
  Context:    How often a customer's tickets breached is the likeliest predictor of a contract not renewing, and tickets belong to the IT Service Desk product.
  Rationale:  A derivation reaches only this product's entities, and a feature group reads only them. Credits paid stand in for breaches, under-counting them by every breach no credit was paid for. Revisit when products can consume one another.
  Alternatives: Copying ticket counts into this product, which duplicates another product's data.
```

```
Decision: DD-PRED-003
  Title:      Features refresh monthly
  Category:   OPERATIONAL
  Module:     prediction
  Applies to: ContractFeatureSet
  Context:    Renewal decisions are taken over months, and credits are issued monthly.
  Rationale:  A monthly refresh after the credit run captures every change a feature can see; scoring on demand covers an account review between runs.
```

**Invariants:** `INV-PRED-001`, `INV-PRED-002`, `INV-PRED-003`, `INV-PRED-004`,
`INV-PRED-005`.

---

## Observability

Change events, quality metrics and lineage for every module, at table level. Credits are
issued monthly, so the product is stale when no credit has been issued for five weeks. The
graph-lineage facet is not enabled, so `INV-OBS-007`, `INV-OBS-008` and `INV-OBS-009` apply
only if it is enabled later.

```
Quality: -
  Weights:
    completeness: 25%
    validity: 30%
    consistency: 25%
    accuracy: 10%
    timeliness: 10%
  Rules:
    - completeness(Customer.billing_contact_email): pass >= 0.95, warn >= 0.80
    - validity(Contract.end_date >= Contract.start_date): pass >= 1.0, warn >= 1.0
    - validity(Contract.annual_value > 0): pass >= 1.0, warn >= 1.0
    - consistency(ServiceLevelTerm.resolution_hours >= ServiceLevelTerm.response_hours): pass >= 1.0, warn >= 0.99
    - validity(ServiceCredit.credit_amount > 0): pass >= 1.0, warn >= 1.0
    - integrity(Contract.customer_id): fail on any
    - integrity(Contract.renewal_of_contract_id): fail on any
    - integrity(ServiceLevelTerm.contract_id): fail on any
    - integrity(ServiceCredit.contract_id): fail on any
    - freshness(ServiceCredit): warn after 35 days, fail after 62 days
  Frequency: on load, monthly
```

```
Lineage: -
  Flows:
    - customers.csv -> load_customers -> Customer
    - contracts.csv -> load_contracts -> Contract
    - service_level_terms.csv -> load_service_levels -> ServiceLevelTerm
    - service_credits.csv -> load_credits -> ServiceCredit
  Scope: Source files into Domain; Search and Prediction lineage is derived from Domain.
```

```
Retention: -
  ChangeEvent:       2 years queryable, 7 years archived
  DataQualityMetric: 2 years queryable, 7 years archived
  LineageRun:        2 years queryable, 7 years archived
  AgentOutcome:      2 years queryable, 7 years archived
  DataLineage:       life of product
```

Retention is `regulatory`: contracts and credit notes are financial records kept seven years,
so audit and execution records are queryable for two years and archived for seven.
Definitional lineage is kept for the life of the product (`INV-OBS-004`).

```
Decision: DD-OBS-001
  Title:      Freshness is measured on credits issued
  Category:   OPERATIONAL
  Module:     observability
  Applies to: Quality
  Context:    Contracts change rarely, so their newest row says little about whether the load is running.
  Rationale:  Credits are issued every month the service levels are missed, which is nearly every month across the customer base; five weeks without one means the monthly run did not load, and nine weeks means two did not.
```

```
Decision: DD-OBS-002
  Title:      Credits are not reconciled with the service desk here
  Category:   INTEGRATION
  Module:     observability
  Applies to: Quality
  Context:    A credit's ticket_key names a ticket in the IT Service Desk product, and whether that ticket breached is that product's fact.
  Rationale:  No rule in this product can read another product, so whether each credited ticket exists and breached is recorded as an open gap, not claimed as checked.
```

**Invariants:** `INV-OBS-001`, `INV-OBS-002`, `INV-OBS-003`, `INV-OBS-004`,
`INV-OBS-005`, `INV-OBS-006`, `INV-OBS-007`, `INV-OBS-008`, `INV-OBS-009`.

---

## Memory

The documentation facet only. All six documentation entities deploy and capture every decision
in this specification, catalogued and product, as a `DesignDecision`; the capture floor applies
per module.

```
Decision: DD-MEM-001
  Title:      No runtime facet
  Category:   ARCHITECTURE
  Module:     memory
  Context:    Memory's runtime facet holds agent sessions, interactions and learned strategies.
  Rationale:  Agents ask this product single questions (a clause search, a renewal list, a contract's terms) and carry no investigation across them, so there is no session state to keep.
  Alternatives: Both facets, as in the service desk product.
```

**Invariants:** `INV-MEMORY-001`, `INV-MEMORY-002`, `INV-MEMORY-003`, `INV-MEMORY-004`,
`INV-MEMORY-005`, `INV-MEMORY-006`.

---

## Glossary

The terms this product introduces, three per module for Memory's capture floor.

```
Glossary: Service tier
  Definition: The service level a customer buys, Platinum to Bronze, which sets its contracts' service level terms; this product is its system of record.
  Module:     domain
  Related:    Customer, ServiceLevelTerm
```

```
Glossary: Service credit
  Definition: Money credited to a customer when a ticket misses its contracted resolution time, as a share of the monthly fee.
  Module:     domain
  Related:    ServiceCredit, ServiceLevelTerm
```

```
Glossary: Renewal chain
  Definition: A customer's contracts in order, each renewing the one before.
  Module:     domain
  Related:    Contract
```

```
Glossary: Annual contract value
  Definition: What a contract is worth per year, before credits.
  Module:     semantic
  Related:    Contract
```

```
Glossary: Notice period
  Definition: The days' notice a party must give before the end of the term not to renew an auto-renewing contract.
  Module:     semantic
  Related:    Contract
```

```
Glossary: Contracted resolution time
  Definition: The hours within which a contract promises a ticket of a given priority is resolved; it differs by tier and may differ from the service desk's own target.
  Module:     semantic
  Related:    ServiceLevelTerm
```

```
Glossary: Similar contract
  Definition: A contract whose terms are at least 0.70 cosine-similar to the one in hand.
  Module:     search
  Related:    Contract, EntityEmbedding
```

```
Glossary: Clause
  Definition: One provision of a contract's terms, such as its coverage hours, credit cap or data residency.
  Module:     search
  Related:    Contract
```

```
Glossary: Terms embedding
  Definition: The embedding of a contract's whole service terms, used to find contracts with similar clauses.
  Module:     search
  Related:    EntityEmbedding
```

```
Glossary: Renewal risk
  Definition: The model's probability, 0 to 1, that an active contract is not renewed at the end of its term.
  Module:     prediction
  Related:    Contract, ModelPrediction
```

```
Glossary: Credit exposure
  Definition: Credits paid against a contract over a recent window, the stand-in for breach history in the renewal model.
  Module:     prediction
  Related:    ContractFeatureSet, ServiceCredit
```

```
Glossary: Ended contract
  Definition: A contract whose term is over: renewed if a later contract renews it, otherwise expired or terminated.
  Module:     prediction
  Related:    Contract
```

```
Glossary: Credit run
  Definition: The monthly process that issues the month's service credits.
  Module:     observability
  Related:    ServiceCredit
```

```
Glossary: Dangling renewal
  Definition: A contract whose renewed contract does not exist; any one fails integrity.
  Module:     observability
  Related:    Contract
```

```
Glossary: Credit reconciliation
  Definition: Checking each credit's ticket against the service desk, which this product cannot do alone.
  Module:     observability
  Related:    ServiceCredit
```

```
Glossary: System of record
  Definition: The product whose value for a fact is authoritative when products disagree.
  Module:     memory
  Related:    Customer
```

```
Glossary: Cross-product key
  Definition: Another product's natural key held as an attribute, such as a ticket number, which this product records but cannot check.
  Module:     memory
  Related:    ServiceCredit
```

```
Glossary: Financial record
  Definition: A contract or credit note, kept seven years, which sets this product's audit retention.
  Module:     memory
  Related:    Contract, ServiceCredit
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
  Rationale:  ROLE_READ serves account managers, finance and BI; ROLE_AGENT serves agents and automated tools with the same read scope plus append-only write-back of usage and quality events; ROLE_ADMIN serves the commercial data steward. With no runtime facet, the agent tier has no Memory write-back.
```

---

## Sensitive attributes

`Customer.billing_contact_email` is `[pii]`. The organisation profile maps the marker to its
classification scheme and protection policy; the design names the attribute and stops there.
Contract terms are commercially confidential but hold no personal data.

## Settled decisions

All seven catalogued decisions take the advocated option. `ServiceLevelTerm` and
`ServiceCredit` allocate inline, each recorded above.
