-- Memory module — DocumentationCapture binding (Teradata).
-- The INSERT templates every module uses to record its design memory
-- (design/modules/memory.md §5.2). Replace {{ product }}, {MODULE}, {NNN}, and
-- {...} placeholders. Temporal field standards: valid_from = CURRENT_DATE,
-- valid_to = DATE '9999-12-31', is_current/is_active = 1, decision_status = 'ACCEPTED'.

-- 1. Register the module (one row per module CONSIDERED, with deployment_status)
INSERT INTO {{ product }}_Memory.Module_Registry
(module_name, database_name, deployment_status, module_version, module_purpose,
 module_scope, key_entities, dependencies, dependents, data_owner, technical_owner,
 version_date, is_current, valid_from, valid_to, created_timestamp, updated_timestamp)
VALUES
('{MODULE_NAME}', '{{ product }}_{Module}', 'DEPLOYED', '1.0.0',
 '{purpose}', '{scope}', '{entity_list}', '{upstream}', '{downstream}',
 '{owner}', '{tech_contact}',
 CURRENT_DATE, 1, CURRENT_DATE, DATE '9999-12-31', CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));

-- 2. Capture a design decision (min. 3 per deployed module)
INSERT INTO {{ product }}_Memory.Design_Decision
(decision_id, decision_version, decision_title, decision_description,
 context, alternatives_considered, rationale, consequences,
 decision_status, decision_category, source_module, module_version, affects_table,
 decided_by, decided_date, valid_from, valid_to, is_current,
 created_timestamp, updated_timestamp)
VALUES
('DD-{MODULE}-{NNN}', 1, '{title}', '{description}',
 '{context}', '{alternatives}', '{rationale}', '{consequences}',
 'ACCEPTED', '{category}', '{MODULE_NAME}', '{version}', '{table_list}',
 '{author}', CURRENT_DATE, CURRENT_DATE, DATE '9999-12-31', 1,
 CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));

-- 2b. Supersede a decision (version chain): close current, insert new version
UPDATE {{ product }}_Memory.Design_Decision
SET valid_to = CURRENT_DATE, is_current = 0, updated_timestamp = CURRENT_TIMESTAMP(6)
WHERE decision_id = 'DD-{MODULE}-{NNN}' AND is_current = 1;
-- then INSERT the same decision_id with decision_version + 1

-- 3. Change-log entry (min. 1 initial release per deployed module)
INSERT INTO {{ product }}_Memory.Change_Log
(change_id, version_number, change_title, change_description,
 change_type, change_category, source_module, affects_table,
 migration_steps, rollback_steps, related_decision_id,
 deployed_date, deployed_by, deployment_status, created_timestamp)
VALUES
('CL-{MODULE}-{NNN}', '1.0.0', '{title}', '{description}',
 'INITIAL_RELEASE', 'ADDITIVE', '{MODULE_NAME}', '{table_list}',
 NULL, NULL, 'DD-{MODULE}-{NNN}',
 CURRENT_DATE, '{deployer}', 'DEPLOYED', CURRENT_TIMESTAMP(6));

-- 4. Glossary term (min. 3 per deployed module)
INSERT INTO {{ product }}_Memory.Business_Glossary
(term, term_category, definition, business_context, source_module, module_version,
 is_active, valid_from, valid_to, created_timestamp, updated_timestamp)
VALUES
('{term}', '{category}', '{definition}', '{context}', '{MODULE_NAME}', '{version}',
 1, CURRENT_DATE, DATE '9999-12-31', CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));

-- 5. Query recipe (min. 1 per deployed module; 1 cross-module per deployed pair)
INSERT INTO {{ product }}_Memory.Query_Cookbook
(recipe_id, recipe_title, recipe_description, use_case, target_module,
 sql_template, parameter_descriptions, performance_notes, complexity, is_batch,
 source_module, module_version, is_active, valid_from, valid_to,
 created_timestamp, updated_timestamp)
VALUES
('QC-{MODULE}-{NNN}', '{title}', '{description}', '{use_case}', '{target_module}',
 '{sql_with_:parameters}', '{param_desc}', '{perf_notes}', '{complexity}', {is_batch},
 '{MODULE_NAME}', '{version}', 1, CURRENT_DATE, DATE '9999-12-31',
 CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));

-- ---------------------------------------------------------------------------
-- Standard ERD recipe (QC-SEMANTIC-002) — required whenever Semantic is present.
-- Lets any agent regenerate a current ER diagram from the living relationship data.
-- ---------------------------------------------------------------------------
INSERT INTO {{ product }}_Memory.Query_Cookbook
(recipe_id, recipe_title, recipe_description, use_case, target_module,
 sql_template, parameter_descriptions, performance_notes, complexity, is_batch,
 source_module, module_version, is_active, valid_from, valid_to,
 created_timestamp, updated_timestamp)
VALUES
('QC-SEMANTIC-002',
 'Generate entity-relationship diagram from table_relationship',
 'Queries Semantic.table_relationship to produce a full relationship listing; render as Mermaid erDiagram or plain listing.',
 'Data model documentation, onboarding, design review',
 'SEMANTIC',
 'SELECT r.from_database, r.from_table, r.from_column, r.relationship_type, r.cardinality,
        r.to_database, r.to_table, r.to_column, r.join_type, r.is_mandatory, r.relationship_desc
 FROM {{ product }}_Semantic.table_relationship r
 WHERE r.is_active = 1
 ORDER BY r.from_table, r.to_table;',
 'None - reads the Semantic relationship metadata.',
 'Lightweight query on a small metadata table.',
 'SIMPLE', 0,
 'SEMANTIC', '1.0.0', 1, CURRENT_DATE, DATE '9999-12-31',
 CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));
