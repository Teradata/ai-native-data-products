---
title: Teradata Temporal Lifecycle Metadata Pattern Implementation
anchor: temporal-lifecycle-metadata
type: implementation
status: standard
version: 2.0
normative: true
implements: temporal-lifecycle-metadata
platform: teradata
---

# Teradata: Temporal & Lifecycle Metadata Implementation

Teradata binding of [`design/patterns/temporal-lifecycle-metadata.md`](../../../../design/patterns/temporal-lifecycle-metadata.md). Read the pattern first; nothing here changes its semantics. Targets Teradata v20.0; conformance queries use `DBC` dictionary views.

## Files

| File | Purpose |
|------|---------|
| `01-ddl-template.sql.j2` | SCD2 history table (`SCD2_HISTORY`) with the canonical columns, flags, sentinel default, and column comments; plus the 1:1 governed locking view. |
| `02-dml-maintenance.sql` | Version change (close + insert, one transaction), logical deletion, late-arriving change. |
| `03-access-views.sql` | Default current access view and point-in-time (as-of) predicate. |
| `04-statistics.sql` | Primary-index and `COLLECT STATISTICS` guidance. |
| `conformance-queries.sql` | `DBC` and data-level checks for the pattern's conformance rules (TLM-04…11). |

## Type and flag bindings

| Pattern concept | Teradata binding |
|-----------------|------------------|
| All `*_dts` columns | `TIMESTAMP(6) WITH TIME ZONE`, persisted normalised to UTC (`+00:00`). |
| Day-grain event (`*_date`) | `DATE`: never for validity bounds or audit. |
| Flags (`is_current`, `is_deleted`, `is_active`) | `BYTEINT NOT NULL` with `CHECK (col IN (0,1))`. |
| Open-end sentinel | `TIMESTAMP '9999-12-31 23:59:59.999999+00:00'` (always with `+00:00`). |
| Row audit defaults | `NOT NULL DEFAULT CURRENT_TIMESTAMP(6)`. |

`TIMESTAMP(6)` **without** `WITH TIME ZONE` is non-conformant (TLM-05): it makes the UTC persistence rule unverifiable and the sentinel ambiguous under session-zone changes. Single-character `'Y'/'N'` encodings and nullable flags are non-conformant (TLM-06).

## Surface bindings (pattern: Access Exposure Policy)

| Object | Pattern surface | Responsibility |
|--------|-----------------|----------------|
| Physical table (`{db}.agreement`) | - | Full canonical column contract; no direct consumer access. |
| Governed view (`{db}.v_agreement`) | Governed full-contract surface | 1:1 `LOCKING ROW FOR ACCESS` view exposing every column. |
| Access views (`{db}.agreement_current`, …) | Default current / purpose-specific | Select from the governed view, never the base table (TLM-14). |

Database/layer naming is owned by the [object-placement](../object-placement/) implementation; the generic tags here bind there.

## Conformance rules → checks

| Rule | Check |
|------|-------|
| TLM-04 (prohibited names) | `conformance-queries.sql` §1: catalogue scan for banned column names. |
| TLM-05 (type/precision) | `conformance-queries.sql` §2: `*_dts` columns not `TIMESTAMP(6) WITH TIME ZONE`. |
| TLM-06 (flag representation) | `conformance-queries.sql` §3: `is_*` columns not `BYTEINT NOT NULL`. |
| TLM-08/09/10/11 (data invariants) | `conformance-queries.sql` §4: overlap, multiple current, flag disagreement, deletion without time. |
