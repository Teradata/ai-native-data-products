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

Target PostgreSQL 16+. The dialect binds platform-neutral contracts; no product model is selected by this profile.

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

Use quoted identifiers and escaped literals through the dialect's `ident` and `literal`. Use Psycopg %s parameters for data values and savepoints after query errors. Arrays do not enforce declared dimensions without checks. JSONB supports equality used by conformance. Historical surfaces are SQL functions with typed timestamp arguments; bitemporal surfaces take both valid_at and known_at. Type/constraint expressions are builder-authored SQL, not user data.

Runtime versions tested are recorded in CONFORMANCE.md; a target version is not itself proof of a native execution matrix.

---

## Binding declarations

The declarations the resolver and renderer read are in [`binding.toml`](binding.toml) ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §5.1): quoting, the object roles this binding emits beyond tables and views, its settings, its phases and checks, its declared gaps, its physical type for each logical type, and its SQL for each expression function. A function with no entry is not rendered by this binding; an expression that uses one is carried unrendered and reported as a gap.

