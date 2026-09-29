---
title: DuckDB Temporal Lifecycle Metadata Implementation
anchor: temporal-lifecycle-metadata
type: implementation
status: standard
version: 2.0
normative: true
implements: temporal-lifecycle-metadata
platform: duckdb
---

# DuckDB temporal binding

Binding of [temporal-lifecycle-metadata](../../../../design/patterns/temporal-lifecycle-metadata.md). Shared fields are defined once in [model.py](../../model.py); generated module schemas carry comments and constraints.

**Provides:**

| Capability | Binding |
|---|---|
| `CurrentStateFilter` | Canonical views require is_current and infinity end; exclude deleted rows. |
| `PointInTimeReconstruction` | `at_<entity>(instant)` table macros use inclusive start / exclusive end. |
| `SoftDelete` | Tombstone successor with deletion timestamp, retaining prior versions. |

Every persisted entity is registered with exactly one profile. History and documentation use SCD2_HISTORY; current registries/keymaps/runtime use CURRENT_STATE; operational and validation evidence use EVENT_APPEND_ONLY. All have created_dts and updated_dts. Event tables have a named event instant. Flags are non-null BOOLEAN, instants TIMESTAMPTZ; session rendering is UTC. No bitemporal profile is claimed.

Open validity is non-null `infinity`; never use a sentinel for events. Every interval satisfies start < end. Primary keys use identity + valid_from_dts. Cross-row non-overlap and single-current conditions require the transactional writer plus runnable checks; they are not enforced by a fictitious exclusion constraint. Tables are the governed full contract. Canonical views explicitly project business columns and valid_from_dts, hiding audit/deletion/currency metadata. As-of macros expose the full contract for history-aware use.

[temporal.py](../../temporal.py) handles unchanged input, replay, successor insertion and late interval splitting in one transaction. Conflicting input at an already recorded boundary is rejected: it is a correction-policy question, not silent data replacement. Restore a deleted entity by adding a later non-deleted successor. Permanent keymaps must never be cleared. A serial host writer is required; admin SQL can bypass the maintenance API. Prediction prohibits retrospective rewrites and validity before observation; as-known corrections require a separately designed bitemporal binding.

The `C360-TLM-*` profile checks required fields, profiles, timestamp/flag types, finite event timestamps, overlaps, current uniqueness, flag/end agreement and exact current-surface row sets. Corpus lint checks prohibited names. Behavioural tests cover boundary instants, unchanged replay, late changes, deletion/restoration, stable keys and rollback. `is_active` appears only on lineage definitions, whose comment declares owner/retirement semantics. No inclusive-end arithmetic is used.
