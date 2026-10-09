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

`entities.json` declares standard-owned event, quality, lineage-definition, lineage-run, model-performance, outcome, retention and validation structures. `01-tables.sql.j2` renders only the selected module. Event and current-state profiles are distinct; definitions do not receive event retention by accident.

Capture is a producer obligation: deployers wire their ingestion, temporal writer and agent runtime to these stores. There is no automatic audit trigger or synthetic quality score, and the maintenance template does not emit change events. DuckDB cannot make a table append-only for a principal, so append-only intent is a convention of the writing application; enforcement is external.

The shared validator (`tooling/bindings/validate.py`) publishes run, area and check evidence using the standard wire 2.1 fields, including severity-aware area summaries. Missing checks, execution errors and missing ML or operational evidence remain visible. Retention is a supplied design decision and an operator-managed process; templates never silently delete historical records.

## Capability bindings

| Capability | Binding |
|---|---|
| `ChangeEventCapture` | Append-only `change_event` table. The writer must emit events; no trigger is emitted. |
| `AgentOutcomeCapture` | Append-only `agent_outcome` table of aggregate outcomes. The host supplies actor identity and redacts parameters. |
| `LineageCapture` | Active-only `lineage_graph` and `lineage_run_latest` views over separate definition and run tables. |
| `QualityScore` | Independent `data_quality_metric` time series, not conflated with validation coverage. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-OBS-001,002` | Standard-owned event schemas contain table-level references and counts; producer payload review required. |
| `INV-OBS-003,006` | Separate definition and run tables; active-only distinct lineage views are mutation-tested. |
| `INV-OBS-004` | Separate retention declaration; operators prove enforcement. |
| `INV-OBS-005` | Wire 2.1 append publisher; execution-error, severity and evidence tests on DuckDB. |
| `INV-OBS-007..009` | Optional graph-native facet not selected; no adapter or graph identity guarantee claimed. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal and lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
