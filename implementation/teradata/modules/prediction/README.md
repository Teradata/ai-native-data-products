---
title: Teradata Prediction Module Implementation
anchor: prediction
type: implementation
status: draft
version: 3.0
normative: true
implements: prediction
platform: teradata
---

# Teradata: Prediction

Binding of [Prediction](../../../../design/modules/prediction.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`01-tables.sql.j2` calls `module_tables('prediction')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). It creates the feature and prediction entities the specification assigns to Prediction, with the columns, keys and temporal profile the context resolves for each. The temporal pattern adds their governed and consumer views.

No template computes features or scores. Product feature SQL must apply both effective and knowledge-time cutoffs to each source and respect observation and availability time. Definitions belong to Semantic and monitoring to Observability; Domain context is reached by identifier join-back, not copied into feature or prediction rows. Prediction tables begin empty: no score or model quality is fabricated.

Feature derivations the specification declares are rendered in the Teradata dialect where the binding declares every function they use. `hours_between` and `days_between` take both instants in UTC and are exact to the microsecond; `as_of` is not declared on any binding, so derivations using it are carried unrendered and reported.

## Capability bindings

| Capability | Binding |
|---|---|
| `PointInTimeReconstruction` | The governed base view carries the full temporal contract and is granted to the read and agent tiers; reads as at an instant apply the profile's predicates to it. Cutoff correctness is a product obligation. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `AccessView` | One consumer view per relation with a `consumer_view` object. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-PRED-001,003` | Review the specification's features; only engineered values and Domain identifiers belong here. |
| `INV-PRED-002` | The governed views support reconstruction; the product's feature pipeline must prove cutoff correctness. |
| `INV-PRED-004,005` | Semantic and Observability stores are separate; product capture and lineage checks remain required. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
