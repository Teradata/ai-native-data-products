# Data Product Validation Results & Trust Gate Standard
## AI-Native Data Product Architecture — Version 1.0 (Draft)

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.0-draft |
| **Status** | DRAFT — Proposed (resolves issue #19) |
| **Last Updated** | 2026-07-15 |
| **Owner** | Worldwide Data Architecture Team, Teradata |
| **Scope** | Machine-readable validation results and the agent stop/go trust gate for every data product |
| **Type** | Design Standard (Core, RDBMS-neutral) |
| **Module home** | Observability (validation results are operational evidence) |
| **Platform bindings** | `platform-standards/Trust_Gate_Extension.md` |
| **Wire schema** | 1.1 (canonical); 1.0 registered as a legacy binding |

This core standard defines one **producer-neutral validation-results
contract** with an authoritative trust gate. Any conformant producer can
populate it — an established unit-test harness, a simple validator, or a
full trust engine — and any consumer can evaluate a product's usability
from it. The gate semantics codify a production-proven contract (wire
schema 1.0) rather than a green-field design; a reader can implement
either side (producer or consumer) from this document and its platform
binding alone.

---

## Table of Contents

1. [Purpose and Principles](#1-purpose-and-principles)
2. [The Validation Result](#2-the-validation-result)
3. [Status Vocabulary and Decision Semantics](#3-status-vocabulary-and-decision-semantics)
4. [Severity Model](#4-severity-model)
5. [Readiness Scores](#5-readiness-scores)
6. [Failed Checks Contract](#6-failed-checks-contract)
7. [Repair Candidates Contract](#7-repair-candidates-contract)
8. [Consumption Contract and Gate Authority](#8-consumption-contract-and-gate-authority)
9. [Schema Versioning and Evolution](#9-schema-versioning-and-evolution)
10. [Staleness and Incomplete Evidence](#10-staleness-and-incomplete-evidence)
11. [Check Identity and Categories](#11-check-identity-and-categories)
12. [Open Standards Alignment (non-normative)](#12-open-standards-alignment-non-normative)
13. [Conformance Rules](#13-conformance-rules)
14. [Relationship to Other Standards](#14-relationship-to-other-standards)

---

## 1. Purpose and Principles

Rules and checklists alone give an agent nothing it can evaluate before
querying a product. Without a standard validation *result* and an explicit
gate, agents may use structurally invalid or operationally unsafe products,
aggregate scores can hide critical failures, and repair candidates have no
portable representation. This standard defines that result and gate.

Principles:

1. **One results contract, many producers.** Unit-test harnesses,
   repository validation tooling, and trust engines all publish into the
   same record shape, distinguished by producer identity — a product's
   validation history is queryable regardless of what produced it.
2. **Trust is computed by a validator, only.** Consumers are read-only:
   they render and act on published results and never re-derive a verdict
   from raw evidence.
3. **The stop/go decision is authoritative and singular.** Each product
   designates one gate-authoritative producer (§8); its latest result's
   `agent_use_allowed` is a decision, not advice. Critical failures block
   use regardless of any aggregate score, and consumers must not silently
   override a blocked status.
4. **Validation results are operational evidence** and live in the
   **Observability module** — the module responsible for event tracking,
   quality monitoring, and lineage. They are append-only event records
   (Temporal & Lifecycle Metadata Standard profile `EVENT_APPEND_ONLY`).

---

## 2. The Validation Result

One logical record per product per producer per validation run; consumers
read the **latest** record per (product, producer). Portable fields
(physical types bind per platform extension):

| Field | Meaning |
|-------|---------|
| `product_prefix` | Product identity the run evaluated |
| `producer_id` | Identity of the producing validator/harness |
| `producer_version` | Version of the producer |
| `profile_id`, `profile_version` | Decision/check profile the run evaluated (nullable for simple harnesses) |
| `source_format` | Provenance of the result: `NATIVE`, or the interchange format it was ingested from (§12) |
| `payload_schema_version` | Wire schema version of this record |
| `run_id` | Deterministic run identifier |
| `started_at`, `completed_at` | Run timestamps (ISO-8601) |
| `trust_status` | `TRUSTED` \| `DEGRADED` \| `UNTRUSTED` (§3) |
| `agent_use_allowed` | Stop/go decision for this producer's suite: `1` = go, `0` = stop |
| `total_checks`, `passed_count`, `failed_count`, `error_count` | Check totals by **status** (§4) |
| `critical_failure_count`, `error_failure_count` | Gate counts by **severity** among failed/errored checks (§4) |
| `data_product_trust_score` | Conformance score, 0–100 or null (§5) |
| `performance_readiness_score` | Performance dimension, 0–100 or null (§5) |
| `operational_readiness_score` | Operational dimension, 0–100 or null (§5) |
| `repair_candidate_count` | True (uncapped) number of repair candidates |
| `failed_checks_json` | Machine-readable failure detail, capped (§6) |
| `repair_candidates_json` | Machine-readable repair proposals, capped (§7) |
| `evidence_expires_at` | Producer-declared expiry of this evidence (nullable; §10) |

A simple test harness populates the identity, status, and count fields and
leaves scores, JSON blobs, and profile fields null — that is a fully
conformant result. Runs are **appended**, never overwritten: run history is
evidence; the latest-per-(product, producer) projection is the consumer
surface.

---

## 3. Status Vocabulary and Decision Semantics

`trust_status` has exactly three values: **`TRUSTED`**, **`DEGRADED`**,
**`UNTRUSTED`**.

The **default decision profile** (rules evaluated in order):

1. Any execution error (`error_count > 0`), any CRITICAL-severity failure,
   or any ERROR-severity failure → `UNTRUSTED`. **The severity gate is
   absolute — no score can rescue it.**
2. Else `data_product_trust_score < 70` → `UNTRUSTED`.
3. Else any failed check, or `data_product_trust_score < 90` → `DEGRADED`.
4. Else → `TRUSTED`.

Producers that compute no scores skip rules 2 and 3's score clauses — the
profile degrades gracefully to pure status/severity gating.

`agent_use_allowed` derives purely from status:

```text
agent_use_allowed = 1  when trust_status IN (TRUSTED, DEGRADED)
agent_use_allowed = 0  when trust_status = UNTRUSTED
```

Rules for the decision:

- Readiness dimensions remain independent: only
  `data_product_trust_score` participates in the threshold rules; the
  performance and operational scores are published evidence (§5). Their
  *checks* still gate through severities in rule 1.
- Implementation profiles may **tighten** the default profile (e.g. gate on
  operational readiness, raise thresholds) but must never loosen it: a
  result the default profile would call `UNTRUSTED` must never be published
  as anything else.
- Consumers must not silently override a blocked status. Overrides are
  human decisions, logged, outside this contract.

---

## 4. Severity Model

Two independent axes, deliberately distinct:

- **Status** — what happened when the check ran: `PASSED` | `FAILED` |
  `ERROR` (the check itself could not execute).
- **Severity** — how much a failure matters: `INFO` | `WARNING` | `ERROR` |
  `CRITICAL`.

Count semantics:

| Field | Counts |
|-------|--------|
| `error_count` | Checks with **status** `ERROR` (execution errors) |
| `critical_failure_count` | Failed/errored checks with **severity** `CRITICAL` |
| `error_failure_count` | Failed/errored checks with **severity** `ERROR` |
| `failed_count` | Checks with status `FAILED`, any severity |

`WARNING` and `INFO` severity failures feed `failed_count` but not the gate
counts — they can produce `DEGRADED`, never `UNTRUSTED`.

Producers whose native format carries no severity (plain unit-test output)
default failed checks to severity `ERROR` unless an ingest mapping (§12)
assigns severities by rule.

The three gate counts (`error_count`, `critical_failure_count`,
`error_failure_count`) are **authoritative**: the JSON blobs are capped
(§6, §7) and must never be counted by consumers.

---

## 5. Readiness Scores

Scores are **optional**: producers that do not compute them publish null,
which means *not assessed*, never *perfect*.

Where computed, each score is a severity-weighted pass rate over its check
family: `round(earned / total × 100)` where a check's weight is
CRITICAL = 40, ERROR = 25, WARNING = 10, INFO = 5; `earned` sums the
weights of passed checks. Range 0–100 integer, or null when no checks in
that family ran.

| Score | Check categories |
|-------|-----------------|
| `data_product_trust_score` | STRUCTURAL, SEMANTIC, QUERY, CAPABILITY, DATA_QUALITY, FREE_TEXT |
| `performance_readiness_score` | PERFORMANCE |
| `operational_readiness_score` | OPERATIONAL |

Only `data_product_trust_score` participates in the default decision
profile's thresholds (§3). Conformance, performance readiness, and
operational readiness are reported separately and must not be blended into
a single number.

---

## 6. Failed Checks Contract

`failed_checks_json` is an array of failed/errored check records, **capped
at 20 items**; each item's `sample_rows` is **capped at 3 rows**. Item
shape:

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
      "repair_hint": "Register the column in column_metadata with a business description."
    }
  ],
  "error_message": null,
  "repair_strategy": "Backfill column_metadata for every deployed column of the entity."
}
```

Contract rules:

1. The check-level identifier is **`test_id`**. `issue_code` exists only
   **inside `sample_rows` elements** — one check can surface multiple issue
   codes.
2. `sample_rows` elements are per-`issue_code` shapes, but every element
   carries at least `issue_code` and `repair_hint`, plus the issue code's
   documented object-identifying keys (the offender vocabulary) so a
   consumer can answer "which objects?".
3. `row_count` is the **true** total for the check; `sample_rows` holds the
   first ≤ 3 examples. Consumers render the remainder as
   `+ (row_count − shown) more`, never by counting the blob.
4. `error_message` is non-null only for status `ERROR`.
5. Every issue code and its identifying keys are catalogued in the
   producer's contract documentation; introducing an issue code without a
   catalogue entry is a producer conformance failure.
6. The blob is optional for simple producers (null when the producer emits
   counts only).

---

## 7. Repair Candidates Contract

`repair_candidates_json` is an array of repair proposals, **capped at 20
items**; the true total is `repair_candidate_count`. Item shape:

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

- `mode` domain: `detect` | `proposal` | `safe-auto`.
- `requires_approval = true` candidates must never be executed
  autonomously. A consumer executing any repair SQL does so under its own
  change-management controls; the candidate is a proposal, not an
  instruction.
- Optional for producers that propose no repairs
  (`repair_candidate_count = 0`, blob null).

---

## 8. Consumption Contract and Gate Authority

### 8.1 Gate authority

Multiple producers may publish results for one product. To keep the stop/go
decision singular and auditable:

- Each product **designates exactly one gate-authoritative producer** in
  its orientation metadata (issue #20).
- The product-level gate is the designated producer's latest result:
  its `agent_use_allowed` and `trust_status`.
- Results from all other producers are **evidence**: consumers may surface
  them (and should surface disagreements), but they do not move the gate.
- Absent a designation, consumers apply the conservative composite: the
  product gate is blocked if **any** producer's latest result blocks, and
  the staleness rules of §10 apply per producer.

### 8.2 Consumer rules

1. Read the gate **before** analytical use; discover the result's location
   and the designated producer through product orientation (issue #20).
2. `agent_use_allowed = 0` (or `trust_status = 'UNTRUSTED'`) on the gate is
   a stop signal for autonomous use. No silent overrides.
3. `DEGRADED` permits use; consumers should surface the degradation and the
   failing checks to their users.
4. Never re-derive verdicts from raw evidence; never recount from the
   capped JSON blobs (§4).
5. Treat unknown JSON keys as additive extension — ignore, don't fail (§9).
6. Apply the staleness rules of §10.

---

## 9. Schema Versioning and Evolution

- Every record carries `payload_schema_version`. The canonical version
  defined by this standard is **`1.1`**.
- **Wire schema `1.0`** is the registered legacy binding: the same status,
  count, score, and JSON-blob fields, without the producer-identity,
  `source_format`, `payload_schema_version`, or `evidence_expires_at`
  fields, published under producer-specific object names in the Semantic
  module (platform extension, Legacy Binding section). Consumers treat a
  1.0 record as having an implied single producer.
- Any incompatible change to the result fields or the two JSON blob shapes
  bumps the major version. Additive optional fields are compatible within
  a major version; consumers ignore unknown fields.
- Producer and consumer are held together by a **shared golden fixture**:
  the producer generates it from its contract module, the consumer vendors
  it into its test suite, and both build gates fail on drift. A version
  bump regenerates the fixture and updates both sides in one coordinated
  change.

---

## 10. Staleness and Incomplete Evidence

1. **Evidence window.** A producer may declare expiry per record
   (`evidence_expires_at`); a product may declare a maximum evidence age in
   its orientation metadata. Absent both, consumers apply a default window
   of **7 days** from `completed_at`.
2. **Stale evidence** (gate result older than the window / past expiry):
   autonomous consumers must treat the product as if
   `agent_use_allowed = 0`, whatever the recorded status says. Interactive
   consumers must surface the staleness prominently.
3. **No evidence** (no gate result exists): the product is *unvalidated*,
   not trusted-by-default. Autonomous consumers must not proceed;
   interactive consumers surface "no trust evidence".
4. **Incomplete evidence** (result present but `total_checks = 0`, or
   unparseable): treat as no evidence.

Conservative outcomes never loosen: staleness can only downgrade a
decision, never upgrade one.

---

## 11. Check Identity and Categories

- **`test_id` scheme:** `{PRODUCT-PREFIX}-{FAMILY}-{NNN}` (e.g.
  `CALLCENTRE-SEM-008`); parameterised checks may extend the suffix (e.g.
  `{PREFIX}-QUERY-BOUNDS-{RECIPE_ID}`). Stable across runs so consumers can
  track a check through history. Ingested results (§12) map their native
  test identity into this scheme deterministically.
- **Categories** (drive score families, §5): `STRUCTURAL`, `SEMANTIC`,
  `QUERY`, `CAPABILITY`, `PERFORMANCE`, `OPERATIONAL`, `DATA_QUALITY`,
  `FREE_TEXT`.
- Validators consume the product's **self-describing metadata** (semantic
  catalogue, orientation manifest, relationship metadata, cookbook,
  observability evidence) and prove those claims against what is physically
  deployed. Other standards supply check sources: the Temporal & Lifecycle
  Metadata Standard's TLM-01..17 rules (blocking rules → CRITICAL/ERROR
  severity) and the Semantic module's primary-object validations (issue
  #14) are designed to be lifted directly into validator profiles.

---

## 12. Open Standards Alignment (non-normative)

The validation result is deliberately mappable from, and to, established
open formats. `source_format` records the provenance of ingested results.

| Standard | Layer | Mapping posture |
|----------|-------|-----------------|
| **JUnit XML** (de-facto) | Test execution results | Ingest: `testsuite`/`testcase` totals → status counts; failures default to severity `ERROR` unless mapped. `source_format = 'JUNIT-XML'` |
| **CTRF** (community JSON standard) | Test execution results | Ingest: `summary` + `tests[]` → status counts and optional check detail. `source_format = 'CTRF'` |
| **Open Test Reporting** (JUnit team) | Test execution results | Ingest when consumer-side adoption matures. `source_format = 'OTR'` |
| **SARIF 2.1.0** (OASIS Standard) | Check/analysis results | Closest semantic match: `ruleId` ↔ `test_id`, `level` ↔ severity, `fixes[]` ↔ repair candidates, `tool.driver` ↔ producer identity. `source_format = 'SARIF'` |
| **OpenLineage** `DataQualityAssertionsDatasetFacet` | Emission | Validation runs may additionally emit per-assertion facets on lineage run events — consistent with the Observability module's OpenLineage alignment |
| **ODCS / ODPS** | Check definitions (contract side) | Declarative quality rules and SLAs in the product contract *define* checks; results land here, linked through `test_id` |

Ingest mappings are implemented by validation tooling, not by this
standard; the fields above ensure the record can carry them without schema
change.

---

## 13. Conformance Rules

For producers and consumers of this contract:

| Rule | Check |
|------|-------|
| TGS-01 | `trust_status` is exactly one of the three vocabulary values. |
| TGS-02 | `agent_use_allowed` agrees with `trust_status` per §3. |
| TGS-03 | The default decision profile is never loosened. |
| TGS-04 | `total_checks = passed_count + failed_count + error_count`. |
| TGS-05 | Gate counts are consistent with the severity model (§4). |
| TGS-06 | Scores are 0–100 integers or null; null only when not assessed. |
| TGS-07 | JSON blobs respect their caps; true totals live in `row_count` / `repair_candidate_count`. |
| TGS-08 | Every `sample_rows` element carries `issue_code` and `repair_hint`; every issue code is catalogued with its identifying keys. |
| TGS-09 | Runs are appended; the latest-per-(product, producer) projection is deterministic (`completed_at`, then `run_id`). |
| TGS-10 | Consumers apply §10 staleness outcomes; no silent override of a blocked gate. |
| TGS-11 | Producer and consumer build gates verify the shared golden fixture at the declared schema version. |
| TGS-12 | Every record carries non-null `producer_id` and `payload_schema_version` (canonical schema). |
| TGS-13 | The gate is taken only from the designated gate-authoritative producer (§8.1); absent designation, the conservative composite applies. |

---

## 14. Relationship to Other Standards

- **Observability Module Standard** — the module home for validation
  results, alongside its other run/event evidence tables.
- **Issue #16 / #10** — this document follows the core/extension
  governance boundary; its file placement moves when the repository
  restructure is agreed.
- **Issue #17 (Temporal & Lifecycle Metadata Standard)** — the results
  table declares profile `EVENT_APPEND_ONLY`; TLM blocking rules are
  canonical CRITICAL/ERROR check sources for validators.
- **Issue #14 (primary object discovery)** — its validation queries are
  canonical STRUCTURAL/SEMANTIC check sources.
- **Issue #20 (orientation/manifest)** — orientation declares the results
  location and the gate-authoritative producer; trust evaluation precedes
  analytical resource use in the discovery order.
- **Teradata binding** — `platform-standards/Trust_Gate_Extension.md`.
