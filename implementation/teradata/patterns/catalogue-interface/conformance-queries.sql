-- Catalogue Interface: conformance checks (Teradata).
-- One check per invariant in design/patterns/catalogue-interface.md. Every query returns
-- the rows that violate its invariant, so the expected result is always zero rows.
--
-- Halt and report on any row returned. Do not auto-correct. A registry that silently
-- repairs itself has a history nobody can trust, which defeats the point of versioning it.

-- INV-CATALOGUE-001: every registration carries a state from the declared vocabulary.
SELECT r.product_id, r.product_version, r.product_status, r.valid_from_dts
FROM governance.data_product_registry AS r
WHERE r.product_status NOT IN ('DRAFT', 'ACTIVE', 'DEPRECATED', 'RETIRED');

-- INV-CATALOGUE-002: at most one version of a product is current.
SELECT r.product_id, COUNT(*) AS current_versions
FROM governance.data_product_registry AS r
WHERE r.is_current = 1
GROUP BY r.product_id
HAVING COUNT(*) > 1;

-- INV-CATALOGUE-002 (flag agreement): is_current must agree with the sentinel. Queries
-- above use one or the other, so a row carrying only one makes both unreliable.
SELECT r.product_id, r.product_version, r.is_current, r.valid_to_dts
FROM governance.data_product_registry AS r
WHERE (r.is_current = 1
       AND r.valid_to_dts <> TIMESTAMP '9999-12-31 23:59:59.999999+00:00')
   OR (r.is_current = 0
       AND r.valid_to_dts  = TIMESTAMP '9999-12-31 23:59:59.999999+00:00');

-- INV-CATALOGUE-003: history is reconstructable - no gap and no overlap between a
-- product's consecutive versions. The successor's start must equal the predecessor's end.
SELECT r.product_id
     , r.product_version
     , r.valid_to_dts     AS closed_at
     , n.product_version  AS next_version
     , n.valid_from_dts   AS next_opened_at
FROM governance.data_product_registry AS r
INNER JOIN governance.data_product_registry AS n
    ON  n.product_id = r.product_id
WHERE r.is_current = 0
  AND n.valid_from_dts > r.valid_from_dts
  AND n.valid_from_dts <> r.valid_to_dts
  AND NOT EXISTS (          -- only compare a version with its immediate successor
      SELECT 1
      FROM governance.data_product_registry AS m
      WHERE m.product_id     = r.product_id
        AND m.valid_from_dts > r.valid_from_dts
        AND m.valid_from_dts < n.valid_from_dts
  );

-- INV-CATALOGUE-004: a retired product is logically deleted and carries the instant.
SELECT r.product_id, r.product_version, r.product_status, r.is_deleted, r.deleted_dts
FROM governance.data_product_registry AS r
WHERE r.is_current = 1
  AND (   (r.product_status = 'RETIRED' AND (r.is_deleted = 0 OR r.deleted_dts IS NULL))
       OR (r.is_deleted = 1 AND r.product_status <> 'RETIRED'));

-- INV-CATALOGUE-005 (a): every container an interface row names is a declared container.
-- A name that appears only in the interface feed is a name somebody derived.
SELECT i.product_id, i.container_name, i.object_name
FROM governance.data_product_interface AS i
WHERE i.is_current = 1
  AND i.is_deleted = 0
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_container AS c
      WHERE c.product_id     = i.product_id
        AND c.container_name = i.container_name
        AND c.is_current     = 1
        AND c.is_deleted     = 0
  );

-- INV-CATALOGUE-005 (b): every declared object exists in the dictionary, and is the kind
-- it was declared as. Catches a registration describing a product that was never
-- deployed, or was deployed somewhere else.
SELECT i.product_id
     , i.container_name
     , i.object_name
     , i.object_kind
     , t.TableKind AS dictionary_kind
FROM governance.data_product_interface AS i
LEFT OUTER JOIN DBC.TablesV AS t
    ON  t.DatabaseName = i.container_name
    AND t.TableName    = i.object_name
WHERE i.is_current = 1
  AND i.is_deleted = 0
  AND i.is_active  = 1
  AND (   t.TableName IS NULL
       OR (i.object_kind = 'TABLE' AND t.TableKind NOT IN ('T', 'O'))
       OR (i.object_kind = 'VIEW'  AND t.TableKind <> 'V')
       OR (i.object_kind = 'MACRO' AND t.TableKind <> 'M'));

-- INV-CATALOGUE-006: the interface feed agrees with the product's own Semantic catalogue,
-- in both directions. Substitute {semantic_db} with the container the container feed
-- declares for module SEMANTIC, and :product_id with the product being checked. This is
-- the one check that cannot cover all products in a single statement, since each
-- product's source catalogue lives in its own container.
--
-- (a) in the feed, not in the Semantic catalogue: the projection has drifted ahead.
SELECT i.container_name, i.object_name
FROM governance.data_product_interface AS i
WHERE i.product_id        = :product_id
  AND i.is_current        = 1
  AND i.is_deleted        = 0
  AND i.is_active         = 1
  AND i.is_consumer_facing = 1
  AND NOT EXISTS (
      SELECT 1
      FROM {semantic_db}.view_metadata AS v
      WHERE v.view_database = i.container_name
        AND v.view_name     = i.object_name
        AND v.is_active     = 1
        AND v.view_type    <> 'LOCKING'
  );

-- (b) in the Semantic catalogue, not in the feed: the projection has not been refreshed.
SELECT v.view_database, v.view_name, v.view_type
FROM {semantic_db}.view_metadata AS v
WHERE v.is_active  = 1
  AND v.view_type <> 'LOCKING'
  AND NOT EXISTS (
      SELECT 1
      FROM governance.data_product_interface AS i
      WHERE i.product_id        = :product_id
        AND i.container_name    = v.view_database
        AND i.object_name       = v.view_name
        AND i.is_current        = 1
        AND i.is_deleted        = 0
        AND i.is_active         = 1
        AND i.is_consumer_facing = 1
  );

-- INV-CATALOGUE-007: a product published as active carries a reachable contact address.
-- owner_team does not satisfy this - a team name is not an address.
SELECT r.product_id, r.product_name, r.owner_team, r.owner_name, r.owner_email
FROM governance.data_product_registry AS r
WHERE r.is_current = 1
  AND r.is_active  = 1
  AND r.product_status IN ('ACTIVE', 'DEPRECATED')
  AND COALESCE(r.owner_email, r.technical_contact_email) IS NULL;

-- INV-CATALOGUE-008: an operator's detail pointer survives re-registration. Checked as a
-- regression on the transition itself: a product that has been registered more than once
-- and now holds no contract pointer, having held one at an earlier version, has been
-- overwritten by a build.
SELECT r.product_id, r.product_version, r.valid_from_dts
FROM governance.data_product_registry AS r
WHERE r.is_current    = 1
  AND r.contract_uri IS NULL
  AND EXISTS (
      SELECT 1
      FROM governance.data_product_registry AS h
      WHERE h.product_id    = r.product_id
        AND h.contract_uri IS NOT NULL
  );

-- INV-CATALOGUE-009: replay opens no new version - no two versions of a product share a
-- start instant, and no version starts at or after the instant it ends.
SELECT r.product_id, r.valid_from_dts, COUNT(*) AS versions_at_instant
FROM governance.data_product_registry AS r
GROUP BY r.product_id, r.valid_from_dts
HAVING COUNT(*) > 1;

SELECT r.product_id, r.product_version, r.valid_from_dts, r.valid_to_dts
FROM governance.data_product_registry AS r
WHERE r.valid_from_dts >= r.valid_to_dts;

-- Parent integrity: every child feed row names a registered product. The parent reference
-- carries no physical constraint, following the corpus convention for metadata parents,
-- so it is checked here.
SELECT 'CONTAINER' AS feed, c.product_id, c.container_name AS detail
FROM governance.data_product_container AS c
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_registry AS r
    WHERE r.product_id = c.product_id
)
UNION ALL
SELECT 'INTERFACE' AS feed, i.product_id, i.object_name AS detail
FROM governance.data_product_interface AS i
WHERE NOT EXISTS (
    SELECT 1
    FROM governance.data_product_registry AS r
    WHERE r.product_id = i.product_id
);

-- At most one current primary surface per entity per product. Two primaries means the
-- catalogue recommends two objects for the same entity, which helps nobody.
SELECT i.product_id, i.entity_name, COUNT(*) AS primary_surfaces
FROM governance.data_product_interface AS i
WHERE i.is_current = 1
  AND i.is_deleted = 0
  AND i.is_active  = 1
  AND i.is_primary = 1
GROUP BY i.product_id, i.entity_name
HAVING COUNT(*) > 1;
