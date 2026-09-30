-- Deterministic demonstration only; no semantic quality claim.
CREATE FUNCTION search.embed(content text) RETURNS double precision[]
LANGUAGE SQL IMMUTABLE STRICT AS $$
 SELECT ARRAY[
 CASE WHEN strpos(lower(content),'savings')>0 THEN 1.0 ELSE 0.1 END,
 CASE WHEN strpos(lower(content),'payments')>0 THEN 1.0 ELSE 0.1 END,
 CASE WHEN strpos(lower(content),'credit')>0 THEN 1.0 ELSE 0.1 END]::double precision[];
$$;

CREATE FUNCTION search.cosine(a double precision[], b double precision[])
RETURNS double precision LANGUAGE SQL IMMUTABLE STRICT AS $$
 SELECT CASE WHEN cardinality(a)=3 AND cardinality(b)=3
 AND array_ndims(a)=1 AND array_ndims(b)=1
 AND array_lower(a,1)=1 AND array_lower(b,1)=1
 AND array_position(a,NULL) IS NULL AND array_position(b,NULL) IS NULL
 AND NOT (a && ARRAY['NaN'::float8,'Infinity'::float8,'-Infinity'::float8])
 AND NOT (b && ARRAY['NaN'::float8,'Infinity'::float8,'-Infinity'::float8])
 THEN (a[1]*b[1]+a[2]*b[2]+a[3]*b[3]) /
 nullif(sqrt(a[1]^2+a[2]^2+a[3]^2)*sqrt(b[1]^2+b[2]^2+b[3]^2),0) END;
$$;

CREATE VIEW search.searchable AS
SELECT e.embedding_id,e.entity_id,e.embedding,e.embedding_model,
 e.embedding_model_version,p.product_name,p.description
FROM search.v_entity_embedding e
JOIN domain.v_product p ON e.entity_kind='PRODUCT' AND e.entity_id=p.product_id;

CREATE FUNCTION search.nearest(query_vector double precision[], k integer)
RETURNS TABLE(entity_id bigint, product_name varchar, description varchar, similarity double precision)
LANGUAGE SQL STABLE AS $$
 SELECT entity_id,product_name,description,search.cosine(embedding,query_vector) AS similarity
 FROM search.searchable WHERE embedding_model='toy-lexical-v1'
 AND search.cosine(embedding,query_vector) IS NOT NULL
 ORDER BY similarity DESC,entity_id LIMIT greatest(0,least(k,100));
$$;

CREATE VIEW prediction.enriched AS
SELECT p.prediction_id,p.entity_id,c.display_name,p.prediction_value,
 p.model_key,p.model_version,p.prediction_dts,p.feature_observation_dts
FROM prediction.v_model_prediction p JOIN domain.v_customer c ON p.entity_id=c.customer_id;

CREATE FUNCTION prediction.training_at(at_dts timestamptz)
RETURNS TABLE(entity_id bigint, segment varchar, value_numeric numeric, observation_dts timestamptz)
LANGUAGE SQL STABLE AS $$
 SELECT f.entity_id,c.segment,f.value_numeric,f.observation_dts
 FROM prediction.at_feature_value(at_dts) f
 JOIN domain.at_customer(at_dts) c ON c.customer_id=f.entity_id
 WHERE f.observation_dts<=at_dts;
$$;
