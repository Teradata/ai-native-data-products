-- Catalogue Interface: resolution queries (Teradata).
-- Binding of design/patterns/catalogue-interface.md, sections Placement Independence and
-- Consumer interfaces.
--
-- How a catalogue integration, or an agent, answers three questions: who owns this
-- product, which objects am I meant to query, and what changed. Every query resolves its
-- answer from metadata. None parses a container or object name or assumes a hierarchy.
-- Substitute the product identifier, and where a query reaches into a product's own
-- module, the container name step 1 returned.
--
-- {semantic_db} is a generic tag for a container name discovered at run time, not a
-- parameter: a container name cannot be bound as one. An MCP server or build script
-- substitutes the value it read in step 1.

-- ---------------------------------------------------------------------------
-- 1. Orientation: the product, its contacts, and where its modules are
-- ---------------------------------------------------------------------------
-- The registry is the only object whose location a client has to be told. Everything below
-- is discovered from what this returns.
SELECT c.product_id
     , c.product_name
     , c.product_domain
     , c.product_version
     , c.product_status
     , c.contact_name                  -- Alation contactName
     , c.contact_email                 -- Alation contactEmail
     , c.owner_team
     , c.owner_name
     , c.owner_email
     , c.technical_contact_name
     , c.technical_contact_email
     , c.approved_entrypoint
     , c.approved_access_mode
FROM governance.data_product_catalogue AS c
WHERE c.product_id = :product_id;

-- Every container the product occupies, under whatever naming the site chose. The names
-- come back as data; the client never reconstructs one. This is what makes a product
-- deployed outside the default hierarchy, or under a different name, work unchanged.
SELECT c.module_name
     , c.layer_code
     , c.container_name
     , c.container_role
FROM governance.data_product_container_current AS c
WHERE c.product_id = :product_id
ORDER BY c.module_name, c.layer_code;

-- ---------------------------------------------------------------------------
-- 2. The consumer object list, from the governance feed
-- ---------------------------------------------------------------------------
-- One query, any product, no connection to the product's own containers. This is what an
-- enterprise catalogue publishes as the product's table and view list.
SELECT i.module_name
     , i.entity_name
     , i.qualified_object_name
     , i.object_kind
     , i.interface_layer
     , i.exposure_type
     , i.object_role
     , i.interface_purpose
     , i.is_primary
FROM governance.data_product_consumer_interface AS i
WHERE i.product_id = :product_id
ORDER BY i.module_name, i.entity_name, i.is_primary DESC, i.object_name;

-- The same list for every product at once, which is how a catalogue synchronises a whole
-- platform: add no predicate.
--
-- Where a catalogue holds one asset list per product and wants the count first:
SELECT i.product_id
     , i.product_name
     , COUNT(*) AS consumer_object_count
FROM governance.data_product_consumer_interface AS i
GROUP BY i.product_id, i.product_name
ORDER BY i.product_id;

-- ---------------------------------------------------------------------------
-- 3. The consumer object list, live from the product's Semantic module
-- ---------------------------------------------------------------------------
-- The source the governance feed projects from. A catalogue reads the feed; a conformance
-- check, or an agent already inside the product, reads this. Substitute {semantic_db} with
-- the container step 1 returned for module SEMANTIC.
--
-- Both catalogues are needed. The view catalogue says which view exposes which base table
-- and which exposure is primary. The primary-object registry says how an agent should use
-- an object, in the role vocabulary. An object in neither is not a consumer surface,
-- whatever its container is called.
SELECT v.view_database   AS container_name
     , v.view_name       AS object_name
     , v.view_type                     -- LOCKING, BUSINESS, CURRENT, ENRICHED, PIT, DERIVED
     , v.base_database
     , v.base_table
     , v.view_purpose
     , v.is_primary
     , e.entity_name
     , e.module_name
     , p.object_role
     , p.usage_guidance
FROM {semantic_db}.view_metadata AS v
LEFT OUTER JOIN {semantic_db}.entity_metadata AS e
    ON  e.database_name = v.base_database
    AND e.table_name    = v.base_table
    AND e.is_active     = 1
LEFT OUTER JOIN {semantic_db}.data_product_map_primary_objects AS p
    ON  p.database_name = v.view_database
    AND p.object_name   = v.view_name
    AND p.is_active     = 1
WHERE v.is_active = 1
  -- The governed full-contract exposure is not a consumer surface: it exists so access
  -- views have something other than the base table to select from. Exclude it by
  -- view_type rather than by name, so this still works at a site whose naming says
  -- nothing about tiers.
  AND v.view_type <> 'LOCKING'
ORDER BY e.module_name, e.entity_name, v.is_primary DESC, v.view_name;

-- Objects an agent may use that are not views at all: procedures, macros and the
-- write-back targets. The role vocabulary is what distinguishes them, not the object kind.
SELECT p.database_name AS container_name
     , p.object_name
     , p.object_type
     , p.object_role
     , p.usage_guidance
     , m.module_name
FROM {semantic_db}.data_product_map_primary_objects AS p
INNER JOIN {semantic_db}.data_product_map AS m
    ON  m.module_id = p.module_id
    AND m.is_active = 1
WHERE p.is_active   = 1
  AND p.object_role IN ('AGENT_ENTRYPOINT', 'ANALYTICAL_QUERY', 'REFERENCE_LOOKUP'
                       ,'RELATIONSHIP_BRIDGE', 'OPERATIONAL_METRIC', 'WRITE_TARGET')
ORDER BY m.module_name, p.object_role, p.object_name;

-- ---------------------------------------------------------------------------
-- 4. Building the governance interface declaration from the Semantic catalogue
-- ---------------------------------------------------------------------------
-- What a release runs to stage the interface declaration that 02-lifecycle-dml.sql
-- section 4 then applies. Keeping the projection in one place is what makes
-- INV-CATALOGUE-006 checkable.
--
-- Two attributes are easily confused. exposure_type is what kind of exposure the object
-- is, from the view catalogue. interface_layer is which layer of the product the object
-- sits in, from the container feed, because the layer is a property of the container.
-- Deriving the layer from the exposure type would be a guess; deriving it from the
-- container name would be a guess that happens to look right at sites whose containers
-- are named for their layers.
INSERT INTO {stage}.interface_declaration
      (product_id, container_name, object_name, object_kind, interface_layer
     , exposure_type, module_name, entity_name, interface_purpose, object_role
     , is_primary, is_consumer_facing, is_active)
SELECT :product_id
     , v.view_database
     , v.view_name
     , 'VIEW'
     , c.layer_code
     , v.view_type
     , COALESCE(e.module_name, 'UNKNOWN')
     , e.entity_name
     , v.view_purpose
     , p.object_role
     , v.is_primary
     , 1
     , 1
FROM {semantic_db}.view_metadata AS v
LEFT OUTER JOIN {semantic_db}.entity_metadata AS e
    ON  e.database_name = v.base_database
    AND e.table_name    = v.base_table
    AND e.is_active     = 1
LEFT OUTER JOIN {semantic_db}.data_product_map_primary_objects AS p
    ON  p.database_name = v.view_database
    AND p.object_name   = v.view_name
    AND p.is_active     = 1
LEFT OUTER JOIN governance.data_product_container AS c
    ON  c.product_id     = :product_id
    AND c.container_name  = v.view_database
    AND c.is_current      = 1
    AND c.is_deleted      = 0
WHERE v.is_active  = 1
  AND v.view_type <> 'LOCKING';

-- ---------------------------------------------------------------------------
-- 5. What changed since the last synchronisation
-- ---------------------------------------------------------------------------
-- A catalogue holds one watermark: the instant of its last successful read. Every
-- transition that opened after it is a change to apply, in order. Retirement arrives
-- through this query like any other transition, so nothing has to detect a product by
-- its absence.
SELECT l.product_id
     , l.product_name
     , l.version_seq
     , l.transition_type
     , l.prior_status
     , l.product_status
     , l.prior_version
     , l.product_version
     , l.version_from_dts
     , l.is_current
     , l.is_deleted
     , l.owner_name
     , l.owner_email
FROM governance.data_product_lifecycle AS l
WHERE l.version_from_dts > :watermark_dts
ORDER BY l.version_from_dts, l.product_id;

-- Objects added and withdrawn by those transitions. After applying the product
-- transitions, a catalogue reconciles its asset list from one pass over the interface
-- feed, which carries the withdrawn rows the consumer view filters out.
SELECT i.product_id
     , i.product_version
     , i.container_name
     , i.object_name
     , i.object_kind
     , i.is_consumer_facing
     , i.is_active
     , i.is_deleted
     , i.valid_from_dts
FROM governance.data_product_interface AS i
WHERE i.valid_from_dts > :watermark_dts
ORDER BY i.valid_from_dts, i.product_id, i.container_name, i.object_name;

-- ---------------------------------------------------------------------------
-- 6. Point-in-time: what was published at a past instant
-- ---------------------------------------------------------------------------
-- What an access review, or a question about last quarter's report, needs. Half-open
-- validity means one predicate answers it for any instant, including instants after a
-- product retired.
SELECT r.product_id
     , r.product_name
     , r.product_version
     , r.product_status
     , r.owner_name
     , r.owner_email
     , r.is_deleted
FROM governance.data_product_registry AS r
WHERE r.valid_from_dts <= :as_of_dts
  AND r.valid_to_dts   >  :as_of_dts
ORDER BY r.product_id;
