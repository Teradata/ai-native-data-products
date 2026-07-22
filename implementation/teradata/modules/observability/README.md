# Teradata — Observability Module Implementation

Teradata binding of [`design/modules/observability.md`](../../../../design/modules/observability.md).
Operational evidence: events, metrics, lineage, and the home of validation results. Read the design
document first. Replace `{{ product }}`; tables live in `{{ product }}_Observability`, the lineage
discovery views deploy into `{{ product }}_Semantic`.

## Files

| File | Purpose |
|------|---------|
| `01-event-tables.sql` | `change_event`, `data_quality_metric`, `model_performance`, `agent_outcome`. |
| `02-lineage-tables.sql` | `data_lineage` (definitional) and `lineage_run` (operational). |
| `03-lineage-views.sql` | `lineage_graph` and `lineage_run_latest` — deployed into the Semantic container. |
| `04-openlineage.md` | OpenLineage entity/column mapping and RunEvent construction. |

**Validation results.** The `validation_run` table and its `validation_latest` gate view are defined
by the [validation pattern implementation](../../patterns/validation/) and deployed into this
module's `{{ product }}_Observability` container. This module does not redefine them.

## Capability bindings

| Capability (design) | Teradata binding |
|---------------------|------------------|
| Outcome & quality evidence | `agent_outcome`, `data_quality_metric` — read by Memory's closed-loop learning. |
| Validation results home | Hosts the validation pattern's `validation_run`. |
| Lineage | `data_lineage` + `lineage_run`, exposed via `lineage_graph` / `lineage_run_latest` in Semantic. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN`. |
| `access-layer` write-back | `ROLE_AGENT` holds `INSERT` here (Phase 2.5). |

## Invariants → checks

| Invariant | How enforced |
|-----------|--------------|
| `INV-OBS-002` (table-level, aggregate) | Schema: `records_affected` count, `table_name` only — no instance-key columns. |
| `INV-OBS-003` (lineage split) | Two tables: `data_lineage` (one row per flow) + `lineage_run` (one row per execution, FK to definition). |
| `INV-OBS-005` (validation home) | `validation_run` deployed here (validation pattern), profile `EVENT_APPEND_ONLY`. |
| `INV-OBS-006` (stable graph) | `lineage_graph` reads `data_lineage WHERE is_active = 1` only. |
