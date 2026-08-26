---
title: Data Product Lineage Module
anchor: data-product-lineage
type: module
status: standard
version: 1.0
normative: true
---

# Data Product Lineage Module: Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Data Product Lineage module: binds an AI-native data product's definitional and access lineage to the Teradata Graph Explorer graph product contract, for graph-native traversal and visualisation |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md), [Observability](observability.md) |
| **Binds to** | Teradata Graph Explorer data contract (external, normative for consumer adapters — see `graph-data-contract.md` in the `teradata-graph-explorer` repository) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/modules/data-product-lineage/`](../../implementation/teradata/modules/data-product-lineage/) |

Data Product Lineage is the exposure layer that turns Observability's lineage and access records into a **Registered Graph Product**: a graph-explorer-conformant node/edge adapter an agent or analyst can traverse, trace upstream/downstream, and visualise, rather than only query as tabular edge lists.

---

## 1. Purpose

Observability already records *what flows where* (`DataLineage`) and *who touched what* (`AgentOutcome`). This module answers a different question from a different interface: **can this product's lineage be opened in Teradata Graph Explorer, searched, traced, and rendered as a graph** — using the same canonical node/edge/catalogue contract every other governed graph in the estate uses, so an agent doesn't need a bespoke traversal API per product.

It does not replace Observability's existing Semantic-facing `lineage_graph` view (`INV-OBS-006`), which stays the lightweight discovery edge-list for agents already inside Semantic. This module is a heavier, separately-packaged adapter for graph-native tooling, built from the same source-of-truth tables.

---

## 2. Scope and Boundaries

**In scope:** mapping `DataLineage`, column-level lineage, and `AgentOutcome` access facts into a graph-explorer `graph_nodes`/`graph_edges` adapter; the catalogue rows, vocabularies, and trace profiles that register it; the load path from Observability into the graph tables.

**Out of scope:** the graph-explorer platform itself (`graph-platform`, the shared engine, quality procedures, and rendering layer are external, normative dependencies — this module conforms to them, it does not define them); business domain content (nodes and edges carry table/column/job/agent identifiers, never row data, per `INV-OBS-001`); cross-product federated lineage (see `DEC-GRAPH-SCOPE`, §5).

---

## 3. Relationship to Observability

This module is a downstream consumer of Observability, not a new system of record:

| Observability entity | Feeds |
|---|---|
| `DataLineage` (definitional, `is_active`-filtered) | `table` and `job` nodes; `produces` edges |
| `DataLineage.source_column`/`target_column` (extension, §4.2) | `column` nodes; `derives_column` edges |
| `AgentOutcome.tables_accessed` (exploded) | `accessed_by` edges from `table` to `agent` |
| `AgentOutcome.agent_key`/`session_key` | `agent`/`query_session` nodes; `queried_in` edges |

Nothing is written back into Observability. The load path (§6) reads Observability's tables and writes exclusively into this module's own `Graphs_<KEY>_STD_0_T` tables — the same zero-duplication-of-authority posture Semantic uses for its discovery map, applied here to a graph-shaped exposure instead of a relational one.

---

## 4. Entity Model

### 4.1 Node categories

| `category` | `node_role` values | Natural key | Source |
|---|---|---|---|
| `table` | `source_table`, `target_table` | `container_name.object_name` | `DataLineage.source_table`/`target_table` |
| `column` | `source_column`, `target_column` | `container_name.object_name.column_name` | `DataLineage.source_column`/`target_column` |
| `job` | `etl_job` | `job_name` | `DataLineage.job_name` (first-class node, as Observability's existing `lineage_graph` already treats it) |
| `agent` | `consumer` | `agent_key` | `AgentOutcome.agent_key` |
| `query_session` | `session` | `session_key` | `AgentOutcome.session_key` (omit this category entirely if a product does not need session-grain traversal) |

`node` is the dense surrogate identity assigned at load time (§6); the natural key above is carried as a separate, non-canonical attribute per the graph-explorer contract's rule that a natural key must not replace `node`.

### 4.2 Column-level lineage extension

`DataLineage` (`design/modules/observability.md` §4) is table-level only today. Rather than a new entity, this module extends it with two nullable columns:

```
Entity: DataLineage               [kind: Record]  // extended, not replaced
  ...existing attributes unchanged...
  source_column: ShortText [optional]  // NULL for table-level flows
  target_column: ShortText [optional]  // NULL for table-level flows
```

`NULL` in both means a table-level flow (unchanged behaviour); populated means a column-level flow. This is additive: existing rows and existing consumers of `DataLineage` (including `lineage_graph`) are unaffected. A `column` node and `derives_column` edge are emitted by the load path only where both columns are non-null.

### 4.3 Edge types

Registered in the graph catalogue's `graph_relationship` vocabulary, all `ASYMMETRIC`:

| `edge_type` | Direction (`node_i` → `node_j`) | Source |
|---|---|---|
| `produces` | upstream (source table or job) → downstream (job or target table) | `DataLineage`, one edge per source→job leg and job→target leg |
| `derives_column` | source column → target column | `DataLineage` column extension |
| `accessed_by` | table → agent | `AgentOutcome.tables_accessed` (exploded to one row per accessed table) |
| `queried_in` | agent → query_session | `AgentOutcome.session_key` |

`is_weighted=0`; every edge emits `weight=1.0` per the contract's guidance for unweighted graphs. `has_relationship=1` since `edge_type` is always populated and vocabulary-backed.

---

## 5. Graph Scope Principle

**One data product, one graph** (`DEC-GRAPH-SCOPE`, decided, not left open per product):

- Each data product registers its own `graph_key` (for example `lineage_<product>`), its own `Graphs_<KEY>_STD_0_T`/`ACL_0_V` objects, and its own catalogue row. Graphs are independently deployable, independently versioned, and independently retirable, matching the graph-explorer contract's placement rule that one Graph Product owns one governed graph's data plane (§3 of the graph-data-contract).
- **`community` is not used to represent product ownership.** The contract defines `community` as an instance grouping or analytical partition that may change between graph builds or analysis runs (e.g. Louvain clustering). Product identity is a stable governance fact and must never move between runs; conflating the two would also block a product from using `community` for its own legitimate subject-area clustering.
- If cross-product lineage (data flowing *between* products) is ever needed, it is a **separate, explicitly designed federated graph** with `data_product` as a genuine `category` value on its own nodes — not a retrofit onto this module's per-product graphs or their `community` column. That federated graph is out of scope for this standard.

---

## 6. Load Semantics

The load path is a set-based upsert from Observability into this module's base tables, run on the same cadence as lineage/outcome capture (or on a scheduled interval — a designer decision, not a platform requirement):

1. **Node upsert**: natural keys from §4.1 are resolved against the existing node table; a natural key not yet seen receives a newly allocated `node_id` (an `Identifier`, allocated via the platform's surrogate-key mechanism, dense and never reused — mirroring the graph-explorer reference adapter's own convention). Existing natural keys are not renumbered — a node identity must refer to the same logical entity for the life of a published graph version, per the contract.
2. **Edge upsert**: `data_lineage` and `agent_outcome` rows resolve their natural keys to `node_id` and are inserted as `(node_i, node_j, edge_type, weight)`, deduplicated on `(node_i, node_j, edge_type)`.
3. Only `DataLineage` rows with `is_active=1` are loaded, matching `INV-OBS-006`'s stability guarantee: a retired flow does not appear as a live edge in the graph.

Base tables and ACL adapter views follow the external contract's naming exactly (§7). This module's own responsibility ends at populating `Graphs_<KEY>_STD_0_T`; the ACL views, catalogue rows, and READ role are declared once per graph and do not change as data flows through.

---

## 7. Graph Product Contract Binding

For graph key `<KEY>` (one per data product per §5):

| Plane | Object | Populated by |
|---|---|---|
| Data tables | `Graphs_<KEY>_STD_0_T.graph_nodes`, `.graph_edges` | Load path (§6) |
| Data locking views | `Graphs_<KEY>_STD_0_V.*` | Standard locking wrapper |
| Consumer adapters | `Graphs_<KEY>_ACL_0_V.graph_nodes`, `.graph_edges`, `.graph_edges_bi` | Canonical column remap (§4) — the only surface external consumers bind to |
| Read role | `R_Graphs_<KEY>_READ` | Standard grant |
| Catalogue | `Graphs_CAT_STD_0_T.graph_registry`, `.graph_relationship`, `.graph_role`, `.graph_trace_profile` | One-time registration, updated only on vocabulary change |

This module's SHIPS package declares the shared `graph-platform` package and this product's `Observability` container as `EXTERNAL_PARENTS`; it does not recreate either.

### 7.1 Trace profiles

Registered in `graph_trace_profile`:

| `profile_id` | `direction` | `relationship` | `stop_at_roles` | Purpose |
|---|---|---|---|---|
| `trace_to_source` | `upstream` | `produces,derives_column` | — | Where did this table/column come from? |
| `impact_analysis` | `downstream` | `produces,derives_column` | — | What breaks if this table/column changes? |
| `who_touched_this` | `downstream` | `accessed_by,queried_in` | `session` | Which agents/sessions have consumed this data? |

---

## 8. Applied Patterns

| Pattern | Contribution to Data Product Lineage |
|---|---|
| `object-placement` | Governs the `Graphs_<KEY>_*` container naming and locking-view pairing. |
| `access-layer` | `R_Graphs_<KEY>_READ` is the sole consumer-facing grant; base tables are never bound to directly. |
| `temporal-lifecycle-metadata` | Node/edge tables carry `created_dts` as provenance only, per the external contract's rule that it must never be read as business validity. As of graph-explorer contract version 2.0.0, `created_dts` is also the contract's own recommended column name, so no adapter-view rename is needed. |
| `validation` | The external contract's structural and semantic quality gates (§9 of the graph-data-contract) are this module's validator source, analogous to how Observability hosts validation evidence for the rest of the product. |

---

## 9. Capabilities and Composition

Data Product Lineage is an **optional exposure layer**, not a core module: a product can be a complete AI-Native Data Product without it. It hard-depends on Observability for its source data and on the external `graph-platform` for its runtime.

**Provides:**

| Capability | Made available to |
|---|---|
| `GraphNativeLineageTraversal` | Teradata Graph Explorer and any agent/analyst using it: upstream/downstream trace, impact analysis, and access-path traversal over this product's lineage. |

**Requires:**

| Capability | Strength | Provider | Why |
|---|---|---|---|
| `LineageCapture` | `[hard]` | `module:Observability` | Source of `DataLineage` and its executions. |
| `AgentOutcomeCapture` | `[hard]` | `module:Observability` | Source of access-lineage edges (`AgentOutcome.tables_accessed`). |
| Graph platform runtime | `[hard]` | `external:graph-platform` | Catalogue, engine, and quality procedures this module's package does not itself define. |
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on the graph package itself. |

---

## 10. Integration with Other Modules

- **Data Product Lineage → Observability**: reads `DataLineage` and `AgentOutcome` only; never writes back (`INV-DPL-001`). Observability's design and retention decisions are unaffected by whether this module is deployed at all.
- **Data Product Lineage + Semantic**: no integration by design. Observability's `lineage_graph` stays the Semantic-facing discovery edge-list for agents already inside Semantic (§1); this module is a separate, heavier adapter for graph-native tooling and does not register into the Semantic map.
- **Data Product Lineage + external `graph-platform`**: hard-depends on the shared catalogue, engine, and quality procedures (§9); provides no capability the platform itself does not already define, only this product's specific graph.

---

## 11. Invariants

- `INV-DPL-001`: this module reads Observability's `DataLineage` and `AgentOutcome`; it never becomes a second system of record for lineage or access facts, and never writes back into Observability.
- `INV-DPL-002`: a graph node or edge carries table/column/job/agent identifiers only, never business row data (extends `INV-OBS-001` into the graph adapter).
- `INV-DPL-003`: one data product registers exactly one lineage graph (`DEC-GRAPH-SCOPE`, §5); `community` is never used to encode product ownership.
- `INV-DPL-004`: only active (`is_active=1`) `DataLineage` rows are loaded into the graph, matching `INV-OBS-006`'s stability guarantee.
- `INV-DPL-005`: a node's surrogate `node` identity, once allocated, refers to the same logical entity for the life of the published graph version; natural-key remapping never reuses or shifts an existing `node` value.

---

## 12. Designer Responsibilities

**Designers supply:** the graph key for their product; whether `query_session` nodes are needed at all; the load cadence; whether column-level lineage is populated (many products may stay table-level only); retention/versioning policy for the graph if it diverges from Observability's.

**Design review checklist:**

- [ ] Graph key chosen and unique across the estate; no cross-product graph created without a separate federated design (`DEC-GRAPH-SCOPE`).
- [ ] `DataLineage` column extension applied only if column-level lineage is in scope for this product.
- [ ] Load path only reads Observability; never writes to it (`INV-DPL-001`).
- [ ] Only active lineage definitions loaded (`INV-DPL-004`).
- [ ] Catalogue rows (`graph_registry`, `graph_relationship`, `graph_role`, `graph_trace_profile`) registered before the ACL views are published.
- [ ] `R_Graphs_<KEY>_READ` is the only grant issued; no consumer binds to `STD_0_T`/`STD_0_V`.
- [ ] This document passes the design linter with no ignore directive.

### 12.1 Decisions to settle

| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-GRAPH-SCOPE` | one graph per data product | Already settled by this standard (§5); revisit only when a genuine cross-product federated graph is separately designed. |
| `DEC-GRAPH-COLUMN-LINEAGE` | omit unless requested | Does any consumer need column-grain trace, or is table-grain sufficient? |
| `DEC-GRAPH-SESSION-NODES` | omit unless requested | Is session-level access traversal (`query_session` nodes) actually queried, or does `agent`-level suffice? |
| `DEC-GRAPH-LOAD-CADENCE` | same cadence as lineage capture | Does graph-explorer need near-real-time lineage, or is a scheduled batch load sufficient? |

---

## 13. Implementation

The Teradata binding (the `Graphs_<KEY>_STD_0_T`/`ACL_0_V` DDL, the load procedure from Observability, and the catalogue seed rows) lives in [`implementation/teradata/modules/data-product-lineage/`](../../implementation/teradata/modules/data-product-lineage/). The external graph-explorer contract itself — ACL column shapes, catalogue table definitions, and quality procedures — is defined in the `teradata-graph-explorer` repository's `docs/graph-data-contract.md` and is out of scope for this repository to redefine.

---

**End of Data Product Lineage Module Design Standard**
