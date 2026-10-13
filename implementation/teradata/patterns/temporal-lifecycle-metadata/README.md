---
title: Teradata Temporal Lifecycle Metadata Pattern Implementation
anchor: temporal-lifecycle-metadata
type: implementation
status: draft
version: 3.0
normative: true
implements: temporal-lifecycle-metadata
platform: teradata
---

# Teradata: Temporal Lifecycle Metadata

Binding of [Temporal Lifecycle Metadata](../../../../design/patterns/temporal-lifecycle-metadata.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`00-macros.sql.j2` holds the macros every other template imports. Each takes a relation from the context (an entity or a standard-owned relation, with its `columns`, `column_names`, `key_columns`, `version_columns` and placed `objects`) and composes no name:

| Macro | Emits |
|---|---|
| `sentinel` | The open end of an interval, `TIMESTAMP '9999-12-31 23:59:59.999999+00:00'`, written by every statement that opens a version and never as a `DEFAULT` (PLATFORM_PROFILE §7) |
| `cols`, `column`, `unicode`, `vector_pattern` | A quoted column list; one column definition with type, `CHARACTER SET UNICODE` for text, identity, `NOT NULL`, `UNIQUE`, and Enum, flag and vector-dimension checks |
| `primary_index`, `uniqueness`, `constraints` | The primary index chosen from the access path; uniqueness of each version (or a keymap's key); interval-order checks |
| `current` | The current-row predicate |
| `table` | `CREATE MULTISET TABLE`, the keymap foreign key (`WITH NO CHECK OPTION`) and the primary index |
| `module_tables` | Every persisted, defined, non-adopted relation of one module, keymaps first |
| `value`, `ref`, `insert`, `member` | A Python value as SQL; a subquery for a current row's key; an insert by logical attribute name with open-row values for temporal columns; whether an Enum permits a value |
| `comment` | A comment literal held to the dictionary's 255 characters |

`02-comments.sql.j2` applies `COMMENT ON TABLE` and `COMMENT ON COLUMN` to every persisted relation from its `description` and each column's description (or its logical name), after the tables and before anything depends on them.

`03-access-views.sql.j2` creates two views per persisted relation, each with `REPLACE VIEW` and `LOCKING ROW FOR ACCESS`, so a consumer never blocks a load:

- the **governed base view**, for every relation with a `base_view` object (this binding emits `base_view: all`): every column and every row, the full temporal contract. Teradata SQL has no table functions, so a read as at an instant applies the profile's predicates to this view; it is not granted to consumers, and the build reports the absence of a consumer point-in-time surface as a gap;
- the **consumer view**, for every relation with a `consumer_view` object: its current rows (the `current` macro) over the base view, carrying every column except the open interval ends `valid_to_dts` and `transaction_to_dts`. Runtime relations have no consumer view.

`04-maintenance.sql.j2` is caller-rendered with `entity`, `stable_key`, `effective_at`, `recorded_at` and `replacement_rows` (each keyed by physical column name). It is a transaction body: the caller controls the transaction and runs the checks before ending it. It:

- for a bitemporal relation, closes every open knowledge interval of the identity at `recorded_at` and clears its current flag;
- otherwise, closes the version whose validity covers `effective_at` at that instant;
- inserts every replacement row with every column: an open end given as `infinity` is written as the sentinel, an instant is cast to its timestamp type, and any other value goes through the literal filter.

It is not a change planner. The caller supplies complete, non-overlapping intervals (for a bitemporal correction, the whole new known timeline), detects unchanged replay, preserves unaffected segments and tombstones, and rejects non-monotonic correction instants. Teradata enforces none of the cross-row rules in its schema; the `entity temporal` check finds them.

`05-statistics.sql.j2` collects statistics on every persisted relation's key and version columns and its currency, deletion and interval-start columns (PLATFORM_PROFILE §6).

Validity and knowledge intervals are half-open; the sentinel appears only as an open end. For bitemporal history, overlap is prohibited only where both axes overlap. The current flag is true exactly when every applicable end is open.

## Capability bindings

| Capability | Binding |
|---|---|
| `CurrentStateFilter` | `current` macro behind the consumer views and reference checks. |
| `PointInTimeReconstruction` | The governed base view; the profile's predicates select the rows at an instant. No consumer surface: a reported gap. |
| `SoftDelete` | `is_deleted` and `deleted_dts`; the `entity temporal` check finds a disagreement; deleted rows are excluded from current reads. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
