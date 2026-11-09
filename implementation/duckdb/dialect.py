"""The DuckDB dialect: what DuckDB does differently from the portable defaults.

Key sequences instead of identity columns, table macros for point-in-time reads, and no
partial unique indexes or exclusion constraints: one open version per identity and
non-overlapping intervals are proved by the temporal check instead.
"""
from portable_dialect import PortableDialect


class DuckDBDialect(PortableDialect):
    # No access phase: DuckDB has no principals, and each tier is enforced outside the engine.
    PHASES = tuple(p for p in PortableDialect.PHASES if p != "access")

    # The column catalogue reads this database file's catalogue only.
    catalogue_scope = "col.table_catalog = current_database() AND "
    text_type = "VARCHAR"
    double_type = "DOUBLE"

    def array(self, *items):
        return f"[{', '.join(items)}]"

    def append(self, array, item):
        return f"list_append({array}, {item})"

    def not_in_array(self, array, item):
        return f"NOT list_contains({array}, {item})"

    def positions(self, array, alias, column):
        return f"CROSS JOIN LATERAL (SELECT unnest(range(1, len({array}) + 1)) AS {column}) {alias}"

    tables_scope = " AND t.table_catalog = current_database()"
    columns_scope = "i.table_catalog = current_database() AND "

    def matches(self, expr, pattern):
        return f"regexp_matches({expr}, '{pattern}')"

    def not_matches(self, expr, pattern):
        return f"NOT regexp_matches({expr}, '{pattern}')"

    def check_entity_metadata(self, entity):
        t = entity["objects"]["table"]
        return "\n".join([
            self.expected_columns(entity),
            "LEFT JOIN duckdb_columns() actual",
            f"  ON actual.database_name = current_database() AND actual.schema_name = {self.literal(t['container'])} "
            f"AND actual.table_name = {self.literal(t['name'])}",
            " AND actual.column_name = expected.column_name",
            "WHERE actual.column_name IS NULL OR nullif(actual.comment, '') IS NULL"])

    def single_key_allocation(self, keymap, natural_value, km, stamps, key):
        """An existing mapping returns its identifier unchanged."""
        n, u = self.ident(self.natural_column(keymap)[0]), self.ident(keymap["column_names"]["updated_dts"])
        return "\n".join([f"INSERT INTO {km} AS k ({stamps})",
                          f"VALUES ({self.literal(natural_value)}, current_timestamp, current_timestamp)",
                          f"ON CONFLICT ({n}) DO UPDATE SET {u} = k.{u}", f"RETURNING {key};"])

    def check_product_comment_coverage(self):
        """DuckDB cannot comment a schema, so schemas are not swept."""
        inside = self.owned_containers()
        here = "database_name = current_database()"
        return "\n".join([
            "SELECT 'table' AS object_kind, t.schema_name AS container_name, t.table_name AS object_name, "
            "CAST(NULL AS VARCHAR) AS column_name",
            "FROM duckdb_tables() t", f"WHERE t.{here} AND NOT t.internal AND t.schema_name IN ({inside})",
            "  AND nullif(trim(t.comment), '') IS NULL",
            "UNION ALL",
            "SELECT 'view', v.schema_name, v.view_name, NULL", "FROM duckdb_views() v",
            f"WHERE v.{here} AND NOT v.internal AND v.schema_name IN ({inside})", "  AND nullif(trim(v.comment), '') IS NULL",
            "UNION ALL",
            "SELECT 'column', c.schema_name, c.table_name, c.column_name", "FROM duckdb_columns() c",
            f"WHERE c.{here} AND NOT c.internal AND c.schema_name IN ({inside})", "  AND nullif(trim(c.comment), '') IS NULL",
            "UNION ALL",
            "SELECT 'sequence', s.schema_name, s.sequence_name, NULL", "FROM duckdb_sequences() s",
            f"WHERE s.{here} AND s.schema_name IN ({inside})", "  AND nullif(trim(s.comment), '') IS NULL",
            "UNION ALL",
            "SELECT 'macro', f.schema_name, f.function_name, NULL", "FROM duckdb_functions() f",
            f"WHERE f.{here} AND NOT f.internal AND f.function_type IN ('macro', 'table_macro')",
            f"  AND f.schema_name IN ({inside})", "  AND nullif(trim(f.comment), '') IS NULL"])

    def open_version_defects(self, x, t, ids):
        """DuckDB enforces neither one open version per identity nor non-overlap in its schema,
        so both are proved by the check."""
        cn, ident = x["column_names"], self.ident
        same = "".join(f"a.{ident(k)} = c.{ident(k)} AND " for k in ids)
        cur = ident(cn["is_current"])
        return [f" OR (a.{cur} AND EXISTS (SELECT 1 FROM {t} c WHERE {same}c.{cur}",
                f"     AND {self.versions_differ('a', 'c', x)}))"]

    def key_default(self, x, col):
        seq = x["objects"].get("sequence")
        return f" DEFAULT nextval({self.literal(seq['container'] + '.' + seq['name'])})" if seq else ""

    def before_table(self, x):
        seq = x["objects"].get("sequence")
        if not seq:
            return ""
        note = self.literal(f"Allocates the permanent identifiers of {x['name']}; never reset or recycled.")
        return f"CREATE SEQUENCE {self.qualified(seq)};\nCOMMENT ON SEQUENCE {self.qualified(seq)} IS {note};\n"

    def point_in_time(self, x):
        f, t = self.qualified(x["objects"]["function"]), self.qualified(x["objects"]["table"])
        args = "valid_at" + (", known_at" if x["bitemporal"] else "")
        takes = " Takes the valid-time and known-time instants." if x["bitemporal"] else " Takes the valid-time instant."
        return "\n".join([f"CREATE MACRO {f}({args}) AS TABLE", f"SELECT * FROM {t} WHERE {self.at(x)};",
                          f"COMMENT ON MACRO TABLE {f} IS "
                          f"{self.literal('Point-in-time reconstruction of ' + x['description'] + takes)};"])


    def similarity(self, b):
        store = self.named(b["store"])
        sc, v, dims = store["column_names"], "e." + self.ident(b["vector_column"]), b["dimensions"]
        q = f"query_vector::FLOAT[{dims}]"
        score = {"cosine": f"array_cosine_similarity({v}, {q})", "dot": f"array_inner_product({v}, {q})",
                 "euclidean": f"1.0 / (1.0 + array_distance({v}, {q}))"}.get(
            b["similarity"],
            f"1.0 / (1.0 + list_sum(list_transform(range(1, {int(dims) + 1}), lambda i: abs({v}[i] - ({q})[i]))))")
        f = self.qualified(b["objects"]["function"])
        note = (f"Similarity search over the {b['name']} embedding of {b['entity']}. "
                "Takes a query vector and a result limit (maximum 1000).")
        return "\n".join(
            [f"CREATE MACRO {f}(query_vector, result_limit) AS TABLE", "SELECT ranked.entity_id, ranked.similarity FROM (",
             f"    SELECT e.{self.ident(sc['entity_id'])} AS entity_id, {score} AS similarity",
             f"    FROM {self.qualified(store['objects']['consumer_view'])} e"]
            + self.similarity_filters(b, sc) + self.similarity_tail(b)
            + [f"COMMENT ON MACRO TABLE {f} IS {self.literal(note)};"])


DIALECT = DuckDBDialect
