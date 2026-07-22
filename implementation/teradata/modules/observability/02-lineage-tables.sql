-- Observability module — lineage tables (Teradata). Binding of design/modules/observability.md §3.
-- Definition/execution split: data_lineage (one row per flow) + lineage_run (one row per execution).
-- Replace {{ product }}.

-- data_lineage: DEFINITIONAL — one row per source -> job -> target -----------
CREATE TABLE {{ product }}_Observability.data_lineage (
    lineage_id            INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    source_database       VARCHAR(128),
    source_table          VARCHAR(100),
    source_system         VARCHAR(100),         -- external origin; NULL if internal
    target_database       VARCHAR(128),
    target_table          VARCHAR(100) NOT NULL,
    job_name              VARCHAR(200),
    transformation_type   VARCHAR(50),          -- ETL, FEATURE_ENG, AGGREGATION, JOIN, EMBEDDING_GEN, ...
    transformation_logic  VARCHAR(4000),
    openlineage_job_name  VARCHAR(200),
    openlineage_namespace VARCHAR(200),
    is_active             BYTEINT NOT NULL DEFAULT 1,   -- 1 = live flow, 0 = retired
    registered_dts        TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    retired_dts           TIMESTAMP(6) WITH TIME ZONE, -- set when is_active -> 0
    created_at            TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (lineage_id);

COMMENT ON TABLE {{ product }}_Observability.data_lineage IS
'Definitional data lineage - declares structural data flows (source -> job -> target). One row per flow. Changes only when pipeline design changes. Retained for the life of the product.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.source_database IS 'Source container - where input originates.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.source_table IS 'Input table for the transformation.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.source_system IS 'External source system - NULL if internal.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.target_database IS 'Target container - where output is written.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.target_table IS 'Output table.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.job_name IS 'ETL job / pipeline step.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.transformation_type IS 'ETL, FEATURE_ENG, AGGREGATION, JOIN, EMBEDDING_GEN, ...';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.transformation_logic IS 'SQL, algorithm, or prose description.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.openlineage_job_name IS 'OpenLineage job identifier.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.openlineage_namespace IS 'OpenLineage namespace (environment/cluster).';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.is_active IS '1 = live flow, 0 = retired (preserved for history).';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.registered_dts IS 'When the flow was first registered.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.retired_dts IS 'When retired - NULL while active.';
COMMENT ON COLUMN {{ product }}_Observability.data_lineage.created_at IS 'When this definition row was created.';

-- lineage_run: OPERATIONAL — one row per execution --------------------------
CREATE TABLE {{ product }}_Observability.lineage_run (
    lineage_run_id     INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    lineage_id         INTEGER NOT NULL,         -- FK -> data_lineage.lineage_id
    run_dts            TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    run_status         VARCHAR(20) NOT NULL,     -- SUCCESS, FAILED, PARTIAL, RUNNING
    run_duration_ms    INTEGER,
    records_read       INTEGER,
    records_written    INTEGER,
    records_rejected   INTEGER,
    batch_key          VARCHAR(100),             -- links to change_event.batch_key
    job_name           VARCHAR(200),             -- denormalised for fast querying
    openlineage_run_id VARCHAR(200),             -- per-execution UUID
    error_message      VARCHAR(2000),
    created_at         TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (lineage_run_id);

COMMENT ON TABLE {{ product }}_Observability.lineage_run IS
'Operational lineage execution log - one row per execution of a declared flow. Event-scale volume; independent retention window.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.lineage_id IS 'FK to data_lineage.lineage_id - the flow this execution runs.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.run_dts IS 'When the run started.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.run_status IS 'SUCCESS, FAILED, PARTIAL, RUNNING.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.run_duration_ms IS 'Wall-clock execution time.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.records_read IS 'Input volume.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.records_written IS 'Output volume.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.records_rejected IS 'Rows rejected during transformation.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.batch_key IS 'Links to change_event.batch_key for the same ETL cycle.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.job_name IS 'Denormalised job name for fast filtering.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.openlineage_run_id IS 'OpenLineage run UUID.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.error_message IS 'Error captured on FAILED/PARTIAL runs.';
COMMENT ON COLUMN {{ product }}_Observability.lineage_run.created_at IS 'When this run row was created.';

-- Retention: data_lineage = life of product; lineage_run = configurable (90-365 days).
