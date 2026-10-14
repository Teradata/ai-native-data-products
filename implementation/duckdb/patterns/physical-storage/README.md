---
title: DuckDB Physical Storage Implementation
anchor: physical-storage
type: implementation
status: standard
version: 2.0
normative: true
implements: physical-storage
platform: duckdb
---

# DuckDB physical storage

Binding of [physical-storage](../../../../design/patterns/physical-storage.md). The core example uses internal local storage; the optional external convention below is not an asserted object-storage deployment.

## 1. Storage Platform Declaration

Default: a local DuckDB file, no OTF and no remote dependency. Companion: [object-placement](../object-placement/). Optional exports use raw Parquet in a separately approved bucket/region or local directory; no snapshot/ACID OTF semantics are implied. All core tables remain internal. A remote profile requires approved service, region and credentials before deployment.

## 2. Path Model

Core path is environment_root/product_name.duckdb. Optional export prefix is `bucket/products/environment/product/module/object/release/`, with raw segments. One approved bucket per classification is the default external policy, to keep authorization review simple. Views have no physical paths. Development and production use distinct environment segments and credentials. Credentials never live in the product file.

## 3. Path Derivation Pattern

`derive_path(logical_container_name, object_name, bucket)` additionally requires the deployment's environment and immutable release id. Split logical_container_name as product.module, validate every segment against `[a-z][a-z0-9_]*` (release may include digits and hyphens), then return `bucket/products/environment/product/module/object/release/` with exactly one separator and trailing slash. Reject traversal and unconfigured inputs.

Examples: `s3://approved/products/dev/customer360/domain/customer/r1/`; `s3://approved/products/test/customer360/domain/customer/r1/`; `s3://approved/products/prod/customer360/domain/customer/r2/`. Exports never become prerequisites for the portable file.

## 4. File Format and Encoding

DuckDB internal columnar encoding is engine-managed. Optional exports are Parquet with ZSTD, explicit timestamp and decimal schema, and canonical column names. No CSV as governed persistent storage. Additive nullable fields require schema validation; incompatible changes publish a new immutable release. Raw Parquet has no OTF schema transaction or time-travel guarantee. Import into internal tables to restore self-containment.

## 5. Partition Strategy

None for the small reference. Optional large exports may use one declared business-date partition key; document units and grain, cap at one key to prevent tiny-file explosion, and publish a new release when changing partition layout. Never partition by a unique identifier.

## 6. Retention and Lifecycle

Core history, keymaps, documentation and lineage definitions last for product life. Demo events retain 90 days and validation 365 days; the operator executes archival. No automatic deletion occurs. External releases remain immutable until the owner confirms no reader references them; orphan cleanup requires a manifest comparison and approval. No OTF snapshots exist. Retire a workstream by removing references, archiving required releases, then deleting eligible assets under the owner's policy.

## 7. Access Model

OS ACLs protect local files; approved IAM/bucket policies protect exports. Physical access must never exceed logical access: consumers requiring view-only restrictions must not receive the underlying file/bucket credentials. A host-mediated query service enforces that boundary. Restrict bucket principals to the declared environment/prefix, deny public access and cross-service credentials by default, and independently audit privileged exporters. None of this is enforced by DuckDB schema names.

## 8. Validation Procedure

The core tests build, checkpoint, close and reopen the file read-only without external dependencies. For an external deployment, the operator must enumerate its manifest, compare every URI with derive_path, inspect Parquet schema/compression and partition keys, list the governed prefix to identify stray files, and verify positive/negative IAM tests for each mapped tier. Halt and report any mismatch; never silently relocate or delete. These checks cannot run without an external deployment, so physical-operations confidence is explicitly unknown in the example.
