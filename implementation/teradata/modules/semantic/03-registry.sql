-- Semantic module — product registry (Teradata). Binding of design/modules/semantic.md §3.2, §4.
-- The Data Product Orientation Layer anchor. Lives in a shared 'governance' container so agents
-- and MCP clients discover products across the platform. Product-first, not tables-first.

CREATE MULTISET TABLE governance.data_product_registry
(
    product_id             VARCHAR(128) NOT NULL
   ,product_name           VARCHAR(256) NOT NULL
   ,product_version        VARCHAR(32) NOT NULL
   ,product_description    VARCHAR(1000)
   ,product_status         VARCHAR(32) NOT NULL      -- DRAFT, ACTIVE, DEPRECATED, RETIRED
   ,owner_team             VARCHAR(256)
   ,semantic_database      VARCHAR(128)
   ,memory_database        VARCHAR(128)
   ,observability_database VARCHAR(128)
   ,manifest_json          CLOB                      -- machine-readable orientation manifest
   ,contract_uri           VARCHAR(1000)
   ,semantic_uri           VARCHAR(1000)
   ,quality_uri            VARCHAR(1000)
   ,lineage_uri            VARCHAR(1000)
   ,policy_uri             VARCHAR(1000)
   ,glossary_uri           VARCHAR(1000)
   ,query_cookbook_uri     VARCHAR(1000)
   ,approved_entrypoint    VARCHAR(1000)             -- approved first data-access surface
   ,approved_access_mode   VARCHAR(32)               -- VIEW, MCP_TOOL, SEMANTIC_QUERY
   ,is_active              BYTEINT NOT NULL
   ,is_deleted             BYTEINT NOT NULL
   ,created_at             TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
   ,updated_at             TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_id);

COMMENT ON TABLE governance.data_product_registry IS
'Product-level registry - agents and MCP clients discover current products, metadata contracts, and approved access entrypoints. Read this first (product-first discovery).';
COMMENT ON COLUMN governance.data_product_registry.product_id IS 'Stable product identifier used by agents, manifests, lineage, policies, contracts.';
COMMENT ON COLUMN governance.data_product_registry.product_name IS 'Human-readable product name.';
COMMENT ON COLUMN governance.data_product_registry.product_version IS 'Current contract/release version.';
COMMENT ON COLUMN governance.data_product_registry.product_description IS 'Purpose, scope, intended consumers.';
COMMENT ON COLUMN governance.data_product_registry.product_status IS 'DRAFT, ACTIVE, DEPRECATED, RETIRED.';
COMMENT ON COLUMN governance.data_product_registry.owner_team IS 'Owning team / steward.';
COMMENT ON COLUMN governance.data_product_registry.semantic_database IS 'Semantic container to query after registry discovery.';
COMMENT ON COLUMN governance.data_product_registry.memory_database IS 'Memory container (glossary, cookbook, design memory).';
COMMENT ON COLUMN governance.data_product_registry.observability_database IS 'Observability container (lineage, quality, usage, validation).';
COMMENT ON COLUMN governance.data_product_registry.manifest_json IS 'Machine-readable product orientation manifest for agents and MCP clients.';
COMMENT ON COLUMN governance.data_product_registry.contract_uri IS 'URI for the product contract.';
COMMENT ON COLUMN governance.data_product_registry.semantic_uri IS 'URI for Semantic metadata / MCP resource.';
COMMENT ON COLUMN governance.data_product_registry.quality_uri IS 'URI for data quality rules/reports.';
COMMENT ON COLUMN governance.data_product_registry.lineage_uri IS 'URI for lineage metadata.';
COMMENT ON COLUMN governance.data_product_registry.policy_uri IS 'URI for policy / access-control guidance.';
COMMENT ON COLUMN governance.data_product_registry.glossary_uri IS 'URI for business glossary (Memory).';
COMMENT ON COLUMN governance.data_product_registry.query_cookbook_uri IS 'URI for validated query recipes (Memory).';
COMMENT ON COLUMN governance.data_product_registry.approved_entrypoint IS 'Approved first data-access surface (access view, semantic view, MCP tool).';
COMMENT ON COLUMN governance.data_product_registry.approved_access_mode IS 'VIEW, MCP_TOOL, SEMANTIC_QUERY, or site-defined.';
COMMENT ON COLUMN governance.data_product_registry.is_active IS '1 = current and discoverable, 0 = inactive.';
COMMENT ON COLUMN governance.data_product_registry.is_deleted IS '1 = logically deleted and hidden, 0 = discoverable when active.';
COMMENT ON COLUMN governance.data_product_registry.created_at IS 'When this row was created.';
COMMENT ON COLUMN governance.data_product_registry.updated_at IS 'When this row was last updated.';

-- MCP catalogue query: discover all current, discoverable products.
-- SELECT product_id, product_name, product_version, semantic_database,
--        approved_entrypoint, approved_access_mode
-- FROM governance.data_product_registry
-- WHERE is_active = 1 AND is_deleted = 0;
