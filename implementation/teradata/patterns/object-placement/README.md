---
title: Teradata Object Placement Pattern Implementation
anchor: object-placement
type: implementation
status: draft
version: 3.0
normative: true
implements: object-placement
platform: teradata
---

# Teradata: Object Placement

Binding of [Object Placement](../../../../design/patterns/object-placement.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Template

`01-containers.sql.j2` is the first phase. It creates one database for each entry in the context's `containers` that is not adopted: parents first, then each child `FROM` its parent. Adopted containers already exist and are never created. A database that holds objects gets the `Container space` binding setting as permanent space (the organisation profile's `Settings:`, or the binding's declared default of 1 GB, recorded in `defaults_applied`); a parent that holds no objects gets enough to allocate its children. `CREATE DATABASE` fails on an existing name, so accidental reuse fails rather than blending two products.

Every database name, and the database of every object, comes from the organisation profile through the resolver: the profile is the organisation's object-placement implementation ([Organisation Profile Standard](../../../../design/core/ORGANISATION_PROFILE.md) §1). No name is inferred from a product prefix, and the example profiles are two possible placements, not a required convention.

A view in one database that reads another compiles only once its database holds `SELECT WITH GRANT OPTION` on the database it reads. Those implied grants are the second phase, computed from the placement ([access-layer](../access-layer/README.md)); the profile never declares them.

The phase order in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations) creates databases, the implied grants, then Memory, Semantic, Domain, Observability, Search and Prediction tables, then comments, views, registration, discovery, the trust map, documentation capture, statistics and, last, roles and grants. Teradata commits each DDL statement on its own, so deploying phase files separately must keep that order, and a failed deployment is cleared by dropping its databases.

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
