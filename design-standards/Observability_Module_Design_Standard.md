# Observability Module Design Standard
## AI-Native Data Product Architecture - Version 1.6

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.6 |
| **Status** | STANDARD |
| **Last Updated** | 2026-04-15 |
| **Owner** | Nathan Green, Worldwide Data Architecture Team, Teradata |
| **Scope** | Observability Module (Monitoring & Feedback) |
| **Type** | Design Standard (Structural Requirements) |

---

## Table of Contents

1. [AI-Native Observability Module Overview](#1-ai-native-observability-module-overview)
2. [Module Scope and Boundaries](#2-module-scope-and-boundaries)
3. [Core Observability Tables](#3-core-observability-tables)
4. [Semantic Views](#4-semantic-views)
5. [Open Standards Integration](#5-open-standards-integration)
6. [Integration with Other Modules](#6-integration-with-other-modules)
7. [Designer Responsibilities](#7-designer-responsibilities)

---

> **Platform Note:** All DDL and SQL examples in this standard use **Teradata** syntax (e.g. `REPLACE VIEW`, `LOCKING ROW FOR ACCESS`, `DBC.TablesV`, `'0A'xc` hex literals). When implementing on a different database platform, these examples must be converted to the target vendor's equivalent DDL. The structural design — table schemas, column contracts, view logic, and module boundaries — is platform-agnostic.

---

## 1. AI-Native Observability Module Overview

### 1.1 Primary Purpose

The Observability Module monitors data product health and enables continuous improvement through outcome tracking and feedback loops.

**Key capabilities**:
- Data quality monitoring
- Change tracking (audit trail)
- Data lineage (provenance) — definitional and operational
- Performance monitoring
- Outcome tracking

### 1.2 Critical Principle: Events and Metrics, Not Data

Observability stores **events and metrics**, not business data:
- ✅ "Party record 1001 was updated by john.doe at 2024-03-15"
- ❌ NOT the customer's actual details
- ✅ "Data quality score for Party_H: 0.95"
- ❌ NOT the actual Party records

### 1.3 Lineage Separation Principle: Definition vs Execution

Lineage is modelled as two distinct concerns:

| Concern | Table | Question it answers | Row cardinality |
|---------|-------|-------------------|-----------------|
| **Definitional** | `data_lineage` | *"What are the declared data flows?"* | One row per source → job → target |
| **Operational** | `lineage_run` | *"Did this flow run, and how did it go?"* | Many rows per flow over time |

This separation ensures:
- ✅ Graph visualisation consumes a stable, deduplicated edge list (definition only)
- ✅ Execution monitoring follows the "events and metrics" principle
- ✅ Independent retention policies — definitions live as long as the product; execution records follow event-retention windows
- ✅ Clear mutation semantics — a new INSERT into `data_lineage` means a new flow; a new INSERT into `lineage_run` means a new execution of an existing flow

---

## 2. Module Scope and Boundaries

**IN SCOPE**:
- Change events (what, when, who, why)
- Data quality metrics
- Data lineage — definition (declared flows) and execution (run history) (OpenLineage aligned)
- Performance metrics
- Outcome tracking

**OUT OF SCOPE**:
- ❌ Business domain data → Domain Module
- ❌ Query result sets → Not stored

---

## 3. Core Observability Tables

### 3.1 change_event (Table-Level Change Tracking)

```sql
CREATE TABLE Observability.change_event (
    change_event_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- What changed (TABLE LEVEL - not individual records)
    database_name VARCHAR(128),
    table_name VARCHAR(128) NOT NULL,
    
    -- Change details
    change_type VARCHAR(20) NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'TRUNCATE'
    change_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    
    -- Who and why
    changed_by VARCHAR(100) NOT NULL,
    change_reason VARCHAR(500),
    change_source VARCHAR(50),  -- 'ETL', 'API', 'MANUAL', 'AGENT'
    
    -- Aggregate metrics (table-level summary)
    records_affected INTEGER,  -- How many records changed
    columns_changed VARCHAR(1000),  -- Comma-separated list of columns modified
    
    -- Batch/job tracking
    batch_key VARCHAR(100),
    job_name VARCHAR(200),
    
    -- Metadata
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (change_event_id);

COMMENT ON TABLE Observability.change_event IS 
'Table-level change event tracking - records aggregated changes for audit trail, NOT individual record details';

COMMENT ON COLUMN Observability.change_event.change_event_id IS 
'Surrogate key for change event record';

COMMENT ON COLUMN Observability.change_event.database_name IS 
'Database where change occurred';

COMMENT ON COLUMN Observability.change_event.table_name IS 
'Table that was changed - table-level tracking, not individual record tracking';

COMMENT ON COLUMN Observability.change_event.change_type IS 
'Type of change - INSERT (new records), UPDATE (modified), DELETE (removed), MERGE (upsert), TRUNCATE (full table clear)';

COMMENT ON COLUMN Observability.change_event.change_dts IS 
'Timestamp when change occurred';

COMMENT ON COLUMN Observability.change_event.changed_by IS 
'User or process that made the change - ETL_NIGHTLY, john.doe, API_SERVICE, etc.';

COMMENT ON COLUMN Observability.change_event.change_reason IS 
'Reason for change - business justification or trigger for modification';

COMMENT ON COLUMN Observability.change_event.change_source IS 
'Source of change - ETL (batch process), API (application), MANUAL (human user), AGENT (AI agent)';

COMMENT ON COLUMN Observability.change_event.records_affected IS 
'Number of records affected by change - aggregate count for table-level tracking, enables scale monitoring';

COMMENT ON COLUMN Observability.change_event.columns_changed IS 
'Columns modified - comma-separated list of column names that were updated';

COMMENT ON COLUMN Observability.change_event.batch_key IS 
'Batch identifier name - links related changes in same ETL run or transaction';

COMMENT ON COLUMN Observability.change_event.job_name IS 
'Job or process name - identifies the ETL job, API endpoint, or process that made change';

COMMENT ON COLUMN Observability.change_event.created_at IS 
'Timestamp when change event record was created in Observability module';
```

**Example**:
```sql
-- ETL updates 125,000 Party records
INSERT INTO Observability.change_event (
    database_name, table_name, change_type, change_dts,
    changed_by, change_source, records_affected, batch_key
) VALUES (
    'Domain', 'Party_H', 'UPDATE', CURRENT_TIMESTAMP(6),
    'ETL_NIGHTLY', 'ETL', 125000, 'BATCH-2024-03-15-001'
);

-- NOT 125,000 separate change events!
```

**Benefits**:
- ✅ Consistent with Memory (table-level references)
- ✅ Scales efficiently (one event per batch, not per record)
- ✅ "Small answers" - aggregate metrics, not individual record tracking
- ✅ Sufficient for monitoring and audit (know what happened at table level)

### 3.2 data_quality_metric

```sql
CREATE TABLE Observability.data_quality_metric (
    quality_metric_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    database_name VARCHAR(128),
    table_name VARCHAR(128) NOT NULL,
    column_name VARCHAR(128),
    metric_name VARCHAR(128) NOT NULL,
    metric_value DECIMAL(10,4),
    metric_category VARCHAR(50),
    measured_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    quality_threshold DECIMAL(5,4),
    is_threshold_met BYTEINT NOT NULL DEFAULT 0,
    sample_size INTEGER,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (quality_metric_id);

COMMENT ON TABLE Observability.data_quality_metric IS 
'Data quality metrics by table and column - tracks quality trends over time for monitoring and alerting';

COMMENT ON COLUMN Observability.data_quality_metric.quality_metric_id IS 
'Surrogate key for quality metric record';

COMMENT ON COLUMN Observability.data_quality_metric.database_name IS 
'Database containing the measured table';

COMMENT ON COLUMN Observability.data_quality_metric.table_name IS 
'Table being measured for quality';

COMMENT ON COLUMN Observability.data_quality_metric.column_name IS 
'Column being measured - NULL for table-level metrics';

COMMENT ON COLUMN Observability.data_quality_metric.metric_name IS 
'Quality metric name - COMPLETENESS, VALIDITY, UNIQUENESS, TIMELINESS, CONSISTENCY, ACCURACY';

COMMENT ON COLUMN Observability.data_quality_metric.metric_value IS 
'Measured metric value - typically 0.0 to 1.0 range representing percentage or score';

COMMENT ON COLUMN Observability.data_quality_metric.metric_category IS 
'Metric category - COMPLETENESS, VALIDITY, CONSISTENCY, TIMELINESS - groups related metrics';

COMMENT ON COLUMN Observability.data_quality_metric.measured_dts IS 
'When metric was measured - enables quality trend analysis over time';

COMMENT ON COLUMN Observability.data_quality_metric.quality_threshold IS 
'Expected quality threshold - minimum acceptable value for this metric';

COMMENT ON COLUMN Observability.data_quality_metric.is_threshold_met IS 
'Threshold met indicator - 1 = passes quality check, 0 = fails quality check - enables alerting';

COMMENT ON COLUMN Observability.data_quality_metric.sample_size IS 
'Sample size used for measurement - number of records analyzed';

COMMENT ON COLUMN Observability.data_quality_metric.created_at IS 
'Timestamp when quality metric record was created';
```

### 3.3 data_lineage (Definitional — OpenLineage Aligned)

The `data_lineage` table declares the **structural data flows** within and into this data product. One row per unique source → job → target relationship. This table changes only when the pipeline design changes — not on every execution.

**Consumed by**: `lineage_graph` view, agent discovery, impact analysis.

```sql
CREATE TABLE Observability.data_lineage (
    lineage_id              INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY

    /* ── Source ─────────────────────────────────────────────────────────── */
   ,source_database         VARCHAR(128)
   ,source_table            VARCHAR(100)
   ,source_system           VARCHAR(100)          /* External origin; NULL if internal */

    /* ── Target ─────────────────────────────────────────────────────────── */
   ,target_database         VARCHAR(128)
   ,target_table            VARCHAR(100) NOT NULL

    /* ── Transformation ─────────────────────────────────────────────────── */
   ,job_name                VARCHAR(200)           /* ETL job / process name  */
   ,transformation_type     VARCHAR(50)            /* ETL, FEATURE_ENG, AGGREGATION, JOIN, EMBEDDING_GEN … */
   ,transformation_logic    VARCHAR(4000)          /* SQL, algorithm, or prose description */

    /* ── OpenLineage alignment ──────────────────────────────────────────── */
   ,openlineage_job_name    VARCHAR(200)           /* Job identifier in OpenLineage format */
   ,openlineage_namespace   VARCHAR(200)           /* Environment / cluster identifier    */

    /* ── Lifecycle ──────────────────────────────────────────────────────── */
   ,is_active               BYTEINT NOT NULL DEFAULT 1   /* 1 = live flow, 0 = retired */
   ,registered_dts          TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
   ,retired_dts             TIMESTAMP(6) WITH TIME ZONE  /* Set when is_active → 0 */

    /* ── Metadata ───────────────────────────────────────────────────────── */
   ,created_at              TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (lineage_id);

COMMENT ON TABLE Observability.data_lineage IS
'Definitional data lineage — declares structural data flows (source → job → target) within the data product. One row per unique flow. Changes only when pipeline design changes. Operational execution is tracked in lineage_run.';

COMMENT ON COLUMN Observability.data_lineage.lineage_id IS
'Surrogate key for lineage definition record';

COMMENT ON COLUMN Observability.data_lineage.source_database IS
'Source database name — where input data originates';

COMMENT ON COLUMN Observability.data_lineage.source_table IS
'Source table name — input table for transformation';

COMMENT ON COLUMN Observability.data_lineage.source_system IS
'External source system name — originating system for data. NULL if internal Teradata source';

COMMENT ON COLUMN Observability.data_lineage.target_database IS
'Target database name — where output data is written';

COMMENT ON COLUMN Observability.data_lineage.target_table IS
'Target table name — output table from transformation';

COMMENT ON COLUMN Observability.data_lineage.job_name IS
'Job or process name — identifies the ETL job, stored procedure, or pipeline step';

COMMENT ON COLUMN Observability.data_lineage.transformation_type IS
'Transformation type — ETL, FEATURE_ENG, AGGREGATION, JOIN, EMBEDDING_GEN, FILTER, PIVOT, etc.';

COMMENT ON COLUMN Observability.data_lineage.transformation_logic IS
'Transformation logic description — SQL, algorithm, or prose description of the transformation';

COMMENT ON COLUMN Observability.data_lineage.openlineage_job_name IS
'OpenLineage job name — job identifier in OpenLineage format for external lineage system correlation';

COMMENT ON COLUMN Observability.data_lineage.openlineage_namespace IS
'OpenLineage namespace — environment or cluster identifier (production, staging, etc.)';

COMMENT ON COLUMN Observability.data_lineage.is_active IS
'Active flag — 1 = live flow in current pipeline design, 0 = retired flow preserved for historical reference';

COMMENT ON COLUMN Observability.data_lineage.registered_dts IS
'Timestamp when this lineage flow was first registered — records when the flow entered the blueprint';

COMMENT ON COLUMN Observability.data_lineage.retired_dts IS
'Timestamp when this lineage flow was retired — NULL while active, set when is_active transitions to 0';

COMMENT ON COLUMN Observability.data_lineage.created_at IS
'Timestamp when lineage definition record was created';
```

**Example — Registering a lineage flow**:
```sql
-- Register the definitional flow (once, when pipeline is designed)
INSERT INTO Observability.data_lineage (
    source_database, source_table, source_system,
    target_database, target_table,
    job_name, transformation_type, transformation_logic
) VALUES (
    'Domain', 'Party_H', NULL,
    'Prediction', 'customer_features',
    'ETL_PARTY_FEATURES', 'FEATURE_ENG',
    'Extracts demographic and account features from Party_H for ML scoring'
);
```

### 3.4 lineage_run (Operational — Execution Log)

The `lineage_run` table records **every execution** of a declared lineage flow. One row per execution. Aligns with the Observability principle: events and metrics, not data.

**Consumed by**: Monitoring dashboards, SLA checks, data freshness calculations, Memory closed-loop learning.

**Volume**: Many rows per `lineage_id` over time (event-scale).

```sql
CREATE TABLE Observability.lineage_run (
    lineage_run_id          INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY

    /* ── Link to definition ─────────────────────────────────────────────── */
   ,lineage_id              INTEGER NOT NULL        /* FK → data_lineage.lineage_id */

    /* ── Execution details ──────────────────────────────────────────────── */
   ,run_dts                 TIMESTAMP(6) WITH TIME ZONE NOT NULL
   ,run_status              VARCHAR(20) NOT NULL     /* SUCCESS, FAILED, PARTIAL, RUNNING */
   ,run_duration_ms         INTEGER                  /* Wall-clock execution time           */

    /* ── Volume metrics ─────────────────────────────────────────────────── */
   ,records_read            INTEGER
   ,records_written         INTEGER
   ,records_rejected        INTEGER                  /* Rows that failed validation / transform */

    /* ── Batch correlation ──────────────────────────────────────────────── */
   ,batch_key               VARCHAR(100)             /* Links to change_event.batch_key     */
   ,job_name                VARCHAR(200)             /* Denormalised for fast querying       */

    /* ── OpenLineage alignment ──────────────────────────────────────────── */
   ,openlineage_run_id      VARCHAR(200)             /* Per-execution UUID from OpenLineage  */

    /* ── Error tracking ─────────────────────────────────────────────────── */
   ,error_message           VARCHAR(2000)            /* Captured on FAILED / PARTIAL runs    */

    /* ── Metadata ───────────────────────────────────────────────────────── */
   ,created_at              TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (lineage_run_id);

COMMENT ON TABLE Observability.lineage_run IS
'Operational lineage execution log — one row per execution of a declared lineage flow (data_lineage). Tracks run status, volume, duration, and errors. Event-scale volume expected.';

COMMENT ON COLUMN Observability.lineage_run.lineage_run_id IS
'Surrogate key for lineage run record';

COMMENT ON COLUMN Observability.lineage_run.lineage_id IS
'Foreign key to data_lineage.lineage_id — links this execution to its declared flow definition';

COMMENT ON COLUMN Observability.lineage_run.run_dts IS
'Execution timestamp — when the transformation run started';

COMMENT ON COLUMN Observability.lineage_run.run_status IS
'Execution status — SUCCESS (completed normally), FAILED (aborted), PARTIAL (completed with rejected rows), RUNNING (in progress)';

COMMENT ON COLUMN Observability.lineage_run.run_duration_ms IS
'Execution duration in milliseconds — wall-clock time from start to completion';

COMMENT ON COLUMN Observability.lineage_run.records_read IS
'Number of records read from source — input volume metric';

COMMENT ON COLUMN Observability.lineage_run.records_written IS
'Number of records written to target — output volume metric';

COMMENT ON COLUMN Observability.lineage_run.records_rejected IS
'Number of records rejected during transformation — validation failures, type mismatches, constraint violations';

COMMENT ON COLUMN Observability.lineage_run.batch_key IS
'Batch identifier — links to change_event.batch_key for cross-referencing lineage runs with change events in the same ETL cycle';

COMMENT ON COLUMN Observability.lineage_run.job_name IS
'Job name denormalised from data_lineage — enables fast filtering without joining to the definition table';

COMMENT ON COLUMN Observability.lineage_run.openlineage_run_id IS
'OpenLineage run UUID — per-execution identifier for correlation with external lineage systems (Marquez, Amundsen)';

COMMENT ON COLUMN Observability.lineage_run.error_message IS
'Error message captured on FAILED or PARTIAL runs — first 2000 characters of the error for diagnostic triage';

COMMENT ON COLUMN Observability.lineage_run.created_at IS
'Timestamp when lineage run record was created';
```

**Example — Logging an execution**:
```sql
-- Log each execution (every time the job runs)
INSERT INTO Observability.lineage_run (
    lineage_id, run_dts, run_status, run_duration_ms,
    records_read, records_written, records_rejected,
    batch_key, job_name
) VALUES (
    1,  /* FK to the definition registered in data_lineage */
    CURRENT_TIMESTAMP(6), 'SUCCESS', 45200,
    250000, 248500, 1500,
    'BATCH-2026-04-09-001', 'ETL_PARTY_FEATURES'
);
```

**Retention guidance**:

| Table | Retention | Rationale |
|-------|-----------|-----------|
| `data_lineage` | Life of data product | Blueprint — always needed for discovery and impact analysis |
| `lineage_run` | Configurable (90–365 days typical) | Event-scale volume; older runs can be aggregated or archived |

### 3.5 model_performance

```sql
CREATE TABLE Observability.model_performance (
    performance_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    model_key VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    metric_name VARCHAR(128) NOT NULL,
    metric_value DECIMAL(10,6),
    evaluation_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    sample_size INTEGER,
    is_sla_met BYTEINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (performance_id);

COMMENT ON TABLE Observability.model_performance IS 
'Model performance metrics over time - tracks ML model accuracy, latency, and drift for monitoring';

COMMENT ON COLUMN Observability.model_performance.performance_id IS 
'Surrogate key for performance metric record';

COMMENT ON COLUMN Observability.model_performance.model_key IS 
'Model identifier name - unique name of ML model being monitored';

COMMENT ON COLUMN Observability.model_performance.model_version IS 
'Model version - tracks which version of model is being evaluated';

COMMENT ON COLUMN Observability.model_performance.metric_name IS 
'Performance metric name - ACCURACY, PRECISION, RECALL, AUC, LATENCY_MS, DRIFT_SCORE, etc.';

COMMENT ON COLUMN Observability.model_performance.metric_value IS 
'Metric value - actual measured performance value';

COMMENT ON COLUMN Observability.model_performance.evaluation_dts IS 
'Evaluation timestamp - when performance was measured';

COMMENT ON COLUMN Observability.model_performance.sample_size IS 
'Evaluation sample size - number of predictions evaluated';

COMMENT ON COLUMN Observability.model_performance.is_sla_met IS 
'SLA met indicator - 1 = meets performance SLA, 0 = below threshold - enables alerting';

COMMENT ON COLUMN Observability.model_performance.created_at IS 
'Timestamp when performance record was created';
```

### 3.6 agent_outcome

```sql
CREATE TABLE Observability.agent_outcome (
    outcome_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    agent_key VARCHAR(100) NOT NULL,
    session_key VARCHAR(100),
    action_type VARCHAR(50) NOT NULL,
    action_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    tables_accessed VARCHAR(1000),
    outcome_status VARCHAR(20) NOT NULL,
    user_feedback VARCHAR(20),
    execution_time_ms INTEGER,
    records_processed INTEGER,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (outcome_id);

COMMENT ON TABLE Observability.agent_outcome IS 
'Agent action outcomes and user feedback - enables closed-loop learning by tracking what worked';

COMMENT ON COLUMN Observability.agent_outcome.outcome_id IS 
'Surrogate key for outcome record';

COMMENT ON COLUMN Observability.agent_outcome.agent_key IS 
'Agent identifier name - which agent performed this action';

COMMENT ON COLUMN Observability.agent_outcome.session_key IS 
'Session identifier name - links outcome to agent session context';

COMMENT ON COLUMN Observability.agent_outcome.action_type IS 
'Action type - QUERY, RECOMMENDATION, DECISION, PREDICTION - classifies agent action';

COMMENT ON COLUMN Observability.agent_outcome.action_dts IS 
'Action timestamp - when agent action was performed';

COMMENT ON COLUMN Observability.agent_outcome.tables_accessed IS 
'Tables accessed - comma-separated list of database.table names involved in action, TABLE LEVEL tracking';

COMMENT ON COLUMN Observability.agent_outcome.outcome_status IS 
'Outcome status - SUCCESS, PARTIAL, FAILED - indicates whether action achieved goal';

COMMENT ON COLUMN Observability.agent_outcome.user_feedback IS 
'User feedback - POSITIVE, NEUTRAL, NEGATIVE, CORRECTION - enables learning from human feedback';

COMMENT ON COLUMN Observability.agent_outcome.execution_time_ms IS 
'Execution time in milliseconds - performance metric for action';

COMMENT ON COLUMN Observability.agent_outcome.records_processed IS 
'Number of records processed - scale metric, aggregate count not individual keys';

COMMENT ON COLUMN Observability.agent_outcome.created_at IS 
'Timestamp when outcome record was created';
```

---

## 4. Semantic Views

The following views are deployed into the `{ProductName}_Semantic` database to enable agent discovery and graph visualisation of lineage data.

### 4.1 lineage_graph (Graph-Ready Edge List)

Transforms the **definitional** `data_lineage` table into a two-leg edge list (source → job, job → target) compatible with typically used Graph standards. Reads active flows only — no duplicate edges from repeated executions.

```sql
REPLACE VIEW Semantic.lineage_graph
(
    -- View contract: agents see all returned columns without parsing the SELECT body
    Src_Object_Name_FQ,
    Src_Container_Name,
    Src_Object_Name,
    Src_Kind,
    Src_Display_Name,
    Edge_Relationship,
    Transformation_Type,
    Transformation_Logic,
    Lineage_ID,
    Tgt_Object_Name_FQ,
    Tgt_Container_Name,
    Tgt_Object_Name,
    Tgt_Kind,
    Tgt_Display_Name
)
AS
/*
 * lineage_graph
 * ───────────────
 * Graph-ready edge list for data lineage with ETL jobs surfaced as
 * first-class nodes. Reads from the DEFINITIONAL data_lineage table
 * (not the execution log) — produces one stable edge per declared flow.
 *
 * Column contract matches the typical Graph standards for direct consumption
 *
 * Each data_lineage row becomes two edges:
 *   Leg 1: source_table  → job_name   (ETL_INPUT)
 *   Leg 2: job_name      → target_table (ETL_OUTPUT)
 *
 * Object types resolved from DBC.TablesV for Table nodes.
 * Job nodes carry Src_Kind / Tgt_Kind = 'Job'.
 *
 * IMPORTANT: All literal strings ('', 'ETL_INPUT', 'Job', etc.) and
 * job_name columns that appear on only one leg of the UNION ALL must
 * be explicitly CAST to a sufficient VARCHAR width. Without CASTs,
 * Teradata infers the column type from Leg 1 — a literal '' becomes
 * VARCHAR(0), truncating Leg 2's actual container names to empty.
 * Similarly, 'ETL_INPUT' (9 chars) truncates 'ETL_OUTPUT' to 'ETL_OUTPU'.
 */
LOCKING ROW FOR ACCESS

    /* ══════════════════════════════════════════════════════════════
     *  Leg 1: Source Table → Job (ETL_INPUT)
     * ══════════════════════════════════════════════════════════════ */
    SELECT
         COALESCE(dl.source_database, '') || '.' || dl.source_table  AS Src_Object_Name_FQ
        ,COALESCE(dl.source_database, '')                            AS Src_Container_Name
        ,dl.source_table                                             AS Src_Object_Name
        /* ── Source Object Type from DBC.TablesV ─────────────────── */
        ,CAST(CASE WHEN Src_Obj.TableKind IS NOT NULL
              THEN CASE Src_Obj.TableKind
                       WHEN 'T' THEN 'Table'
                       WHEN 'O' THEN 'No PI Table'
                       WHEN 'V' THEN 'View'
                       WHEN 'M' THEN 'Macro'
                       WHEN 'P' THEN 'Procedure'
                       WHEN 'E' THEN 'Procedure'
                       WHEN 'G' THEN 'Trigger'
                       WHEN 'I' THEN 'Join Index'
                       WHEN 'A' THEN 'Function'
                       WHEN 'F' THEN 'Function'
                       WHEN 'R' THEN 'Function'
                       WHEN 'B' THEN 'Function'
                       WHEN 'S' THEN 'Function'
                       WHEN 'N' THEN 'Hash Index'
                       WHEN 'K' THEN 'Foreign Server'
                       WHEN 'X' THEN 'Authorization'
                       WHEN 'U' THEN 'Type'
                       WHEN 'C' THEN 'Table Operator'
                       WHEN 'D' THEN 'JAR'
                       WHEN 'H' THEN 'Method'
                       WHEN 'J' THEN 'Journal'
                       WHEN 'L' THEN 'SQL-MR function - Table Operator'
                       WHEN 'Q' THEN 'Queue Table'
                       WHEN 'Y' THEN 'GLOP Set'
                       WHEN 'Z' THEN 'UIF'
                       WHEN '1' THEN 'Schema'
                       WHEN '2' THEN 'Function Alias'
                       WHEN '3' THEN 'UAF - Unbounded Array Framework'
                       ELSE 'Unknown: ' || Src_Obj.TableKind
                   END
              ELSE 'Unknown'
         END AS VARCHAR(30))                                             AS Src_Kind
        ,COALESCE(dl.source_database, '') || '.' || dl.source_table
         || '0A'xc || ' [' || Src_Kind || ']'                        AS Src_Display_Name
        /* ── CAST literals to prevent UNION ALL type-width truncation ── */
        ,CAST('ETL_INPUT' AS VARCHAR(12))                            AS Edge_Relationship
        ,dl.transformation_type                                      AS Transformation_Type
        ,dl.transformation_logic                                     AS Transformation_Logic
        ,dl.lineage_id                                               AS Lineage_ID
        /* ── Target is the Job ───────────────────────────────────── */
        ,CAST(dl.job_name AS VARCHAR(128))                           AS Tgt_Object_Name_FQ
        ,CAST('' AS VARCHAR(128))                                    AS Tgt_Container_Name
        ,dl.job_name                                                 AS Tgt_Object_Name
        ,CAST('Job' AS VARCHAR(30))                                  AS Tgt_Kind
        ,dl.job_name || '0A'xc || ' [' || Tgt_Kind || ']'            AS Tgt_Display_Name
    FROM
        Observability.data_lineage AS dl
    LEFT OUTER JOIN DBC.TablesV AS Src_Obj
      ON  Src_Obj.DatabaseName = dl.source_database
      AND Src_Obj.TableName    = dl.source_table
    WHERE
        dl.is_active = 1

    UNION ALL

    /* ══════════════════════════════════════════════════════════════
     *  Leg 2: Job → Target Table (ETL_OUTPUT)
     * ══════════════════════════════════════════════════════════════ */
    SELECT
        /* ── CAST literals to match Leg 1 column widths ────────────── */
        CAST(dl.job_name AS VARCHAR(128))                            AS Src_Object_Name_FQ
        ,CAST('' AS VARCHAR(128))                                    AS Src_Container_Name
        ,dl.job_name                                                 AS Src_Object_Name
        ,CAST('Job' AS VARCHAR(30))                                  AS Src_Kind
        ,dl.job_name || '0A'xc || ' [' || Src_Kind || ']'            AS Src_Display_Name
        ,CAST('ETL_OUTPUT' AS VARCHAR(12))                           AS Edge_Relationship
        ,dl.transformation_type                                      AS Transformation_Type
        ,dl.transformation_logic                                     AS Transformation_Logic
        ,dl.lineage_id                                               AS Lineage_ID
        ,COALESCE(dl.target_database, '') || '.' || dl.target_table  AS Tgt_Object_Name_FQ
        ,COALESCE(dl.target_database, '')                            AS Tgt_Container_Name
        ,dl.target_table                                             AS Tgt_Object_Name
        /* ── Target Object Type from DBC.TablesV ─────────────────── */
        ,CAST(CASE WHEN Tgt_Obj.TableKind IS NOT NULL
              THEN CASE Tgt_Obj.TableKind
                       WHEN 'T' THEN 'Table'
                       WHEN 'O' THEN 'No PI Table'
                       WHEN 'V' THEN 'View'
                       WHEN 'M' THEN 'Macro'
                       WHEN 'P' THEN 'Procedure'
                       WHEN 'E' THEN 'Procedure'
                       WHEN 'G' THEN 'Trigger'
                       WHEN 'I' THEN 'Join Index'
                       WHEN 'A' THEN 'Function'
                       WHEN 'F' THEN 'Function'
                       WHEN 'R' THEN 'Function'
                       WHEN 'B' THEN 'Function'
                       WHEN 'S' THEN 'Function'
                       WHEN 'N' THEN 'Hash Index'
                       WHEN 'K' THEN 'Foreign Server'
                       WHEN 'X' THEN 'Authorization'
                       WHEN 'U' THEN 'Type'
                       WHEN 'C' THEN 'Table Operator'
                       WHEN 'D' THEN 'JAR'
                       WHEN 'H' THEN 'Method'
                       WHEN 'J' THEN 'Journal'
                       WHEN 'L' THEN 'SQL-MR function - Table Operator'
                       WHEN 'Q' THEN 'Queue Table'
                       WHEN 'Y' THEN 'GLOP Set'
                       WHEN 'Z' THEN 'UIF'
                       WHEN '1' THEN 'Schema'
                       WHEN '2' THEN 'Function Alias'
                       WHEN '3' THEN 'UAF - Unbounded Array Framework'
                       ELSE 'Unknown: ' || Tgt_Obj.TableKind
                   END
              ELSE 'Unknown'
         END AS VARCHAR(30))                                             AS Tgt_Kind
        ,COALESCE(dl.target_database, '') || '.' || dl.target_table
         || '0A'xc || ' [' || Tgt_Kind || ']'                        AS Tgt_Display_Name
    FROM
        Observability.data_lineage AS dl
    LEFT OUTER JOIN DBC.TablesV AS Tgt_Obj
      ON  Tgt_Obj.DatabaseName = dl.target_database
      AND Tgt_Obj.TableName    = dl.target_table
    WHERE
        dl.is_active = 1
;
```

### 4.2 lineage_run_latest (Latest Execution per Flow)

Convenience view joining each active lineage definition to its most recent execution. Useful for dashboards showing "last run status" alongside the blueprint.

```sql
REPLACE VIEW Semantic.lineage_run_latest
(
    -- View contract: agents see all returned columns without parsing the SELECT body
    lineage_id,
    source_database,
    source_table,
    job_name,
    target_database,
    target_table,
    transformation_type,
    is_active,
    lineage_run_id,
    last_run_dts,
    last_run_status,
    last_run_duration_ms,
    last_records_read,
    last_records_written,
    last_records_rejected,
    last_error_message
)
AS
LOCKING ROW FOR ACCESS
SELECT
     dl.lineage_id
    ,dl.source_database
    ,dl.source_table
    ,dl.job_name
    ,dl.target_database
    ,dl.target_table
    ,dl.transformation_type
    ,dl.is_active
    ,lr.lineage_run_id
    ,lr.run_dts                AS last_run_dts
    ,lr.run_status             AS last_run_status
    ,lr.run_duration_ms        AS last_run_duration_ms
    ,lr.records_read           AS last_records_read
    ,lr.records_written        AS last_records_written
    ,lr.records_rejected       AS last_records_rejected
    ,lr.error_message          AS last_error_message
FROM
    Observability.data_lineage AS dl
LEFT OUTER JOIN Observability.lineage_run AS lr
  ON  lr.lineage_id = dl.lineage_id
  AND lr.run_dts = (
        SELECT MAX(lr2.run_dts)
        FROM   Observability.lineage_run AS lr2
        WHERE  lr2.lineage_id = dl.lineage_id
      )
WHERE
    dl.is_active = 1
;
```

---

## 5. Open Standards Integration

### 5.1 OpenLineage

**Reference**: https://openlineage.io/

The lineage tables are designed to align with the OpenLineage specification. The definition/execution split directly mirrors OpenLineage's separation of design-time events (`JobEvent` — static metadata about declared flows) and runtime events (`RunEvent` — per-execution observations).

#### 5.1.1 Entity Mapping

| OpenLineage Entity | Our Table | Key Columns |
|-------------------|-----------|-------------|
| **Job** (a process that consumes/produces Datasets) | `data_lineage` | `job_name`, `openlineage_job_name`, `openlineage_namespace` |
| **Run** (a single execution of a Job) | `lineage_run` | `openlineage_run_id`, `run_dts`, `run_status` |
| **InputDataset** | `data_lineage` | `source_database`, `source_table` |
| **OutputDataset** | `data_lineage` | `target_database`, `target_table` |

OpenLineage identifies datasets by `namespace` + `name`. The spec defines the Teradata convention as:
- **Namespace**: `teradata://{host}:{port}`
- **Name**: `{database}.{table}`

Our `source_database.source_table` and `target_database.target_table` columns compose directly into the OpenLineage `name` portion. The namespace prefix is environment-specific and should be supplied at event-emission time or stored as configuration.

#### 5.1.2 Column-Level Mapping

**Definitional columns** (`data_lineage` → OpenLineage JobEvent):

| Our Column | OpenLineage Concept |
|------------|-------------------|
| `openlineage_namespace` | Job.namespace |
| `openlineage_job_name` | Job.name |
| `source_database` + `source_table` | InputDataset.name |
| `target_database` + `target_table` | OutputDataset.name |
| `transformation_logic` | `sql` or `sourceCode` facet |
| `registered_dts` | JobEvent.eventTime |

**Operational columns** (`lineage_run` → OpenLineage RunEvent):

| Our Column | OpenLineage Concept |
|------------|-------------------|
| `openlineage_run_id` | Run.runId (UUID) |
| `run_dts` | RunEvent.eventTime |
| `run_status` | RunEvent.eventType (SUCCESS→COMPLETE, FAILED→FAIL, RUNNING→START) |
| `records_read` | InputDataset `inputStatistics` facet (rowCount) |
| `records_written` | OutputDataset `outputStatistics` facet (rowCount) |
| `error_message` | Run `errorMessage` facet |

#### 5.1.3 Example: Generating an OpenLineage RunEvent

The following query constructs an OpenLineage-compliant RunEvent JSON payload from the lineage tables, suitable for emission to an OpenLineage-compatible backend (e.g., Marquez, Amundsen, Datadog):

```sql
/* ──────────────────────────────────────────────────────────────────────────
 *  Uses Teradata native JSON functions (JSON_COMPOSE, JSON_AGG) for
 *  proper type handling, automatic escaping, and cleaner SQL.
 * ────────────────────────────────────────────────────────────────────────── */
SELECT
    lr.lineage_run_id

    /* ── Compose the RunEvent as a native JSON object ────────────── */
   ,JSON_COMPOSE(
        CAST(lr.run_dts AS VARCHAR(50))                              AS "eventTime"
       ,CASE lr.run_status
             WHEN 'SUCCESS' THEN 'COMPLETE'
             WHEN 'FAILED'  THEN 'FAIL'
             WHEN 'RUNNING' THEN 'START'
             WHEN 'PARTIAL' THEN 'COMPLETE'
             ELSE 'OTHER'
        END                                                          AS "eventType"

       /* ── Run object ───────────────────────────────────────────── */
       ,JSON_COMPOSE(
            COALESCE(lr.openlineage_run_id,
                     CAST(lr.lineage_run_id AS VARCHAR(36)))         AS "runId"
        )                                                            AS "run"

       /* ── Job object ───────────────────────────────────────────── */
       ,JSON_COMPOSE(
            COALESCE(dl.openlineage_namespace,
                     'teradata://localhost:1025')                     AS "namespace"
           ,COALESCE(dl.openlineage_job_name, dl.job_name)           AS "name"
        )                                                            AS "job"

       /* ── Input dataset (single) ───────────────────────────────── */
       ,JSON_COMPOSE(
            'teradata://localhost:1025'                               AS "namespace"
           ,COALESCE(dl.source_database, '') || '.' || dl.source_table
                                                                     AS "name"
           ,lr.records_read                                          AS "rowCount"
        )                                                            AS "input"

       /* ── Output dataset (single) ──────────────────────────────── */
       ,JSON_COMPOSE(
            'teradata://localhost:1025'                               AS "namespace"
           ,COALESCE(dl.target_database, '') || '.' || dl.target_table
                                                                     AS "name"
           ,lr.records_written                                       AS "rowCount"
        )                                                            AS "output"

       ,'https://teradata.com/ai-native-data-product'                AS "producer"
       ,'https://openlineage.io/spec/2-0-2/OpenLineage.json#/definitions/RunEvent'
                                                                     AS "schemaURL"
    ) AS openlineage_run_event_json

FROM
    Observability.lineage_run AS lr
INNER JOIN Observability.data_lineage AS dl
  ON lr.lineage_id = dl.lineage_id
WHERE
    lr.run_dts >= CURRENT_DATE - 1
;
```

**Benefits over string concatenation**:
- ✅ Automatic escaping of special characters (e.g., quotes in `error_message`)
- ✅ Correct JSON types — integers remain numeric, NULLs are omitted cleanly
- ✅ Readable, maintainable SQL that mirrors the OpenLineage structure

**Example output**:
```json
{
  "eventTime": "2026-04-09T02:15:33.123456+00:00",
  "eventType": "COMPLETE",
  "run": { "runId": "3b452093-782c-4ef2-9c0c-aafe2aa6f34d" },
  "job": {
    "namespace": "airflow://prod-scheduler.corp.com",
    "name": "BigBankMortgage_ETL.ETL_PARTY_FEATURES"
  },
  "input": {
    "namespace": "teradata://tdprod.corp.com:1025",
    "name": "BigBankMortgage_Domain.Party_H",
    "rowCount": 250000
  },
  "output": {
    "namespace": "teradata://tdprod.corp.com:1025",
    "name": "BigBankMortgage_Prediction.customer_features",
    "rowCount": 248500
  },
  "producer": "https://teradata.com/ai-native-data-product",
  "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/definitions/RunEvent"
}
```

#### 5.1.4 Example: Data Freshness from Lineage Runs

OpenLineage consumers compute data freshness from the latest successful RunEvent. The same metric can be derived directly from `lineage_run`:

```sql
SELECT
    dl.target_database || '.' || dl.target_table   AS dataset_name
   ,dl.job_name
   ,MAX(lr.run_dts)                                AS last_successful_run
   ,(CURRENT_TIMESTAMP(6) - MAX(lr.run_dts)) HOUR(4) TO MINUTE
                                                   AS freshness_lag
   ,CASE
        WHEN MAX(lr.run_dts) >= CURRENT_TIMESTAMP(6) - INTERVAL '24' HOUR THEN 'FRESH'
        WHEN MAX(lr.run_dts) >= CURRENT_TIMESTAMP(6) - INTERVAL '48' HOUR THEN 'STALE'
        ELSE 'CRITICAL'
    END                                            AS freshness_status
FROM
    Observability.data_lineage AS dl
INNER JOIN Observability.lineage_run AS lr
  ON lr.lineage_id = dl.lineage_id
WHERE
    dl.is_active = 1
    AND lr.run_status = 'SUCCESS'
GROUP BY
    dl.target_database, dl.target_table, dl.job_name
;
```

#### 5.1.5 Design Notes

- **Run lifecycle**: OpenLineage expects at least a START and COMPLETE/FAIL event per run. Our tables store a single final-status row per execution, which is a pragmatic trade-off for Teradata efficiency. Full lifecycle tracking can be added if required by extending `lineage_run` to allow multiple rows per `openlineage_run_id`.
- **Multi-input jobs**: A job with multiple input datasets is represented as multiple `data_lineage` rows sharing the same `job_name`. When constructing OpenLineage events, use `JSON_AGG` to aggregate these into a single event with a JSON array of input datasets.
- **Custom facets**: Columns such as `transformation_type`, `batch_key`, and `records_rejected` do not have standard OpenLineage facets and should be emitted as custom facets using a project-specific prefix (e.g., `teradata_aiNativeDataProduct_transformationType`).

### 5.2 Data Quality Frameworks

Reference: Great Expectations, Deequ, Monte Carlo

Use standard metric names for consistency.

---

## 6. Integration with Other Modules

### 6.1 Integration with Domain (Table-Level Change Tracking)

**Pattern**: Track changes at table level with aggregate metrics

```sql
-- ETL updates 250,000 Party records
INSERT INTO Observability.change_event (
    database_name, table_name, change_type, change_dts,
    changed_by, change_source, records_affected, batch_key
) VALUES (
    'Domain', 'Party_H', 'UPDATE', CURRENT_TIMESTAMP(6),
    'ETL_DAILY', 'ETL', 250000, 'BATCH-2024-03-15'
);

-- Query change history for table
SELECT 
    change_type,
    change_dts,
    changed_by,
    records_affected,
    batch_key
FROM Observability.change_event
WHERE table_name = 'Party_H'
  AND change_dts >= CURRENT_DATE - 30
ORDER BY change_dts DESC;
```

**Benefits**: One event per batch (not millions per record), efficient audit trail

### 6.2 Feed Memory Module (Closed-Loop Learning)

**Pattern**: Observability outcomes feed Memory learnings

```sql
-- Identify successful query patterns for Memory
INSERT INTO Memory.learned_strategy (
    strategy_name, strategy_category, success_rate,
    discovered_by_agent, scope_level
)
SELECT 
    'FastPartyQueries_' || CURRENT_DATE,
    'QUERY_OPTIMIZATION',
    SUM(CASE WHEN execution_time_ms < 1000 THEN 1 ELSE 0 END) * 1.0 / COUNT(*),
    'observability_analyzer',
    'ORGANIZATION'
FROM Observability.agent_outcome
WHERE action_type = 'QUERY'
  AND tables_accessed LIKE '%Party_H%'
  AND action_dts >= CURRENT_DATE - 7
HAVING COUNT(*) >= 10;
```

### 6.3 Monitor All Modules

**Track quality and performance across all modules**:

```sql
-- Monitor quality across Domain, Prediction, Search
SELECT 
    database_name,
    table_name,
    metric_name,
    AVG(metric_value) AS avg_quality,
    MIN(metric_value) AS min_quality
FROM Observability.data_quality_metric
WHERE table_name IN ('Party_H', 'customer_features', 'product_embedding')
  AND measured_dts >= CURRENT_DATE - 7
GROUP BY database_name, table_name, metric_name;

-- Track lineage execution across modules (uses operational table)
SELECT 
    dl.source_database || '.' || dl.source_table AS source,
    dl.target_database || '.' || dl.target_table AS target,
    dl.transformation_type,
    lr.records_written,
    lr.run_status
FROM Observability.lineage_run AS lr
INNER JOIN Observability.data_lineage AS dl
  ON lr.lineage_id = dl.lineage_id
WHERE lr.run_dts >= CURRENT_DATE - 1
ORDER BY lr.run_dts DESC;
```

---

## 7. Designer Responsibilities

### 7.1 Required Tables

- change_event
- data_quality_metric
- data_lineage
- lineage_run
- model_performance (if using ML)
- agent_outcome (if using agents)

### 7.2 Required Semantic Views

- lineage_graph (deployed to `{ProductName}_Semantic`)
- lineage_run_latest (deployed to `{ProductName}_Semantic`)

### 7.3 Design Checklist

- [ ] Quality metrics defined
- [ ] Quality thresholds set
- [ ] Lineage flows registered in data_lineage for all declared pipelines
- [ ] OpenLineage integration configured
- [ ] Retention policies defined (separate policies for data_lineage vs lineage_run)
- [ ] Integration with Memory configured
- [ ] lineage_graph and lineage_run_latest views deployed to Semantic
- [ ] Module_Registry INSERT generated for this module
- [ ] Min. 3 Design_Decision INSERTs generated
- [ ] Change_Log initial release entry generated
- [ ] Min. 3 Business_Glossary terms captured
- [ ] Min. 1 Query_Cookbook recipe captured

### 7.4 Documentation Capture Requirements

Every Observability module must populate the Memory database documentation tables as part of its design workflow. The table definitions, workflows, and full protocol are defined in the **Memory Module Design Standard, Section 8**.

**Minimum requirements:**

| Record Type | Table | Minimum | Notes |
|-------------|-------|---------|-------|
| Module_Registry | `Memory.Module_Registry` | 1 | Register this module with data_product and version |
| Design_Decision | `Memory.Design_Decision` | 3 | Key architectural and schema choices |
| Change_Log | `Memory.Change_Log` | 1 | Initial release entry (version 1.0.0) |
| Business_Glossary | `Memory.Business_Glossary` | 3 | Observability terms, metric definitions, and lineage concepts introduced |
| Query_Cookbook | `Memory.Query_Cookbook` | 1 | Key query patterns (e.g., quality metric trend, agent outcome analysis) |

**Typical decision categories for Observability modules:**

| Decision Category | Example |
|-------------------|---------|
| `OPERATIONAL` | Quality threshold values and alerting strategy |
| `INTEGRATION` | OpenLineage scope — which modules and tables are tracked |
| `ARCHITECTURE` | Closed-loop feed strategy from agent_outcome into Memory.learned_strategy |
| `ARCHITECTURE` | Lineage definition/execution split — why two tables |
| `SCHEMA` | Retention policy — how long to keep change events vs quality metrics vs lineage runs |
| `PERFORMANCE` | Aggregation window and metric granularity decisions |

**Decision ID prefix for this module:** `DD-OBSERVABILITY-{NNN}` (e.g., `DD-OBSERVABILITY-001`)

**Output file placement:** Write documentation capture SQL as the last numbered file in the observability deployment directory (e.g., `05-observability/05-documentation.sql`).

**Full protocol, SQL templates, and ID conventions:** See Memory Module Design Standard, Section 8.3 (Workflow 2 — Capture).

---

## Appendix: Quick Reference

### Core Tables
```
✅ change_event           -- Audit trail
✅ data_quality_metric    -- Quality metrics
✅ data_lineage           -- Lineage definition (blueprint)
✅ lineage_run            -- Lineage execution (operational log)
✅ model_performance      -- Model metrics
✅ agent_outcome          -- Agent outcomes
```

### Semantic Views
```
✅ lineage_graph          -- Graph-ready edge list
✅ lineage_run_latest     -- Latest execution per flow (dashboard-ready)
```

### Key Principles
```
✅ Store events/metrics (NOT data)
✅ Table-level change tracking (NOT individual record changes)
✅ Aggregate metrics (records_affected count, not individual keys)
✅ Separate lineage definition from execution (stable graph, event-scale runs)
✅ Align with OpenLineage for data lineage
✅ Feed Memory module (closed-loop learning)
✅ Monitor all modules
✅ Event-scale volume acceptable (millions of events OK)
✅ Don't duplicate business data
```

### Open Standards
```
OpenLineage:         openlineage.io
Great Expectations:  Data quality
OpenTelemetry:       Observability
```
---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.6 | 2026-04-15 | Added Platform Note — all DDL examples use Teradata syntax; structural design is platform-agnostic. Fixed UNION ALL type-width truncation in lineage_graph view — added explicit CAST to all literal strings and job_name columns that appear on only one leg (without CASTs, `''` truncated container names to empty, `'ETL_INPUT'` truncated `'ETL_OUTPUT'` to `'ETL_OUTPU'`). Replaced Teradata `END (VARCHAR(30))` cast shorthand with ANSI `CAST(CASE...END AS VARCHAR(30))` longhand throughout. Added CAST rationale comment to view header. | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 1.5 | 2026-04-09 | Lineage definition/execution split — replaced single data_lineage table with definitional data_lineage (one row per declared flow, with is_active lifecycle) and operational lineage_run (one row per execution, FK to definition). Added Section 1.3 Lineage Separation Principle. Added new Section 4 Semantic Views with lineage_graph (reads definitions only, VARCHAR(30) casts on all Kind columns) and lineage_run_latest views. Updated Section 6.3 Monitor All Modules query to use lineage_run. Updated Required Tables (7.1), added Required Semantic Views (7.2), updated Design Checklist (7.3) and Documentation Capture (7.4). Renumbered sections 4–7 (previously 4–6). | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 1.4 | 2026-03-20 | Revised Documentation Capture Requirements section — updated to reflect self-contained data product principle. Documentation tables now reside in the Memory database ({ProductName}_Memory), not a shared dp_documentation database. Removed data_product column from INSERT templates, removed bootstrap checklist item, updated prose references from dp_documentation to Memory database. |
| 1.3 | 2026-03-20 | Added Section 6.3 Documentation Capture Requirements — minimum dp_documentation records, typical decision categories, output file placement, and reference to Memory Module Section 8 protocol. Updated Section 6.2 checklist to include documentation capture steps. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.2 | 2026-03-18 | Applied surrogate key naming convention to internal management tables: renamed {table}_key → {table}_id for all GENERATED ALWAYS AS IDENTITY columns | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.1 | 2025-02-27 | changed meets_threshold & meets_sla to is_threshold_met & is_sla_met to be consistent with booleans accross modules | Nathan Green, Worldwide Data Architecture Team, Teradata |

---

**End of Observability Module Design Standard**
