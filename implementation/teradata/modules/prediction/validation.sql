-- Prediction module — Teradata invariant checks.
-- Backs design/modules/prediction.md §8. Each query must return ZERO rows for a conforming
-- deployment. Replace {{ product }}; list the module's feature tables where indicated.

-- INV-PRED-001 : engineered features only — no raw Domain-content columns on feature tables.
-- Flags a feature table column whose name looks like a raw copied Domain attribute.
SELECT c.TableName, c.ColumnName
FROM DBC.ColumnsV AS c
WHERE c.DatabaseName = '{{ product }}_Prediction'
  AND c.TableName IN ('feature_value')   -- add wide feature-group tables here
  AND (LOWER(c.ColumnName) IN (
         'legal_name','full_name','birth_date','email','phone','address',
         'credit_limit_amt','annual_income_amt','party_name','product_name')
    OR LOWER(c.ColumnName) LIKE '%_name'
    OR LOWER(c.ColumnName) LIKE '%_amt');

-- INV-PRED-002 : point-in-time — feature tables carry observation + validity columns.
-- Any feature table missing observation_dts / valid_from_dts / valid_to_dts is a violation.
SELECT t.TableName,
       MAX(CASE WHEN c.ColumnName = 'observation_dts' THEN 1 ELSE 0 END) AS has_observation,
       MAX(CASE WHEN c.ColumnName = 'valid_from_dts'  THEN 1 ELSE 0 END) AS has_valid_from,
       MAX(CASE WHEN c.ColumnName = 'valid_to_dts'    THEN 1 ELSE 0 END) AS has_valid_to
FROM DBC.TablesV t
JOIN DBC.ColumnsV c
  ON c.DatabaseName = t.DatabaseName AND c.TableName = t.TableName
WHERE t.DatabaseName = '{{ product }}_Prediction'
  AND t.TableName IN ('feature_value')   -- add wide feature-group tables here
GROUP BY t.TableName
HAVING has_observation = 0 OR has_valid_from = 0 OR has_valid_to = 0;

-- RichMetadata : every column of a feature table carries a comment.
SELECT TableName, ColumnName
FROM DBC.ColumnsV
WHERE DatabaseName = '{{ product }}_Prediction'
  AND TableName IN ('feature_value','model_prediction')
  AND (CommentString IS NULL OR TRIM(CommentString) = '');
