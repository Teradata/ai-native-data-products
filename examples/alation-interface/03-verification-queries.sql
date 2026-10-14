-- Worked example: what an enterprise catalogue reads, and what proves it correct.
-- Run after 01-seed-registry.sql and 02-lifecycle-walk.sql.
--
-- Every query states its expected result. The example fixes every instant as a literal so
-- those results are exact rather than approximate.

-- ---------------------------------------------------------------------------
-- 1. The product feed: three products, one of them retired
-- ---------------------------------------------------------------------------
-- Expected: 3 rows.
--   ops.it_service_desk         1.4.0  ACTIVE      Dana Ilic        (fallback contact)
--   retail.customer_experience  1.1.0  RETIRED     Priya Raman      is_deleted = 1
--   risk.credit_exposure        2.3.1  ACTIVE      Alan Whitcombe
--
-- The retired product is present. Without it a catalogue could not tell a product it
-- published last year and must now mark retired from one that never existed.
SELECT c.product_id
     , c.product_name
     , c.product_domain
     , c.product_version
     , c.product_status
     , c.contact_name
     , c.contact_email
     , c.is_active
     , c.is_deleted
     , c.retired_dts
FROM governance.data_product_catalogue AS c
ORDER BY c.product_id;

-- Expected: 2 rows, the two ACTIVE products. CustExp has left discovery because it is
-- retired.
SELECT d.product_id, d.product_name, d.product_version, d.approved_entrypoint
FROM governance.data_product_current AS d
ORDER BY d.product_id;

-- ---------------------------------------------------------------------------
-- 2. The whole life of one product
-- ---------------------------------------------------------------------------
-- Expected: 5 rows, in this order. The version 1.0 registry could not produce this at all.
--
--  seq  version  status      transition_type   from                        to
--  ---  -------  ----------  ----------------  --------------------------  --------------------------
--   1   1.0.0    DRAFT       REGISTERED        2025-01-15 09:00:00+00:00   2025-02-03 14:30:00+00:00
--   2   1.0.0    ACTIVE      STATUS_CHANGE     2025-02-03 14:30:00+00:00   2025-06-10 11:15:00+00:00
--   3   1.1.0    ACTIVE      VERSION_RELEASE   2025-06-10 11:15:00+00:00   2026-01-19 08:45:00+00:00
--   4   1.1.0    DEPRECATED  STATUS_CHANGE     2026-01-19 08:45:00+00:00   2026-06-15 17:00:00+00:00
--   5   1.1.0    RETIRED     RETIRED           2026-06-15 17:00:00+00:00   9999-12-31 23:59:59+00:00
SELECT l.version_seq
     , l.product_version
     , l.prior_version
     , l.product_status
     , l.prior_status
     , l.transition_type
     , l.version_from_dts
     , l.version_to_dts
     , l.is_current
     , l.is_deleted
FROM governance.data_product_lifecycle AS l
WHERE l.product_id = 'retail.customer_experience'
ORDER BY l.version_seq;

-- ---------------------------------------------------------------------------
-- 3. Change feed: what a catalogue applies on its next synchronisation
-- ---------------------------------------------------------------------------
-- A catalogue last synchronised on 2025-03-01. Expected: 3 rows for CustExp - the 1.1.0
-- release, the deprecation and the retirement - and nothing for the other two products,
-- whose registrations are older than the watermark and have not changed since.
SELECT l.product_id
     , l.transition_type
     , l.prior_status
     , l.product_status
     , l.prior_version
     , l.product_version
     , l.version_from_dts
FROM governance.data_product_lifecycle AS l
WHERE l.version_from_dts > TIMESTAMP '2025-03-01 00:00:00.000000+00:00'
ORDER BY l.version_from_dts, l.product_id;

-- Object-level changes over the same watermark. Expected: 10 rows for CustExp - five opened
-- at the 1.1.0 release (four carried forward plus the new channel-switching view), then
-- five withdrawn successors opened at retirement, each carrying is_active = 0.
SELECT i.product_version
     , i.container_name
     , i.object_name
     , i.is_consumer_facing
     , i.is_active
     , i.is_deleted
     , i.valid_from_dts
FROM governance.data_product_interface AS i
WHERE i.product_id     = 'retail.customer_experience'
  AND i.valid_from_dts > TIMESTAMP '2025-03-01 00:00:00.000000+00:00'
ORDER BY i.valid_from_dts, i.container_name, i.object_name;

-- ---------------------------------------------------------------------------
-- 4. The object list: which views and tables a consumer is meant to query
-- ---------------------------------------------------------------------------
-- Expected: 9 rows across two products. CustExp contributes nothing - it is retired and
-- its surface is withdrawn.
--
--   risk.credit_exposure  GRPRISK_AU_CREDEXP_PUB.exposure_quality_summary   ACCESS  DERIVED
--   risk.credit_exposure  GRPRISK_AU_CREDEXP_PUB.facility_exposure_current  ACCESS  CURRENT
--   risk.credit_exposure  GRPRISK_AU_CREDEXP_PUB.obligor_exposure_as_of     ACCESS  PIT
--   risk.credit_exposure  GRPRISK_AU_CREDEXP_PUB.obligor_exposure_current   ACCESS  CURRENT
--   ops.it_service_desk   ITSD_ACC.Agent                                    ACCESS  CURRENT
--   ops.it_service_desk   ITSD_ACC.Category                                 ACCESS  CURRENT
--   ops.it_service_desk   ITSD_ACC.Ticket                                   ACCESS  CURRENT
--   ops.it_service_desk   ITSD_ACC.Ticket_History                           ACCESS  PIT
--   ops.it_service_desk   ITSD_ACC.Ticket_Prediction                        ACCESS  DERIVED
--
-- Three unrelated naming schemes, one query, no name parsing.
SELECT i.product_id
     , i.module_name
     , i.entity_name
     , i.qualified_object_name
     , i.interface_layer
     , i.exposure_type
     , i.object_role
     , i.is_primary
FROM governance.data_product_consumer_interface AS i
ORDER BY i.product_id, i.module_name, i.entity_name, i.object_name;

-- The same list as it stood while CustExp was live. Expected: 5 rows, the 1.1.0 surface,
-- including the channel-switching view. This is how an access review answers what a
-- consumer could reach on a given day.
SELECT i.product_version
     , TRIM(i.container_name) || '.' || TRIM(i.object_name) AS qualified_object_name
     , i.interface_layer
     , i.exposure_type
     , i.object_role
FROM governance.data_product_interface AS i
WHERE i.product_id         = 'retail.customer_experience'
  AND i.is_consumer_facing = 1
  AND i.valid_from_dts    <= TIMESTAMP '2025-09-01 00:00:00.000000+00:00'
  AND i.valid_to_dts       > TIMESTAMP '2025-09-01 00:00:00.000000+00:00'
ORDER BY i.container_name, i.object_name;

-- ---------------------------------------------------------------------------
-- 5. Owner name and email
-- ---------------------------------------------------------------------------
-- Expected: 3 rows. CustExp and CredExp resolve their contact from the business owner.
-- ITSD has no business owner recorded and falls back to its technical contact, with
-- contact_source showing which was used. All three yield an address; a governance report
-- chasing named business owners sees one gap.
SELECT c.product_id
     , c.contact_name                  -- Alation contactName
     , c.contact_email                 -- Alation contactEmail
     , CASE WHEN c.owner_email IS NOT NULL THEN 'BUSINESS_OWNER'
            ELSE 'TECHNICAL_CONTACT'
       END AS contact_source
     , c.owner_team
     , c.owner_name
     , c.owner_email
     , c.technical_contact_name
     , c.technical_contact_email
FROM governance.data_product_catalogue AS c
ORDER BY c.product_id;

-- ---------------------------------------------------------------------------
-- 6. Where each product is deployed
-- ---------------------------------------------------------------------------
-- Expected: 22 rows - 9 for CustExp, 6 for CredExp, 7 for ITSD. layer_code is comparable
-- across the three products; container_name is not.
--
-- Which container holds each product's consumer surface. Expected: 4 rows.
--   ops.it_service_desk         DOMAIN  ACCESS    ITSD_ACC
--   retail.customer_experience  DOMAIN  ACCESS    CustExp_DOM_ACL_V
--   retail.customer_experience  DOMAIN  BUSINESS  CustExp_DOM_BUS_V
--   risk.credit_exposure        DOMAIN  ACCESS    GRPRISK_AU_CREDEXP_PUB
SELECT c.product_id
     , c.module_name
     , c.layer_code
     , c.container_name
     , c.container_role
FROM governance.data_product_container_current AS c
WHERE c.layer_code IN ('ACCESS', 'BUSINESS')
  AND c.module_name = 'DOMAIN'
ORDER BY c.product_id, c.layer_code;

-- Every container, every product.
SELECT c.product_id, c.module_name, c.layer_code, c.container_name
FROM governance.data_product_container_current AS c
ORDER BY c.product_id, c.module_name, c.layer_code;

-- ---------------------------------------------------------------------------
-- 7. Point in time: what was published on a given day
-- ---------------------------------------------------------------------------
-- 2025-09-01, between the 1.1.0 release and the deprecation. Expected: 3 rows, with CustExp
-- as ACTIVE 1.1.0 and not deleted. The same query at 2026-07-01 returns CustExp as RETIRED
-- with is_deleted = 1. A current-state registry cannot answer either.
SELECT r.product_id
     , r.product_name
     , r.product_version
     , r.product_status
     , r.owner_name
     , r.owner_email
     , r.is_deleted
FROM governance.data_product_registry AS r
WHERE r.valid_from_dts <= TIMESTAMP '2025-09-01 00:00:00.000000+00:00'
  AND r.valid_to_dts   >  TIMESTAMP '2025-09-01 00:00:00.000000+00:00'
ORDER BY r.product_id;

-- ---------------------------------------------------------------------------
-- 8. The definition change, and what the database does and does not retain
-- ---------------------------------------------------------------------------
-- Expected: 1 row, the 1.1.0 wording. The 1.0.0 wording is not in the database - the
-- Semantic column catalogue is CURRENT_STATE, and the update overwrote it.
SELECT c.table_name
     , c.column_name
     , c.business_description
     , c.updated_dts
FROM CustExp_SEM_STD_T.column_metadata AS c
WHERE c.database_name = 'CustExp_DOM_STD_T'
  AND c.table_name    = 'customer_interaction'
  AND c.column_name   = 'satisfaction_score';

-- Expected: 3 rows. The database does retain that the change happened, when, under which
-- release, and why - including the warning that the two series are not comparable. Between
-- this and the exports either side of 2025-06-10, a catalogue can show a user both
-- wordings and the reason for the change.
SELECT e.table_name
     , e.change_type
     , e.columns_changed
     , e.change_reason
     , e.batch_key
     , e.change_dts
FROM CustExp_OBS_STD_T.change_event AS e
WHERE e.batch_key = 'CUSTEXP-1.1.0'
ORDER BY e.table_name, e.change_type;

-- The added column and the added relationship are simply present, since neither overwrote
-- anything. Expected: 1 row each.
SELECT c.column_name, c.business_description, c.data_classification, c.created_dts
FROM CustExp_SEM_STD_T.column_metadata AS c
WHERE c.database_name = 'CustExp_DOM_STD_T'
  AND c.table_name    = 'customer_interaction'
  AND c.column_name   = 'resolution_channel_code';

SELECT r.relationship_name
     , r.source_table
     , r.source_column
     , r.target_table
     , r.target_column
     , r.cardinality
     , r.created_dts
FROM CustExp_SEM_STD_T.table_relationship AS r
WHERE r.relationship_name = 'interaction_resolution_channel';

-- ---------------------------------------------------------------------------
-- 9. Conformance
-- ---------------------------------------------------------------------------
-- Run implementation/teradata/patterns/catalogue-interface/conformance-queries.sql against
-- the seeded example. Every check returns zero rows except one:
--
--   INV-CATALOGUE-005 (b), the dictionary check, returns every declared object. The example
--   registers metadata for products whose objects are not deployed on the system you are
--   running against, and the check is meant to catch exactly that. Run it for real only
--   where the products are deployed.
--
-- INV-CATALOGUE-007 passes for all three products, including ITSD, since it requires a
-- reachable address and the fallback supplies one. A site wanting a named business owner on
-- every active product adds that check separately; it will fail for ITSD until filled in.
