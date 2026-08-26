---
title: Validation Pattern
anchor: validation
type: pattern
status: standard
version: 2.1
normative: true
---

# Validation: Pattern

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Pattern (cross-cutting, platform-agnostic) |
| **Scope** | Machine-readable validation results and the per-area trust map every product publishes |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Module home** | [Observability](../modules/observability.md): validation results are operational evidence |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Wire schema** | 2.1 (canonical, additive over 2.0); 1.0 registered as a legacy binding |
| **Implementations** | [`implementation/teradata/patterns/validation/`](../../implementation/teradata/patterns/validation/) |

This pattern defines the **validation result contract** and the **trust map** an agent reads before using a product. Each module and pattern contributes *conformance checks*, its invariants, the temporal `TLM-01..17` rules, the Semantic primary-object validations, which validators execute and publish as results in this contract. Results are append-only operational evidence in the Observability module (temporal profile `EVENT_APPEND_ONLY`).

---

## 1. Purpose and Principles

An agent needs published validation *evidence*, resolved per area, so it can judge how far to trust the part of the product it is about to use. This pattern defines that evidence and how to read it.

1. **One results contract, many producers.** A unit-test harness, a simple validator, or a full trust engine all publish the same record shape, distinguished by `producer_id`.
2. **Only a validator computes trust.** Consumers are read-only: they act on published results and never re-derive a verdict from raw evidence.
3. **The map informs; it does not block.** Trust is published per area, and no value in this contract withholds permission to use the product. A consumer proceeds and **discloses**: it states the confidence and the open gaps for every area it used. What a failure costs is bounded by the area it belongs to, so a defect in one module no longer withdraws a product an agent needed for another.
4. **Coverage is part of the answer.** An area no check reached is *unknown*, never *fine*. The map records which checks existed, which ran, and what would raise confidence, so an agent can say how far it trusts an answer and a product owner can see what to build next.
5. **Validation results are operational evidence**: append-only event records in Observability.

---

## 2. Capabilities

**Provides:**

| Capability | Made available to |
|------------|-------------------|
| `QualityScore` | Agents and reviewers, as the per-area trust map, the readiness scores, and the status vocabularies this pattern defines over validation evidence. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `RichMetadata` | `[hard]` | `self` / `platform` | Validation results are self-describing, so an agent can interpret a run without external narration. |

---

## 3. The Validation Result

Two related records: one **run** record summarising the whole run, and one **area** record for each area the run covers. Both are append-only, and both bind their physical types per implementation.

### 3.1 The run record

The result entity is **`ValidationRun`**, bound to `validation_run`. The name is part of the contract, not a designer's choice: the standard conformance queries and the latest-run projection resolve it by name, so a product that names it something else does not fail loudly. The queries find no rows, count no failures, and report clean. A design brief that proposes a different name is corrected rather than accommodated.

One logical record per product per producer per run; consumers read the **latest** per (product, producer).

| Field | Meaning |
|-------|---------|
| `product_prefix` | Product identity the run evaluated |
| `producer_id`, `producer_version` | Identity and version of the producing validator/harness |
| `profile_id`, `profile_version` | Check profile evaluated: which checks it defines, and their scopes (nullable for simple harnesses) |
| `source_format` | Provenance: `NATIVE`, or the interchange format it was ingested from |
| `payload_schema_version` | Wire schema version of this record |
| `run_id` | Deterministic run identifier |
| `started_dts`, `completed_dts` | Run instants (typed timestamps, persisted UTC) |
| `trust_status` | Advisory product-level summary of the map: `TRUSTED` \| `DEGRADED` \| `UNTRUSTED` |
| `agent_use_allowed` | **Deprecated at schema 2.1**: retained for wire compatibility, no longer a decision (§4.4) |
| `total_checks`, `passed_count`, `failed_count`, `error_count` | Check totals by **status** |
| `critical_failure_count`, `error_failure_count` | Counts by **severity** among failed/errored checks |
| `data_product_trust_score` | Conformance score, 0-100 or null |
| `performance_readiness_score`, `operational_readiness_score` | Other score dimensions, 0-100 or null |
| `repair_candidate_count` | True (uncapped) number of repair candidates |
| `failed_checks_json` | Machine-readable failure detail, capped |
| `repair_candidates_json` | Machine-readable repair proposals, capped |
| `evidence_expires_dts` | Producer-declared expiry of this evidence (nullable) |

A simple test harness populates the identity, status, and count fields and leaves scores, JSON blobs, and profile fields null: a fully conformant result. Runs are **appended**, never overwritten.

### 3.2 The area record

The trust-map entity is **`ValidationArea`**, bound to `validation_area`. One logical record per run per area; consumers read the **latest** per (product, producer, area). Its name is part of the contract for the same reason `validation_run` is.

| Field | Meaning |
|-------|---------|
| `product_prefix`, `producer_id`, `run_id` | Parentage: the run this entry belongs to |
| `scope_kind`, `scope_id` | The area this entry describes (§4.1) |
| `checks_expected` | How many checks the profile defines for this area; `0` means none is defined |
| `checks_ran` | How many of them executed in this run |
| `passed_count`, `failed_count`, `error_count` | Check outcomes within the area, by **status** |
| `critical_failure_count`, `error_failure_count` | Counts by **severity** among the area's failed/errored checks |
| `area_status` | `pass` \| `fail` \| `partial` \| `not-validated` \| `no-evidence` (§4.3) |
| `confidence` | `strong` \| `partial` \| `weak` \| `unknown` (§4.3) |
| `open_gaps` | What is uncovered or unproven here; required unless `confidence` is `strong` |
| `recommended_action` | What would raise confidence in this area; required unless `confidence` is `strong` |
| `completed_dts` | Inherited from the run, so the latest-per-area projection is deterministic |

Coverage is `checks_ran / checks_expected`. It is **derived on read**, not stored, so there is no second copy of it to drift from the counts.

A run publishes an entry for **every area its profile covers, including the areas it could not check**. An area left out of the map is invisible, and an invisible area reads as an area with nothing wrong: the opposite of what this pattern is for.

A producer that publishes no area records is at wire schema 2.0. Consumers read its run record as a single `PRODUCT`-scope entry (§10), so the map has one shape everywhere.

---

## 4. Status Vocabularies and Trust Semantics

### 4.1 The area

An **area** is the unit the map resolves trust to. Its key is (`scope_kind`, `scope_id`):

| `scope_kind` | `scope_id` is | Example |
|--------------|---------------|---------|
| `MODULE` | The module anchor | `domain` |
| `ENTITY` | The catalogued entity, qualified by its module anchor | `domain.Ticket` |
| `PATTERN` | The pattern anchor | `temporal-lifecycle-metadata` |
| `CAPABILITY` | The capability name from the catalogue | `NearestNeighbors` |
| `PRODUCT` | The product prefix: whole-product entries that belong to no narrower area | `CALLCENTRE` |

Identities come from the corpus and the product's own Semantic catalogue, never from a convention applied to an object name. Areas may overlap by design: an `ENTITY` entry says something narrower than the `MODULE` entry above it, and a consumer reading both takes the narrowest entry that covers what it is about to query.

### 4.2 Coverage

Coverage separates *proven sound* from *never looked at*, which a pass rate alone cannot express. `checks_expected` is what the producer's profile defines for the area; `checks_ran` is what executed. An area whose only check is unwritten reports `checks_expected = 0`, which is `no-evidence`: an honest statement that nothing is known, and a coverage gap for the product owner to close.

### 4.3 Area status and confidence

**`area_status`** — what happened to this area in this run:

| Condition | `area_status` |
|-----------|---------------|
| `checks_expected = 0` | `no-evidence` |
| Checks defined, `checks_ran = 0` | `not-validated` |
| Checks ran, no failures, `checks_ran = checks_expected` | `pass` |
| Checks ran, no failures, `checks_ran < checks_expected` | `partial` |
| Any failed or errored check in the area | `fail` |

**`confidence`** — how far the entry supports use of the area, severity-weighted and coverage-aware:

| Condition | `confidence` |
|-----------|--------------|
| Nothing ran (`no-evidence` or `not-validated`) | `unknown` |
| Any CRITICAL or ERROR-severity failure in the area, or coverage below half | `weak` |
| Failures only at WARNING/INFO severity, or full pass on partial coverage | `partial` |
| Every defined check ran and passed | `strong` |

Rules apply in order, first match wins. The vocabulary is deliberately the reviewer's (`roles/review.md`): a review that becomes a deployed product's first published map should not have to be retyped in a different language.

An area at `weak` or `unknown` is **not** an area an agent may not use. It is an area an agent must be honest about when it uses it (§9).

### 4.4 The product-level summary

`trust_status` has exactly three values: **`TRUSTED`**, **`DEGRADED`**, **`UNTRUSTED`**. It is an **advisory summary** of the map, useful for a dashboard or a first glance, and it is not permission and not a decision. A consumer that needs to know whether to rely on something reads the entries for the areas it is about to use.

**Default summary profile** (rules in order):

1. Any execution error (`error_count > 0`), any CRITICAL-severity failure, or any ERROR-severity failure → `UNTRUSTED`. **No score can rescue this rule.**
2. Else `data_product_trust_score < 70` → `UNTRUSTED`.
3. Else any failed check, or `data_product_trust_score < 90` → `DEGRADED`.
4. Else → `TRUSTED`.

Producers that compute no scores skip the score clauses. Implementation profiles may **tighten** the summary toward caution but never loosen it.

**`agent_use_allowed` is deprecated at schema 2.1.** The field remains so a 2.0 reader still parses a 2.1 record, and a 2.1 producer publishes go in it. It carries no authority at any schema version, and a consumer must not branch on it: an area that needs disclosure gets disclosure, and nothing in this contract withholds use. Consumers reading 1.0 or 2.0 records ignore the field for the same reason.

---

## 5. Severity Model

Two independent axes:

- **Status**: what happened when the check ran: `PASSED` | `FAILED` | `ERROR` (could not execute).
- **Severity**: how much a failure matters: `INFO` | `WARNING` | `ERROR` | `CRITICAL`.

| Field | Counts |
|-------|--------|
| `error_count` | Checks with **status** `ERROR` |
| `critical_failure_count` | Failed/errored checks with **severity** `CRITICAL` |
| `error_failure_count` | Failed/errored checks with **severity** `ERROR` |
| `failed_count` | Checks with status `FAILED`, any severity |

Both axes are counted twice over: once for the whole run on the run record, and once per area on that area's entry. `WARNING`/`INFO` failures feed `failed_count` but not the severity counts: they can hold an area at `partial` confidence, never drive it to `weak`. Producers whose native format carries no severity default failed checks to `ERROR`. The counts are **authoritative**; the JSON blobs are capped and must never be counted by consumers.

---

## 6. Readiness Scores

Scores are **optional**: null means *not assessed*, never *perfect*. Where computed, each score is a severity-weighted pass rate over its check family: `round(earned / total × 100)` with weights CRITICAL = 40, ERROR = 25, WARNING = 10, INFO = 5; `earned` sums the weights of passed checks.

| Score | Check categories |
|-------|-----------------|
| `data_product_trust_score` | STRUCTURAL, SEMANTIC, QUERY, CAPABILITY, DATA_QUALITY, FREE_TEXT |
| `performance_readiness_score` | PERFORMANCE |
| `operational_readiness_score` | OPERATIONAL |

Only `data_product_trust_score` participates in the default summary profile's thresholds. The three scores are reported separately and must not be blended. A score is a run-level figure: it summarises, it does not locate, which is what the map is for.

---

## 7. Failed Checks Contract

`failed_checks_json` is an array of failed/errored check records, **capped at 20 items**; each item's `sample_rows` is **capped at 3 rows**. Item shape:

```json
{
  "test_id": "CALLCENTRE-SEM-004",
  "name": "Curated column metadata covers deployed columns",
  "category": "SEMANTIC",
  "severity": "CRITICAL",
  "status": "FAILED",
  "scope_kind": "MODULE",
  "scope_id": "semantic",
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

Rules: the check-level identifier is **`test_id`** (`issue_code` exists only inside `sample_rows`); `scope_kind` / `scope_id` name the area the check belongs to (§4.1, §12), so a consumer reading a failure knows which map entry it landed on; every `sample_rows` element carries `issue_code`, `repair_hint`, and the object-identifying keys; `row_count` is the **true** total, `sample_rows` the first ≤ 3: consumers render the remainder as `+ (row_count − shown) more`, never by counting the blob; `error_message` is non-null only for status `ERROR`; every issue code is catalogued in the producer's documentation; the blob is optional for count-only producers.

---

## 8. Repair Candidates Contract

`repair_candidates_json` is an array of repair proposals, **capped at 20 items**; the true total is `repair_candidate_count`. Item shape:

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

`mode` ∈ `detect` | `proposal` | `safe-auto`. `requires_approval = true` candidates must never be executed autonomously: a candidate is a proposal, not an instruction; a consumer executing repair does so under its own change-management controls. Optional when no repairs are proposed.

---

## 9. Consumption Contract and Trust Authority

**Read, select, proceed, disclose.** A consumer works through the map in four steps:

1. **Read** the map **before** analytical use, discovering its location and the authoritative producer through product orientation.
2. **Select** the entries covering the areas the work will touch: the modules, entities, patterns, and capabilities the query plan reaches, taking the narrowest entry that covers each. Areas the work does not touch place no constraint on it.
3. **Proceed.** Nothing in this contract withholds use, at any confidence.
4. **Disclose, proportionally.** State the confidence for every area used. An area at `weak`, or any CRITICAL/ERROR failure in an area used, is surfaced with its consequence and its `recommended_action`. An area at `unknown` is reported as unknown: never as sound, never silently. An answer drawn only from `strong` areas says that too, because the consumer has earned the right to say it.

**Trust authority.** Multiple producers may publish for one product. Each product **designates exactly one trust-authoritative producer** in its orientation metadata; that producer's latest entries are *the* map. Other producers' results are **evidence**: surfaced, especially where they disagree, but not map-defining. Absent a designation, consumers take the most cautious entry per area across producers and say that they did so, because a product with two maps and no designation has not told anyone which one it means.

**The designation is made at design time.** Everything above is written from the consumer's side, and a consumer can only read a designation that already exists. VAL-13 is checked at runtime; the fact it checks has to be established while the product is being designed, because by deploy time the manifest is already written. So it is a designer's obligation, stated here rather than left to be inferred from the consumer rule:

> Name the producer whose trust map is the product's authoritative one. Record it as a design decision, and carry it into the orientation manifest as `trust_authoritative_producer` (the [Semantic module](../modules/semantic.md) owns the field). Where the product has exactly one producer it is authoritative by definition, and must still be named: an implicit designation is not readable.

**Further consumer rules.** Never re-derive a status or a confidence, and never recount capped blobs: only a validator computes trust. Treat unknown JSON keys as additive extension (ignore, don't fail). Apply the staleness rules (§11).

**Consumer-side policy is out of contract.** A consumer may hold its own rule about which confidence it will act on unsupervised, and a high-consequence autonomous action is a reasonable place to hold one. That rule belongs to the consumer and its operator, and it is theirs to state and log. This pattern's job is to make the confidence legible and located, so a policy has something honest to act on; it is not to decide, on a product owner's behalf, what an agent may not read.

---

## 10. Schema Versioning and Evolution

Every record carries `payload_schema_version`; the canonical version is **`2.1`**. Incompatible changes bump the major version; additive optional fields are compatible within a major version.

**Wire schema `2.1`** adds the area record, the `scope_kind` / `scope_id` keys on failed-check items, and the deprecation of `agent_use_allowed`. It is additive: a 2.0 reader parses a 2.1 run record unchanged.

**Reading a 2.0 or 1.0 producer.** A producer that publishes no area records still has a readable map: consumers project its run record as one `PRODUCT`-scope entry, with `checks_expected` and `checks_ran` both taken from `total_checks` and the §4.3 rules applied to the run counts. A derived entry is **capped at `partial` confidence**, because a run-level pass says nothing about which areas it covered, and it is marked as derived rather than published so a consumer can tell the difference. The map then covers one area, the whole product, which is exactly as much as such a producer knows.

**Selecting records by version.** `payload_schema_version` is a version string, not an ordered number, so a reader must never select records by comparing it lexically. `'10.0'` sorts below `'2.1'`, so a reader written as "at least 2.1" silently stops covering the schema it was written for the moment a two-digit major version exists. **Registered legacy versions are enumerated explicitly**, and every other version is canonical-or-later by exclusion: a new major version is then covered by every check the day it appears, and registering a new legacy binding is a single edit per reader. This binds consumers and conformance checks alike.

**Wire schema `1.0`** remains the registered legacy binding (the same status/count/score/JSON fields without the producer-identity, `source_format`, `payload_schema_version`, or `evidence_expires_dts` fields); consumers treat a 1.0 record as an implied single producer. Producer and consumer are held together by a **shared golden fixture**: both build gates fail on drift.

---

## 11. Staleness and Incomplete Evidence

Age and absence are **coverage facts**: they change what the map claims, not whether the product may be read.

1. **Evidence window.** A producer may declare per-record expiry; a product may declare a maximum evidence age in orientation. Absent both, the default window is **7 days** from `completed_dts`.
2. **Stale evidence** (past expiry / older than window): every entry from that run reads at `confidence` = `unknown`, whatever it recorded, because a passed check proves the state of a product as it was. Consumers surface the staleness and its date, and `recommended_action` is to re-run the validator.
3. **No evidence**: the area is *unvalidated* rather than sound. An area with no published entry reads as `no-evidence` / `unknown`, and a product with no published run has a map of one such entry.
4. **Incomplete evidence** (`total_checks = 0` or unparseable): treat as no evidence.

Staleness can only downgrade confidence, never raise it. It does not block: an agent may answer from a stale product, and says that it did.

---

## 12. Check Identity and Categories

- **`test_id` scheme:** `{PRODUCT-PREFIX}-{FAMILY}-{NNN}` (e.g. `CALLCENTRE-SEM-008`); parameterised checks may extend the suffix. Stable across runs. Ingested results map their native identity into this scheme deterministically.
- **Categories** (drive score families): `STRUCTURAL`, `SEMANTIC`, `QUERY`, `CAPABILITY`, `PERFORMANCE`, `OPERATIONAL`, `DATA_QUALITY`, `FREE_TEXT`.
- **Scope** (drives the map): every check belongs to exactly one area. **By ownership, a check's scope is the module or pattern that owns it** — the checks shipped under a module's own directory are that module's area, and a pattern's conformance queries are that pattern's — so an existing check suite acquires its scope without being rewritten. A check that resolves a single entity or a single capability declares the narrower scope instead, and a check about the product as a whole declares `PRODUCT`. A category is what a check tests; a scope is what it tests *about*, and the two are independent: one `STRUCTURAL` check can belong to Domain and the next to Search.
- Validators prove the product's **self-describing metadata** (semantic catalogue, orientation manifest, relationships, cookbook) against what is physically deployed. The temporal pattern's `TLM-01..17` rules (blocking → CRITICAL/ERROR) and the Semantic module's primary-object validations lift directly into validator profiles: as do each module's own `INV-*` invariant checks. Each lifts with the scope of the document that states it.

---

## 13. Open Standards Alignment (non-normative)

The result is mappable from/to established open formats; `source_format` records provenance. Ingest mappings are implemented by validation tooling, not by this pattern.

| Standard | Layer | Mapping |
|----------|-------|---------|
| **JUnit XML** | Test results | `testsuite`/`testcase` totals → status counts; failures default to severity `ERROR`. `source_format = 'JUNIT-XML'` |
| **CTRF** | Test results | `summary` + `tests[]` → counts and optional detail. `source_format = 'CTRF'` |
| **Open Test Reporting** | Test results | Ingest as consumer adoption matures. `source_format = 'OTR'` |
| **SARIF 2.1.0** | Analysis results | `ruleId` ↔ `test_id`, `level` ↔ severity, `fixes[]` ↔ repair candidates. `source_format = 'SARIF'` |
| **OpenLineage** quality facet | Emission | Runs may additionally emit per-assertion facets on lineage run events |
| **ODCS / ODPS** | Check definitions | Contract-side quality rules *define* checks; results land here, linked through `test_id` |

---

## 14. Conformance Rules

| Rule | Check |
|------|-------|
| VAL-01 | `trust_status` is exactly one of the three vocabulary values. |
| VAL-02 | `agent_use_allowed` is published as go on every 2.1 record, and no consumer branches on it at any version. |
| VAL-03 | The default summary and confidence profiles are tightened toward caution or not at all, never loosened. |
| VAL-04 | `total_checks = passed_count + failed_count + error_count`. |
| VAL-05 | Severity counts are consistent with the severity model, on the run record and on every area entry. |
| VAL-06 | Scores are 0-100 integers or null; null only when not assessed. |
| VAL-07 | JSON blobs respect their caps; true totals live in `row_count` / `repair_candidate_count`. |
| VAL-08 | Every `sample_rows` element carries `issue_code` and `repair_hint`; every issue code is catalogued. |
| VAL-09 | Runs are appended; the latest-per-(product, producer) and latest-per-area projections are deterministic (`completed_dts`, then `run_id`). |
| VAL-10 | Consumers apply staleness as a confidence downgrade, and disclose every area they used at `weak` or `unknown`. |
| VAL-11 | Producer and consumer build gates verify the shared golden fixture at the declared schema version. |
| VAL-12 | Every record carries non-null `producer_id` and `payload_schema_version`. |
| VAL-13 | The map is taken from the designated producer; absent designation, the most cautious entry per area applies and the consumer says so. |
| VAL-14 | `scope_kind`, `area_status`, and `confidence` come from their vocabularies, and `scope_id` resolves to a real module, entity, pattern, capability, or the product. Runtime-checkable for `PRODUCT`, `MODULE`, and `ENTITY` against deployed catalogue metadata; `PATTERN` and `CAPABILITY` have no deployed catalogue to resolve against, so the producer's build-time assertion against its own validator profile is the enforcement point. |
| VAL-15 | Per area: `checks_ran = passed_count + failed_count + error_count`, and `checks_ran` never exceeds `checks_expected`. |
| VAL-16 | `pass` and `strong` require checks that ran at full coverage; `no-evidence` and `not-validated` carry `confidence` = `unknown`. |
| VAL-17 | Every entry below `strong` carries `open_gaps` and `recommended_action`. |
| VAL-18 | Every area a run's profile covers has an entry, including uncovered ones; every failed check's scope resolves to an entry in the same run. |

---

## 15. Relationship to Other Standards

- **[Observability module](../modules/observability.md)**: the module home for the run record and the trust map, alongside its other run/event evidence.
- **[Temporal & lifecycle metadata pattern](temporal-lifecycle-metadata.md)**: both results relations declare profile `EVENT_APPEND_ONLY`; `TLM` blocking rules are canonical CRITICAL/ERROR checks, scoped to that pattern's area.
- **[Semantic module](../modules/semantic.md)**: its primary-object validations are canonical STRUCTURAL/SEMANTIC checks; product orientation declares the results location and the trust-authoritative producer, so the map is read before analytical resource use. Its catalogue is also where an `ENTITY` scope resolves.
- **`roles/review.md`**: a reviewer builds this same map by hand, in this vocabulary, before a validator exists to publish it. The two are the same artefact at different stages of a product's life.
- **Implementation**: the Teradata binding (results table, DBC/data checks, wire-schema bindings) lives in [`implementation/teradata/patterns/validation/`](../../implementation/teradata/patterns/validation/).

---

**End of Validation Pattern**
