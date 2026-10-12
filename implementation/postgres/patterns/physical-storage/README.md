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

This pattern has no template. The baseline is native, unpartitioned storage. The only indexes emitted are those the shared table macro creates: primary keys, unique keys, and for each history table a partial unique index on the current row and a GiST exclusion constraint over its intervals. Further indexing, statistics, vacuum and checkpoint settings, partitioning and storage layout are chosen from measured workloads; review the exclusion constraints before partitioning a history table. No external file, foreign table, object-store mount or approximate vector index is emitted.

The validator does not establish backup and restore, durability, replication, disaster recovery or performance. Publish operator evidence separately. Rendered SQL and deployment packages belong in the user's output location, not this repository.

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
