---
title: DuckDB Observability Implementation
anchor: observability
type: implementation
status: draft
version: 2.0
normative: true
implements: observability
platform: duckdb
---

# DuckDB: Observability

Binding of [Observability](../../../../design/modules/observability.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`01-tables.sql.j2` calls `module_tables('observability')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). The relations are those the Observability standard defines and the resolver places: change events, quality metrics, lineage definitions and runs, model performance, agent outcomes, and the validation relations `ValidationRun` and `ValidationArea`. Event relations are append-only by profile; lineage definitions are current-state. Each gets a consumer view from the temporal pattern.

The module's views are rendered elsewhere: `LineageGraph` and `LineageRunLatest` by [Semantic discovery](../semantic/README.md), and `TrustMap` by [Validation](../../patterns/validation/README.md).

Capture is a producer obligation: deployers wire their ingestion, temporal writer and agent runtime to these stores. No trigger or synthetic quality score is emitted, and the maintenance template emits no change event. DuckDB cannot make a table append-only for one writer, so append-only intent is a convention of the writing application. Validation evidence is written by [`validate.py`](../../../../tooling/bindings/README.md) using the placement the manifest carries. Retention is a settled design decision and an operator-managed process; no template deletes records.

## Capability bindings

| Capability | Binding |
|---|---|
| `ChangeEventCapture` | Append-only change-event table; the writer must emit events. |
| `AgentOutcomeCapture` | Append-only agent-outcome table; the host supplies actor identity and redacts parameters. |
| `LineageCapture` | Separate definition and run tables, with the lineage graph and latest-run views over active definitions. |
| `QualityScore` | Quality-metric time series, separate from validation evidence. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-OBS-001,002` | Standard-owned event structures hold table-level references and counts; producer payload review required. |
| `INV-OBS-003,006` | Separate definition and run tables; lineage views read active definitions only. |
| `INV-OBS-004` | Retention is a settled decision; operators prove enforcement. |
| `INV-OBS-005` | Wire 2.1 run and area records appended by the validator; engine tests of failures, errors, staleness and producer selection. |
| `INV-OBS-007..009` | Optional graph-native facet not rendered; no graph identity guarantee claimed. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
