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

## 1. Scope

Target PostgreSQL 16+. The module and pattern directories bind platform-neutral contracts through Jinja; no product model is selected by this profile.

## 2. Type bindings

| Logical type | Physical binding |
|---|---|
| Identifier / Reference | BIGINT |
| NaturalKey / Code / Text | VARCHAR or TEXT |
| Integer / Decimal | INTEGER / DECIMAL(p,s) |
| Flag | BOOLEAN |
| Timestamp / Date | TIMESTAMPTZ / DATE; UTC sessions |
| Vector[n] | DOUBLE PRECISION[] with explicit dimension checks |
| Process JSON | JSONB |

## 3. Temporal integrity

Half-open valid and optional knowledge intervals; infinity is confined to interval boundaries. GiST exclusion with btree_gist enforces non-overlap across both axes. Partial unique indexes enforce one current row. Bitemporal history retains old knowledge; it cannot be replaced with ordinary SCD2 when the design requires correction semantics.

## 4. Physical storage

Start with native storage and unpartitioned small tables. Index and partition only from measured workload requirements; establish backup/restore and operational evidence separately.

## 5. Access boundary

Native roles, view grants and USER RLS are emitted. Identity is session_user; owners/superusers remain privileged. Shared scopes require a separate membership policy.

## 6. Capabilities and gaps

Exact cosine retrieval joins vectors back to Domain. Encoder/model execution and predictive quality require explicit product implementations; approximate indexing is optional. Runtime identity, storage operations and performance are not certified by schema checks. See CONFORMANCE.md.

## 7. SQL Idioms and Driver Constraints

Use quoted identifiers and escaped literals through the documented filters. Use Psycopg %s parameters for data values and savepoints after query errors. Arrays do not enforce declared dimensions without checks. JSONB supports equality used by conformance. Historical surfaces are SQL functions with typed timestamp arguments; bitemporal surfaces take both valid_at and known_at. Render StrictUndefined templates with a loader rooted at this platform directory. Type/constraint expressions are builder-authored SQL, not user data.

Runtime versions tested are recorded in CONFORMANCE.md; a target version is not itself proof of a native execution matrix.

## 8. Layout

The platform's part of the [Platform Layout Standard](../../design/core/PLATFORM_LAYOUT.md). Modules are schemas within one database. Readers do not block writers under MVCC, so the governed one-to-one view adds no isolation here: it is an interface layer only, and is still emitted while the [Organisation Profile Standard](../../design/core/ORGANISATION_PROFILE.md) requires a `base_view` role. No profile pack exists for this platform, so no platform-specific physical checks are declared.

```
Layout: -
  Container term:     SCHEMA
  Qualification:      schema.object: two levels within one database
  Grant boundary:     SCHEMA
  Access layer:       optional
  Access rationale:   MVCC readers do not block writers, so a one-to-one view adds an interface layer and no isolation.
  Consumer container: may-share
  Catalogue source:   information_schema.tables, information_schema.columns, pg_catalog
  Dialect:            PostgreSQL SQL
  Physical checks:    none
```
