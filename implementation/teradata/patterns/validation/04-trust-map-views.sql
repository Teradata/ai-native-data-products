-- Validation: trust-map view (Teradata). Binding of the trust map and its consumption contract
-- in design/patterns/validation.md §4, §9, §10, §11.
-- Latest-per-(product, producer, area) projection, with coverage derived on read. The deterministic
-- tie-break (completed_dts DESC, run_id DESC) is part of the contract (VAL-09).
-- A producer publishing no area rows is at wire schema 2.0; its run record projects a single
-- PRODUCT-scope entry here, capped at 'partial' confidence, so the map has one shape everywhere.
-- Staleness (§11) is evaluated per area against the run that actually produced it, not against
-- the producer's latest run: two areas in this map can come from different runs, so evaluating
-- staleness against "the latest run" would grade older evidence by a newer run's clock.
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
    -- Stale evidence reads at 'unknown' whatever it recorded (§11); the run's own declared
    -- expiry wins, else the default 7-day window from the completion this area belongs to.
    , CASE WHEN a.evidence_is_stale = 1 THEN 'unknown' ELSE a.confidence END AS confidence
    , a.confidence AS recorded_confidence
    , a.evidence_is_stale
    , a.open_gaps
    , CASE WHEN a.evidence_is_stale = 1
           THEN 'Evidence has expired; re-run the validator for this area.'
           ELSE a.recommended_action
      END AS recommended_action
    , a.recommended_action AS recorded_recommended_action
    , a.completed_dts
    , 'PUBLISHED' AS map_source
-- The latest run per area is resolved in a derived table: QUALIFY is scoped to its own query
-- block, and nesting it keeps the projection unambiguous across the UNION below. Joined to its
-- own parent run (not the producer's latest run) so staleness reflects the evidence's own age.
FROM (
    SELECT
          la.product_prefix, la.producer_id, la.run_id
        , la.scope_kind, la.scope_id
        , la.checks_expected, la.checks_ran
        , la.passed_count, la.failed_count, la.error_count
        , la.critical_failure_count, la.error_failure_count
        , la.area_status, la.confidence
        , la.open_gaps, la.recommended_action
        , la.completed_dts
        , CASE WHEN COALESCE(r.evidence_expires_dts, la.completed_dts + INTERVAL '7' DAY)
                    < CURRENT_TIMESTAMP(6)
               THEN 1 ELSE 0
          END AS evidence_is_stale
    FROM {db}.validation_area AS la
    INNER JOIN {db}.validation_run AS r
            ON  r.product_prefix = la.product_prefix
            AND r.producer_id    = la.producer_id
            AND r.run_id         = la.run_id
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY la.product_prefix, la.producer_id, la.scope_kind, la.scope_id
        ORDER BY la.completed_dts DESC, la.run_id DESC
    ) = 1
) AS a

UNION ALL

-- Wire schema 2.0 / 1.0 fallback: derive one PRODUCT entry from the run counts (§10), staleness
-- evaluated against this same run since there is only one row to derive it from.
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
    , CASE WHEN COALESCE(v.evidence_expires_dts, v.completed_dts + INTERVAL '7' DAY)
                < CURRENT_TIMESTAMP(6)                           THEN 'unknown'
           WHEN v.total_checks = 0                               THEN 'unknown'
           WHEN v.critical_failure_count + v.error_failure_count > 0
             OR v.error_count > 0                                THEN 'weak'
           ELSE 'partial'
      END AS confidence
    , CASE WHEN v.total_checks = 0                              THEN 'unknown'
           WHEN v.critical_failure_count + v.error_failure_count > 0
             OR v.error_count > 0                               THEN 'weak'
           ELSE 'partial'
      END AS recorded_confidence
    , CASE WHEN COALESCE(v.evidence_expires_dts, v.completed_dts + INTERVAL '7' DAY)
                < CURRENT_TIMESTAMP(6) THEN 1 ELSE 0
      END AS evidence_is_stale
    , 'Producer publishes no per-area map (wire schema 2.0), so trust is stated for the whole product only and cannot be resolved to the area a query touches.' AS open_gaps
    , CASE WHEN COALESCE(v.evidence_expires_dts, v.completed_dts + INTERVAL '7' DAY)
                < CURRENT_TIMESTAMP(6)
           THEN 'Evidence has expired; re-run the validator for this product.'
           ELSE 'Upgrade the validator to publish validation_area entries at wire schema 2.1.'
      END AS recommended_action
    , 'Upgrade the validator to publish validation_area entries at wire schema 2.1.' AS recorded_recommended_action
    , v.completed_dts
    , 'DERIVED' AS map_source
FROM {db}.validation_latest AS v
-- Scoped to explicit legacy versions (never a lexical '< 2.1', which breaks on a future major
-- version) and to THIS run: a malformed 2.1 run that published no area rows must fail VAL-18,
-- not be quietly re-dressed as a legacy product. An older producer's historical 2.1 area rows
-- do not suppress the fallback for a current 2.0 run from the same producer, because the
-- existence check is scoped to v.run_id, not to the producer as a whole.
WHERE v.payload_schema_version IN ('1.0', '2.0')
  AND NOT EXISTS (
    SELECT 1
    FROM {db}.validation_area AS a
    WHERE a.product_prefix = v.product_prefix
      AND a.producer_id    = v.producer_id
      AND a.run_id         = v.run_id
);

COMMENT ON VIEW {db}.validation_trust_map IS
'Trust map - latest entry per product, producer and area; coverage and staleness derived on read against the evidence''s own run. Read the areas a query touches, proceed, and disclose confidence and gaps. Nothing here withholds use.';

-- The authoritative map is the set of rows whose producer_id matches the trust-authoritative
-- producer designated in the product's orientation metadata; other producers' rows are evidence.
-- Absent a designation, take the most cautious entry per area across producers and say so
-- (see consumer-queries.sql).
