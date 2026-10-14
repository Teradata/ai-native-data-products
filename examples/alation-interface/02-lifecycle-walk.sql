-- Worked example: the full life of one data product, DRAFT to RETIRED.
-- Companion to implementation/teradata/patterns/catalogue-interface/.
--
-- Run 01-seed-registry.sql first: it registers CustExp as DRAFT at 2025-01-15 09:00, and
-- registers two other products that this file never touches. Then run the five stages
-- below in order. After each stage, the queries in 03-verification-queries.sql show what an
-- enterprise catalogue now reads, and what it reads as having changed.
--
-- Every instant is a literal rather than CURRENT_TIMESTAMP, so two people running this get
-- identical output and the verification queries can state exact expected results.
--
--   Stage  Instant (UTC)              Transition
--   -----  -------------------------  ----------------------------------------------------
--   0      2025-01-15 09:00           DRAFT 1.0.0 registered          (01-seed-registry.sql)
--   1      2025-02-03 14:30           ACTIVE 1.0.0, consumer surface published
--   2      2025-06-10 11:15           1.1.0 released: column added, definition changed,
--                                     relationship added, one new business view
--   3      2026-01-19 08:45           DEPRECATED, replacement announced
--   4      2026-06-15 17:00           RETIRED, logically deleted
--
-- Each stage is one transaction: the predecessor closes at the event instant and the
-- successor opens from it. The product never has two current versions, or none.

-- ===========================================================================
-- STAGE 1 - Publication. DRAFT 1.0.0 becomes ACTIVE 1.0.0.
-- ===========================================================================
-- The version does not move - publishing is a governance event, not a contract change.
-- is_active moves from 0 to 1, offering the product to consumers.

BT;

UPDATE governance.data_product_registry
SET   valid_to_dts = TIMESTAMP '2025-02-03 14:30:00.000000+00:00'
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE product_id   = 'retail.customer_experience'
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND (product_status <> 'ACTIVE' OR is_active <> 1);

INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database, manifest_json
     , contract_uri, semantic_uri, quality_uri, lineage_uri, policy_uri
     , glossary_uri, query_cookbook_uri, approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted, deleted_dts)
SELECT r.product_id, r.product_name, r.product_version, r.product_domain, r.product_description
     , 'ACTIVE', r.owner_team, r.owner_name, r.owner_email
     , r.technical_contact_name, r.technical_contact_email
     , r.semantic_database, r.memory_database, r.observability_database, r.manifest_json
     , r.contract_uri, r.semantic_uri, r.quality_uri, r.lineage_uri, r.policy_uri
     , r.glossary_uri, r.query_cookbook_uri, r.approved_entrypoint, r.approved_access_mode
     , 1
     , TIMESTAMP '2025-02-03 14:30:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
     , 1, 0, NULL
FROM governance.data_product_registry AS r
WHERE r.product_id   = 'retail.customer_experience'
  AND r.valid_to_dts = TIMESTAMP '2025-02-03 14:30:00.000000+00:00'
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_registry AS x
      WHERE x.product_id     = 'retail.customer_experience'
        AND x.valid_from_dts = TIMESTAMP '2025-02-03 14:30:00.000000+00:00'
  );

-- The consumer surface, published with the product. Four objects: two access views, one
-- business view, and the semantic column catalogue an agent reads before generating SQL.
-- interface_layer comes from the container feed, not from the container name - the same
-- values would appear if these containers were called something else.
INSERT INTO governance.data_product_interface
      (product_id, product_version, container_name, object_name, object_kind
     , interface_layer, exposure_type, module_name, entity_name, interface_purpose
     , object_role, is_primary, is_consumer_facing, is_active
     , valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT d.product_id, '1.0.0', d.container_name, d.object_name, 'VIEW'
     , d.interface_layer, d.exposure_type, d.module_name, d.entity_name, d.interface_purpose
     , d.object_role, d.is_primary, 1, 1
     , TIMESTAMP '2025-02-03 14:30:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
FROM (
    SELECT 'retail.customer_experience' AS product_id
         , 'CustExp_DOM_ACL_V' AS container_name
         , 'customer_interaction' AS object_name
         , 'ACCESS' AS interface_layer
         , 'CURRENT' AS exposure_type
         , 'DOMAIN' AS module_name
         , 'Customer Interaction' AS entity_name
         , 'Current customer interactions, one row per interaction. The approved entrypoint.' AS interface_purpose
         , 'AGENT_ENTRYPOINT' AS object_role
         , 1 AS is_primary
    UNION ALL SELECT 'retail.customer_experience', 'CustExp_DOM_ACL_V', 'customer', 'ACCESS'
         , 'CURRENT', 'DOMAIN', 'Customer'
         , 'Current customer master. Joins to interactions on customer_id.'
         , 'REFERENCE_LOOKUP', 1
    UNION ALL SELECT 'retail.customer_experience', 'CustExp_DOM_BUS_V'
         , 'customer_experience_summary', 'BUSINESS', 'ENRICHED', 'DOMAIN'
         , 'Customer Experience Summary'
         , 'Interactions joined to customer and satisfaction, aggregated per customer and month.'
         , 'ANALYTICAL_QUERY', 1
    UNION ALL SELECT 'retail.customer_experience', 'CustExp_SEM_ACL_V', 'column_catalogue'
         , 'ACCESS', 'DERIVED', 'SEMANTIC', 'Column Catalogue'
         , 'Column meanings and classifications. Read this before generating SQL.'
         , 'REFERENCE_LOOKUP', 1
) AS d
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_interface AS i
    WHERE i.product_id     = d.product_id
      AND i.container_name  = d.container_name
      AND i.object_name     = d.object_name
);

ET;

-- ===========================================================================
-- STAGE 2 - Release 1.1.0. Three metadata changes and one new interface.
-- ===========================================================================
-- The stage that matters: a contract change a catalogue has to receive correctly. Four
-- things change, in three places, reaching a catalogue by three different routes.
--
--   What changed                          Where it is recorded        How a catalogue sees it
--   ------------------------------------  --------------------------  ------------------------
--   Column added to the interaction set   Semantic column_metadata    version-stamped export
--   Satisfaction definition reworded      Semantic column_metadata    version-stamped export
--   Relationship to channel added         Semantic table_relationship version-stamped export
--   New business view published           governance interface feed   the interface feed
--   The release itself                    governance registry         the lifecycle feed
--
-- The first three land in the product's own Semantic catalogue, which is CURRENT_STATE and
-- holds today's meaning only. The reworded definition overwrites the old text, and no
-- query can recover it.
--
-- The change stays auditable because the product version moves at the same instant, and
-- the release exports a full detail snapshot stamped 1.1.0. A catalogue ends up holding
-- the 1.0.0 and 1.1.0 wordings as two snapshots either side of the transition. A site
-- wanting that history inside the database chooses DEC-TEMPORAL-PATTERN differently for
-- its Semantic module and records the choice; the interface is the same either way.

-- --- 2a. The Semantic catalogue changes ------------------------------------
-- A column added to the domain entity. Its row is new, so nothing is lost.
INSERT INTO CustExp_SEM_STD_T.column_metadata
      (database_name, table_name, column_name, business_description
     , is_pii, is_sensitive, data_classification, is_required, data_type
     , is_active, created_dts, updated_dts)
SELECT 'CustExp_DOM_STD_T', 'customer_interaction', 'resolution_channel_code'
     , 'Channel the interaction was finally resolved through, which may differ from the channel it arrived on. Added in 1.1.0 to support channel-switching analysis.'
     , 0, 0, 'INTERNAL', 0, 'VARCHAR(10)'
     , 1
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
WHERE NOT EXISTS (
    SELECT 1
    FROM CustExp_SEM_STD_T.column_metadata AS c
    WHERE c.database_name = 'CustExp_DOM_STD_T'
      AND c.table_name    = 'customer_interaction'
      AND c.column_name   = 'resolution_channel_code'
);

-- A business definition reworded. An update in place, so the old text is gone from the
-- database once this commits. The change_event row below records that it happened; the
-- export stamped 1.0.0 holds what it said before.
UPDATE CustExp_SEM_STD_T.column_metadata
SET   business_description = 'Customer satisfaction rating for the interaction, 1 to 5, captured by post-interaction survey. From 1.1.0 an unanswered survey is recorded as unknown rather than as the neutral value 3, so averages over 1.0.0 data and later data are not comparable.'
    , updated_dts         = TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
WHERE database_name = 'CustExp_DOM_STD_T'
  AND table_name    = 'customer_interaction'
  AND column_name   = 'satisfaction_score';

-- A relationship added, so an agent can join the new column to something.
INSERT INTO CustExp_SEM_STD_T.table_relationship
      (relationship_name, relationship_description
     , source_database, source_table, source_column
     , target_database, target_table, target_column
     , relationship_type, cardinality, relationship_meaning
     , is_mandatory, is_active, created_dts, updated_dts)
SELECT 'interaction_resolution_channel'
     , 'Resolution channel of an interaction. Added in 1.1.0 with resolution_channel_code.'
     , 'CustExp_DOM_STD_T', 'customer_interaction', 'resolution_channel_code'
     , 'CustExp_DOM_STD_T', 'channel', 'channel_code'
     , 'FOREIGN_KEY', 'MANY_TO_ONE'
     , 'The channel an interaction was resolved through; optional, since an unresolved interaction has none.'
     , 0, 1
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
WHERE NOT EXISTS (
    SELECT 1
    FROM CustExp_SEM_STD_T.table_relationship AS r
    WHERE r.relationship_name = 'interaction_resolution_channel'
);

-- The change events. Table-level and aggregate, per the Observability module. They record
-- that the metadata changed, who changed it and why - the part an update in place would
-- otherwise lose.
INSERT INTO CustExp_OBS_STD_T.change_event
      (database_name, table_name, change_type, change_dts, changed_by
     , change_reason, change_source, records_affected, columns_changed
     , batch_key, job_name, created_dts, updated_dts)
SELECT d.database_name, d.table_name, d.change_type
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
     , 'release_pipeline', d.change_reason, 'ETL', d.records_affected, d.columns_changed
     , 'CUSTEXP-1.1.0', 'customer_experience_release'
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
FROM (
    SELECT 'CustExp_SEM_STD_T' AS database_name, 'column_metadata' AS table_name
         , 'INSERT' AS change_type
         , 'Release 1.1.0: resolution_channel_code added to customer_interaction.' AS change_reason
         , 1 AS records_affected
         , 'resolution_channel_code' AS columns_changed
    UNION ALL SELECT 'CustExp_SEM_STD_T', 'column_metadata', 'UPDATE'
         , 'Release 1.1.0: satisfaction_score definition reworded. Unanswered surveys are now unknown, previously neutral 3; series are not comparable across the boundary.'
         , 1, 'business_description'
    UNION ALL SELECT 'CustExp_SEM_STD_T', 'table_relationship', 'INSERT'
         , 'Release 1.1.0: interaction_resolution_channel relationship added.'
         , 1, 'relationship_name'
) AS d;

-- --- 2b. The new interface ------------------------------------------------
-- One new business view, and the four existing objects carried into 1.1.0. Existing rows
-- are closed and reopened rather than left alone, so the feed states the whole consumer
-- surface as at 1.1.0 and a catalogue never has to assemble it from two versions.

BT;

UPDATE governance.data_product_interface
SET   valid_to_dts = TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE product_id      = 'retail.customer_experience'
  AND valid_to_dts    = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND product_version <> '1.1.0';   -- replay guard: see 02-lifecycle-dml.sql section 4

-- Carry the surviving objects forward at the new version.
INSERT INTO governance.data_product_interface
      (product_id, product_version, container_name, object_name, object_kind
     , interface_layer, exposure_type, module_name, entity_name, interface_purpose
     , object_role, is_primary, is_consumer_facing, is_active
     , valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT i.product_id, '1.1.0', i.container_name, i.object_name, i.object_kind
     , i.interface_layer, i.exposure_type, i.module_name, i.entity_name, i.interface_purpose
     , i.object_role, i.is_primary, 1, 1
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
FROM governance.data_product_interface AS i
WHERE i.product_id   = 'retail.customer_experience'
  AND i.valid_to_dts = TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_interface AS x
      WHERE x.product_id     = i.product_id
        AND x.container_name  = i.container_name
        AND x.object_name     = i.object_name
        AND x.valid_from_dts  = TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
  );

-- The new object.
INSERT INTO governance.data_product_interface
      (product_id, product_version, container_name, object_name, object_kind
     , interface_layer, exposure_type, module_name, entity_name, interface_purpose
     , object_role, is_primary, is_consumer_facing, is_active
     , valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT 'retail.customer_experience', '1.1.0', 'CustExp_DOM_BUS_V'
     , 'interaction_channel_switching', 'VIEW'
     , 'BUSINESS', 'ENRICHED', 'DOMAIN', 'Channel Switching'
     , 'Interactions whose resolution channel differs from their arrival channel. New in 1.1.0.'
     , 'ANALYTICAL_QUERY', 1, 1, 1
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_interface AS i
    WHERE i.product_id     = 'retail.customer_experience'
      AND i.container_name  = 'CustExp_DOM_BUS_V'
      AND i.object_name     = 'interaction_channel_switching'
      AND i.valid_from_dts  = TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
  );

ET;

-- --- 2c. The registry transition -----------------------------------------
-- The version moves and the description gains the incompatibility warning. A catalogue
-- reads this row as VERSION_RELEASE.

BT;

UPDATE governance.data_product_registry
SET   valid_to_dts = TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE product_id   = 'retail.customer_experience'
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND product_version <> '1.1.0';

INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database, manifest_json
     , contract_uri, semantic_uri, quality_uri, lineage_uri, policy_uri
     , glossary_uri, query_cookbook_uri, approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted, deleted_dts)
SELECT r.product_id, r.product_name
     , '1.1.0'
     , r.product_domain
     , 'Customer interaction, channel and satisfaction history for retail customers. Intended for service analytics, churn modelling and agent-assisted enquiry. From 1.1.0 satisfaction averages are not comparable with earlier data.'
     , r.product_status, r.owner_team, r.owner_name, r.owner_email
     , r.technical_contact_name, r.technical_contact_email
     , r.semantic_database, r.memory_database, r.observability_database, r.manifest_json
     , r.contract_uri, r.semantic_uri, r.quality_uri, r.lineage_uri, r.policy_uri
     , r.glossary_uri, r.query_cookbook_uri, r.approved_entrypoint, r.approved_access_mode
     , r.is_active
     , TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
     , 1, 0, NULL
FROM governance.data_product_registry AS r
WHERE r.product_id   = 'retail.customer_experience'
  AND r.valid_to_dts = TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_registry AS x
      WHERE x.product_id     = 'retail.customer_experience'
        AND x.valid_from_dts = TIMESTAMP '2025-06-10 11:15:00.000000+00:00'
  );

ET;

-- ===========================================================================
-- STAGE 3 - Deprecation. The product is still queryable and no longer recommended.
-- ===========================================================================
-- is_active stays 1. A deprecated product that dropped out of discovery would break every
-- consumer still on it. The status and the named replacement both reach a catalogue from
-- this row.

BT;

UPDATE governance.data_product_registry
SET   valid_to_dts = TIMESTAMP '2026-01-19 08:45:00.000000+00:00'
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE product_id   = 'retail.customer_experience'
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND product_status <> 'DEPRECATED';

INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database, manifest_json
     , contract_uri, semantic_uri, quality_uri, lineage_uri, policy_uri
     , glossary_uri, query_cookbook_uri, approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted, deleted_dts)
SELECT r.product_id, r.product_name, r.product_version, r.product_domain
     , 'DEPRECATED 2026-01-19. Superseded by retail.customer_experience_360, which carries the same interactions plus digital channel events. Retirement is planned for 2026-06-15. ' || r.product_description
     , 'DEPRECATED', r.owner_team, r.owner_name, r.owner_email
     , r.technical_contact_name, r.technical_contact_email
     , r.semantic_database, r.memory_database, r.observability_database, r.manifest_json
     , r.contract_uri, r.semantic_uri, r.quality_uri, r.lineage_uri, r.policy_uri
     , r.glossary_uri, r.query_cookbook_uri, r.approved_entrypoint, r.approved_access_mode
     , 1
     , TIMESTAMP '2026-01-19 08:45:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
     , 1, 0, NULL
FROM governance.data_product_registry AS r
WHERE r.product_id   = 'retail.customer_experience'
  AND r.valid_to_dts = TIMESTAMP '2026-01-19 08:45:00.000000+00:00'
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_registry AS x
      WHERE x.product_id     = 'retail.customer_experience'
        AND x.valid_from_dts = TIMESTAMP '2026-01-19 08:45:00.000000+00:00'
  );

ET;

-- ===========================================================================
-- STAGE 4 - Retirement. Logically deleted, fully reconstructable.
-- ===========================================================================
-- Retirement is a logical deletion, which under the temporal pattern means a new current
-- version carrying the flag - never an update in place, never a delete. The consumer
-- surface is withdrawn in the same transaction, so the feed stops offering objects for a
-- product that no longer serves them while still recording that it once did.

BT;

UPDATE governance.data_product_registry
SET   valid_to_dts = TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE product_id   = 'retail.customer_experience'
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND is_deleted   = 0;

INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database, manifest_json
     , contract_uri, semantic_uri, quality_uri, lineage_uri, policy_uri
     , glossary_uri, query_cookbook_uri, approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted, deleted_dts)
SELECT r.product_id, r.product_name, r.product_version, r.product_domain
     , 'RETIRED 2026-06-15. Data retained for audit until 2033-06-15; no consumer access. Superseded by retail.customer_experience_360. ' || r.product_description
     , 'RETIRED', r.owner_team, r.owner_name, r.owner_email
     , r.technical_contact_name, r.technical_contact_email
     , r.semantic_database, r.memory_database, r.observability_database, r.manifest_json
     , r.contract_uri, r.semantic_uri, r.quality_uri, r.lineage_uri, r.policy_uri
     , r.glossary_uri, r.query_cookbook_uri, r.approved_entrypoint, r.approved_access_mode
     , 0
     , TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
     , 1, 1
     , TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
FROM governance.data_product_registry AS r
WHERE r.product_id   = 'retail.customer_experience'
  AND r.valid_to_dts = TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_registry AS x
      WHERE x.product_id     = 'retail.customer_experience'
        AND x.valid_from_dts = TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
  );

-- Withdraw the consumer surface. Each object gets a successor marked withdrawn rather than
-- just being closed, so a catalogue reading the feed forward sees the withdrawal directly
-- instead of inferring it from a missing row.
UPDATE governance.data_product_interface
SET   valid_to_dts = TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE product_id   = 'retail.customer_experience'
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND is_active    = 1;   -- replay guard: a withdrawn surface is not withdrawn twice

INSERT INTO governance.data_product_interface
      (product_id, product_version, container_name, object_name, object_kind
     , interface_layer, exposure_type, module_name, entity_name, interface_purpose
     , object_role, is_primary, is_consumer_facing, is_active
     , valid_from_dts, valid_to_dts, is_current, is_deleted, deleted_dts)
SELECT i.product_id, i.product_version, i.container_name, i.object_name, i.object_kind
     , i.interface_layer, i.exposure_type, i.module_name, i.entity_name, i.interface_purpose
     , i.object_role, i.is_primary, 0, 0
     , TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 1
     , TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
FROM governance.data_product_interface AS i
WHERE i.product_id   = 'retail.customer_experience'
  AND i.valid_to_dts = TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
  AND i.is_active    = 1
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_interface AS x
      WHERE x.product_id     = i.product_id
        AND x.container_name  = i.container_name
        AND x.object_name     = i.object_name
        AND x.valid_from_dts  = TIMESTAMP '2026-06-15 17:00:00.000000+00:00'
  );

-- The containers stay declared and active. The objects still exist and the data is
-- retained for audit, so emptying the container feed on retirement would make it
-- unfindable.

ET;

-- ===========================================================================
-- What the five stages leave behind
-- ===========================================================================
-- Five registry versions for one product, no gap and no overlap, one current. Three
-- interface generations: published at 1.0.0, extended at 1.1.0, withdrawn at retirement.
-- Three change events. Nothing deleted, and every instant still queryable.
--
-- 03-verification-queries.sql runs the reads and states the expected output.
