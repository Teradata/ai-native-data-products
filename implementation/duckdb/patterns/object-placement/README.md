---
title: DuckDB Object Placement Implementation
anchor: object-placement
type: implementation
status: draft
version: 2.0
normative: true
implements: object-placement
platform: duckdb
---

# DuckDB: Object Placement

Binding of [Object Placement](../../../../design/patterns/object-placement.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Template

`01-containers.sql.j2` is the first phase. It creates one schema, inside the database the deployer has opened, for each entry in the context's `containers` that holds objects and is not adopted. Adopted containers already exist; parent containers hold no objects on this platform. Schema creation does not use `IF NOT EXISTS`, so accidental reuse fails rather than blending two products.

Every container name, and the schema of every object and sequence, comes from the organisation profile through the resolver. No name is inferred from a product prefix, and the example profile is one possible placement, not a required convention. The database file and its location are a deployment choice outside the templates.

The phase order in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations) creates schemas, then Memory, Semantic, Domain, Observability, Search and Prediction sequences and tables, then comments, views and macros, registration, discovery, the trust map and documentation capture. There is no access phase. `deploy.sql` applies them in one transaction; deploying phase files separately must keep that order.

DuckDB schemas are logical groupings, not security containers. Discovery and validation queries filter by schema name, not by `current_database()`, so attach no other database with same-named schemas to a session that runs them. Do not name the database file after a module; in particular the catalogue `memory` collides with DuckDB's default in-memory catalogue.

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
