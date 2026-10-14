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

`01-schemas.sql.j2` creates only explicitly supplied containers. The input declares a container for every selected module and a consumer access container. Environment placement is supplied by the organisation; names are never inferred from a product prefix.

Schema creation does not use IF NOT EXISTS, so accidental reuse fails rather than blending products. The helper orders Memory and Semantic before Domain and Observability, then Search and Prediction. Cross-module views and registration follow dependencies; grants are last within the transactional deployment. Deploying phases separately must preserve the design's staged access sequence.

The example overlays are one possible placement, not required naming conventions. PostgreSQL roles are cluster-wide and must be deliberately provisioned. DuckDB schemas are logical grouping, not security containers. No generated path or placement is a universal organisational standard.

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
