-- Validation: consumer queries (Teradata). Binding of the consumption contract, trust authority,
-- and staleness rules in design/patterns/validation.md §9, §11.
-- {db} is a generic tag, e.g. {Product}_Observability. :trust_producer comes from orientation
-- (trust_authoritative_producer; gate_authoritative_producer is the legacy spelling).
--
-- Nothing below withholds use of the product. The map says how far to trust each area and what
-- would raise it; the consumer proceeds and reports what it read (§9: read, select, proceed, disclose).

-- 1. The areas this query plan touches, read BEFORE analytical use.
-- :scope_keys is the set of 'KIND:id' keys the plan reaches - the modules, entities, patterns and
-- capabilities behind the objects resolved through AccessObject ('MODULE:domain',
-- 'ENTITY:domain.Ticket'). Concatenated rather than a two-column IN list, which Teradata does not
-- take as a literal row constructor. Take the narrowest entry that covers each.
-- Rules: a row missing for an area means no-evidence / unknown, not sound;
-- a row whose evidence is stale reads at confidence 'unknown' whatever it recorded (query 4);
-- never recount the run's capped JSON blobs.
SELECT m.scope_kind
     , m.scope_id
     , m.area_status
     , m.confidence
     , m.checks_ran
     , m.checks_expected
     , m.coverage_ratio
     , m.critical_failure_count
     , m.error_failure_count
     , m.open_gaps
     , m.recommended_action
     , m.map_source
     , m.completed_dts
FROM {db}.validation_trust_map AS m
WHERE m.product_prefix = :product_prefix
  AND m.producer_id    = :trust_producer
  AND m.scope_kind || ':' || m.scope_id IN (:scope_keys)
ORDER BY CASE m.confidence WHEN 'unknown' THEN 1 WHEN 'weak' THEN 2
                           WHEN 'partial' THEN 3 ELSE 4 END
       , m.scope_kind
       , m.scope_id;

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

-- 4. Evidence age for the authoritative map: staleness downgrades confidence to 'unknown'
-- and is disclosed with its date. It never blocks. The window is the producer's declared
-- expiry, else the product's declared maximum age, else 7 days from completed_dts.
SELECT v.producer_id
     , v.completed_dts
     , v.evidence_expires_dts
     , v.payload_schema_version
     , CASE WHEN v.evidence_expires_dts IS NOT NULL
              AND v.evidence_expires_dts < CURRENT_TIMESTAMP(6)                     THEN 1
            WHEN v.evidence_expires_dts IS NULL
              AND v.completed_dts < CURRENT_TIMESTAMP(6) - INTERVAL '7' DAY          THEN 1
            ELSE 0
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
