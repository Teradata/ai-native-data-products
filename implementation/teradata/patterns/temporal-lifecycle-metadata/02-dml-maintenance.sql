-- Temporal & Lifecycle Metadata — DML maintenance patterns (Teradata).
-- Binding of design/patterns/temporal-lifecycle-metadata.md §5.2 invariants.
-- {db}, {entity}, {natural_key} are generic tags; :params are runtime values.

-- 6.1 Standard version change (close + insert, one transaction).
-- Both statements commit or roll back together (invariant 7). The successor's
-- valid_from_dts equals the predecessor's new valid_to_dts (no gap, no overlap).
BT;

UPDATE {db}.agreement
SET   valid_to_dts = :event_dts
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE agreement_bk = :agreement_bk
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  -- Change detection: close only when the incoming version differs (invariant 6)
  AND (agreement_status <> :new_status OR premium_amount <> :new_premium);

INSERT INTO {db}.agreement
      (agreement_sk, agreement_bk, agreement_status, premium_amount, valid_from_dts)
SELECT :new_sk, :agreement_bk, :new_status, :new_premium, :event_dts
WHERE NOT EXISTS (
    SELECT 1 FROM {db}.agreement AS a
    WHERE a.agreement_bk = :agreement_bk
      AND a.valid_from_dts = :event_dts
);   -- Idempotent replay: re-running the same input inserts nothing (invariant 8)

ET;

-- 6.2 Logical deletion — a NEW current version, never update-in-place (invariant 10).
BT;

UPDATE {db}.agreement
SET valid_to_dts = :deletion_dts, is_current = 0, updated_dts = CURRENT_TIMESTAMP(6)
WHERE agreement_bk = :agreement_bk
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00';

INSERT INTO {db}.agreement
      (agreement_sk, agreement_bk, agreement_status, premium_amount
     , valid_from_dts, is_deleted, deleted_dts)
VALUES (:new_sk, :agreement_bk, :last_status, :last_premium
     , :deletion_dts, 1, :deletion_dts);

ET;
-- Restoration inserts a further successor with is_deleted = 0.

-- 6.3 Late-arriving change (invariant 9): place the change at its actual effective
-- instant and split the covering period — close the covering version at :late_dts,
-- insert the late version [:late_dts, original_valid_to_dts), preserving is_current
-- on whichever row now holds the sentinel. Same close + insert transaction shape as 6.1.
