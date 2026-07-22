-- Semantic module — live hybrid column catalogue (Teradata). Binding of design/modules/semantic.md §6.
-- Lists every deployed column, decodes types live from DBC (with view_column_type overrides),
-- resolves descriptions by precedence (curated -> deployed comment -> none), and carries the
-- provenance of every resolved value so consumers see a complete schema without the curated store
-- copying dictionary facts. Replace {{ product }}.

REPLACE VIEW {{ product }}_Semantic.column_catalogue
(
      catalogue_database, catalogue_table, column_name, ordinal_position
    , data_type, data_type_source, is_nullable, is_required
    , business_description, description_source, is_documented
    , is_pii, is_sensitive, data_classification, allowed_values_json
)
AS
SELECT
      dcol.DatabaseName                                        AS catalogue_database
    , dcol.TableName                                           AS catalogue_table
    , dcol.ColumnName                                          AS column_name
    , dcol.ColumnId                                            AS ordinal_position
    , COALESCE(
          vtype.data_type
        , CASE TRIM(dcol.ColumnType)
              WHEN 'I'  THEN 'INTEGER'
              WHEN 'I1' THEN 'BYTEINT'
              WHEN 'I2' THEN 'SMALLINT'
              WHEN 'I8' THEN 'BIGINT'
              WHEN 'F'  THEN 'FLOAT'
              WHEN 'D'  THEN 'DECIMAL(' || TRIM(dcol.DecimalTotalDigits)
                              || ',' || TRIM(dcol.DecimalFractionalDigits) || ')'
              WHEN 'DA' THEN 'DATE'
              WHEN 'AT' THEN 'TIME'
              WHEN 'TS' THEN 'TIMESTAMP'
              WHEN 'SZ' THEN 'TIMESTAMP WITH TIME ZONE'
              WHEN 'CF' THEN 'CHAR(' || TRIM(CAST(
                                  CASE WHEN dcol.CharType = 2
                                       THEN dcol.ColumnLength / 2
                                       ELSE dcol.ColumnLength END AS INTEGER)) || ')'
              WHEN 'CV' THEN 'VARCHAR(' || TRIM(CAST(
                                  CASE WHEN dcol.CharType = 2
                                       THEN dcol.ColumnLength / 2
                                       ELSE dcol.ColumnLength END AS INTEGER)) || ')'
              WHEN 'CO' THEN 'CLOB'
              WHEN 'JN' THEN 'JSON'
              WHEN 'BO' THEN 'BLOB'
              WHEN 'BV' THEN 'VARBYTE'
              WHEN 'BF' THEN 'BYTE'
              ELSE TRIM(dcol.ColumnType)
          END
      )                                                        AS data_type
    , CASE WHEN vtype.data_type IS NOT NULL THEN 'override' ELSE 'dictionary' END AS data_type_source
    , CASE WHEN dcol.Nullable = 'Y' THEN 1 ELSE 0 END          AS is_nullable
    , CASE WHEN dcol.Nullable = 'N' THEN 1 ELSE 0 END          AS is_required
    , COALESCE(meta.business_description, NULLIF(TRIM(dcol.CommentString), '')) AS business_description
    , CASE WHEN meta.business_description IS NOT NULL            THEN 'curated'
           WHEN NULLIF(TRIM(dcol.CommentString), '') IS NOT NULL THEN 'comment'
           ELSE 'none' END                                     AS description_source
    , CASE WHEN COALESCE(meta.business_description, NULLIF(TRIM(dcol.CommentString), '')) IS NOT NULL
           THEN 1 ELSE 0 END                                   AS is_documented
    , COALESCE(meta.is_pii, 0)                                 AS is_pii
    , COALESCE(meta.is_sensitive, 0)                           AS is_sensitive
    , meta.data_classification                                 AS data_classification
    , meta.allowed_values_json                                 AS allowed_values_json
FROM DBC.ColumnsV AS dcol
LEFT OUTER JOIN {{ product }}_Semantic.column_metadata AS meta
    ON  meta.database_name = dcol.DatabaseName
    AND meta.table_name    = dcol.TableName
    AND meta.column_name   = dcol.ColumnName
    AND meta.is_active     = 1
LEFT OUTER JOIN {{ product }}_Semantic.view_column_type AS vtype
    ON  vtype.database_name = dcol.DatabaseName
    AND vtype.view_name     = dcol.TableName
    AND vtype.column_name   = dcol.ColumnName
    AND vtype.is_active     = 1
WHERE dcol.DatabaseName IN (
    SELECT m.database_name FROM {{ product }}_Semantic.data_product_map AS m
    WHERE m.is_active = 1
);

COMMENT ON VIEW {{ product }}_Semantic.column_catalogue IS
'Live hybrid column catalogue - every deployed column, types decoded live, descriptions resolved by precedence, with per-row provenance. A documentation-gap report is WHERE is_documented = 0.';
