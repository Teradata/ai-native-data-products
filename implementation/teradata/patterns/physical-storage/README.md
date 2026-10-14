---
title: Teradata Physical Storage Pattern Implementation
anchor: physical-storage
type: implementation
status: draft
version: 3.0
normative: true
implements: physical-storage
platform: teradata
---

# Teradata: Physical Storage

Binding of [Physical Storage](../../../../design/patterns/physical-storage.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

This pattern has no template. Every table is created in Teradata's own block storage: a `MULTISET` table with the primary index the [shared macros](../temporal-lifecycle-metadata/README.md) choose from its access path, and statistics collected on its key, versioning and temporal columns after deployment. No secondary, join or partitioned primary index, column partitioning or compression is emitted; those are chosen from measured workloads, following the advice in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md) §§1 to 6.

No table is placed in object storage. An organisation profile with the `Storage Section` headings (object storage under an open table format) is honoured by no template: the build creates its tables in block storage and reports the storage placement in the manifest as a gap.

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
