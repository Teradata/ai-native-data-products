---
title: Teradata Observability Module Implementation
anchor: observability
type: implementation
status: standard
version: 2.0
normative: true
implements: observability
platform: teradata
---

# Teradata: Observability Module Implementation

Teradata binding of [`design/modules/observability.md`](../../../../design/modules/observability.md). Operational evidence: events, metrics, lineage, and the home of validation results. Read the design document first. Replace `{{ product }}`; tables live in `{{ product }}_Observability`, the lineage discovery views deploy into `{{ product }}_Semantic`.

## Files

| File | Purpose |
|------|---------|
| `01-event-tables.sql.j2` | `change_event`, `data_quality_metric`, `model_performance`, `agent_outcome`. |
| `02-lineage-tables.sql.j2` | `data_lineage` (definitional) and `lineage_run` (operational). `data_lineage` carries optional `source_column`/`target_column` for column-level flows, consumed by the `graph-lineage`/`column-lineage` facets (below) if enabled. |
| `03-lineage-views.sql.j2` | `lineage_graph` and `lineage_run_latest`: deployed into the Semantic container. |
| `04-openlineage.md` | OpenLineage entity/column mapping and RunEvent construction. |

**Validation results.** The `validation_run` and `validation_area` tables and their `validation_latest` / `validation_trust_map` views are defined by the [validation pattern implementation](../../patterns/validation/) and deployed into this module's `{{ product }}_Observability` container. This module does not redefine them.

### Graph-lineage facet (optional)

This binding's graph consumer contract (design §5.1) is the external **Teradata Graph Explorer** data contract, `docs/graph-data-contract.md` in the `teradata-graph-explorer` repository. It is normative for the consumer surface, fixes the `Graphs_<KEY>_*` object names and the catalogue table definitions, and supplies the quality procedures; this repository does not redefine it. Binding to it lets a product opt in to opening its lineage in Graph Explorer, tracing it, and visualising it as a graph, in addition to the `lineage_graph` discovery view above. Read [`design/modules/observability.md`](../../../../design/modules/observability.md) §4.1/§5.1 first. Replace `{{ graph_key }}` (this graph's unique catalogue key, e.g. `LIN_DEMO` — see `DEC-GRAPH-SCOPE`: one graph per data product, never shared). This facet's package must declare the shared `graph-platform` package as an external parent; it creates neither.

| File | Purpose |
|------|---------|
| `05-graph-tables.sql.j2` | `Graphs_{{ graph_key }}_STD_0_T.graph_nodes` / `.graph_edges` — this facet's own data plane. |
| `06-graph-locking-views.sql.j2` | `Graphs_{{ graph_key }}_STD_0_V.*` — governed 1:1 locking views over the base tables. |
| `07-graph-acl-views.sql.j2` | `Graphs_{{ graph_key }}_ACL_0_V.graph_nodes` / `.graph_edges` / `.graph_edges_bi` — **the contract surface**; the only views a consumer binds to. |
| `08-catalogue-seed.sql.j2` | Idempotent seed of the shared `Graphs_CAT_STD_0_T` registry, relationship/role vocabularies, and trace profiles. Takes `column_lineage_enabled` to gate the `column-lineage` facet's catalogue rows, and writes the registered `graph_key` back onto this product's `data_product_map.graph_key` ([Teradata/ai-native-data-products#65](https://github.com/Teradata/ai-native-data-products/issues/65)) so a consumer can resolve it from the product prefix alone. |
| `09-load-lineage.sql.j2` | Set-based, idempotent load from `data_lineage` / `.agent_outcome` (above) into `05-graph-tables.sql.j2`'s node/edge tables. Also takes `column_lineage_enabled`. |
| `10-access.dcl.sql.j2` | Implied grants, this graph's `R_Graphs_{{ graph_key }}_READ` role, and registration into the shared `R_Graphs_USR_APP` consumer role. |

**Column-lineage facet (optional, requires `graph-lineage`).** `data_lineage.source_column`/`.target_column` (`02-lineage-tables.sql.j2`) are optional and NULL for table-level flows. Enable by passing `column_lineage_enabled=true` to `08-catalogue-seed.sql.j2` and `09-load-lineage.sql.j2` only if `DEC-GRAPH-COLUMN-LINEAGE` is settled toward column-grain tracing for this product; the flag gates the `COLUMN` role and `derives_column` relationship/trace-leg registration in the catalogue seed and the `COLUMN` node / `derives_column` edge population in the load path together, so `ColumnGrainLineageTraversal` is only ever advertised when it is actually populated.

## Capability bindings

| Capability (design) | Teradata binding |
|---------------------|------------------|
| Outcome & quality evidence | `agent_outcome`, `data_quality_metric`: read by Memory's closed-loop learning. |
| Validation results home | Hosts the validation pattern's `validation_run` and `validation_area` (the trust map). |
| Lineage | `data_lineage` + `lineage_run`, exposed via `lineage_graph` / `lineage_run_latest` in Semantic. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN`. |
| `access-layer` write-back | `ROLE_AGENT` holds `INSERT` here (Phase 2.5). |
| `GraphNativeLineageTraversal` | `graph-lineage` facet only: `Graphs_{{ graph_key }}_ACL_0_V.*`, registered in `Graphs_CAT_STD_0_T.graph_registry`. |
| `ColumnGrainLineageTraversal` | `column-lineage` facet only: `COLUMN` role and `derives_column` relationship in `Graphs_CAT_STD_0_T.graph_role`/`.graph_relationship`, populated by `09-load-lineage.sql.j2` when `column_lineage_enabled`. |

## Invariants → checks

| Invariant | How enforced |
|-----------|--------------|
| `INV-OBS-002` (table-level, aggregate) | Schema: `records_affected` count, `table_name` only: no instance-key columns. |
| `INV-OBS-003` (lineage split) | Two tables: `data_lineage` (one row per flow) + `lineage_run` (one row per execution, FK to definition). |
| `INV-OBS-005` (validation home) | `validation_run` and `validation_area` deployed here (validation pattern), profile `EVENT_APPEND_ONLY`. |
| `INV-OBS-006` (stable graph) | `lineage_graph` reads `data_lineage WHERE is_active = 1` only; `09-load-lineage.sql.j2` filters `dl.is_active = 1` the same way. |
| `INV-OBS-007` (read-only, identifiers only) | `09-load-lineage.sql.j2` only ever `SELECT`s from this module's own tables; every `INSERT` targets `Graphs_{{ graph_key }}_STD_0_T`; `graph_nodes`/`graph_edges` carry natural keys and labels only, no Domain columns. |
| `INV-OBS-008` (one graph per product) | One `graph_key` per product in `08-catalogue-seed.sql.j2`; `community` is left NULL for the shared analysis engine, never set from a product identifier. |
| `INV-OBS-009` (stable node identity) | `graph_nodes.node_id` is `GENERATED ALWAYS AS IDENTITY`; the load path only ever `INSERT`s a new natural key, never updates or renumbers an existing one. |

## Naming note: `created_dts` (graph-lineage facet)

Earlier versions of the external graph-explorer contract (< 2.0.0) recommended the singular `created_dt`, which collided with this repository's own `temporal-lifecycle-metadata` naming (TLM-04 prohibits it as an audit-column name). That collision was resolved upstream, in the contract itself: as of contract version 2.0.0 the recommended provenance column is `created_dts`, matching this repository's convention exactly, so `07-graph-acl-views.sql.j2` carries the name through unchanged from the base table. If this facet is ever pointed at a pre-2.0.0 graph-explorer deployment, the ACL view's `created_dts` column will need renaming back to `created_dt` for that deployment only — do not make that change here by default.
