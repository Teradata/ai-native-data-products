-- Semantic module — Teradata invariant / validator checks.
-- Backs design/modules/semantic.md §9; canonical STRUCTURAL/SEMANTIC checks the validation
-- pattern lifts. Each query must return ZERO rows for a conforming deployment. Replace {{ product }}.

-- INV-SEMANTIC-003: orphan module references (primary object with no live module)
SELECT po.primary_object_id, po.module_id
FROM {{ product }}_Semantic.data_product_map_primary_objects AS po
WHERE po.is_active = 1
  AND NOT EXISTS (
      SELECT 1 FROM {{ product }}_Semantic.data_product_map AS m
      WHERE m.module_id = po.module_id AND m.is_active = 1);

-- INV-SEMANTIC-003: registered objects missing from the catalogue, or catalogue-kind mismatch
SELECT po.database_name, po.object_name, po.table_kind, t.TableKind AS actual_kind
FROM {{ product }}_Semantic.data_product_map_primary_objects AS po
LEFT JOIN DBC.TablesV AS t
    ON t.DatabaseName = po.database_name AND t.TableName = po.object_name
WHERE po.is_active = 1
  AND (t.TableName IS NULL
       OR (po.table_kind IS NOT NULL AND TRIM(t.TableKind) <> TRIM(po.table_kind)));

-- INV-SEMANTIC-003/007: invalid object roles
SELECT po.primary_object_id, po.object_role
FROM {{ product }}_Semantic.data_product_map_primary_objects AS po
WHERE po.object_role NOT IN
    ('AGENT_ENTRYPOINT','ANALYTICAL_QUERY','REFERENCE_LOOKUP','RELATIONSHIP_BRIDGE',
     'LINEAGE_EVIDENCE','OPERATIONAL_METRIC','WRITE_TARGET','INTERNAL_SUPPORT');

-- INV-SEMANTIC-003: duplicate active registrations
SELECT po.module_id, po.database_name, po.object_name, COUNT(*) AS regs
FROM {{ product }}_Semantic.data_product_map_primary_objects AS po
WHERE po.is_active = 1
GROUP BY po.module_id, po.database_name, po.object_name
HAVING COUNT(*) > 1;

-- INV-SEMANTIC-007: more than one active primary exposure per base table
SELECT vm.base_database, vm.base_table, COUNT(*) AS primaries
FROM {{ product }}_Semantic.view_metadata AS vm
WHERE vm.is_active = 1 AND vm.is_primary = 1
GROUP BY vm.base_database, vm.base_table
HAVING COUNT(*) > 1;

-- INV-SEMANTIC-005: governed base tables with no registered exposure
SELECT e.database_name, e.table_name
FROM {{ product }}_Semantic.entity_metadata AS e
WHERE e.is_active = 1
  AND NOT EXISTS (
      SELECT 1 FROM {{ product }}_Semantic.view_metadata AS vm
      WHERE vm.base_database = e.database_name AND vm.base_table = e.table_name AND vm.is_active = 1);

-- INV-SEMANTIC-005: isolated entities (in entity_metadata but no relationship)
SELECT em.table_name
FROM {{ product }}_Semantic.entity_metadata em
WHERE em.is_active = 1
  AND NOT EXISTS (
      SELECT 1 FROM {{ product }}_Semantic.table_relationship r
      WHERE r.is_active = 1
        AND (r.source_table = em.table_name OR r.target_table = em.table_name));
-- An isolated entity is either a documented standalone (record a Design_Decision) or an omission.
