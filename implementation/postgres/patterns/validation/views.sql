CREATE VIEW observability.validation_run_latest AS
SELECT DISTINCT ON (product_prefix,producer_id) * FROM observability.validation_run ORDER BY product_prefix,producer_id,completed_dts DESC,run_id DESC;

-- Authoritative producer and latest PER AREA; newer runs need not cover old areas.
-- No evidence remains visible, and stale evidence cannot retain strong confidence.
CREATE VIEW observability.trust_map_evidence AS
WITH latest_area AS (
 SELECT DISTINCT ON (a.product_prefix,a.producer_id,a.scope_kind,a.scope_id) a.*,r.evidence_expires_dts FROM observability.validation_area a
 JOIN observability.validation_run r USING(product_prefix,producer_id,run_id)
 ORDER BY a.product_prefix,a.producer_id,a.scope_kind,a.scope_id,a.completed_dts DESC,a.run_id DESC
)
SELECT a.product_prefix,a.producer_id,a.run_id,a.scope_kind,a.scope_id,a.area_status,
 CASE WHEN current_timestamp > coalesce(a.evidence_expires_dts,
      a.completed_dts + p.max_evidence_age_days * INTERVAL '1 day') THEN 'unknown' ELSE a.confidence END AS confidence,
 a.checks_expected,a.checks_ran,a.passed_count,a.failed_count,a.error_count,
 a.critical_failure_count,a.error_failure_count,
 a.checks_ran::DOUBLE PRECISION/nullif(a.checks_expected,0) AS coverage,
 CASE WHEN current_timestamp > coalesce(a.evidence_expires_dts,a.completed_dts+p.max_evidence_age_days*INTERVAL '1 day')
      THEN 'Evidence is stale.' ELSE a.open_gaps END AS open_gaps,
 CASE WHEN current_timestamp > coalesce(a.evidence_expires_dts,a.completed_dts+p.max_evidence_age_days*INTERVAL '1 day')
      THEN 'Re-run the validator; disclose unknown confidence.' ELSE a.recommended_action END AS recommended_action,
 a.completed_dts
FROM latest_area a JOIN semantic.data_product_registry p ON p.product_id=a.product_prefix
 AND (p.trust_authoritative_producer=a.producer_id OR nullif(p.trust_authoritative_producer,'') IS NULL)
UNION ALL
SELECT p.product_id,p.trust_authoritative_producer,NULL,'PRODUCT',p.product_id,'no-evidence','unknown',
       0,0,0,0,0,0,0,NULL,'No published area evidence.','Run the validator before reporting confidence.',NULL
FROM semantic.data_product_registry p WHERE NOT EXISTS
 (SELECT 1 FROM latest_area a WHERE a.product_prefix=p.product_id
 AND (a.producer_id=p.trust_authoritative_producer OR nullif(p.trust_authoritative_producer,'') IS NULL));

CREATE VIEW observability.trust_map AS
SELECT DISTINCT ON (e.product_prefix,e.scope_kind,e.scope_id) e.product_prefix,e.producer_id,e.run_id,e.scope_kind,e.scope_id,e.area_status,e.confidence,
       e.checks_expected,e.checks_ran,e.passed_count,e.failed_count,e.error_count,
       e.critical_failure_count,e.error_failure_count,e.coverage,e.open_gaps,
       CASE WHEN nullif(p.trust_authoritative_producer,'') IS NULL
            THEN 'No designated producer: cautious per-area fallback. '||coalesce(e.recommended_action,'Designate one producer.')
            ELSE e.recommended_action END AS recommended_action,e.completed_dts
FROM observability.trust_map_evidence e JOIN semantic.data_product_registry p ON p.product_id=e.product_prefix
ORDER BY e.product_prefix,e.scope_kind,e.scope_id,
 CASE e.confidence WHEN 'unknown' THEN 0 WHEN 'weak' THEN 1 WHEN 'partial' THEN 2 ELSE 3 END,
 e.completed_dts DESC,e.run_id DESC,e.producer_id;
