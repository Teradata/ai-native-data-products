-- Observability module — event and metric tables (Teradata).
-- Binding of design/modules/observability.md §4. Events and metrics, not data; table-level.
-- Replace {{ product }}.

-- change_event: table-level change tracking (aggregate, not per-record) -------
CREATE TABLE {{ product }}_Observability.change_event (
    change_event_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    database_name VARCHAR(128),
    table_name VARCHAR(128) NOT NULL,
    change_type VARCHAR(20) NOT NULL,       -- INSERT, UPDATE, DELETE, MERGE, TRUNCATE
    change_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    changed_by VARCHAR(100) NOT NULL,
    change_reason VARCHAR(500),
    change_source VARCHAR(50),              -- ETL, API, MANUAL, AGENT
    records_affected INTEGER,               -- aggregate count, never individual keys
    columns_changed VARCHAR(1000),
    batch_key VARCHAR(100),
    job_name VARCHAR(200),
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (change_event_id);

COMMENT ON TABLE {{ product }}_Observability.change_event IS
'Table-level change event tracking - aggregated changes for audit trail, NOT individual record details.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.database_name IS 'Container where the change occurred.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.table_name IS 'Table changed - table-level, not per-record.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.change_type IS 'INSERT, UPDATE, DELETE, MERGE, TRUNCATE.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.change_dts IS 'When the change occurred.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.changed_by IS 'User or process that made the change.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.change_reason IS 'Business justification or trigger.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.change_source IS 'ETL, API, MANUAL, AGENT.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.records_affected IS 'Aggregate count of records affected - scale monitoring, not keys.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.columns_changed IS 'Comma-separated modified column names.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.batch_key IS 'Batch identifier - links related changes in one run.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.job_name IS 'Job/process that made the change.';
COMMENT ON COLUMN {{ product }}_Observability.change_event.created_at IS 'When this event record was created.';

-- data_quality_metric --------------------------------------------------------
CREATE TABLE {{ product }}_Observability.data_quality_metric (
    quality_metric_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    database_name VARCHAR(128),
    table_name VARCHAR(128) NOT NULL,
    column_name VARCHAR(128),               -- NULL for table-level metrics
    metric_name VARCHAR(128) NOT NULL,      -- COMPLETENESS, VALIDITY, UNIQUENESS, TIMELINESS, CONSISTENCY, ACCURACY
    metric_value DECIMAL(10,4),
    metric_category VARCHAR(50),
    measured_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    quality_threshold DECIMAL(5,4),
    is_threshold_met BYTEINT NOT NULL DEFAULT 0,
    sample_size INTEGER,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (quality_metric_id);

COMMENT ON TABLE {{ product }}_Observability.data_quality_metric IS
'Data quality metrics by table and column - quality trends over time for monitoring and alerting.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.database_name IS 'Container of the measured table.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.table_name IS 'Table being measured.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.column_name IS 'Column measured - NULL for table-level.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.metric_name IS 'COMPLETENESS, VALIDITY, UNIQUENESS, TIMELINESS, CONSISTENCY, ACCURACY.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.metric_value IS 'Measured value, typically 0.0-1.0.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.metric_category IS 'Groups related metrics.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.measured_dts IS 'When measured - enables trend analysis.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.quality_threshold IS 'Minimum acceptable value.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.is_threshold_met IS '1 = passes, 0 = fails - enables alerting.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.sample_size IS 'Records analysed for the measurement.';
COMMENT ON COLUMN {{ product }}_Observability.data_quality_metric.created_at IS 'When this metric row was created.';

-- model_performance ----------------------------------------------------------
CREATE TABLE {{ product }}_Observability.model_performance (
    performance_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    model_key VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    metric_name VARCHAR(128) NOT NULL,      -- ACCURACY, PRECISION, RECALL, AUC, LATENCY_MS, DRIFT_SCORE
    metric_value DECIMAL(10,6),
    evaluation_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    sample_size INTEGER,
    is_sla_met BYTEINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (performance_id);

COMMENT ON TABLE {{ product }}_Observability.model_performance IS
'Model performance metrics over time - accuracy, latency, and drift for monitoring.';
COMMENT ON COLUMN {{ product }}_Observability.model_performance.model_key IS 'Model identifier.';
COMMENT ON COLUMN {{ product }}_Observability.model_performance.model_version IS 'Model version evaluated.';
COMMENT ON COLUMN {{ product }}_Observability.model_performance.metric_name IS 'ACCURACY, PRECISION, RECALL, AUC, LATENCY_MS, DRIFT_SCORE.';
COMMENT ON COLUMN {{ product }}_Observability.model_performance.metric_value IS 'Measured performance value.';
COMMENT ON COLUMN {{ product }}_Observability.model_performance.evaluation_dts IS 'When performance was measured.';
COMMENT ON COLUMN {{ product }}_Observability.model_performance.sample_size IS 'Predictions evaluated.';
COMMENT ON COLUMN {{ product }}_Observability.model_performance.is_sla_met IS '1 = meets SLA, 0 = below - enables alerting.';
COMMENT ON COLUMN {{ product }}_Observability.model_performance.created_at IS 'When this row was created.';

-- agent_outcome --------------------------------------------------------------
CREATE TABLE {{ product }}_Observability.agent_outcome (
    outcome_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    agent_key VARCHAR(100) NOT NULL,
    session_key VARCHAR(100),
    action_type VARCHAR(50) NOT NULL,       -- QUERY, RECOMMENDATION, DECISION, PREDICTION
    action_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    tables_accessed VARCHAR(1000),          -- comma-separated, TABLE LEVEL
    outcome_status VARCHAR(20) NOT NULL,    -- SUCCESS, PARTIAL, FAILED
    user_feedback VARCHAR(20),              -- POSITIVE, NEUTRAL, NEGATIVE, CORRECTION
    execution_time_ms INTEGER,
    records_processed INTEGER,              -- aggregate count
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (outcome_id);

COMMENT ON TABLE {{ product }}_Observability.agent_outcome IS
'Agent action outcomes and user feedback - enables closed-loop learning by tracking what worked. Read by Memory.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.agent_key IS 'Agent that performed the action.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.session_key IS 'Links to the agent session context.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.action_type IS 'QUERY, RECOMMENDATION, DECISION, PREDICTION.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.action_dts IS 'When the action was performed.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.tables_accessed IS 'Comma-separated qualified table names - TABLE LEVEL.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.outcome_status IS 'SUCCESS, PARTIAL, FAILED.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.user_feedback IS 'POSITIVE, NEUTRAL, NEGATIVE, CORRECTION.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.execution_time_ms IS 'Action execution time.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.records_processed IS 'Aggregate count, not keys.';
COMMENT ON COLUMN {{ product }}_Observability.agent_outcome.created_at IS 'When this row was created.';
