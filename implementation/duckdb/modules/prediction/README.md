---
title: DuckDB Prediction Module Implementation
anchor: prediction
type: implementation
status: standard
version: 2.0
normative: true
implements: prediction
platform: duckdb
---

# DuckDB Prediction

Binding of [Prediction](../../../../design/modules/prediction.md). [schema.sql](schema.sql) chooses tall engineered values and versioned model outputs. Wide feature groups are an alternative model choice, not a second required copy of the same values.

**Provides:**

| Capability | Binding |
|---|---|
| `PointInTimeReconstruction` | Half-open feature history plus observation cutoff. |
| `CurrentStateFilter` | Canonical current feature and prediction views. |
| `AccessView` | Current, enriched and `training_at(t)` surfaces. |

Spend intensity clips aggregate AUD spend divided by 1000 to [0,1]; no customer descriptive attributes are copied. Definitions and model metadata are Semantic-owned; lineage and quality are Observability-owned. The score is reproducible as one minus the exact feature snapshot and has no calibrated predictive claim.

The example's snapshot computation filters each source entity as-of observation_dts and includes transactions posted strictly before it. Feature validity cannot precede availability. Prediction records the exact feature observation timestamp and model version; training joins Domain at the same historical instant. Source-observation joins, bounds and scoring reconstruction are runnable checks.

`DD-PREDICTION-001` records the departure from advocated bitemporal history: this small fixture has no as-known correction use case. The writer rejects retrospective feature corrections. A production design needing those must add a bitemporal profile rather than silently rewriting old feature knowledge. No claim is made that business-time SCD2 alone solves every late-source leakage problem.

Tests cover January/February boundaries, future-feature exclusion, source joins, prediction provenance and absence of raw content. Soft deletion and metadata follow the shared compiler/writer.
