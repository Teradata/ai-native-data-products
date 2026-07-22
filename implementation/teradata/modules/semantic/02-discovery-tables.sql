-- Semantic module — discovery tables (Teradata). Binding of design/modules/semantic.md §3.2.
-- Module map, primary objects, and view catalogue. Replace {{ product }}.

-- data_product_map: which modules are deployed, and where --------------------
CREATE TABLE {{ product }}_Semantic.data_product_map (
    module_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    module_name VARCHAR(50) NOT NULL,       -- DOMAIN, SEMANTIC, PREDICTION, SEARCH, MEMORY, OBSERVABILITY
    module_description VARCHAR(1000),
    module_purpose VARCHAR(500),
    database_name VARCHAR(128) NOT NULL,    -- critical for agent discovery
    naming_pattern VARCHAR(20),             -- SEPARATE_DB or SINGLE_DB_PREFIX
    table_prefix VARCHAR(10),
    module_version VARCHAR(20),
    deployment_status VARCHAR(20),          -- DEPLOYED, PLANNED, DEPRECATED
    deployed_dts TIMESTAMP(6) WITH TIME ZONE,
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (module_id);

COMMENT ON TABLE {{ product }}_Semantic.data_product_map IS
'Module registry - agents discover deployed modules and their containers.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.module_name IS 'Module name.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.module_description IS 'Purpose and scope.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.module_purpose IS 'Concise purpose statement.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.database_name IS 'Container the module is deployed in - critical for discovery.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.naming_pattern IS 'SEPARATE_DB or SINGLE_DB_PREFIX.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.table_prefix IS 'Table prefix if SINGLE_DB_PREFIX - D_, P_, S_.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.module_version IS 'Module design-standard version.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.deployment_status IS 'DEPLOYED, PLANNED, DEPRECATED.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.deployed_dts IS 'When the module was deployed.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.is_active IS '1 = active, 0 = deprecated.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.created_at IS 'When this row was created.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map.updated_at IS 'When this row was last updated.';

-- data_product_map_primary_objects: one row per agent-facing object ----------
-- Authoritative fully qualified identity; no CSV, no name derivation.
CREATE TABLE {{ product }}_Semantic.data_product_map_primary_objects (
    primary_object_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    module_id INTEGER NOT NULL,             -- logical parent -> data_product_map.module_id
    database_name VARCHAR(128) CHARACTER SET UNICODE NOT NULL,
    object_name VARCHAR(128) CHARACTER SET UNICODE NOT NULL,
    object_type VARCHAR(50) NOT NULL,       -- TABLE, VIEW, PROCEDURE, FUNCTION
    object_role VARCHAR(50) NOT NULL,       -- controlled vocabulary (design S3.2)
    usage_guidance VARCHAR(500) CHARACTER SET UNICODE,
    table_kind CHAR(1),                     -- DBC.TablesV.TableKind (optional)
    is_active BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (module_id);

COMMENT ON TABLE {{ product }}_Semantic.data_product_map_primary_objects IS
'Primary object registry - one row per agent-facing object; authoritative fully qualified identities.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.module_id IS 'Logical parent -> data_product_map.module_id (validated by trust checks, no physical FK).';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.database_name IS 'Exact deployed container - used verbatim as database_name.object_name.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.object_name IS 'Exact deployed object name - never derived from naming conventions.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.object_type IS 'TABLE, VIEW, PROCEDURE, FUNCTION.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.object_role IS 'How agents should use the object - one role per row, controlled vocabulary.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.usage_guidance IS 'Object-specific instructions or constraints.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.table_kind IS 'DBC.TablesV.TableKind code - enables catalogue-kind mismatch validation.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.is_active IS '1 = live and discoverable, 0 = retired; independent of physical existence.';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.created_dts IS 'Physical row creation time (UTC).';
COMMENT ON COLUMN {{ product }}_Semantic.data_product_map_primary_objects.updated_dts IS 'Physical row last-change time (UTC).';

-- Object role vocabulary: AGENT_ENTRYPOINT, ANALYTICAL_QUERY, REFERENCE_LOOKUP,
-- RELATIONSHIP_BRIDGE, LINEAGE_EVIDENCE, OPERATIONAL_METRIC, WRITE_TARGET, INTERNAL_SUPPORT.

-- view_metadata: one row per (base table, exposing view) ---------------------
CREATE TABLE {{ product }}_Semantic.view_metadata (
    view_metadata_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    base_database VARCHAR(128) NOT NULL,
    base_table VARCHAR(128) NOT NULL,
    view_database VARCHAR(128) NOT NULL,
    view_name VARCHAR(128) NOT NULL,
    view_type VARCHAR(20) NOT NULL,         -- LOCKING, BUSINESS, CURRENT, ENRICHED, PIT, DERIVED
    view_purpose VARCHAR(500),
    is_primary BYTEINT NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    is_active BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (base_table);

COMMENT ON TABLE {{ product }}_Semantic.view_metadata IS
'View catalogue - one row per (base table, exposing view); consumers resolve exposure from metadata, not naming conventions.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.base_database IS 'Container of the base table this view exposes.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.base_table IS 'Base table this view exposes.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.view_database IS 'Container the exposing view is deployed in.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.view_name IS 'Exposing view name - used verbatim.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.view_type IS 'LOCKING (1:1 full contract), BUSINESS, CURRENT, ENRICHED, PIT, DERIVED.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.view_purpose IS 'What this exposure is for and any consumer constraints.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.is_primary IS '1 = primary consumer exposure; at most one active primary per base table.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.is_active IS '1 = live, 0 = retired.';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.created_dts IS 'Physical row creation time (UTC).';
COMMENT ON COLUMN {{ product }}_Semantic.view_metadata.updated_dts IS 'Physical row last-change time (UTC).';

-- view_column_type: curated types for view columns (dictionary cannot report) -
CREATE TABLE {{ product }}_Semantic.view_column_type (
    view_column_type_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    database_name VARCHAR(128) NOT NULL,
    view_name VARCHAR(128) NOT NULL,
    column_name VARCHAR(128) NOT NULL,
    data_type VARCHAR(100) NOT NULL,        -- full friendly string, generated at view-deploy time
    is_active BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (view_name);

COMMENT ON TABLE {{ product }}_Semantic.view_column_type IS
'Curated data types for view columns - supplies what the dictionary cannot report; consumed by column_catalogue.';
