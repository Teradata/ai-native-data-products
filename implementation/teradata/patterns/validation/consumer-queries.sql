-- Validation — consumer queries (Teradata). Binding of design/patterns/validation.md §8, §10.
-- {db} is a generic tag, e.g. {Product}_Observability. :gate_producer comes from orientation.

-- Product gate check BEFORE analytical use.
-- Rules: a missing gate row means unvalidated (stop for autonomous use); a row past
-- evidence_expires_dts (or older than the applicable window, default 7 days from
-- completed_dts) is stale (treat as agent_use_allowed = 0); never recount the JSON
-- blobs; never proceed on UNTRUSTED.
SELECT v.trust_status
     , v.agent_use_allowed
     , v.completed_dts
     , v.evidence_expires_dts
     , v.critical_failure_count
     , v.error_failure_count
     , v.data_product_trust_score
FROM {db}.validation_latest AS v
WHERE v.product_prefix = :product_prefix
  AND v.producer_id = :gate_producer;

-- All-producer evidence summary (surface disagreements).
SELECT v.producer_id
     , v.producer_version
     , v.source_format
     , v.trust_status
     , v.agent_use_allowed
     , v.completed_dts
     , v.total_checks
     , v.failed_count
FROM {db}.validation_latest AS v
WHERE v.product_prefix = :product_prefix
ORDER BY v.producer_id;

-- Run-history trend (auditors).
SELECT r.producer_id
     , r.completed_dts
     , r.trust_status
     , r.data_product_trust_score
     , r.critical_failure_count
     , r.error_failure_count
     , r.failed_count
FROM {db}.validation_run AS r
WHERE r.product_prefix = :product_prefix
ORDER BY r.completed_dts DESC;
