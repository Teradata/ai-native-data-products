-- Validation — conformance queries (Teradata). Backs the VAL rules (design §13).
-- Each query must return ZERO rows for a conforming deployment.
-- {db} is a generic tag, e.g. {Product}_Observability.

-- VAL-01/02: vocabulary and status/decision agreement
SELECT run_id, producer_id, trust_status, agent_use_allowed
FROM {db}.validation_run
WHERE trust_status NOT IN ('TRUSTED', 'DEGRADED', 'UNTRUSTED')
   OR (trust_status IN ('TRUSTED', 'DEGRADED') AND agent_use_allowed <> 1)
   OR (trust_status = 'UNTRUSTED' AND agent_use_allowed <> 0);

-- VAL-04: check totals reconcile
SELECT run_id, producer_id, total_checks, passed_count, failed_count, error_count
FROM {db}.validation_run
WHERE total_checks <> passed_count + failed_count + error_count;

-- VAL-06: score ranges
SELECT run_id, producer_id
FROM {db}.validation_run
WHERE data_product_trust_score    NOT BETWEEN 0 AND 100
   OR performance_readiness_score NOT BETWEEN 0 AND 100
   OR operational_readiness_score NOT BETWEEN 0 AND 100;

-- VAL-12: producer identity present (canonical schema)
SELECT run_id
FROM {db}.validation_run
WHERE producer_id IS NULL
   OR TRIM(producer_id) = ''
   OR payload_schema_version IS NULL;

-- Deployment: the latest view yields one row per (product, producer)
SELECT product_prefix, producer_id, COUNT(*) AS rows_seen
FROM {db}.validation_latest
GROUP BY product_prefix, producer_id
HAVING COUNT(*) > 1;
