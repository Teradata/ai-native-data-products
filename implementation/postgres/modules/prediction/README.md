---
title: PostgreSQL Prediction Implementation
anchor: prediction
type: implementation
status: draft
version: 2.0
normative: true
implements: prediction
platform: postgres
---

# PostgreSQL: Prediction

Binding of [Prediction](../../../../design/modules/prediction.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[schema.sql](schema.sql) holds tall engineered feature history and versioned outputs. Domain attributes are joined, never duplicated. Features and models are defined in Semantic; performance observations and lineage belong to Observability.

`CurrentStateFilter` uses current views. `PointInTimeReconstruction` and `AccessView` use half-open history and the administrative `prediction.training_at(t)` SQL function. Source snapshots use the same observation cutoff for all joins, and transactions must have been posted strictly before it. Feature availability may not follow its validity start. The toy output is exactly one minus clipped spend intensity; it makes no predictive-quality claim.

`PRED`, `JOIN`, `BOUNDARY` and temporal checks validate provenance, cutoffs and reproducibility. Tests verify pre-feature and boundary behavior. The writer rejects retrospective prediction changes: requirements for as-known corrections need a bitemporal design, not rewritten effective history.
