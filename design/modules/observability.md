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

**Events and metrics, not data** (`INV-OBS-001`). Observability records *that* something happened and *how it measured*, never the business data itself. "Party was updated by ETL at 02:15, 250,000 records affected, quality 0.95", never the customer records.

---

## 2. Scope and Boundaries

**In scope:** change events (what/when/who/why, table-level), data-quality metrics, data lineage (declared flows and their executions), performance metrics, outcome tracking, validation results, and an optional graph-native lineage exposure (§5.1) for products that need graph traversal rather than only tabular discovery.

**Out of scope:** business domain data (→ Domain); query result sets (not stored). Event-scale volume is acceptable (millions of events); business content is not. The graph-native tooling a binding targets (its shared engine, quality procedures, and rendering layer are external, normative dependencies this module conforms to, not defines) and cross-product federated lineage (a separate, explicitly designed federated graph, not a retrofit onto a per-product graph) are also out of scope.

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

Every entity header states its temporal profile, because a `Record` has no default one. The event entities are append-only operational records and declare `EVENT_APPEND_ONLY`. `DataLineage` carries an `is_active` lifecycle and is updated when a flow retires, so it declares `CURRENT_STATE`: an entity with lifecycle flags cannot be append-only. The audit columns each profile requires come from the temporal pattern and are not repeated below. All apply `object-placement`, `access-layer` and `temporal-lifecycle-metadata`; all require `RichMetadata`. All are standard-owned relations ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.1), placed and named by the organisation profile. Table references are table-level; content is obtained by join-back to Domain.

```
Entity: ChangeEvent               [kind: Record] [profile: EVENT_APPEND_ONLY]
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

Entity: DataQualityMetric         [kind: Record] [profile: EVENT_APPEND_ONLY]
  quality_metric_id: Identifier
  container_name: ShortText [optional]
  table_name: ShortText [required]
  column_name: ShortText [optional]  // null for table-level metrics
  quality_dimension: Enum{COMPLETENESS|VALIDITY|CONSISTENCY|ACCURACY|TIMELINESS} [required]  // the category the rule scores into
  check_function: Enum{COMPLETENESS|VALIDITY|CONSISTENCY|INTEGRITY|UNIQUENESS|FRESHNESS} [required]  // the Quality block rule's check
  rule_text: Text [required]  // the rule and its thresholds, as the Quality block states them
  metric_value: Decimal(10,4) [optional]  // the measured share, count, or age in hours
  pass_threshold: Decimal(5,4) [optional]  // a share rule's pass threshold
  warn_threshold: Decimal(5,4) [optional]  // a share rule's warn threshold
  check_outcome: Enum{PASS|WARN|FAIL} [required]  // per the Quality block's threshold mapping
  measured_dts: Timestamp [required]
  sample_size: Integer [optional]

Entity: DataLineage               [kind: Record] [profile: CURRENT_STATE]  // definitional; one row per flow
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
  openlineage_namespace: ShortText [optional]  // organisation or deployment configuration, never the designer's
  is_active: Flag  // the flow is live: set at registration, cleared when it retires and retired_dts is recorded
  registered_dts: Timestamp [optional]
  retired_dts: Timestamp [optional]

Entity: LineageRun                [kind: Record] [profile: EVENT_APPEND_ONLY]  // operational; one row per execution
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

Entity: ModelPerformance          [kind: Record] [profile: EVENT_APPEND_ONLY]
  performance_id: Identifier
  model_key: ShortText [required]
  model_version: ShortText [required]
  metric_name: Enum{ACCURACY|PRECISION|RECALL|AUC|LATENCY_MS|DRIFT_SCORE} [required]
  metric_value: Decimal(10,6) [optional]
  evaluation_dts: Timestamp [required]
  sample_size: Integer [optional]
  is_sla_met: Flag

Entity: AgentOutcome              [kind: Record] [profile: EVENT_APPEND_ONLY]
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

**Quality measurements follow the `Quality:` block.** Each rule in the specification's `Quality:` block ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.7) produces one `DataQualityMetric` row per measurement, recording its check function, its thresholds and the outcome they give. `quality_dimension` takes the five standard categories of `DEC-QUALITY-STORAGE`, the same dimensions the block's `Weights` combine. A rule scores into the category its check names; `freshness` scores into timeliness, `integrity` into consistency and `uniqueness` into validity.

**Validation results.** The [validation pattern](../patterns/validation.md)'s result record, `ValidationRun`, and its trust map, `ValidationArea`, are owned by this module as append-only evidence (`EVENT_APPEND_ONLY`, `INV-OBS-005`) and placed per the organisation profile, like every other standard-owned relation. Their contract is owned by the validation pattern, and their logical names are fixed by it, not a designer's choice. An organisation may map them to physical names of its own; the binding registers that mapping in Semantic, and conformance queries resolve the relations through it rather than through a literal name.

### 4.1 Graph Node and Edge Model (optional, `graph-lineage` facet)

A product that enables the `graph-lineage` facet (§8.1) maps `DataLineage` and `AgentOutcome` into a node/edge exposure that conforms to a graph consumer contract, so lineage can be opened in graph-native tooling, traced, and rendered as a graph, rather than only queried as the tabular `LineageGraph` edge list (§5). This is a mapping onto the entities already defined in §4, not a new system of record (`INV-OBS-007`).

**Node categories:**

| `category` | `node_role` values | Natural key | Source |
|---|---|---|---|
| `table` | `source_table`, `target_table` | `container_name.object_name` | `DataLineage.source_table`/`target_table` |
| `column` | `source_column`, `target_column` | `container_name.object_name.column_name` | `DataLineage.source_column`/`target_column`, only where the `column-lineage` facet (§8.1) is also enabled |
| `job` | `etl_job` | `job_name` | `DataLineage.job_name` (first-class node, as `LineageGraph` already treats it) |
| `agent` | `consumer` | `agent_key` | `AgentOutcome.agent_key` |
| `query_session` | `session` | `session_key` | `AgentOutcome.session_key`, only where the `Graph:` block's `Session nodes` is `include` (`DEC-GRAPH-SESSION-NODES`) |

`node` is the dense surrogate identity assigned at load time (§5.1); the natural key above is carried as a separate, non-canonical attribute because a natural key must not replace the surrogate node identity.

**Edge types**, registered in the graph catalogue's relationship vocabulary, all asymmetric:

| `edge_type` | Direction (`node_i` → `node_j`) | Source |
|---|---|---|
| `produces` | upstream (source table or job) → downstream (job or target table) | `DataLineage`, one edge per source→job leg and job→target leg |
| `derives_column` | source column → target column | `DataLineage.source_column`/`target_column`, only where `column-lineage` is enabled |
| `accessed_by` | table → agent | `AgentOutcome.tables_accessed` (exploded to one row per accessed table) |
| `queried_in` | agent → query_session | `AgentOutcome.session_key`, only where session nodes are included |

The graph is unweighted: every edge carries a weight of 1.0. Every edge carries an `edge_type` drawn from the registered vocabulary.

---

## 5. Discovery Exposure

Two standard-owned discovery views expose lineage to agents. Their names, `LineageGraph` and `LineageRunLatest`, are logical, and an organisation may map them to physical names of its own. The organisation profile places them; an organisation may route them alongside Semantic's relations so agents find lineage in the same place they find everything else. Wherever they are placed, they are registered in Semantic, so an agent reaches them through metadata.

- **`LineageGraph`**: a graph-ready edge list built from `DataLineage`, with jobs surfaced as first-class nodes (source → job, job → target). Its definition **filters to active lineage definitions**, and does so in the view body rather than leaving it to the caller: no duplicate edges from repeated executions, so the graph is stable and deduplicated (`INV-OBS-006`). Omitting the filter is not a cosmetic lapse. Retired flows stay in the graph and there is nothing in the result to mark them as retired, so an agent navigating lineage is led to a flow that no longer runs and cannot tell.
- **`LineageRunLatest`**: each active flow joined to its most recent execution, for dashboards showing last-run status against the blueprint.

### 5.1 Graph-Native Exposure (optional, `graph-lineage` facet)

Where `LineageGraph` is the lightweight discovery edge list agents reach through Semantic, a product that enables the `graph-lineage` facet additionally exposes its lineage and access records through a **graph consumer contract**: the published contract of the graph-native tooling a platform binding targets, which that binding names and conforms to. It is a heavier, separately packaged exposure built from the same source-of-truth entities (§4), so an agent or analyst can open the product's lineage in graph tooling, search it, trace it upstream or downstream, and visualise it rather than only query it as a tabular edge list. Nothing here creates a second system of record: it reads `DataLineage`/`AgentOutcome` only and never writes back into them (`INV-OBS-007`).

**Graph scope principle.** One data product, one graph (`INV-OBS-008`). This is a rule of this standard, not a decision a product settles: each data product registers its own graph key, its own node and edge relations, and its own catalogue entry. The graph key is not a design fact: the organisation profile's `Naming:` `Graph key` template derives it from the product code, its uniqueness follows from that template, and the build records it on the product's `DataProductMap` rows for Observability. `community` is not used to represent product ownership: graph consumer contracts treat `community` as an instance grouping or analytical partition that may change between graph builds (e.g. Louvain clustering); product identity is a stable governance fact that must never move between runs, and conflating the two would also block a product from using `community` for its own legitimate subject-area clustering. Cross-product federated lineage, if ever needed, is a separate, explicitly designed federated graph with `data_product` as a genuine `category` value on its own nodes — out of scope for this module.

**Load semantics.** A set-based upsert from `DataLineage`/`AgentOutcome` into the graph tables, run when the `Graph:` block's `Load cadence` says (`DEC-GRAPH-LOAD-CADENCE`): in the capture path whenever lineage or outcomes are captured (`with-lineage`), or on the block's `Schedule` (`scheduled`):

1. **Node upsert**: natural keys (§4.1) are resolved against the existing node table; an unseen natural key receives a newly allocated `node_id`, dense and never reused. Existing natural keys are not renumbered — a node identity refers to the same logical entity for the life of a published graph version (`INV-OBS-009`).
2. **Edge upsert**: `DataLineage` and `AgentOutcome` rows resolve their natural keys to `node_id` and are inserted as `(node_i, node_j, edge_type, weight)`, deduplicated on `(node_i, node_j, edge_type)`.
3. Only active `DataLineage` rows, those with `is_active` set, are loaded, matching `INV-OBS-006`'s stability guarantee: a retired flow does not appear as a live edge in the graph.

**Exposure planes**, one set per graph key (one per data product):

| Plane | Holds | Populated by |
|---|---|---|
| Data | The node and edge relations | Load path above |
| Consumer surface | The node and edge projection in the shape the graph consumer contract defines: the only surface external consumers bind to | Derived from the data plane |
| Access | Read on the consumer surface, granted to the `ROLE_READ` and `ROLE_AGENT` tiers | Access layer |
| Catalogue | The graph's registry entry, relationship vocabulary, role vocabulary and trace profiles | One-time registration, updated only on vocabulary change |

Physical names for every plane arrive through the build context, never from this document. The graph consumer contract is part of the platform binding, so a name it fixes is a constant of the binding; every other name comes from the organisation profile. Where the contract requires a read principal of its own, that principal is likewise a binding constant, not a design or profile fact. The shared graph catalogue and engine belong to the graph tooling, not the product: a product registers into them and does not recreate them.

**Trace profiles**, registered in the graph catalogue:

| `profile_id` | `direction` | `relationship` | `stop_at_roles` | Purpose |
|---|---|---|---|---|
| `trace_to_source` | `upstream` | `produces`(`,derives_column` if `column-lineage` enabled) | — | Where did this table/column come from? |
| `impact_analysis` | `downstream` | `produces`(`,derives_column` if `column-lineage` enabled) | — | What breaks if this table/column changes? |
| `who_touched_this` | `downstream` | `accessed_by`(`,queried_in` if session nodes are included) | `session` if session nodes are included | Which agents/sessions have consumed this data? |

---

## 6. Open Standards Alignment

The lineage entities align with **OpenLineage**: the definition/execution split mirrors OpenLineage's separation of a `Job` (declared flow → `DataLineage`) from a `Run` (execution → `LineageRun`). `source`/`target` container+table compose into OpenLineage dataset names; `openlineage_namespace` and `openlineage_job_name`/`openlineage_run_id` carry the OpenLineage identifiers. The namespace is organisation or deployment configuration, never supplied by a designer; what a cycle's lineage covers is the `Lineage:` block's `Scope`, and its jobs are the block's declared flows. Data-quality dimensions are the five standard categories of `DEC-QUALITY-STORAGE`, and checks are the quality functions of the specification's expression vocabulary. The concrete event construction is an implementation concern.

---

## 7. Applied Patterns

| Pattern | Contribution to Observability |
|---------|-------------------------------|
| `temporal-lifecycle-metadata` | Event entities declare the `EVENT_APPEND_ONLY` profile; `DataLineage` declares `CURRENT_STATE` and carries an `is_active` lifecycle. When `graph-lineage` is enabled, its node/edge tables carry `created_dts` as provenance only, never business validity. |
| `object-placement` | The organisation profile places this module's relations, the validation relations, the discovery views and, when `graph-lineage` is enabled, the graph exposure planes; this module dictates no placement. |
| `access-layer` | `ROLE_AGENT` write-back (append) to this module: agents record outcomes and quality signals (Phase 2.5). When `graph-lineage` is enabled, the graph's consumer surface is granted to `ROLE_READ` and `ROLE_AGENT`. |
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

A product that does not enable `graph-lineage` gets the tabular `LineageGraph` discovery view (§5) only. A product that enables it also carries the specification's `Graph:` block ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.14). Whether `column-lineage` is enabled is recorded by the facet itself, not by a decision. A product that enables `graph-lineage` but not `column-lineage` gets the full graph exposure at table grain: it does not populate the column extension, and its catalogue registration omits the `derives_column` relationship and `COLUMN` role, so an agent can tell the capability is absent from the catalogue alone rather than by tracing an empty result.

**Provides:**

| Capability | Facet | Made available to |
|------------|-------|-------------------|
| `ChangeEventCapture` | — | Any module recording who changed an entity instance, when, and why: the audit trail that `DEC-COLUMN-STRATEGY` offloads here. |
| `LineageCapture` | — | Any module recording the origin of an instance: source system, source record, and producing run. |
| `AgentOutcomeCapture` | — | Any module or exposure layer recording which tables an agent touched, when, and with what outcome (`AgentOutcome`). |
| `QualityScore` | — | Agents judging fitness before use, and Memory as a learning input. Held as a time series per `DEC-QUALITY-STORAGE`. |
| Validation results home | — | The validation pattern, as the owner of `ValidationRun` and the `ValidationArea` trust map. |
| Lineage exposure (definitional + operational) | — | Agents and dashboards, via the `LineageGraph` and `LineageRunLatest` discovery views registered in Semantic. |
| `GraphNativeLineageTraversal` | `graph-lineage` | Graph-native lineage tooling and any agent or analyst using it: upstream/downstream trace, impact analysis, and access-path traversal over this product's lineage. |
| `ColumnGrainLineageTraversal` | `column-lineage` | Graph-native lineage tooling and any agent or analyst using it: column-to-column derivation trace, in addition to table-grain trace. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on every object. |
| `SemanticRegistration` | `[soft]` | `module:Semantic` | Register its entities, the validation relations and the discovery views, so agents find them through Semantic. |
| `DocumentationCapture` | `[soft]` | `module:Memory` | Record its own design decisions. |
| `EntityJoinBack` | `[soft]` | `module:Domain` | Resolve a table reference to Domain context when needed. |
| Graph platform runtime | `[hard]`, only when `graph-lineage` is enabled | `external:graph-platform` | Catalogue, engine, and quality procedures the `graph-lineage` facet's package does not itself define. |

---

## 9. Integration with Other Modules

- **Observability → Memory**: outcomes and quality trends feed Memory's learned strategies (the closed loop). Memory soft-requires these learning inputs.
- **Observability + Domain**: table-level change tracking of Domain loads; one event per batch, never per record.
- **Observability monitors all modules**: quality, performance, and lineage across every module in the composition. The monitored modules are the composition; they are not a separate design choice.
- **Observability → Semantic**: its entities, the validation relations and the `LineageGraph` and `LineageRunLatest` discovery views register in Semantic like any other relation.
- **Observability + external `graph-platform`**: when `graph-lineage` is enabled, hard-depends on the shared catalogue, engine, and quality procedures (§8); provides no capability the platform itself does not already define, only this product's specific graph. The graph key is recorded on the product's `DataProductMap` rows for Observability, so a consumer resolves it from metadata. The graph's node and edge relations are not registered as product entities: they are a separate, heavier exposure for graph-native tooling, described by that tooling's catalogue, while `LineageGraph` (§5) stays the discovery edge list.

---

## 10. Invariants

- `INV-OBS-001`: Observability stores events and metrics, never business data or query result sets.
- `INV-OBS-002`: change tracking is table-level with aggregate metrics (e.g. `records_affected`), never individual record keys, and **never** before/after business values: capturing changed column *values* (e.g. old/new `legal_name`, `email`) duplicates Domain content into Observability and is a PII / data-privacy defect. The audit trail records *what table changed, when, by whom, and how many rows*: not the data itself; the prior state is reconstructed from Domain's temporal history.
- `INV-OBS-003`: lineage is split: `DataLineage` declares flows (one row per source → job → target), `LineageRun` records executions (one row per run).
- `INV-OBS-004`: definitional lineage is retained for the life of the product; execution records follow independent event-retention windows.
- `INV-OBS-005`: validation results are homed here as append-only evidence (`EVENT_APPEND_ONLY`), both the run record and the per-area trust map.
- `INV-OBS-006`: the `LineageGraph` edge list consumed by discovery reads active definitions only, so it is stable and deduplicated.
- `INV-OBS-007`: when `graph-lineage` is enabled, its node/edge tables are a read-derived exposure of `DataLineage`/`AgentOutcome`; they carry table/column/job/agent identifiers only, never business row data, and are never written back into by anything else.
- `INV-OBS-008`: one data product registers exactly one lineage graph, under the graph key the organisation profile derives from its product code (§5.1); `community` is never used to encode product ownership.
- `INV-OBS-009`: a graph node's surrogate `node_id`, once allocated, refers to the same logical entity for the life of the published graph version; natural-key resolution never reuses or shifts an existing `node_id` value.

---

## 11. Designer Responsibilities

**Designers supply**, in the design specification: the `Quality:` block (dimension weights, rules with their check functions and thresholds, and validation frequency); the `Lineage:` block (declared flows, and the `Scope` that sets the OpenLineage scope); the `Retention:` block (separately for `DataLineage` and `LineageRun`, within the organisation profile's bounds); whether the `graph-lineage` facet is enabled and, if so, the `Graph:` block (session nodes, load cadence and any schedule); and whether `column-lineage` is also enabled.

**Not designer-supplied:** the monitored modules, which are the composition; the OpenLineage namespace, which is organisation or deployment configuration; the graph key, which the organisation profile derives; and the graph consumer contract and the names it fixes, which belong to the platform binding.

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] The specification carries the `Quality:`, `Lineage:` and `Retention:` blocks, and the `Graph:` block when `graph-lineage` is enabled ([Design Specification Standard](../core/DESIGN_SPECIFICATION.md) §4.1).
- [ ] Events/metrics only; no business data or result sets (`INV-OBS-001`).
- [ ] Change tracking is table-level with aggregate metrics (`INV-OBS-002`).
- [ ] Lineage flows registered in `DataLineage`; executions logged in `LineageRun` (`INV-OBS-003`).
- [ ] Separate retention policies for definition vs execution (`INV-OBS-004`).
- [ ] Validation results homed here (`INV-OBS-005`); `LineageGraph` and `LineageRunLatest` registered in Semantic.
- [ ] Entities registered in the Semantic map (`SemanticRegistration`); documentation captured, including the lineage split as a design decision.
- [ ] If `graph-lineage` is enabled: the `Graph:` block settles session nodes and load cadence; one graph for the product, under the graph key the organisation profile derives (`INV-OBS-008`), recorded on this product's `DataProductMap.graph_key` (`OBSERVABILITY` rows) so a consumer resolves it from metadata, never from a naming convention; catalogue entries registered before the consumer surface is published; the consumer surface granted to `ROLE_READ` and `ROLE_AGENT` only.
- [ ] `column-lineage` enabled only if column-level lineage is in scope for this product; the `DataLineage` column extension populated and catalogue rows registered together, never one without the other.
- [ ] This document passes the design linter with no ignore directive.

---

### 11.1 Decisions to settle

These are the catalogued decisions an Observability module design must settle. The recommendation is this standard's default; the question is what shifts it. The design skill walks a designer through each one at design time and records the answer in the design specification. The two graph decisions apply only when the `graph-lineage` facet is enabled, and are settled in the specification's `Graph:` block rather than its frontmatter.


| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-QUALITY-STORAGE` | `observability` | Does anything examine quality trend or per-rule detail, or only the latest score? |
| `DEC-AUDIT-RETENTION` | `regulatory` | Which entities carry a retention obligation, and how long does it run? |
| `DEC-TIMESTAMP-ZONE` | `zone-aware` | Are events recorded across regions? |
| `DEC-GRAPH-SESSION-NODES` | omit | Settled in the Graph block, only when graph-lineage is enabled: is session-level access traversal (`query_session` nodes) actually queried, or does `agent`-level suffice? |
| `DEC-GRAPH-LOAD-CADENCE` | with-lineage | Settled in the Graph block, only when graph-lineage is enabled: do graph consumers tolerate staleness up to a schedule interval, or must the graph never be behind its sources? |

---

## 12. Implementation

Each platform binding provides the event, metric, and lineage tables, the `LineageGraph` and `LineageRunLatest` discovery views, the OpenLineage event construction, and, when `graph-lineage` is enabled, the graph exposure planes, catalogue registration and load path, in `implementation/{platform}/modules/observability/`. It conforms to the [Platform Implementation Authoring Standard](../core/IMPLEMENTATION_AUTHORING.md). The validation results relations are realised by that platform's binding of the [validation pattern](../patterns/validation.md) and placed per the organisation profile.

A binding that supports `graph-lineage` names the graph consumer contract it targets and conforms to it. That contract's column shapes, catalogue definitions and quality procedures belong to its owner and are not redefined here; a platform with no graph consumer contract reports the facet as unsupported. Adding a platform changes nothing in this document.

---

**End of Observability Module Design Standard**
