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

## Template

`01-grants.sql.j2` is the last phase. It reads `principals` (the name of each of `ROLE_READ`, `ROLE_AGENT` and `ROLE_ADMIN`, and whether the build creates it), `grant_level`, `containers`, `module_containers`, the placed objects of `entities` and `relations`, and `embeddings`. In order it:

1. creates each principal the profile says to `create`, as a `NOLOGIN` role; an `existing` principal is used by name and not altered;
2. for every container the product owns (never an adopted one), revokes schema access and function execution from `PUBLIC` (including default privileges for new functions), grants `USAGE` to all three tiers, and grants the admin tier all privileges on tables, sequences and functions;
3. grants `SELECT` on consumer views to the read and agent tiers: per view at grant level `object`, or on every table and view in each container that holds consumer views at grant level `container`;
4. grants `EXECUTE` on every point-in-time function and similarity function to the read and agent tiers;
5. for each table whose primary role is `WRITE_TARGET`: on a runtime Memory relation, enables row-level security with a policy limiting the agent tier to rows with `scope_level = 'USER'` and `scope_identifier = session_user`, an unrestricted policy for the admin tier, and `SELECT`, `INSERT` and `UPDATE` for the agent tier; on any other write target (agent outcomes), `INSERT` for the agent tier.

Point-in-time functions are `SECURITY DEFINER` with a fixed `search_path`, so the read and agent tiers reach history through them without a grant on the base table. Similarity functions run with invoker rights over consumer views. At grant level `container`, every table in a consumer-view container becomes readable, so such a container should hold consumer views only.

The deploy script does not create login users, assign passwords or grant role membership; those are operator steps. Object owners and superusers remain trusted administrators. Review the memberships of an `existing` role before binding a product to it.

## Capability bindings

| Capability | Binding |
|---|---|
| `AccessView` | Consumer views are the read and agent tiers' only table-like surface. |
| `ProductRoleAccess` | Native roles named by the profile; grants per object or per container; `USER` row-level security on runtime Memory. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
