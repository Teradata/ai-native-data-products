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

Binding of [Temporal Lifecycle Metadata](../../../../design/patterns/temporal-lifecycle-metadata.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[model.py](../../model.py) owns shared lifecycle/audit fields; [render.py](../../render.py) emits constraints and views. Instants bind to `TIMESTAMPTZ`, flags to `BOOLEAN`, and open validity to PostgreSQL infinity. Sessions use UTC. Audit columns record actual deployment/write instants.

SCD2 uses `[valid_from_dts,valid_to_dts)`, primary key `(stable_key,valid_from_dts)`, a partial unique index for one current version, and a GiST exclusion constraint over key equality and `tstzrange(...,'[)')` overlap. The `btree_gist` extension supplies scalar equality operators. Deleted versions remain historical tombstones; current projections exclude them. CURRENT_STATE and EVENT_APPEND_ONLY do not receive historical lifecycle fields.

The [writer](../../temporal.py) locks each entity identity transactionally, splits late intervals, ignores unchanged replay and rejects conflicting existing boundaries. Exclusion constraints also protect against concurrent SQL writers. Sequence gaps are acceptable. `TLM` checks cover columns, types, finite event instants, intervals, currency, profiles and exact view projections. This is effective history, not bitemporal transaction-time reconstruction.
