-- Validation: conformance queries (Teradata). Backs the VAL conformance rules.
-- Each query must return ZERO rows for a conforming deployment.
-- {db} is a generic tag, e.g. {Product}_Observability.

-- VAL-01: status vocabulary
SELECT run_id, producer_id, trust_status
FROM {db}.validation_run
WHERE trust_status NOT IN ('TRUSTED', 'DEGRADED', 'UNTRUSTED');

-- VAL-02: agent_use_allowed is deprecated at 2.1 and published as go. It is retained only so a
-- 2.0 reader still parses the record; consumers branch on the trust map, never on this field.
SELECT run_id, producer_id, payload_schema_version, agent_use_allowed
FROM {db}.validation_run
WHERE payload_schema_version >= '2.1'
  AND agent_use_allowed <> 1;

-- VAL-04: run check totals reconcile
SELECT run_id, producer_id, total_checks, passed_count, failed_count, error_count
FROM {db}.validation_run
WHERE total_checks <> passed_count + failed_count + error_count;

-- VAL-05: severity counts cannot exceed the failures they classify, on either relation
SELECT run_id, producer_id, critical_failure_count, error_failure_count, failed_count, error_count
FROM {db}.validation_run
WHERE critical_failure_count + error_failure_count > failed_count + error_count;

SELECT run_id, producer_id, scope_kind, scope_id
FROM {db}.validation_area
WHERE critical_failure_count + error_failure_count > failed_count + error_count;

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

-- VAL-14: area vocabularies. The CHECK constraints on validation_area enforce the three closed
-- vocabularies at insert; this catches a scope_id that names nothing, which no constraint can.
SELECT a.run_id, a.scope_kind, a.scope_id
FROM {db}.validation_area AS a
WHERE TRIM(a.scope_id) = '';

-- VAL-14 (ENTITY scope is module-qualified, e.g. 'domain.Ticket')
SELECT a.run_id, a.scope_kind, a.scope_id
FROM {db}.validation_area AS a
WHERE a.scope_kind = 'ENTITY'
  AND POSITION('.' IN a.scope_id) = 0;

-- VAL-14 (ENTITY scope resolves): every entity-scoped area names a catalogued entity.
-- {sem} is the product's Semantic container, e.g. {Product}_Semantic.
SELECT a.run_id, a.scope_kind, a.scope_id
FROM {db}.validation_area AS a
WHERE a.scope_kind = 'ENTITY'
  AND POSITION('.' IN a.scope_id) > 0
  AND NOT EXISTS (
        SELECT 1
        FROM {sem}.entity_metadata AS e
        WHERE UPPER(e.module_name) = UPPER(SUBSTRING(a.scope_id FROM 1
                                            FOR POSITION('.' IN a.scope_id) - 1))
          AND UPPER(e.entity_name) = UPPER(SUBSTRING(a.scope_id FROM
                                            POSITION('.' IN a.scope_id) + 1))
      );

-- VAL-15: per-area counts reconcile, and coverage cannot exceed what the profile defines
SELECT run_id, producer_id, scope_kind, scope_id, checks_ran, checks_expected
FROM {db}.validation_area
WHERE checks_ran <> passed_count + failed_count + error_count
   OR checks_ran > checks_expected
   OR checks_ran < 0
   OR checks_expected < 0;

-- VAL-16: status and confidence agree with coverage. A pass claims full coverage of checks that
-- ran; an area nothing reached is 'unknown', never 'fine'.
SELECT run_id, producer_id, scope_kind, scope_id, area_status, confidence, checks_ran, checks_expected
FROM {db}.validation_area
WHERE (area_status = 'pass'         AND (checks_ran = 0 OR checks_ran <> checks_expected))
   OR (confidence  = 'strong'      AND (checks_ran = 0 OR checks_ran <> checks_expected
                                         OR failed_count + error_count > 0))
   OR (area_status = 'no-evidence'   AND (checks_expected <> 0 OR confidence <> 'unknown'))
   OR (area_status = 'not-validated' AND (checks_ran <> 0 OR confidence <> 'unknown'))
   OR (area_status = 'fail'          AND failed_count + error_count = 0)
   OR (failed_count + error_count > 0 AND area_status <> 'fail')
   OR (critical_failure_count + error_failure_count > 0 AND confidence NOT IN ('weak', 'unknown'))
   -- VAL-03: coverage below half is 'weak' by default, and the default is never loosened
   OR (confidence = 'partial' AND checks_expected > 0 AND checks_ran * 2 < checks_expected);

-- VAL-17: every entry below 'strong' says what is missing and what would raise it
SELECT run_id, producer_id, scope_kind, scope_id, confidence
FROM {db}.validation_area
WHERE confidence <> 'strong'
  AND (open_gaps IS NULL OR TRIM(open_gaps) = ''
       OR recommended_action IS NULL OR TRIM(recommended_action) = '');

-- VAL-18: every area entry belongs to a published run (the converse - every area the profile
-- covers has an entry - is a producer-side assertion; a consumer cannot see the profile).
SELECT a.run_id, a.producer_id, a.scope_kind, a.scope_id
FROM {db}.validation_area AS a
WHERE NOT EXISTS (
        SELECT 1
        FROM {db}.validation_run AS r
        WHERE r.product_prefix = a.product_prefix
          AND r.producer_id    = a.producer_id
          AND r.run_id         = a.run_id
      );

-- VAL-18 (a run that found failures publishes somewhere for them to land)
SELECT r.run_id, r.producer_id, r.failed_count, r.error_count
FROM {db}.validation_run AS r
WHERE r.payload_schema_version >= '2.1'
  AND r.failed_count + r.error_count > 0
  AND NOT EXISTS (
        SELECT 1
        FROM {db}.validation_area AS a
        WHERE a.product_prefix = r.product_prefix
          AND a.producer_id    = r.producer_id
          AND a.run_id         = r.run_id
          AND a.area_status    = 'fail'
      );

-- Deployment: the latest views yield one row per (product, producer) and per area
SELECT product_prefix, producer_id, COUNT(*) AS rows_seen
FROM {db}.validation_latest
GROUP BY product_prefix, producer_id
HAVING COUNT(*) > 1;

SELECT product_prefix, producer_id, scope_kind, scope_id, COUNT(*) AS rows_seen
FROM {db}.validation_trust_map
GROUP BY product_prefix, producer_id, scope_kind, scope_id
HAVING COUNT(*) > 1;
