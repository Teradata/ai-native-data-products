---
title: PostgreSQL Physical Storage Implementation
anchor: physical-storage
type: implementation
status: draft
version: 2.0
normative: true
implements: physical-storage
platform: postgres
---

# PostgreSQL: Physical Storage

Binding of [Physical Storage](../../../../design/patterns/physical-storage.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

The baseline stores all data in native PostgreSQL heap tables with WAL-backed transactions. B-tree primary/unique indexes support identity lookup; GiST range exclusion enforces history integrity. `ANALYZE`, autovacuum, connection limits and backup/restore are operator responsibilities. Small fixture tables are deliberately unpartitioned.

For larger workloads, choose partition keys from measured access patterns and review uniqueness/exclusion behavior across partitions before migration. BRIN can suit append-ordered event time scans; measure with `EXPLAIN (ANALYZE, BUFFERS)` before adding indexes. JSONB runtime context is process metadata, not a substitute for typed Domain columns.

No object-store extension, foreign table, vector index or external file is required. This example does not prove backup durability, disaster recovery, replication or storage performance; the trust map keeps physical-storage unknown pending operator evidence.
