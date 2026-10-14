---
title: DuckDB Temporal Lifecycle Metadata Implementation
anchor: temporal-lifecycle-metadata
type: implementation
status: draft
version: 2.0
normative: true
implements: temporal-lifecycle-metadata
platform: duckdb
---

# DuckDB: Temporal Lifecycle Metadata

Binding of [Temporal Lifecycle Metadata](../../../../design/patterns/temporal-lifecycle-metadata.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`00-macros.sql.j2` holds the macros every other template imports. Each takes a relation from the context (an entity or a standard-owned relation, with its `columns`, `column_names`, `key_columns`, `version_columns` and placed `objects`) and composes no name:

| Macro | Emits |
|---|---|
| `cols`, `column` | A quoted column list; one column definition with type, sequence default, `NOT NULL`, `UNIQUE` and Enum check |
| `primary_key`, `constraints` | The key (version columns plus interval starts for history); interval-order, current-flag and deletion-flag checks |
| `current`, `at` | The current-row predicate; the half-open point-in-time predicate on `valid_at` and, when bitemporal, `known_at` |
| `table` | `CREATE TABLE` with the keymap foreign key |
| `module_tables` | Every persisted, defined, non-adopted relation of one module, keymaps first, each preceded by `CREATE SEQUENCE` where it has an `objects.sequence` |
| `value`, `ref`, `insert`, `member` | A Python value as SQL; a subquery for a current row's key; an insert by logical attribute name with open-row defaults for temporal columns; whether an Enum permits a value |

DuckDB has no partial unique indexes or exclusion constraints, so `table` emits neither: one open version per identity and non-overlapping intervals are proved by the `entity temporal` check and by serialised writer discipline. A direct SQL write can violate them until the check runs.

`02-comments.sql.j2` applies `COMMENT ON TABLE` and `COMMENT ON COLUMN` to every persisted relation from its `description` and each column's description (or its logical name), after the tables and before anything depends on them; DuckDB dependencies can block a later comment change.

`03-access-views.sql.j2` creates, for every relation with a `consumer_view` object, a view of its current rows (the `current` macro) carrying every column except the open interval ends `valid_to_dts` and `transaction_to_dts`. Runtime relations have no consumer view. For every relation with a `function` object it creates a point-in-time table macro `(valid_at)`, or `(valid_at, known_at)` when bitemporal, returning the table's rows at that instant. Macro parameters are untyped: pass `TIMESTAMPTZ` values.

`04-maintenance.sql.j2` is caller-rendered with `entity`, `stable_key`, `effective_at`, `recorded_at` and `replacement_rows` (each keyed by physical column name). It is a transaction body: the caller controls `BEGIN` and `COMMIT` on the single writing connection, retries a transaction conflict and runs the checks before committing. It:

- for a bitemporal relation, closes every open knowledge interval of the identity at `recorded_at` and clears its current flag;
- otherwise, closes the version whose validity covers `effective_at` at that instant;
- inserts every replacement row with every column, each value through the literal filter.

It is not a change planner. The caller supplies complete, non-overlapping intervals (for a bitemporal correction, the whole new known timeline), detects unchanged replay, preserves unaffected segments and tombstones, and rejects non-finite or non-monotonic correction instants. Pass an open end as the text `infinity`; the Python driver turns infinity into a finite datetime.

Validity and knowledge intervals are half-open; infinity appears only as an open end. For bitemporal history, overlap is prohibited only where both axes overlap. The current flag is true exactly when every applicable end is open.

## Capability bindings

| Capability | Binding |
|---|---|
| `CurrentStateFilter` | `current` macro behind the consumer views and reference checks. |
| `PointInTimeReconstruction` | `at` macro behind the point-in-time table macros. |
| `SoftDelete` | `is_deleted` and `deleted_dts` with a consistency check; deleted rows are excluded from current and point-in-time reads. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
