-- Validation: consumer queries (Teradata). Binding of the consumption contract, trust authority,
-- and staleness rules in design/patterns/validation.md §9, §11.
-- {db} is a generic tag, e.g. {Product}_Observability. :trust_producer comes from orientation
-- (trust_authoritative_producer; gate_authoritative_producer is the legacy spelling).
--
-- Nothing below withholds use of the product. The map says how far to trust each area and what
-- would raise it; the consumer proceeds and reports what it read (§9: read, select, proceed, disclose).

-- 1. The areas this query plan touches, read BEFORE analytical use.
-- requested_validation_scope is a request-scoped relation (e.g. a volatile table) the caller
-- populates with one (scope_kind, scope_id) row per module, entity, pattern or capability the
-- plan reaches - the areas behind the objects resolved through AccessObject
-- (('MODULE', 'domain'), ('ENTITY', 'domain.Ticket')). Kept as two columns rather than a
-- concatenated 'KIND:id' key so the join uses real column statistics, not a computed string.
-- Driving FROM the caller's own request (LEFT OUTER JOIN to the map, not the map filtered by the
-- request) is what guarantees every requested area gets a row: a plain filter silently drops a
-- scope the map has no entry for, which is the exact failure mode the trust map exists to remove.
-- Rules: a row missing for an area means no-evidence / unknown, not sound;
-- a row whose evidence is stale reads at confidence 'unknown' whatever it recorded;
-- never recount the run's capped JSON blobs.
SELECT s.scope_kind
     , s.scope_id
     , COALESCE(m.area_status, 'no-evidence') AS area_status
     , COALESCE(m.confidence, 'unknown') AS confidence
     , m.recorded_confidence
     , COALESCE(m.evidence_is_stale, 0) AS evidence_is_stale
     , m.checks_ran
     , m.checks_expected
     , m.coverage_ratio
     , m.critical_failure_count
     , m.error_failure_count
     , COALESCE(m.open_gaps,
           'No trust-map entry was published for an area used by this query.') AS open_gaps
     , COALESCE(m.recommended_action,
           'Add this area to the validator profile and publish a validation_area entry.') AS recommended_action
     , COALESCE(m.map_source, 'NONE') AS map_source
     , m.completed_dts
FROM requested_validation_scope AS s
LEFT OUTER JOIN {db}.validation_trust_map AS m
             ON  m.product_prefix = :product_prefix
             AND m.producer_id    = :trust_producer
             AND m.scope_kind     = s.scope_kind
             AND m.scope_id       = s.scope_id
ORDER BY CASE COALESCE(m.confidence, 'unknown')
              WHEN 'unknown' THEN 1 WHEN 'weak' THEN 2 WHEN 'partial' THEN 3 ELSE 4 END
       , s.scope_kind
       , s.scope_id;

-- 2. The whole map, for orientation and for reporting where a product is strong and where it is not.
SELECT m.scope_kind
     , m.scope_id
     , m.area_status
     , m.confidence
     , m.coverage_ratio
     , m.open_gaps
     , m.recommended_action
FROM {db}.validation_trust_map AS m
WHERE m.product_prefix = :product_prefix
  AND m.producer_id    = :trust_producer
ORDER BY m.scope_kind, m.scope_id;

-- 3. No designated producer: take the most cautious entry per area, and say that you did.
-- (§9 trust authority. A product with two maps and no designation has not said which it means.)
SELECT m.scope_kind
     , m.scope_id
     , MIN(CASE m.confidence WHEN 'unknown' THEN 1 WHEN 'weak' THEN 2
                             WHEN 'partial' THEN 3 ELSE 4 END) AS lowest_confidence_rank
     , COUNT(DISTINCT m.confidence) AS producers_disagree
FROM {db}.validation_trust_map AS m
WHERE m.product_prefix = :product_prefix
GROUP BY m.scope_kind, m.scope_id
ORDER BY lowest_confidence_rank, m.scope_kind, m.scope_id;

-- 4. Evidence age for the producer's most recent run, for run-history context only. Staleness
-- that governs what a consumer may say about an AREA is already folded into query 1/2's
-- confidence and evidence_is_stale columns, evaluated against each area's own run (§11) - do not
-- recompute it from this producer-latest row, which can be newer than the area actually read.
SELECT v.producer_id
     , v.completed_dts
     , v.evidence_expires_dts
     , v.payload_schema_version
     , CASE WHEN COALESCE(v.evidence_expires_dts, v.completed_dts + INTERVAL '7' DAY)
                < CURRENT_TIMESTAMP(6) THEN 1 ELSE 0
       END AS evidence_is_stale
FROM {db}.validation_latest AS v
WHERE v.product_prefix = :product_prefix
  AND v.producer_id    = :trust_producer;

-- 5. Advisory product summary (§4.4). A first glance, not permission: agent_use_allowed is
-- deprecated at schema 2.1 and no consumer branches on it.
SELECT v.trust_status
     , v.data_product_trust_score
     , v.performance_readiness_score
     , v.operational_readiness_score
     , v.total_checks
     , v.failed_count
     , v.error_count
     , v.completed_dts
FROM {db}.validation_latest AS v
WHERE v.product_prefix = :product_prefix
  AND v.producer_id    = :trust_producer;

-- 6. Failed-check detail for an area a consumer intends to use, so the disclosure names the defect
-- rather than only its severity. The capped blob carries scope_kind / scope_id per item (schema 2.1).
SELECT v.producer_id
     , v.completed_dts
     , v.failed_checks_json
     , v.repair_candidate_count
FROM {db}.validation_latest AS v
WHERE v.product_prefix = :product_prefix
  AND v.producer_id    = :trust_producer;

-- 7. Per-area trend (auditors, and product owners closing coverage gaps).
SELECT a.scope_kind
     , a.scope_id
     , a.completed_dts
     , a.area_status
     , a.confidence
     , a.checks_ran
     , a.checks_expected
FROM {db}.validation_area AS a
WHERE a.product_prefix = :product_prefix
  AND a.producer_id    = :trust_producer
ORDER BY a.scope_kind, a.scope_id, a.completed_dts DESC;

-- 8. Run-history trend (auditors).
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
