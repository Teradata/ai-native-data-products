# Validation — Pattern

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Pattern (cross-cutting, platform-agnostic) |
| **Scope** | Machine-readable validation results and the agent stop/go gate for every product |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Module home** | [Observability](../modules/observability.md) — validation results are operational evidence |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Wire schema** | 2.0 (canonical); 1.0 registered as a legacy binding |
| **Implementations** | [`implementation/teradata/patterns/validation/`](../../implementation/teradata/patterns/validation/) |

This pattern defines the **validation result contract** and the **gate** an agent evaluates before
using a product. Each module and pattern contributes *conformance checks* — its invariants, the
temporal `TLM-01..17` rules, the Semantic primary-object validations — which validators execute and
publish as results in this contract. Results are append-only operational evidence in the
Observability module (temporal profile `EVENT_APPEND_ONLY`).

---

## 1. Purpose and Principles

An agent needs a published validation *result* and an explicit gate to evaluate a product before
querying it. This pattern defines both.

1. **One results contract, many producers.** A unit-test harness, a simple validator, or a full
   trust engine all publish the same record shape, distinguished by `producer_id`.
2. **Trust is computed by a validator, only.** Consumers are read-only: they act on published
   results and never re-derive a verdict from raw evidence.
3. **The stop/go decision is authoritative and singular.** Each product designates one
   gate-authoritative producer (§8); its latest `agent_use_allowed` is a decision, not advice.
   Critical failures block use regardless of any score.
4. **Validation results are operational evidence** — append-only event records in Observability.

---

## 2. The Validation Result

One logical record per product per producer per run; consumers read the **latest** per
(product, producer). Physical types bind per implementation.

| Field | Meaning |
|-------|---------|
| `product_prefix` | Product identity the run evaluated |
| `producer_id`, `producer_version` | Identity and version of the producing validator/harness |
| `profile_id`, `profile_version` | Decision/check profile evaluated (nullable for simple harnesses) |
| `source_format` | Provenance: `NATIVE`, or the interchange format it was ingested from (§12) |
| `payload_schema_version` | Wire schema version of this record |
| `run_id` | Deterministic run identifier |
| `started_dts`, `completed_dts` | Run instants (typed timestamps, persisted UTC) |
| `trust_status` | `TRUSTED` \| `DEGRADED` \| `UNTRUSTED` (§3) |
| `agent_use_allowed` | Stop/go decision: go / stop |
| `total_checks`, `passed_count`, `failed_count`, `error_count` | Check totals by **status** (§4) |
| `critical_failure_count`, `error_failure_count` | Gate counts by **severity** among failed/errored checks (§4) |
| `data_product_trust_score` | Conformance score, 0–100 or null (§5) |
| `performance_readiness_score`, `operational_readiness_score` | Other score dimensions, 0–100 or null (§5) |
| `repair_candidate_count` | True (uncapped) number of repair candidates |
| `failed_checks_json` | Machine-readable failure detail, capped (§6) |
| `repair_candidates_json` | Machine-readable repair proposals, capped (§7) |
| `evidence_expires_dts` | Producer-declared expiry of this evidence (nullable; §10) |

A simple test harness populates the identity, status, and count fields and leaves scores, JSON
blobs, and profile fields null — a fully conformant result. Runs are **appended**, never overwritten.

---

## 3. Status Vocabulary and Decision Semantics

`trust_status` has exactly three values: **`TRUSTED`**, **`DEGRADED`**, **`UNTRUSTED`**.

**Default decision profile** (rules in order):

1. Any execution error (`error_count > 0`), any CRITICAL-severity failure, or any ERROR-severity
   failure → `UNTRUSTED`. **No score can rescue this rule.**
2. Else `data_product_trust_score < 70` → `UNTRUSTED`.
3. Else any failed check, or `data_product_trust_score < 90` → `DEGRADED`.
4. Else → `TRUSTED`.

Producers that compute no scores skip the score clauses. `agent_use_allowed` derives purely from
status:

```text
agent_use_allowed = go    when trust_status IN (TRUSTED, DEGRADED)
agent_use_allowed = stop  when trust_status = UNTRUSTED
```

Implementation profiles may **tighten** the default profile but never loosen it. Consumers must not
silently override a blocked status; overrides are logged human decisions, outside this contract.

---

## 4. Severity Model

Two independent axes:

- **Status** — what happened when the check ran: `PASSED` | `FAILED` | `ERROR` (could not execute).
- **Severity** — how much a failure matters: `INFO` | `WARNING` | `ERROR` | `CRITICAL`.

| Field | Counts |
|-------|--------|
| `error_count` | Checks with **status** `ERROR` |
| `critical_failure_count` | Failed/errored checks with **severity** `CRITICAL` |
| `error_failure_count` | Failed/errored checks with **severity** `ERROR` |
| `failed_count` | Checks with status `FAILED`, any severity |

`WARNING`/`INFO` failures feed `failed_count` but not the gate counts — they can produce `DEGRADED`,
never `UNTRUSTED`. Producers whose native format carries no severity default failed checks to
`ERROR`. The three gate counts are **authoritative**; the JSON blobs are capped and must never be
counted by consumers.

---

## 5. Readiness Scores

Scores are **optional**: null means *not assessed*, never *perfect*. Where computed, each score is a
severity-weighted pass rate over its check family: `round(earned / total × 100)` with weights
CRITICAL = 40, ERROR = 25, WARNING = 10, INFO = 5; `earned` sums the weights of passed checks.

| Score | Check categories |
|-------|-----------------|
| `data_product_trust_score` | STRUCTURAL, SEMANTIC, QUERY, CAPABILITY, DATA_QUALITY, FREE_TEXT |
| `performance_readiness_score` | PERFORMANCE |
| `operational_readiness_score` | OPERATIONAL |

Only `data_product_trust_score` participates in the default profile's thresholds (§3). The three
scores are reported separately and must not be blended.

---

## 6. Failed Checks Contract

`failed_checks_json` is an array of failed/errored check records, **capped at 20 items**; each
item's `sample_rows` is **capped at 3 rows**. Item shape:

```json
{
  "test_id": "CALLCENTRE-SEM-004",
  "name": "Curated column metadata covers deployed columns",
  "category": "SEMANTIC",
  "severity": "CRITICAL",
  "status": "FAILED",
  "row_count": 39,
  "sample_rows": [
    {
      "entity_name": "Agent",
      "column_name": "agent_status",
      "issue_code": "MISSING_COLUMN_METADATA",
      "repair_hint": "Register the column in the Semantic column metadata with a business description."
    }
  ],
  "error_message": null,
  "repair_strategy": "Backfill column metadata for every deployed column of the entity."
}
```

Rules: the check-level identifier is **`test_id`** (`issue_code` exists only inside `sample_rows`);
every `sample_rows` element carries `issue_code`, `repair_hint`, and the object-identifying keys;
`row_count` is the **true** total, `sample_rows` the first ≤ 3 — consumers render the remainder as
`+ (row_count − shown) more`, never by counting the blob; `error_message` is non-null only for
status `ERROR`; every issue code is catalogued in the producer's documentation; the blob is optional
for count-only producers.

---

## 7. Repair Candidates Contract

`repair_candidates_json` is an array of repair proposals, **capped at 20 items**; the true total is
`repair_candidate_count`. Item shape:

```json
{
  "candidate_id": "CALLCENTRE-STRUCT-001-COLUMN-TYPE-DRIFT",
  "issue_code": "COLUMN_TYPE_DRIFT",
  "summary": "Align datatype, length, precision and scale for same/similar columns.",
  "mode": "proposal",
  "requires_approval": true,
  "sql": "-- review and align column datatypes"
}
```

`mode` ∈ `detect` | `proposal` | `safe-auto`. `requires_approval = true` candidates must never be
executed autonomously — a candidate is a proposal, not an instruction; a consumer executing repair
does so under its own change-management controls. Optional when no repairs are proposed.

---

## 8. Consumption Contract and Gate Authority

**Gate authority.** Multiple producers may publish for one product; the decision stays singular. Each
product **designates exactly one gate-authoritative producer** in its orientation metadata. The
product-level gate is that producer's latest `agent_use_allowed` / `trust_status`. Other producers'
results are **evidence** — surfaced (especially disagreements) but not gate-moving. Absent a
designation, consumers apply the conservative composite: blocked if **any** producer's latest blocks.

**Consumer rules.** Read the gate **before** analytical use (discovering its location and the
designated producer through product orientation); `agent_use_allowed = stop` (or `UNTRUSTED`) is a
stop signal for autonomous use with no silent override; `DEGRADED` permits use but the degradation is
surfaced; never re-derive verdicts or recount capped blobs; treat unknown JSON keys as additive
extension (ignore, don't fail); apply the §10 staleness rules.

---

## 9. Schema Versioning and Evolution

Every record carries `payload_schema_version`; the canonical version is **`2.0`**. **Wire schema
`1.0`** is the registered legacy binding (the same status/count/score/JSON fields without the
producer-identity, `source_format`, `payload_schema_version`, or `evidence_expires_dts` fields);
consumers treat a 1.0 record as an implied single producer. Incompatible changes bump the major
version; additive optional fields are compatible within a major version. Producer and consumer are
held together by a **shared golden fixture** — both build gates fail on drift.

---

## 10. Staleness and Incomplete Evidence

1. **Evidence window.** A producer may declare per-record expiry; a product may declare a maximum
   evidence age in orientation. Absent both, the default window is **7 days** from `completed_dts`.
2. **Stale evidence** (past expiry / older than window): autonomous consumers treat the product as
   stop, whatever the recorded status; interactive consumers surface staleness prominently.
3. **No evidence**: the product is *unvalidated*, not trusted-by-default — autonomous consumers must
   not proceed.
4. **Incomplete evidence** (`total_checks = 0` or unparseable): treat as no evidence.

Staleness can only downgrade a decision, never upgrade one.

---

## 11. Check Identity and Categories

- **`test_id` scheme:** `{PRODUCT-PREFIX}-{FAMILY}-{NNN}` (e.g. `CALLCENTRE-SEM-008`); parameterised
  checks may extend the suffix. Stable across runs. Ingested results map their native identity into
  this scheme deterministically.
- **Categories** (drive score families): `STRUCTURAL`, `SEMANTIC`, `QUERY`, `CAPABILITY`,
  `PERFORMANCE`, `OPERATIONAL`, `DATA_QUALITY`, `FREE_TEXT`.
- Validators prove the product's **self-describing metadata** (semantic catalogue, orientation
  manifest, relationships, cookbook) against what is physically deployed. The temporal pattern's
  `TLM-01..17` rules (blocking → CRITICAL/ERROR) and the Semantic module's primary-object validations
  lift directly into validator profiles — as do each module's own `INV-*` invariant checks.

---

## 12. Open Standards Alignment (non-normative)

The result is mappable from/to established open formats; `source_format` records provenance. Ingest
mappings are implemented by validation tooling, not by this pattern.

| Standard | Layer | Mapping |
|----------|-------|---------|
| **JUnit XML** | Test results | `testsuite`/`testcase` totals → status counts; failures default to severity `ERROR`. `source_format = 'JUNIT-XML'` |
| **CTRF** | Test results | `summary` + `tests[]` → counts and optional detail. `source_format = 'CTRF'` |
| **Open Test Reporting** | Test results | Ingest as consumer adoption matures. `source_format = 'OTR'` |
| **SARIF 2.1.0** | Analysis results | `ruleId` ↔ `test_id`, `level` ↔ severity, `fixes[]` ↔ repair candidates. `source_format = 'SARIF'` |
| **OpenLineage** quality facet | Emission | Runs may additionally emit per-assertion facets on lineage run events |
| **ODCS / ODPS** | Check definitions | Contract-side quality rules *define* checks; results land here, linked through `test_id` |

---

## 13. Conformance Rules

| Rule | Check |
|------|-------|
| VAL-01 | `trust_status` is exactly one of the three vocabulary values. |
| VAL-02 | `agent_use_allowed` agrees with `trust_status` per §3. |
| VAL-03 | The default decision profile is never loosened. |
| VAL-04 | `total_checks = passed_count + failed_count + error_count`. |
| VAL-05 | Gate counts are consistent with the severity model (§4). |
| VAL-06 | Scores are 0–100 integers or null; null only when not assessed. |
| VAL-07 | JSON blobs respect their caps; true totals live in `row_count` / `repair_candidate_count`. |
| VAL-08 | Every `sample_rows` element carries `issue_code` and `repair_hint`; every issue code is catalogued. |
| VAL-09 | Runs are appended; the latest-per-(product, producer) projection is deterministic (`completed_dts`, then `run_id`). |
| VAL-10 | Consumers apply §10 staleness outcomes; no silent override of a blocked gate. |
| VAL-11 | Producer and consumer build gates verify the shared golden fixture at the declared schema version. |
| VAL-12 | Every record carries non-null `producer_id` and `payload_schema_version`. |
| VAL-13 | The gate is taken only from the designated producer (§8); absent designation, the conservative composite applies. |

---

## 14. Relationship to Other Standards

- **[Observability module](../modules/observability.md)** — the module home for validation results,
  alongside its other run/event evidence.
- **[Temporal & lifecycle metadata pattern](temporal-lifecycle-metadata.md)** — the results table
  declares profile `EVENT_APPEND_ONLY`; `TLM` blocking rules are canonical CRITICAL/ERROR checks.
- **[Semantic module](../modules/semantic.md)** — its primary-object validations are canonical
  STRUCTURAL/SEMANTIC checks; product orientation declares the results location and the
  gate-authoritative producer, so trust evaluation precedes analytical resource use.
- **Implementation** — the Teradata binding (results table, DBC/data checks, wire-schema bindings)
  lives in [`implementation/teradata/patterns/validation/`](../../implementation/teradata/patterns/validation/).

---

**End of Validation Pattern**
