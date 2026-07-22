-- Search module — Teradata invariant checks.
-- Runnable checks backing the invariants in design/modules/search.md §10.
-- Each query must return ZERO rows for a conforming deployment.
-- Replace {{ product }} with the data product name before running.

-- ---------------------------------------------------------------------------
-- INV-SEARCH-001 : keys only — the embedding table holds no Domain-owned content.
-- Flags any column whose name looks like content rather than a key/metadata column.
-- ---------------------------------------------------------------------------
SELECT ColumnName
FROM DBC.ColumnsV
WHERE DatabaseName = '{{ product }}_Search'
  AND TableName = 'entity_embedding'
  AND (LOWER(ColumnName) IN (
         'name','legal_name','full_name','title','description','long_description',
         'short_description','content','content_text','text','body','notes','email',
         'address','phone','price','category','product_name','party_name'
       )
    OR LOWER(ColumnName) LIKE '%_name'
    OR LOWER(ColumnName) LIKE '%_description'
    OR LOWER(ColumnName) LIKE '%_text');

-- ---------------------------------------------------------------------------
-- INV-SEARCH-003 : every embedding records the model and dimensionality.
-- Any current embedding with a missing model or dimensionality is a violation.
-- ---------------------------------------------------------------------------
SELECT embedding_id
FROM {{ product }}_Search.entity_embedding
WHERE is_current = 1
  AND (embedding_model IS NULL
    OR TRIM(embedding_model) = ''
    OR embedding_dimensions IS NULL);

-- ---------------------------------------------------------------------------
-- INV-SEARCH-002 : every embedding references exactly one current Domain entity.
-- Template — repeat per entity_kind against its Domain table. Example: PARTY.
-- Any current embedding whose entity_id has no current Domain row is a violation.
-- ---------------------------------------------------------------------------
SELECT e.embedding_id, e.entity_id
FROM {{ product }}_Search.entity_embedding e
WHERE e.is_current = 1
  AND e.entity_kind = 'PARTY'
  AND NOT EXISTS (
        SELECT 1
        FROM {{ product }}_Domain.Party_H d
        WHERE d.party_id = e.entity_id
          AND d.is_current = 1
          AND d.is_deleted = 0
      );

-- ---------------------------------------------------------------------------
-- RichMetadata : every column of the embedding table carries a comment.
-- ---------------------------------------------------------------------------
SELECT ColumnName
FROM DBC.ColumnsV
WHERE DatabaseName = '{{ product }}_Search'
  AND TableName = 'entity_embedding'
  AND (CommentString IS NULL OR TRIM(CommentString) = '');
