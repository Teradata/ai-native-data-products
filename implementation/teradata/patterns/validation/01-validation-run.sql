-- Validation — results table (Teradata). Binding of design/patterns/validation.md §2.
-- Operational evidence in the Observability module; append-only (EVENT_APPEND_ONLY).
-- {db} is a generic tag bound by object-placement, e.g. {Product}_Observability.

CREATE MULTISET TABLE {db}.validation_run
(
    product_prefix VARCHAR(128) CHARACTER SET LATIN NOT NULL,

    -- Producer identity (canonical schema 2.0)
    producer_id VARCHAR(64) CHARACTER SET LATIN NOT NULL,
    producer_version VARCHAR(32) CHARACTER SET LATIN,
    profile_id VARCHAR(64) CHARACTER SET LATIN,
    profile_version VARCHAR(32) CHARACTER SET LATIN,
    source_format VARCHAR(20) CHARACTER SET LATIN NOT NULL DEFAULT 'NATIVE',
    payload_schema_version VARCHAR(8) CHARACTER SET LATIN NOT NULL DEFAULT '2.0',

    -- Run identity
    run_id VARCHAR(64) CHARACTER SET LATIN NOT NULL,
    started_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    completed_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,

    -- Gate result
    trust_status VARCHAR(16) CHARACTER SET LATIN NOT NULL,
    agent_use_allowed BYTEINT NOT NULL CHECK (agent_use_allowed IN (0, 1)),

    -- Check totals (status axis) and gate counts (severity axis)
    total_checks INTEGER NOT NULL,
    passed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    critical_failure_count INTEGER NOT NULL,
    error_failure_count INTEGER NOT NULL,

    -- Scores (null = not assessed)
    data_product_trust_score INTEGER,
    performance_readiness_score INTEGER,
    operational_readiness_score INTEGER,

    -- Detail (capped; true totals in the count columns)
    repair_candidate_count INTEGER NOT NULL,
    failed_checks_json JSON(32000) CHARACTER SET UNICODE,
    repair_candidates_json JSON(32000) CHARACTER SET UNICODE,

    -- Evidence expiry (null = product/consumer default window applies)
    evidence_expires_dts TIMESTAMP(6) WITH TIME ZONE,

    -- Row audit (temporal-lifecycle pattern, EVENT_APPEND_ONLY)
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_prefix, completed_dts);

-- Declares temporal_pattern = EVENT_APPEND_ONLY in the Semantic entity metadata.
-- Column comments required on deploy (RichMetadata). Statistics:
COLLECT STATISTICS
      COLUMN (product_prefix)
    , COLUMN (producer_id)
    , COLUMN (product_prefix, producer_id)
    , COLUMN (product_prefix, completed_dts)
ON {db}.validation_run;
