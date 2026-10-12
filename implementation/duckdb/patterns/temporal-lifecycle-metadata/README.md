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

`00-temporal-macros.sql.j2` owns canonical fields, current filters and point-in-time predicates. `01-entity.sql.j2` emits generic DDL; `02-comments.sql.j2` is a separate metadata step; `03-access-views.sql.j2` emits explicit consumer projections and historical table macros. All supported profiles are selected by input, never by table name. Timestamps are `TIMESTAMPTZ`; an open end is `'infinity'::TIMESTAMPTZ`.

Validity and knowledge intervals are half-open. For bitemporal history, overlap is prohibited only where both axes overlap; different knowledge-time versions may cover the same valid time. `is_current` requires both applicable ends to be open. DuckDB has no exclusion constraints or partial unique indexes, so non-overlap and single-current rules are enforced by the generated conformance checks and by serialized writer discipline, not by the engine. A direct SQL write can violate them until a check runs.

`04-maintenance.sql.j2` is a transaction body for a caller-planned replacement timeline. For bitemporal corrections it closes open knowledge intervals and inserts the complete new known business timeline. It is not an automatic change planner: the caller must detect unchanged replay, preserve unaffected segments and tombstones, reject non-finite or non-monotonic correction instants, use one writing connection and run conformance before commit. SCD2 replacements must preserve the predecessor end and split late changes without losing successors. Python must not round-trip an open end through a finite datetime; pass `'infinity'` as text.

Generated checks verify physical columns and comments, finite non-validity timestamps, non-overlap, ordered bounds and flags. Native tests prove half-open boundaries, effective-history replay, late change, deletion and restoration, rollback of a failed replacement, and two-axis reconstruction using a test-only planner. Full replay planning, concurrent writer stress and data-specific temporal completeness remain deployment obligations.

## Capability bindings

| Capability | Binding |
|---|---|
| `CurrentStateFilter` | `tlm.current` predicate used by the access views and checks. |
| `PointInTimeReconstruction` | `tlm.at` predicate behind the `at_` table macros. |
| `SoftDelete` | Tombstone successor with `is_deleted` and `deleted_dts`; predecessors retained. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
