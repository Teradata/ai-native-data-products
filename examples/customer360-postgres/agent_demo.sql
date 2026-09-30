-- Resolve registered surfaces; trust is advisory, and gaps must be disclosed.
SELECT * FROM semantic.data_product_manifest WHERE product_id='customer360';
SELECT * FROM observability.trust_map ORDER BY scope_kind,scope_id;
SELECT * FROM semantic.v_data_product_orientation ORDER BY discovery_order;
SELECT * FROM semantic.access_relationship_paths
 WHERE source_entity='domain.customer' AND target_entity='domain.transaction';
SELECT * FROM domain.v_customer;
SELECT * FROM search.nearest(search.embed('savings'),3);
SELECT * FROM prediction.enriched;
