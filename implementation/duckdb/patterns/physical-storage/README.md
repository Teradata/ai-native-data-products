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

This pattern has no template. The baseline is DuckDB's native columnar storage in one database file. Tables carry only their key constraints; further indexing and storage layout are chosen from measured workloads. No external file, Parquet path, object-store mount, `httpfs` extension or approximate vector index is emitted, and no template installs or loads an extension.

DuckDB supports one writing process. Close and checkpoint a file before promoting it, and open readers read-only. Do not copy an active file without a consistent backup protocol. External storage, if an organisation adopts it, is a deployment dependency with its own credentials, extension versions and validation obligations; this binding does not render it.

The validator does not establish backup and restore, durability, replication, disaster recovery or performance. Publish operator evidence separately. Database files and rendered SQL belong in the user's output location, not this repository.

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
