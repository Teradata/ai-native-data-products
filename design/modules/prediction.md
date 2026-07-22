# Prediction Module — Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Prediction module — the feature store: engineered features, model outputs, point-in-time training data |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/modules/prediction/`](../../implementation/teradata/modules/prediction/) |

Prediction is the feature store. Like Search, it is an **enhancement** module that hard-depends on
Domain — it references Domain entities and joins back for raw context.

---

## 1. Purpose

Prediction stores **engineered features** for ML training and serving with **point-in-time
correctness** and **feature discoverability**.

| AI-native characteristic | Purpose |
|--------------------------|---------|
| **Feature engineering** | Features are transformed, normalised, aggregated — not raw copies. |
| **Normalised scaling** | Features scaled to a common range (typically 0–1) for equal weighting in training. |
| **Point-in-time correctness** | Features reconstructable exactly as they existed historically (no leakage). |
| **Feature discoverability** | Agents discover available features without human direction. |
| **Training/serving consistency** | The same features serve training and inference. |

---

## 2. Scope and Boundaries

**In scope:** engineered feature values (and their history), feature groups, model predictions
(scores, classes, confidence), and optionally training datasets.

**Out of scope:**

| Concern | Owning module |
|---------|---------------|
| Feature definitions / computation metadata | Semantic |
| Source entity data (raw values) | Domain — join back for it |
| Feature monitoring / drift | Observability |
| Vector embeddings | Search |

**Engineering requirement (`INV-PRED-001`).** The feature store holds *engineered* values —
normalised, transformed, aggregated — **not** raw copies of Domain columns. A feature that is just a
domain column with no transformation must not be duplicated here; it is obtained by join-back.
`recency_score = 1 − days_since_last / 365` belongs here; `legal_name`, `birth_date`, raw
`credit_limit` do not. Selective duplication is acceptable **only** for documented low-latency scoring
exceptions.

---

## 3. Entity Model

Two storage patterns are supported; a designer chooses per feature set (and may mix them). Both are
versioned (`SCD2_HISTORY`) and reference Domain by the generic-reference pattern. Content is obtained
by join-back; raw domain values are never copied (`INV-PRED-003`).

```
Entity: FeatureGroup              [kind: History]     — WIDE format
  feature_group_id      : Identifier
  entity_id             : Reference [required]         — Domain entity (id only)
  entity_kind           : Enum{PARTY|PRODUCT|DOCUMENT} — generic-reference discriminator
  <feature>             : Decimal(5,4) [optional]      — ENGINEERED, normalised 0–1; designer-supplied
  observation_at        : Timestamp [required]         — when observed/computed (point-in-time)
  is_current            : Flag [current-flag]
  feature_group_name    : ShortText [required]
  feature_group_version : ShortText [optional]         — feature-engineering logic version

Entity: FeatureValue              [kind: History]     — TALL format
  feature_value_id : Identifier
  entity_id        : Reference [required]
  entity_kind      : Enum{PARTY|PRODUCT|DOCUMENT}
  feature_name     : ShortText [required]
  feature_group    : ShortText [optional]
  value_numeric    : Decimal(18,4) [optional]          — normalised 0–1 where appropriate
  value_text       : Text [optional]
  value_json       : Json [optional]
  value_type       : Enum{NUMERIC|TEXT|JSON|BOOLEAN} [required]
  observation_at   : Timestamp [required]
  is_current       : Flag [current-flag]
  feature_version  : ShortText [optional]

Entity: ModelPrediction           [kind: History]
  prediction_id          : Identifier
  entity_id              : Reference [required]
  entity_kind            : Enum{PARTY|PRODUCT|DOCUMENT}
  model_key              : ShortText [required]
  model_version          : ShortText [required]
  prediction_value       : Decimal(10,6) [optional]    — score / probability / continuous output
  prediction_class       : ShortText [optional]        — classification label
  prediction_json        : Json [optional]             — multi-class or structured output
  confidence_score       : Decimal(5,4) [optional]     — 0–1
  predicted_at           : Timestamp [required]
  feature_observation_at : Timestamp [optional]        — links the prediction to its feature timestamp (reproducibility)
  is_current             : Flag [current-flag]
```

**Pattern choice:** wide when features are dense and always accessed together; tall when features are
sparse, dynamic, or mixed-type.

---

## 4. Point-in-Time Correctness

Using current features to train on a historical label causes **data leakage**. Prediction guarantees
features are reconstructable as they existed at any past instant (`INV-PRED-002`), by applying the
`temporal-lifecycle-metadata` pattern: each feature carries `observation_at` plus the pattern's
validity period, aligned with the Domain entity's temporal tracking. Training as-of a date selects the
feature version valid at that date and joins to the Domain entity state valid at the same date. This
is the `PointInTimeReconstruction` capability, shared with Domain.

---

## 5. Applied Patterns

| Pattern | Contribution to Prediction |
|---------|----------------------------|
| `temporal-lifecycle-metadata` | The `SCD2_HISTORY` versioning that makes point-in-time reconstruction correct. |
| `object-placement` | Which container the feature tables and views live in, and who may reach them. |
| `access-layer` | Standard current / enriched / point-in-time views exposed to consumers. |
| `validation` | The conformance checks run before the module is declared done. |

---

## 6. Capabilities and Composition

Prediction is an **enhancement** module: it hard-depends on Domain (features reference Domain
entities and join back for context), so it cannot be deployed alone — valid as an add-on to an
existing Domain. See the
[composition mechanism](../core/DESIGN_LANGUAGE.md#62-provision-requirement-and-composition).

**Provides:** engineered feature values and model predictions, to agents and model-serving.

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

- **Prediction + Domain** — features reference Domain entities by `Identifier` and join back for raw
  values; engineered values live here, raw values stay in Domain, views join them (no duplication).
- **Prediction + Semantic** — feature *definitions* and computation metadata live in Semantic; feature
  *values* live here (`INV-PRED-004`). Agents read Semantic to learn what features mean, then read
  Prediction for the values.
- **Prediction + Observability** — feature drift and quality are monitored in Observability, not here
  (`INV-PRED-005`); model performance metrics are Observability's `ModelPerformance`.

---

## 8. Invariants

- `INV-PRED-001`: the feature store holds engineered features (transformed / normalised / aggregated), never raw copies of Domain columns.
- `INV-PRED-002`: features are point-in-time reconstructable — feature observation and validity align with Domain temporal tracking, so training uses features as they existed (no leakage).
- `INV-PRED-003`: features reference Domain entities by `Identifier` and obtain raw context by join-back; no Domain content is duplicated, except documented low-latency exceptions recorded as design decisions.
- `INV-PRED-004`: feature definitions and computation metadata live in Semantic; feature values live here.
- `INV-PRED-005`: feature monitoring, drift, and model-performance metrics live in Observability, not here.

---

## 9. Designer Responsibilities

**Designers supply:** the feature list and computation logic; the storage pattern (wide/tall) per
feature set; feature groups; source dependencies; refresh frequency; retention policy; the feature
definitions registered in Semantic.

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Features are engineered, not raw copies of Domain columns (`INV-PRED-001`); any low-latency duplication is documented.
- [ ] Reference to Domain uses the generic-reference pattern and obtains raw context by join-back (`INV-PRED-003`).
- [ ] Temporal columns support point-in-time reconstruction aligned with Domain (`INV-PRED-002`).
- [ ] Feature definitions registered in Semantic; values in Prediction (`INV-PRED-004`).
- [ ] Current / enriched / point-in-time views exist (`AccessView`).
- [ ] Feature entities registered in the Semantic map (`SemanticRegistration`); documentation captured.
- [ ] Every invariant has a check in the implementation.
- [ ] This document passes the design linter with no ignore directive.

---

## 10. Implementation

The Teradata binding — the wide and tall feature tables, the prediction table, the current / enriched
/ point-in-time views, and the invariant checks — lives in
[`implementation/teradata/modules/prediction/`](../../implementation/teradata/modules/prediction/).
Other platforms add sibling directories under `implementation/` without changing this document.

---

**End of Prediction Module Design Standard**
