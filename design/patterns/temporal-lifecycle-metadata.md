# Temporal & Lifecycle Metadata — Pattern

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Pattern (cross-cutting, platform-agnostic) |
| **Scope** | Every persisted table in every module — temporal and lifecycle metadata |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/patterns/temporal-lifecycle-metadata/`](../../implementation/teradata/patterns/temporal-lifecycle-metadata/) |

This pattern defines **semantic contracts only** — the canonical names and meanings of temporal
and lifecycle metadata. It contains no platform types, sentinel literals, or catalogue queries;
those bind in the implementation. It underpins the `CurrentStateFilter` and
`PointInTimeReconstruction` capabilities, and its conformance rules are lifted directly by the
[validation pattern](validation.md).

---

## 1. Purpose

Without a single temporal contract, products and standards drift into failure modes that break
every consumer filtering on a shared contract: competing spellings for one concept
(`valid_from_dts` vs bare `valid_from` vs `effective_date`; `created_at` vs `created_dts` vs
`created_date`), one flag carrying two meanings (`is_active` for currency here and lifecycle
there), transaction time both mandated and optional, two open-state conventions coexisting, and
audit-only dialects that leave consumers nothing to filter on.

This pattern gives each concept **exactly one name and one meaning**, defines the SCD2 period
contract precisely, and makes each table declare which temporal profile it implements so
validators enforce the contract mechanically.

---

## 2. The Seven Temporal Concepts

Every temporal or lifecycle column represents exactly one of these. Conflating two concepts in
one column is a conformance failure.

| # | Concept | Question it answers | Canonical columns |
|---|---------|---------------------|-------------------|
| 1 | **Business validity** | During which real-world period was this version true? | `valid_from_dts`, `valid_to_dts` |
| 2 | **Row audit** | When did the platform physically create / last change this row? | `created_dts`, `updated_dts` |
| 3 | **Ingestion** | When was this data accepted at the ingestion boundary? | `ingested_dts` |
| 4 | **Event time** | When did the specific business/technical event occur? | `<event>_dts` (e.g. `measured_dts`, `run_dts`, `decided_dts`) |
| 5 | **SCD2 currency** | Is this the current version for its natural key? | `is_current` (convenience over concept 1) |
| 6 | **Logical deletion** | Does this version record deletion of the entity? | `is_deleted`, `deleted_dts` |
| 7 | **Lifecycle state** | Is this thing operationally live / approved for use, independent of versioning? | `is_active` |

**Transaction time** (`transaction_from_dts`, `transaction_to_dts`) is an optional bitemporal
extension of concept 1 for full correction semantics — **not** part of the mandatory core (§6).

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
| `ingested_dts` | Time accepted at the ingestion boundary | Conditional |
| `is_deleted` | Logical deletion state | Required when deletion is supported |
| `deleted_dts` | Effective logical deletion time | Required when `is_deleted` is present |
| `is_active` | Domain/metadata lifecycle state, independent of currency and deletion | Conditional; semantics must be documented (§4.3) |
| `<event>_dts` | Named business/technical event time | Conditional on table grain |
| `transaction_from_dts` / `transaction_to_dts` | Database (transaction-time) validity | Optional — bitemporal variant only (§6) |

All `*_dts` columns are timestamp-grain (logical type `Timestamp`). Day-grain business facts
(e.g. a contractual `decided_date`, logical type `Date`) remain legal as *event* columns, but
validity bounds and audit columns are always timestamps. Precision, time-zone handling, and
physical types bind per implementation.

### 3.2 Prohibited generic names

Prohibited in new designs; each has exactly one canonical replacement:

| Prohibited | Canonical |
|------------|-----------|
| `created_at`, `created_timestamp`, `created_dt`, `created_date` (as audit) | `created_dts` |
| `updated_at`, `updated_timestamp` | `updated_dts` |
| `valid_from`, `effective_from`, `effective_date`, `start_timestamp` | `valid_from_dts` |
| `valid_to`, `effective_to`, `expiration_date`, `end_timestamp` | `valid_to_dts` |
| `deleted_flag`, `active_ind`, `*_yn`, single-character / Y-N flag encodings | `is_deleted` / `is_active` (a `Flag`) |

Event-specific names remain valid where they describe distinct events rather than audit or SCD2
metadata: `run_dts`, `measured_dts`, `observation_dts`, `generated_dts`, `discovered_dts`,
`change_dts`, `deployed_dts`, `registered_dts`, `retired_dts`, and similar.

---

## 4. Lifecycle Flag Semantics

Flags are `Flag`-typed (the implementation defines the physical representation, restricted to two
values). Each answers exactly one question.

**4.1 `is_current`** — *"Is this the current SCD2 version for this natural key?"* The validity
period remains **authoritative**; the flag is a consumer convenience. It changes transactionally
with `valid_to_dts`; validation fails any disagreement; no more than one current row per natural
key.

**4.2 `is_deleted`** — *"Does this version represent logical deletion?"* Not an expired historical
version. `deleted_dts` required when true. Governed history is retained; deletion never rewrites
it. Default current surfaces exclude deleted rows (§8). Restoration creates a successor version.

**4.3 `is_active`** — an independently defined domain/metadata lifecycle state (e.g. a cookbook
recipe approved for discovery, a lineage flow live, an agreement operationally in force). It must
**not** alias `is_current` or `is_deleted`, must not be added mechanically to every table, and its
meaning, owner, and allowed transitions must be documented — an undocumented `is_active` is a
conformance failure.

> Where a table needs both version currency *and* an approval/discoverability state (common for
> curated registries such as glossaries and cookbooks), use `is_current` for currency and
> `is_active` for approval — never one flag for both.

---

## 5. SCD2 Period Contract

### 5.1 Period semantics

Business validity uses **half-open** periods:

```text
[valid_from_dts, valid_to_dts)
```

A row is valid at instant `t` when:

```text
valid_from_dts <= t  AND  t < valid_to_dts
```

The end bound is exclusive. Adjacent versions share a boundary instant
(`predecessor.valid_to_dts = successor.valid_from_dts`) with no gap and no overlap. Half-open
semantics prohibit inclusive-end failure modes: no inclusive end dates, no current-date-minus-one,
no second-subtraction, no precision-dependent end conventions.

### 5.2 Required invariants

1. Both validity boundaries are non-null (§7).
2. `valid_from_dts < valid_to_dts` — no zero-duration or negative periods.
3. Periods for one natural key do not overlap.
4. No more than one current row exists per natural key.
5. `is_current` agrees with the open-ended validity representation.
6. Unchanged input does not create another version (change detection is mandatory).
7. Predecessor closure and successor insertion occur in one transaction.
8. Replay is idempotent — reprocessing the same input produces no new versions.
9. Late-arriving changes are placed at their actual effective instant, splitting existing periods.
10. Logical deletion preserves governed history: a deletion is a new current version with `is_deleted` set and `deleted_dts` recorded.

### 5.3 Bitemporal extension (optional)

Products requiring correction semantics ("what did we believe on date X about date Y?") add
`transaction_from_dts` / `transaction_to_dts` with the same half-open semantics on the
transaction-time axis. Corrections close the transaction period of the mistaken row and insert
corrected rows; business validity is never destructively rewritten. Transaction time is an
**optional profile variant** (§6), never part of the mandatory core — `created_dts` / `updated_dts`
already provide physical audit time.

---

## 6. Table Metadata Profiles

Every persisted table **declares exactly one profile**. The declaration lives in the Semantic
module's entity metadata (a `temporal_pattern` descriptor, with current/deleted flag descriptors
naming the physical flags where present), so agents and validators resolve a table's temporal
behaviour from metadata rather than inference.

| Profile | Vocabulary value | Required | Prohibited |
|---------|------------------|----------|------------|
| Current-state table | `CURRENT_STATE` | `created_dts`, `updated_dts` | SCD2 validity pair, `is_current` |
| Append-only event / fact | `EVENT_APPEND_ONLY` | audit columns + ≥1 `<event>_dts` | lifecycle flags, SCD2 period (normally) |
| SCD2 history | `SCD2_HISTORY` | validity pair, `is_current`, audit columns | — (`is_deleted`/`is_active` only when applicable) |
| Association / bridge | `ASSOCIATION_CURRENT` or `ASSOCIATION_SCD2` | per the chosen underlying profile | per the chosen underlying profile |
| Operational log / audit | `OPERATIONAL_LOG` | audit + event timestamps | lifecycle / SCD2 columns unless the logged object is versioned |
| SCD2 bitemporal | `SCD2_BITEMPORAL` | SCD2 required columns + transaction-time pair | — |

Missing required columns, or prohibited columns present, are conformance failures for the declared
profile. (The `[kind: History]` entities in the module docs are the `SCD2_HISTORY` profile;
`[kind: Record]` entities are typically `EVENT_APPEND_ONLY` or `CURRENT_STATE`.)

---

## 7. Open-State Representation

Two different "still open" situations take different representations:

1. **Validity bounds are never null.** An open-ended current version carries the implementation's
   far-future **sentinel** in `valid_to_dts` (and `transaction_to_dts` where present). This keeps
   range predicates uniform and efficient.
2. **Event timestamps are null until the event occurs.** `deleted_dts`, `retired_dts`,
   `session_end_dts`, `validation_dts`, and similar record instants of events that may not yet have
   happened; `null` means "has not occurred". They are not validity bounds and must not carry
   sentinels.

---

## 8. Access Exposure Policy

The pattern defines two exposure **surfaces** per consumable entity. How each is realised — views,
schemas, grants, or direct table access — is a platform decision bound in the implementation and
governed by the [access-layer pattern](access-layer.md); every platform provides both surfaces,
however thinly.

- The **governed full-contract surface** exposes every temporal and lifecycle column, for
  auditors, maintainers, and history-aware consumers.
- The **default current surface** per consumable entity: filters on authoritative current validity
  **plus** `is_current`; additionally excludes deleted rows when deletion is supported; hides
  `valid_to_dts`, `is_current`, deletion metadata, and operational audit timestamps by default;
  may expose `valid_from_dts` as "effective since"; exposes `is_active` only where
  business-meaningful; exposes event timestamps when part of the consumer contract.
- Historical and deletion-aware surfaces may expose additional metadata for approved use cases.
- Purpose-specific surfaces derive from the governed full-contract surface and must not apply
  temporal semantics that disagree with it.

---

## 9. Conformance Rules

Lifted directly into validator profiles by the [validation pattern](validation.md). Rules marked
**[B]** are blocking (agent stop/go); the rest default to warning severity.

| Rule | Check |
|------|-------|
| TLM-01 **[B]** | Every persisted table declares exactly one profile (§6) in the Semantic entity metadata. |
| TLM-02 **[B]** | All required columns for the declared profile exist. |
| TLM-03 | No prohibited columns for the declared profile exist. |
| TLM-04 | No prohibited generic names (§3.2) exist. |
| TLM-05 | Physical type, precision, time-zone handling, and flag representation match the implementation. |
| TLM-06 **[B]** | Flags are non-null and restricted to the two values. |
| TLM-07 **[B]** | Validity bounds are non-null and `valid_from_dts < valid_to_dts`. |
| TLM-08 **[B]** | No overlapping validity periods per natural key. |
| TLM-09 **[B]** | At most one current row per natural key. |
| TLM-10 **[B]** | `is_current` agrees with the open-ended validity representation. |
| TLM-11 | `is_deleted` rows have a non-null `deleted_dts`. |
| TLM-12 | Every `is_active` column has documented semantics, owner, and transitions. |
| TLM-13 | Default current surfaces apply the §8 filters (no deleted rows exposed). |
| TLM-14 | Purpose-specific surfaces agree with the governed full-contract surface's temporal semantics. |
| TLM-15 | Every temporal/lifecycle column carries a column comment (`RichMetadata`). |
| TLM-16 | No inclusive-end idioms (current-date-minus-one, second-subtraction) in maintenance code or surfaces. |
| TLM-17 | Sentinels appear only on validity bounds; event timestamps use `null` for "not yet occurred". |

---

## 10. Migration and Compatibility

**Legacy-to-canonical mapping** (forms found in existing products and their replacements): DATE-grain
`valid_from`/`valid_to` and `effective_date`/`expiration_date` → `valid_from_dts`/`valid_to_dts`
(grain widens day → timestamp); `created_at`/`created_dt`/`created_timestamp`/`created_date` →
`created_dts`; `updated_at`/`updated_timestamp` → `updated_dts`; `is_active`-as-currency →
`is_current` (retain `is_active` only for a distinct documented approval state); audit-only dialects
(`rec_load_dts`/`rec_updt_dts`) → canonical audit columns; transaction-time-as-mandatory → optional
`SCD2_BITEMPORAL` variant.

**Migration rules:** new products apply the canonical contract immediately; deployed products migrate
through **versioned compatibility projections** (a compatibility surface presenting canonical names
over legacy columns until base tables are regenerated — consumers never parse dialects); widening
alone cannot recover semantics (DATE→timestamp migrations document that intra-day ordering is
unavailable for historical rows); validators flag non-canonical names on new objects while allowing
registered legacy aliases with an expiry.

**Precedence.** Where any other design standard disagrees on the naming, typing, grain, sentinel, or
lifecycle semantics of temporal metadata, this pattern takes precedence; a disagreeing document is
aligned at its next revision.

---

## 11. Relationship to Other Standards

- **[Validation pattern](validation.md)** — §9 rules are written to lift directly into validator
  profiles; blocking rules gate agent use.
- **[Object-placement pattern](object-placement.md)** — layer *naming* is owned by object placement;
  §8 defines layer *responsibilities* only.
- **[Access-layer pattern](access-layer.md)** — realises the §8 surfaces as concrete access objects.
- **[Semantic module](../modules/semantic.md)** — its entity metadata carries the profile
  declaration (§6); its own catalogue tables follow the current-state or SCD2 profile.
- **Implementation** — the Teradata binding (types, sentinel, flag representation, DDL/DML templates,
  access views, catalogue conformance queries) lives in
  [`implementation/teradata/patterns/temporal-lifecycle-metadata/`](../../implementation/teradata/patterns/temporal-lifecycle-metadata/).

---

**End of Temporal & Lifecycle Metadata Pattern**
