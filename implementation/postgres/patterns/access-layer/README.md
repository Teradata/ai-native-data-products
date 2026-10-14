---
title: PostgreSQL Access Layer Implementation
anchor: access-layer
type: implementation
status: draft
version: 2.0
normative: true
implements: access-layer
platform: postgres
---

# PostgreSQL: Access Layer

Binding of [Access Layer](../../../../design/patterns/access-layer.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`01-grants.sql.j2` binds the design's access tiers. PostgreSQL consumes explicit READ, AGENT and ADMIN role names, revokes PUBLIC access to product schemas/tables/functions and grants only declared consumer views. Historical functions are ADMIN-only; registered search functions query consumer views with invoker rights. Runtime USER policies bind to session_user; outcome writes are append-only for AGENT. Object owners and privileged roles remain trusted administrators.

Where role creation is unavailable to the deployer, render this template for the operator and keep that outstanding step visible. The bundled deploy script assumes all required privileges; it does not create LOGIN users, assign passwords or modify existing roles. Do not reuse a cluster role without reviewing its memberships.

DuckDB emits an explicit enforcement-boundary note rather than simulated GRANT or RLS statements. Authenticated application controls and separate runtime storage are choices the deployment must settle. Read-only connections are not row security.

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
