---
title: PostgreSQL Platform Profile
anchor: postgres
type: platform-profile
status: draft
version: 2.0
normative: false
platform: postgres
---

# PostgreSQL platform profile

Target PostgreSQL 16+ with `btree_gist`. The reference has been exercised on embedded PostgreSQL 18.3 (PGlite 0.5.8), not a native production server. Python uses Psycopg 3 and `%s` parameter binding. Generated SQL is also executable directly with psql. All object names in the fixed model are trusted lowercase identifiers; this is not an arbitrary SQL-template input interface.

| Logical concern | Binding | Classification |
|---|---|---|
| Identifier / stable allocation | BIGINT identity in permanent natural-key keymaps; atomic upsert | Native |
| Timestamp / open end | TIMESTAMPTZ, UTC sessions, infinity sentinel | Native |
| Flag / text / decimal / process JSON | BOOLEAN / VARCHAR / NUMERIC / JSONB | Native |
| Effective-history integrity | Half-open tstzrange exclusion, partial current uniqueness | Adapted; requires supplied btree_gist extension |
| Point-in-time reconstruction | STABLE SQL functions with explicit timestamp arguments | Adapted |
| Rich metadata | COMMENT plus pg_catalog, joined to authored metadata | Native and adapted |
| Recursive discovery | Bounded recursive CTEs with visited arrays | Native |
| Access / runtime privacy | NOLOGIN group roles, view grants and USER RLS | Native; login provisioning external |
| Embed | Reproducible lexical SQL encoder | Demonstration; semantic quality unassessed |
| NearestNeighbors | Exact cosine over three-element float8 arrays | Adapted; no approximate index |
| ApproxIndex | Optional pgvector HNSW/IVFFlat | External extension; not deployed |
| Bitemporal / as-known history | Not selected by this fixture | Unsupported in this example |
| Backup, HA, external storage, production ML | Operator/service evidence | External; not validated |

PostgreSQL arrays do not enforce a declared dimension; checks must enforce cardinality, shape and element validity. JSONB supports equality/set operations used by conformance queries. `TIMESTAMPTZ` preserves instants, not the original input time-zone label. Python's datetime cannot represent infinity: the temporal writer reads validity ends as text to preserve the sentinel.

Sequences may have gaps, including after rollback; permanence, not contiguity, is the identifier contract. Keymaps use sequence allocation starting at 1000 to leave room for fixture ids 1..12. When importing other data, reconcile sequence positions as part of the migration. No destructive rebuild option is provided.

Keep small tables unpartitioned. Index measured join and time predicates, maintain statistics and autovacuum, and review constraints before partitioning history. The range constraint is concurrency-safe at the database level; the writer also locks per identity. Native concurrent-writer, durability and recovery testing remains outstanding.

Runtime RLS uses session_user, not a user-controlled setting. It requires separate authenticated identities; shared application logins cannot distinguish end users. Shared scopes are denied pending a membership policy. Owners, superusers and BYPASSRLS users remain trusted administrators. Public function execution is revoked; historical functions remain administrative, while approved search functions use invoker rights.

Authoritative references: [range exclusion constraints](https://www.postgresql.org/docs/16/rangetypes.html#RANGETYPES-CONSTRAINT), [row security and bypass boundaries](https://www.postgresql.org/docs/16/ddl-rowsecurity.html), and [function execution/security](https://www.postgresql.org/docs/16/sql-createfunction.html).
