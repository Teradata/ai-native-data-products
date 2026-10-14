-- Semantic module: product registry (Teradata). Binding of design/modules/semantic.md.
-- The Data Product Orientation Layer anchor. Lives in a shared 'governance' container so agents
-- and MCP clients discover products across the platform. Product-first, not tables-first.
--
-- Version 2.0. The registration is a versioned entity on the SCD2_HISTORY temporal profile
-- with logical deletion, per the catalogue-interface pattern (DEC-TEMPORAL-PATTERN = scd2).
-- Under version 1.0 a status transition overwrote the row, so DRAFT -> ACTIVE -> DEPRECATED
-- -> RETIRED left only the latest state behind. Every transition now closes a version and
-- opens a successor.
--
-- This file cannot import the temporal macros: it is a plain .sql referencing a shared
-- container and takes no product variable (see the temporal-lifecycle-metadata binding).
-- The temporal block below is spelled out and must match what 00-temporal-macros.sql.j2
-- emits for columns('SCD2_HISTORY', supports_deletion=true).
--
-- Portability: where the physical governance container is not named 'governance',
-- map the contract/governance token to it (CTR_DATABASE=governance) rather than editing
-- this file per environment.

CREATE MULTISET TABLE governance.data_product_registry
(
    product_id              VARCHAR(128) CHARACTER SET UNICODE NOT NULL
   ,product_name            VARCHAR(256) CHARACTER SET UNICODE NOT NULL
   ,product_version         VARCHAR(32) NOT NULL
   ,product_domain          VARCHAR(128) CHARACTER SET UNICODE
   ,product_description     VARCHAR(1000) CHARACTER SET UNICODE
   ,product_status          VARCHAR(32) NOT NULL      -- DRAFT, ACTIVE, DEPRECATED, RETIRED
   -- Ownership. owner_team names the accountable function; the contact pairs name the
   -- people a catalogue publishes and a consumer writes to.
   ,owner_team              VARCHAR(256) CHARACTER SET UNICODE
   ,owner_name              VARCHAR(128) CHARACTER SET UNICODE
   ,owner_email             VARCHAR(256) CHARACTER SET UNICODE
   ,technical_contact_name  VARCHAR(128) CHARACTER SET UNICODE
   ,technical_contact_email VARCHAR(256) CHARACTER SET UNICODE
   -- Module containers, retained for compatibility with version 1.0 clients. The
   -- authoritative, placement-independent record is governance.data_product_container,
   -- which carries every module and layer a product occupies under any naming.
   ,semantic_database       VARCHAR(128)
   ,memory_database         VARCHAR(128)
   ,observability_database  VARCHAR(128)
   ,manifest_json           CLOB                      -- machine-readable orientation manifest
   ,contract_uri            VARCHAR(1000)
   ,semantic_uri            VARCHAR(1000)
   ,quality_uri             VARCHAR(1000)
   ,lineage_uri             VARCHAR(1000)
   ,policy_uri              VARCHAR(1000)
   ,glossary_uri            VARCHAR(1000)
   ,query_cookbook_uri      VARCHAR(1000)
   ,approved_entrypoint     VARCHAR(1000)             -- approved first data-access surface
   ,approved_access_mode    VARCHAR(32)               -- VIEW, MCP_TOOL, SEMANTIC_QUERY
   ,trust_authoritative_producer VARCHAR(64)         -- producer_id whose trust map is the product's authoritative one
   ,is_active               BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
    -- Business validity: half-open [valid_from_dts, valid_to_dts)
   ,valid_from_dts          TIMESTAMP(6) WITH TIME ZONE NOT NULL
   ,valid_to_dts            TIMESTAMP(6) WITH TIME ZONE NOT NULL
   ,is_current              BYTEINT NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1))
    -- Logical deletion
   ,is_deleted              BYTEINT NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1))
   ,deleted_dts             TIMESTAMP(6) WITH TIME ZONE
    -- Row audit
   ,created_dts             TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
   ,updated_dts             TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_id);

COMMENT ON TABLE governance.data_product_registry IS
'Product-level registry - agents and MCP clients discover current products, metadata contracts, and approved access entrypoints. Read this first (product-first discovery). Versioned: one row per product version.';
COMMENT ON COLUMN governance.data_product_registry.product_id IS 'Stable product identifier used by agents, manifests, lineage, policies, contracts.';
COMMENT ON COLUMN governance.data_product_registry.product_name IS 'Human-readable product name.';
COMMENT ON COLUMN governance.data_product_registry.product_version IS 'Current contract/release version.';
COMMENT ON COLUMN governance.data_product_registry.product_domain IS 'Business domain the product belongs to; the grouping an enterprise catalogue files it under.';
COMMENT ON COLUMN governance.data_product_registry.product_description IS 'Purpose, scope, intended consumers.';
COMMENT ON COLUMN governance.data_product_registry.product_status IS 'DRAFT, ACTIVE, DEPRECATED, RETIRED. A transition opens a new version; it never updates this value in place.';
COMMENT ON COLUMN governance.data_product_registry.owner_team IS 'Owning team / steward function.';
COMMENT ON COLUMN governance.data_product_registry.owner_name IS 'Accountable business owner, by name. Published as the catalogue contact name.';
COMMENT ON COLUMN governance.data_product_registry.owner_email IS 'Accountable business owner address. Published as the catalogue contact email; required of an active product.';
COMMENT ON COLUMN governance.data_product_registry.technical_contact_name IS 'Engineering contact for the product, by name.';
COMMENT ON COLUMN governance.data_product_registry.technical_contact_email IS 'Engineering contact address, for build, schema and availability questions.';
COMMENT ON COLUMN governance.data_product_registry.semantic_database IS 'Semantic container. Compatibility copy; data_product_container is authoritative.';
COMMENT ON COLUMN governance.data_product_registry.memory_database IS 'Memory container. Compatibility copy; data_product_container is authoritative.';
COMMENT ON COLUMN governance.data_product_registry.observability_database IS 'Observability container. Compatibility copy; data_product_container is authoritative.';
COMMENT ON COLUMN governance.data_product_registry.manifest_json IS 'Machine-readable product orientation manifest for agents and MCP clients.';
COMMENT ON COLUMN governance.data_product_registry.contract_uri IS 'URI for the product contract. Operator-governed; never cleared by re-registration.';
COMMENT ON COLUMN governance.data_product_registry.semantic_uri IS 'URI for Semantic metadata / MCP resource. Operator-governed.';
COMMENT ON COLUMN governance.data_product_registry.quality_uri IS 'URI for data quality rules/reports. Operator-governed.';
COMMENT ON COLUMN governance.data_product_registry.lineage_uri IS 'URI for lineage metadata. Operator-governed.';
COMMENT ON COLUMN governance.data_product_registry.policy_uri IS 'URI for policy / access-control guidance. Operator-governed.';
COMMENT ON COLUMN governance.data_product_registry.glossary_uri IS 'URI for business glossary (Memory). Operator-governed.';
COMMENT ON COLUMN governance.data_product_registry.query_cookbook_uri IS 'URI for validated query recipes (Memory). Operator-governed.';
COMMENT ON COLUMN governance.data_product_registry.approved_entrypoint IS 'Approved first data-access surface (access view, semantic view, MCP tool).';
COMMENT ON COLUMN governance.data_product_registry.approved_access_mode IS 'VIEW, MCP_TOOL, SEMANTIC_QUERY, or site-defined.';
COMMENT ON COLUMN governance.data_product_registry.trust_authoritative_producer IS 'producer_id whose validation trust map is this product''s authoritative one; other producers publish evidence. Named at design time - an implicit designation is not readable (validation pattern, VAL-13).';
COMMENT ON COLUMN governance.data_product_registry.is_active IS '1 = current and discoverable, 0 = inactive.';
COMMENT ON COLUMN governance.data_product_registry.valid_from_dts IS
'Inclusive start of business validity (UTC). Half-open period.';
COMMENT ON COLUMN governance.data_product_registry.valid_to_dts IS
'Exclusive end of business validity (UTC); sentinel 9999-12-31 = current, set by the load.';
COMMENT ON COLUMN governance.data_product_registry.is_current IS
'Convenience currency flag; must agree with the valid_to_dts sentinel.';
COMMENT ON COLUMN governance.data_product_registry.is_deleted IS
'Logical deletion state; 1 requires deleted_dts. History retained.';
COMMENT ON COLUMN governance.data_product_registry.deleted_dts IS
'Effective logical deletion time (UTC); NULL until deleted.';
COMMENT ON COLUMN governance.data_product_registry.created_dts IS
'Physical row-version creation time (UTC).';
COMMENT ON COLUMN governance.data_product_registry.updated_dts IS
'Physical row last-change time (UTC).';

-- Statistics. product_id is the PI and the join column to every child feed. The currency
-- and deletion flags carry the predicate of the default discovery query; the two-flag
-- multi-column statistic lets the optimiser cost the combination rather than multiply two
-- independent estimates.
COLLECT STATISTICS
    COLUMN (product_id)
   ,COLUMN (product_status)
   ,COLUMN (is_current)
   ,COLUMN (is_current, is_deleted)
   ,COLUMN (valid_from_dts)
   ,COLUMN (product_id, valid_from_dts)
ON governance.data_product_registry;

-- MCP catalogue query: discover all current, discoverable products.
-- SELECT product_id, product_name, product_version, semantic_database,
--        approved_entrypoint, approved_access_mode
-- FROM governance.data_product_registry
-- WHERE is_current = 1 AND is_deleted = 0 AND is_active = 1;
--
-- Version 1.0 clients filtered on is_active / is_deleted alone. That predicate now matches
-- every historical version of every product, so is_current = 1 is required. The view
-- governance.data_product_current in the catalogue-interface binding applies it.
