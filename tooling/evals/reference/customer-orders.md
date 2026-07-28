---
product: Customer Orders
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
platform: teradata
decisions:
  - id: DEC-TEMPORAL-PATTERN
    choice: bi-temporal
  - id: DEC-COLUMN-STRATEGY
    choice: offload
  - id: DEC-SURROGATE-ALLOCATION
    choice: keymap
  - id: DEC-DELETE-STRATEGY
    choice: soft-delete
  - id: DEC-TIMESTAMP-ZONE
    choice: zone-aware
  - id: DEC-QUALITY-STORAGE
    choice: observability
  - id: DEC-AUDIT-RETENTION
    choice: bounded
    because: this is a reference fixture with no regulated entity, so a single retention window is sufficient and exercises the non-advocated path
---

# Customer Orders: Design Brief

A deliberately small product used to test the standards. It is the fixture the design
work is checked against after every material change to `design/`, so it is kept dull:
four business entities, one of each Domain entity kind, and no domain complexity worth
arguing about.

It takes the full **AI-Native Data Product** composition, so every module's contracts
and invariants are exercised.

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

Every `[hard]` requirement is met inside the composition: Search and Prediction
hard-depend on Domain for `EntityJoinBack`, which Domain provides, and the remaining
hard requirements are satisfied by `self` or the platform.

The Access Layer is deployed in the standard two phases.

---

## Domain

Four entities, one of each kind.

```
Entity: Customer                  [kind: History]
  customer_id      : Identifier                        // surrogate; stable across all versions
  customer_key     : NaturalKey [required] [unique]    // account number from the ordering system
  legal_name       : ShortText [required]              // registered name
  email            : ShortText [optional] [pii]        // contact address
  region_code      : Code [required]                   // trading region, from Region
  is_current       : Flag [current-flag]               // current version marker
  is_deleted       : Flag [deleted-flag]               // soft-delete marker

  Keys:
    surrogate: customer_id
    natural:   customer_key

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
Entity: Order                     [kind: History]
  order_id         : Identifier                        // surrogate; stable across all versions
  order_key        : NaturalKey [required] [unique]    // order number from the ordering system
  customer_id      : Reference [required] [-> Customer]  // the ordering customer
  order_status     : Code [required]                   // status, from OrderStatus
  ordered_dts      : Timestamp [required]              // when the order was placed
  order_total      : Decimal(12,2) [required]          // gross order value
  is_current       : Flag [current-flag]               // current version marker
  is_deleted       : Flag [deleted-flag]               // soft-delete marker

  Keys:
    surrogate: order_id
    natural:   order_key

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
Entity: OrderStatus               [kind: Reference]
  order_status_id  : Identifier                        // surrogate for the entry
  order_status_code: Code [required] [unique]          // status code used by Order
  short_description: ShortText [required]              // label for reports
  long_description : Text [optional]                   // definition and usage guidance
  effective_date   : Date [required]                   // when the value becomes valid
  expiration_date  : Date [optional]                   // when the value expires
  is_current       : Flag [current-flag]               // currently valid indicator
  sort_order       : Integer [optional]                // display sequence

  Applies patterns:
    - object-placement
    - access-layer

  Requires capabilities:
    - RichMetadata
```

```
Entity: CustomerOrder             [kind: Relationship]
  customer_order_id: Identifier                        // surrogate for the association
  customer_id      : Reference [required] [-> Customer]  // first entity
  order_id         : Reference [required] [-> Order]     // second entity
  relationship_type: Code [required]                   // placed-by, billed-to, shipped-to
  is_current       : Flag [current-flag]               // current version marker

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement
    - access-layer

  Requires capabilities:
    - CurrentStateFilter
    - RichMetadata
```

```
Entity: CustomerKeymap            [kind: Keymap]
  customer_id      : Identifier                        // allocated once per natural key
  customer_key     : NaturalKey [required] [unique]    // natural key from source
  source_system    : ShortText [optional]              // system that introduced the key
  created_at       : Timestamp [required]              // allocation time; immutable

  Requires capabilities:
    - SurrogateKeyAllocation
```

`Order` is referenced by Search and Prediction, so its `Identifier` is allocated
through a keymap on the same terms as `Customer`.

**Invariants to satisfy:** `INV-DOMAIN-001`, `INV-DOMAIN-002`, `INV-DOMAIN-003`,
`INV-DOMAIN-004`, `INV-DOMAIN-005`, `INV-DOMAIN-006`, `INV-DOMAIN-007`.

---

## Semantic

Every Domain, Search, Prediction, Observability, and Memory entity registers itself on
deploy through `SemanticRegistration`. The discovery map carries the entity catalogue,
the column dictionary, the relationship graph (`Customer` to `Order` via
`CustomerOrder`), and the product orientation manifest.

**Invariants to satisfy:** `INV-SEMANTIC-001`, `INV-SEMANTIC-002`, `INV-SEMANTIC-003`,
`INV-SEMANTIC-004`, `INV-SEMANTIC-005`, `INV-SEMANTIC-006`, `INV-SEMANTIC-007`.

---

## Search

One embedding entity over the product-facing text of an `Order`, keys only, joining
back to Domain for content.

```
Entity: OrderEmbedding            [kind: History]
  order_embedding_id: Identifier                       // surrogate for the embedding
  order_key         : NaturalKey [required]            // the embedded order
  order_id          : Reference [required] [-> Order]  // key only; no content duplication
  embedding         : Vector[768] [required]           // dense embedding of the order text
  embedding_model   : ShortText [required]             // model that produced the vector
  is_current        : Flag [current-flag]              // current embedding for this order

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

**Invariants to satisfy:** `INV-SEARCH-001`, `INV-SEARCH-002`, `INV-SEARCH-003`,
`INV-SEARCH-004`, `INV-SEARCH-005`.

---

## Prediction

One engineered feature and one model output. Features reference Domain and join back;
no Domain content is copied.

```
Entity: CustomerFeature           [kind: History]
  customer_feature_id: Identifier                      // surrogate for the feature row
  feature_key        : NaturalKey [required]           // feature name and version
  customer_id        : Reference [required] [-> Customer]  // the subject
  reorder_propensity : Decimal(5,4) [optional]         // engineered; normalised 0-1
  observation_dts    : Timestamp [required]            // as-at instant for the feature
  is_current         : Flag [current-flag]             // current feature version

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

**Invariants to satisfy:** `INV-PRED-001`, `INV-PRED-002`, `INV-PRED-003`,
`INV-PRED-004`, `INV-PRED-005`.

---

## Observability

Change events, quality metrics, and lineage for every module. `DEC-COLUMN-STRATEGY`
is `offload`, so no Domain entity carries audit, lineage, or quality attributes; they
are reached by joining on the entity reference and presented through `AccessView`.

**Invariants to satisfy:** `INV-OBS-001`, `INV-OBS-002`, `INV-OBS-003`, `INV-OBS-004`,
`INV-OBS-005`, `INV-OBS-006`.

---

## Memory

Both facets. The `documentation` facet holds the settled decisions above, the glossary
terms this product introduces, and a query cookbook. The `runtime` facet holds agent
sessions and learned strategies.

**Invariants to satisfy:** `INV-MEMORY-001`, `INV-MEMORY-002`, `INV-MEMORY-003`,
`INV-MEMORY-004`, `INV-MEMORY-005`, `INV-MEMORY-006`.

---

## Sensitive attributes

`Customer.email` is flagged `[pii]`. The platform binding applies its protection
mechanism; the design names the attribute and stops there.

---

## Settled decisions

Six decisions take the advocated option. One does not:

`DEC-AUDIT-RETENTION` is settled as `bounded` rather than the advocated `regulatory`,
because this fixture models no regulated entity and a single retention window is
sufficient. The departure is deliberate: it keeps the non-advocated path exercised, so
a change that breaks the reason-carrying requirement fails here rather than in a real
product.
