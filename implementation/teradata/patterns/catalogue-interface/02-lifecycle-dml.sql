-- Catalogue Interface: lifecycle transition DML (Teradata).
-- Binding of design/patterns/catalogue-interface.md, section Change visibility.
--
-- One transition shape, parameterised. DRAFT -> ACTIVE, a contract version change, and
-- ACTIVE -> DEPRECATED are the same operation with different values: close the current
-- version at the event instant, open a successor from it, in one unit of work. Retirement
-- is the same operation plus the deletion flag, per the temporal pattern's rule that a
-- logical deletion is a new current version and never an update in place.
--
-- The five events share one statement rather than having one each, so the sentinel, the
-- change-detection predicate and the transaction boundary are spelled once. Section 1 is
-- the only thing a caller runs for an existing product.
--
-- :params are runtime values; {stage} is a generic tag for the container the build stages
-- its release declaration in, following the convention of the temporal pattern's
-- maintenance file. The open-end sentinel is written explicitly at INSERT time, never as a
-- column default (see the temporal-lifecycle-metadata binding and PLATFORM_PROFILE, SQL
-- idioms and driver constraints).

-- ---------------------------------------------------------------------------
-- 1. The registration transition (close + insert, one transaction)
-- ---------------------------------------------------------------------------
-- Call with the values the successor version carries. The predecessor is found by the
-- sentinel, not by status, so the same statement serves every transition.
--
--   Event                     :new_status   :new_version        :is_deleted  :is_active
--   ------------------------- ------------- ------------------- ------------ ----------
--   Register a new product    DRAFT         initial version     0            0
--   Publish for consumption   ACTIVE        unchanged           0            1
--   Release a new contract    ACTIVE        the new version     0            1
--   Announce withdrawal       DEPRECATED    unchanged           0            1
--   Retire                    RETIRED       unchanged           1            0
--
-- A DRAFT product carries is_active = 0: it is registered and discoverable to its own
-- builders, and not yet offered to consumers. Publication is the transition that flips it.

BT;

-- Close the current version. The change-detection predicate makes replay safe
-- (INV-CATALOGUE-009): re-running a registration whose values already match closes
-- nothing, so the INSERT below finds its guard satisfied and inserts nothing either.
UPDATE governance.data_product_registry
SET   valid_to_dts = :event_dts
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE product_id   = :product_id
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND (   product_status          <> :new_status
       OR product_version         <> :new_version
       OR COALESCE(owner_email, '')             <> COALESCE(:new_owner_email, '')
       OR COALESCE(owner_name, '')              <> COALESCE(:new_owner_name, '')
       OR COALESCE(technical_contact_email, '') <> COALESCE(:new_tech_email, '')
       OR COALESCE(product_description, '')     <> COALESCE(:new_description, '')
       OR is_active                             <> :new_is_active
       OR is_deleted                            <> :new_is_deleted);

-- Open the successor. Every column is carried forward from the closed version except the
-- ones the event changes, so a transition cannot drop a value nobody passed. That matters
-- most for the *_uri pointers and approved_entrypoint: an operator sets those, and an
-- automated registration must not clear them (INV-CATALOGUE-008).
INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database
     , manifest_json
     , contract_uri, semantic_uri, quality_uri, lineage_uri, policy_uri
     , glossary_uri, query_cookbook_uri
     , approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted, deleted_dts)
SELECT r.product_id
     , COALESCE(:new_name, r.product_name)
     , :new_version
     , COALESCE(:new_domain, r.product_domain)
     , COALESCE(:new_description, r.product_description)
     , :new_status
     , COALESCE(:new_owner_team, r.owner_team)
     , COALESCE(:new_owner_name, r.owner_name)
     , COALESCE(:new_owner_email, r.owner_email)
     , COALESCE(:new_tech_name, r.technical_contact_name)
     , COALESCE(:new_tech_email, r.technical_contact_email)
     , r.semantic_database
     , r.memory_database
     , r.observability_database
     , COALESCE(:new_manifest_json, r.manifest_json)
     , r.contract_uri, r.semantic_uri, r.quality_uri, r.lineage_uri, r.policy_uri
     , r.glossary_uri, r.query_cookbook_uri
     , COALESCE(:new_entrypoint, r.approved_entrypoint)
     , COALESCE(:new_access_mode, r.approved_access_mode)
     , :new_is_active
     , :event_dts
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
     , 1
     , :new_is_deleted
     , CASE WHEN :new_is_deleted = 1 THEN :event_dts ELSE NULL END
FROM governance.data_product_registry AS r
WHERE r.product_id    = :product_id
  AND r.valid_to_dts  = :event_dts          -- the row this transaction just closed
  AND NOT EXISTS (                          -- idempotent replay: nothing on a re-run
      SELECT 1
      FROM governance.data_product_registry AS x
      WHERE x.product_id     = :product_id
        AND x.valid_from_dts = :event_dts
  );

ET;

-- ---------------------------------------------------------------------------
-- 2. First registration (no predecessor to close)
-- ---------------------------------------------------------------------------
-- Section 1 carries every value forward from the closed predecessor, so it cannot open the
-- first version of a product. This is the only statement that supplies values outright.
-- Its guard makes a repeated first registration a no-op rather than a duplicate.

INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database
     , manifest_json, approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT :product_id, :product_name, :product_version, :product_domain, :product_description
     , :product_status, :owner_team, :owner_name, :owner_email
     , :tech_name, :tech_email
     , :semantic_database, :memory_database, :observability_database
     , :manifest_json, :approved_entrypoint, :approved_access_mode
     , :is_active
     , :event_dts, TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_registry AS x
    WHERE x.product_id = :product_id
);

-- ---------------------------------------------------------------------------
-- 3. Refreshing the container feed for a release
-- ---------------------------------------------------------------------------
-- Declared containers are refreshed the same way: close what the release no longer
-- declares, open what it newly declares. The build stages the release's own declaration in
-- {stage}.container_declaration, one row per module and layer.

BT;

-- Close containers the release no longer declares. Logical deletion, so a container the
-- product has moved out of stays answerable at any earlier instant.
UPDATE c
FROM   governance.data_product_container AS c
SET   valid_to_dts = :event_dts
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE c.product_id   = :product_id
  AND c.valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND NOT EXISTS (
      SELECT 1
      FROM {stage}.container_declaration AS s
      WHERE s.product_id     = c.product_id
        AND s.module_name     = c.module_name
        AND s.layer_code      = c.layer_code
        AND s.container_name  = c.container_name
  );

INSERT INTO governance.data_product_container
      (product_id, module_name, layer_code, container_name, container_role
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT s.product_id, s.module_name, s.layer_code, s.container_name, s.container_role
     , 1, :event_dts, TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
FROM {stage}.container_declaration AS s
WHERE s.product_id = :product_id
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_container AS c
      WHERE c.product_id    = s.product_id
        AND c.module_name    = s.module_name
        AND c.layer_code     = s.layer_code
        AND c.container_name = s.container_name
        AND c.valid_to_dts   = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  );

ET;

-- ---------------------------------------------------------------------------
-- 4. Refreshing the interface feed for a release
-- ---------------------------------------------------------------------------
-- Same shape at object grain. An object the release withdraws is closed and a successor
-- opened as withdrawn, rather than just closed. A catalogue synchronising on version
-- validity then reads the withdrawal as a fact of the new version, so it can report what
-- a release removed.

BT;

-- The version guard is what makes the refresh replayable. Without it, a re-run closes the
-- generation it just opened, the insert below finds its NOT EXISTS guard already satisfied
-- and opens nothing, and the product is left with a consumer surface of no rows at all.
UPDATE governance.data_product_interface
SET   valid_to_dts = :event_dts
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE product_id      = :product_id
  AND valid_to_dts    = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND product_version <> :new_version;

INSERT INTO governance.data_product_interface
      (product_id, product_version, container_name, object_name, object_kind
     , interface_layer, exposure_type, module_name, entity_name, interface_purpose
     , object_role, is_primary, is_consumer_facing, is_active
     , valid_from_dts, valid_to_dts, is_current, is_deleted, deleted_dts)
SELECT s.product_id, :new_version, s.container_name, s.object_name, s.object_kind
     , s.interface_layer, s.exposure_type, s.module_name, s.entity_name, s.interface_purpose
     , s.object_role, s.is_primary, s.is_consumer_facing, s.is_active
     , :event_dts, TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1
     , 1 - s.is_active
     , CASE WHEN s.is_active = 0 THEN :event_dts ELSE NULL END
FROM {stage}.interface_declaration AS s
WHERE s.product_id = :product_id
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_interface AS i
      WHERE i.product_id     = s.product_id
        AND i.container_name  = s.container_name
        AND i.object_name     = s.object_name
        AND i.valid_from_dts  = :event_dts
  );

ET;

-- ---------------------------------------------------------------------------
-- 5. What this file does not do
-- ---------------------------------------------------------------------------
-- It does not upsert on product_id alone. A single-row MERGE keyed on the product is the
-- version 1.0 registration idiom. Against a versioned registry it either matches several
-- rows or overwrites the current one, and either way the transition history is lost. An
-- automated registration calls section 2 once, then section 1 for every release after.
