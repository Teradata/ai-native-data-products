---
title: PostgreSQL Semantic Implementation
anchor: semantic
type: implementation
status: draft
version: 2.0
normative: true
implements: semantic
platform: postgres
---

# PostgreSQL: Semantic

Binding of [Semantic](../../../../design/modules/semantic.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[schema.sql](schema.sql) stores product, module, entity, field, relationship, model, feature, metric, synonym and approved-access contracts. [discovery.sql](discovery.sql) joins `pg_catalog` structural facts to authored meaning; provenance stays explicit. `SemanticRegistration` comes from the deployment model, never inferred from consumer object names.

Bootstrap at `semantic.data_product_manifest` (or `semantic.v_data_product_registry`), then resolve ordered orientation resources. The manifest uses `jsonb_agg`; consumers read the trust map before business surfaces. Recursive CTEs preserve ordered join predicates, prevent cycles and cap traversal at four hops. Access paths resolve registered consumer views; base-table paths are descriptive metadata, not grants.

`SEM`, `REL`, `META` and `DOC` checks cover inventory, resources, comments, joins, metrics and minimum documentation. Object registries describe datasets, never individual business instances. The model is fixed for the example; deployments must regenerate and review registrations when changing it.
