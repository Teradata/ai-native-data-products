---
title: DuckDB Memory Implementation
anchor: memory
type: implementation
status: draft
version: 2.0
normative: true
implements: memory
platform: duckdb
---

# DuckDB: Memory

Binding of [Memory](../../../../design/modules/memory.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`entities.json` provides the six standard documentation entities and five runtime entities. Documentation uses versioned history. Runtime is optional (`runtime_memory`) and has no public passthrough view. `02-capture.sql.j2` records supplied design decisions and module declarations; it does not fabricate glossary terms, recipes or decisions to satisfy minimum counts.

`validation.sql.j2` checks per-module minimum decisions, glossary and cookbook coverage. Incomplete capture is a reported gap until the builder records the actual design. Runtime stores process context and aggregate counts, not copied business results. Process context uses the DuckDB `JSON` type.

DuckDB has no row-level security or authenticated principals. Runtime rows carry required `scope_level` and `scope_identifier` columns, but nothing in the engine filters by caller, and read-only mode does not hide them. Privacy needs an authenticated serving application that derives scope from identity, or separate protected storage. Direct access to the database file exposes runtime data.

## Capability bindings

| Capability | Binding |
|---|---|
| `DocumentationCapture` | Six versioned documentation entities; `02-capture.sql.j2` loads supplied records; `validation.sql.j2` reports minimum-capture gaps. |
| `AgentContinuity` | Five scoped runtime entities with required scope columns and CHECK-constrained scope levels. Scope enforcement is external to DuckDB. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-MEMORY-001,002,004` | Standard structures separate process and design context; producer payload review remains necessary. |
| `INV-MEMORY-003` | Required scope columns and no consumer view or agent-consumable registration are tested. Runtime privacy enforcement is a declared gap. |
| `INV-MEMORY-005` | Shared versioned temporal templates and checks. |
| `INV-MEMORY-006` | Module minimum decision, glossary and recipe query; complete capture protocol still applies. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal and lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
