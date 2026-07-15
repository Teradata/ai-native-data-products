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
| **Platform bindings** | `design-standards/extensions/platforms/teradata/Temporal_Lifecycle_Metadata_Extension.md` |

This is a **core** standard: it defines semantic contracts only. It contains
no vendor SQL types, sentinel literals, catalogue queries, index syntax, or
deployment-tool behaviour — those bind in platform extensions. It is the
first document delivered through the modular core/extensions structure
proposed in issue #16.

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

The module standards currently prescribe temporal and lifecycle metadata
inconsistently. A survey of this repository (2026-07-15) found:

- **three validity spellings** for the same concept — `valid_from_dts` /
  `valid_to_dts` (Advocated, Domain `_H`, Prediction, Search), bare
  `valid_from` / `valid_to` at DATE grain (Memory registry tables, Access
  Layer seed, Master prose), and `effective_date` / `expiration_date`
  (Advocated Type-2 alternative, Domain `_R`);
- **four row-creation audit spellings** — `created_at` (Semantic,
  Observability, Memory event tables), `created_dts` (Advocated),
  `created_dt` (Domain `_Keymap`), `created_timestamp` (Memory registry
  tables) — with a fifth, `created_date`, appearing in a Physical Storage
  example;
- **one flag, two meanings**: `is_active` marks SCD2 currency on Memory's
  `Business_Glossary` and `Query_Cookbook` but catalogue lifecycle on every
  Semantic table, while sibling Memory tables (`Design_Decision`,
  `Module_Registry`) use `is_current` for the same currency concept;
- **transaction time mandated and optional simultaneously**: part of the
  Advocated "Tier 1 core", commented-out optional in the Domain template,
  absent everywhere else;
- **two open-state conventions**: a far-future sentinel on validity bounds,
  but `NULL` on `data_lineage.retired_dts`.

Field deployments amplify the drift (audit-column dialects such as
`rec_load_dts` / `rec_updt_dts` with no lifecycle flags at all), and every
divergence breaks consumers that filter on the standard contract.

The problem is not merely naming: distinct concepts are being conflated.
This standard gives each concept exactly one name and one meaning, defines
the SCD2 period contract precisely, and makes each table declare which
temporal profile it implements so that validators can enforce the contract
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

> **Resolved contradiction.** Memory's `Business_Glossary` and
> `Query_Cookbook` previously used `is_active` where their siblings used
> `is_current` for the same version-currency concept. Under this standard,
> version currency is always `is_current`; those tables may *additionally*
> carry `is_active` for the distinct "approved for discovery" state.

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
overlap. This codifies the predicate form every current document already
uses, and prohibits the failure modes half-open semantics exist to prevent:
no inclusive end dates, no `CURRENT_DATE - 1`, no second-subtraction, no
precision-dependent end conventions.

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

> **Resolved contradiction.** The Advocated standard listed transaction
> time in its mandatory "Tier 1 core" while the Domain template made the
> same columns optional. Under this standard, transaction time is an
> **optional profile variant** (§6.3): `created_dts` / `updated_dts`
> already provide physical audit time for products that do not need
> correction history.

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

> **Resolved contradiction.** Observability's `data_lineage.retired_dts`
> (`NULL` while the flow is live) is *correct* under rule 2 — it is an
> event timestamp paired with the documented lifecycle flag `is_active`.
> The sentinel convention applies only to concept-1 validity bounds.

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

| Legacy (where observed) | Canonical | Notes |
|-------------------------|-----------|-------|
| `valid_from` / `valid_to` DATE (Memory registry, Access seed, Master prose) | `valid_from_dts` / `valid_to_dts` | Grain widens day → timestamp; day-grain values map to midnight at period start |
| `effective_date` / `expiration_date` (Advocated Type-2, Domain `_R`) | `valid_from_dts` / `valid_to_dts` | As above |
| `created_at` (Semantic, Observability, Memory event, Prediction) | `created_dts` | Rename only |
| `created_dt` (Domain `_Keymap`) / `created_timestamp`, `updated_timestamp` (Memory registry) / `updated_at` | `created_dts` / `updated_dts` | Rename only |
| `is_active` as version currency (Memory `Business_Glossary`, `Query_Cookbook`) | `is_current` | `is_active` may be retained for the distinct approved-for-discovery state |
| `rec_load_dts` / `rec_updt_dts` / `rec_src_id` (field dialects) | `created_dts` / `updated_dts` / source-audit metadata | Field-observed; not prescribed by any repo document |
| Transaction-time pair as mandatory core (Advocated) | Optional `SCD2_BITEMPORAL` variant | §5.3, §6.3 |

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

### 10.3 Consequential updates to existing documents

This standard supersedes the conflicting clauses surveyed in §1. The
following documents require follow-up alignment edits (tracked separately;
this document is authoritative in the interim): Advocated Data Management
Standards (Tier-1 column list, Type-2 alternative), Memory (registry table
DDL and lifecycle prose), Semantic (`created_at`/`updated_at` triplet),
Observability (`created_at`), Domain (`_R` DATE grain, `_Keymap`
`created_dt`), Prediction (`created_at`), Master Design (temporal prose).

---

## 11. Relationship to Other Standards

- **Issue #16 / #10** — this document inaugurates the
  `design-standards/core/` + `extensions/platforms/` structure and follows
  the core/extension governance boundary.
- **Issue #19 (trust gate)** — §9 rules are written to be lifted directly
  into validator profiles; blocking rules feed `agent_use_allowed`.
- **Issue #11 (Teradata extension)** — the Teradata binding of this
  standard lives at
  `design-standards/extensions/platforms/teradata/Temporal_Lifecycle_Metadata_Extension.md`.
- **Object Placement Standard** — layer *naming* is owned by object
  placement standards; §8 defines layer *responsibilities* only.
- **Semantic Module Standard** — `entity_metadata` carries the profile
  declaration (§6); its own catalogue tables follow profile 1 or 3.
