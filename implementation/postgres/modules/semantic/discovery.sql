CREATE VIEW semantic.column_catalogue AS
SELECT c.schema_name AS container_name, c.table_name, c.column_name,
       c.data_type, c.is_nullable, m.business_description, m.is_pii,
       m.is_sensitive, m.data_classification,
       'postgres_columns' AS declared_type_source,
       CASE WHEN m.business_description IS NOT NULL THEN 'authored' ELSE 'missing' END AS description_source,
       m.business_description IS NOT NULL AS documentation_covered
FROM (SELECT current_database() AS database_name, n.nspname AS schema_name, c.relname AS table_name,
 a.attname AS column_name, pg_catalog.format_type(a.atttypid,a.atttypmod) AS data_type,
 NOT a.attnotnull AS is_nullable, pg_catalog.col_description(c.oid,a.attnum) AS comment
 FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 WHERE a.attnum>0 AND NOT a.attisdropped AND c.relkind IN ('r','v','p')
 AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) c
LEFT JOIN semantic.column_metadata m ON m.container_name=c.schema_name
 AND m.table_name=c.table_name AND m.column_name=c.column_name
WHERE c.database_name=current_database() AND c.schema_name IN
 ('domain','semantic','search','prediction','observability','memory');

CREATE VIEW semantic.data_product_manifest AS
SELECT p.product_id, p.product_version, p.trust_authoritative_producer,
       p.approved_entrypoint, p.approved_access_mode,
       max(o.object_identity) FILTER(WHERE o.resource_role='TRUST_MAP') AS trust_map,
       max(o.object_identity) FILTER(WHERE o.resource_role='MODULE_MAP') AS module_map,
       max(o.object_identity) FILTER(WHERE o.resource_role='OBJECT_CATALOGUE') AS object_catalogue,
       jsonb_agg(jsonb_build_object('role',o.resource_role,'object_identity',o.object_identity,'discovery_order',o.discovery_order,'is_required',o.is_required) ORDER BY o.discovery_order) AS resources
FROM semantic.data_product_registry p JOIN semantic.data_product_orientation o USING(product_id)
GROUP BY p.product_id, p.product_version, p.trust_authoritative_producer, p.approved_entrypoint, p.approved_access_mode;

CREATE VIEW semantic.relationship_edges AS
SELECT source_entity, source_column, target_entity, target_column FROM semantic.table_relationship
UNION ALL
SELECT target_entity, target_column, source_entity, source_column FROM semantic.table_relationship;

-- Cycle-free and bounded; retain full ordered join predicates at every hop.
CREATE VIEW semantic.relationship_paths AS
WITH RECURSIVE paths AS (
 SELECT source_entity, target_entity, ARRAY[source_entity::text,target_entity::text] AS visited,
        source_entity||'.'||source_column||' = '||target_entity||'.'||target_column AS join_path, 1 AS hops
 FROM semantic.relationship_edges
 UNION ALL
 SELECT p.source_entity, e.target_entity, array_append(p.visited,e.target_entity),
        p.join_path||' AND '||e.source_entity||'.'||e.source_column||' = '||e.target_entity||'.'||e.target_column, p.hops+1
 FROM paths p JOIN semantic.relationship_edges e ON p.target_entity=e.source_entity
 WHERE p.hops<4 AND NOT (e.target_entity=ANY(p.visited))
) SELECT source_entity,target_entity,visited,join_path,hops FROM paths;

CREATE VIEW semantic.access_edges AS
SELECT e.source_entity, a.object_identity AS source_object, e.source_column,
       e.target_entity, b.object_identity AS target_object, e.target_column
FROM semantic.relationship_edges e
JOIN semantic.access_object a ON a.represents_entity=e.source_entity AND a.is_agent_consumable AND a.access_role='PASSTHROUGH'
JOIN semantic.access_object b ON b.represents_entity=e.target_entity AND b.is_agent_consumable AND b.access_role='PASSTHROUGH';

CREATE VIEW semantic.access_relationship_paths AS
WITH RECURSIVE paths AS (
 SELECT source_entity,target_entity,source_object,target_object,
        ARRAY[source_entity::text,target_entity::text] AS visited,
        source_object||'.'||source_column||' = '||target_object||'.'||target_column AS join_path, 1 AS hops
 FROM semantic.access_edges
 UNION ALL
 SELECT p.source_entity,e.target_entity,p.source_object,e.target_object,array_append(p.visited,e.target_entity),
        p.join_path||' AND '||e.source_object||'.'||e.source_column||' = '||e.target_object||'.'||e.target_column,p.hops+1
 FROM paths p JOIN semantic.access_edges e ON p.target_entity=e.source_entity
 WHERE p.hops<4 AND NOT (e.target_entity=ANY(p.visited))
) SELECT source_entity,target_entity,source_object,target_object,visited,join_path,hops FROM paths;

CREATE VIEW semantic.lineage_graph AS
SELECT DISTINCT source_table AS source_node, job_name AS target_node, 'produces' AS edge_type
FROM observability.data_lineage WHERE is_active
UNION
SELECT DISTINCT job_name, target_table, 'produces' FROM observability.data_lineage WHERE is_active;

CREATE VIEW semantic.lineage_run_latest AS
SELECT DISTINCT ON (d.lineage_id) d.lineage_id,d.source_table,d.target_table,d.job_name,r.run_dts,r.run_status
FROM observability.data_lineage d LEFT JOIN observability.lineage_run r USING(lineage_id)
WHERE d.is_active
ORDER BY d.lineage_id,r.run_dts DESC,r.lineage_run_id DESC;
