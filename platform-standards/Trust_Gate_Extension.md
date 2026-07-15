# Data Product Trust Gate Extension — Teradata
## AI-Native Data Product Architecture — Version 1.0 (Draft)

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.0-draft |
| **Status** | DRAFT — Proposed (resolves issue #19 with `design-standards/Trust_Gate_Standard.md`) |
| **Last Updated** | 2026-07-15 |
| **Owner** | Worldwide Data Architecture Team, Teradata |
| **Scope** | Teradata binding of the Data Product Trust Gate Standard (wire schema 1.0) |
| **Type** | Platform Extension (Teradata) |
| **Reference implementation** | `ai-native-data-product-trust-engine` — this extension documents its deployed contract |

---

## Table of Contents

1. [Physical Model](#1-physical-model)
2. [Publish Semantics](#2-publish-semantics)
3. [The Latest-Run View](#3-the-latest-run-view)
4. [Type Bindings and 1.0 Compatibility Notes](#4-type-bindings-and-10-compatibility-notes)
5. [Consumer Queries](#5-consumer-queries)
6. [Conformance Queries](#6-conformance-queries)
7. [Placement and Layer Alignment](#7-placement-and-layer-alignment)
8. [Check Sources from Other Standards](#8-check-sources-from-other-standards)

---

## 1. Physical Model

A history **table** plus a latest-per-product **view**:

```sql
CREATE MULTISET TABLE {Product}_SEM_STD_T.trust_engine_run
(
    product_prefix VARCHAR(128) CHARACTER SET LATIN NOT NULL,
    run_id VARCHAR(64) CHARACTER SET LATIN NOT NULL,
    started_at VARCHAR(40) CHARACTER SET LATIN NOT NULL,
    completed_at VARCHAR(40) CHARACTER SET LATIN NOT NULL,
    trust_status VARCHAR(16) CHARACTER SET LATIN NOT NULL,
    agent_use_allowed BYTEINT NOT NULL,
    total_checks INTEGER NOT NULL,
    passed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    critical_failure_count INTEGER NOT NULL,
    error_failure_count INTEGER NOT NULL,
    data_product_trust_score INTEGER,
    performance_readiness_score INTEGER,
    operational_readiness_score INTEGER,
    repair_candidate_count INTEGER NOT NULL,
    failed_checks_json JSON(32000) CHARACTER SET UNICODE,
    repair_candidates_json JSON(32000) CHARACTER SET UNICODE
)
PRIMARY INDEX (product_prefix, completed_at);
```

Column comments per the naming conventions are required on deployment;
statistics:

```sql
COLLECT STATISTICS
      COLUMN (product_prefix)
    , COLUMN (product_prefix, completed_at)
ON {Product}_SEM_STD_T.trust_engine_run;
```

---

## 2. Publish Semantics

- **Append, never replace.** Each validation run INSERTs exactly one row;
  the table accumulates run history as evidence (core §2, TGS-09).
- `run_id` is deterministic: the first 32 hex characters of a SHA-256 over
  `prefix|started_at|completed_at|result_count` — replaying the same run
  yields the same identifier.
- JSON blobs are serialised compact with sorted keys, item caps applied
  (20 checks × 3 sample rows; 20 repair candidates), then truncated to the
  column's 32000-character limit. The authoritative totals are the count
  columns, never the blobs.

---

## 3. The Latest-Run View

The consumer surface is a 1-row-per-product projection:

```sql
REPLACE VIEW {Product}_SEM_ACS_V.trust_engine_latest
AS
LOCKING ROW FOR ACCESS
SELECT
      product_prefix
    , run_id
    , started_at
    , completed_at
    , trust_status
    , agent_use_allowed
    , total_checks
    , passed_count
    , failed_count
    , error_count
    , critical_failure_count
    , error_failure_count
    , data_product_trust_score
    , performance_readiness_score
    , operational_readiness_score
    , repair_candidate_count
    , failed_checks_json
    , repair_candidates_json
FROM {Product}_SEM_STD_T.trust_engine_run
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY product_prefix
    ORDER BY completed_at DESC, run_id DESC
) = 1;
```

The deterministic tie-break (`completed_at DESC, run_id DESC`) is part of
the contract (TGS-09). See §7 for the view's placement and its registered
legacy locations.

---

## 4. Type Bindings and 1.0 Compatibility Notes

| Contract element | 1.0 binding | Note |
|------------------|-------------|------|
| `started_at` / `completed_at` | `VARCHAR(40)` ISO-8601 | Known 1.0 limitation, kept for compatibility: changing to `TIMESTAMP(6) WITH TIME ZONE` (per the Temporal & Lifecycle Metadata Standard) is an **incompatible** change reserved for wire schema 2.0. Consumers parse ISO-8601 strings. |
| `agent_use_allowed` | `BYTEINT` 0/1 | Matches platform flag convention |
| Scores | `INTEGER` nullable | NULL = not assessed, never 100 |
| JSON blobs | `JSON(32000) CHARACTER SET UNICODE` | Cap discipline in §2 |
| `payload_schema_version` | **Not a column in 1.0** | Declared at build time via the shared golden fixture; runtime column is a planned 1.1 additive change requiring a coordinated DDL migration |

---

## 5. Consumer Queries

Stop/go check before analytical use:

```sql
SELECT trust_status, agent_use_allowed, completed_at,
       critical_failure_count, error_failure_count,
       data_product_trust_score
FROM {Product}_SEM_ACS_V.trust_engine_latest
WHERE product_prefix = :product_prefix;
```

Consumer rules (core §8, §10): a missing row means *unvalidated* — stop for
autonomous use; a row older than the evidence window (default 7 days from
`completed_at`) is stale — treat as `agent_use_allowed = 0`; never recount
the JSON blobs; never proceed on `UNTRUSTED`.

Run-history trend (auditors):

```sql
SELECT completed_at, trust_status, data_product_trust_score,
       critical_failure_count, error_failure_count, failed_count
FROM {Product}_SEM_STD_V.trust_engine_run
WHERE product_prefix = :product_prefix
ORDER BY completed_at DESC;
```

---

## 6. Conformance Queries

```sql
-- TGS-01/02: vocabulary and status/decision agreement
SELECT run_id, trust_status, agent_use_allowed
FROM {Product}_SEM_STD_V.trust_engine_run
WHERE trust_status NOT IN ('TRUSTED', 'DEGRADED', 'UNTRUSTED')
   OR (trust_status IN ('TRUSTED', 'DEGRADED') AND agent_use_allowed <> 1)
   OR (trust_status = 'UNTRUSTED' AND agent_use_allowed <> 0);

-- TGS-04: check totals reconcile
SELECT run_id, total_checks, passed_count, failed_count, error_count
FROM {Product}_SEM_STD_V.trust_engine_run
WHERE total_checks <> passed_count + failed_count + error_count;

-- TGS-06: score ranges
SELECT run_id
FROM {Product}_SEM_STD_V.trust_engine_run
WHERE data_product_trust_score    NOT BETWEEN 0 AND 100
   OR performance_readiness_score NOT BETWEEN 0 AND 100
   OR operational_readiness_score NOT BETWEEN 0 AND 100;

-- Deployment: the latest view exists and yields exactly one row per product
SELECT product_prefix, COUNT(*) AS rows_seen
FROM {Product}_SEM_ACS_V.trust_engine_latest
GROUP BY product_prefix
HAVING COUNT(*) > 1;
```

---

## 7. Placement and Layer Alignment

- Base table: Semantic module, `{Product}_SEM_STD_T`; 1:1 locking view in
  `{Product}_SEM_STD_V` per the standard view-layer rule.
- Latest view: the Access Layer — `{Product}_SEM_ACS_V` for new products
  per the Temporal & Lifecycle Metadata Extension's `ACS_V` adoption.
  `{Product}_SEM_BUS_V` and `{Product}_SEM_ACL_V` are registered legacy
  locations for this view; consumers should resolve the object through
  product orientation metadata (issue #20), not by guessing layer
  suffixes.
- The trust result must be reachable by the product's registered semantic
  discovery database so registry-driven consumers (e.g. the Data Product
  Browser) find `trust_engine_latest` without convention-guessing.

---

## 8. Check Sources from Other Standards

Validator profiles on Teradata should lift, at minimum:

| Source | Checks | Category / severity guidance |
|--------|--------|------------------------------|
| Temporal & Lifecycle Metadata Extension §9 | TLM-04/05/06 dictionary checks; TLM-08/09/10/11 data invariants | STRUCTURAL / blocking rules as CRITICAL |
| Semantic Module Standard §3.6 | Orphan modules, missing objects, invalid roles, kind mismatches, duplicate registrations | SEMANTIC / STRUCTURAL, ERROR–CRITICAL |
| Object Placement Standard | Container and naming conformance | STRUCTURAL, WARNING–ERROR |
| Observability evidence | Freshness, lineage and quality evidence objects deployed and populated | OPERATIONAL |

Issue codes introduced for these checks must be catalogued with their
object-identifying keys per core §6 rule 5 before first publication.
