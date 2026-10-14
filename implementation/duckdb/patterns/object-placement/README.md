---
title: DuckDB Object Placement Implementation
anchor: object-placement
type: implementation
status: standard
version: 2.0
normative: true
implements: object-placement
platform: duckdb
---

# DuckDB object placement

Binding of [object-placement](../../../../design/patterns/object-placement.md).

## 1. Platform Declaration

DuckDB 1.4.3; containers are catalogues and schemas. Principals are OS users and authenticated host identities, not DuckDB roles. The namespace is catalogue.schema.object. This binding limits names to 63 ASCII characters matching `[a-z][a-z0-9_]*`, avoids SQL reserved words and module names for the file stem, and quotes identifiers in generated consumer SQL. The 63-character bound is a product convention, not an engine limit.

## 2. Container Model

One product file/catalogue contains six sibling schemas: domain, semantic, search, prediction, observability and memory. Only these child schemas hold governed objects. The default `main` schema remains empty. Development and production have different parent directories, not different logical objects. Optional private runtime in another protected file is a documented security exception to self-containment; the synthetic example needs no exception.

## 3. Naming Pattern

File path: `{{environment_root}}/{{product_name}}.duckdb`; object identity: `{{module}}.{{object_name}}`. All segments are mandatory: environment_root is an operator-selected absolute directory, product_name follows the identifier convention, module is one of the six anchors, object_name is the authored model identity. Example: `/products/dev/customer360.duckdb`, `domain.customer`. Promotion changes the directory/catalogue attachment only; `_dev` and `_uat` object suffixes are prohibited.

## 4. Object Placement Rules

| Type | Container / naming |
|---|---|
| Persistent table | Owning module, authored logical name |
| View | Owning module, `v_` + logical name for canonical projections |
| Stored procedure | Unsupported; host transaction functions replace maintenance procedures |
| Scalar function / UDF | Owning module; `fn_` for host UDFs; host registration is not portable persistence |
| Table/scalar macro | Owning module; `at_` for temporal tables; named operations `embed`, `nearest`, `training_at` are explicitly registered/documented functions |
| Index | Owning table's schema, `ix_` + logical name; none required by baseline |
| Temporary object | Connection-local scratch only, never a persisted product dependency |

**Rule B: name-discriminated**: table `customer` maps to view `v_customer`, table `product` maps to view `v_product`; strip exactly one `v_` to recover the logical name. Logical names cannot start with reserved type prefixes. Purpose-specific logical names such as `searchable`, `enriched`, `trust_map`, `column_catalogue` and discovery paths are explicitly named views without corresponding tables; they are reserved in the model. No tier architecture applies: a view may join module tables or canonical views, with dependencies recorded by its definition and composition metadata. Objects are classified at deployment, never inferred from names by consumers.

## 5. Separation Policy

`CO_LOCATED`. Each module owns tables and public interfaces in one schema. This preserves a small portable namespace. Co-location offers no security boundary: external authorization must enforce public surfaces, and private runtime has no public SQL view.

## 6. Derivation Function

`derive_container(object_type, environment_inputs, classification)`:

1. Require `environment_inputs = {environment_root, product_name, module}` with the naming rules above.
2. Reject unsupported procedures and modules outside the six anchors.
3. For persistent tables, views, macros and indexes return `product_name.module`; for temporary objects return connection-local temporary scope.
4. Classification does not change a schema; a private-runtime classification requires an authenticated host or an explicitly configured protected runtime file. Never infer that another schema enforces privacy.

Examples: (table, dev/customer360/domain, PUBLIC) → customer360.domain; (view, test/customer360/search, PUBLIC) → customer360.search; (macro, prod/customer360/prediction, PUBLIC) → customer360.prediction. Parent file is always environment_root/product_name.duckdb.

## 7. Access Model

No database grants or implied cross-container grants are needed to compile views. The deploying process owns the file. Logical consumer tiers and their external enforcement are defined only in [access-layer](../access-layer/). OS/container permissions protect files, not schemas. Do not grant arbitrary SQL/file access to consumers who require view-only or scoped access.

## 8. Validation Procedure

Run `python implementation/duckdb/validate.py <file>` and inspect `C360-PLACE-001`, the schema/table inventory and access-object resolution checks. Zero violations is SQL placement success; any failure halts the builder before publication. The trust map separately reports external access as unknown; SQL cannot verify host authorization or OS ACLs. Operators must supply that evidence before claiming security conformance. Never silently move objects to repair a failure.
