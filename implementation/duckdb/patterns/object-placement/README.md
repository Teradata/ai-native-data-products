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

`01-schemas.sql.j2` creates only explicitly supplied containers, which are DuckDB schemas inside the database the deployer has opened. The input declares a container for every selected module and a consumer access container. Environment placement is supplied by the organisation; names are never inferred from a product prefix. The database file itself and its location are a deployment choice outside the templates. Discovery queries filter on `current_database()`, so a same-named schema in another attached database is not mistaken for the product.

Schema creation does not use IF NOT EXISTS, so accidental reuse fails rather than blending products. The helper orders Memory and Semantic before Domain and Observability, then Search and Prediction. Cross-module views and registration follow dependencies; the access phase is last within the transactional deployment. Deploying phases separately must preserve the design's staged access sequence.

The example overlay is one possible placement, not a required naming convention. DuckDB schemas are logical groupings, not security containers. Do not name the database file after a module; in particular the catalogue `memory` collides with DuckDB's default in-memory catalogue. No generated path or placement is a universal organisational standard.

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
