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

Binding of [Object Placement](../../../../design/patterns/object-placement.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

Use one dedicated database per product and environment, with exactly six schemas: `memory`, `semantic`, `domain`, `observability`, `search`, `prediction`. This is the declared placement standard for Customer360. Environment differentiation belongs to the database/connection, not logical entity names. Schemas co-locate modules for transactional deployment and join-back.

Deploy Memory and Semantic first, Domain and Observability next, Search and Prediction last. Cross-module discovery, registration and grants follow their dependencies in the same transaction; no partly granted product is exposed. Role names are cluster-wide and therefore must be unique across products/environments; the fixed example role names require a fresh cluster namespace.

Consumers resolve deployed names from the registries. `PLACE`, `SEM` and orientation checks cover placement. The builder creates schemas without `IF NOT EXISTS`, so it fails and rolls back on an occupied target. It never drops or replaces a product.
