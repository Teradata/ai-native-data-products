---
title: PostgreSQL Observability Implementation
anchor: observability
type: implementation
status: draft
version: 2.0
normative: true
implements: observability
platform: postgres
---

# PostgreSQL: Observability

Binding of [Observability](../../../../design/modules/observability.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`entities.json` declares standard-owned event, quality, lineage-definition, lineage-run, model-performance, outcome, retention and validation structures. `01-tables.sql.j2` renders only the selected module. Event and current-state profiles are distinct; definitions do not receive event retention by accident.

Capture is a producer obligation: deployers wire their ingestion, temporal writer and agent runtime to these stores. There is no automatic audit trigger or synthetic quality score. PostgreSQL AGENT can append outcomes, while validation evidence is maintainer-only; privileged administration can bypass append-only intent. DuckDB enforcement is external.

The shared validator publishes run/area/check evidence using the standard wire 2.1 fields. Missing checks, execution errors and missing ML/operational evidence remain visible. Retention is a supplied design decision and an operator-managed process; templates never silently delete historical records.

## Capability bindings

| Capability | Binding |
|---|---|
| `ChangeEventCapture` | Templates and enforcement limits described above. |
| `AgentOutcomeCapture` | Templates and enforcement limits described above. |
| `LineageCapture` | Templates and enforcement limits described above. |
| `QualityScore` | Templates and enforcement limits described above. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-OBS-001,002` | Standard-owned event schemas contain table-level references and counts; producer payload review required. |
| `INV-OBS-003,006` | Separate definition/run tables and active-only distinct lineage views. |
| `INV-OBS-004` | Separate retention declaration; operators prove enforcement. |
| `INV-OBS-005` | Wire 2.1 append publisher; native execution-error/evidence tests. |
| `INV-OBS-007..009` | Optional graph-native facet not selected; no adapter or graph identity guarantee claimed. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal/lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
