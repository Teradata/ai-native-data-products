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

# Customer Orders: Design Brief

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
Entity: Customer                  [kind: History]
  customer_id      : Identifier                        // surrogate; stable across all versions
  customer_key     : NaturalKey [required] [unique]    // account number from the ordering system
  legal_name       : ShortText [required] [pii]        // registered name
  email            : ShortText [optional] [pii]        // contact address
  region_code      : Code [required]                   // trading region
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
Entity: Product                   [kind: History]
  product_id       : Identifier                        // surrogate; stable across all versions
  product_key      : NaturalKey [required] [unique]    // SKU from the ordering system
  product_name     : ShortText [required]              // display name
  description      : Text [optional]                   // the text Search embeds
  is_current       : Flag [current-flag]               // current version marker
  is_deleted       : Flag [deleted-flag]               // soft-delete marker

  Keys:
    surrogate: product_id
    natural:   product_key

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
Entity: Order                     [kind: History]
  order_id         : Identifier                        // surrogate; stable across all versions
  order_key        : NaturalKey [required] [unique]    // order number from the ordering system
  customer_id      : Reference [required] [-> Customer]  // the ordering customer
  order_status     : Code [required]                   // status, from OrderStatus
  ordered_dts      : Timestamp [required]              // when the order was placed
  order_total      : Decimal(12,2) [required]          // gross order value
  change_event_id  : Reference [optional] [-> ChangeEvent]  // per DEC-COLUMN-STRATEGY: reference
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
Entity: OrderLine                 [kind: Relationship]
  order_line_id    : Identifier                        // surrogate for the association
  order_id         : Reference [required] [-> Order]     // the order
  product_id       : Reference [required] [-> Product]   // the product ordered
  quantity         : Integer [required]                // units ordered
  line_value       : Decimal(12,2) [required]          // extended line value
  is_current       : Flag [current-flag]               // current version marker

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
Entity: OrderStatus               [kind: Reference]
  order_status_id  : Identifier                        // surrogate for the entry
  order_status_code: Code [required] [unique]          // status code used by Order; natural key
  short_description: ShortText [required]              // label for reports
  long_description : Text [optional]                   // definition and usage guidance
  is_current       : Flag [current-flag]               // marks the current version of the code
  sort_order       : Integer [optional]                // display sequence

  Keys:
    surrogate: order_status_id
    natural:   order_status_code

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

```
Entity: CustomerKeymap            [kind: Keymap]
  customer_id      : Identifier                        // allocated once per natural key
  customer_key     : NaturalKey [required] [unique]    // natural key from source
  source_system    : ShortText [optional]              // system that introduced the key
  created_dts      : Timestamp [required]              // allocation time; immutable

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - SurrogateKeyAllocation
    - RichMetadata
```

`Product` and `Order` take the same keymap shape, since both are reference targets.

**Invariants:** `INV-DOMAIN-001`, `INV-DOMAIN-002`, `INV-DOMAIN-003`, `INV-DOMAIN-004`,
`INV-DOMAIN-005`, `INV-DOMAIN-006`, `INV-DOMAIN-007`.

---

## Semantic

Every entity above, plus the Search, Prediction, Observability, and Memory entities,
registers on deploy through `SemanticRegistration`. The relationship graph carries
Customer to Order, and Order to Product through OrderLine.

The orientation relation lists the product's resources in `discovery_order` with the
trust gate ordered before every analytical resource, so agents orient and check trust
before touching data. The manifest is a generated view over the registry and that
orientation relation, so it cannot drift from the metadata it summarises.

**Invariants:** `INV-SEMANTIC-001`, `INV-SEMANTIC-002`, `INV-SEMANTIC-003`,
`INV-SEMANTIC-004`, `INV-SEMANTIC-005`, `INV-SEMANTIC-006`, `INV-SEMANTIC-007`,
`INV-SEMANTIC-011`, `INV-SEMANTIC-012`.

---

## Search

Embeddings over `Product.description`, the only free text in the model. Keys only; the
embedding joins back to Domain for content.

```
Entity: ProductEmbedding          [kind: History]
  product_embedding_id : Identifier                    // surrogate for the embedding
  product_key          : NaturalKey [required]         // the embedded product
  product_id           : Reference [required] [-> Product]  // key only; no content duplication
  embedding            : Vector[768] [required]        // dense embedding of the description
  embedding_model      : ShortText [required]          // model that produced the vector
  embedding_dimensions : Integer [required]            // dimensionality, for reproducibility
  is_current           : Flag [current-flag]           // current embedding for this product

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
Entity: CustomerFeature           [kind: History]
  customer_feature_id : Identifier                     // surrogate for the feature row
  feature_key         : NaturalKey [required]          // feature name and version
  customer_id         : Reference [required] [-> Customer]  // the subject
  reorder_propensity  : Decimal(5,4) [optional]        // engineered; normalised 0-1
  observation_dts     : Timestamp [required]           // as-at instant for the feature
  is_current          : Flag [current-flag]            // current feature version

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

**Invariants:** `INV-OBS-001`, `INV-OBS-002`, `INV-OBS-003`, `INV-OBS-004`,
`INV-OBS-005`, `INV-OBS-006`.

---

## Memory

Both facets. The documentation facet holds the settled decisions below, the glossary
terms this product introduces, and a query cookbook. The runtime facet holds agent
sessions and learned strategies.

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
