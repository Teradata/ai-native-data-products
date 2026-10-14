---
title: DuckDB Observability Module Implementation
anchor: observability
type: implementation
status: standard
version: 2.0
normative: true
implements: observability
platform: duckdb
---

# DuckDB Observability

Binding of [Observability](../../../../design/modules/observability.md). [schema.sql](schema.sql) separates change events, quality measurements, flow definitions, flow executions, model performance, agent outcomes and validation runs/areas/checks. It records aggregate counts and table identities, never before/after business values or result sets.

**Provides:**

| Capability | Binding |
|---|---|
| `ChangeEventCapture` | Host appends table-level change evidence. |
| `LineageCapture` | Stable definitions and independent executions. |
| `AgentOutcomeCapture` | Host appends aggregate actions/outcomes. |
| `QualityScore` | Data-quality time series, separate from trust coverage. |

`semantic.lineage_graph` derives distinct source→job→target edges from active definitions only; `lineage_run_latest` finds latest execution deterministically. The supplied temporal writer records aggregate changes in the same transaction when Observability is present; direct SQL and other ingestion paths must supply their own capture. Definitions are retained for product life; events 90 days and validation 365 days in the explicitly synthetic retention policy. The operator applies lifecycle actions; no SQL trigger or silent purge is claimed.

Validation follows the [validation binding](../../patterns/validation/). Trust reads the designated producer and downgrades stale evidence. Model performance is intentionally empty until actual evaluation exists; an invented accuracy measurement would be misleading. Optional graph-native/column-lineage facets are not enabled, with decisions recorded in Memory. SQL checks and tests cover active-only lineage, independent execution grain, evidence append history, area counts, severity, staleness and external gaps.
