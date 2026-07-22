# Teradata — Platform Profile

Platform-specific physical-design guidance for Teradata implementations of the AI-Native Data
Product standard. The structural requirements live in [`design/`](../../design/) and are
platform-agnostic; the guidance here is Teradata-specific. Teams on other platforms produce an
equivalent profile covering the same topics: physical key strategy, partitioning, indexing,
statistics, compression, and query optimisation.

This profile complements the per-pattern and per-module implementation directories (which carry the
concrete DDL); it collects the cross-cutting physical-design advice that applies across them.

> **Advocacy, not mandate.** These are recommended defaults for AI-native workloads (point-in-time
> feature computation, high-volume batch ML, low-latency agent lookups, cross-module joins). Deviate
> where a workload justifies it and record the deviation as a design decision.

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

**Decision:** single-row lookup by surrogate → surrogate UPI; by natural key → natural-key UPI;
time-range on entity → composite `(entity_id, time_column)` NUPI; frequent join to parent → parent FK
NUPI for co-location; mixed → surrogate UPI plus secondary indexes.

```sql
-- Surrogate key UPI (most common); UNIQUE PI includes the SCD2 period for versioned tables
CREATE TABLE Party_H ( party_id BIGINT NOT NULL /* ... */ )
UNIQUE PRIMARY INDEX (party_id, valid_from_dts, transaction_from_dts);

-- Relationship table co-located with the first parent
CREATE TABLE PartyProduct_H ( /* ... */ )
PRIMARY INDEX (party_id, product_id);

-- Time-series composite + monthly partitioning
CREATE TABLE Transaction_H ( transaction_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL /* ... */ )
PRIMARY INDEX (party_id, transaction_dts)
PARTITION BY RANGE_N(transaction_dts BETWEEN DATE '2020-01-01' AND DATE '2030-12-31' EACH INTERVAL '1' MONTH);
```

Note: the [temporal-lifecycle implementation](patterns/temporal-lifecycle-metadata/) uses NUPI on the
natural key for co-located joins across versions; choose UPI-with-period where in-schema uniqueness of
`(natural_key, valid_from_dts)` is preferred.

---

## 2. Partitioning

Advocate partitioning for tables > 100M rows, time-series access patterns, or where partition
elimination materially helps. Below 100M rows, usually skip it.

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

Selective use only: create when a critical, frequent query doesn't use the PI and performance is
unacceptable, and insert volume is moderate. Avoid on rare/ad-hoc queries, when the PI already covers
the query, or under high insert/update volume.

```sql
-- Natural-key lookup when PI is the surrogate (current rows only)
CREATE UNIQUE INDEX idx_party_natural_key ON Party_H (party_key) WHERE is_current = 1 AND is_deleted = 0;
-- FK index for join optimisation
CREATE INDEX idx_partyproduct_product ON PartyProduct_H (product_id) WHERE is_current = 1 AND is_deleted = 0;
```

---

## 4. Join Indexes

Advocate for expensive, frequently-used joins, pre-computed aggregations, and materialised current
views. Costs write throughput, so reserve for genuinely hot patterns.

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

Advocate compression for large text (> 500 chars), JSON, and sparse columns; skip small strings,
numerics, and frequently-updated columns (recompression cost).

```sql
CREATE TABLE Document_H ( document_id BIGINT NOT NULL, document_content CLOB )
WITH COLUMN_PARTITION = ( COLUMN (document_content) COMPRESS USING ZLIBHIGH );
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
| 1M–100M rows | Daily | 10% sample |
| > 100M rows | Weekly | 5% sample |
| Reference tables | After changes only | Full scan |

---

## 7. Physical-Design Checklist

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
