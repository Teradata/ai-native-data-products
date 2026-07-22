-- Temporal & Lifecycle Metadata — conformance queries (Teradata).
-- Implementable checks for the pattern's conformance rules (design §9).
-- ColumnType codes: SZ = TIMESTAMP WITH TIME ZONE, TS = TIMESTAMP, I1 = BYTEINT.
-- Each catalogue/data query must return ZERO rows for a conforming deployment.
-- :product_db_pattern e.g. '{Product}\_%' ; parameterise data checks per SCD2 table.

-- §1  TLM-04: prohibited generic names on product objects
SELECT c.DatabaseName, c.TableName, c.ColumnName
FROM DBC.ColumnsV AS c
WHERE c.DatabaseName LIKE :product_db_pattern
  AND LOWER(TRIM(c.ColumnName)) IN
      ('created_at','created_timestamp','created_dt','updated_at','updated_timestamp',
       'valid_from','valid_to','effective_from','effective_to','effective_date',
       'expiration_date','start_timestamp','end_timestamp','deleted_flag','active_ind');

-- §2  TLM-05: temporal columns missing WITH TIME ZONE or microsecond precision
SELECT c.DatabaseName, c.TableName, c.ColumnName, c.ColumnType
FROM DBC.ColumnsV AS c
WHERE c.DatabaseName LIKE :product_db_pattern
  AND LOWER(TRIM(c.ColumnName)) LIKE '%!_dts' ESCAPE '!'
  AND (c.ColumnType <> 'SZ' OR c.DecimalFractionalDigits <> 6);

-- §3  TLM-06: flags that are not BYTEINT NOT NULL
SELECT c.DatabaseName, c.TableName, c.ColumnName, c.ColumnType, c.Nullable
FROM DBC.ColumnsV AS c
WHERE c.DatabaseName LIKE :product_db_pattern
  AND LOWER(TRIM(c.ColumnName)) LIKE 'is!_%' ESCAPE '!'
  AND (c.ColumnType <> 'I1' OR c.Nullable = 'Y');

-- §4  Data-level invariants (parameterise per SCD2 table; example: agreement)

-- TLM-09: more than one current row per natural key
SELECT agreement_bk, COUNT(*) AS current_rows
FROM {db}.v_agreement
WHERE valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
GROUP BY agreement_bk
HAVING COUNT(*) > 1;

-- TLM-10: flag / validity disagreement
SELECT agreement_bk, valid_from_dts, is_current, valid_to_dts
FROM {db}.v_agreement
WHERE (is_current = 1) <> (valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00');

-- TLM-08: overlapping periods per natural key
SELECT agreement_bk, valid_from_dts, valid_to_dts, next_from
FROM (
    SELECT agreement_bk, valid_from_dts, valid_to_dts,
           MIN(valid_from_dts) OVER (
               PARTITION BY agreement_bk ORDER BY valid_from_dts
               ROWS BETWEEN 1 FOLLOWING AND 1 FOLLOWING
           ) AS next_from
    FROM {db}.v_agreement
) AS t
WHERE next_from IS NOT NULL AND next_from < valid_to_dts;

-- TLM-11: deletion without deletion time
SELECT agreement_bk, valid_from_dts
FROM {db}.v_agreement
WHERE is_deleted = 1 AND deleted_dts IS NULL;
