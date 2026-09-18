-- Worked example: three registered products, three different placements.
-- Companion to implementation/teradata/patterns/catalogue-interface/.
--
-- Three products under three unrelated naming schemes, so you can see that every query in
-- the catalogue interface works for all of them without being told which scheme is in use.
-- Nothing is parsed; every container name is declared. Run it as-is: the governance
-- container is the only name the example fixes, and a site maps its own via the
-- contract/governance token.
--
--   CustExp   Customer Experience     {Product}_{MOD}_{LAYER}, the demo data-product scheme
--   CredExp   Credit Exposure         a group-standard hierarchy that says nothing about
--                                     modules or layers, and does not contain the word
--                                     'dataproducts' anywhere
--   ITSD      IT Service Desk         {ProductCode}_{ModuleAbbrev}, the ITServiceDesk scheme
--
-- 02-lifecycle-walk.sql takes CustExp from DRAFT to RETIRED. CredExp and ITSD stay put, so
-- you can see one product's transitions leave the others alone.

-- ---------------------------------------------------------------------------
-- 1. CustExp: Customer Experience (default demo hierarchy)
-- ---------------------------------------------------------------------------
-- Registered as DRAFT with is_active = 0: it exists and its builders can find it, but it
-- is not yet offered to consumers.
INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database
     , approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT 'retail.customer_experience'
     , 'Customer Experience'
     , '1.0.0'
     , 'Retail Banking'
     , 'Customer interaction, channel and satisfaction history for retail customers. Intended for service analytics, churn modelling and agent-assisted enquiry.'
     , 'DRAFT'
     , 'Retail Customer Analytics'
     , 'Priya Raman'
     , 'priya.raman@example.com'
     , 'Tom Okafor'
     , 'tom.okafor@example.com'
     , 'CustExp_SEM_STD_T'
     , 'CustExp_MEM_STD_T'
     , 'CustExp_OBS_STD_T'
     , 'CustExp_DOM_ACL_V.customer_interaction'
     , 'VIEW'
     , 0
     , TIMESTAMP '2025-01-15 09:00:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
     , 1, 0
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_registry AS x
    WHERE x.product_id = 'retail.customer_experience'
);

-- Containers. Four layers on Domain, fewer on the metadata modules - the usual shape,
-- since only Domain has a business layer worth building.
INSERT INTO governance.data_product_container
      (product_id, module_name, layer_code, container_name, container_role
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT d.product_id, d.module_name, d.layer_code, d.container_name, d.container_role
     , 1, TIMESTAMP '2025-01-15 09:00:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
FROM (
    SELECT 'retail.customer_experience' AS product_id, 'DOMAIN' AS module_name
         , 'BASE' AS layer_code, 'CustExp_DOM_STD_T' AS container_name
         , 'Domain base tables. No consumer access.' AS container_role
    UNION ALL SELECT 'retail.customer_experience', 'DOMAIN', 'VIEW', 'CustExp_DOM_STD_V'
         , 'Governed full-contract views, one per base table. Not a consumer surface.'
    UNION ALL SELECT 'retail.customer_experience', 'DOMAIN', 'ACCESS', 'CustExp_DOM_ACL_V'
         , 'Consumer access views. Current-state exposures granted to the read and agent roles.'
    UNION ALL SELECT 'retail.customer_experience', 'DOMAIN', 'BUSINESS', 'CustExp_DOM_BUS_V'
         , 'Business views. Enriched and joined exposures for analysts and agents.'
    UNION ALL SELECT 'retail.customer_experience', 'SEMANTIC', 'BASE', 'CustExp_SEM_STD_T'
         , 'Semantic catalogue tables. Read directly by agents.'
    UNION ALL SELECT 'retail.customer_experience', 'SEMANTIC', 'ACCESS', 'CustExp_SEM_ACL_V'
         , 'Semantic catalogue views, including the column catalogue and relationship paths.'
    UNION ALL SELECT 'retail.customer_experience', 'MEMORY', 'BASE', 'CustExp_MEM_STD_T'
         , 'Glossary, cookbook, design decisions and agent runtime state.'
    UNION ALL SELECT 'retail.customer_experience', 'OBSERVABILITY', 'BASE', 'CustExp_OBS_STD_T'
         , 'Change events, quality metrics and lineage.'
    UNION ALL SELECT 'retail.customer_experience', 'DOMAIN', 'STAGING', 'CustExp_STG_STD_T'
         , 'Load staging. Cleared after each run; never a consumer surface.'
) AS d
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_container AS c
    WHERE c.product_id     = d.product_id
      AND c.module_name     = d.module_name
      AND c.layer_code      = d.layer_code
      AND c.container_name  = d.container_name
);

-- ---------------------------------------------------------------------------
-- 2. CredExp: Credit Exposure (a hierarchy of the site's own)
-- ---------------------------------------------------------------------------
-- The interesting case. These containers are named for a group risk programme and a
-- jurisdiction. Nothing in them says 'CredExp', nothing says which module or layer they
-- hold, and the word 'dataproducts' does not appear. Every query in
-- 03-verification-queries.sql still returns the right answer, because the module and layer
-- are declared below rather than read out of the name.
INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database
     , approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT 'risk.credit_exposure'
     , 'Credit Exposure'
     , '2.3.1'
     , 'Group Risk'
     , 'Counterparty and facility credit exposure, aggregated to obligor group. Regulatory and internal limit reporting.'
     , 'ACTIVE'
     , 'Group Credit Risk Analytics'
     , 'Alan Whitcombe'
     , 'alan.whitcombe@example.com'
     , 'Sanjay Deol'
     , 'sanjay.deol@example.com'
     , 'GRPRISK_AU_CREDEXP_META'
     , 'GRPRISK_AU_CREDEXP_KNOW'
     , 'GRPRISK_AU_CREDEXP_MON'
     , 'GRPRISK_AU_CREDEXP_PUB.obligor_exposure_current'
     , 'VIEW'
     , 1
     , TIMESTAMP '2024-07-01 08:00:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
     , 1, 0
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_registry AS x
    WHERE x.product_id = 'risk.credit_exposure'
);

INSERT INTO governance.data_product_container
      (product_id, module_name, layer_code, container_name, container_role
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT d.product_id, d.module_name, d.layer_code, d.container_name, d.container_role
     , 1, TIMESTAMP '2024-07-01 08:00:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
FROM (
    SELECT 'risk.credit_exposure' AS product_id, 'DOMAIN' AS module_name
         , 'BASE' AS layer_code, 'GRPRISK_AU_CREDEXP_CORE' AS container_name
         , 'Domain base tables. Restricted to the admin role and the load user.' AS container_role
    UNION ALL SELECT 'risk.credit_exposure', 'DOMAIN', 'VIEW', 'GRPRISK_AU_CREDEXP_CORE_V'
         , 'Governed full-contract views over the core tables.'
    UNION ALL SELECT 'risk.credit_exposure', 'DOMAIN', 'ACCESS', 'GRPRISK_AU_CREDEXP_PUB'
         , 'The consumer surface. Everything a reporting or agent consumer may query.'
    UNION ALL SELECT 'risk.credit_exposure', 'SEMANTIC', 'BASE', 'GRPRISK_AU_CREDEXP_META'
         , 'Semantic catalogue. Entity, column and relationship metadata.'
    UNION ALL SELECT 'risk.credit_exposure', 'MEMORY', 'BASE', 'GRPRISK_AU_CREDEXP_KNOW'
         , 'Glossary and validated query recipes.'
    UNION ALL SELECT 'risk.credit_exposure', 'OBSERVABILITY', 'BASE', 'GRPRISK_AU_CREDEXP_MON'
         , 'Quality metrics and lineage for regulatory attestation.'
) AS d
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_container AS c
    WHERE c.product_id     = d.product_id
      AND c.module_name     = d.module_name
      AND c.layer_code      = d.layer_code
      AND c.container_name  = d.container_name
);

-- Consumer surface. This product exposes everything from one container and has no business
-- layer - its access views are its business views. A catalogue asking for the object list
-- gets four objects. The shape differs from CustExp's because the site chose differently,
-- and nothing downstream needs to care.
INSERT INTO governance.data_product_interface
      (product_id, product_version, container_name, object_name, object_kind
     , interface_layer, exposure_type, module_name, entity_name, interface_purpose
     , object_role, is_primary, is_consumer_facing, is_active
     , valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT d.product_id, '2.3.1', d.container_name, d.object_name, 'VIEW'
     , 'ACCESS', d.exposure_type, 'DOMAIN', d.entity_name, d.interface_purpose
     , d.object_role, d.is_primary, 1, 1
     , TIMESTAMP '2024-07-01 08:00:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
FROM (
    SELECT 'risk.credit_exposure' AS product_id
         , 'GRPRISK_AU_CREDEXP_PUB' AS container_name
         , 'obligor_exposure_current' AS object_name
         , 'CURRENT' AS exposure_type
         , 'Obligor Exposure' AS entity_name
         , 'Current exposure by obligor group. Start here for limit and utilisation questions.' AS interface_purpose
         , 'AGENT_ENTRYPOINT' AS object_role
         , 1 AS is_primary
    UNION ALL SELECT 'risk.credit_exposure', 'GRPRISK_AU_CREDEXP_PUB'
         , 'facility_exposure_current', 'CURRENT', 'Facility Exposure'
         , 'Current exposure by facility. Joins to obligor exposure on obligor_group_id.'
         , 'ANALYTICAL_QUERY', 1
    UNION ALL SELECT 'risk.credit_exposure', 'GRPRISK_AU_CREDEXP_PUB'
         , 'obligor_exposure_as_of', 'PIT', 'Obligor Exposure'
         , 'Point-in-time exposure. Takes an as-at instant; use for attestation and restatement.'
         , 'ANALYTICAL_QUERY', 0
    UNION ALL SELECT 'risk.credit_exposure', 'GRPRISK_AU_CREDEXP_PUB'
         , 'exposure_quality_summary', 'DERIVED', 'Exposure Quality'
         , 'Quality scores for the exposure set. Read before using exposure in a regulatory return.'
         , 'OPERATIONAL_METRIC', 1
) AS d
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_interface AS i
    WHERE i.product_id     = d.product_id
      AND i.container_name  = d.container_name
      AND i.object_name     = d.object_name
);

-- ---------------------------------------------------------------------------
-- 3. ITSD: IT Service Desk (the ITServiceDesk scheme)
-- ---------------------------------------------------------------------------
-- A third scheme: product code plus three-letter module abbreviation, every consumer view
-- in one access container, no per-module view layer.
--
-- Registered with no business owner, only a technical contact, which shows what contact
-- resolution does when the preferred contact is missing - it falls back, so the catalogue
-- still publishes a working address. INV-CATALOGUE-007 passes. A governance report wanting
-- a named business owner still sees the gap, rather than a build user's name in its place.
INSERT INTO governance.data_product_registry
      (product_id, product_name, product_version, product_domain, product_description
     , product_status, owner_team, owner_name, owner_email
     , technical_contact_name, technical_contact_email
     , semantic_database, memory_database, observability_database
     , approved_entrypoint, approved_access_mode
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT 'ops.it_service_desk'
     , 'IT Service Desk'
     , '1.4.0'
     , 'Technology Operations'
     , 'Incident, request and change ticket history with agent and category reference data. Supports service analytics and ticket triage agents.'
     , 'ACTIVE'
     , 'Service Management'
     , NULL
     , NULL
     , 'Dana Ilic'
     , 'dana.ilic@example.com'
     , 'ITSD_SEM'
     , 'ITSD_MEM'
     , 'ITSD_OBS'
     , 'ITSD_ACC.Ticket'
     , 'VIEW'
     , 1
     , TIMESTAMP '2024-11-12 22:30:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
     , 1, 0
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_registry AS x
    WHERE x.product_id = 'ops.it_service_desk'
);

INSERT INTO governance.data_product_container
      (product_id, module_name, layer_code, container_name, container_role
     , is_active, valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT d.product_id, d.module_name, d.layer_code, d.container_name, d.container_role
     , 1, TIMESTAMP '2024-11-12 22:30:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
FROM (
    SELECT 'ops.it_service_desk' AS product_id, 'DOMAIN' AS module_name
         , 'BASE' AS layer_code, 'ITSD_DOM' AS container_name
         , 'Domain tables and internal current views.' AS container_role
    UNION ALL SELECT 'ops.it_service_desk', 'DOMAIN', 'ACCESS', 'ITSD_ACC'
         , 'All consumer-facing views, for every module. Views only; no tables.'
    UNION ALL SELECT 'ops.it_service_desk', 'SEMANTIC', 'BASE', 'ITSD_SEM'
         , 'Semantic catalogue. Granted to the read and agent roles directly.'
    UNION ALL SELECT 'ops.it_service_desk', 'MEMORY', 'BASE', 'ITSD_MEM'
         , 'Documentation and agent runtime state.'
    UNION ALL SELECT 'ops.it_service_desk', 'OBSERVABILITY', 'BASE', 'ITSD_OBS'
         , 'Change events, quality metrics, lineage and agent outcomes.'
    UNION ALL SELECT 'ops.it_service_desk', 'SEARCH', 'BASE', 'ITSD_SCH'
         , 'Entity embeddings for semantic ticket search.'
    UNION ALL SELECT 'ops.it_service_desk', 'PREDICTION', 'BASE', 'ITSD_PRD'
         , 'Ticket feature sets and model predictions.'
) AS d
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_container AS c
    WHERE c.product_id     = d.product_id
      AND c.module_name     = d.module_name
      AND c.layer_code      = d.layer_code
      AND c.container_name  = d.container_name
);

INSERT INTO governance.data_product_interface
      (product_id, product_version, container_name, object_name, object_kind
     , interface_layer, exposure_type, module_name, entity_name, interface_purpose
     , object_role, is_primary, is_consumer_facing, is_active
     , valid_from_dts, valid_to_dts, is_current, is_deleted)
SELECT d.product_id, '1.4.0', 'ITSD_ACC', d.object_name, 'VIEW'
     , 'ACCESS', d.exposure_type, d.module_name, d.entity_name, d.interface_purpose
     , d.object_role, d.is_primary, 1, 1
     , TIMESTAMP '2024-11-12 22:30:00.000000+00:00'
     , TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
FROM (
    SELECT 'ops.it_service_desk' AS product_id, 'Ticket' AS object_name
         , 'CURRENT' AS exposure_type, 'DOMAIN' AS module_name, 'Ticket' AS entity_name
         , 'Current tickets. The approved entrypoint; start every ticket question here.' AS interface_purpose
         , 'AGENT_ENTRYPOINT' AS object_role, 1 AS is_primary
    UNION ALL SELECT 'ops.it_service_desk', 'Ticket_History', 'PIT', 'DOMAIN', 'Ticket'
         , 'Full ticket version history. Use for cycle-time and reopen analysis.'
         , 'ANALYTICAL_QUERY', 0
    UNION ALL SELECT 'ops.it_service_desk', 'Agent', 'CURRENT', 'DOMAIN', 'Agent'
         , 'Service desk agents. Joins to Ticket on assigned_agent_id.'
         , 'REFERENCE_LOOKUP', 1
    UNION ALL SELECT 'ops.it_service_desk', 'Category', 'CURRENT', 'DOMAIN', 'Category'
         , 'Ticket category reference set, including the hierarchy parent.'
         , 'REFERENCE_LOOKUP', 1
    UNION ALL SELECT 'ops.it_service_desk', 'Ticket_Prediction', 'DERIVED', 'PREDICTION'
         , 'Ticket Prediction'
         , 'Predicted resolution time and escalation risk per open ticket.'
         , 'ANALYTICAL_QUERY', 1
) AS d
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_interface AS i
    WHERE i.product_id     = d.product_id
      AND i.container_name  = 'ITSD_ACC'
      AND i.object_name     = d.object_name
);
