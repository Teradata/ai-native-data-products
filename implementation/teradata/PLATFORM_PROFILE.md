---
title: Teradata Platform Profile
anchor: teradata
type: platform-profile
status: standard
version: 2.0
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

Note: the [temporal-lifecycle implementation](patterns/temporal-lifecycle-metadata/) uses NUPI on the natural key for co-located joins across versions; choose UPI-with-period where in-schema uniqueness of `(natural_key, valid_from_dts)` is preferred.

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
| Zone-qualified `TIMESTAMP` literal in a `CREATE TABLE` `DEFAULT` clause | No error. The driver hangs in its parse phase and the session times out after minutes. | Set the value at INSERT time. This is why the open-end sentinel is never a `DEFAULT` (see the [temporal-lifecycle binding](patterns/temporal-lifecycle-metadata/)). |
| `CREATE INDEX name ON table (cols)` | `[3706] Must specify index field(s) for CREATE INDEX` | `CREATE INDEX name (cols) ON table` |
| `WHERE` predicate on `CREATE INDEX` | Syntax error: Teradata has no filtered/partial indexes | Index all rows; filter at query time |
| `ORDER BY` inside a view body | `[3706] ORDER BY clause not permitted in this context` | Ordering is a consumer concern; apply it at query time. Use `QUALIFY ROW_NUMBER() OVER (... ORDER BY ...)` where the view needs a latest-row projection. |
| `SELECT 'literal'` with no `FROM`, including inside a derived table | `[3888] A SELECT for a UNION, INTERSECT or MINUS must reference a table` | Query the `DBC` catalogue directly for existence checks: `SELECT DatabaseName FROM DBC.DatabasesV WHERE DatabaseName IN (...)` and count the rows returned. |
| An aggregate referencing another aggregate's result | `[3568] Cannot nest aggregate operations` | Wrap the inner aggregation in a derived table and filter in the outer query's `WHERE`. |
| `DBC.AllRightsV` filtered on `Grantee` | `[5628] Column Grantee not found` | The columns are `UserName` (who holds the right) and `GrantorName` (who granted it). |
| `DBC.DatabasePrivilegesV` | `[3807] Object does not exist` | Use `DBC.AllRightsV` throughout; database-level rights carry an empty `TableName`. |
| Non-ASCII characters in a string literal | `[6706] The string contains an untranslatable character` | Columns default to `CHARACTER SET LATIN`. Declare `CHARACTER SET UNICODE` on text columns that hold prose; see the [Memory binding](modules/memory/). |
| `:identifier` inside a stored SQL string | `InvalidRequestError: A value is required for bind parameter` | The MCP driver's SQLAlchemy layer intercepts `:word` as a named bind parameter before the SQL reaches the database. Stored templates use `<param_name>`; the same applies to an unquoted `:true` or `:1` inside JSON. |

The last row has a boundary worth keeping straight: `:param` is correct for a **runtime** bind parameter in maintenance DML a pipeline executes, and wrong for a parameter placeholder **stored inside a string literal**, such as a cookbook template. The driver cannot tell the two apart; you can.

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

## Related

- Time-zone / UTC persistence and the SCD2 sentinel: [temporal-lifecycle implementation](patterns/temporal-lifecycle-metadata/).
- Container naming and separation: [object-placement implementation](patterns/object-placement/).
- Object-storage physical layout (Iceberg on S3): [physical-storage implementation](patterns/physical-storage/).
