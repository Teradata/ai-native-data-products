-- Validation: trust-map view (Teradata). Binding of the trust map and its consumption contract
-- in design/patterns/validation.md §4, §9, §10.
-- Latest-per-(product, producer, area) projection, with coverage derived on read. The deterministic
-- tie-break (completed_dts DESC, run_id DESC) is part of the contract (VAL-09).
-- A producer publishing no area rows is at wire schema 2.0; its run record projects a single
-- PRODUCT-scope entry here, capped at 'partial' confidence, so the map has one shape everywhere.
-- {db} is a generic tag, e.g. {Product}_Observability.

REPLACE VIEW {db}.validation_trust_map
AS
LOCKING ROW FOR ACCESS
SELECT
      a.product_prefix
    , a.producer_id
    , a.run_id
    , a.scope_kind
    , a.scope_id
    , a.checks_expected
    , a.checks_ran
    , CASE WHEN a.checks_expected > 0
           THEN CAST(a.checks_ran AS DECIMAL(9, 4)) / a.checks_expected
      END AS coverage_ratio
    , a.passed_count
    , a.failed_count
    , a.error_count
    , a.critical_failure_count
    , a.error_failure_count
    , a.area_status
    , a.confidence
    , a.open_gaps
    , a.recommended_action
    , a.completed_dts
    , 'PUBLISHED' AS map_source
-- The latest run per area is resolved in a derived table: QUALIFY is scoped to its own query
-- block, and nesting it keeps the projection unambiguous across the UNION below.
FROM (
    SELECT
          product_prefix, producer_id, run_id
        , scope_kind, scope_id
        , checks_expected, checks_ran
        , passed_count, failed_count, error_count
        , critical_failure_count, error_failure_count
        , area_status, confidence
        , open_gaps, recommended_action
        , completed_dts
    FROM {db}.validation_area
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY product_prefix, producer_id, scope_kind, scope_id
        ORDER BY completed_dts DESC, run_id DESC
    ) = 1
) AS a

UNION ALL

-- Wire schema 2.0 / 1.0 fallback: derive one PRODUCT entry from the run counts (§10).
SELECT
      v.product_prefix
    , v.producer_id
    , v.run_id
    , 'PRODUCT' AS scope_kind
    , v.product_prefix AS scope_id
    , v.total_checks AS checks_expected
    , v.total_checks AS checks_ran
    , CASE WHEN v.total_checks > 0 THEN CAST(1 AS DECIMAL(9, 4)) END AS coverage_ratio
    , v.passed_count
    , v.failed_count
    , v.error_count
    , v.critical_failure_count
    , v.error_failure_count
    , CASE WHEN v.total_checks = 0                              THEN 'no-evidence'
           WHEN v.failed_count + v.error_count > 0              THEN 'fail'
           ELSE 'pass'
      END AS area_status
      -- Capped at 'partial': a run-level pass says nothing about which areas it covered.
    , CASE WHEN v.total_checks = 0                              THEN 'unknown'
           WHEN v.critical_failure_count + v.error_failure_count > 0
             OR v.error_count > 0                               THEN 'weak'
           ELSE 'partial'
      END AS confidence
    , 'Producer publishes no per-area map (wire schema 2.0), so trust is stated for the whole product only and cannot be resolved to the area a query touches.' AS open_gaps
    , 'Upgrade the validator to publish validation_area entries at wire schema 2.1.' AS recommended_action
    , v.completed_dts
    , 'DERIVED' AS map_source
FROM {db}.validation_latest AS v
WHERE NOT EXISTS (
    SELECT 1
    FROM {db}.validation_area AS a
    WHERE a.product_prefix = v.product_prefix
      AND a.producer_id    = v.producer_id
);

COMMENT ON VIEW {db}.validation_trust_map IS
'Trust map - latest entry per product, producer and area, with coverage derived on read. Read the areas a query touches, proceed, and disclose their confidence and gaps. Nothing here withholds use of the product.';

-- The authoritative map is the set of rows whose producer_id matches the trust-authoritative
-- producer designated in the product's orientation metadata; other producers' rows are evidence.
-- Absent a designation, take the most cautious entry per area across producers and say so
-- (see consumer-queries.sql).
