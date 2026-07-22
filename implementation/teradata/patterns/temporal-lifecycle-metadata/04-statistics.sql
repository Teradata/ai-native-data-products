-- Temporal & Lifecycle Metadata — primary index and statistics (Teradata).
-- Binding of design/patterns/temporal-lifecycle-metadata.md §5 invariants 3-4.

-- Primary index: NUPI on the natural key for co-located joins across versions.
-- Where in-schema uniqueness enforcement is preferred:
--   UNIQUE PRIMARY INDEX (agreement_bk, valid_from_dts)
-- otherwise enforce invariants 3-4 in maintenance code plus TLM validation.

-- Statistics: collect after creation and refresh with maintenance.
-- The valid_to_dts = sentinel equality predicate is statistics-friendly:
-- current rows cluster on a single value, so the optimiser estimates
-- current-row selectivity well (a further reason validity bounds are non-null).
COLLECT STATISTICS
      COLUMN (agreement_bk)
    , COLUMN (is_current)
    , COLUMN (valid_from_dts)
    , COLUMN (valid_to_dts)
    , COLUMN (agreement_bk, valid_from_dts)
ON {db}.agreement;
