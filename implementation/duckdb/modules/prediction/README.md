---
title: DuckDB Prediction Implementation
anchor: prediction
type: implementation
status: draft
version: 2.0
normative: true
implements: prediction
platform: duckdb
---

# DuckDB: Prediction

Binding of [Prediction](../../../../design/modules/prediction.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`01-tables.sql.j2` renders the approved FeatureGroup, tall FeatureValue or ModelPrediction entities supplied by the design. Features, keys, profiles, model identifiers and score types are inputs. Definitions belong to Semantic; monitoring belongs to Observability. Domain context is obtained by identity join-back, not copied into feature or prediction records.

The temporal macros provide SCD2 and bitemporal historical surfaces as DuckDB table macros. Product feature SQL must apply both effective and knowledge-time cutoffs to each source, and respect observation and availability time. A wide feature group and tall values are choices, not mandatory duplicate stores.

Generic checks validate the declared temporal structure; they cannot certify leakage freedom, model calibration or feature correctness. Supply product-specific engineering, training and scoring checks. ITSD inputs describe its ten features and breach probability, but neither trained scores nor retrospective source history are fabricated. The earlier DuckDB reference's bespoke point-in-time training function and retrospective-rewrite guard are not carried by this binding; see [conformance scope](../../CONFORMANCE.md).

## Capability bindings

| Capability | Binding |
|---|---|
| `PointInTimeReconstruction` | Half-open table macros over feature and prediction history. Cutoff correctness is a product obligation. |
| `CurrentStateFilter` | Current views over open validity, current flag and deletion state. |
| `AccessView` | Explicit consumer projections hiding lifecycle and audit fields. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-PRED-001,003` | Product feature design review; only engineered values and Domain identifiers belong here. |
| `INV-PRED-002` | Temporal templates support reconstruction; product feature pipeline must prove cutoff correctness. |
| `INV-PRED-004,005` | Standard metadata and monitoring stores are separate; product capture and lineage checks remain required. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal and lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
