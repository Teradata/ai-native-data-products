-- Validation: trust-map area table (Teradata). Binding of the area record in design/patterns/validation.md §3.2.
-- One row per run per area: the per-area picture a consumer reads before using that area.
-- Operational evidence in the Observability module; append-only (EVENT_APPEND_ONLY).
-- {db} is a generic tag bound by object-placement, e.g. {Product}_Observability.

CREATE MULTISET TABLE {db}.validation_area
(
    -- Parentage: the run this entry belongs to ({db}.validation_run)
    product_prefix VARCHAR(128) CHARACTER SET LATIN NOT NULL,
    producer_id VARCHAR(64) CHARACTER SET LATIN NOT NULL,
    run_id VARCHAR(64) CHARACTER SET LATIN NOT NULL,

    -- The area (§4.1)
    scope_kind VARCHAR(16) CHARACTER SET LATIN NOT NULL
        CHECK (scope_kind IN ('MODULE', 'ENTITY', 'PATTERN', 'CAPABILITY', 'PRODUCT')),
    scope_id VARCHAR(128) CHARACTER SET LATIN NOT NULL,

    -- Coverage: what the profile defines here, and what actually ran (§4.2)
    checks_expected INTEGER NOT NULL,
    checks_ran INTEGER NOT NULL,

    -- Outcomes within the area (status axis) and severity counts
    passed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    critical_failure_count INTEGER NOT NULL,
    error_failure_count INTEGER NOT NULL,

    -- Verdict for the area (§4.3): informs use, never withholds it
    area_status VARCHAR(16) CHARACTER SET LATIN NOT NULL
        CHECK (area_status IN ('pass', 'fail', 'partial', 'not-validated', 'no-evidence')),
    confidence VARCHAR(8) CHARACTER SET LATIN NOT NULL
        CHECK (confidence IN ('strong', 'partial', 'weak', 'unknown')),

    -- Guidance: required unless confidence is 'strong' (VAL-17)
    open_gaps VARCHAR(1000) CHARACTER SET UNICODE,
    recommended_action VARCHAR(1000) CHARACTER SET UNICODE,

    -- Inherited from the run, so the latest-per-area projection is deterministic
    completed_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,

    -- Row audit (temporal-lifecycle pattern, EVENT_APPEND_ONLY)
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_prefix, scope_kind, scope_id);

COMMENT ON TABLE {db}.validation_area IS
'Trust map - one append-only row per validation run per area (module, entity, pattern, capability, product): coverage, outcome, confidence, and what would raise it. Read the areas a query touches; nothing here blocks use.';
COMMENT ON COLUMN {db}.validation_area.product_prefix IS 'Product identity the run evaluated; joins to validation_run.';
COMMENT ON COLUMN {db}.validation_area.producer_id IS 'Producing validator; the trust-authoritative producer named in orientation owns the map.';
COMMENT ON COLUMN {db}.validation_area.run_id IS 'Run this entry belongs to; joins to validation_run.run_id.';
COMMENT ON COLUMN {db}.validation_area.scope_kind IS 'What kind of area this entry describes: MODULE, ENTITY, PATTERN, CAPABILITY or PRODUCT.';
COMMENT ON COLUMN {db}.validation_area.scope_id IS 'Identity of the area - module or pattern anchor, qualified entity, capability name, or the product prefix. Taken from the corpus and the Semantic catalogue, never derived from an object name.';
COMMENT ON COLUMN {db}.validation_area.checks_expected IS 'Checks the profile defines for this area; 0 means none is defined, which reads as no-evidence rather than as nothing wrong.';
COMMENT ON COLUMN {db}.validation_area.checks_ran IS 'How many of the expected checks executed in this run; coverage is checks_ran / checks_expected, derived on read.';
COMMENT ON COLUMN {db}.validation_area.passed_count IS 'Checks in this area with status PASSED.';
COMMENT ON COLUMN {db}.validation_area.failed_count IS 'Checks in this area with status FAILED, any severity.';
COMMENT ON COLUMN {db}.validation_area.error_count IS 'Checks in this area that could not execute (status ERROR).';
COMMENT ON COLUMN {db}.validation_area.critical_failure_count IS 'Failed or errored checks in this area at CRITICAL severity.';
COMMENT ON COLUMN {db}.validation_area.error_failure_count IS 'Failed or errored checks in this area at ERROR severity.';
COMMENT ON COLUMN {db}.validation_area.area_status IS 'What happened here: pass, fail, partial (clean but incomplete cover), not-validated (checks defined, none ran), no-evidence (no check defined).';
COMMENT ON COLUMN {db}.validation_area.confidence IS 'How far this entry supports use of the area: strong, partial, weak, unknown. Severity-weighted and coverage-aware; advisory to the consumer, never permission.';
COMMENT ON COLUMN {db}.validation_area.open_gaps IS 'What is uncovered or unproven in this area. Required unless confidence is strong.';
COMMENT ON COLUMN {db}.validation_area.recommended_action IS 'What would raise confidence here - a check to write, a re-run, a metadata backfill, a design decision to settle. Required unless confidence is strong.';
COMMENT ON COLUMN {db}.validation_area.completed_dts IS 'Completion instant inherited from the run, so latest-per-area ordering matches latest-per-run.';
COMMENT ON COLUMN {db}.validation_area.created_dts IS 'When this row was appended.';
COMMENT ON COLUMN {db}.validation_area.updated_dts IS 'When this row was last touched; append-only evidence, so equal to created_dts.';

-- Declares temporal_pattern = EVENT_APPEND_ONLY in the Semantic entity metadata.
-- Apply the comments above as their own step, then collect statistics:
COLLECT STATISTICS
      COLUMN (product_prefix)
    , COLUMN (producer_id)
    , COLUMN (run_id)
    , COLUMN (product_prefix, producer_id)
    , COLUMN (scope_kind, scope_id)
    , COLUMN (product_prefix, scope_kind, scope_id)
    , COLUMN (product_prefix, completed_dts)
ON {db}.validation_area;
