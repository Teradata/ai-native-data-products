---
title: Teradata Data Product Lineage Module Implementation
anchor: data-product-lineage
type: implementation
status: standard
version: 1.0
normative: true
implements: data-product-lineage
platform: teradata
---

# Teradata: Data Product Lineage Module Implementation

Teradata binding of [`design/modules/data-product-lineage.md`](../../../../design/modules/data-product-lineage.md). Binds this product's Observability lineage and access data to the external **Teradata Graph Explorer** data contract, so the product's lineage can be opened, traced, and rendered as a graph. Read the design document first. Replace `{{ product }}` (the source data product, e.g. `Demo`) and `{{ graph_key }}` (this graph's unique catalogue key, e.g. `LIN_DEMO` — see `DEC-GRAPH-SCOPE`: one graph per data product, never shared).

This module's package must declare the shared `graph-platform` package and this product's `{{ product }}_Observability` container as external parents; it creates neither.

## Files

| File | Purpose |
|------|---------|
| `01-graph-tables.sql.j2` | `Graphs_{{ graph_key }}_STD_0_T.graph_nodes` / `.graph_edges` — this package's own data plane. |
| `02-graph-locking-views.sql.j2` | `Graphs_{{ graph_key }}_STD_0_V.*` — governed 1:1 locking views over the base tables. |
| `03-graph-acl-views.sql.j2` | `Graphs_{{ graph_key }}_ACL_0_V.graph_nodes` / `.graph_edges` / `.graph_edges_bi` — **the contract surface**; the only views a consumer binds to. |
| `04-catalogue-seed.sql.j2` | Idempotent seed of the shared `Graphs_CAT_STD_0_T` registry, relationship/role vocabularies, and trace profiles. |
| `05-load-lineage.sql.j2` | Set-based, idempotent load from `{{ product }}_Observability.data_lineage` / `.agent_outcome` into this package's node/edge tables. |
| `06-access.dcl.sql.j2` | Implied grants, this graph's `R_Graphs_{{ graph_key }}_READ` role, and registration into the shared `R_Graphs_USR_APP` consumer role. |

**Column-level lineage.** `data_lineage.source_column`/`.target_column` (added to [`modules/observability/02-lineage-tables.sql.j2`](../observability/02-lineage-tables.sql.j2)) are optional and NULL for table-level flows. Populate them only if `DEC-GRAPH-COLUMN-LINEAGE` is settled toward column-grain tracing for this product; the load path emits `COLUMN` nodes and `derives_column` edges only where both are non-null.

## Capability bindings

| Capability (design) | Teradata binding |
|---|---|
| `GraphNativeLineageTraversal` | `Graphs_{{ graph_key }}_ACL_0_V.*`, registered in `Graphs_CAT_STD_0_T.graph_registry`. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN` on every object in `01-graph-tables.sql.j2`. |

## Invariants → checks

| Invariant | How enforced |
|---|---|
| `INV-DPL-001` (read-only consumer of Observability) | `05-load-lineage.sql.j2` only ever `SELECT`s from `{{ product }}_Observability`; every `INSERT` targets this package's own `Graphs_{{ graph_key }}_STD_0_T`. |
| `INV-DPL-002` (identifiers only, never business data) | `graph_nodes`/`graph_edges` carry natural keys and labels only — no columns from Domain. |
| `INV-DPL-003` (one graph per product; `community` never encodes ownership) | One `graph_key` per product in `04-catalogue-seed.sql.j2`; `community` is left NULL for the shared analysis engine, never set from a product identifier. |
| `INV-DPL-004` (active definitions only) | Every read of `data_lineage` in `05-load-lineage.sql.j2` filters `is_active = 1`. |
| `INV-DPL-005` (stable node identity) | `graph_nodes.node_id` is `GENERATED ALWAYS AS IDENTITY`; the load path only ever `INSERT`s a new natural key, never updates or renumbers an existing one. |

## Naming note: `created_dts`

Earlier versions of the external graph-explorer contract (< 2.0.0) recommended the singular `created_dt`, which collided with this repository's own `temporal-lifecycle-metadata` naming (TLM-04 prohibits it as an audit-column name). That collision was resolved upstream, in the contract itself: as of contract version 2.0.0 the recommended provenance column is `created_dts`, matching this repository's convention exactly, so `03-graph-acl-views.sql.j2` carries the name through unchanged from the base table. If this module is ever pointed at a pre-2.0.0 graph-explorer deployment, the ACL view's `created_dts` column will need renaming back to `created_dt` for that deployment only — do not make that change here by default.
