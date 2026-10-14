---
title: DuckDB Physical Storage Implementation
anchor: physical-storage
type: implementation
status: draft
version: 2.0
normative: true
implements: physical-storage
platform: duckdb
---

# DuckDB: Physical Storage

Binding of [Physical Storage](../../../../design/patterns/physical-storage.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

The baseline is DuckDB's native columnar storage in one database file. Tables are unindexed beyond key constraints; indexing and storage layout are selected from measured workloads. No external file, Parquet path, object-store mount, httpfs extension or approximate vector index is assumed by the templates, and a test asserts none is emitted.

DuckDB supports one writing process. Close and checkpoint a file before promoting it, and open readers read-only. Do not copy an active file without a consistent backup protocol. External storage, if an organisation profile later selects it, becomes a deployment dependency with its own credentials, extension versions and validation obligations; this binding does not render it.

The validator does not establish backup and restore, durability, replication, disaster recovery or performance. Publish operator evidence separately. Generated database files and deployment packages belong in the user's output location, not this repository.

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
