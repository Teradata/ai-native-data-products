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

Binding of [Physical Storage](../../../../design/patterns/physical-storage.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

The baseline is native database storage. Small tables are unpartitioned; indexing, statistics, vacuum/checkpoint and storage layout are selected from measured workloads. No external file, object-store mount or approximate vector index is assumed by the templates.

PostgreSQL uses B-tree identity indexes and GiST history exclusion; review constraint behavior before partitioning. DuckDB uses its native columnar storage and transaction model. File permissions and serving processes are its access boundary.

The validator does not establish backup/restore, durability, replication, disaster recovery or performance. Publish operator evidence separately. Generated database files and deployment packages belong in the user's output location, not this skill.

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
