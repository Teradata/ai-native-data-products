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

DuckDB has no roles, GRANT, REVOKE or row-level security. `01-grants.sql.j2` therefore emits no simulated privilege statements. It renders a comment-only record of the enforcement boundary and lists the consumer surfaces (access views, search macros, the discovery entry point) and the runtime stores that an authenticated serving application must expose or withhold. The design's READ, AGENT and ADMIN tiers are an external obligation: the binding does not claim that any tier is enforced.

Opening the database file read-only prevents writes. It does not hide base tables, historical macros, runtime memory or PII, nor does it constrain host file or network access. Schema separation and naming are not authorisation. Direct file or JDBC users see everything; DuckDB documents its [security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview). A production service must authorise queries, derive runtime scope from authenticated identity, bound append rights and expose no arbitrary SQL channel; real private runtime data belongs in separate protected storage.

The access-layer trust area stays unknown until a deployment owner supplies evidence of external enforcement. This is declared in [conformance scope](../../CONFORMANCE.md), not reported as conformance.

## Capability bindings

| Capability | Binding |
|---|---|
| `AccessView` | Explicit consumer projections in the access container (see temporal-lifecycle-metadata). Not a security boundary. |
| `ProductRoleAccess` | Unsupported natively; external application enforcement. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
