-- Human-readable bootstrap companion. agent_demo.py follows returned identities
-- dynamically, including trust, field meanings, decisions and a two-hop query.
SELECT * FROM semantic.data_product_registry WHERE product_id='customer360';
SELECT * FROM semantic.data_product_manifest WHERE product_id='customer360';
SELECT resource_role,object_identity,discovery_order FROM semantic.data_product_orientation
WHERE product_id='customer360' ORDER BY discovery_order;
