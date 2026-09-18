-- Catalogue Interface: the query surfaces an enterprise catalogue reads (Teradata).
-- Binding of design/patterns/catalogue-interface.md, section The Interface Contract.
--
-- Five views, one per feed. A catalogue integration reads these and nothing else: it does
-- not carry the currency predicate, parse a container name, or join across a product's own
-- containers. Every view takes LOCKING ROW FOR ACCESS so a synchronisation cannot block a
-- registration.
--
-- Each view declares its column list, so the published contract is pinned independently of
-- the select list and a column change is visible in the diff.
--
-- The views live in the same container as the tables. The governance container holds a
-- platform-wide registry rather than one product's module, so the object-placement
-- separation policy that splits a product's tables from its views does not apply. Rule A
-- does apply: no type markers in object names, hence no view suffix on any of these.

-- 1. data_product_current: the default discovery surface ---------------------
-- What version 1.0 clients expect, with the currency predicate applied. A client filtering
-- on is_active and is_deleted alone now matches every historical version of every product;
-- reading this view instead of the table is the one-line migration.
REPLACE VIEW governance.data_product_current
(
      product_id
    , product_name
    , product_version
    , product_domain
    , product_description
    , product_status
    , owner_team
    , owner_name
    , owner_email
    , technical_contact_name
    , technical_contact_email
    , semantic_database
    , memory_database
    , observability_database
    , manifest_json
    , contract_uri
    , semantic_uri
    , quality_uri
    , lineage_uri
    , policy_uri
    , glossary_uri
    , query_cookbook_uri
    , approved_entrypoint
    , approved_access_mode
    , version_from_dts
    , created_dts
    , updated_dts
)
AS
LOCKING ROW FOR ACCESS
SELECT
      r.product_id
    , r.product_name
    , r.product_version
    , r.product_domain
    , r.product_description
    , r.product_status
    , r.owner_team
    , r.owner_name
    , r.owner_email
    , r.technical_contact_name
    , r.technical_contact_email
    , r.semantic_database
    , r.memory_database
    , r.observability_database
    , r.manifest_json
    , r.contract_uri
    , r.semantic_uri
    , r.quality_uri
    , r.lineage_uri
    , r.policy_uri
    , r.glossary_uri
    , r.query_cookbook_uri
    , r.approved_entrypoint
    , r.approved_access_mode
    , r.valid_from_dts
    , r.created_dts
    , r.updated_dts
FROM governance.data_product_registry AS r
WHERE r.is_current = 1
  AND r.is_deleted = 0
  AND r.is_active  = 1;

COMMENT ON VIEW governance.data_product_current IS
'Default product discovery surface - current, live, consumer-visible products only. Read this rather than the registry table: the currency predicate is applied here.';

-- 2. data_product_catalogue: the enterprise catalogue product feed -----------
-- Every registered product in its current version, whatever its state, retired ones
-- included. A catalogue needs the retired rows: without them it cannot tell a product it
-- published and can no longer see from one that was never registered.
--
-- contact_name and contact_email are the single contact for a catalogue that holds exactly
-- one (Alation's contactName and contactEmail). Business owner first, technical contact as
-- fallback, since a catalogue entry is usually read by someone looking for the accountable
-- owner before an engineer. Both pairs are also exposed unreduced.
REPLACE VIEW governance.data_product_catalogue
(
      product_id
    , product_name
    , product_domain
    , product_version
    , product_description
    , product_status
    , is_active
    , is_deleted
    , contact_name
    , contact_email
    , owner_team
    , owner_name
    , owner_email
    , technical_contact_name
    , technical_contact_email
    , approved_entrypoint
    , approved_access_mode
    , contract_uri
    , semantic_uri
    , quality_uri
    , lineage_uri
    , policy_uri
    , glossary_uri
    , query_cookbook_uri
    , version_from_dts
    , retired_dts
    , updated_dts
)
AS
LOCKING ROW FOR ACCESS
SELECT
      r.product_id
    , r.product_name
    , r.product_domain
    , r.product_version
    , r.product_description
    , r.product_status
    , r.is_active
    , r.is_deleted
    , COALESCE(r.owner_name,  r.technical_contact_name)
    , COALESCE(r.owner_email, r.technical_contact_email)
    , r.owner_team
    , r.owner_name
    , r.owner_email
    , r.technical_contact_name
    , r.technical_contact_email
    , r.approved_entrypoint
    , r.approved_access_mode
    , r.contract_uri
    , r.semantic_uri
    , r.quality_uri
    , r.lineage_uri
    , r.policy_uri
    , r.glossary_uri
    , r.query_cookbook_uri
    , r.valid_from_dts
    , r.deleted_dts
    , r.updated_dts
FROM governance.data_product_registry AS r
WHERE r.is_current = 1;

COMMENT ON VIEW governance.data_product_catalogue IS
'Enterprise catalogue product feed - one row per product in its current version, retired products included, with the single resolved contact name and address a catalogue publishes.';
COMMENT ON COLUMN governance.data_product_catalogue.contact_name IS 'Resolved catalogue contact name: business owner, or technical contact where no business owner is recorded.';
COMMENT ON COLUMN governance.data_product_catalogue.contact_email IS 'Resolved catalogue contact address, resolved on the same preference as contact_name.';
COMMENT ON COLUMN governance.data_product_catalogue.retired_dts IS 'Instant the product was retired; NULL while it is not retired.';

-- 3. data_product_lifecycle: the transition feed -----------------------------
-- One row per version of every product, in order, with the state it moved from. A
-- catalogue reads the rows whose version_from_dts is later than its watermark and applies
-- each transition.
--
-- prior_status is derived here rather than stored. A stored predecessor state duplicates
-- what the row order already says, and the two disagree the first time a late correction
-- is loaded out of sequence.
REPLACE VIEW governance.data_product_lifecycle
(
      product_id
    , product_name
    , version_seq
    , product_version
    , prior_version
    , product_status
    , prior_status
    , transition_type
    , version_from_dts
    , version_to_dts
    , is_current
    , is_deleted
    , owner_name
    , owner_email
    , product_description
)
AS
LOCKING ROW FOR ACCESS
SELECT
      r.product_id
    , r.product_name
    , ROW_NUMBER() OVER (PARTITION BY r.product_id ORDER BY r.valid_from_dts)
    , r.product_version
    , LAG(r.product_version) OVER (PARTITION BY r.product_id ORDER BY r.valid_from_dts)
    , r.product_status
    , LAG(r.product_status) OVER (PARTITION BY r.product_id ORDER BY r.valid_from_dts)
    , CASE
          WHEN LAG(r.product_status) OVER (PARTITION BY r.product_id
                                           ORDER BY r.valid_from_dts) IS NULL
              THEN 'REGISTERED'
          WHEN r.is_deleted = 1
              THEN 'RETIRED'
          WHEN r.product_status <> LAG(r.product_status) OVER (PARTITION BY r.product_id
                                                                ORDER BY r.valid_from_dts)
              THEN 'STATUS_CHANGE'
          WHEN r.product_version <> LAG(r.product_version) OVER (PARTITION BY r.product_id
                                                                  ORDER BY r.valid_from_dts)
              THEN 'VERSION_RELEASE'
          ELSE 'METADATA_CHANGE'
      END
    , r.valid_from_dts
    , r.valid_to_dts
    , r.is_current
    , r.is_deleted
    , r.owner_name
    , r.owner_email
    , r.product_description
FROM governance.data_product_registry AS r;

COMMENT ON VIEW governance.data_product_lifecycle IS
'Product transition feed - every version of every product in order, with the state and version it moved from and a classified transition type. The change feed a catalogue synchronises against.';
COMMENT ON COLUMN governance.data_product_lifecycle.transition_type IS 'REGISTERED, STATUS_CHANGE, VERSION_RELEASE, RETIRED, or METADATA_CHANGE - derived from the predecessor version.';
COMMENT ON COLUMN governance.data_product_lifecycle.version_seq IS 'Ordinal of this version within the product, oldest first.';

-- 4. data_product_consumer_interface: what a consumer may query --------------
-- The object list for every product at once. Fully qualified names are assembled from the
-- declared container and object, so a product deployed in any hierarchy under any naming
-- returns correct identities (INV-CATALOGUE-005).
REPLACE VIEW governance.data_product_consumer_interface
(
      product_id
    , product_name
    , product_status
    , product_version
    , module_name
    , entity_name
    , container_name
    , object_name
    , qualified_object_name
    , object_kind
    , interface_layer
    , exposure_type
    , object_role
    , interface_purpose
    , is_primary
    , interface_from_dts
)
AS
LOCKING ROW FOR ACCESS
SELECT
      i.product_id
    , r.product_name
    , r.product_status
    , i.product_version
    , i.module_name
    , i.entity_name
    , i.container_name
    , i.object_name
    , TRIM(i.container_name) || '.' || TRIM(i.object_name)
    , i.object_kind
    , i.interface_layer
    , i.exposure_type
    , i.object_role
    , i.interface_purpose
    , i.is_primary
    , i.valid_from_dts
FROM governance.data_product_interface AS i
INNER JOIN governance.data_product_registry AS r
    ON  r.product_id = i.product_id
    AND r.is_current = 1
WHERE i.is_current         = 1
  AND i.is_deleted         = 0
  AND i.is_active          = 1
  AND i.is_consumer_facing = 1;

COMMENT ON VIEW governance.data_product_consumer_interface IS
'Consumer object list - every object a consumer may query, per product, fully qualified from declared names. The table and view list an enterprise catalogue publishes against a product.';
COMMENT ON COLUMN governance.data_product_consumer_interface.qualified_object_name IS 'Container and object joined for direct use in a query; assembled from declared names, never from a naming convention.';

-- 5. data_product_container_current: where the product is deployed -----------
REPLACE VIEW governance.data_product_container_current
(
      product_id
    , product_name
    , module_name
    , layer_code
    , container_name
    , container_role
    , container_from_dts
)
AS
LOCKING ROW FOR ACCESS
SELECT
      c.product_id
    , r.product_name
    , c.module_name
    , c.layer_code
    , c.container_name
    , c.container_role
    , c.valid_from_dts
FROM governance.data_product_container AS c
INNER JOIN governance.data_product_registry AS r
    ON  r.product_id = c.product_id
    AND r.is_current = 1
WHERE c.is_current = 1
  AND c.is_deleted = 0
  AND c.is_active  = 1;

COMMENT ON VIEW governance.data_product_container_current IS
'Current container map - every container each product occupies, by module and layer, under whatever hierarchy and naming the site deployed it in.';
