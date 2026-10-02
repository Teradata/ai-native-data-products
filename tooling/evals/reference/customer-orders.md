---
product: Customer Orders
product_code: CUSTORD
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
  - id: DEC-TEMPORAL-PATTERN
    choice: bi-temporal
  - id: DEC-COLUMN-STRATEGY
    choice: reference
    because: agents answering "why did this order change" read order provenance on nearly every lookup, and at 5M rows the two reference attributes cost less than the join they remove from the hot path
  - id: DEC-SURROGATE-ALLOCATION
    choice: keymap
  - id: DEC-DELETE-STRATEGY
    choice: soft-delete
  - id: DEC-TIMESTAMP-ZONE
    choice: zone-aware
  - id: DEC-QUALITY-STORAGE
    choice: observability
  - id: DEC-AUDIT-RETENTION
    choice: regulatory
---

# Customer Orders: Design Specification

```
Product: -
  Description:    Customer orders, their lines and products, for order analytics, product search and reorder prediction.
  Domain:         Retail sales
  Owner:          Sales operations
  Technical contact: Data engineering
  Trust producer: the Customer Orders validation pipeline, run by the product owner
```

The fixture the standards are tested against. It is re-validated on every test run, so a
change to `design/` that would invalidate a conforming design fails the build.

It is deliberately small: six entities, an ordinary retail model, nothing worth arguing
about. What it covers is chosen, not incidental, and the reasoning is in
[the evals README](../README.md).

It takes the full **AI-Native Data Product** composition, so every module's contracts and
all thirty-six invariants are exercised.

---

## Composition

| Module | Included | Why |
|---|---|---|
| Domain | yes | The business entities. The composition root. |
| Semantic | yes | Discovery map over the entities. |
| Search | yes | Similarity over product descriptions. |
| Prediction | yes | A reorder-propensity feature and its model outputs. |
| Observability | yes | Change events, quality, lineage. |
| Memory | yes (both facets) | Design memory and agent runtime state. |

Every `[hard]` requirement is met inside the composition. Search and Prediction
hard-depend on Domain for `EntityJoinBack`, which Domain provides; the rest are satisfied
by `self` or the platform. No soft requirement goes unmet, so no feature is disabled.

The Access Layer deploys in the standard two phases.

---

## Domain

Six entities covering all four kinds. `Order` and `Product` relate many-to-many through
`OrderLine`, which is what makes an associative entity the right shape here rather than a
plain reference.

```
Entity: Customer                  [kind: History] [profile: SCD2_BITEMPORAL]
  customer_id      : Identifier                        // surrogate; stable across all versions
  legal_name       : ShortText [required] [pii]        // registered name
  email            : ShortText [optional] [pii]        // contact address
  region_code      : Code [required]                   // trading region
  is_current       : Flag [current-flag]               // current version marker
  is_deleted       : Flag [deleted-flag]               // soft-delete marker

  Keys:
    surrogate: customer_id

  Volume:
    initial: 200000
    growth:  2000 per month
    horizon: 3 years

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
Entity: Product                   [kind: History] [profile: SCD2_BITEMPORAL]
  product_id       : Identifier                        // surrogate; stable across all versions
  product_name     : ShortText [required]              // display name
  description      : Text [optional]                   // the text Search embeds
  is_current       : Flag [current-flag]               // current version marker
  is_deleted       : Flag [deleted-flag]               // soft-delete marker

  Keys:
    surrogate: product_id

  Volume:
    initial: 20000
    growth:  200 per month
    horizon: 3 years

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - SurrogateKeyAllocation
    - CurrentStateFilter
    - NaturalKeyLookup
    - RichMetadata
```

```
Entity: Order                     [kind: History] [profile: SCD2_BITEMPORAL]
  order_id         : Identifier                        // surrogate; stable across all versions
  customer_id      : Reference [required] [-> Customer]  // the ordering customer
  order_status     : Code [required]                   // status, from OrderStatus
  ordered_dts      : Timestamp [required]              // when the order was placed
  order_total      : Decimal(12,2) [required]          // gross order value
  change_event_id  : Reference [optional] [-> ChangeEvent]  // per DEC-COLUMN-STRATEGY: reference
  is_current       : Flag [current-flag]               // current version marker
  is_deleted       : Flag [deleted-flag]               // soft-delete marker

  Keys:
    surrogate: order_id

  Volume:
    initial: 5000000
    growth:  150000 per month
    horizon: 3 years

  Synonyms: basket, sale

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - SurrogateKeyAllocation
    - CurrentStateFilter
    - PointInTimeReconstruction
    - EntityJoinBack
    - RichMetadata
```

```
Entity: OrderLine                 [kind: Relationship] [profile: ASSOCIATION_SCD2] [allocation: inline]
  order_line_id    : Identifier                        // surrogate for the association
  order_id         : Reference [required] [-> Order]     // the order
  product_id       : Reference [required] [-> Product]   // the product ordered
  quantity         : Integer [required]                // units ordered
  line_value       : Decimal(12,2) [required]          // extended line value
  is_current       : Flag [current-flag]               // current version marker

  Keys:
    surrogate: order_line_id
    natural:   order_id, product_id

  Volume:
    initial: 15000000
    growth:  450000 per month
    horizon: 3 years

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
Entity: OrderStatus               [kind: Reference] [profile: SCD2_HISTORY] [allocation: inline]
  order_status_id  : Identifier                        // surrogate for the entry
  order_status_code: Code [required] [unique]          // status code used by Order; natural key
  short_description: ShortText [required]              // label for reports
  long_description : Text [optional]                   // definition and usage guidance
  is_current       : Flag [current-flag]               // marks the current version of the code
  sort_order       : Integer [optional]                // display sequence

  Keys:
    surrogate: order_status_id
    natural:   order_status_code

  Volume:
    initial: 8
    growth:  0 per year
    horizon: 3 years

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - CurrentStateFilter
    - PointInTimeReconstruction
    - RichMetadata
```

`OrderStatus` versions on the default `SCD2_HISTORY` profile: a status label can be
reworded, and an order placed last year should still read back with the wording that
was current when it was placed. The validity pair comes from the temporal pattern and
is not restated here, exactly as for `Customer` above.

`Customer`, `Product` and `Order` are reference targets, so each allocates its surrogate through a keymap, and its natural key lives on that keymap alone. A customer's account number is personal data in some jurisdictions; holding it in one place is what lets it be protected in one place. `OrderLine` and `OrderStatus` are referenced by nothing, so they allocate inline.

```
Entity: CustomerKeymap          [kind: Keymap] [profile: CURRENT_STATE] [allocates: Customer]
  customer_id      : Identifier                        // allocated once per natural key
  customer_key     : NaturalKey [required] [unique]    // account number from the ordering system
  source_system    : ShortText [optional]              // system that introduced the key
  created_dts      : Timestamp [required]              // allocation time; immutable

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
Entity: ProductKeymap           [kind: Keymap] [profile: CURRENT_STATE] [allocates: Product]
  product_id       : Identifier                        // allocated once per natural key
  product_key      : NaturalKey [required] [unique]    // SKU from the ordering system
  source_system    : ShortText [optional]              // system that introduced the key
  created_dts      : Timestamp [required]              // allocation time; immutable

  Keys:
    surrogate: product_id
    natural:   product_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - SurrogateKeyAllocation
    - RichMetadata
```

```
Entity: OrderKeymap             [kind: Keymap] [profile: CURRENT_STATE] [allocates: Order]
  order_id         : Identifier                        // allocated once per natural key
  order_key        : NaturalKey [required] [unique]    // order number from the ordering system
  source_system    : ShortText [optional]              // system that introduced the key
  created_dts      : Timestamp [required]              // allocation time; immutable

  Keys:
    surrogate: order_id
    natural:   order_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - SurrogateKeyAllocation
    - RichMetadata
```

**Invariants:** `INV-DOMAIN-001`, `INV-DOMAIN-002`, `INV-DOMAIN-003`, `INV-DOMAIN-004`,
`INV-DOMAIN-005`, `INV-DOMAIN-006`, `INV-DOMAIN-007`.

---

## Semantic

Every entity above, plus the Search, Prediction, Observability, and Memory entities,
registers on deploy through `SemanticRegistration`. The relationship graph carries
Customer to Order, and Order to Product through OrderLine.

The orientation relation lists the product's resources in `discovery_order` with the
trust map ordered before every analytical resource, so agents orient and read how far each
area can be trusted before touching data. The manifest is a generated view over the registry and that
orientation relation, so it cannot drift from the metadata it summarises.

Consumers resolve the object to query through the access-object registry rather than
object names: each current view is registered against the entity it represents, and the
enriched Order-with-lines view is a `COMPOSITE` whose members (Order as anchor, OrderLine,
Product) are recorded so an agent expands it from metadata. The registry is established
once at deployment from verifiable structure.

Three measures are published. `Average Order Value` is a ratio, and therefore
non-additive: summing it across customers or months gives a wrong answer rather than an
imprecise one. Each is defined in logical terms over the entities above; the platform
binding generates its expressions. Synonyms cover the terms the business uses that the
schema does not: *basket* and *sale* for `Order` (declared on the entity), *revenue* for
`Order Value`.

```
Metric: Order Value
  Description: Gross value of current orders, before returns.
  Dataset:     Order
  Measure:     sum(Order.order_total)
  Filter:      Order.is_current = true and Order.is_deleted = false
  Grain:       Order
  Unit:        currency
  Additive:    yes
  Synonyms:    revenue
```

```
Metric: Units Sold
  Description: Units ordered across current order lines.
  Dataset:     OrderLine
  Measure:     sum(OrderLine.quantity)
  Filter:      OrderLine.is_current = true
  Grain:       OrderLine
  Unit:        count
  Additive:    yes
```

```
Metric: Average Order Value
  Description: Order value per current order. A ratio: never summed across groups.
  Dataset:     Order
  Measure:     ratio(metric('Order Value'), count_rows(Order))
  Filter:      Order.is_current = true and Order.is_deleted = false
  Grain:       Order
  Unit:        currency
  Additive:    no
```

```
AccessObject: OrderWithLines
  Kind:    composite
  Anchor:  Order
  Members: OrderLine, Product
  Purpose: An order with its lines and the products ordered, expanded as one unit.
```

```
Orientation: -
  Entrypoint:     access-layer
  Access mode:    VIEW
```

**Invariants:** `INV-SEMANTIC-001`, `INV-SEMANTIC-002`, `INV-SEMANTIC-003`,
`INV-SEMANTIC-004`, `INV-SEMANTIC-005`, `INV-SEMANTIC-006`, `INV-SEMANTIC-007`,
`INV-SEMANTIC-008`, `INV-SEMANTIC-009`, `INV-SEMANTIC-010`,
`INV-SEMANTIC-011`, `INV-SEMANTIC-012`, `INV-SEMANTIC-013`,
`INV-SEMANTIC-014`, `INV-SEMANTIC-015`.

---

## Search

Embeddings over `Product.description`, the only free text in the model. Keys only; the
embedding joins back to Domain for content.

```
Embedding: product_description
  Entity:     Product
  Source:     Product.description
  Where:      is_not_null(Product.description)
  Dimensions: 768
  Similarity: cosine
  Index:      exact
  Refresh:    on load
```

```
Decision: DD-SEARCH-001
  Title:     Exact similarity search at catalogue scale
  Category:  PERFORMANCE
  Module:    search
  Applies to: product_description
  Context:   Search supports an approximate index for large embedding sets.
  Rationale: Twenty thousand products scan exactly in well under a second, so an index would add maintenance for no gain.
  Alternatives: An approximate index, revisited if the catalogue passes a million products.
```

```
Entity: ProductEmbedding          [kind: History] [profile: SCD2_HISTORY] [module: search] [allocation: inline]
  product_embedding_id : Identifier                    // surrogate for the embedding
  product_id           : Reference [required] [-> Product]  // key only; no content duplication
  embedding            : Vector[768] [required]        // dense embedding of the description
  embedding_model      : ShortText [required]          // model that produced the vector
  embedding_dimensions : Integer [required]            // dimensionality, for reproducibility
  is_current           : Flag [current-flag]           // current embedding for this product

  Keys:
    surrogate: product_embedding_id
    natural:   product_id, embedding_model

  Volume:
    initial: 20000
    growth:  200 per month
    horizon: 3 years

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - EntityJoinBack
    - CurrentStateFilter
    - RichMetadata
    - AccessView
```

**Invariants:** `INV-SEARCH-001`, `INV-SEARCH-002`, `INV-SEARCH-003`, `INV-SEARCH-004`,
`INV-SEARCH-005`.

---

## Prediction

One engineered feature and the model outputs it drives. Features reference Domain and
join back; no Domain content is copied.

```
Model: reorder
  Subject:  Customer
  Features: CustomerFeature
  Target:   Whether the customer places another order within 30 days.
  Output:   probability
  Scoring:  daily
```

```
Entity: CustomerFeature           [kind: History] [profile: SCD2_HISTORY] [module: prediction] [allocation: inline]
  customer_feature_id : Identifier                     // surrogate for the feature row
  customer_id         : Reference [required] [-> Customer]  // the subject
  reorder_propensity  : Decimal(5,4) [optional] [derive: count_related(Order, Order.ordered_dts, 90 days) / coalesce(count_related(Order, Order.ordered_dts, 365 days), 1)]  // share of the last year's orders placed in the last 90 days
  observation_dts     : Timestamp [required]           // as-at instant for the feature
  is_current          : Flag [current-flag]            // current feature version

  Keys:
    surrogate: customer_feature_id
    natural:   customer_id

  Volume:
    initial: 200000
    growth:  200000 per month
    horizon: 3 years

  Features:
    subject: Customer
    as of:   CustomerFeature.observation_dts
    storage: wide
    refresh: daily

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

**Invariants:** `INV-PRED-001`, `INV-PRED-002`, `INV-PRED-003`, `INV-PRED-004`,
`INV-PRED-005`.

---

## Observability

Change events, quality metrics, and lineage for every module. Under
`DEC-COLUMN-STRATEGY: reference`, `Order` carries a reference to its change event and
nothing more; lineage and quality are reached by joining on the entity reference and
presented through `AccessView`.

```
Quality: -
  Weights:
    completeness: 40%
    validity: 25%
    consistency: 20%
    timeliness: 15%
  Rules:
    - completeness(Customer.legal_name): pass >= 0.99, warn >= 0.95
    - validity(OrderLine.quantity > 0): pass >= 1.0, warn >= 0.99
    - integrity(Order.customer_id): fail on any
    - integrity(OrderLine.product_id): fail on any
    - freshness(Order): warn after 24 hours, fail after 48 hours
  Frequency: on load
```

```
Lineage: -
  Flows:
    - ordering.customers -> load_customers -> Customer
    - ordering.products -> load_products -> Product
    - ordering.orders -> load_orders -> Order
    - ordering.order_lines -> load_order_lines -> OrderLine
  Scope: Source to Domain; Search and Prediction lineage is derived from Domain.
```

```
Retention: -
  ChangeEvent:      7 years
  LineageRun:       2 years
  DataLineage:      life of product
  AgentSession:     90 days after close
  AgentInteraction: 1 years
  LearnedStrategy:  2 years
```

**Invariants:** `INV-OBS-001`, `INV-OBS-002`, `INV-OBS-003`, `INV-OBS-004`,
`INV-OBS-005`, `INV-OBS-006`, `INV-OBS-007`, `INV-OBS-008`, `INV-OBS-009`.

---

## Memory

Both facets. The documentation facet holds the settled decisions below, the glossary
terms this product introduces, and a query cookbook. The runtime facet holds agent
sessions and learned strategies. Retention for both is in the Observability section's
`Retention:` block.

```
Runtime: -
  Session timeout: 8 hours
```

```
Glossary: Order Value
  Definition: Gross value of an order before returns; the measure the business calls revenue.
  Module:     semantic
  Related:    Order
```

```
Glossary: Reorder propensity
  Definition: How likely a customer is to order again soon, as the share of the last year's orders placed in the last 90 days.
  Module:     prediction
  Related:    Customer, CustomerFeature
```

```
Glossary: SKU
  Definition: The stock-keeping unit that identifies a product in the ordering system.
  Module:     domain
  Related:    Product
```

**Invariants:** `INV-MEMORY-001`, `INV-MEMORY-002`, `INV-MEMORY-003`,
`INV-MEMORY-004`, `INV-MEMORY-005`, `INV-MEMORY-006`.

---

## Sensitive attributes

`Customer.legal_name` and `Customer.email` are flagged `[pii]`. The platform binding
applies its protection mechanism; the design names the attributes and stops there.

---

## Settled decisions

Six of the seven take the advocated option. `DEC-AUDIT-RETENTION` is `regulatory`
because the product holds personal data, so erasure records outlive the data they
describe.

`DEC-COLUMN-STRATEGY` is settled as `reference` rather than the advocated `offload`,
with the reason recorded in the frontmatter: order provenance is on the hot path for
nearly every agent lookup, and at this volume two reference attributes cost less than
the join they remove. The departure is deliberate. Without one, the requirement that a
non-advocated choice carries its reason would never execute here, and could rot
untested.
