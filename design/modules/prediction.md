---
title: Prediction Module
anchor: prediction
type: module
status: standard
version: 2.0
normative: true
---

# Prediction Module: Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Prediction module: the feature store: engineered features, model outputs, point-in-time training data |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | `implementation/{platform}/modules/prediction/`, one per platform |

Prediction is the feature store. Like Search, it is an **enhancement** module that hard-depends on Domain: it references Domain entities and joins back for raw context.

---

## 1. Purpose

Prediction stores **engineered features** for ML training and serving with **point-in-time correctness** and **feature discoverability**.

| AI-native characteristic | Purpose |
|--------------------------|---------|
| **Feature engineering** | Features are transformed, encoded, aggregated: not raw copies. |
| **Declared derivations** | Every feature is an expression in the platform-neutral vocabulary, so it computes the same on every platform. |
| **Point-in-time correctness** | Features reconstructable exactly as they existed historically (no leakage). |
| **Feature discoverability** | Agents discover available features without human direction. |
| **Training/serving consistency** | The same features serve training and inference. |

---

## 2. Scope and Boundaries

**In scope:** engineered feature values (and their history), feature groups, model predictions (scores, classes, confidence), and optionally training datasets.

**Out of scope:**

| Concern | Owning module |
|---------|---------------|
| Feature definitions / computation metadata | Semantic |
| Source entity data (raw values) | Domain: join back for it |
| Feature monitoring / drift | Observability |
| Vector embeddings | Search |

**Engineering requirement (`INV-PRED-001`).** The feature store holds *engineered* values, transformed, encoded, aggregated, **not** raw copies of Domain columns. A feature that is just a domain column with no transformation must not be duplicated here; it is obtained by join-back. A recency feature, `[derive: days_since_last(<Event>, <Event>.<event>_dts)]`, belongs here; `legal_name`, `birth_date`, raw `credit_limit` do not. Selective duplication is acceptable **only** for documented low-latency scoring exceptions.

The expression vocabulary has no population scaling: nothing rescales a feature against the other rows. A designer who wants a bounded value expresses the bound in the derivation itself, with `map` or `when`; scaling across the population is the model's own preprocessing, not a stored feature.

**Where a passthrough is legitimate.** The exception above is real and needs a boundary, or every untransformed column arrives claiming it. Not all Domain attributes are business observations: some are configuration the business set, which a model consumes as a constant rather than as something measured. A passthrough is acceptable when all three hold:

1. The attribute is a **contractual or configuration constant**, not an observed business value.
2. It does **not vary over the entity's history** in a way that would leak future information into a past training row.
3. The reason is recorded as a design decision, naming which of the two categories it falls in.

A contracted `sla_hours` is the canonical yes: the business set it, the model treats it as a bound, and transforming it would only obscure what it is. A `priority_label` or a `subject_text` is the canonical no: both are observations, both vary, and copying them here duplicates Domain content and calls it a feature. The distinction is what the value *is*, not whether arithmetic was applied to it.

---

## 3. Entity Model

Features are declared as `[derive:]` attributes of a **feature group** entity, which carries a `Features:` section naming its subject, its point-in-time anchor, its storage and its refresh ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §3.5). Every derived attribute is a feature, written in the expression vocabulary of that standard's section 5. A feature group whose name does not identify the module declares `[module: prediction]`. Feature and prediction entities reference Domain by the generic-reference pattern; content is obtained by join-back and raw domain values are never copied (`INV-PRED-003`).

Feature and prediction entities version per their declared profile: the History default the product's `DEC-TEMPORAL-PATTERN` gives (`SCD2_BITEMPORAL` under the advocated option, shown below), or `SCD2_HISTORY` where the designer declares it. Each has no business identifier of its own, so it declares its identity as a natural key over its references and discriminators and allocates `inline`.

```
Entity: <Subject>FeatureSet       [kind: History] [profile: SCD2_BITEMPORAL] [allocation: inline] [module: prediction]
  feature_group_id: Identifier  // surrogate for the feature row
  entity_id: Reference [required] [-> <Subject>]  // the featurised Domain entity (id only)
  entity_kind: Enum{<SUBJECT>} [required]  // generic-reference discriminator; a feature group has one subject
  <feature>: <LogicalType> [optional] [derive: <expression>]  // ENGINEERED; one attribute per feature, designer-supplied
  observation_dts: Timestamp [required]  // the point-in-time anchor every feature is computed as at
  is_current: Flag [current-flag]
  feature_group_name: ShortText [required]  // this feature group
  feature_group_version: ShortText [required]  // feature-engineering logic version

  Keys:
    surrogate: feature_group_id
    natural:   entity_kind, entity_id, feature_group_version

  Volume:
    initial: <rows at first load>
    growth:  <count> per <day|month|year>
    horizon: <duration>

  Features:
    subject: <Subject>
    as of:   <Subject>FeatureSet.observation_dts
    storage: wide
    refresh: daily
```

Feature attributes, for a customer subject, look like this:

```
  orders_90d: Integer [optional] [derive: count_related(Order, Order.ordered_dts, 90 days)]  // orders in the 90 days before the anchor
  spend_90d: Decimal(18,2) [optional] [derive: sum_related(Order.order_value, Order.ordered_dts, 90 days)]  // spend over the same window
  days_since_order: Decimal(10,4) [optional] [derive: days_since_last(Order, Order.ordered_dts)]  // recency; absent when there is no order
  tier_rank: Integer [optional] [derive: map(as_of(Customer.tier, CustomerFeatureSet.observation_dts), {Gold: 1, Silver: 2, Bronze: 3})]  // tier as at the anchor
```

Windowed aggregates use `count_related`, `sum_related` and `days_since_last`, which look back from the `as of` anchor over rows that reference the subject.

**Storage.** The `Features:` section's `storage` chooses the shape. `wide` keeps one attribute per feature on the feature group. `tall` makes the build create the standard-owned `FeatureValue` relation, one row per feature value, and the pivot between it and the feature group (Design Specification Standard §4.1); the specification declares only the feature group either way. Wide suits features that are dense and always read together; tall suits features that are sparse, dynamic, or mixed-type.

```
Entity: FeatureValue              [kind: History] [profile: SCD2_BITEMPORAL] [allocation: inline]  // TALL format; standard-owned
  feature_value_id: Identifier
  entity_id: Reference [required] [-> <Entity1> | <Entity2>] [discriminator: entity_kind]
  entity_kind: Enum{<ENTITY1>|<ENTITY2>} [required]
  feature_name: ShortText [required]  // the feature attribute's name
  feature_group: ShortText [required]  // the feature group it is declared on
  value_numeric: Decimal(18,4) [optional]
  value_text: Text [optional]
  value_json: Json [optional]
  value_type: Enum{NUMERIC|TEXT|JSON|BOOLEAN} [required]
  observation_dts: Timestamp [required]
  is_current: Flag [current-flag]
  feature_version: ShortText [required]

  Keys:
    surrogate: feature_value_id
    natural:   entity_kind, entity_id, feature_group, feature_name, feature_version
```

`FeatureValue` takes the profile of the feature groups it pivots.

```
Entity: ModelPrediction           [kind: History] [profile: SCD2_BITEMPORAL] [allocation: inline]
  prediction_id: Identifier
  entity_id: Reference [required] [-> <Entity1> | <Entity2>] [discriminator: entity_kind]
  entity_kind: Enum{<ENTITY1>|<ENTITY2>} [required]
  model_key: ShortText [required]  // the Model block's name
  model_version: ShortText [required]
  prediction_value: Decimal(10,6) [optional]  // score / probability / continuous output
  prediction_class: ShortText [optional]  // classification label
  prediction_json: Json [optional]  // multi-class or structured output
  confidence_score: Decimal(5,4) [optional]  // 0-1
  prediction_dts: Timestamp [required]
  feature_observation_dts: Timestamp [optional]  // links the prediction to its feature timestamp (reproducibility)
  is_current: Flag [current-flag]

  Keys:
    surrogate: prediction_id
    natural:   entity_kind, entity_id, model_key, model_version

  Volume:
    initial: <rows at first load>
    growth:  <count> per <day|month|year>
    horizon: <duration>
```

**Models.** Each model is declared in a `Model:` block (Design Specification Standard §4.3), which names what it scores, the feature group it reads, what it predicts, the form of its output, and when scores are produced:

```
Model: <model_name>
  Subject:  <Subject>
  Features: <Subject>FeatureSet
  Target:   <what the model predicts, in business terms>
  Output:   probability
  Scoring:  daily
```

---

## 4. Point-in-Time Correctness

Using current features to train on a historical label causes **data leakage**. Prediction guarantees features are reconstructable as they existed at any past instant (`INV-PRED-002`), by applying the `temporal-lifecycle-metadata` pattern: each feature carries `observation_dts` plus the validity period of its declared profile, aligned with the Domain entity's temporal tracking. Every feature is computed as at the `Features:` section's `as of` anchor: windowed aggregates look back from it, and `as_of` reads another entity as it stood at it, so no derivation sees a value recorded later. Training as-of a date selects the feature version valid at that date and joins to the Domain entity state valid at the same date. This is the `PointInTimeReconstruction` capability, shared with Domain.

---

## 5. Applied Patterns

| Pattern | Contribution to Prediction |
|---------|----------------------------|
| `temporal-lifecycle-metadata` | The versioning each feature and prediction entity declares in its `profile` (`SCD2_BITEMPORAL` or `SCD2_HISTORY`), which makes point-in-time reconstruction correct. |
| `object-placement` | Where the feature tables and views are placed, what they are called, and who may reach them: all from the organisation profile, never from the design. |
| `access-layer` | Standard current / enriched / point-in-time views exposed to consumers. |
| `validation` | The conformance checks run before the module is declared done. |

---

## 6. Capabilities and Composition

Prediction is an **enhancement** module: it hard-depends on Domain (features reference Domain entities and join back for context), so it cannot be deployed alone, though it is valid as an add-on to an existing Domain. See the [composition mechanism](../core/DESIGN_LANGUAGE.md).

**Provides:**

| Capability | Made available to |
|------------|-------------------|
| `PointInTimeReconstruction` | Model training and scoring, as the guarantee that a feature can be read as it stood at any past instant: the module's reason for existing. |
| `CurrentStateFilter` | Agents and serving paths reading only current feature values. |
| `AccessView` | Consumers, as current / enriched / point-in-time views over feature values and model predictions with explicit column contracts. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `EntityJoinBack` | `[hard]` | `module:Domain` | Features reference a Domain entity and join back for raw context. Without Domain, Prediction cannot be deployed. |
| `PointInTimeReconstruction` | `[hard]` | `self` | Reconstruct features as at any past instant (no leakage). |
| `CurrentStateFilter` | `[hard]` | `self` | Restrict to current feature values. |
| `AccessView` | `[hard]` | `self` | Current / enriched / point-in-time views with explicit column contracts. |
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on every feature. |
| `SemanticRegistration` | `[soft]` | `module:Semantic` | Register feature entities in the Semantic map; feature *definitions* live in Semantic. |
| `DocumentationCapture` | `[soft]` | `module:Memory` | Record design decisions when Memory is present. |

---

## 7. Integration with Other Modules

- **Prediction + Domain**: features reference Domain entities by `Identifier` and join back for raw values; engineered values live here, raw values stay in Domain, views join them (no duplication).
- **Prediction + Semantic**: feature *definitions* and computation metadata live in Semantic; feature *values* live here (`INV-PRED-004`). Agents read Semantic to learn what features mean, then read Prediction for the values.
- **Prediction + Observability**: feature drift and quality are monitored in Observability, not here (`INV-PRED-005`); model performance metrics are Observability's `ModelPerformance`.

---

## 8. Invariants

- `INV-PRED-001`: the feature store holds engineered features (transformed, encoded or aggregated), never raw copies of Domain columns, except passthroughs that meet the three conditions and carry their decision.
- `INV-PRED-002`: features are point-in-time reconstructable. Feature observation and validity align with Domain temporal tracking, so training uses features as they existed, without leakage.
- `INV-PRED-003`: features reference Domain entities by `Identifier` and obtain raw context by join-back; no Domain content is duplicated, except documented low-latency exceptions recorded as design decisions.
- `INV-PRED-004`: feature definitions and computation metadata live in Semantic; feature values live here.
- `INV-PRED-005`: feature monitoring, drift, and model-performance metrics live in Observability, not here.

---

## 9. Designer Responsibilities

**Designers supply:**

| Element | Recorded as |
|---------|-------------|
| Features and their computation | `[derive:]` attributes of a feature group entity. Each expression is the feature's definition, registered in Semantic (`INV-PRED-004`), and names the sources it reads. |
| Feature groups | Feature group entities, each with a `Features:` section: `subject`, `as of`, `storage` (`wide` or `tall`) and `refresh`. |
| Refresh frequency | The `Features:` section's `refresh` for features; the `Model:` block's `Scoring` for predictions. |
| Models | `Model:` blocks: subject, feature group, target, output, scoring. |
| Volume | The `Volume:` section of each feature group and prediction entity. |
| Retention | A line per feature and prediction entity in the specification's `Retention:` block. |
| Passthroughs | A decision per passthrough feature, naming which of the two categories it falls in. |

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Every feature is a `[derive:]` attribute in the expression vocabulary; every feature group has a `Features:` section, and every model a `Model:` block.
- [ ] Features are engineered, not raw copies of Domain columns (`INV-PRED-001`); every passthrough meets the three conditions and carries its decision.
- [ ] Reference to Domain uses the generic-reference pattern and obtains raw context by join-back (`INV-PRED-003`).
- [ ] Temporal columns support point-in-time reconstruction aligned with Domain (`INV-PRED-002`).
- [ ] Feature definitions registered in Semantic; values in Prediction (`INV-PRED-004`).
- [ ] Current / enriched / point-in-time views exist (`AccessView`).
- [ ] Feature entities registered in the Semantic map (`SemanticRegistration`); documentation captured.
- [ ] Every invariant has a check in the implementation.
- [ ] This document passes the design linter with no ignore directive.

---

### 9.1 Decisions to settle

These are the catalogued decisions a Prediction module design must settle. The recommendation is this standard's default; the question is what shifts it. The design skill walks a designer through each one at design time and records the answer in the product's own design.


| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-TEMPORAL-PATTERN` | `bi-temporal` | Point-in-time correctness is the module's reason for existing: departing from this option reintroduces feature leakage. Feature and prediction entities version per their declared profile, so a product that settles `scd2` declares `SCD2_HISTORY` on them and loses transaction time. |
| `DEC-DELETE-STRATEGY` | `soft-delete` | Does an explanation of a past prediction need the feature values as they stood? |
| `DEC-TIMESTAMP-ZONE` | `zone-aware` | Are features computed or served across regions? |

Every settled decision is recorded as part of designing the product: see *Capturing the Design* in the [Master Design](../core/MASTER_DESIGN.md) for the destination and the record set. This module's decisions take the id prefix `DD-PREDICTION-<NNN>`; the module part may instead be a recognisable short form, such as `DD-PRED-<NNN>`, used consistently across the product (the Memory module's capture protocol). They typically fall under `SCHEMA` (the feature set, passthroughs, point-in-time anchors), `ARCHITECTURE` (wide or tall storage), and `OPERATIONAL` (refresh and scoring).

---

## 10. Implementation

Each platform binding provides the wide and tall feature tables, the prediction table, the current, enriched, and point-in-time views, and the invariant checks, in `implementation/{platform}/modules/prediction/`, and conforms to the [Platform Implementation Authoring Standard](../core/IMPLEMENTATION_AUTHORING.md). Adding a platform changes nothing in this document.

---

**End of Prediction Module Design Standard**
