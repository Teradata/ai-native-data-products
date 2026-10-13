---
title: Teradata Observability Module Implementation
anchor: observability
type: implementation
status: draft
version: 3.0
normative: true
implements: observability
platform: teradata
---

# Teradata: Observability

Binding of [Observability](../../../../design/modules/observability.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`01-tables.sql.j2` calls `module_tables('observability')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). The relations are those the Observability standard defines and the resolver places: change events, quality metrics, lineage definitions and runs, model performance, agent outcomes, and the validation relations `ValidationRun` and `ValidationArea`. Event relations are append-only by profile; lineage definitions are current-state. Each gets a governed and a consumer view from the temporal pattern.

The module's views are rendered elsewhere: `LineageGraph` and `LineageRunLatest` by [Semantic discovery](../semantic/README.md), and `TrustMap` by [Validation](../../patterns/validation/README.md).

Capture is a producer obligation: deployers wire their ingestion, temporal writer and agent runtime to these stores. No trigger or synthetic quality score is emitted. The [access-layer template](../../patterns/access-layer/README.md) grants the agent tier `INSERT` on agent outcomes, the write target the context marks; validation evidence is written by [`validate.py`](../../../../tooling/bindings/README.md) using the placement the manifest carries. Privileged administration can bypass append-only intent. Retention is a settled design decision and an operator-managed process; no template deletes records.

## Capability bindings

| Capability | Binding |
|---|---|
| `ChangeEventCapture` | Append-only change-event table; the writer must emit events. |
| `AgentOutcomeCapture` | Append-only agent-outcome table; the agent tier may insert. |
| `LineageCapture` | Separate definition and run tables, with the lineage graph and latest-run views over active definitions. |
| `QualityScore` | Quality-metric time series, separate from validation evidence. |
| `GraphNativeLineageTraversal` | Not rendered: see below. A specification enabling `observability:graph-lineage` has it reported as a gap. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-OBS-001,002` | Standard-owned event structures hold table-level references and counts; producer payload review required. |
| `INV-OBS-003,006` | Separate definition and run tables; lineage views read active definitions only. |
| `INV-OBS-004` | Retention is a settled decision; operators prove enforcement. |
| `INV-OBS-005` | Wire 2.1 run and area records appended by the validator; engine tests of failures, errors, staleness, legacy runs and producer selection. |
| `INV-OBS-007..009` | Optional graph-native facet not rendered; no graph identity guarantee claimed. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## Graph-lineage facet: not migrated

The graph-lineage templates below were written for the old flat template context, before the build context, and no phase renders them. Whether they are ported onto the build context or retired is an open decision; until it is made they are kept unchanged, as written, and a product that enables the facet has the exposure reported as a gap. What follows describes them as they were designed.

### The graph-lineage facet's templates

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

### Naming note: `created_dts` (graph-lineage facet)

Earlier versions of the external graph-explorer contract (< 2.0.0) recommended the singular `created_dt`, which collided with this repository's own `temporal-lifecycle-metadata` naming (TLM-04 prohibits it as an audit-column name). That collision was resolved upstream, in the contract itself: as of contract version 2.0.0 the recommended provenance column is `created_dts`, matching this repository's convention exactly, so `07-graph-acl-views.sql.j2` carries the name through unchanged from the base table. If this facet is ever pointed at a pre-2.0.0 graph-explorer deployment, the ACL view's `created_dts` column will need renaming back to `created_dt` for that deployment only — do not make that change here by default.
