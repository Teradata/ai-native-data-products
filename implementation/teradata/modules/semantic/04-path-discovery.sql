-- Semantic module — multi-hop path discovery (Teradata). Binding of design/modules/semantic.md §5.
-- Recursive traversal of table_relationship, bidirectional, bounded to 5 hops, with cycle
-- avoidance and generated JOIN syntax. Replace {{ product }}.

CREATE VIEW {{ product }}_Semantic.v_relationship_paths
(
    source_table, target_table, path_tables, path_joins, hop_count, path_description
)
AS
WITH RECURSIVE relationship_paths
    (source_table, target_table, path_tables, path_joins, hop_count, path_description) AS (
    -- Anchor: forward (1 hop)
    SELECT source_table, target_table,
           source_table || ' -> ' || target_table AS path_tables,
           'JOIN ' || target_table || ' ON ' || target_table || '.' || target_column
               || ' = ' || source_table || '.' || source_column AS path_joins,
           1 AS hop_count,
           relationship_description AS path_description
    FROM {{ product }}_Semantic.table_relationship
    WHERE is_active = 1

    UNION ALL
    -- Anchor: reversed (1 hop backward)
    SELECT target_table AS source_table, source_table AS target_table,
           target_table || ' -> ' || source_table AS path_tables,
           'JOIN ' || source_table || ' ON ' || source_table || '.' || source_column
               || ' = ' || target_table || '.' || target_column AS path_joins,
           1 AS hop_count,
           'REVERSE: ' || relationship_description AS path_description
    FROM {{ product }}_Semantic.table_relationship
    WHERE is_active = 1

    UNION ALL
    -- Recursive: forward
    SELECT rp.source_table, tr.target_table,
           rp.path_tables || ' -> ' || tr.target_table AS path_tables,
           rp.path_joins || ' | ' || 'JOIN ' || tr.target_table || ' ON '
               || tr.target_table || '.' || tr.target_column || ' = '
               || tr.source_table || '.' || tr.source_column AS path_joins,
           rp.hop_count + 1 AS hop_count,
           rp.path_description || ' -> ' || tr.relationship_description AS path_description
    FROM relationship_paths rp
    INNER JOIN {{ product }}_Semantic.table_relationship tr
        ON tr.source_table = rp.target_table AND tr.is_active = 1
    WHERE rp.hop_count < 5
      AND rp.path_tables NOT LIKE '%' || tr.target_table || '%'

    UNION ALL
    -- Recursive: backward
    SELECT rp.source_table, tr.source_table AS target_table,
           rp.path_tables || ' -> ' || tr.source_table AS path_tables,
           rp.path_joins || ' | ' || 'JOIN ' || tr.source_table || ' ON '
               || tr.source_table || '.' || tr.source_column || ' = '
               || tr.target_table || '.' || tr.target_column AS path_joins,
           rp.hop_count + 1 AS hop_count,
           rp.path_description || ' -> REVERSE: ' || tr.relationship_description AS path_description
    FROM relationship_paths rp
    INNER JOIN {{ product }}_Semantic.table_relationship tr
        ON tr.target_table = rp.target_table AND tr.is_active = 1
    WHERE rp.hop_count < 5
      AND rp.path_tables NOT LIKE '%' || tr.source_table || '%'
)
SELECT * FROM relationship_paths;

COMMENT ON VIEW {{ product }}_Semantic.v_relationship_paths IS
'Multi-hop relationship path discovery - indirect join paths between any two tables up to 5 hops, bidirectional, with generated JOIN syntax.';

-- Agent example: shortest path from Party_H to Transaction_H
-- SELECT hop_count, path_tables, path_joins
-- FROM {{ product }}_Semantic.v_relationship_paths
-- WHERE source_table = 'Party_H' AND target_table = 'Transaction_H'
-- ORDER BY hop_count
-- QUALIFY ROW_NUMBER() OVER (ORDER BY hop_count) = 1;
