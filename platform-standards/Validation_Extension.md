# Data Product Validation Extension — Teradata
## AI-Native Data Product Architecture — Version 1.0 (Draft)

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.0-draft |
| **Status** | DRAFT — Proposed (resolves issue #19 with `design-standards/Validation_Standard.md`) |
| **Last Updated** | 2026-07-16 |
| **Owner** | Worldwide Data Architecture Team, Teradata |
| **Scope** | Teradata binding of the Data Product Validation Standard |
| **Type** | Platform Extension (Teradata) |
| **Wire schema** | 1.1 (canonical, Observability); 1.0 legacy binding (Semantic) documented in §5 |

---

## Table of Contents

1. [Physical Model](#1-physical-model)
2. [Publish Semantics](#2-publish-semantics)
3. [Latest-Run and Gate Views](#3-latest-run-and-gate-views)
4. [Type Bindings](#4-type-bindings)
5. [Legacy Binding — Wire Schema 1.0](#5-legacy-binding--wire-schema-10)
6. [Consumer Queries](#6-consumer-queries)
7. [Conformance Queries](#7-conformance-queries)
8. [Placement and Layer Alignment](#8-placement-and-layer-alignment)
9. [Check Sources from Other Standards](#9-check-sources-from-other-standards)

---

## 1. Physical Model

Validation results are operational evidence and live in the
**Observability module**, alongside its other run/event tables. One history
table plus consumer views:

```sql
CREATE MULTISET TABLE {Product}_OBS_STD_T.validation_run
(
    product_prefix VARCHAR(128) CHARACTER SET LATIN NOT NULL,

    -- Producer identity (canonical schema 1.1)
    producer_id VARCHAR(64) CHARACTER SET LATIN NOT NULL,
    producer_version VARCHAR(32) CHARACTER SET LATIN,
    profile_id VARCHAR(64) CHARACTER SET LATIN,
    profile_version VARCHAR(32) CHARACTER SET LATIN,
    source_format VARCHAR(20) CHARACTER SET LATIN NOT NULL DEFAULT 'NATIVE',
    payload_schema_version VARCHAR(8) CHARACTER SET LATIN NOT NULL DEFAULT '1.1',

    -- Run identity
    run_id VARCHAR(64) CHARACTER SET LATIN NOT NULL,
    started_at VARCHAR(40) CHARACTER SET LATIN NOT NULL,
    completed_at VARCHAR(40) CHARACTER SET LATIN NOT NULL,

    -- Gate result
    trust_status VARCHAR(16) CHARACTER SET LATIN NOT NULL,
    agent_use_allowed BYTEINT NOT NULL CHECK (agent_use_allowed IN (0, 1)),

    -- Check totals (status axis) and gate counts (severity axis)
    total_checks INTEGER NOT NULL,
    passed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    critical_failure_count INTEGER NOT NULL,
    error_failure_count INTEGER NOT NULL,

    -- Scores (null = not assessed)
    data_product_trust_score INTEGER,
    performance_readiness_score INTEGER,
    operational_readiness_score INTEGER,

    -- Detail (capped; true totals in the count columns)
    repair_candidate_count INTEGER NOT NULL,
    failed_checks_json JSON(32000) CHARACTER SET UNICODE,
    repair_candidates_json JSON(32000) CHARACTER SET UNICODE,

    -- Evidence expiry (null = product/consumer default window applies)
    evidence_expires_at VARCHAR(40) CHARACTER SET LATIN,

    -- Row audit (Temporal & Lifecycle Metadata Standard, EVENT_APPEND_ONLY)
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_prefix, completed_at);
```

Column comments are required on deployment per the naming conventions; the
table declares temporal profile `EVENT_APPEND_ONLY` in
`entity_metadata.temporal_pattern`. Statistics:

```sql
COLLECT STATISTICS
      COLUMN (product_prefix)
    , COLUMN (producer_id)
    , COLUMN (product_prefix, producer_id)
    , COLUMN (product_prefix, completed_at)
ON {Product}_OBS_STD_T.validation_run;
```

A 1:1 locking view exposes the table in `{Product}_OBS_STD_V` per the
standard view-layer rule.

---

## 2. Publish Semantics

- **Append, never replace.** Each validation run INSERTs exactly one row;
  the table accumulates run history as evidence (core §2, VAL-09). This
  holds for every producer.
- `run_id` is deterministic: the first 32 hex characters of a SHA-256 over
  `prefix|producer_id|started_at|completed_at|result_count` — replaying
  the same run yields the same identifier.
- JSON blobs are serialised compact with sorted keys, item caps applied
  (20 checks × 3 sample rows; 20 repair candidates), then truncated to the
  column's 32000-character limit. Authoritative totals are the count
  columns, never the blobs.
- Ingested results (JUnit XML, CTRF, SARIF — core §12) are loaded by
  validation tooling with `source_format` set accordingly and the loader
  recorded as `producer_id`.

---

## 3. Latest-Run and Gate Views

The consumer surface is a latest-per-(product, producer) projection:

```sql
REPLACE VIEW {Product}_OBS_ACS_V.validation_latest
AS
LOCKING ROW FOR ACCESS
SELECT
      product_prefix
    , producer_id
    , producer_version
    , profile_id
    , profile_version
    , source_format
    , payload_schema_version
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
    , evidence_expires_at
FROM {Product}_OBS_STD_T.validation_run
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY product_prefix, producer_id
    ORDER BY completed_at DESC, run_id DESC
) = 1;
```

The deterministic tie-break (`completed_at DESC, run_id DESC`) is part of
the contract (VAL-09). The **product-level gate** is the row whose
`producer_id` matches the gate-authoritative producer designated in the
product's orientation metadata (core §8.1); other rows are evidence.

---

## 4. Type Bindings

| Contract element | Binding | Note |
|------------------|---------|------|
| `started_at` / `completed_at` / `evidence_expires_at` | `VARCHAR(40)` ISO-8601 | Retained from wire schema 1.0 so one consumer parser serves both bindings; migration to `TIMESTAMP(6) WITH TIME ZONE` is an **incompatible** change reserved for wire schema 2.0 |
| `agent_use_allowed` | `BYTEINT` 0/1, CHECK-constrained | Platform flag convention |
| Scores | `INTEGER` nullable | Null = not assessed, never 100 |
| JSON blobs | `JSON(32000) CHARACTER SET UNICODE` | Cap discipline in §2 |
| `created_dts` / `updated_dts` | `TIMESTAMP(6) WITH TIME ZONE`, UTC | Row audit per the Temporal & Lifecycle Metadata Extension; distinct from the run's business timestamps |

---

## 5. Legacy Binding — Wire Schema 1.0

Deployments of wire schema 1.0 publish the same status, count, score, and
JSON-blob columns **without** the producer-identity, `source_format`,
`payload_schema_version`, `evidence_expires_at`, or audit columns, under
producer-specific object names in the **Semantic** module:

```text
{Product}_SEM_STD_T.trust_engine_run       (history table)
{Product}_SEM_BUS_V.trust_engine_latest    (latest view; ACL_V also a
                                            registered layer alias)
PRIMARY INDEX (product_prefix, completed_at)
```

Consumer rules for the legacy binding:

- Treat every 1.0 record as having an implied single producer, which is
  also the gate-authoritative producer.
- Resolve the object location through product orientation metadata — never
  by guessing module or layer suffixes.
- Migration to the canonical binding is a re-publish, not a rename: the
  producer starts inserting into `{Product}_OBS_STD_T.validation_run`
  (with its identity columns populated) and orientation metadata is
  repointed; the legacy objects retire on the product's compatibility
  schedule.

---

## 6. Consumer Queries

Product gate check before analytical use (`:gate_producer` comes from
orientation metadata):

```sql
SELECT v.trust_status
     , v.agent_use_allowed
     , v.completed_at
     , v.evidence_expires_at
     , v.critical_failure_count
     , v.error_failure_count
     , v.data_product_trust_score
FROM {Product}_OBS_ACS_V.validation_latest AS v
WHERE v.product_prefix = :product_prefix
  AND v.producer_id = :gate_producer;
```

Consumer rules (core §8, §10): a missing gate row means *unvalidated* —
stop for autonomous use; a row past `evidence_expires_at` (or older than
the applicable window, default 7 days from `completed_at`) is stale — treat
as `agent_use_allowed = 0`; never recount the JSON blobs; never proceed on
`UNTRUSTED`.

All-producer evidence summary:

```sql
SELECT v.producer_id
     , v.producer_version
     , v.source_format
     , v.trust_status
     , v.agent_use_allowed
     , v.completed_at
     , v.total_checks
     , v.failed_count
FROM {Product}_OBS_ACS_V.validation_latest AS v
WHERE v.product_prefix = :product_prefix
ORDER BY v.producer_id;
```

Run-history trend (auditors):

```sql
SELECT r.producer_id
     , r.completed_at
     , r.trust_status
     , r.data_product_trust_score
     , r.critical_failure_count
     , r.error_failure_count
     , r.failed_count
FROM {Product}_OBS_STD_V.validation_run AS r
WHERE r.product_prefix = :product_prefix
ORDER BY r.completed_at DESC;
```

---

## 7. Conformance Queries

```sql
-- VAL-01/02: vocabulary and status/decision agreement
SELECT run_id, producer_id, trust_status, agent_use_allowed
FROM {Product}_OBS_STD_V.validation_run
WHERE trust_status NOT IN ('TRUSTED', 'DEGRADED', 'UNTRUSTED')
   OR (trust_status IN ('TRUSTED', 'DEGRADED') AND agent_use_allowed <> 1)
   OR (trust_status = 'UNTRUSTED' AND agent_use_allowed <> 0);

-- VAL-04: check totals reconcile
SELECT run_id, producer_id, total_checks, passed_count, failed_count, error_count
FROM {Product}_OBS_STD_V.validation_run
WHERE total_checks <> passed_count + failed_count + error_count;

-- VAL-06: score ranges
SELECT run_id, producer_id
FROM {Product}_OBS_STD_V.validation_run
WHERE data_product_trust_score    NOT BETWEEN 0 AND 100
   OR performance_readiness_score NOT BETWEEN 0 AND 100
   OR operational_readiness_score NOT BETWEEN 0 AND 100;

-- VAL-12: producer identity present (canonical schema)
SELECT run_id
FROM {Product}_OBS_STD_V.validation_run
WHERE producer_id IS NULL
   OR TRIM(producer_id) = ''
   OR payload_schema_version IS NULL;

-- Deployment: the latest view yields one row per (product, producer)
SELECT product_prefix, producer_id, COUNT(*) AS rows_seen
FROM {Product}_OBS_ACS_V.validation_latest
GROUP BY product_prefix, producer_id
HAVING COUNT(*) > 1;
```

---

## 8. Placement and Layer Alignment

- History table: Observability module, `{Product}_OBS_STD_T`, with the
  mandatory 1:1 locking view in `{Product}_OBS_STD_V`.
- Latest view: the Access Layer — `{Product}_OBS_ACS_V` for new products
  per the Temporal & Lifecycle Metadata Extension's `ACS_V` adoption
  (`BUS_V` / `ACL_V` are registered legacy aliases for the layer).
- The gate must be reachable through the product's orientation metadata
  (issue #20) so registry-driven consumers (catalogue and browser tooling)
  find it — and the designated gate producer — without convention-guessing.
- Validation results sit alongside the module's other evidence
  (`data_quality_metric`, `lineage_run`, `model_performance`): one module
  answers "what has been observed about this product?".

---

## 9. Check Sources from Other Standards

Validator profiles on Teradata should lift, at minimum:

| Source | Checks | Category / severity guidance |
|--------|--------|------------------------------|
| Temporal & Lifecycle Metadata Extension §9 | TLM-04/05/06 dictionary checks; TLM-08/09/10/11 data invariants | STRUCTURAL / blocking rules as CRITICAL |
| Semantic Module Standard §3.6 | Orphan modules, missing objects, invalid roles, kind mismatches, duplicate registrations | SEMANTIC / STRUCTURAL, ERROR–CRITICAL |
| Object Placement Standard | Container and naming conformance | STRUCTURAL, WARNING–ERROR |
| Observability evidence | Freshness, lineage and quality evidence objects deployed and populated | OPERATIONAL |

Issue codes introduced for these checks must be catalogued with their
object-identifying keys per core §6 rule 5 before first publication.
