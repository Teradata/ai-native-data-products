# Customer360 on PostgreSQL

An executable sibling of [Customer360 on DuckDB](../customer360-duckdb/), using the same small synthetic business scenario to make platform differences visible. It adds server roles, USER row security, identity allocation and database-enforced history exclusion. All six modules and both Memory facets are included.

Follow the [PostgreSQL implementation instructions](../../implementation/postgres/README.md) to build an empty dedicated database, validate it and run [agent_demo.sql](agent_demo.sql). The Python build publishes only if all defined checks pass; SQL-only deployment starts with unknown trust until evidence is published. No existing database is erased or replaced.

## Fixed design brief

The authoritative entities are Customer, Product, Account and Transaction. Each has a permanent natural-key keymap and SCD2 business history. Customer owns Account; Account selects Product; Transaction references Account. Search references Product and joins back for descriptions. Prediction references Customer and computes clipped posted spend/1000 at monthly observation cutoffs, then the illustrative score `1 - spend_intensity`. This is a teaching fixture, not a trained financial model.

The seed has three customers (one tombstoned and without accounts), three products, three accounts and twelve transactions. Customer history includes a segment change and deletion; feature history contains two monthly snapshots. Nullable retirement/session-end/deletion fields exercise null semantics. Documentation captures rationale, glossary, queries and release records inside Memory.

| Decision | Selected answer and reason |
|---|---|
| DEC-TEMPORAL-PATTERN | SCD2 effective history, a departure from bitemporal: no as-known correction use case in this fixture. Runtime/current registries and append-only events use their own profiles. |
| DEC-COLUMN-STRATEGY | Canonical lifecycle/audit columns inline; operational evidence and quality separate in Observability. |
| DEC-SURROGATE-ALLOCATION | Permanent keymap identity sequences, atomic upsert and foreign-key history binding. |
| DEC-DELETE-STRATEGY | Versioned soft-delete tombstones; current views omit deleted rows. |
| DEC-TIMESTAMP-ZONE | Zone-aware timestamps; sessions and published instants use UTC. |
| DEC-QUALITY-STORAGE | Observability owns quality measurements; Semantic exposes discovery references. |
| DEC-AUDIT-RETENTION | Definitions for product life, events 90 days, validation 365 days; an explicit demo policy executed by operators, not automatic deletion. |

## Placement and access

The declared placement is one database per product/environment with schemas `memory`, `semantic`, `domain`, `observability`, `search`, `prediction`. Environment labels belong in the database/connection. The product registry identity is `customer360`; its approved initial business surface is `domain.v_customer`. Consumers resolve further surfaces from orientation and access registries.

The three group roles are `customer360_role_read`, `customer360_role_agent`, `customer360_role_admin`. PostgreSQL roles are cluster-wide, so this fixed example requires unused names. Assign real login memberships separately. USER runtime ownership is checked against session_user; the synthetic `demo-user` runtime rows are intentionally invisible to other unprivileged logins. Team/organization/agent sharing is not configured.

The input sources are [model.py](../../implementation/postgres/model.py), [seed.sql](seed.sql), authored implementation SQL and [render.py](../../implementation/postgres/render.py). `build.sql`, `registration.sql`, module schemas and conformance SQL are generated and checked in. No external model API, vector extension or object storage is needed.
