-- Offline lexical demonstration, identical source/query encoder. Not an ML model.
CREATE MACRO search.embed(content) AS [
    CASE WHEN contains(lower(content), 'savings') THEN 1.0 ELSE 0.1 END,
    CASE WHEN contains(lower(content), 'payments') THEN 1.0 ELSE 0.1 END,
    CASE WHEN contains(lower(content), 'credit') THEN 1.0 ELSE 0.1 END
]::FLOAT[3];

CREATE VIEW search.searchable AS
SELECT e.embedding_id, e.entity_id, e.embedding, e.embedding_model,
       e.embedding_model_version, p.product_name, p.description
FROM search.v_entity_embedding e
JOIN domain.v_product p ON e.entity_kind='PRODUCT' AND e.entity_id=p.product_id;

CREATE MACRO search.nearest(query_vector, k) AS TABLE
SELECT entity_id, product_name, description,
       array_cosine_similarity(embedding, query_vector::FLOAT[3]) AS similarity
FROM search.searchable
WHERE embedding_model='toy-lexical-v1'
ORDER BY similarity DESC, entity_id LIMIT k;

CREATE VIEW prediction.enriched AS
SELECT p.prediction_id, p.entity_id, c.display_name, p.prediction_value,
       p.model_key, p.model_version, p.prediction_dts, p.feature_observation_dts
FROM prediction.v_model_prediction p JOIN domain.v_customer c ON p.entity_id=c.customer_id;

CREATE MACRO prediction.training_at(at_dts) AS TABLE
SELECT f.entity_id, c.segment, f.value_numeric, f.observation_dts
FROM prediction.at_feature_value(at_dts) f
JOIN domain.at_customer(at_dts) c ON c.customer_id=f.entity_id
WHERE f.observation_dts <= at_dts::TIMESTAMPTZ;
