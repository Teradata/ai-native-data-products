---
title: PostgreSQL Object Placement Implementation
anchor: object-placement
type: implementation
status: draft
version: 2.0
normative: true
implements: object-placement
platform: postgres
---

# PostgreSQL: Object Placement

Binding of [Object Placement](../../../../design/patterns/object-placement.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Template

`01-containers.sql.j2` is the first phase. It creates the `btree_gist` extension if absent, which the history tables' exclusion constraints need, then one schema for each entry in the context's `containers` that holds objects and is not adopted. Adopted containers already exist; parent containers hold no objects on this platform. Schema creation does not use `IF NOT EXISTS`, so accidental reuse fails rather than blending two products.

Every container name, and the container of every object, comes from the organisation profile through the resolver. No name is inferred from a product prefix, and the example profile is one possible placement, not a required convention.

The phase order in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations) creates containers, then Memory, Semantic, Domain, Observability, Search and Prediction tables, then comments, views and functions, registration, discovery, the trust map, documentation capture and, last, access. `deploy.sql` applies them in one transaction; deploying phase files separately must keep that order.

PostgreSQL roles are cluster-wide and are provisioned deliberately by the access-layer phase or by an operator.

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
