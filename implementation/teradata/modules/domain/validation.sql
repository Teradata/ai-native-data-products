-- Domain module — Teradata invariant checks.
-- Runnable checks backing the invariants in design/modules/domain.md §8.
-- Each query must return ZERO rows for a conforming deployment.
-- Replace {{ product }} with the data product name before running.

-- ---------------------------------------------------------------------------
-- INV-DOMAIN-001 : every attribute of every entity carries descriptive metadata.
-- MetadataCoverageCheck — any table with uncommented columns is a violation.
-- ---------------------------------------------------------------------------
SELECT TableName,
       COUNT(*) AS total_columns,
       COUNT(*) - SUM(CASE WHEN CommentString IS NOT NULL
                            AND TRIM(CommentString) <> '' THEN 1 ELSE 0 END) AS missing
FROM DBC.ColumnsV
WHERE DatabaseName = '{{ product }}_Domain'
  AND (TableName LIKE '%\_H' ESCAPE '\'
    OR TableName LIKE '%\_R' ESCAPE '\'
    OR TableName LIKE '%\_Keymap' ESCAPE '\')
GROUP BY TableName
HAVING missing > 0
ORDER BY missing DESC;

-- ---------------------------------------------------------------------------
-- INV-DOMAIN-004 : every history entity exposes the identity shape
--                  (a surrogate {entity}_id and a natural {entity}_key).
-- Any _H table missing either identity column is a violation.
-- ---------------------------------------------------------------------------
SELECT t.TableName,
       MAX(CASE WHEN c.ColumnName LIKE '%\_id' ESCAPE '\'  THEN 1 ELSE 0 END) AS has_surrogate,
       MAX(CASE WHEN c.ColumnName LIKE '%\_key' ESCAPE '\' THEN 1 ELSE 0 END) AS has_natural_key
FROM DBC.TablesV t
JOIN DBC.ColumnsV c
  ON c.DatabaseName = t.DatabaseName
 AND c.TableName    = t.TableName
WHERE t.DatabaseName = '{{ product }}_Domain'
  AND t.TableName LIKE '%\_H' ESCAPE '\'
GROUP BY t.TableName
HAVING has_surrogate = 0 OR has_natural_key = 0;

-- ---------------------------------------------------------------------------
-- INV-DOMAIN-002 : current, non-deleted records reachable by a predictable filter.
-- Every _H table must have a {Entity}_Current view.
-- ---------------------------------------------------------------------------
SELECT h.TableName AS history_table
FROM DBC.TablesV h
WHERE h.DatabaseName = '{{ product }}_Domain'
  AND h.TableName LIKE '%\_H' ESCAPE '\'
  AND NOT EXISTS (
        SELECT 1
        FROM DBC.TablesV v
        WHERE v.DatabaseName = h.DatabaseName
          AND v.TableKind = 'V'
          AND v.TableName = SUBSTRING(h.TableName FROM 1 FOR CHARACTER_LENGTH(h.TableName) - 2) || '_Current'
      );

-- ---------------------------------------------------------------------------
-- INV-DOMAIN-003 : surrogate {entity}_id is stable across versions (keymap-sourced).
-- The {entity}_id column on an _H table must NOT be identity-generated.
-- Any identity-generated {entity}_id on an _H table is a violation.
-- ---------------------------------------------------------------------------
SELECT TableName, ColumnName
FROM DBC.ColumnsV
WHERE DatabaseName = '{{ product }}_Domain'
  AND TableName LIKE '%\_H' ESCAPE '\'
  AND ColumnName LIKE '%\_id' ESCAPE '\'
  AND IdColType IS NOT NULL;   -- identity column present where it must not be
