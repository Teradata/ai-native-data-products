-- Validation: product-wide comment coverage (Teradata). MetadataCoverageCheck, catalogue-wide.
-- Every row returned is a database, object or column with no COMMENT ON. Zero rows is a pass.
-- {Product} is the product database prefix, e.g. ITSD for ITSD_Domain, ITSD_Semantic.
-- Unlike the per-module INV-DOMAIN-001 query this does not filter by object-name convention, so
-- an object the declared entities never mention is still caught. Covers databases; tables, views,
-- macros, procedures and functions; and the columns of tables and views.
-- Procedure and function arguments are documented in the object's header block, not here.
-- Read-only; running it twice returns the same rows.
SELECT CAST('DATABASE' AS VARCHAR(12)) AS ObjectKind,
       dbs.DatabaseName,
       CAST(NULL AS VARCHAR(128)) AS ObjectName,
       CAST(NULL AS VARCHAR(128)) AS ColumnName
FROM DBC.DatabasesV dbs
WHERE dbs.DatabaseName LIKE '{Product}\_%' ESCAPE '\'
  AND (dbs.CommentString IS NULL OR TRIM(dbs.CommentString) = '')
UNION ALL
SELECT CASE obj.TableKind
         WHEN 'V' THEN 'VIEW'
         WHEN 'M' THEN 'MACRO'
         WHEN 'P' THEN 'PROCEDURE'
         WHEN 'E' THEN 'PROCEDURE'
         WHEN 'F' THEN 'FUNCTION'
         WHEN 'R' THEN 'FUNCTION'
         ELSE 'TABLE'
       END,
       obj.DatabaseName,
       obj.TableName,
       CAST(NULL AS VARCHAR(128))
FROM DBC.TablesV obj
WHERE obj.DatabaseName LIKE '{Product}\_%' ESCAPE '\'
  AND obj.TableKind IN ('T', 'O', 'V', 'M', 'P', 'E', 'F', 'R')
  AND (obj.CommentString IS NULL OR TRIM(obj.CommentString) = '')
UNION ALL
SELECT CAST('COLUMN' AS VARCHAR(12)),
       col.DatabaseName,
       col.TableName,
       col.ColumnName
FROM DBC.ColumnsV col
INNER JOIN DBC.TablesV obj
   ON obj.DatabaseName = col.DatabaseName
  AND obj.TableName = col.TableName
WHERE col.DatabaseName LIKE '{Product}\_%' ESCAPE '\'
  AND obj.TableKind IN ('T', 'O', 'V')
  AND (col.CommentString IS NULL OR TRIM(col.CommentString) = '')
ORDER BY 1, 2, 3, 4;
