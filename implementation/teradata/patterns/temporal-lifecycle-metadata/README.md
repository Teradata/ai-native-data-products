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
| `00-temporal-macros.sql.j2` | **The single definition site for the temporal and lifecycle columns.** Every table in every module imports it. |
| `01-ddl-template.sql.j2` | SCD2 history table (`SCD2_HISTORY`) with the canonical columns, flags, and column comments; plus the 1:1 governed locking view. Built from the macros, like any other table. |
| `02-dml-maintenance.sql` | Version change (close + insert, one transaction), logical deletion, late-arriving change. |
| `03-access-views.sql` | Default current access view and point-in-time (as-of) predicate. |
| `04-statistics.sql` | Primary-index and `COLLECT STATISTICS` guidance. |
| `conformance-queries.sql` | `DBC` and data-level checks for the pattern's conformance rules (TLM-04…11). |

## How a table gets its temporal columns

A table does not spell them out. It declares a profile and imports the macros:

```jinja
{% import 'patterns/temporal-lifecycle-metadata/00-temporal-macros.sql.j2' as tlm %}

CREATE TABLE {{ product }}_Domain.party (
    party_id    BIGINT NOT NULL,
    party_key   VARCHAR(60) NOT NULL,
{{ tlm.columns('SCD2_HISTORY', pad=20, supports_deletion=true) }}
)
PRIMARY INDEX (party_key);

{{ tlm.comments(product ~ '_Domain.party', 'SCD2_HISTORY', supports_deletion=true) }}
```

Three macros: `columns` for the definitions, `comments` for the matching `COMMENT ON COLUMN` statements (TLM-15), and `select_list` for a governed full-contract view body. The macro file documents the arguments and what each profile contributes.

**This is the implementation-side counterpart of a design rule.** The [Design Language](../../../../design/core/DESIGN_LANGUAGE.md) authoring checklist requires that cross-cutting concerns are *referenced* by pattern anchor and never restated inline, and the module documents follow it: a `History` entity does not list its validity pair, because the pattern supplies it. Until these macros existed, that rule stopped at the design boundary. Every implementation table transcribed the block as literal text, conformance was a matter of typing it correctly, and thirty tables across six modules drifted to `created_at`, `created_timestamp`, and a DATE-grain `valid_from`/`valid_to`. Renaming them was the smaller half of the fix; the reason they could drift was that nothing owned the names on this side.

Two consequences worth stating plainly:

- **A macro argument must be an expression, not a quoted placeholder.** `tlm.comments('{{ product }}_Memory.Change_Log', …)` renders the placeholder literally, because it is already inside a Jinja expression. Write `product ~ '_Memory.Change_Log'`.
- **An unknown profile emits a line that cannot parse as SQL.** Jinja has no portable raise, and a table whose temporal block came out empty is precisely the failure this file exists to prevent, so the deploy fails on the statement instead.

Plain `.sql` files cannot import: `conformance-queries.sql`, `02-dml-maintenance.sql`, and the two files that define columns without being templates, `modules/semantic/03-registry.sql` and `patterns/access-layer/dd-access-001.sql`. They reference a shared `governance` container or a fixed statement and take no product variable, so making them templates would change how they are deployed to buy nothing. They are covered by the `tlm-04` check in `tooling/validation/design_lint.py`, which reads the prohibited names from the pattern document and scans every SQL artifact: composition where the mechanism exists, enforcement everywhere.

## Type and flag bindings

| Pattern concept | Teradata binding |
|-----------------|------------------|
| All `*_dts` columns | `TIMESTAMP(6) WITH TIME ZONE`, persisted normalised to UTC (`+00:00`). |
| Day-grain event (`*_date`) | `DATE`: never for validity bounds or audit. |
| Flags (`is_current`, `is_deleted`, `is_active`) | `BYTEINT NOT NULL` with `CHECK (col IN (0,1))`. |
| Open-end sentinel | `TIMESTAMP '9999-12-31 23:59:59.999999+00:00'` (always with `+00:00`), written at INSERT time. |
| Row audit defaults | `NOT NULL DEFAULT CURRENT_TIMESTAMP(6)`. |

**The sentinel is an INSERT-time value, never a `DEFAULT` clause.** The driver hangs parsing a zone-qualified timestamp literal inside a `DEFAULT` clause during `CREATE TABLE`: a silent timeout rather than an error, so the failure surfaces minutes later with nothing to read (see [PLATFORM_PROFILE](../../PLATFORM_PROFILE.md), SQL idioms and driver constraints). Independently of the driver, a `DEFAULT` on a mandatory validity bound reads as though the value were optional, which it is not: every statement that opens a version states the sentinel, as `02-dml-maintenance.sql` does.

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
| TLM-04 (prohibited names) | Two checks, at different times. `tooling/validation/design_lint.py` (`tlm-04`) scans every `.sql` and `.sql.j2` artifact at commit time, reading the prohibited names from the pattern document itself so the list is never copied. `conformance-queries.sql` §1 is the catalogue scan of a deployed database; §1b resolves `effective_date` / `expiration_date` against the declared temporal profile, since they are permitted on `CURRENT_STATE` and prohibited elsewhere. The linter deliberately checks only the names decidable from a file alone, which is why its set matches §1 exactly. |
| TLM-05 (type/precision) | `conformance-queries.sql` §2: `*_dts` columns not `TIMESTAMP(6) WITH TIME ZONE`. |
| TLM-06 (flag representation) | `conformance-queries.sql` §3: `is_*` columns not `BYTEINT NOT NULL`. |
| TLM-08/09/10/11 (data invariants) | `conformance-queries.sql` §4: overlap, multiple current, flag disagreement, deletion without time. |
