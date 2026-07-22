# Observability Module — Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Observability module — monitoring, feedback, lineage, and the home of validation results |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/modules/observability/`](../../implementation/teradata/modules/observability/) |

Observability is the operational-evidence module: it monitors product health, records lineage, and
is the **home of validation results** ([validation pattern](../patterns/validation.md)). It closes
the feedback loop by supplying the learning inputs Memory consumes.

---

## 1. Purpose

Observability monitors data-product health and enables continuous improvement through outcome
tracking and feedback loops. Its capabilities: data-quality monitoring, change tracking (audit
trail), data lineage (definitional and operational), performance monitoring, outcome tracking, and
hosting validation evidence.

**Events and metrics, not data** (`INV-OBS-001`). Observability records *that* something happened
and *how it measured* — never the business data itself. "Party_H was updated by ETL at 02:15,
250,000 records affected, quality 0.95" — never the customer records.

---

## 2. Scope and Boundaries

**In scope:** change events (what/when/who/why, table-level), data-quality metrics, data lineage
(declared flows and their executions), performance metrics, outcome tracking, and validation results.

**Out of scope:** business domain data (→ Domain); query result sets (not stored). Event-scale volume
is acceptable (millions of events); business content is not.

---

## 3. Lineage Separation Principle

Lineage is modelled as two distinct concerns (`INV-OBS-003`):

| Concern | Entity | Question | Cardinality |
|---------|--------|----------|-------------|
| **Definitional** | `DataLineage` | *What are the declared data flows?* | One row per source → job → target |
| **Operational** | `LineageRun` | *Did this flow run, and how did it go?* | Many rows per flow over time |

This gives a stable, deduplicated edge list for graph visualisation (definition only), keeps
execution monitoring on the events-and-metrics principle, allows **independent retention**
(definitions live as long as the product; runs follow event-retention windows, `INV-OBS-004`), and
gives clear mutation semantics — a new `DataLineage` row is a new flow; a new `LineageRun` row is a
new execution of an existing flow.

---

## 4. Entity Model

All entities are append-oriented operational records (`EVENT_APPEND_ONLY`, except `DataLineage` which
carries an `is_active` lifecycle). All apply `object-placement`, `access-layer`; all require
`RichMetadata`. Table references are table-level; content is obtained by join-back to Domain.

```
Entity: ChangeEvent               [kind: Record]
  change_event_id  : Identifier
  container_name   : ShortText [optional]
  table_name       : ShortText [required]            — TABLE-LEVEL, not individual records
  change_type      : Enum{INSERT|UPDATE|DELETE|MERGE|TRUNCATE} [required]
  change_at        : Timestamp [required]
  changed_by       : ShortText [required]
  change_source    : Enum{ETL|API|MANUAL|AGENT} [optional]
  records_affected : Integer [optional]              — aggregate count, never the keys
  columns_changed  : Text [optional]
  batch_key        : ShortText [optional]

Entity: DataQualityMetric         [kind: Record]
  quality_metric_id : Identifier
  container_name    : ShortText [optional]
  table_name        : ShortText [required]
  column_name       : ShortText [optional]           — null for table-level metrics
  metric_name       : Enum{COMPLETENESS|VALIDITY|UNIQUENESS|TIMELINESS|CONSISTENCY|ACCURACY} [required]
  metric_value      : Decimal(10,4) [optional]
  measured_at       : Timestamp [required]
  quality_threshold : Decimal(5,4) [optional]
  is_threshold_met  : Flag
  sample_size       : Integer [optional]

Entity: DataLineage               [kind: Record]     — definitional; one row per flow
  lineage_id            : Identifier
  source_container      : ShortText [optional]
  source_table          : ShortText [optional]
  source_system         : ShortText [optional]       — external origin; null if internal
  target_container      : ShortText [optional]
  target_table          : ShortText [required]
  job_name              : ShortText [optional]
  transformation_type   : Enum{ETL|FEATURE_ENG|AGGREGATION|JOIN|EMBEDDING_GEN|FILTER|PIVOT} [optional]
  transformation_logic  : Text [optional]
  openlineage_job_name  : ShortText [optional]
  openlineage_namespace : ShortText [optional]
  is_active             : Flag
  registered_at         : Timestamp [optional]
  retired_at            : Timestamp [optional]

Entity: LineageRun                [kind: Record]     — operational; one row per execution
  lineage_run_id     : Identifier
  lineage_id         : Reference [required] [-> DataLineage]
  run_at             : Timestamp [required]
  run_status         : Enum{SUCCESS|FAILED|PARTIAL|RUNNING} [required]
  run_duration_ms    : Integer [optional]
  records_read       : Integer [optional]
  records_written    : Integer [optional]
  records_rejected   : Integer [optional]
  batch_key          : ShortText [optional]          — links to ChangeEvent.batch_key
  openlineage_run_id : ShortText [optional]
  error_message      : Text [optional]

Entity: ModelPerformance          [kind: Record]
  performance_id : Identifier
  model_key      : ShortText [required]
  model_version  : ShortText [required]
  metric_name    : Enum{ACCURACY|PRECISION|RECALL|AUC|LATENCY_MS|DRIFT_SCORE} [required]
  metric_value   : Decimal(10,6) [optional]
  evaluated_at   : Timestamp [required]
  sample_size    : Integer [optional]
  is_sla_met     : Flag

Entity: AgentOutcome              [kind: Record]
  outcome_id        : Identifier
  agent_key         : ShortText [required]
  session_key       : ShortText [optional]
  action_type       : Enum{QUERY|RECOMMENDATION|DECISION|PREDICTION} [required]
  action_at         : Timestamp [required]
  tables_accessed   : Text [optional]                — TABLE-LEVEL, comma-separated
  outcome_status    : Enum{SUCCESS|PARTIAL|FAILED} [required]
  user_feedback     : Enum{POSITIVE|NEUTRAL|NEGATIVE|CORRECTION} [optional]
  records_processed : Integer [optional]             — aggregate count
```

**Validation results.** The [validation pattern](../patterns/validation.md)'s result record is homed
in this module as append-only evidence (`EVENT_APPEND_ONLY`, `INV-OBS-005`). Its contract is owned by
the validation pattern; this module provides its container.

---

## 5. Discovery Exposure

Two views are deployed **into the Semantic container** so agents discover lineage from the same place
they discover everything else (Semantic §7):

- **`lineage_graph`** — a graph-ready edge list built from `DataLineage`, with jobs surfaced as
  first-class nodes (source → job, job → target). Reads **active definitions only** — no duplicate
  edges from repeated executions, so the graph is stable and deduplicated (`INV-OBS-006`).
- **`lineage_run_latest`** — each active flow joined to its most recent execution, for dashboards
  showing last-run status against the blueprint.

---

## 6. Open Standards Alignment

The lineage entities align with **OpenLineage**: the definition/execution split mirrors OpenLineage's
separation of a `Job` (declared flow → `DataLineage`) from a `Run` (execution → `LineageRun`).
`source`/`target` container+table compose into OpenLineage dataset names; `openlineage_namespace` and
`openlineage_job_name`/`openlineage_run_id` carry the OpenLineage identifiers. Data-quality metric
names align with common frameworks (Great Expectations, Deequ). The concrete event construction is an
implementation concern.

---

## 7. Applied Patterns

| Pattern | Contribution to Observability |
|---------|-------------------------------|
| `temporal-lifecycle-metadata` | Event entities declare the `EVENT_APPEND_ONLY` profile; `DataLineage` carries an `is_active` lifecycle. |
| `object-placement` | Which container the tables and views live in, and who may reach them. |
| `access-layer` | `ROLE_AGENT` write-back (append) to this module — agents record outcomes and quality signals (Phase 2.5). |
| `validation` | Hosts the validation results; its own quality/lineage evidence is a validator source. |

---

## 8. Capabilities and Composition

Observability is **cross-cutting and soft**: nothing hard-depends on it, and it hard-depends on
nothing — it observes whatever modules are present. It is in a traditional data product and an
AI-native product, absent in a minimal Data Asset.

**Provides:**

| Capability | Made available to |
|------------|-------------------|
| Outcome & quality evidence (learning inputs) | Memory, for closed-loop learning. |
| Validation results home | The validation pattern, as the container for `validation_run`. |
| Lineage (definitional + operational) | Agents and dashboards, via the Semantic exposure. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on every object. |
| `SemanticRegistration` | `[soft]` | `module:Semantic` | Register its entities and deploy the lineage views into the Semantic container. |
| `DocumentationCapture` | `[soft]` | `module:Memory` | Record its own design decisions. |
| `EntityJoinBack` | `[soft]` | `module:Domain` | Resolve a table reference to Domain context when needed. |

---

## 9. Integration with Other Modules

- **Observability → Memory** — outcomes and quality trends feed Memory's learned strategies (the
  closed loop). Memory soft-requires these learning inputs.
- **Observability + Domain** — table-level change tracking of Domain loads; one event per batch, never
  per record.
- **Observability monitors all modules** — quality, performance, and lineage across whatever is
  deployed.

---

## 10. Invariants

- `INV-OBS-001`: Observability stores events and metrics, never business data or query result sets.
- `INV-OBS-002`: change tracking is table-level with aggregate metrics (e.g. `records_affected`), never individual record keys, and **never** before/after business values — capturing changed column *values* (e.g. old/new `legal_name`, `email`) duplicates Domain content into Observability and is a PII / data-privacy defect. The audit trail records *what table changed, when, by whom, and how many rows* — not the data itself; the prior state is reconstructed from Domain's temporal history.
- `INV-OBS-003`: lineage is split — `DataLineage` declares flows (one row per source → job → target), `LineageRun` records executions (one row per run).
- `INV-OBS-004`: definitional lineage is retained for the life of the product; execution records follow independent event-retention windows.
- `INV-OBS-005`: validation results are homed here as append-only evidence (`EVENT_APPEND_ONLY`).
- `INV-OBS-006`: the lineage graph/edge-list consumed by discovery reads active definitions only, so it is stable and deduplicated.

---

## 11. Designer Responsibilities

**Designers supply:** the quality metrics and thresholds; the declared lineage flows; the OpenLineage
scope; retention policies (separately for `DataLineage` vs `LineageRun`); which modules are monitored.

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Events/metrics only; no business data or result sets (`INV-OBS-001`).
- [ ] Change tracking is table-level with aggregate metrics (`INV-OBS-002`).
- [ ] Lineage flows registered in `DataLineage`; executions logged in `LineageRun` (`INV-OBS-003`).
- [ ] Separate retention policies for definition vs execution (`INV-OBS-004`).
- [ ] Validation results homed here (`INV-OBS-005`); `lineage_graph` / `lineage_run_latest` deployed to Semantic.
- [ ] Entities registered in the Semantic map (`SemanticRegistration`); documentation captured, including the lineage split as a design decision.
- [ ] This document passes the design linter with no ignore directive.

---

## 12. Implementation

The Teradata binding — the event/metric/lineage tables, the `lineage_graph` and `lineage_run_latest`
Semantic views, and the OpenLineage event construction — lives in
[`implementation/teradata/modules/observability/`](../../implementation/teradata/modules/observability/).
The validation results table is defined by the
[validation pattern implementation](../../implementation/teradata/patterns/validation/) and deployed
into this module's container.

---

**End of Observability Module Design Standard**
