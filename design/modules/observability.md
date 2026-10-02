---
title: Observability Module
anchor: observability
type: module
status: standard
version: 2.1
normative: true
---

# Observability Module: Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Observability module: monitoring, feedback, lineage, and the home of validation results |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | `implementation/{platform}/modules/observability/`, one per platform |

Observability is the operational-evidence module: it monitors product health, records lineage, and is the **home of validation results** ([validation pattern](../patterns/validation.md)). It closes the feedback loop by supplying the learning inputs Memory consumes.

---

## 1. Purpose

Observability monitors data-product health and enables continuous improvement through outcome tracking and feedback loops. Its capabilities: data-quality monitoring, change tracking (audit trail), data lineage (definitional and operational), performance monitoring, outcome tracking, hosting validation evidence, and — optionally — exposing its lineage and access history as a traversable graph (§5.1).

**Events and metrics, not data** (`INV-OBS-001`). Observability records *that* something happened and *how it measured*, never the business data itself. "Party_H was updated by ETL at 02:15, 250,000 records affected, quality 0.95", never the customer records.

---

## 2. Scope and Boundaries

**In scope:** change events (what/when/who/why, table-level), data-quality metrics, data lineage (declared flows and their executions), performance metrics, outcome tracking, validation results, and an optional graph-native lineage exposure (§5.1) for products that need graph traversal rather than only tabular discovery.

**Out of scope:** business domain data (→ Domain); query result sets (not stored). Event-scale volume is acceptable (millions of events); business content is not. The graph-explorer platform itself (the shared engine, quality procedures, and rendering layer are external, normative dependencies this module conforms to, not defines) and cross-product federated lineage (a separate, explicitly designed federated graph, not a retrofit onto a per-product graph) are also out of scope.

---

## 3. Lineage Separation Principle

Lineage is modelled as two distinct concerns (`INV-OBS-003`):

| Concern | Entity | Question | Cardinality |
|---------|--------|----------|-------------|
| **Definitional** | `DataLineage` | *What are the declared data flows?* | One row per source → job → target |
| **Operational** | `LineageRun` | *Did this flow run, and how did it go?* | Many rows per flow over time |

Separating them yields a stable, deduplicated edge list for graph visualisation, and keeps execution monitoring on the events-and-metrics principle. It also allows **independent retention**: definitions live as long as the product, while runs follow event-retention windows (`INV-OBS-004`). Mutation semantics stay clear, since a new `DataLineage` row is a new flow and a new `LineageRun` row is a new execution of an existing flow.

---

## 4. Entity Model

All entities are append-oriented operational records (`EVENT_APPEND_ONLY`, except `DataLineage` which carries an `is_active` lifecycle). All apply `object-placement`, `access-layer`; all require `RichMetadata`. Table references are table-level; content is obtained by join-back to Domain.

```
Entity: ChangeEvent               [kind: Record]
  change_event_id: Identifier
  container_name: ShortText [optional]
  table_name: ShortText [required]  // TABLE-LEVEL, not individual records
  change_type: Enum{INSERT|UPDATE|DELETE|MERGE|TRUNCATE} [required]
  change_dts: Timestamp [required]
  changed_by: ShortText [required]
  change_source: Enum{ETL|API|MANUAL|AGENT} [optional]
  records_affected: Integer [optional]  // aggregate count, never the keys
  columns_changed: Text [optional]
  batch_key: ShortText [optional]

Entity: DataQualityMetric         [kind: Record]
  quality_metric_id: Identifier
  container_name: ShortText [optional]
  table_name: ShortText [required]
  column_name: ShortText [optional]  // null for table-level metrics
  metric_name: Enum{COMPLETENESS|VALIDITY|UNIQUENESS|TIMELINESS|CONSISTENCY|ACCURACY} [required]
  metric_value: Decimal(10,4) [optional]
  measured_dts: Timestamp [required]
  quality_threshold: Decimal(5,4) [optional]
  is_threshold_met: Flag
  sample_size: Integer [optional]

Entity: DataLineage               [kind: Record]  // definitional; one row per flow
  lineage_id: Identifier
  source_container: ShortText [optional]
  source_table: ShortText [optional]
  source_column: ShortText [optional]  // null for a table-level flow; set only for column-level lineage
  source_system: ShortText [optional]  // external origin; null if internal
  target_container: ShortText [optional]
  target_table: ShortText [required]
  target_column: ShortText [optional]  // null for a table-level flow; set only for column-level lineage
  job_name: ShortText [optional]
  transformation_type: Enum{ETL|FEATURE_ENG|AGGREGATION|JOIN|EMBEDDING_GEN|FILTER|PIVOT} [optional]
  transformation_logic: Text [optional]
  openlineage_job_name: ShortText [optional]
  openlineage_namespace: ShortText [optional]
  is_active: Flag
  registered_dts: Timestamp [optional]
  retired_dts: Timestamp [optional]

Entity: LineageRun                [kind: Record]  // operational; one row per execution
  lineage_run_id: Identifier
  lineage_id: Reference [required] [-> DataLineage]
  run_dts: Timestamp [required]
  run_status: Enum{SUCCESS|FAILED|PARTIAL|RUNNING} [required]
  run_duration_ms: Integer [optional]
  records_read: Integer [optional]
  records_written: Integer [optional]
  records_rejected: Integer [optional]
  batch_key: ShortText [optional]  // links to ChangeEvent.batch_key
  openlineage_run_id: ShortText [optional]
  error_message: Text [optional]

Entity: ModelPerformance          [kind: Record]
  performance_id: Identifier
  model_key: ShortText [required]
  model_version: ShortText [required]
  metric_name: Enum{ACCURACY|PRECISION|RECALL|AUC|LATENCY_MS|DRIFT_SCORE} [required]
  metric_value: Decimal(10,6) [optional]
  evaluation_dts: Timestamp [required]
  sample_size: Integer [optional]
  is_sla_met: Flag

Entity: AgentOutcome              [kind: Record]
  outcome_id: Identifier
  agent_key: ShortText [required]
  session_key: ShortText [optional]
  action_type: Enum{QUERY|RECOMMENDATION|DECISION|PREDICTION} [required]
  action_dts: Timestamp [required]
  tables_accessed: Text [optional]  // TABLE-LEVEL, comma-separated
  outcome_status: Enum{SUCCESS|PARTIAL|FAILED} [required]
  user_feedback: Enum{POSITIVE|NEUTRAL|NEGATIVE|CORRECTION} [optional]
  records_processed: Integer [optional]  // aggregate count
```

**Validation results.** The [validation pattern](../patterns/validation.md)'s result record, the `ValidationRun` entity, is homed in this module as append-only evidence (`EVENT_APPEND_ONLY`, `INV-OBS-005`). Its contract is owned by the validation pattern; this module provides its container. Its logical name is fixed by that contract and is not a designer's choice. An organisation may map it to a physical name of its own; the binding registers that mapping in Semantic, and conformance queries resolve the relation through it rather than through a literal name.

### 4.1 Graph Node and Edge Model (optional, `graph-lineage` facet)

A product that enables the `graph-lineage` facet (§8.1) maps `DataLineage` and `AgentOutcome` into a node/edge exposure that conforms to a graph consumer contract, so lineage can be opened in graph-native tooling, traced, and rendered as a graph, rather than only queried as the tabular `lineage_graph` edge list (§5). This is a mapping onto the entities already defined in §4, not a new system of record (`INV-OBS-007`).

**Node categories:**

| `category` | `node_role` values | Natural key | Source |
|---|---|---|---|
| `table` | `source_table`, `target_table` | `container_name.object_name` | `DataLineage.source_table`/`target_table` |
| `column` | `source_column`, `target_column` | `container_name.object_name.column_name` | `DataLineage.source_column`/`target_column`, only where the `column-lineage` facet (§8.1) is also enabled |
| `job` | `etl_job` | `job_name` | `DataLineage.job_name` (first-class node, as `lineage_graph` already treats it) |
| `agent` | `consumer` | `agent_key` | `AgentOutcome.agent_key` |
| `query_session` | `session` | `session_key` | `AgentOutcome.session_key` (omit this category entirely if a product does not need session-grain traversal) |

`node` is the dense surrogate identity assigned at load time (§5.1); the natural key above is carried as a separate, non-canonical attribute because a natural key must not replace the surrogate node identity.

**Edge types**, registered in the graph catalogue's relationship vocabulary, all asymmetric:

| `edge_type` | Direction (`node_i` → `node_j`) | Source |
|---|---|---|
| `produces` | upstream (source table or job) → downstream (job or target table) | `DataLineage`, one edge per source→job leg and job→target leg |
| `derives_column` | source column → target column | `DataLineage.source_column`/`target_column`, only where `column-lineage` is enabled |
| `accessed_by` | table → agent | `AgentOutcome.tables_accessed` (exploded to one row per accessed table) |
| `queried_in` | agent → query_session | `AgentOutcome.session_key` |

The graph is unweighted: every edge carries a weight of 1.0. Every edge carries an `edge_type` drawn from the registered vocabulary.

---

## 5. Discovery Exposure

Two views are deployed **into the Semantic container** so agents discover lineage from the same place they discover everything else (Semantic):

- **`lineage_graph`**: a graph-ready edge list built from `DataLineage`, with jobs surfaced as first-class nodes (source → job, job → target). Its definition **filters to active lineage definitions**, and does so in the view body rather than leaving it to the caller: no duplicate edges from repeated executions, so the graph is stable and deduplicated (`INV-OBS-006`). Omitting the filter is not a cosmetic lapse. Retired flows stay in the graph and there is nothing in the result to mark them as retired, so an agent navigating lineage is led to a flow that no longer runs and cannot tell.
- **`lineage_run_latest`**: each active flow joined to its most recent execution, for dashboards showing last-run status against the blueprint.

### 5.1 Graph-Native Exposure (optional, `graph-lineage` facet)

Where `lineage_graph` is the lightweight discovery edge-list for agents already inside Semantic, a product that enables the `graph-lineage` facet additionally exposes its lineage and access records through a **graph consumer contract**: the published contract of the graph-native tooling a platform binding targets, which that binding names and conforms to. It is a heavier, separately packaged exposure built from the same source-of-truth entities (§4), so an agent or analyst can open the product's lineage in graph tooling, search it, trace it upstream or downstream, and visualise it rather than only query it as a tabular edge list. Nothing here creates a second system of record: it reads `DataLineage`/`AgentOutcome` only and never writes back into them (`INV-OBS-007`).

**Graph scope principle.** One data product, one graph (`DEC-GRAPH-SCOPE`, §11.1, decided, not left open per product): each data product registers its own `graph_key`, its own node and edge relations, and its own catalogue entry (`INV-OBS-008`). `community` is not used to represent product ownership: graph consumer contracts treat `community` as an instance grouping or analytical partition that may change between graph builds (e.g. Louvain clustering); product identity is a stable governance fact that must never move between runs, and conflating the two would also block a product from using `community` for its own legitimate subject-area clustering. Cross-product federated lineage, if ever needed, is a separate, explicitly designed federated graph with `data_product` as a genuine `category` value on its own nodes — out of scope for this module.

**Load semantics.** A set-based upsert from `DataLineage`/`AgentOutcome` into the graph tables, run on the same cadence as lineage/outcome capture or on a scheduled interval (`DEC-GRAPH-LOAD-CADENCE`, §11.1):

1. **Node upsert**: natural keys (§4.1) are resolved against the existing node table; an unseen natural key receives a newly allocated `node_id`, dense and never reused. Existing natural keys are not renumbered — a node identity refers to the same logical entity for the life of a published graph version (`INV-OBS-009`).
2. **Edge upsert**: `DataLineage` and `AgentOutcome` rows resolve their natural keys to `node_id` and are inserted as `(node_i, node_j, edge_type, weight)`, deduplicated on `(node_i, node_j, edge_type)`.
3. Only `DataLineage` rows with `is_active=1` are loaded, matching `INV-OBS-006`'s stability guarantee: a retired flow does not appear as a live edge in the graph.

**Exposure planes**, one set per graph key (one per data product):

| Plane | Holds | Populated by |
|---|---|---|
| Data | The node and edge relations | Load path above |
| Consumer surface | The node and edge projection in the shape the graph consumer contract defines: the only surface external consumers bind to | Derived from the data plane |
| Access | One read principal per graph, the sole consumer-facing grant onto the consumer surface | Access layer |
| Catalogue | The graph's registry entry, relationship vocabulary, role vocabulary and trace profiles | One-time registration, updated only on vocabulary change |

Physical names for every plane arrive through the build context, never from this document: from the graph consumer contract where it fixes them, otherwise from the organisation's placement and naming rules. The shared graph catalogue and engine belong to the graph platform, not the product: a product registers into them and does not recreate them.

**Trace profiles**, registered in the graph catalogue:

| `profile_id` | `direction` | `relationship` | `stop_at_roles` | Purpose |
|---|---|---|---|---|
| `trace_to_source` | `upstream` | `produces`(`,derives_column` if `column-lineage` enabled) | — | Where did this table/column come from? |
| `impact_analysis` | `downstream` | `produces`(`,derives_column` if `column-lineage` enabled) | — | What breaks if this table/column changes? |
| `who_touched_this` | `downstream` | `accessed_by,queried_in` | `session` | Which agents/sessions have consumed this data? |

---

## 6. Open Standards Alignment

The lineage entities align with **OpenLineage**: the definition/execution split mirrors OpenLineage's separation of a `Job` (declared flow → `DataLineage`) from a `Run` (execution → `LineageRun`). `source`/`target` container+table compose into OpenLineage dataset names; `openlineage_namespace` and `openlineage_job_name`/`openlineage_run_id` carry the OpenLineage identifiers. Data-quality metric names align with common frameworks (Great Expectations, Deequ). The concrete event construction is an implementation concern.

---

## 7. Applied Patterns

| Pattern | Contribution to Observability |
|---------|-------------------------------|
| `temporal-lifecycle-metadata` | Event entities declare the `EVENT_APPEND_ONLY` profile; `DataLineage` carries an `is_active` lifecycle. When `graph-lineage` is enabled, its node/edge tables carry `created_dts` as provenance only, never business validity. |
| `object-placement` | Which container the tables and views live in, and who may reach them; governs the containers the graph exposure planes occupy when `graph-lineage` is enabled. |
| `access-layer` | `ROLE_AGENT` write-back (append) to this module: agents record outcomes and quality signals (Phase 2.5). The graph's read principal is the sole consumer-facing grant onto the graph exposure when enabled. |
| `validation` | Hosts the validation results and the trust map; its own quality/lineage evidence is a validator source. The graph consumer contract's own structural and semantic quality gates are the validator source for the `graph-lineage` facet. |

---

## 8. Capabilities and Composition

Observability is **cross-cutting and soft**: nothing hard-depends on it, and it hard-depends on nothing, so it observes whatever modules are present. It appears in a traditional data product and an AI-native product, and is absent from a minimal Data Asset.

### 8.1 Facets

Beyond its always-present base, Observability exposes two facets that a product enables independently (see the [composition mechanism](../core/DESIGN_LANGUAGE.md)); `column-lineage` only adds anything once `graph-lineage` is also enabled:

| Facet | Holds | Provides |
|---|---|---|
| **`graph-lineage`** | The graph node/edge exposure (§4.1, §5.1): node and edge relations, consumer surface, catalogue registration, trace profiles. | `GraphNativeLineageTraversal`. |
| **`column-lineage`** | Populated `DataLineage.source_column`/`.target_column`; `column` nodes and `derives_column` edges within the `graph-lineage` exposure. | `ColumnGrainLineageTraversal`, catalogue-registered so a consumer can discover it without querying the graph. |

A product that does not enable `graph-lineage` gets the tabular `lineage_graph` discovery view (§5) only. A product that enables `graph-lineage` but not `column-lineage` gets the full graph exposure at table grain: it does not populate the column extension, and its catalogue registration omits the `derives_column` relationship and `COLUMN` role, so an agent can tell the capability is absent from the catalogue alone rather than by tracing an empty result.

**Provides:**

| Capability | Facet | Made available to |
|------------|-------|-------------------|
| `ChangeEventCapture` | — | Any module recording who changed an entity instance, when, and why: the audit trail that `DEC-COLUMN-STRATEGY` offloads here. |
| `LineageCapture` | — | Any module recording the origin of an instance: source system, source record, and producing run. |
| `AgentOutcomeCapture` | — | Any module or exposure layer recording which tables an agent touched, when, and with what outcome (`AgentOutcome`). |
| `QualityScore` | — | Agents judging fitness before use, and Memory as a learning input. Held as a time series per `DEC-QUALITY-STORAGE`. |
| Validation results home | — | The validation pattern, as the container for `validation_run` and the `validation_area` trust map. |
| Lineage exposure (definitional + operational) | — | Agents and dashboards, via the Semantic exposure. |
| `GraphNativeLineageTraversal` | `graph-lineage` | Graph-native lineage tooling and any agent or analyst using it: upstream/downstream trace, impact analysis, and access-path traversal over this product's lineage. |
| `ColumnGrainLineageTraversal` | `column-lineage` | Graph-native lineage tooling and any agent or analyst using it: column-to-column derivation trace, in addition to table-grain trace. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on every object. |
| `SemanticRegistration` | `[soft]` | `module:Semantic` | Register its entities and deploy the lineage views into the Semantic container. |
| `DocumentationCapture` | `[soft]` | `module:Memory` | Record its own design decisions. |
| `EntityJoinBack` | `[soft]` | `module:Domain` | Resolve a table reference to Domain context when needed. |
| Graph platform runtime | `[hard]`, only when `graph-lineage` is enabled | `external:graph-platform` | Catalogue, engine, and quality procedures the `graph-lineage` facet's package does not itself define. |

---

## 9. Integration with Other Modules

- **Observability → Memory**: outcomes and quality trends feed Memory's learned strategies (the closed loop). Memory soft-requires these learning inputs.
- **Observability + Domain**: table-level change tracking of Domain loads; one event per batch, never per record.
- **Observability monitors all modules**: quality, performance, and lineage across whatever is deployed.
- **Observability + external `graph-platform`**: when `graph-lineage` is enabled, hard-depends on the shared catalogue, engine, and quality procedures (§8); provides no capability the platform itself does not already define, only this product's specific graph. No integration with Semantic: `lineage_graph` (§5) stays the Semantic-facing discovery edge-list; the graph exposure is a separate, heavier surface for graph-native tooling and does not register into the Semantic map.

---

## 10. Invariants

- `INV-OBS-001`: Observability stores events and metrics, never business data or query result sets.
- `INV-OBS-002`: change tracking is table-level with aggregate metrics (e.g. `records_affected`), never individual record keys, and **never** before/after business values: capturing changed column *values* (e.g. old/new `legal_name`, `email`) duplicates Domain content into Observability and is a PII / data-privacy defect. The audit trail records *what table changed, when, by whom, and how many rows*: not the data itself; the prior state is reconstructed from Domain's temporal history.
- `INV-OBS-003`: lineage is split: `DataLineage` declares flows (one row per source → job → target), `LineageRun` records executions (one row per run).
- `INV-OBS-004`: definitional lineage is retained for the life of the product; execution records follow independent event-retention windows.
- `INV-OBS-005`: validation results are homed here as append-only evidence (`EVENT_APPEND_ONLY`), both the run record and the per-area trust map.
- `INV-OBS-006`: the lineage graph/edge-list consumed by discovery reads active definitions only, so it is stable and deduplicated.
- `INV-OBS-007`: when `graph-lineage` is enabled, its node/edge tables are a read-derived exposure of `DataLineage`/`AgentOutcome`; they carry table/column/job/agent identifiers only, never business row data, and are never written back into by anything else.
- `INV-OBS-008`: one data product registers exactly one lineage graph (`DEC-GRAPH-SCOPE`, §5.1); `community` is never used to encode product ownership.
- `INV-OBS-009`: a graph node's surrogate `node_id`, once allocated, refers to the same logical entity for the life of the published graph version; natural-key resolution never reuses or shifts an existing `node_id` value.

---

## 11. Designer Responsibilities

**Designers supply:** the quality metrics and thresholds; the declared lineage flows; the OpenLineage scope; retention policies (separately for `DataLineage` vs `LineageRun`); which modules are monitored; whether the `graph-lineage` facet is enabled and, if so, the graph key, whether `query_session` nodes are needed, the load cadence, and whether `column-lineage` is also enabled.

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Events/metrics only; no business data or result sets (`INV-OBS-001`).
- [ ] Change tracking is table-level with aggregate metrics (`INV-OBS-002`).
- [ ] Lineage flows registered in `DataLineage`; executions logged in `LineageRun` (`INV-OBS-003`).
- [ ] Separate retention policies for definition vs execution (`INV-OBS-004`).
- [ ] Validation results homed here (`INV-OBS-005`); `lineage_graph` / `lineage_run_latest` deployed to Semantic.
- [ ] Entities registered in the Semantic map (`SemanticRegistration`); documentation captured, including the lineage split as a design decision.
- [ ] If `graph-lineage` is enabled: graph key chosen and unique across the estate (`INV-OBS-008`); catalogue entries registered before the consumer surface is published; the graph's read principal is the only grant issued; the same graph key is written back onto this product's `DataProductMap.graph_key` (`OBSERVABILITY` row) so a consumer can resolve it from the product prefix alone, without guessing a naming convention.
- [ ] `column-lineage` enabled only if column-level lineage is in scope for this product; the `DataLineage` column extension populated and catalogue rows registered together, never one without the other.
- [ ] This document passes the design linter with no ignore directive.

---

### 11.1 Decisions to settle

These are the catalogued decisions a Observability module design must settle. The recommendation is this standard's default; the question is what shifts it. The design skill walks a designer through each one at design time and records the answer in the product's own design.


| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-QUALITY-STORAGE` | `observability` | Does anything examine quality trend or per-rule detail, or only the latest score? |
| `DEC-AUDIT-RETENTION` | `regulatory` | Which entities carry a retention obligation, and how long does it run? |
| `DEC-TIMESTAMP-ZONE` | `zone-aware` | Are events recorded across regions? |
| `DEC-GRAPH-SCOPE` | one graph per data product | Already settled by this standard (§5.1); revisit only when a genuine cross-product federated graph is separately designed. |
| `DEC-GRAPH-COLUMN-LINEAGE` | omit the `column-lineage` facet unless requested | Does any consumer need column-grain trace, or is table-grain sufficient? |
| `DEC-GRAPH-SESSION-NODES` | omit unless requested | Is session-level access traversal (`query_session` nodes) actually queried, or does `agent`-level suffice? |
| `DEC-GRAPH-LOAD-CADENCE` | same cadence as lineage capture | Do graph consumers need near-real-time lineage, or is a scheduled batch load sufficient? |

---

## 12. Implementation

Each platform binding provides the event, metric, and lineage tables, the `lineage_graph` and `lineage_run_latest` Semantic views, the OpenLineage event construction, and, when `graph-lineage` is enabled, the graph exposure planes, catalogue registration and load path, in `implementation/{platform}/modules/observability/`. It conforms to the [Platform Implementation Authoring Standard](../core/IMPLEMENTATION_AUTHORING.md). The validation results relations are defined by that platform's binding of the [validation pattern](../patterns/validation.md) and deployed into this module's container.

A binding that supports `graph-lineage` names the graph consumer contract it targets and conforms to it. That contract's column shapes, catalogue definitions and quality procedures belong to its owner and are not redefined here; a platform with no graph consumer contract reports the facet as unsupported. Adding a platform changes nothing in this document.

---

**End of Observability Module Design Standard**
