# Temporal & Lifecycle Metadata Standard
## AI-Native Data Product Architecture — Version 1.0 (Draft)

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.0-draft |
| **Status** | DRAFT — Proposed (resolves issue #17) |
| **Last Updated** | 2026-07-15 |
| **Owner** | Worldwide Data Architecture Team, Teradata |
| **Scope** | All modules — temporal and lifecycle metadata on every persisted table |
| **Type** | Design Standard (Core, RDBMS-neutral) |
| **Platform bindings** | `platform-standards/Temporal_Lifecycle_Metadata_Extension.md` |

This is a **core** standard: it defines semantic contracts only. It contains
no vendor SQL types, sentinel literals, catalogue queries, index syntax, or
deployment-tool behaviour — those bind in platform extensions.

---

## Table of Contents

1. [Purpose and Motivation](#1-purpose-and-motivation)
2. [The Seven Temporal Concepts](#2-the-seven-temporal-concepts)
3. [Canonical Column Contract](#3-canonical-column-contract)
4. [Lifecycle Flag Semantics](#4-lifecycle-flag-semantics)
5. [SCD2 Period Contract](#5-scd2-period-contract)
6. [Table Metadata Profiles](#6-table-metadata-profiles)
7. [Open-State Representation](#7-open-state-representation)
8. [Access Exposure Policy](#8-access-exposure-policy)
9. [Conformance Rules](#9-conformance-rules)
10. [Migration and Compatibility](#10-migration-and-compatibility)
11. [Relationship to Other Standards](#11-relationship-to-other-standards)

---

## 1. Purpose and Motivation

Without a single temporal contract, data products and their standards drift
into failure modes that break every consumer filtering on a shared
contract. This standard exists to prevent:

- **competing spellings for one concept** — validity appearing variously as
  `valid_from_dts` / `valid_to_dts`, bare `valid_from` / `valid_to` at DATE
  grain, or `effective_date` / `expiration_date`; row-creation audit
  appearing as `created_at`, `created_dts`, `created_dt`,
  `created_timestamp`, or `created_date`;
- **one flag carrying two meanings** — `is_active` marking SCD2 currency on
  some tables and catalogue lifecycle on others, while sibling tables use
  `is_current` for the same currency concept;
- **transaction time both mandated and optional** depending on which
  document a designer reads;
- **two open-state conventions coexisting** — a far-future sentinel on some
  open-ended columns, `NULL` on others, with no rule saying which applies
  where;
- **audit-only dialects** (e.g. `rec_load_dts` / `rec_updt_dts` with no
  lifecycle flags at all) that leave consumers nothing to filter on.

The problem is not merely naming: distinct concepts get conflated. This
standard gives each concept exactly one name and one meaning, defines the
SCD2 period contract precisely, and makes each table declare which temporal
profile it implements so that validators can enforce the contract
mechanically.

---

## 2. The Seven Temporal Concepts

Every temporal or lifecycle column on a governed table represents exactly
one of these concepts. Conflating two concepts in one column is a
conformance failure.

| # | Concept | Question it answers | Canonical columns |
|---|---------|---------------------|-------------------|
| 1 | **Business validity** | During which real-world period was this version true? | `valid_from_dts`, `valid_to_dts` |
| 2 | **Row audit** | When did the platform physically create / last change this row? | `created_dts`, `updated_dts` |
| 3 | **Ingestion** | When was this data accepted at the product's ingestion boundary? | `ingested_dts` |
| 4 | **Event time** | When did the specific business or technical event occur? | `<event>_dts` (e.g. `measured_dts`, `run_dts`, `decided_dts`) |
| 5 | **SCD2 currency** | Is this the current version for its natural key? | `is_current` (convenience over concept 1) |
| 6 | **Logical deletion** | Does this version record deletion of the entity? | `is_deleted`, `deleted_dts` |
| 7 | **Lifecycle state** | Is this thing operationally live / approved for use, independent of versioning? | `is_active` |

**Transaction time** (when the *database* believed a version, as distinct
from when it was *true*) is an optional extension of concept 1 for full
bitemporal correction semantics: `transaction_from_dts`,
`transaction_to_dts`. It is **not** part of the mandatory core — see §6.

---

## 3. Canonical Column Contract

### 3.1 Canonical columns

| Column | Meaning | Requirement |
|--------|---------|-------------|
| `valid_from_dts` | Inclusive start of business validity | Required for SCD2 |
| `valid_to_dts` | **Exclusive** end of business validity | Required for SCD2 |
| `is_current` | Convenience indicator that the version is current | Required for SCD2 where stored flags are supported |
| `created_dts` | Physical row-version creation time | Required for governed persisted tables |
| `updated_dts` | Physical row last-change time | Required for governed persisted tables |
| `ingested_dts` | Time accepted at the product ingestion boundary | Conditional |
| `is_deleted` | Logical deletion state | Required when deletion is supported |
| `deleted_dts` | Effective logical deletion time | Required when `is_deleted` is present |
| `is_active` | Domain or metadata lifecycle state, independent of currency and deletion | Conditional; semantics must be documented (§4.3) |
| `<event>_dts` | Named business or technical event time | Conditional on table grain |
| `transaction_from_dts` / `transaction_to_dts` | Database (transaction-time) validity | Optional — bitemporal variant only (§6.3) |

All `*_dts` columns are timestamp-grain in the portable contract. Day-grain
business facts (for example a contractual `decided_date`) remain legal as
*event* columns with a `_date` suffix, but validity bounds and audit columns
are always timestamps. Precision, time-zone handling, and physical types
bind per platform extension.

### 3.2 Prohibited generic names

The following are prohibited in new designs. Each has exactly one canonical
replacement:

| Prohibited | Canonical |
|------------|-----------|
| `created_at`, `created_timestamp`, `created_dt`, `created_date` (as audit) | `created_dts` |
| `updated_at`, `updated_timestamp` | `updated_dts` |
| `valid_from`, `effective_from`, `effective_date`, `start_timestamp` | `valid_from_dts` |
| `valid_to`, `effective_to`, `expiration_date`, `end_timestamp` | `valid_to_dts` |
| `deleted_flag`, `active_ind`, `*_yn`, `CHAR(1)` flag encodings | `is_deleted` / `is_active` (boolean-valued) |

Event-specific names remain valid where they describe distinct events rather
than audit or SCD2 metadata: `run_dts`, `measured_dts`, `observation_dts`,
`generated_dts`, `discovered_dts`, `change_dts`, `deployed_dts`,
`registered_dts`, `retired_dts`, and similar.

---

## 4. Lifecycle Flag Semantics

Flags are boolean-valued (platform extensions define the physical
representation, restricted to two values). Each flag answers exactly one
question.

### 4.1 `is_current`

Answers only: *"Is this the current SCD2 version for this natural key?"*

- The validity period remains **authoritative**; the flag is a consumer
  convenience and optimisation aid.
- It must change transactionally with `valid_to_dts`.
- Validation must fail any disagreement between the flag and the open-ended
  validity representation.
- No more than one current row may exist per natural key.

### 4.2 `is_deleted`

Answers only: *"Does this version represent logical deletion of the
entity?"*

- It does **not** mean an expired historical version.
- `deleted_dts` is required when true.
- Governed history is retained; deletion never rewrites it.
- Default current access views exclude deleted rows (§8).
- Restoration creates a successor version rather than rewriting deletion
  history.

### 4.3 `is_active`

Represents an independently defined domain or metadata lifecycle state —
for example, whether a cookbook recipe is approved for discovery, a lineage
flow is live, or an agreement is operationally in force.

- It must **not** alias `is_current` or `is_deleted`.
- It must not be added mechanically to every table.
- Its meaning, owner, and allowed transitions must be documented at table
  and column level; an undocumented `is_active` is a conformance failure.

> **Note.** Where a table needs both version currency *and* an approval or
> discoverability state (a common pattern for curated registry tables such
> as glossaries and cookbooks), use `is_current` for currency and
> `is_active` for the approval state — never one flag for both. This
> avoids the drift where sibling tables express the same currency concept
> through different flags.

---

## 5. SCD2 Period Contract

### 5.1 Period semantics

Business validity uses **half-open** periods:

```text
[valid_from_dts, valid_to_dts)
```

A row is valid at instant `t` when:

```text
valid_from_dts <= t AND t < valid_to_dts
```

The end bound is exclusive. Adjacent versions share a boundary instant
(`predecessor.valid_to_dts = successor.valid_from_dts`) with no gap and no
overlap. Half-open semantics prohibit the failure modes inclusive-end
conventions invite: no inclusive end dates, no `CURRENT_DATE - 1`, no
second-subtraction, no precision-dependent end conventions.

### 5.2 Required invariants

1. Both validity boundaries are non-null (§7).
2. `valid_from_dts < valid_to_dts` — no zero-duration or negative periods.
3. Periods for one natural key do not overlap.
4. No more than one current row exists per natural key.
5. `is_current` agrees with the open-ended validity representation.
6. Unchanged input does not create another version (change detection is
   mandatory).
7. Predecessor closure and successor insertion occur in one transaction.
8. Replay is idempotent — reprocessing the same input produces no new
   versions.
9. Late-arriving changes are placed at their actual effective instant,
   splitting existing periods when necessary.
10. Logical deletion preserves governed history: a deletion is a new
    current version with `is_deleted = 1` and `deleted_dts` set.

### 5.3 Bitemporal extension (optional)

Products requiring correction semantics ("what did we believe on date X
about date Y?") add transaction-time columns `transaction_from_dts` /
`transaction_to_dts` with the same half-open semantics on the
transaction-time axis. Corrections close the transaction period of the
mistaken row and insert corrected rows; business validity is never
destructively rewritten.

> **Note.** Transaction time is an **optional profile variant** (§6.3),
> never part of the mandatory core: `created_dts` / `updated_dts` already
> provide physical audit time for products that do not need correction
> history. Making the requirement explicit avoids designs where transaction
> time is simultaneously treated as mandatory by one document and optional
> by another.

---

## 6. Table Metadata Profiles

Every persisted table **declares exactly one profile**. The declaration
lives in the Semantic module's `entity_metadata` (`temporal_pattern`
column, with `current_flag_column` / `deleted_flag_column` descriptors
naming the physical flags where present), so that agents and validators
resolve a table's temporal behaviour from metadata rather than inference.

| Profile | Vocabulary value | Required columns | Prohibited columns |
|---------|------------------|------------------|--------------------|
| 1. Current-state table | `CURRENT_STATE` | `created_dts`, `updated_dts` | SCD2 validity pair, `is_current` |
| 2. Append-only event / fact table | `EVENT_APPEND_ONLY` | audit columns + at least one `<event>_dts` | lifecycle flags, SCD2 period (normally) |
| 3. SCD2 history table | `SCD2_HISTORY` | validity pair, `is_current`, audit columns | — (`is_deleted` / `is_active` only when semantically applicable) |
| 4. Association / bridge table | `ASSOCIATION_CURRENT` or `ASSOCIATION_SCD2` | per the chosen underlying profile | per the chosen underlying profile |
| 5. Operational log / audit table | `OPERATIONAL_LOG` | audit + event timestamps | lifecycle / SCD2 columns unless the logged object itself is versioned |

**6.3 Bitemporal variant.** An SCD2 history table implementing §5.3
declares `SCD2_BITEMPORAL` and adds the transaction-time pair to its
required columns.

Missing required columns, or prohibited columns present, are conformance
failures for the declared profile.

---

## 7. Open-State Representation

Two different "still open" situations exist and take different
representations:

1. **Validity bounds are never null.** An open-ended current version
   carries the platform extension's far-future sentinel in
   `valid_to_dts` (and `transaction_to_dts` where present). This keeps
   range predicates sargable and uniform.
2. **Event timestamps are null until the event occurs.** `deleted_dts`,
   `retired_dts`, `session_end_dts`, `validation_dts`, and similar columns
   record instants of events that may not yet have happened; `NULL` means
   "has not occurred". They are not validity bounds and must not carry
   sentinels.

> **Note.** An event timestamp paired with a documented lifecycle flag —
> for example a `retired_dts` that is `NULL` while a lineage flow is live,
> alongside `is_active` — is correct under rule 2. The sentinel convention
> applies only to concept-1 validity bounds; applying it to event
> timestamps (or `NULL` to validity bounds) is the drift this section
> prevents.

---

## 8. Access Exposure Policy

The portable exposure contract; platform extensions bind it to their
physical layer architecture.

- The **governed standard view layer** exposes the full metadata contract —
  every temporal and lifecycle column — for auditors, maintainers, and
  history-aware consumers.
- A **default current access view** per consumable entity:
  - filters on authoritative current validity **plus** `is_current`;
  - additionally excludes `is_deleted = 1` when deletion is supported;
  - hides `valid_to_dts`, `is_current`, deletion metadata, and operational
    audit timestamps by default;
  - may expose `valid_from_dts` as "effective since";
  - exposes `is_active` only where business-meaningful;
  - exposes event timestamps when they are part of the consumer contract.
- Historical and deletion-aware access views may expose additional temporal
  metadata for approved use cases.
- Access views derive from the governed standard view, never bypass it.

---

## 9. Conformance Rules

Implementable by the Trust Engine and other validators. Severity guidance:
rules marked **[B]** are blocking (agent stop/go per issue #19); the rest
default to warning severity.

| Rule | Check |
|------|-------|
| TLM-01 **[B]** | Every persisted table declares exactly one profile (§6) in `entity_metadata.temporal_pattern`. |
| TLM-02 **[B]** | All required columns for the declared profile exist. |
| TLM-03 | No prohibited columns for the declared profile exist. |
| TLM-04 | No prohibited generic names (§3.2) exist. |
| TLM-05 | Physical type, precision, time-zone handling, and flag representation match the platform extension. |
| TLM-06 **[B]** | Flags are non-null and restricted to the two boolean values. |
| TLM-07 **[B]** | Validity bounds are non-null and `valid_from_dts < valid_to_dts`. |
| TLM-08 **[B]** | No overlapping validity periods per natural key. |
| TLM-09 **[B]** | At most one current row per natural key. |
| TLM-10 **[B]** | `is_current` agrees with the open-ended validity representation. |
| TLM-11 | `is_deleted = 1` rows have non-null `deleted_dts`. |
| TLM-12 | Every `is_active` column has documented semantics, owner, and transitions. |
| TLM-13 | Default current access views apply the §8 filters (no deleted rows exposed). |
| TLM-14 | Access views do not bypass the governed standard view. |
| TLM-15 | Every temporal/lifecycle column carries a column comment. |
| TLM-16 | No inclusive-end idioms (`CURRENT_DATE - 1`, second subtraction) in maintenance code or views. |
| TLM-17 | Sentinels appear only on validity bounds; event timestamps use `NULL` for "not yet occurred". |

---

## 10. Migration and Compatibility

### 10.1 Legacy-to-canonical mapping

Legacy forms that may be encountered in existing documents and deployed
products, and their canonical replacements:

| Legacy form | Canonical | Notes |
|-------------|-----------|-------|
| `valid_from` / `valid_to` at DATE grain | `valid_from_dts` / `valid_to_dts` | Grain widens day → timestamp; day-grain values map to midnight at period start |
| `effective_date` / `expiration_date` | `valid_from_dts` / `valid_to_dts` | As above |
| `created_at`, `created_dt`, `created_timestamp`, `created_date` | `created_dts` | Rename only |
| `updated_at`, `updated_timestamp` | `updated_dts` | Rename only |
| `is_active` used as version currency | `is_current` | `is_active` may be retained for a distinct, documented approval state (§4.3) |
| `rec_load_dts` / `rec_updt_dts` / `rec_src_id` audit dialects | `created_dts` / `updated_dts` / source-audit metadata | Common field dialect with no lifecycle flags |
| Transaction-time pair treated as mandatory | Optional `SCD2_BITEMPORAL` variant | §5.3, §6.3 |

### 10.2 Migration rules

1. New standards and products apply the canonical contract immediately.
2. Deployed products migrate through **versioned compatibility views** —
   the compatibility layer projects canonical names over legacy columns
   until the base tables are regenerated; consumers never parse dialects.
3. Widening alone cannot recover semantics: DATE-grain validity migrated to
   timestamp grain must document that intra-day ordering is unavailable for
   historical rows.
4. Validators flag non-canonical names on new objects while allowing
   registered legacy aliases on migrating products, with an expiry.

### 10.3 Precedence

Where any other design standard disagrees with this standard on the naming,
typing, grain, sentinel, or lifecycle semantics of temporal metadata, this
standard takes precedence. A disagreeing document is aligned at its next
revision; until then its conflicting clauses are read as legacy forms under
the §10.1 mapping.

---

## 11. Relationship to Other Standards

- **Issue #16 / #10** — this document follows the core/extension
  governance boundary; its file placement moves when the repository
  restructure is agreed.
- **Issue #19 (trust gate)** — §9 rules are written to be lifted directly
  into validator profiles; blocking rules feed `agent_use_allowed`.
- **Issue #11 (Teradata extension)** — the Teradata binding of this
  standard lives at
  `platform-standards/Temporal_Lifecycle_Metadata_Extension.md`.
- **Object Placement Standard** — layer *naming* is owned by object
  placement standards; §8 defines layer *responsibilities* only.
- **Semantic Module Standard** — `entity_metadata` carries the profile
  declaration (§6); its own catalogue tables follow profile 1 or 3.
