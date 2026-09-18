-- Catalogue Interface: container and interface feeds (Teradata).
-- Binding of design/patterns/catalogue-interface.md, sections Consumer interfaces and Containers.
--
-- Two child feeds of governance.data_product_registry, at the two grains a catalogue needs
-- and the registry cannot hold in columns: where the product is deployed, and what a
-- consumer may query. Both are versioned on SCD2_HISTORY with logical deletion, for the
-- same reason the registry is. An object withdrawn between versions has to stay visible as
-- withdrawn, and a container a product has moved out of still answers questions about
-- reports run before the move.
--
-- Plain .sql, like the registry: these live in the shared governance container and take no
-- product variable, so they cannot import the temporal macros. The temporal block must
-- match what 00-temporal-macros.sql.j2 emits for
-- columns('SCD2_HISTORY', supports_deletion=true).
--
-- product_id -> data_product_registry.product_id carries no physical referential
-- constraint, following the corpus convention for metadata parents. The conformance
-- queries in this directory check it.

-- data_product_container: every container the product occupies ----------------
-- One row per (product, module, layer). A site that places a module in a different
-- hierarchy, names a container to its own standard, adds a module, or splits one module
-- across more layers, adds rows here rather than needing new columns. Nothing downstream
-- derives a container name from a naming convention (INV-CATALOGUE-005).
CREATE MULTISET TABLE governance.data_product_container
(
    product_id      VARCHAR(128) CHARACTER SET UNICODE NOT NULL
   ,module_name     VARCHAR(50) NOT NULL       -- DOMAIN, SEMANTIC, MEMORY, OBSERVABILITY, SEARCH, PREDICTION, or site-defined
   ,layer_code      VARCHAR(20) NOT NULL       -- BASE, VIEW, ACCESS, BUSINESS, STAGING, or site-defined
   ,container_name  VARCHAR(128) CHARACTER SET UNICODE NOT NULL
   ,container_role  VARCHAR(500) CHARACTER SET UNICODE
   ,is_active       BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
    -- Business validity: half-open [valid_from_dts, valid_to_dts)
   ,valid_from_dts  TIMESTAMP(6) WITH TIME ZONE NOT NULL
   ,valid_to_dts    TIMESTAMP(6) WITH TIME ZONE NOT NULL
   ,is_current      BYTEINT NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1))
    -- Logical deletion
   ,is_deleted      BYTEINT NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1))
   ,deleted_dts     TIMESTAMP(6) WITH TIME ZONE
    -- Row audit
   ,created_dts     TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
   ,updated_dts     TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_id);

COMMENT ON TABLE governance.data_product_container IS
'Container map - one row per (product, module, layer). The authoritative, placement-independent record of where every part of a product is deployed, under any site naming or hierarchy.';
COMMENT ON COLUMN governance.data_product_container.product_id IS 'Logical parent -> data_product_registry.product_id (validated by the conformance queries, no physical constraint).';
COMMENT ON COLUMN governance.data_product_container.module_name IS 'Owning module, or a site-defined module name. Not parsed from the container name.';
COMMENT ON COLUMN governance.data_product_container.layer_code IS 'Which layer of the module this container holds: BASE, VIEW, ACCESS, BUSINESS, STAGING, or a site value. Comparable across products; the container name is not.';
COMMENT ON COLUMN governance.data_product_container.container_name IS 'Exact deployed container name - used verbatim as container_name.object_name.';
COMMENT ON COLUMN governance.data_product_container.container_role IS 'What this container holds and any consumer constraint on reaching it.';
COMMENT ON COLUMN governance.data_product_container.is_active IS '1 = in use, 0 = declared but not in use.';
COMMENT ON COLUMN governance.data_product_container.valid_from_dts IS
'Inclusive start of business validity (UTC). Half-open period.';
COMMENT ON COLUMN governance.data_product_container.valid_to_dts IS
'Exclusive end of business validity (UTC); sentinel 9999-12-31 = current, set by the load.';
COMMENT ON COLUMN governance.data_product_container.is_current IS
'Convenience currency flag; must agree with the valid_to_dts sentinel.';
COMMENT ON COLUMN governance.data_product_container.is_deleted IS
'Logical deletion state; 1 requires deleted_dts. History retained.';
COMMENT ON COLUMN governance.data_product_container.deleted_dts IS
'Effective logical deletion time (UTC); NULL until deleted.';
COMMENT ON COLUMN governance.data_product_container.created_dts IS
'Physical row-version creation time (UTC).';
COMMENT ON COLUMN governance.data_product_container.updated_dts IS
'Physical row last-change time (UTC).';

COLLECT STATISTICS
    COLUMN (product_id)
   ,COLUMN (module_name)
   ,COLUMN (layer_code)
   ,COLUMN (container_name)
   ,COLUMN (is_current, is_deleted)
   ,COLUMN (product_id, module_name, layer_code)
ON governance.data_product_container;

-- data_product_interface: what a consumer is meant to query -------------------
-- A projection of the product's own Semantic catalogue (view_metadata and
-- data_product_map_primary_objects), flattened to the governance container so a catalogue
-- gets one list across every product without connecting to each product's Semantic
-- container. The Semantic catalogue stays authoritative; INV-CATALOGUE-006 checks that
-- this copy still agrees with it.
CREATE MULTISET TABLE governance.data_product_interface
(
    product_id          VARCHAR(128) CHARACTER SET UNICODE NOT NULL
   ,product_version     VARCHAR(32) NOT NULL
   ,container_name      VARCHAR(128) CHARACTER SET UNICODE NOT NULL
   ,object_name         VARCHAR(128) CHARACTER SET UNICODE NOT NULL
   ,object_kind         VARCHAR(20) NOT NULL       -- TABLE, VIEW, MACRO, PROCEDURE, FUNCTION
   ,interface_layer     VARCHAR(20)                -- layer of the container the object lives in
   ,exposure_type       VARCHAR(20)                -- Semantic view catalogue: BUSINESS, CURRENT, ENRICHED, PIT, DERIVED
   ,module_name         VARCHAR(50)
   ,entity_name         VARCHAR(128) CHARACTER SET UNICODE
   ,interface_purpose   VARCHAR(500) CHARACTER SET UNICODE
   ,object_role         VARCHAR(50)                -- Semantic primary-object role vocabulary
   ,is_primary          BYTEINT NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1))
   ,is_consumer_facing  BYTEINT NOT NULL DEFAULT 0 CHECK (is_consumer_facing IN (0, 1))
   ,is_active           BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
    -- Business validity: half-open [valid_from_dts, valid_to_dts)
   ,valid_from_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL
   ,valid_to_dts        TIMESTAMP(6) WITH TIME ZONE NOT NULL
   ,is_current          BYTEINT NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1))
    -- Logical deletion
   ,is_deleted          BYTEINT NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1))
   ,deleted_dts         TIMESTAMP(6) WITH TIME ZONE
    -- Row audit
   ,created_dts         TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
   ,updated_dts         TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_id);

COMMENT ON TABLE governance.data_product_interface IS
'Consumer interface feed - one row per consumer-facing object per product version. Projection of the product Semantic catalogue; the exact object list an enterprise catalogue publishes.';
COMMENT ON COLUMN governance.data_product_interface.product_id IS 'Logical parent -> data_product_registry.product_id (validated by the conformance queries, no physical constraint).';
COMMENT ON COLUMN governance.data_product_interface.product_version IS 'The product version this interface row describes; a withdrawn object is closed, not removed.';
COMMENT ON COLUMN governance.data_product_interface.container_name IS 'Exact deployed container - used verbatim, never derived from a naming convention.';
COMMENT ON COLUMN governance.data_product_interface.object_name IS 'Exact deployed object name - used verbatim, never derived.';
COMMENT ON COLUMN governance.data_product_interface.object_kind IS 'TABLE, VIEW, MACRO, PROCEDURE, FUNCTION.';
COMMENT ON COLUMN governance.data_product_interface.interface_layer IS 'Layer of the container the object lives in, taken from the container feed. Comparable across products whatever the container is named.';
COMMENT ON COLUMN governance.data_product_interface.exposure_type IS 'What kind of exposure the object is, from the Semantic view catalogue: BUSINESS, CURRENT, ENRICHED, PIT, DERIVED.';
COMMENT ON COLUMN governance.data_product_interface.module_name IS 'Module that owns the object.';
COMMENT ON COLUMN governance.data_product_interface.entity_name IS 'Business entity the object exposes - the name a consumer recognises.';
COMMENT ON COLUMN governance.data_product_interface.interface_purpose IS 'What this surface is for and any consumer constraint on using it.';
COMMENT ON COLUMN governance.data_product_interface.object_role IS 'How agents should use the object - the Semantic primary-object role vocabulary.';
COMMENT ON COLUMN governance.data_product_interface.is_primary IS '1 = recommended surface for its entity; at most one current primary per entity.';
COMMENT ON COLUMN governance.data_product_interface.is_consumer_facing IS '1 = a consumer may query it. Declared from the access model, never inferred from a name.';
COMMENT ON COLUMN governance.data_product_interface.is_active IS '1 = live, 0 = withdrawn.';
COMMENT ON COLUMN governance.data_product_interface.valid_from_dts IS
'Inclusive start of business validity (UTC). Half-open period.';
COMMENT ON COLUMN governance.data_product_interface.valid_to_dts IS
'Exclusive end of business validity (UTC); sentinel 9999-12-31 = current, set by the load.';
COMMENT ON COLUMN governance.data_product_interface.is_current IS
'Convenience currency flag; must agree with the valid_to_dts sentinel.';
COMMENT ON COLUMN governance.data_product_interface.is_deleted IS
'Logical deletion state; 1 requires deleted_dts. History retained.';
COMMENT ON COLUMN governance.data_product_interface.deleted_dts IS
'Effective logical deletion time (UTC); NULL until deleted.';
COMMENT ON COLUMN governance.data_product_interface.created_dts IS
'Physical row-version creation time (UTC).';
COMMENT ON COLUMN governance.data_product_interface.updated_dts IS
'Physical row last-change time (UTC).';

COLLECT STATISTICS
    COLUMN (product_id)
   ,COLUMN (product_version)
   ,COLUMN (container_name)
   ,COLUMN (object_name)
   ,COLUMN (is_consumer_facing)
   ,COLUMN (is_current, is_deleted)
   ,COLUMN (product_id, container_name, object_name)
ON governance.data_product_interface;

-- Indexes. Both feeds are metadata: hundreds to low thousands of rows per product, always
-- reached through product_id, which is the primary index. No secondary index is created,
-- since it would be maintained on every registration and read by nothing. The one access
-- path that does not lead with product_id is a catalogue asking which product exposes a
-- given object; on a set this size that is a full scan of a small table. Revisit if a site
-- starts registering products in the thousands.
