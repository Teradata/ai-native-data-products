-- Validation: conformance queries (Teradata). Backs the VAL conformance rules.
-- Each query must return ZERO rows for a conforming deployment.
-- {db} is a generic tag, e.g. {Product}_Observability.

-- VAL-01: status vocabulary
SELECT run_id, producer_id, trust_status
FROM {db}.validation_run
WHERE trust_status NOT IN ('TRUSTED', 'DEGRADED', 'UNTRUSTED');

-- VAL-02: agent_use_allowed is deprecated at 2.1 and published as go. It is retained only so a
-- 2.0 reader still parses the record; consumers branch on the trust map, never on this field.
-- "At the canonical schema or later" is expressed by excluding the registered legacy versions,
-- never as a lexical comparison against '2.1': payload_schema_version is a string, so '10.0'
-- sorts below '2.1' and a future major version would silently fall out of every check below.
-- The list is the same one the trust map's legacy fallback uses (04-trust-map-views.sql), so a
-- newly registered legacy binding is added in exactly two places.
SELECT run_id, producer_id, payload_schema_version, agent_use_allowed
FROM {db}.validation_run
WHERE payload_schema_version NOT IN ('1.0', '2.0')
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

-- VAL-09: an area's completed_dts is inherited from its parent run, so latest-per-area ordering
-- matches latest-per-run and the trust map's staleness join (04-trust-map-views.sql) is sound.
SELECT a.run_id, a.producer_id, a.scope_kind, a.scope_id, a.completed_dts, r.completed_dts AS run_completed_dts
FROM {db}.validation_area AS a
INNER JOIN {db}.validation_run AS r
        ON  r.product_prefix = a.product_prefix
        AND r.producer_id    = a.producer_id
        AND r.run_id         = a.run_id
WHERE a.completed_dts <> r.completed_dts;

-- VAL-12: producer identity present (canonical schema)
SELECT run_id
FROM {db}.validation_run
WHERE producer_id IS NULL
   OR TRIM(producer_id) = ''
   OR payload_schema_version IS NULL;

-- VAL-14: area vocabularies. The CHECK constraints on validation_area enforce the three closed
-- vocabularies at insert; this catches a scope_id that names nothing, which no constraint can.
-- Resolvable here for PRODUCT, MODULE and ENTITY against deployed catalogue metadata; PATTERN
-- and CAPABILITY have no such catalogue and are a producer build-time assertion instead (§14).
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

-- VAL-14 (MODULE scope resolves): every module-scoped area names a module the product actually
-- deployed. {sem} is the product's Semantic container, e.g. {Product}_Semantic.
SELECT a.run_id, a.scope_kind, a.scope_id
FROM {db}.validation_area AS a
WHERE a.scope_kind = 'MODULE'
  AND NOT EXISTS (
        SELECT 1
        FROM {sem}.data_product_map AS dm
        WHERE dm.is_active = 1
          AND UPPER(dm.module_name) = UPPER(a.scope_id)
      );

-- VAL-14 (PRODUCT scope resolves): a PRODUCT-scoped area names this product, not another one.
SELECT a.run_id, a.scope_kind, a.scope_id
FROM {db}.validation_area AS a
WHERE a.scope_kind = 'PRODUCT'
  AND a.scope_id <> a.product_prefix;

-- VAL-14 (PATTERN, CAPABILITY): these vocabularies have no deployed catalogue a consumer can
-- resolve against, so a typo'd scope_id (e.g. 'CAPABILITY:reposrting') is caught only by the
-- producer's own build-time assertion against its validator profile - not runtime SQL, which
-- cannot see the profile. See design/patterns/validation.md §14 (VAL-14) for the split.

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

-- VAL-18 (every canonical-schema run publishes at least one area entry - not only a run with
-- failures. Without this, a malformed 2.1 producer that publishes zero area rows is silently
-- re-dressed as a legacy product by the trust map's schema 2.0/1.0 fallback
-- (04-trust-map-views.sql).)
SELECT r.run_id, r.producer_id, r.payload_schema_version
FROM {db}.validation_run AS r
WHERE r.payload_schema_version NOT IN ('1.0', '2.0')
  AND NOT EXISTS (
        SELECT 1
        FROM {db}.validation_area AS a
        WHERE a.product_prefix = r.product_prefix
          AND a.producer_id    = r.producer_id
          AND a.run_id         = r.run_id
      );

-- VAL-18 (a run that found failures publishes somewhere for them to land)
SELECT r.run_id, r.producer_id, r.failed_count, r.error_count
FROM {db}.validation_run AS r
WHERE r.payload_schema_version NOT IN ('1.0', '2.0')
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
