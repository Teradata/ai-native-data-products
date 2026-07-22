# Observability — OpenLineage Alignment (Teradata)

Binding of [`design/modules/observability.md`](../../../../design/modules/observability.md) §6. The
lineage tables align with [OpenLineage](https://openlineage.io/): the definition/execution split
mirrors OpenLineage's `Job` (declared flow) vs `Run` (execution).

## Entity mapping

| OpenLineage | Our table | Key columns |
|-------------|-----------|-------------|
| `Job` | `data_lineage` | `openlineage_job_name`, `openlineage_namespace`, `job_name` |
| `Run` | `lineage_run` | `openlineage_run_id`, `run_dts`, `run_status` |
| `InputDataset` | `data_lineage` | `source_database`, `source_table` |
| `OutputDataset` | `data_lineage` | `target_database`, `target_table` |

OpenLineage identifies datasets by `namespace` + `name`. Teradata convention: namespace
`teradata://{host}:{port}`, name `{database}.{table}`. Our `source_database.source_table` and
`target_database.target_table` compose directly into `name`; the namespace prefix is supplied at
emission time.

## Column mapping

**Definitional → JobEvent:** `openlineage_namespace` → Job.namespace; `openlineage_job_name` →
Job.name; source/target → Input/OutputDataset.name; `transformation_logic` → `sql`/`sourceCode`
facet; `registered_dts` → JobEvent.eventTime.

**Operational → RunEvent:** `openlineage_run_id` → Run.runId; `run_dts` → RunEvent.eventTime;
`run_status` → eventType (`SUCCESS`→COMPLETE, `FAILED`→FAIL, `RUNNING`→START, `PARTIAL`→COMPLETE);
`records_read`/`records_written` → input/output statistics facets (rowCount); `error_message` → Run
`errorMessage` facet.

## Event construction

Construct a RunEvent by joining `lineage_run` to `data_lineage` and composing a JSON object with
native JSON functions (`JSON_COMPOSE`, `JSON_AGG`) for correct typing and escaping — one payload per
execution, suitable for emission to Marquez / Amundsen / a collector.

```json
{
  "eventTime": "2026-04-09T02:15:33.123456+00:00",
  "eventType": "COMPLETE",
  "run":  { "runId": "3b452093-782c-4ef2-9c0c-aafe2aa6f34d" },
  "job":  { "namespace": "airflow://prod-scheduler", "name": "Product_ETL.ETL_PARTY_FEATURES" },
  "input":  { "namespace": "teradata://host:1025", "name": "Product_Domain.Party_H", "rowCount": 250000 },
  "output": { "namespace": "teradata://host:1025", "name": "Product_Prediction.customer_features", "rowCount": 248500 },
  "producer": "https://teradata.com/ai-native-data-product",
  "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/definitions/RunEvent"
}
```

## Notes

- **Run lifecycle**: we store a single final-status row per execution (pragmatic for Teradata). Full
  START/COMPLETE lifecycle can be added by allowing multiple rows per `openlineage_run_id`.
- **Multi-input jobs**: a job with several inputs is several `data_lineage` rows sharing `job_name`;
  aggregate into one event with `JSON_AGG`.
- **Custom facets**: `transformation_type`, `batch_key`, `records_rejected` have no standard facet —
  emit as project-prefixed custom facets.
- **Data freshness**: derive from `MAX(lineage_run.run_dts)` per active flow where `run_status = 'SUCCESS'`.
