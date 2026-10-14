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

## Templates

`01-tables.sql.j2` calls `module_tables('prediction')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). It creates the feature and prediction entities the specification assigns to Prediction, with the columns, keys, sequences and temporal profile the context resolves for each. The temporal pattern adds their consumer views and point-in-time table macros.

No template computes features or scores. Product feature SQL must apply both effective and knowledge-time cutoffs to each source and respect observation and availability time. Definitions belong to Semantic and monitoring to Observability; Domain context is reached by identifier join-back, not copied into feature or prediction rows. Prediction tables begin empty: no score or model quality is fabricated. A point-in-time training function and a retrospective-rewrite guard are not rendered; see [conformance scope](../../CONFORMANCE.md).

## Capability bindings

| Capability | Binding |
|---|---|
| `PointInTimeReconstruction` | Point-in-time table macro per versioned feature or prediction relation. Cutoff correctness is a product obligation. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `AccessView` | One consumer view per relation with a `consumer_view` object. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-PRED-001,003` | Review the specification's features; only engineered values and Domain identifiers belong here. |
| `INV-PRED-002` | Point-in-time macros support reconstruction; the product's feature pipeline must prove cutoff correctness. |
| `INV-PRED-004,005` | Semantic and Observability stores are separate; product capture and lineage checks remain required. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
