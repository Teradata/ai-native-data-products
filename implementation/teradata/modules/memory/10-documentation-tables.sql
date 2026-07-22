-- Memory module — documentation facet tables (Teradata).
-- Binding of design/modules/memory.md §5. These six tables ARE the design memory.
-- Temporally versioned (INV-MEMORY-005). Replace {{ product }} with the product name.

-- ---------------------------------------------------------------------------
-- Module_Registry — every module considered during design (deployed or not)
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.Module_Registry (
    module_registry_key  BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    module_name          VARCHAR(50) NOT NULL,       -- DOMAIN, SEARCH, PREDICTION, OBSERVABILITY, SEMANTIC, MEMORY
    database_name        VARCHAR(128) NOT NULL,
    deployment_status    VARCHAR(20) NOT NULL DEFAULT 'DEPLOYED',  -- DEPLOYED, PLANNED, DEPRECATED
    module_version       VARCHAR(20) NOT NULL,
    module_purpose       CLOB NOT NULL,
    module_scope         CLOB,
    key_entities         VARCHAR(500),
    dependencies         VARCHAR(500),
    dependents           VARCHAR(500),
    data_owner           VARCHAR(100),
    technical_owner      VARCHAR(100),
    version_date         DATE NOT NULL,
    is_current           BYTEINT NOT NULL DEFAULT 1,
    valid_from           DATE NOT NULL,
    valid_to             DATE DEFAULT DATE '9999-12-31',
    created_timestamp    TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp    TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (module_registry_key);

COMMENT ON TABLE {{ product }}_Memory.Module_Registry IS
'Version registry for all modules considered during design (deployed, planned, deprecated). Backbone for point-in-time documentation and full scope visibility.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.module_name IS 'Module name - DOMAIN, SEARCH, PREDICTION, OBSERVABILITY, SEMANTIC, MEMORY.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.database_name IS 'Container the module is deployed in.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.deployment_status IS 'DEPLOYED (active), PLANNED (in scope, not built), DEPRECATED (retired).';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.module_version IS 'Semantic version string.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.module_purpose IS 'What the module is for.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.module_scope IS 'Scope notes, including plan/dependency for PLANNED modules.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.key_entities IS 'Key entities the module owns.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.dependencies IS 'Upstream modules.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.dependents IS 'Downstream modules.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.data_owner IS 'Business owner.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.technical_owner IS 'Technical contact.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.version_date IS 'When this version became active.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.is_current IS '1 = current version, 0 = historical.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.valid_from IS 'Temporal validity start.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.valid_to IS 'Temporal validity end - 9999-12-31 for current.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.created_timestamp IS 'When this row was created.';
COMMENT ON COLUMN {{ product }}_Memory.Module_Registry.updated_timestamp IS 'When this row was last updated.';

-- ---------------------------------------------------------------------------
-- Design_Decision — Architecture Decision Records with version chain
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.Design_Decision (
    decision_key            BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    decision_id             VARCHAR(50) NOT NULL,       -- DD-{MODULE}-{NNN}
    decision_version        INTEGER NOT NULL DEFAULT 1,
    decision_title          VARCHAR(200) NOT NULL,
    decision_description    CLOB,
    context                 CLOB,
    alternatives_considered CLOB,
    rationale               CLOB,
    consequences            CLOB,
    decision_status         VARCHAR(20) NOT NULL,       -- PROPOSED, ACCEPTED, SUPERSEDED, DEPRECATED
    decision_category       VARCHAR(50) NOT NULL,       -- ARCHITECTURE, SCHEMA, NAMING, PERFORMANCE, SECURITY, INTEGRATION, OPERATIONAL
    source_module           VARCHAR(50) NOT NULL,
    module_version          VARCHAR(20),
    affects_table           VARCHAR(200),
    decided_by              VARCHAR(100),
    decided_date            DATE,
    superseded_by           VARCHAR(50),
    valid_from              DATE NOT NULL,
    valid_to                DATE DEFAULT DATE '9999-12-31',
    is_current              BYTEINT NOT NULL DEFAULT 1,
    created_timestamp       TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp       TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (decision_key);

COMMENT ON TABLE {{ product }}_Memory.Design_Decision IS
'Architecture Decision Records - why design choices were made, with version chain for superseded decisions.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.decision_id IS 'Human-readable decision id - DD-{MODULE}-{NNN}.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.decision_version IS 'Version within decision_id; increments on supersede.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.decision_title IS 'Short title of the decision.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.decision_description IS 'What was decided.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.context IS 'Why the decision was needed.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.alternatives_considered IS 'Options considered.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.rationale IS 'Why this option was chosen.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.consequences IS 'Impact of the decision.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.decision_status IS 'PROPOSED, ACCEPTED, SUPERSEDED, DEPRECATED.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.decision_category IS 'ARCHITECTURE, SCHEMA, NAMING, PERFORMANCE, SECURITY, INTEGRATION, OPERATIONAL.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.source_module IS 'Module that made the decision.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.module_version IS 'Module version at decision time.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.affects_table IS 'Tables affected.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.decided_by IS 'Author of the decision.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.decided_date IS 'When the decision was made.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.superseded_by IS 'decision_id of the replacement when SUPERSEDED.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.valid_from IS 'Temporal validity start.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.valid_to IS 'Temporal validity end - 9999-12-31 for current.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.is_current IS '1 = current version, 0 = historical.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.created_timestamp IS 'When this row was created.';
COMMENT ON COLUMN {{ product }}_Memory.Design_Decision.updated_timestamp IS 'When this row was last updated.';

-- ---------------------------------------------------------------------------
-- Business_Glossary
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.Business_Glossary (
    glossary_key        BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    term                VARCHAR(200) NOT NULL,
    term_category       VARCHAR(50) NOT NULL,          -- ENTITY, ATTRIBUTE, METRIC, BUSINESS_RULE, CLASSIFICATION, REFERENCE_CODE
    definition          CLOB NOT NULL,
    business_context    CLOB,
    synonyms            VARCHAR(500),
    related_terms       VARCHAR(500),
    related_table       VARCHAR(200),
    related_column      VARCHAR(200),
    source_module       VARCHAR(50) NOT NULL,
    module_version      VARCHAR(20),
    is_active           BYTEINT NOT NULL DEFAULT 1,
    valid_from          DATE NOT NULL,
    valid_to            DATE DEFAULT DATE '9999-12-31',
    created_timestamp   TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp   TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (glossary_key);

COMMENT ON TABLE {{ product }}_Memory.Business_Glossary IS
'Domain term definitions - reduces ambiguity for agents and new team members, versioned per module.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.term IS 'The term being defined.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.term_category IS 'ENTITY, ATTRIBUTE, METRIC, BUSINESS_RULE, CLASSIFICATION, REFERENCE_CODE.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.definition IS 'The definition.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.business_context IS 'Business context and usage.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.synonyms IS 'Synonyms.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.related_terms IS 'Related terms.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.related_table IS 'Table the term relates to.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.related_column IS 'Column the term relates to.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.source_module IS 'Module that introduced the term.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.module_version IS 'Module version at capture time.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.is_active IS '1 = active, 0 = retired.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.valid_from IS 'Temporal validity start.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.valid_to IS 'Temporal validity end - 9999-12-31 for current.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.created_timestamp IS 'When this row was created.';
COMMENT ON COLUMN {{ product }}_Memory.Business_Glossary.updated_timestamp IS 'When this row was last updated.';

-- ---------------------------------------------------------------------------
-- Query_Cookbook
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.Query_Cookbook (
    recipe_key              BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    recipe_id               VARCHAR(50) NOT NULL,       -- QC-{MODULE}-{NNN}
    recipe_title            VARCHAR(200) NOT NULL,
    recipe_description      CLOB NOT NULL,
    use_case                VARCHAR(200) NOT NULL,
    target_module           VARCHAR(50) NOT NULL,       -- DOMAIN, SEARCH, PREDICTION, OBSERVABILITY, SEMANTIC, MEMORY, CROSS
    sql_template            CLOB NOT NULL,
    parameter_descriptions  CLOB,
    performance_notes       CLOB,
    complexity              VARCHAR(20) NOT NULL,       -- SIMPLE, MODERATE, COMPLEX, ADVANCED
    is_batch                BYTEINT NOT NULL DEFAULT 1, -- 1 = batch only, 0 = interactive-safe
    source_module           VARCHAR(50) NOT NULL,
    module_version          VARCHAR(20),
    is_active               BYTEINT NOT NULL DEFAULT 1,
    valid_from              DATE NOT NULL,
    valid_to                DATE DEFAULT DATE '9999-12-31',
    created_timestamp       TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp       TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (recipe_key);

COMMENT ON TABLE {{ product }}_Memory.Query_Cookbook IS
'Proven query patterns - agents use these as starting points rather than generating queries from scratch.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.recipe_id IS 'Human-readable recipe id - QC-{MODULE}-{NNN}.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.recipe_title IS 'Short title.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.recipe_description IS 'What the recipe does.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.use_case IS 'When to use it.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.target_module IS 'Module the recipe queries - or CROSS.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.sql_template IS 'Parameterised query with :parameter placeholders.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.parameter_descriptions IS 'What each parameter means.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.performance_notes IS 'Performance guidance.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.complexity IS 'SIMPLE, MODERATE, COMPLEX, ADVANCED.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.is_batch IS '1 = batch only, 0 = interactive-safe; agents must not run batch recipes interactively unless policy allows.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.source_module IS 'Module that contributed the recipe.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.module_version IS 'Module version at capture time.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.is_active IS '1 = active, 0 = retired/superseded.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.valid_from IS 'Temporal validity start.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.valid_to IS 'Temporal validity end - 9999-12-31 for current.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.created_timestamp IS 'When this recipe version was created.';
COMMENT ON COLUMN {{ product }}_Memory.Query_Cookbook.updated_timestamp IS 'When this recipe version was last maintained.';

-- ---------------------------------------------------------------------------
-- Implementation_Note
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.Implementation_Note (
    note_key            BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    note_id             VARCHAR(50) NOT NULL,          -- IN-{MODULE}-{NNN}
    note_title          VARCHAR(200) NOT NULL,
    note_content        CLOB NOT NULL,
    note_category       VARCHAR(50) NOT NULL,          -- DEPLOYMENT, WORKAROUND, KNOWN_ISSUE, PERFORMANCE_TIP, OPERATIONAL, SECURITY
    severity            VARCHAR(20),                   -- LOW, MEDIUM, HIGH, CRITICAL
    affects_table       VARCHAR(200),
    resolution_status   VARCHAR(20),                   -- OPEN, IN_PROGRESS, RESOLVED, WONT_FIX
    resolution_notes    CLOB,
    source_module       VARCHAR(50) NOT NULL,
    module_version      VARCHAR(20),
    is_active           BYTEINT NOT NULL DEFAULT 1,
    valid_from          DATE NOT NULL,
    valid_to            DATE DEFAULT DATE '9999-12-31',
    created_timestamp   TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp   TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (note_key);

COMMENT ON TABLE {{ product }}_Memory.Implementation_Note IS
'Operational knowledge - workarounds, known issues, deployment tips, and gotchas.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.note_id IS 'Human-readable note id - IN-{MODULE}-{NNN}.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.note_title IS 'Short title.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.note_content IS 'The note.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.note_category IS 'DEPLOYMENT, WORKAROUND, KNOWN_ISSUE, PERFORMANCE_TIP, OPERATIONAL, SECURITY.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.severity IS 'LOW, MEDIUM, HIGH, CRITICAL (NULL for non-issues).';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.affects_table IS 'Tables affected.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.resolution_status IS 'OPEN, IN_PROGRESS, RESOLVED, WONT_FIX.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.resolution_notes IS 'Resolution detail.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.source_module IS 'Module that contributed the note.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.module_version IS 'Module version at capture time.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.is_active IS '1 = active, 0 = retired.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.valid_from IS 'Temporal validity start.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.valid_to IS 'Temporal validity end - 9999-12-31 for current.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.created_timestamp IS 'When this row was created.';
COMMENT ON COLUMN {{ product }}_Memory.Implementation_Note.updated_timestamp IS 'When this row was last updated.';

-- ---------------------------------------------------------------------------
-- Change_Log
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.Change_Log (
    change_key          BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    change_id           VARCHAR(50) NOT NULL,          -- CL-{MODULE}-{NNN}
    version_number      VARCHAR(20) NOT NULL,
    change_title        VARCHAR(200) NOT NULL,
    change_description  CLOB NOT NULL,
    change_type         VARCHAR(30) NOT NULL,          -- INITIAL_RELEASE, SCHEMA_CHANGE, FEATURE_ADDITION, BUG_FIX, PERFORMANCE, DEPRECATION
    change_category     VARCHAR(50) NOT NULL,          -- BREAKING, NON_BREAKING, ADDITIVE, DEPRECATION
    source_module       VARCHAR(50) NOT NULL,
    affects_table       VARCHAR(200),
    migration_steps     CLOB,
    rollback_steps      CLOB,
    related_decision_id VARCHAR(50),                   -- FK to Design_Decision.decision_id
    deployed_date       DATE,
    deployed_by         VARCHAR(100),
    deployment_status   VARCHAR(20) NOT NULL,          -- PLANNED, DEPLOYED, ROLLED_BACK
    created_timestamp   TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (change_key);

COMMENT ON TABLE {{ product }}_Memory.Change_Log IS
'Versioned change history - each row is a point-in-time event; order by version_number to reconstruct deployment history.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.change_id IS 'Human-readable change id - CL-{MODULE}-{NNN}.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.version_number IS 'Version this change belongs to.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.change_title IS 'Short title.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.change_description IS 'What changed.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.change_type IS 'INITIAL_RELEASE, SCHEMA_CHANGE, FEATURE_ADDITION, BUG_FIX, PERFORMANCE, DEPRECATION.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.change_category IS 'BREAKING, NON_BREAKING, ADDITIVE, DEPRECATION.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.source_module IS 'Module the change belongs to.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.affects_table IS 'Tables affected.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.migration_steps IS 'Migration detail.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.rollback_steps IS 'Rollback detail.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.related_decision_id IS 'Links to Design_Decision.decision_id - traceability from change to rationale.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.deployed_date IS 'When deployed.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.deployed_by IS 'Who deployed it.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.deployment_status IS 'PLANNED, DEPLOYED, ROLLED_BACK.';
COMMENT ON COLUMN {{ product }}_Memory.Change_Log.created_timestamp IS 'When this row was created.';
