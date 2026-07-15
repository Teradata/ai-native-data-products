# Temporal & Lifecycle Metadata Extension — Teradata
## AI-Native Data Product Architecture — Version 1.0 (Draft)

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.0-draft |
| **Status** | DRAFT — Proposed (resolves issue #17, first extension under issue #16 structure) |
| **Last Updated** | 2026-07-15 |
| **Owner** | Worldwide Data Architecture Team, Teradata |
| **Scope** | Teradata binding of `design-standards/core/Temporal_Lifecycle_Metadata_Standard.md` |
| **Type** | Platform Extension (Teradata) |
| **Testing** | Targets Teradata v20.0; conformance queries use DBC dictionary views |

This extension binds the portable temporal/lifecycle contract to Teradata
types, formats, sentinel values, flags, physical layers, access views,
statistics, and catalogue validation. Read the core standard first; nothing
here changes core semantics.

---

## Table of Contents

1. [Type and Format Bindings](#1-type-and-format-bindings)
2. [Flag Representation](#2-flag-representation)
3. [Open-End Sentinel and Synchronisation](#3-open-end-sentinel-and-synchronisation)
4. [Layer Responsibilities](#4-layer-responsibilities)
5. [DDL Template](#5-ddl-template)
6. [DML Maintenance Patterns](#6-dml-maintenance-patterns)
7. [Default Current Access View](#7-default-current-access-view)
8. [Primary Index and Statistics Guidance](#8-primary-index-and-statistics-guidance)
9. [DBC Conformance Queries](#9-dbc-conformance-queries)
10. [Migration Guidance](#10-migration-guidance)

---

## 1. Type and Format Bindings

| Core concept | Teradata binding |
|--------------|------------------|
| All `*_dts` columns | `TIMESTAMP(6) WITH TIME ZONE` |
| Persistence rule | Values persisted normalised to UTC (`+00:00`); presentation-zone conversion is the consumer's concern |
| Day-grain business facts (`*_date` event columns) | `DATE` — never used for validity bounds or audit columns |
| Row audit defaults | `created_dts ... NOT NULL DEFAULT CURRENT_TIMESTAMP(6)`; `updated_dts ... NOT NULL DEFAULT CURRENT_TIMESTAMP(6)` |

`TIMESTAMP(6)` **without** `WITH TIME ZONE` is non-conformant for
temporal/lifecycle metadata columns (TLM-05): it makes the UTC persistence
rule unverifiable and the sentinel ambiguous. This ratifies the position the
Advocated Data Management Standards already take.

---

## 2. Flag Representation

All boolean-valued lifecycle columns (`is_current`, `is_deleted`,
`is_active`):

```sql
is_current  BYTEINT NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
is_deleted  BYTEINT NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
is_active   BYTEINT NOT NULL DEFAULT 1 CHECK (is_active  IN (0, 1))
```

- `BYTEINT NOT NULL`, restricted to `0` and `1` by CHECK constraint.
- `CHAR(1)` `'Y'/'N'` encodings, nullable flags, and `*_ind` / `*_yn` /
  `*_flag` names are non-conformant (core §3.2, TLM-06).

---

## 3. Open-End Sentinel and Synchronisation

The open-ended (current) validity bound is the **non-null UTC sentinel**:

```sql
TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
```

```sql
valid_to_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL
    DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
```

Rules:

1. The sentinel literal always carries `+00:00`. The zone-less form
   `TIMESTAMP '9999-12-31 23:59:59.999999'` is non-conformant — it shifts
   under session-zone changes and breaks equality tests.
2. The **authoritative** current-row predicate is
   `valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'`.
3. `is_current` must be updated in the same transaction as `valid_to_dts`;
   `is_current = 1 ⟺ valid_to_dts = sentinel` at all times (TLM-10).
4. Sentinels appear **only** on validity bounds. Event timestamps
   (`deleted_dts`, `retired_dts`, `session_end_dts`, …) are `NULL` until
   the event occurs (core §7).

---

## 4. Layer Responsibilities

| Layer | Suffix | Responsibility |
|-------|--------|----------------|
| Physical standard table | `*_STD_T` | Full canonical column contract; no consumer access |
| Governed standard view | `*_STD_V` | Mandatory **1:1 locking view** (`LOCKING ROW FOR ACCESS`) exposing every column of its base table, including all temporal/lifecycle metadata |
| Access Layer view | `*_ACS_V` | Purpose-specific consumer views; the default current view per entity follows §7 |

**`ACS` means Access** and replaces the misleading `BUS` abbreviation in
new standards. Deployed `*_BUS_V` objects (and the field-observed `*_ACL_V`
variant) are registered legacy aliases, migrated separately through
versioned compatibility per core §10.2 — this document does not force their
rename.

Access views select from `*_STD_V`, never from `*_STD_T` directly
(TLM-14). Concrete database naming (`{Product}_{Module}_{Layer}`) is owned
by the Object Placement Standard; this extension defines only what each
layer must expose.

---

## 5. DDL Template

SCD2 history table (profile `SCD2_HISTORY`), Domain module example:

```sql
CREATE TABLE {Product}_DOM_STD_T.agreement
(
      agreement_sk        BIGINT NOT NULL
    , agreement_bk        VARCHAR(60) CHARACTER SET UNICODE NOT NULL
    , agreement_status    VARCHAR(20)
    , premium_amount      DECIMAL(15, 2)
    -- Business validity: half-open [valid_from_dts, valid_to_dts)
    , valid_from_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL
    , valid_to_dts        TIMESTAMP(6) WITH TIME ZONE NOT NULL
                              DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
    , is_current          BYTEINT NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1))
    -- Logical deletion (only where deletion is supported)
    , is_deleted          BYTEINT NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1))
    , deleted_dts         TIMESTAMP(6) WITH TIME ZONE
    -- Row audit
    , created_dts         TIMESTAMP(6) WITH TIME ZONE NOT NULL
                              DEFAULT CURRENT_TIMESTAMP(6)
    , updated_dts         TIMESTAMP(6) WITH TIME ZONE NOT NULL
                              DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (agreement_bk);

COMMENT ON COLUMN {Product}_DOM_STD_T.agreement.valid_from_dts IS
    'Inclusive start of business validity (UTC). Half-open period.';
COMMENT ON COLUMN {Product}_DOM_STD_T.agreement.valid_to_dts IS
    'Exclusive end of business validity (UTC); sentinel 9999-12-31 = current.';
COMMENT ON COLUMN {Product}_DOM_STD_T.agreement.is_current IS
    'Convenience currency flag; must agree with valid_to_dts sentinel.';
COMMENT ON COLUMN {Product}_DOM_STD_T.agreement.is_deleted IS
    'Logical deletion state; 1 requires deleted_dts. History retained.';
COMMENT ON COLUMN {Product}_DOM_STD_T.agreement.created_dts IS
    'Physical row-version creation time (UTC).';
COMMENT ON COLUMN {Product}_DOM_STD_T.agreement.updated_dts IS
    'Physical row last-change time (UTC).';
```

Every temporal/lifecycle column carries a comment (TLM-15). The bitemporal
variant (`SCD2_BITEMPORAL`) adds `transaction_from_dts` /
`transaction_to_dts` with the same types, sentinel, and comment discipline.

The 1:1 locking view:

```sql
REPLACE VIEW {Product}_DOM_STD_V.agreement
AS
LOCKING ROW FOR ACCESS
SELECT
      agreement_sk
    , agreement_bk
    , agreement_status
    , premium_amount
    , valid_from_dts
    , valid_to_dts
    , is_current
    , is_deleted
    , deleted_dts
    , created_dts
    , updated_dts
FROM {Product}_DOM_STD_T.agreement;
```

---

## 6. DML Maintenance Patterns

### 6.1 Standard version change (close + insert, one transaction)

```sql
BT;

UPDATE {Product}_DOM_STD_T.agreement
SET   valid_to_dts = :event_dts
    , is_current   = 0
    , updated_dts  = CURRENT_TIMESTAMP(6)
WHERE agreement_bk = :agreement_bk
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  -- Change detection: close only when the incoming version differs (TLM invariant 6)
  AND (agreement_status <> :new_status OR premium_amount <> :new_premium);

INSERT INTO {Product}_DOM_STD_T.agreement
      (agreement_sk, agreement_bk, agreement_status, premium_amount, valid_from_dts)
SELECT :new_sk, :agreement_bk, :new_status, :new_premium, :event_dts
WHERE NOT EXISTS (
    SELECT 1
    FROM {Product}_DOM_STD_T.agreement AS a
    WHERE a.agreement_bk = :agreement_bk
      AND a.valid_from_dts = :event_dts
);   -- Idempotent replay: re-running the same input inserts nothing (invariant 8)

ET;
```

Both statements commit or roll back together (invariant 7). The successor's
`valid_from_dts` equals the predecessor's new `valid_to_dts` — no gap, no
overlap.

### 6.2 Logical deletion

A deletion is a **new current version**, never an update-in-place:

```sql
BT;

UPDATE {Product}_DOM_STD_T.agreement
SET valid_to_dts = :deletion_dts, is_current = 0, updated_dts = CURRENT_TIMESTAMP(6)
WHERE agreement_bk = :agreement_bk
  AND valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00';

INSERT INTO {Product}_DOM_STD_T.agreement
      (agreement_sk, agreement_bk, agreement_status, premium_amount
     , valid_from_dts, is_deleted, deleted_dts)
VALUES (:new_sk, :agreement_bk, :last_status, :last_premium
     , :deletion_dts, 1, :deletion_dts);

ET;
```

Restoration inserts a further successor with `is_deleted = 0` (core §4.2).

### 6.3 Late-arriving change

Place the change at its actual effective instant and split the covering
period: close the covering version at `:late_dts`, insert the late version
`[:late_dts, original_valid_to_dts)`, preserving `is_current` on whichever
row now holds the sentinel. Splits follow the same close + insert
transaction shape as §6.1.

---

## 7. Default Current Access View

```sql
REPLACE VIEW {Product}_DOM_ACS_V.agreement_current
AS
LOCKING ROW FOR ACCESS
SELECT
      a.agreement_bk
    , a.agreement_status
    , a.premium_amount
    , a.valid_from_dts AS effective_since   -- optional exposure (core §8)
FROM {Product}_DOM_STD_V.agreement AS a
WHERE a.valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
  AND a.is_current = 1
  AND a.is_deleted = 0;
```

- Filters on the **authoritative** sentinel predicate *plus* the
  convenience flag (belt and braces; any disagreement is a TLM-10 defect
  that validation catches).
- Hides `valid_to_dts`, `is_current`, deletion metadata, and audit
  timestamps.
- Selects from `*_STD_V`, not the base table.

Point-in-time (as-of) access views use the half-open predicate:

```sql
WHERE a.valid_from_dts <= :as_of_dts
  AND :as_of_dts < a.valid_to_dts
```

---

## 8. Primary Index and Statistics Guidance

- **PI:** NUPI on the natural key (`agreement_bk`) for co-located joins
  across versions. Where uniqueness enforcement is preferred in-schema, use
  `UNIQUE PRIMARY INDEX (natural_key, valid_from_dts)`; otherwise enforce
  invariants 3-4 in maintenance code plus TLM validation.
- **Statistics** — collect after creation and refresh with maintenance:

```sql
COLLECT STATISTICS
      COLUMN (agreement_bk)
    , COLUMN (is_current)
    , COLUMN (valid_from_dts)
    , COLUMN (valid_to_dts)
    , COLUMN (agreement_bk, valid_from_dts)
ON {Product}_DOM_STD_T.agreement;
```

- The `valid_to_dts = sentinel` equality predicate is statistics-friendly:
  current rows cluster on a single value, so the optimiser estimates
  current-row selectivity well. This is a further reason validity bounds
  are non-null (core §7).

---

## 9. DBC Conformance Queries

Implementable checks for the Trust Engine (rule numbers from core §9).
`ColumnType` codes: `SZ` = `TIMESTAMP WITH TIME ZONE`, `TS` = `TIMESTAMP`,
`I1` = `BYTEINT`.

```sql
-- TLM-04: prohibited generic names on product objects
SELECT c.DatabaseName, c.TableName, c.ColumnName
FROM DBC.ColumnsV AS c
WHERE c.DatabaseName LIKE :product_db_pattern
  AND LOWER(TRIM(c.ColumnName)) IN
      ('created_at', 'created_timestamp', 'created_dt', 'updated_at'
     , 'updated_timestamp', 'valid_from', 'valid_to', 'effective_from'
     , 'effective_to', 'effective_date', 'expiration_date'
     , 'start_timestamp', 'end_timestamp', 'deleted_flag', 'active_ind');

-- TLM-05: temporal columns missing WITH TIME ZONE or microsecond precision
SELECT c.DatabaseName, c.TableName, c.ColumnName, c.ColumnType
FROM DBC.ColumnsV AS c
WHERE c.DatabaseName LIKE :product_db_pattern
  AND LOWER(TRIM(c.ColumnName)) LIKE '%!_dts' ESCAPE '!'
  AND (c.ColumnType <> 'SZ' OR c.DecimalFractionalDigits <> 6);

-- TLM-06: flags that are not BYTEINT NOT NULL
SELECT c.DatabaseName, c.TableName, c.ColumnName, c.ColumnType, c.Nullable
FROM DBC.ColumnsV AS c
WHERE c.DatabaseName LIKE :product_db_pattern
  AND LOWER(TRIM(c.ColumnName)) LIKE 'is!_%' ESCAPE '!'
  AND (c.ColumnType <> 'I1' OR c.Nullable = 'Y');
```

Data-level invariants (parameterise per SCD2 table):

```sql
-- TLM-09: more than one current row per natural key
SELECT agreement_bk, COUNT(*) AS current_rows
FROM {Product}_DOM_STD_V.agreement
WHERE valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
GROUP BY agreement_bk
HAVING COUNT(*) > 1;

-- TLM-10: flag / validity disagreement
SELECT agreement_bk, valid_from_dts, is_current, valid_to_dts
FROM {Product}_DOM_STD_V.agreement
WHERE (is_current = 1) <>
      (valid_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00');

-- TLM-08: overlapping periods per natural key
SELECT agreement_bk, valid_from_dts, valid_to_dts, next_from
FROM (
    SELECT agreement_bk, valid_from_dts, valid_to_dts
         , MIN(valid_from_dts) OVER (
               PARTITION BY agreement_bk
               ORDER BY valid_from_dts
               ROWS BETWEEN 1 FOLLOWING AND 1 FOLLOWING
           ) AS next_from
    FROM {Product}_DOM_STD_V.agreement
) AS t
WHERE next_from IS NOT NULL
  AND next_from < valid_to_dts;

-- TLM-11: deletion without deletion time
SELECT agreement_bk, valid_from_dts
FROM {Product}_DOM_STD_V.agreement
WHERE is_deleted = 1
  AND deleted_dts IS NULL;
```

---

## 10. Migration Guidance

1. **New products** apply this extension in full from first deployment.
2. **Legacy names** (core §10.1 mapping) migrate by adding canonical
   columns, backfilling, then retiring the legacy column behind a
   versioned compatibility view that projects both names during the
   deprecation window.
3. **DATE-grain validity** (Memory registry tables, Domain `_R`):
   `valid_from_dts = CAST(valid_from AS TIMESTAMP(6) WITH TIME ZONE AT
   TIME ZONE 'GMT')`; `valid_to = DATE '9999-12-31'` maps to the timestamp
   sentinel. Document that historical intra-day ordering is unavailable
   (core §10.2 rule 3).
4. **`BUS_V` / `ACL_V` databases** keep their names as registered legacy
   aliases; new Access Layer databases use `ACS_V`. Renames, where
   undertaken, ship as versioned compatibility (parallel database, view
   redirection, consumer cut-over, retirement) — never in-place.
5. **Field dialects** with no lifecycle columns at all (e.g.
   `rec_load_dts`-style audit trios) are non-conformant; bridge with
   compatibility views (constant `is_current = 1` is acceptable only in
   the bridge layer, never in regenerated base tables), then regenerate to
   the canonical contract.
