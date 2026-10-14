---
title: Teradata Access Layer Pattern Implementation
anchor: access-layer
type: implementation
status: draft
version: 3.0
normative: true
implements: access-layer
platform: teradata
---

# Teradata: Access Layer

Binding of [Access Layer](../../../../design/patterns/access-layer.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`00-implied-grants.sql.j2` is the second phase, before any view. A view in one database compiles, and serves its readers, only once that database holds `SELECT WITH GRANT OPTION` on the database it reads; without it view creation fails with `[5315]`. The template derives each pair from what a view reads, from `entities`, `relations` and their placed `objects`: a base view reads its table; a consumer view reads its base view, or its table where there is none; a discovery view reads the Semantic and Observability tables it is built over. It grants nothing else, and never a database to itself.

`01-grants.sql.j2` is the last phase. It reads `principals` (the name of each of `ROLE_READ`, `ROLE_AGENT` and `ROLE_ADMIN`, and whether the build creates it), `product.name`, `grant_level`, `containers`, `module_containers` and the placed objects of `entities` and `relations`. In order it:

1. creates each principal the profile says to `create` as a role, with a comment naming who it is for, never what it reaches; an `existing` principal is used by name and not altered;
2. grants the admin tier `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, `DROP TABLE`, `CREATE VIEW`, `DROP VIEW` and `STATISTICS` on every database the product owns (never an adopted one) that holds objects (`ALL` carries `CREATE USER`, which Teradata grants to no role);
3. grants `SELECT` on consumer views to the read and agent tiers: per view at grant level `object`; at grant level `container`, on each database that holds consumer views and no tables, and per view where a database holds both, so a grant never reaches a table;
4. grants `SELECT` on the governed base view of every versioned relation with a consumer view to the read and agent tiers, one view at a time, so history is reachable as other bindings make it reachable through point-in-time functions (temporal-lifecycle-metadata §9); base views can share a database with tables, so these are never database grants;
5. for each table whose primary role is `WRITE_TARGET`: on a runtime Memory relation, `SELECT`, `INSERT` and `UPDATE` for the agent tier; on any other write target (agent outcomes), `INSERT`.

Runtime Memory is not restricted to the requesting identity's scope: Teradata has no row-level security in SQL, so the binding declares `Runtime scope: unsupported` and every build with runtime relations reports it.

The deploy script does not create users, assign passwords or grant roles to users; those are operator steps. Creating roles needs the `CREATE ROLE` right. Review the members of an `existing` role before binding a product to it.

## Capability bindings

| Capability | Binding |
|---|---|
| `AccessView` | Consumer views, and the governed views that carry history, are the read and agent tiers' only table-like surfaces; the engine tests read the read role's rights from `DBC.AllRoleRightsV`. |
| `ProductRoleAccess` | Roles named by the profile; grants per object or per database. Runtime scope enforcement is a reported gap. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
