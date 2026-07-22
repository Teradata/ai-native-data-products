# Teradata — Physical Storage (conforming reference implementation)

A conforming implementation of the
[`physical-storage`](../../../../design/patterns/physical-storage.md) interface spec, for Teradata
deployments that use **object storage with an Open Table Format** (Teradata's Open Table Format /
Lake support over Iceberg on S3/ADLS/GCS). It is the companion to the
[object-placement](../object-placement/) implementation.

**Applicability.** For all-block-storage Teradata deployments this pattern does not apply and
object-placement alone suffices. Deploy this only for the subset of objects held in object storage;
Section 1 must declare that subset.

## Section 1 — Storage Platform Declaration
Object store: Amazon S3 (region-pinned). OTF: Apache Iceberg. Companion:
`implementation/teradata/patterns/object-placement`. Governs OTF tables only; volatile/temporary
tables remain on block storage and are excluded.

## Section 2 — Path Model
One bucket per environment tier. Logical `{{Product}}_{{Module}}` maps to the path prefix
`{{product}}/{{module}}/`. Root prefix `/data/`. Segments use raw values. Views have no physical
path. Environment separation is by bucket, not by path.

## Section 3 — Path Derivation Pattern
```
derive_path(logical_container_name, object_name, bucket):
    (product, module) = split(logical_container_name, '_')
    return bucket || '/data/' || lower(product) || '/' || lower(module) || '/' || object_name || '/'
```
Examples (bucket `s3://c360-prod`): `Customer360_Domain` + `party` →
`s3://c360-prod/data/customer360/domain/party/`; dev bucket `s3://c360-dev` yields the same suffix
under a different bucket.

## Section 4 — File Format and Encoding
Default Parquet with ZSTD compression. Schema evolution: add-nullable-column and widen-type permitted
in place; rename and type-narrowing require a new table version. CSV/JSON never used for persistent
tables.

## Section 5 — Partition Strategy
Hidden (Iceberg) partitioning. Time-based tables partition by `month(valid_from_dts)` or
`month(<event>_dts)`. High-cardinality columns are excluded as partition keys. Maximum two partition
columns. Partition-spec changes are applied via Iceberg partition evolution, not table rebuild.

## Section 6 — Retention and Lifecycle
Core model: indefinite. Staging: 7 days. Snapshots retained 30 days for time travel. Orphan-file
cleanup weekly. Cold data tiers to infrequent-access storage after 90 days. Workstream retirement
archives then deletes the path prefix. A scheduled maintenance agent executes lifecycle actions.

## Section 7 — Access Model
Bucket policies + IAM roles mapped 1:1 to the product roles from
[access-layer](../access-layer/). **Physical access never exceeds logical access:** a principal with
read on the view database must not hold direct S3 read on the underlying table's prefix. Production
bucket requires MFA-delete. External engines (Spark, Trino) accessing the store are governed by the
same IAM mapping and audited.

## Section 8 — Validation Procedure
Agent-executable checks (halt and report on failure): the object-store path exists and matches
`derive_path`; data-file format is Parquet; the Iceberg partition spec matches Section 5; no data
files exist at non-conforming prefixes; no IAM principal has broader physical access than its logical
grant permits.
