---
title: DuckDB Semantic Module Implementation
anchor: semantic
type: implementation
status: standard
version: 2.0
normative: true
implements: semantic
platform: duckdb
---

# DuckDB Semantic

Binding of [Semantic](../../../../design/modules/semantic.md). [schema.sql](schema.sql) defines the authored registry; [discovery.sql](discovery.sql) defines live catalogue, orientation, lineage and path projections.

**Provides:**

| Capability | Binding |
|---|---|
| `SemanticRegistration` | Explicit model-derived inserts at deployment. |

Bootstrap is `semantic.data_product_registry` followed by `semantic.data_product_orientation`. The manifest is generated as a view over those sources; trust comes before analytical resources. The [agent demo](../../../../examples/customer360-duckdb/agent_demo.py) takes only the product name and these bootstrap conventions, then uses stored identities verbatim.

Every table, column, module and canonical public projection is registered. Access roles come from the compiler's verifiable structure: explicit single-table projections are PASSTHROUGH, joined Search/Prediction surfaces are COMPOSITE with one ANCHOR. Private runtime has BASE records only and is not agent-consumable. No runtime DDL parsing, suffix inference or fake grants are used. The live column catalogue joins schema/object/column facts to curated descriptions and marks each value's provenance. Comments cannot describe schemas, so module meaning is stored here.

Relationships include generated history-to-keymap edges for every reference target, intra-Domain joins, cross-module references and infrastructure links. Unconnected registries have explicit standalone rationale. Bidirectional recursive paths stop at four hops, exclude cycles, retain the complete join chain, and have a separate access-resolved projection which omits private endpoints. Metric expressions, dataset roles and resolver synonyms are separate from glossary definitions. Feature and model computation definitions live here, never in feature rows.

`C360-SEM-*`, `REL-*`, `META-*` and discovery tests verify inventory, metadata, orientation, paths, roles, metric datasets, synonyms and physical resolution. Documentation records DD-DISCOVERY-001, trust authority and the ERD cookbook recipe.
