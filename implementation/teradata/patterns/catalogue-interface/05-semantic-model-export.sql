-- Catalogue Interface: semantic model extraction (Teradata).
-- Binding of design/patterns/catalogue-interface.md, section Semantic Model Export.
--
-- Six result sets that together are one product's semantic model: datasets, fields,
-- relationships, metrics, metric expressions, and synonyms. An emitter runs these in order
-- and renders the target format; the shaping of the output belongs to the emitter, and the
-- selection of what is in the model belongs here.
--
-- Substitute {semantic_db} with the container the container feed declares for module
-- SEMANTIC (04-resolution-queries.sql, step 1), and bind :product_id. Nothing is derived
-- from a container or object name.
--
-- Every query selects declared rows only. A product with no metrics returns no metric
-- rows, and the export then has no metrics; see EMITTERS.md for what an emitter does with
-- an empty result and INV-CATALOGUE-011 for why it does not fill the gap.

-- ---------------------------------------------------------------------------
-- 1. Datasets
-- ---------------------------------------------------------------------------
-- One row per business entity. The source object is the consumer-facing exposure where the
-- product declares one, and the base table otherwise: a semantic model that named base
-- tables would publish a surface consumers have no rights on.
SELECT e.entity_name
     , e.entity_description
     , e.module_name
     , COALESCE(i.container_name, e.database_name) AS source_container
     , COALESCE(i.object_name, e.table_name)       AS source_object
     , e.surrogate_key_column
     , e.natural_key_column
     , e.temporal_pattern
     , e.table_name                                AS base_table
     , e.database_name                             AS base_container
FROM {semantic_db}.entity_metadata AS e
LEFT OUTER JOIN governance.data_product_consumer_interface AS i
    ON  i.product_id = :product_id
    AND i.entity_name = e.entity_name
    AND i.is_primary  = 1
WHERE e.is_active = 1
ORDER BY e.module_name, e.entity_name;

-- ---------------------------------------------------------------------------
-- 2. Fields
-- ---------------------------------------------------------------------------
-- One row per column of each dataset. The join is on the base table, since column metadata
-- is curated against the physical column; the emitter attaches each field to the dataset
-- query 1 returned for that base table.
--
-- is_time marks a field a consuming tool may use as a time dimension. Resolved from the
-- declared type rather than from the column name, so a column called period_key that holds
-- an integer is not offered as a date.
SELECT c.database_name AS base_container
     , c.table_name    AS base_table
     , c.column_name
     , c.business_description
     , c.data_type
     , c.is_required
     , c.is_pii
     , c.is_sensitive
     , c.data_classification
     , c.allowed_values_json
     , CASE WHEN UPPER(c.data_type) LIKE 'DATE%'
              OR UPPER(c.data_type) LIKE 'TIMESTAMP%'
            THEN 1 ELSE 0
       END AS is_time
FROM {semantic_db}.column_metadata AS c
INNER JOIN {semantic_db}.entity_metadata AS e
    ON  e.database_name = c.database_name
    AND e.table_name    = c.table_name
    AND e.is_active     = 1
WHERE c.is_active = 1
ORDER BY c.table_name, c.column_name;

-- ---------------------------------------------------------------------------
-- 3. Relationships
-- ---------------------------------------------------------------------------
-- Emitted from the referencing entity to the referenced one. The declared cardinality says
-- which way that runs, and emit_direction below tells the emitter what to do rather than
-- leaving it to interpret the vocabulary:
--
--   MANY_TO_ONE, ONE_TO_ONE   AS_DECLARED  source holds the reference
--   ONE_TO_MANY               INVERT       target holds the reference
--   MANY_TO_MANY, unstated    REPORT       no single-direction form (INV-CATALOGUE-013)
--
-- A MANY_TO_MANY row is returned rather than filtered out, so the emitter can report it.
-- Silently dropping it would leave a model that looks complete and is not.
SELECT r.relationship_name
     , r.relationship_description
     , r.source_database
     , r.source_table
     , r.source_column
     , r.target_database
     , r.target_table
     , r.target_column
     , r.relationship_type
     , r.cardinality
     , r.is_mandatory
     , r.relationship_meaning
     , CASE r.cardinality
           WHEN 'MANY_TO_ONE'  THEN 'AS_DECLARED'
           WHEN 'ONE_TO_ONE'   THEN 'AS_DECLARED'
           WHEN 'ONE_TO_MANY'  THEN 'INVERT'
           ELSE 'REPORT'
       END AS emit_direction
FROM {semantic_db}.table_relationship AS r
WHERE r.is_active = 1
ORDER BY r.relationship_name;

-- ---------------------------------------------------------------------------
-- 4. Metrics
-- ---------------------------------------------------------------------------
-- Model-level, with the entity the metric is grained on. A metric whose primary dataset is
-- not a registered active entity is excluded here and reported by the module check
-- (INV-SEMANTIC-014): exporting it would put a measure into a catalogue that resolves to
-- nothing.
SELECT m.metric_name
     , m.metric_description
     , m.metric_datatype
     , m.aggregation_type
     , m.unit
     , m.grain_description
     , m.is_additive
     , d.container_name AS primary_container
     , d.table_name     AS primary_table
FROM {semantic_db}.metric_metadata AS m
INNER JOIN {semantic_db}.metric_dataset AS d
    ON  d.metric_name  = m.metric_name
    AND d.dataset_role = 'PRIMARY'
    AND d.is_active    = 1
WHERE m.is_active = 1
  AND EXISTS (
      SELECT 1
      FROM {semantic_db}.entity_metadata AS e
      WHERE e.table_name = d.table_name
        AND e.is_active  = 1
  )
ORDER BY m.metric_name;

-- Every dataset each metric reads, primary and joined. An emitter uses this to place a
-- metric only in a model that contains all the entities it needs.
SELECT d.metric_name
     , d.container_name
     , d.table_name
     , d.dataset_role
FROM {semantic_db}.metric_dataset AS d
INNER JOIN {semantic_db}.metric_metadata AS m
    ON  m.metric_name = d.metric_name
    AND m.is_active   = 1
WHERE d.is_active = 1
ORDER BY d.metric_name, d.dataset_role, d.table_name;

-- ---------------------------------------------------------------------------
-- 5. Metric expressions
-- ---------------------------------------------------------------------------
-- One row per metric per dialect. An emitter targeting a format that accepts several
-- dialects emits them all; one that accepts a single expression takes the dialect named in
-- its configuration, and reports a metric that has no expression in that dialect rather
-- than substituting another one.
SELECT x.metric_name
     , x.sql_dialect
     , x.expression_text
FROM {semantic_db}.metric_expression AS x
INNER JOIN {semantic_db}.metric_metadata AS m
    ON  m.metric_name = x.metric_name
    AND m.is_active   = 1
WHERE x.is_active = 1
ORDER BY x.metric_name, x.sql_dialect;

-- ---------------------------------------------------------------------------
-- 6. Synonyms
-- ---------------------------------------------------------------------------
-- Attached to entities, columns and metrics. The emitter groups them onto the object each
-- resolves to; an orphaned synonym is reported by the module check (INV-SEMANTIC-015) and
-- is excluded here by the resolution predicates.
SELECT s.object_kind
     , s.container_name
     , s.object_name
     , s.column_name
     , s.synonym_text
FROM {semantic_db}.semantic_synonym AS s
WHERE s.is_active = 1
  AND (   (s.object_kind = 'ENTITY'
           AND EXISTS (SELECT 1
                       FROM {semantic_db}.entity_metadata AS e
                       WHERE e.table_name = s.object_name
                         AND e.is_active  = 1))
       OR (s.object_kind = 'COLUMN'
           AND EXISTS (SELECT 1
                       FROM {semantic_db}.column_metadata AS c
                       WHERE c.table_name  = s.object_name
                         AND c.column_name = s.column_name
                         AND c.is_active   = 1))
       OR (s.object_kind = 'METRIC'
           AND EXISTS (SELECT 1
                       FROM {semantic_db}.metric_metadata AS m
                       WHERE m.metric_name = s.object_name
                         AND m.is_active   = 1)))
ORDER BY s.object_kind, s.object_name, s.column_name, s.synonym_text;

-- ---------------------------------------------------------------------------
-- 7. The product descriptor
-- ---------------------------------------------------------------------------
-- The second artefact. Identity, contacts and pointers from the product feed; the output
-- objects from the interface feed. Both are governance-container reads and need no
-- {semantic_db} substitution, which is why a descriptor can be emitted for a product whose
-- Semantic module is not deployed.
SELECT c.product_id
     , c.product_name
     , c.product_domain
     , c.product_version
     , c.product_description
     , c.product_status
     , c.contact_name
     , c.contact_email
     , c.owner_team
     , c.owner_name
     , c.owner_email
     , c.technical_contact_name
     , c.technical_contact_email
     , c.approved_entrypoint
     , c.approved_access_mode
     , c.contract_uri
     , c.semantic_uri
     , c.quality_uri
     , c.lineage_uri
     , c.policy_uri
     , c.glossary_uri
     , c.query_cookbook_uri
     , c.version_from_dts
FROM governance.data_product_catalogue AS c
WHERE c.product_id = :product_id;

SELECT i.entity_name
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
