-- Memory module — Teradata invariant checks.
-- Backs the invariants in design/modules/memory.md §10. Each query must return
-- ZERO rows for a conforming deployment. Replace {{ product }} with the product name.

-- ---------------------------------------------------------------------------
-- INV-MEMORY-001 : references are table-level; no instance-key columns on runtime tables.
-- Flags any runtime column that looks like it stores an entity instance id/key.
-- (referenced_tables / involved_tables are table-level lists and are excluded.)
-- ---------------------------------------------------------------------------
SELECT TableName, ColumnName
FROM DBC.ColumnsV
WHERE DatabaseName = '{{ product }}_Memory'
  AND TableName IN ('agent_session','agent_interaction','learned_strategy',
                    'user_preference','discovered_pattern')
  AND (LOWER(ColumnName) LIKE 'party\_id' ESCAPE '\'
    OR LOWER(ColumnName) LIKE 'product\_id' ESCAPE '\'
    OR LOWER(ColumnName) LIKE 'entity\_id' ESCAPE '\'
    OR LOWER(ColumnName) LIKE '%\_key\_list' ESCAPE '\'
    OR LOWER(ColumnName) LIKE 'result\_ids' ESCAPE '\');

-- ---------------------------------------------------------------------------
-- INV-MEMORY-003 : every runtime table carries a privacy scope.
-- Any runtime table missing scope_level or scope_identifier is a violation.
-- ---------------------------------------------------------------------------
SELECT t.TableName,
       MAX(CASE WHEN c.ColumnName = 'scope_level'      THEN 1 ELSE 0 END) AS has_scope_level,
       MAX(CASE WHEN c.ColumnName = 'scope_identifier' THEN 1 ELSE 0 END) AS has_scope_identifier
FROM DBC.TablesV t
JOIN DBC.ColumnsV c
  ON c.DatabaseName = t.DatabaseName AND c.TableName = t.TableName
WHERE t.DatabaseName = '{{ product }}_Memory'
  AND t.TableName IN ('agent_session','agent_interaction','learned_strategy',
                      'user_preference','discovered_pattern')
GROUP BY t.TableName
HAVING has_scope_level = 0 OR has_scope_identifier = 0;

-- ---------------------------------------------------------------------------
-- INV-MEMORY-005 : documentation tables are temporally versioned.
-- Any versioned documentation table missing valid_from/valid_to is a violation.
-- ---------------------------------------------------------------------------
SELECT t.TableName
FROM DBC.TablesV t
WHERE t.DatabaseName = '{{ product }}_Memory'
  AND t.TableName IN ('Module_Registry','Design_Decision','Business_Glossary',
                      'Query_Cookbook','Implementation_Note','Change_Log')
  AND NOT EXISTS (
        SELECT 1 FROM DBC.ColumnsV c
        WHERE c.DatabaseName = t.DatabaseName AND c.TableName = t.TableName
          AND c.ColumnName = 'valid_from')
  AND t.TableName <> 'Change_Log';   -- Change_Log is an event log, not version-chained

-- ---------------------------------------------------------------------------
-- INV-MEMORY-006 : capture protocol satisfied — minimum documentation per deployed module.
-- Any DEPLOYED module with fewer than the minimum design decisions is a violation.
-- (Repeat/extend for glossary >= 3 and cookbook >= 1 as needed.)
-- ---------------------------------------------------------------------------
SELECT mr.module_name,
       (SELECT COUNT(*) FROM {{ product }}_Memory.Design_Decision dd
         WHERE dd.source_module = mr.module_name AND dd.is_current = 1) AS decision_count
FROM {{ product }}_Memory.Module_Registry mr
WHERE mr.is_current = 1
  AND mr.deployment_status = 'DEPLOYED'
  AND (SELECT COUNT(*) FROM {{ product }}_Memory.Design_Decision dd
        WHERE dd.source_module = mr.module_name AND dd.is_current = 1) < 3;
