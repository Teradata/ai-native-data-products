-- Temporal & Lifecycle Metadata — access views (Teradata).
-- Binding of design/patterns/temporal-lifecycle-metadata.md §8. Default current
-- surface selects from the governed view, never the base table (TLM-14).

-- Default current access view: authoritative sentinel predicate PLUS the
-- convenience flag (any disagreement is a TLM-10 defect validation catches).
-- Hides valid_to_dts, is_current, deletion metadata, and audit timestamps.
REPLACE VIEW {db}.agreement_current
AS
LOCKING ROW FOR ACCESS
SELECT
      a.agreement_bk
    , a.agreement_status
    , a.premium_amount
    , a.valid_from_dts AS effective_since   -- optional exposure (pattern §8)
FROM {db}.v_agreement AS a
WHERE a.valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND a.is_current = 1
  AND a.is_deleted = 0;

-- Point-in-time (as-of) access uses the half-open predicate:
--   WHERE a.valid_from_dts <= :as_of_dts
--     AND :as_of_dts < a.valid_to_dts
