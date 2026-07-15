# Data Product Trust Gate Standard
## AI-Native Data Product Architecture — Version 1.0 (Draft)

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.0-draft |
| **Status** | DRAFT — Proposed (resolves issue #19) |
| **Last Updated** | 2026-07-15 |
| **Owner** | Worldwide Data Architecture Team, Teradata |
| **Scope** | Machine-readable conformance result and agent stop/go contract for every data product |
| **Type** | Design Standard (Core, RDBMS-neutral) |
| **Platform bindings** | `platform-standards/Trust_Gate_Extension.md` |
| **Reference implementation** | `ai-native-data-product-trust-engine` (wire schema 1.0) |

This core standard codifies a **proven wire contract**: the trust result
defined by the ADP Trust Engine's payload schema `1.0` and its tested
producer/consumer contract. Where the standard extends beyond that schema
(validator identity, staleness), the extensions are explicitly additive and
versioned (§9).

---

## Table of Contents

1. [Purpose and Principles](#1-purpose-and-principles)
2. [The Trust Result](#2-the-trust-result)
3. [Status Vocabulary and Decision Semantics](#3-status-vocabulary-and-decision-semantics)
4. [Severity Model](#4-severity-model)
5. [Readiness Scores](#5-readiness-scores)
6. [Failed Checks Contract](#6-failed-checks-contract)
7. [Repair Candidates Contract](#7-repair-candidates-contract)
8. [Consumption Contract](#8-consumption-contract)
9. [Schema Versioning and Evolution](#9-schema-versioning-and-evolution)
10. [Staleness and Incomplete Evidence](#10-staleness-and-incomplete-evidence)
11. [Check Identity and Categories](#11-check-identity-and-categories)
12. [Conformance Rules](#12-conformance-rules)
13. [Relationship to Other Standards](#13-relationship-to-other-standards)

---

## 1. Purpose and Principles

Rules and checklists alone give an agent nothing it can evaluate before
querying a product. Without a standard conformance *result* and an explicit
gate, agents may use structurally invalid or operationally unsafe products,
aggregate scores can hide critical failures, and repair candidates have no
portable representation. This standard defines that result and gate.

Three principles govern this contract:

1. **Trust is computed by the validator, only.** Consumers are read-only:
   they render and act on the published result and must never re-derive a
   verdict from raw evidence. (Reference implementation ADR-0001.)
2. **The stop/go decision is authoritative.** `agent_use_allowed` is a
   decision, not advice. Critical failures block use regardless of any
   aggregate score, and consumers must not silently override a blocked
   status.
3. **A stop/go decision is more useful than a score alone.** Scores are
   published as graded evidence; the gate is binary.

---

## 2. The Trust Result

One logical record per product per validation run; consumers read the
**latest** record per product. Portable fields (physical types bind per
platform extension):

| Field | Meaning |
|-------|---------|
| `product_prefix` | Product identity the run evaluated |
| `run_id` | Deterministic run identifier |
| `started_at`, `completed_at` | Run timestamps (ISO-8601) |
| `trust_status` | `TRUSTED` \| `DEGRADED` \| `UNTRUSTED` (§3) |
| `agent_use_allowed` | Authoritative stop/go decision: `1` = go, `0` = stop |
| `total_checks`, `passed_count`, `failed_count`, `error_count` | Check totals by **status** (§4) |
| `critical_failure_count`, `error_failure_count` | Gate counts by **severity** among failed/errored checks (§4) |
| `data_product_trust_score` | Conformance score, 0–100 or null (§5) |
| `performance_readiness_score` | Performance dimension, 0–100 or null (§5) |
| `operational_readiness_score` | Operational dimension, 0–100 or null (§5) |
| `repair_candidate_count` | True (uncapped) number of repair candidates |
| `failed_checks_json` | Machine-readable failure detail, capped (§6) |
| `repair_candidates_json` | Machine-readable repair proposals, capped (§7) |

Runs are **appended**, never overwritten: the run history is evidence; the
"latest per product" projection is the consumer surface.

---

## 3. Status Vocabulary and Decision Semantics

`trust_status` has exactly three values: **`TRUSTED`**, **`DEGRADED`**,
**`UNTRUSTED`**.

The **default decision profile** (the reference implementation's rules,
evaluated in order):

1. Any execution error (`error_count > 0`), any CRITICAL-severity failure,
   or any ERROR-severity failure → `UNTRUSTED`. **The severity gate is
   absolute — no score can rescue it.**
2. Else `data_product_trust_score < 70` → `UNTRUSTED`.
3. Else any failed check, or `data_product_trust_score < 90` → `DEGRADED`.
4. Else → `TRUSTED`.

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
  result that the default profile would call `UNTRUSTED` must never be
  published as anything else.
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

The three gate counts (`error_count`, `critical_failure_count`,
`error_failure_count`) are **authoritative**: the JSON blobs are capped
(§6, §7) and must never be counted by consumers.

---

## 5. Readiness Scores

Each score is a severity-weighted pass rate over its check family:
`round(earned / total × 100)` where a check's weight is
CRITICAL = 40, ERROR = 25, WARNING = 10, INFO = 5; `earned` sums the
weights of passed checks. Range 0–100 integer, or **null when no checks in
that family ran** (null means *not assessed*, never *perfect*).

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
  "test_id": "CALLCENTRE-SEM-008",
  "name": "Entity metadata publishes access-layer view names",
  "category": "SEMANTIC",
  "severity": "CRITICAL",
  "status": "FAILED",
  "row_count": 39,
  "sample_rows": [
    {
      "entity_name": "Agent",
      "view_name": "CallCentre_DOM_BUS_V.Agent_Current",
      "issue_code": "ENTITY_VIEW_NAME_NOT_DEPLOYED",
      "repair_hint": "Deploy the access-layer view for agent access."
    }
  ],
  "error_message": null,
  "repair_strategy": "Populate entity_metadata.view_name and deploy the referenced views."
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
   validator's contract documentation; introducing an issue code without
   catalogue entry is a producer conformance failure.

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

---

## 8. Consumption Contract

1. Read the latest trust result for the product **before** analytical use;
   discoverability of the result is part of the product's orientation
   contract (issue #20).
2. `agent_use_allowed = 0` (or `trust_status = 'UNTRUSTED'`) is a stop
   signal for autonomous use. No silent overrides.
3. `DEGRADED` permits use; consumers should surface the degradation and the
   failing checks to their users.
4. Never re-derive the verdict from raw evidence; never recount from the
   capped JSON blobs (§4).
5. Treat unknown JSON keys as additive extension — ignore, don't fail
   (§9).
6. Apply the staleness rules of §10.

---

## 9. Schema Versioning and Evolution

- The wire contract carries a payload schema version; the current version
  is **`1.0`**.
- Any incompatible change to the result fields or the two JSON blob shapes
  **bumps the version**. Additive optional fields are compatible within a
  major version; consumers ignore unknown fields.
- Producer and consumer are held together by a **shared golden fixture**:
  the producer generates it from the contract module, the consumer vendors
  it into its test suite, and both build gates fail on drift. A version
  bump regenerates the fixture and updates both sides in one coordinated
  change.
- Schema `1.0` declares the version at build time only (contract module +
  fixture). A runtime `payload_schema_version` field is a **planned
  additive extension (1.1)**, alongside validator identity
  (`validator_id`, `validator_version`) and decision-profile identity
  (`profile_id`, `profile_version`) so a result records explicitly what
  evaluated it rather than implying it.

---

## 10. Staleness and Incomplete Evidence

Schema 1.0 carries no expiry; this section defines the consumer-side
conservative outcome the contract requires (and charts `evidence_expires_at`
as a 1.1 additive field so producers can declare it explicitly).

1. **Evidence window.** A product may declare a maximum evidence age in its
   orientation metadata. Absent a declaration, consumers apply a default
   window of **7 days** from `completed_at`.
2. **Stale evidence** (latest run older than the window): autonomous
   consumers must treat the product as if `agent_use_allowed = 0`,
   whatever the recorded status says. Interactive consumers must surface
   the staleness prominently.
3. **No evidence** (no trust result exists): the product is *unvalidated*,
   not trusted-by-default. Autonomous consumers must not proceed;
   interactive consumers surface "no trust evidence".
4. **Incomplete evidence** (run present but `total_checks = 0`, or the
   result is unparseable): treat as no evidence.

Conservative outcomes never loosen: staleness can only downgrade a
decision, never upgrade one.

---

## 11. Check Identity and Categories

- **`test_id` scheme:** `{PRODUCT-PREFIX}-{FAMILY}-{NNN}` (e.g.
  `CALLCENTRE-SEM-008`); parameterised checks may extend the suffix (e.g.
  `{PREFIX}-QUERY-BOUNDS-{RECIPE_ID}`). Stable across runs so consumers can
  track a check through history.
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

## 12. Conformance Rules

For validators (producers) and consumers of this contract:

| Rule | Check |
|------|-------|
| TGS-01 | `trust_status` is exactly one of the three vocabulary values. |
| TGS-02 | `agent_use_allowed` agrees with `trust_status` per §3. |
| TGS-03 | The default decision profile is never loosened. |
| TGS-04 | `total_checks = passed_count + failed_count + error_count`. |
| TGS-05 | Gate counts are consistent with the severity model (§4). |
| TGS-06 | Scores are 0–100 integers or null; null only when the family has no checks. |
| TGS-07 | JSON blobs respect their caps; true totals live in `row_count` / `repair_candidate_count`. |
| TGS-08 | Every `sample_rows` element carries `issue_code` and `repair_hint`; every issue code is catalogued with its identifying keys. |
| TGS-09 | Runs are appended; the latest-per-product projection is deterministic (`completed_at`, then `run_id`). |
| TGS-10 | Consumers apply §10 staleness outcomes; no silent override of a blocked status. |
| TGS-11 | Producer and consumer build gates verify the shared golden fixture at the declared schema version. |

---

## 13. Relationship to Other Standards

- **Issue #16 / #10** — this document follows the core/extension
  governance boundary; its file placement moves when the repository
  restructure is agreed.
- **Issue #17 (Temporal & Lifecycle Metadata Standard)** — TLM blocking
  rules are canonical CRITICAL/ERROR check sources for validators.
- **Issue #14 (primary object discovery)** — its validation queries are
  canonical STRUCTURAL/SEMANTIC check sources.
- **Issue #20 (orientation/manifest)** — the trust result must be
  discoverable from product orientation; trust evaluation precedes
  analytical resource use in the discovery order.
- **Teradata binding** —
  `platform-standards/Trust_Gate_Extension.md`.
