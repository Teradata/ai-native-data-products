-- Observability module — lineage discovery views (Teradata).
-- Binding of design/modules/observability.md §5. Deployed into the Semantic container so agents
-- discover lineage from the same place. lineage_graph reads DEFINITIONS ONLY (stable, deduplicated).
-- Replace {{ product }}.

-- lineage_graph: graph-ready edge list; ETL jobs are first-class nodes.
-- Each data_lineage row becomes two edges: source -> job (ETL_INPUT), job -> target (ETL_OUTPUT).
-- NOTE: literals and single-leg columns are CAST to explicit widths so the UNION ALL does not
-- infer VARCHAR(0)/short widths from leg 1 and truncate leg 2.
REPLACE VIEW {{ product }}_Semantic.lineage_graph
(
    Src_Object_Name_FQ, Src_Container_Name, Src_Object_Name, Src_Kind, Src_Display_Name,
    Edge_Relationship, Transformation_Type, Transformation_Logic, Lineage_ID,
    Tgt_Object_Name_FQ, Tgt_Container_Name, Tgt_Object_Name, Tgt_Kind, Tgt_Display_Name
)
AS
LOCKING ROW FOR ACCESS
    -- Leg 1: source table -> job
    SELECT
         COALESCE(dl.source_database, '') || '.' || dl.source_table  AS Src_Object_Name_FQ
        ,COALESCE(dl.source_database, '')                            AS Src_Container_Name
        ,dl.source_table                                             AS Src_Object_Name
        ,CAST(COALESCE(src.kind_label, 'Unknown') AS VARCHAR(30))    AS Src_Kind
        ,COALESCE(dl.source_database, '') || '.' || dl.source_table
             || '0A'xc || ' [' || Src_Kind || ']'                   AS Src_Display_Name
        ,CAST('ETL_INPUT' AS VARCHAR(12))                           AS Edge_Relationship
        ,dl.transformation_type                                      AS Transformation_Type
        ,dl.transformation_logic                                     AS Transformation_Logic
        ,dl.lineage_id                                               AS Lineage_ID
        ,CAST(dl.job_name AS VARCHAR(128))                           AS Tgt_Object_Name_FQ
        ,CAST('' AS VARCHAR(128))                                    AS Tgt_Container_Name
        ,dl.job_name                                                 AS Tgt_Object_Name
        ,CAST('Job' AS VARCHAR(30))                                  AS Tgt_Kind
        ,dl.job_name || '0A'xc || ' [' || Tgt_Kind || ']'           AS Tgt_Display_Name
    FROM {{ product }}_Observability.data_lineage AS dl
    LEFT OUTER JOIN (
        SELECT DatabaseName, TableName,
               CASE TableKind WHEN 'T' THEN 'Table' WHEN 'O' THEN 'No PI Table'
                    WHEN 'V' THEN 'View' WHEN 'M' THEN 'Macro' WHEN 'P' THEN 'Procedure'
                    WHEN 'E' THEN 'Procedure' WHEN 'A' THEN 'Function' WHEN 'F' THEN 'Function'
                    ELSE 'Object' END AS kind_label
        FROM DBC.TablesV
    ) AS src ON src.DatabaseName = dl.source_database AND src.TableName = dl.source_table
    WHERE dl.is_active = 1

    UNION ALL

    -- Leg 2: job -> target table
    SELECT
         CAST(dl.job_name AS VARCHAR(128))                           AS Src_Object_Name_FQ
        ,CAST('' AS VARCHAR(128))                                    AS Src_Container_Name
        ,dl.job_name                                                 AS Src_Object_Name
        ,CAST('Job' AS VARCHAR(30))                                  AS Src_Kind
        ,dl.job_name || '0A'xc || ' [' || Src_Kind || ']'           AS Src_Display_Name
        ,CAST('ETL_OUTPUT' AS VARCHAR(12))                          AS Edge_Relationship
        ,dl.transformation_type                                      AS Transformation_Type
        ,dl.transformation_logic                                     AS Transformation_Logic
        ,dl.lineage_id                                               AS Lineage_ID
        ,COALESCE(dl.target_database, '') || '.' || dl.target_table  AS Tgt_Object_Name_FQ
        ,COALESCE(dl.target_database, '')                            AS Tgt_Container_Name
        ,dl.target_table                                             AS Tgt_Object_Name
        ,CAST(COALESCE(tgt.kind_label, 'Unknown') AS VARCHAR(30))    AS Tgt_Kind
        ,COALESCE(dl.target_database, '') || '.' || dl.target_table
             || '0A'xc || ' [' || Tgt_Kind || ']'                   AS Tgt_Display_Name
    FROM {{ product }}_Observability.data_lineage AS dl
    LEFT OUTER JOIN (
        SELECT DatabaseName, TableName,
               CASE TableKind WHEN 'T' THEN 'Table' WHEN 'O' THEN 'No PI Table'
                    WHEN 'V' THEN 'View' WHEN 'M' THEN 'Macro' WHEN 'P' THEN 'Procedure'
                    WHEN 'E' THEN 'Procedure' WHEN 'A' THEN 'Function' WHEN 'F' THEN 'Function'
                    ELSE 'Object' END AS kind_label
        FROM DBC.TablesV
    ) AS tgt ON tgt.DatabaseName = dl.target_database AND tgt.TableName = dl.target_table
    WHERE dl.is_active = 1;

COMMENT ON VIEW {{ product }}_Semantic.lineage_graph IS
'Graph-ready lineage edge list from definitional data_lineage (active flows only); jobs are first-class nodes. Stable and deduplicated.';

-- lineage_run_latest: each active flow joined to its most recent execution.
REPLACE VIEW {{ product }}_Semantic.lineage_run_latest
(
    lineage_id, source_database, source_table, job_name, target_database, target_table,
    transformation_type, is_active, lineage_run_id, last_run_dts, last_run_status,
    last_run_duration_ms, last_records_read, last_records_written, last_records_rejected, last_error_message
)
AS
LOCKING ROW FOR ACCESS
SELECT
     dl.lineage_id, dl.source_database, dl.source_table, dl.job_name,
     dl.target_database, dl.target_table, dl.transformation_type, dl.is_active,
     lr.lineage_run_id, lr.run_dts, lr.run_status, lr.run_duration_ms,
     lr.records_read, lr.records_written, lr.records_rejected, lr.error_message
FROM {{ product }}_Observability.data_lineage AS dl
LEFT OUTER JOIN {{ product }}_Observability.lineage_run AS lr
  ON lr.lineage_id = dl.lineage_id
 AND lr.run_dts = (SELECT MAX(lr2.run_dts) FROM {{ product }}_Observability.lineage_run AS lr2
                   WHERE lr2.lineage_id = dl.lineage_id)
WHERE dl.is_active = 1;

COMMENT ON VIEW {{ product }}_Semantic.lineage_run_latest IS
'Each active lineage flow joined to its most recent execution - dashboard-ready last-run status against the blueprint.';
