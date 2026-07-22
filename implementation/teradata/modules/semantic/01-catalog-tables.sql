-- Semantic module — catalogue tables (Teradata). Binding of design/modules/semantic.md §3.1.
-- Schema metadata only (hundreds of rows), never instance data. Replace {{ product }}.

-- entity_metadata: the entity (table) catalogue -------------------------------
CREATE TABLE {{ product }}_Semantic.entity_metadata (
    entity_metadata_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    entity_name VARCHAR(128) NOT NULL,
    entity_description VARCHAR(1000) NOT NULL,
    module_name VARCHAR(50) NOT NULL,
    database_name VARCHAR(128),
    table_name VARCHAR(128) NOT NULL,
    view_name VARCHAR(128),
    surrogate_key_column VARCHAR(128),
    natural_key_column VARCHAR(128),
    temporal_pattern VARCHAR(50),           -- temporal-lifecycle profile: CURRENT_STATE, SCD2_HISTORY, EVENT_APPEND_ONLY, ...
    current_flag_column VARCHAR(128),
    deleted_flag_column VARCHAR(128),
    industry_standard VARCHAR(50),
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (entity_metadata_id);

COMMENT ON TABLE {{ product }}_Semantic.entity_metadata IS
'Entity (table) catalogue - describes all tables across all modules for agent discovery.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.entity_name IS 'Business name of the entity - Party, Product, Customer.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.entity_description IS 'Business purpose and scope.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.module_name IS 'Owning module - DOMAIN, SEARCH, PREDICTION, OBSERVABILITY, SEMANTIC, MEMORY.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.database_name IS 'Container the table lives in.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.table_name IS 'Physical table name - Party_H, Product_H.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.view_name IS 'Standard current view name - Party_Current.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.surrogate_key_column IS 'Surrogate key column - party_id.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.natural_key_column IS 'Natural key column - party_key.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.temporal_pattern IS 'Temporal-lifecycle profile the entity declares (temporal pattern S6).';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.current_flag_column IS 'Name of the current-version flag - typically is_current.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.deleted_flag_column IS 'Name of the soft-delete flag - typically is_deleted.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.industry_standard IS 'Industry model used - FIBO, HL7, CUSTOM.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.is_active IS '1 = active, 0 = deprecated.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.created_at IS 'When this metadata row was created.';
COMMENT ON COLUMN {{ product }}_Semantic.entity_metadata.updated_at IS 'When this metadata row was last updated.';

-- column_metadata: the column (attribute) catalogue --------------------------
CREATE TABLE {{ product }}_Semantic.column_metadata (
    column_metadata_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    database_name VARCHAR(128) NOT NULL,
    table_name VARCHAR(128) NOT NULL,
    column_name VARCHAR(128) NOT NULL,
    business_description VARCHAR(1000),
    is_pii BYTEINT NOT NULL DEFAULT 0,
    is_sensitive BYTEINT NOT NULL DEFAULT 0,
    data_classification VARCHAR(50),        -- PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
    is_required BYTEINT NOT NULL DEFAULT 1,
    data_type VARCHAR(100),                 -- declared type, as a friendly string
    allowed_values_json JSON,
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (column_metadata_id);

COMMENT ON TABLE {{ product }}_Semantic.column_metadata IS
'Column (attribute) metadata - meanings, classifications, and validation rules. Curated write-target for column_catalogue.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.database_name IS 'Container the table lives in.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.table_name IS 'Table containing the column.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.column_name IS 'Physical column name.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.business_description IS 'What the data represents.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.is_pii IS '1 = contains PII, 0 = none.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.is_sensitive IS '1 = sensitive, 0 = not.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.data_classification IS 'PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.is_required IS '1 = required (NOT NULL), 0 = nullable.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.data_type IS 'Declared data type as a friendly string.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.allowed_values_json IS 'Permitted-value domain for constrained columns.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.is_active IS '1 = active, 0 = deprecated.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.created_at IS 'When this row was created.';
COMMENT ON COLUMN {{ product }}_Semantic.column_metadata.updated_at IS 'When this row was last updated.';

-- naming_standard: documented naming conventions -----------------------------
CREATE TABLE {{ product }}_Semantic.naming_standard (
    naming_standard_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    standard_type VARCHAR(50) NOT NULL,     -- SUFFIX, PREFIX, PATTERN, ABBREVIATION
    standard_value VARCHAR(100) NOT NULL,
    meaning VARCHAR(500) NOT NULL,
    usage_guidance VARCHAR(1000),
    applies_to VARCHAR(50),                 -- TABLE, COLUMN, VIEW, ALL
    examples VARCHAR(1000),
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (naming_standard_id);

COMMENT ON TABLE {{ product }}_Semantic.naming_standard IS
'Naming conventions - documents naming patterns for agent interpretation.';
COMMENT ON COLUMN {{ product }}_Semantic.naming_standard.standard_type IS 'SUFFIX, PREFIX, PATTERN, ABBREVIATION.';
COMMENT ON COLUMN {{ product }}_Semantic.naming_standard.standard_value IS 'The naming element - _H, _id, is_, dts.';
COMMENT ON COLUMN {{ product }}_Semantic.naming_standard.meaning IS 'What the element means.';
COMMENT ON COLUMN {{ product }}_Semantic.naming_standard.usage_guidance IS 'How and when to apply it.';
COMMENT ON COLUMN {{ product }}_Semantic.naming_standard.applies_to IS 'TABLE, COLUMN, VIEW, ALL.';
COMMENT ON COLUMN {{ product }}_Semantic.naming_standard.examples IS 'Example usage.';
COMMENT ON COLUMN {{ product }}_Semantic.naming_standard.is_active IS '1 = current, 0 = deprecated.';
COMMENT ON COLUMN {{ product }}_Semantic.naming_standard.created_at IS 'When documented.';

-- table_relationship: how tables join ----------------------------------------
CREATE TABLE {{ product }}_Semantic.table_relationship (
    relationship_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    relationship_name VARCHAR(128) NOT NULL,
    relationship_description VARCHAR(1000),
    source_database VARCHAR(128),
    source_table VARCHAR(100) NOT NULL,
    source_column VARCHAR(128) NOT NULL,
    target_database VARCHAR(128),
    target_table VARCHAR(100) NOT NULL,
    target_column VARCHAR(128) NOT NULL,
    relationship_type VARCHAR(50) NOT NULL, -- FOREIGN_KEY, HIERARCHY, ASSOCIATIVE
    cardinality VARCHAR(20),                -- ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY
    relationship_meaning VARCHAR(500),
    is_mandatory BYTEINT NOT NULL DEFAULT 0,
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (relationship_id);

COMMENT ON TABLE {{ product }}_Semantic.table_relationship IS
'Table-level relationship metadata - how tables join, for correct agent SQL generation. Must be complete (design S5).';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.relationship_name IS 'Descriptive relationship name.';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.source_table IS 'Table holding the referencing (foreign) key.';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.source_column IS 'The referencing key column.';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.target_table IS 'The referenced table.';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.target_column IS 'The referenced key column.';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.relationship_type IS 'FOREIGN_KEY, HIERARCHY, ASSOCIATIVE.';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.cardinality IS 'ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY.';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.is_mandatory IS '1 = referencing key is required, 0 = optional.';
COMMENT ON COLUMN {{ product }}_Semantic.table_relationship.is_active IS '1 = valid, 0 = deprecated.';
