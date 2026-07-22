-- Memory module — documentation facet standard views (Teradata). AccessView binding.
-- Replace {{ product }} with the data product name.

REPLACE VIEW {{ product }}_Memory.v_Current_Decisions
(
    decision_id, decision_version, decision_title, decision_category,
    source_module, rationale, decided_by, decided_date
)
AS
SELECT
    decision_id, decision_version, decision_title, decision_category,
    source_module, rationale, decided_by, decided_date
FROM {{ product }}_Memory.Design_Decision
WHERE is_current = 1
  AND decision_status <> 'SUPERSEDED';

COMMENT ON VIEW {{ product }}_Memory.v_Current_Decisions IS
'All current, non-superseded design decisions.';

REPLACE VIEW {{ product }}_Memory.v_Module_Registry_Current
(
    module_name, database_name, deployment_status, module_version, module_purpose, version_date
)
AS
SELECT
    module_name, database_name, deployment_status, module_version, module_purpose, version_date
FROM {{ product }}_Memory.Module_Registry
WHERE is_current = 1;

COMMENT ON VIEW {{ product }}_Memory.v_Module_Registry_Current IS
'Current version of each registered module.';

REPLACE VIEW {{ product }}_Memory.v_Glossary_Active
(
    term, term_category, definition, source_module, related_table, related_column
)
AS
SELECT
    term, term_category, definition, source_module, related_table, related_column
FROM {{ product }}_Memory.Business_Glossary
WHERE is_active = 1;

COMMENT ON VIEW {{ product }}_Memory.v_Glossary_Active IS
'Active glossary terms.';

REPLACE VIEW {{ product }}_Memory.v_Cookbook_Active
(
    recipe_id, recipe_title, use_case, target_module, complexity, is_batch, sql_template
)
AS
SELECT
    recipe_id, recipe_title, use_case, target_module, complexity, is_batch, sql_template
FROM {{ product }}_Memory.Query_Cookbook
WHERE is_active = 1;

COMMENT ON VIEW {{ product }}_Memory.v_Cookbook_Active IS
'Active query recipes with complexity and batch/interactive intent.';

REPLACE VIEW {{ product }}_Memory.v_Change_History
(
    change_id, version_number, change_title, change_type, source_module, deployed_date
)
AS
SELECT
    change_id, version_number, change_title, change_type, source_module, deployed_date
FROM {{ product }}_Memory.Change_Log;

COMMENT ON VIEW {{ product }}_Memory.v_Change_History IS
'Full change log; order by version_number descending to see latest first.';
