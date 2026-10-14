---
title: DuckDB Access Layer Implementation
anchor: access-layer
type: implementation
status: draft
version: 2.0
normative: true
implements: access-layer
platform: duckdb
---

# DuckDB: Access Layer

Binding of [Access Layer](../../../../design/patterns/access-layer.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

DuckDB has no roles, `GRANT`, `REVOKE` or row-level security. The binding declares `Principals: unsupported` in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations), so this pattern has **no template and no access phase**, and nothing simulates privilege statements.

The organisation profile declares each tier (`ROLE_READ`, `ROLE_AGENT`, `ROLE_ADMIN`) as `outside <how it is enforced>`, for example read-only file access for the read tier. The resolver records that text in the context's `principals` and rejects a profile that asks the build to `create` a principal or bind an `existing` one for this binding. The tiers are an external obligation: the binding does not claim that any tier is enforced.

Opening the database file read-only prevents writes. It does not hide base tables, point-in-time macros, runtime Memory or PII, nor does it constrain host file or network access. Schema separation and naming are not authorisation; direct file users see everything. See DuckDB's [security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview). A production service must authorise queries, derive runtime scope from authenticated identity, bound append rights and expose no arbitrary SQL channel; private runtime data belongs in separate protected storage.

No check covers access, and no evidence is published for it. This is declared in [conformance scope](../../CONFORMANCE.md), not reported as conformance.

## Capability bindings

| Capability | Binding |
|---|---|
| `AccessView` | Consumer views in the containers the profile places (see temporal-lifecycle-metadata). Not a security boundary. |
| `ProductRoleAccess` | Unsupported natively; enforced outside the engine as the profile declares. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
