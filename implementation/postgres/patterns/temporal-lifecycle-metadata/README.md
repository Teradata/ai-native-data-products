---
title: PostgreSQL Temporal Lifecycle Metadata Implementation
anchor: temporal-lifecycle-metadata
type: implementation
status: draft
version: 2.0
normative: true
implements: temporal-lifecycle-metadata
platform: postgres
---

# PostgreSQL: Temporal Lifecycle Metadata

Binding of [Temporal Lifecycle Metadata](../../../../design/patterns/temporal-lifecycle-metadata.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`00-temporal-macros.sql.j2` owns canonical fields, current filters and point-in-time predicates. `01-entity.sql.j2` emits generic DDL; `02-comments.sql.j2` is a separate metadata step; `03-access-views.sql.j2` emits explicit consumer projections and historical functions/macros. All supported profiles are selected by input, never by table name.

Validity and knowledge intervals are half-open. For bitemporal history, overlap is prohibited only where both axes overlap; different knowledge-time versions may cover the same valid time. is_current requires both applicable ends to be open. PostgreSQL uses two-dimensional GiST exclusion via btree_gist; DuckDB uses conformance checks and serialized writer discipline.

`04-maintenance.sql.j2` is a transaction body for a caller-planned replacement timeline. For bitemporal corrections it closes open knowledge intervals and inserts the complete new known business timeline. It is not an automatic change planner: the caller must detect unchanged replay, preserve unaffected segments and tombstones, reject non-finite/non-monotonic correction instants, serialize DuckDB writes and run conformance before commit. SCD2 replacements must preserve the predecessor end and split late changes without losing successors.

Generated checks verify physical columns/comments, finite non-validity timestamps, non-overlap, ordered bounds and flags. Native tests prove two-axis reconstruction. Full replay, late-change planning, concurrent writer stress and data-specific temporal completeness remain deployment obligations.

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
