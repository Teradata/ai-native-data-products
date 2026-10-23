---
title: Teradata Platform Profile
anchor: teradata
type: platform-profile
status: draft
version: 3.0
normative: false
platform: teradata
---

# Teradata: Platform Profile

Platform-specific physical-design guidance for Teradata implementations of the AI-Native Data Product standard. The structural requirements live in [`design/`](../../design/) and are platform-agnostic; the guidance here is Teradata-specific. Teams on other platforms produce an equivalent profile covering the same topics: physical key strategy, partitioning, indexing, statistics, compression, and query optimisation.

This profile complements the per-pattern and per-module implementation directories (which carry the concrete DDL); it collects what applies across all of them: the cross-cutting physical-design advice in sections 1 to 6, and in section 7 the dialect and driver constraints that decide whether generated SQL runs at all.

> **These are recommended defaults** for AI-native workloads (point-in-time feature computation, high-volume batch ML, low-latency agent lookups, cross-module joins). Deviate where a workload justifies it and record the deviation as a design decision.

---

## 1. Primary Index Selection

The Primary Index (PI) is the most critical physical-design decision in Teradata.

| Entity type | Advocated PI | Rationale |
|-------------|--------------|-----------|
| Core entities | Surrogate key (UPI) | Even distribution, simple joins |
| High-volume entities | Natural key (NUPI) | If frequently queried by business id |
| Reference data | Code (UPI) | Code lookups most common |
| Relationship tables | Composite FK (NUPI) | Co-locate with the parent entity |
| Time-series entities | Composite entity + time (NUPI) | Partition-elimination benefits |

**Decision:** single-row lookup by surrogate → surrogate UPI; by natural key → natural-key UPI; time-range on entity → composite `(entity_id, time_column)` NUPI; frequent join to parent → parent FK NUPI for co-location; mixed → surrogate UPI plus secondary indexes.

```sql
-- Surrogate key UPI (most common); UNIQUE PI includes the SCD2 period for versioned tables
CREATE TABLE Party_H ( party_id BIGINT NOT NULL /*... */)
UNIQUE PRIMARY INDEX (party_id, valid_from_dts, transaction_from_dts);

-- Relationship table co-located with the first parent
CREATE TABLE PartyProduct_H ( /*... */)
PRIMARY INDEX (party_id, product_id);

-- Time-series composite + monthly partitioning
CREATE TABLE Transaction_H ( transaction_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL /*... */)
PRIMARY INDEX (party_id, transaction_dts)
PARTITION BY RANGE_N(transaction_dts BETWEEN DATE '2020-01-01' AND DATE '2030-12-31' EACH INTERVAL '1' MONTH);
```

Note: the [shared macros](README.md#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata) give a versioned table a NUPI on its version columns, so every version of an identity sits on one AMP, with a unique constraint on the version columns plus the interval starts; a keymap a UPI on its natural key, which its allocating `MERGE` matches on; and anything else a UPI on its key.

---

## 2. Partitioning

Advocate partitioning for tables > 100M rows, time-series access patterns, or where partition elimination materially helps. Below 100M rows, usually skip it.

| Dimension | When | Example |
|-----------|------|---------|
| Transaction time | Queries filter on load/update date (most common) | `transaction_from_dts` |
| Valid time | Business queries filter on effective date | `valid_from_dts` |
| Date attribute | Event data with natural dates | `transaction_date` |
| Multi-level | Time + status/type | time + `is_deleted` |

```sql
-- Monthly (most common)
PARTITION BY RANGE_N(transaction_from_dts BETWEEN DATE '2020-01-01' AND DATE '2030-12-31' EACH INTERVAL '1' MONTH);

-- Multi-level: yearly validity + active/deleted split
PARTITION BY (
    RANGE_N(valid_from_dts BETWEEN DATE '2020-01-01' AND DATE '2030-12-31' EACH INTERVAL '1' YEAR),
    CASE_N(is_deleted = 0, is_deleted = 1, UNKNOWN)
);
```

---

## 3. Secondary Indexes

Selective use only: create when a critical, frequent query doesn't use the PI and performance is unacceptable, and insert volume is moderate. Avoid on rare/ad-hoc queries, when the PI already covers the query, or under high insert/update volume.

Two things separate Teradata's syntax from the SQL Server and PostgreSQL form most generators reach for: the column list comes **before** `ON`, and there is no `WHERE` predicate, because Teradata has no filtered (partial) indexes. The index covers every row; consumers apply the currency filter at query time.

```sql
-- Natural-key lookup when PI is the surrogate
CREATE UNIQUE INDEX idx_party_natural_key (party_key) ON Party_H;
-- FK index for join optimisation
CREATE INDEX idx_partyproduct_product (product_id) ON PartyProduct_H;
```

---

## 4. Join Indexes

Advocate for expensive, frequently-used joins, pre-computed aggregations, and materialised current views. Costs write throughput, so reserve for genuinely hot patterns.

```sql
-- Materialised current-version view
CREATE JOIN INDEX jidx_party_current AS
SELECT party_id, party_key, legal_name, status_code
FROM Party_H
WHERE is_current = 1 AND is_deleted = 0
  AND transaction_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
PRIMARY INDEX (party_id);
```

Also usable for denormalised hot joins and pre-computed aggregations (counts, sums) keyed by entity.

---

## 5. Compression

Advocate compression for large text (> 500 chars), JSON, and sparse columns; skip small strings, numerics, and frequently-updated columns (recompression cost).

```sql
CREATE TABLE Document_H ( document_id BIGINT NOT NULL, document_content CLOB)
WITH COLUMN_PARTITION = ( COLUMN (document_content) COMPRESS USING ZLIBHIGH);
```

---

## 6. Statistics

Collect on join/filter columns after creation and refresh with maintenance; sample large tables.

```sql
COLLECT STATISTICS
    COLUMN (party_id), COLUMN (party_key), COLUMN (is_current), COLUMN (is_deleted),
    COLUMN (valid_from_dts), COLUMN (transaction_from_dts)
ON Party_H;
-- Large tables: COLLECT STATISTICS ON Party_H USING SAMPLE 10 PERCENT;
```

| Table size | Frequency | Method |
|------------|-----------|--------|
| < 1M rows | After major loads | Full scan |
| 1M-100M rows | Daily | 10% sample |
| > 100M rows | Weekly | 5% sample |
| Reference tables | After changes only | Full scan |

---

## 7. SQL Idioms and Driver Constraints

Everything above is about making the physical design fast. This section is about making the SQL run at all.

Generators trained on the wider SQL corpus reach for SQL Server and PostgreSQL idioms that Teradata rejects, and the rejection usually arrives as a bare error number several statements after the cause. Each row below is a construct that has failed a real deployment. **Search this table by error code**: the code is what you will meet first.

| Construct | What happens | Use instead |
|---|---|---|
| Zone-qualified `TIMESTAMP` literal in a `CREATE TABLE` `DEFAULT` clause | No error. The driver hangs in its parse phase and the session times out after minutes. | Set the value at INSERT time. This is why the open-end sentinel is never a `DEFAULT` (see the [temporal-lifecycle binding](README.md#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata)). |
| `COMMENT ON` text longer than **255 characters** (any object type) | `[5550] Comment string is longer than permitted` | Keep the comment to 255 characters. The limit is characters, not bytes: `DBC` stores comments as `VARCHAR(510) CHARACTER SET UNICODE`, and `DBC.ColumnsV.ColumnLength` reports UNICODE widths in bytes at two per character (`DatabaseName`, a `VARCHAR(128)`, reports 256). An em dash or a curly quote therefore costs one character, not three, so the UNICODE prose these standards ask for is not penalised. For roles specifically the [access-layer pattern](../../design/patterns/access-layer.md) caps it far lower: one short sentence naming who the role is for, never what it can reach. |
| `CREATE INDEX name ON table (cols)` | `[3706] Must specify index field(s) for CREATE INDEX` | `CREATE INDEX name (cols) ON table` |
| `WHERE` predicate on `CREATE INDEX` | Syntax error: Teradata has no filtered/partial indexes | Index all rows; filter at query time |
| `ORDER BY` inside a view body | `[3706] ORDER BY clause not permitted in this context` | Ordering is a consumer concern; apply it at query time. Use `QUALIFY ROW_NUMBER() OVER (... ORDER BY ...)` where the view needs a latest-row projection. |
| `SELECT 'literal'` with no `FROM`, including inside a derived table | `[3888] A SELECT for a UNION, INTERSECT or MINUS must reference a table` | Query the `DBC` catalogue directly for existence checks: `SELECT DatabaseName FROM DBC.DatabasesV WHERE DatabaseName IN (...)` and count the rows returned. |
| An untyped `NULL` as a select-list item in a branch of a `UNION` (or `INTERSECT`, `MINUS`) | `[3654] Corresponding select-list expressions are incompatible`, raised when the view is queried, not when it is created | Type it: `CAST(NULL AS VARCHAR(400))`, `CAST(NULL AS TIMESTAMP(6) WITH TIME ZONE)`, matching the other branches' column. |
| A vector in `VARBYTE` written as 4-byte floats and read by `TD_VECTORDISTANCE` | No error where the length is a multiple of 8: the function reads the bytes as 8-byte floats, and every distance is wrong. Otherwise `[9134] Embeddings contain invalid double values. Row length must be multiple of 8` | Store each element as a little-endian 8-byte float: `VARBYTE(dimensions × 8)` (see Vectors, below). |
| A bind (`?`) or macro parameter inside a `TD_VECTORDISTANCE` `ON` clause | `[3706] Parameter token '?' is not allowed in SQLMRQuery`; in a macro, `[3939]` | Build the request as dynamic SQL in a stored procedure, with the value written in as a literal. |
| `FROM_BYTES(x, 'base16')` used to write bytes back as a hex literal | No error: leading zero digits are dropped, so the literal is shorter than the value and a vector's length is wrong | `LPAD(CAST(FROM_BYTES(x, 'base16') AS VARCHAR(2n)), 2n, '0')` for `n` bytes, then `'...'XB` cast to the column's type. |
| Concatenating `FROM_BYTES` output into a string in a stored procedure | `[5526]`, from the compiler's `[3798] A column or character expression is larger than the max size` | Cast `FROM_BYTES` to the exact hex length first, as above. |
| `CREATE` or `REPLACE PROCEDURE` in a database the deploying user created | `[5526] Stored Procedure is not created/replaced due to error(s)`: a database's creator is granted `DROP PROCEDURE` on it but not `CREATE PROCEDURE` | `GRANT CREATE PROCEDURE ON <database> TO <deploying user>` first; the `Deploying user` binding setting renders it. BTEQ's `.COMPILE FILE` prints the compiler's own messages; teradatasql does not. |
| A stored procedure sent without the semicolon after its final `END`, or split at its body's semicolons (as BTEQ splits a script) | `[5526] Stored Procedure is not created/replaced due to error(s)`, or a cascade of `[3706]` | Send each procedure as one request, ending `END;`: through a driver, or in BTEQ with `.COMPILE FILE`. |
| An aggregate referencing another aggregate's result | `[3568] Cannot nest aggregate operations` | Wrap the inner aggregation in a derived table and filter in the outer query's `WHERE`. |
| `DBC.AllRightsV` filtered on `Grantee` | `[5628] Column Grantee not found` | The columns are `UserName` (who holds the right) and `GrantorName` (who granted it). |
| `DBC.DatabasePrivilegesV` | `[3807] Object does not exist` | Use `DBC.AllRightsV` throughout; database-level rights carry an empty `TableName`. |
| Non-ASCII characters in a string literal | `[6706] The string contains an untranslatable character` | Columns default to `CHARACTER SET LATIN`. Declare `CHARACTER SET UNICODE` on text columns that hold prose; see the [Memory binding](README.md#3-memory-module-memory). |
| `:identifier` inside a stored SQL string | `InvalidRequestError: A value is required for bind parameter` | The MCP driver's SQLAlchemy layer intercepts `:word` as a named bind parameter before the SQL reaches the database. Stored templates use `<param_name>`; the same applies to an unquoted `:true` or `:1` inside JSON. |

The last row has a boundary worth keeping straight: `:param` is correct for a **runtime** bind parameter in maintenance DML a pipeline executes, and wrong for a parameter placeholder **stored inside a string literal**, such as a cookbook template. The driver cannot tell the two apart; you can.

### Vectors

A `Vector[n]` is held as `VARBYTE(n × 8)`: its elements as little-endian 8-byte floats (IEEE 754 doubles), with a `CHECK` that the value is exactly that long. This is the encoding `TD_VECTORDISTANCE` reads from a `VARBYTE` column, so the stored vectors are scored with no conversion. The same column holding 4-byte floats is misread without an error whenever its length is a multiple of 8, and every distance is then wrong.

A producer writes a vector as:

- **from outside the database**: `numpy.asarray(v, dtype="<f8").tobytes()`, or `struct.pack(f"<{n}d", *v)`, bound as a `VARBYTE` parameter;
- **from an in-database embedding function**: converted to 8-byte floats first. `mldb.ONNXEmbeddings` with `OutputFormat('VARBYTE(n × 4)')` writes 4-byte floats, which is not this encoding; whether it can write 8-byte floats has not been tested here.

Similarity is a stored procedure per `Embedding:` block, called as `CALL <procedure>(query_vector, result_limit)`, with the query vector in the same encoding. It returns one result set of `(entity_id, similarity)`; see the [Search binding](README.md#7-search-module-search).

---

## 8. Physical-Design Checklist

- [ ] Primary Index chosen and justified.
- [ ] Partitioning defined (if > 100M rows or time-series).
- [ ] Secondary indexes planned with rationale (selective).
- [ ] Join indexes considered for expensive, hot patterns.
- [ ] Compression defined for large text / JSON columns.
- [ ] Statistics collection automated on join/filter columns.
- [ ] Query patterns tested against the physical design.

---

## Binding declarations

The declarations the resolver and renderer read are in [`binding.toml`](binding.toml) ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §5.1): quoting, the object roles this binding emits beyond tables and views, its settings, its phases and checks, its declared gaps, its physical type for each logical type, and its SQL for each expression function. A function with no entry is not rendered by this binding; an expression that uses one is carried unrendered and reported as a gap.

## Related

- Time-zone / UTC persistence and the SCD2 sentinel: [temporal-lifecycle implementation](README.md#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata).
- Databases and their space: [object-placement implementation](README.md#1-object-placement-pattern-object-placement); naming and separation are the organisation profile's.
- Physical storage: [physical-storage implementation](README.md#11-physical-storage-pattern-physical-storage). Object storage is not rendered.
