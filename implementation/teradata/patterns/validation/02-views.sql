-- Validation — latest-run / gate view (Teradata). Binding of design/patterns/validation.md §8.
-- Latest-per-(product, producer) projection. The deterministic tie-break
-- (completed_dts DESC, run_id DESC) is part of the contract (VAL-09).
-- {db} is a generic tag, e.g. {Product}_Observability.

REPLACE VIEW {db}.validation_latest
AS
LOCKING ROW FOR ACCESS
SELECT
      product_prefix
    , producer_id
    , producer_version
    , profile_id
    , profile_version
    , source_format
    , payload_schema_version
    , run_id
    , started_dts
    , completed_dts
    , trust_status
    , agent_use_allowed
    , total_checks
    , passed_count
    , failed_count
    , error_count
    , critical_failure_count
    , error_failure_count
    , data_product_trust_score
    , performance_readiness_score
    , operational_readiness_score
    , repair_candidate_count
    , failed_checks_json
    , repair_candidates_json
    , evidence_expires_dts
FROM {db}.validation_run
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY product_prefix, producer_id
    ORDER BY completed_dts DESC, run_id DESC
) = 1;

-- The product-level gate is the row whose producer_id matches the gate-authoritative
-- producer designated in the product's orientation metadata; other rows are evidence.
