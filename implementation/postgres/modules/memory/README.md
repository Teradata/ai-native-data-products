---
title: PostgreSQL Memory Implementation
anchor: memory
type: implementation
status: draft
version: 2.0
normative: true
implements: memory
platform: postgres
---

# PostgreSQL: Memory

Binding of [Memory](../../../../design/modules/memory.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`entities.json` provides the six standard documentation entities and five runtime entities. Documentation uses versioned history. Runtime is optional (`runtime_memory`) and has no public passthrough view. `02-capture.sql.j2` records supplied design decisions and module declarations; it does not fabricate glossary terms, recipes or decisions to satisfy minimum counts.

`validation.sql.j2` checks per-module minimum decisions, glossary and cookbook coverage. Incomplete capture is a reported gap until the builder records the actual design. Runtime stores process context and aggregate counts, not copied business results.

PostgreSQL USER rows are scoped to authenticated session_user. Shared scopes are denied until a membership policy is supplied; owners, superusers and BYPASSRLS principals remain privileged. A pooled single database login cannot distinguish end users. DuckDB needs an authenticated serving application or separate protected storage; file access exposes runtime data.

## Capability bindings

| Capability | Binding |
|---|---|
| `DocumentationCapture` | Templates and enforcement limits described above. |
| `AgentContinuity` | Templates and enforcement limits described above. |

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-MEMORY-001,002,004` | Standard structures separate process/design context; producer payload review remains necessary. |
| `INV-MEMORY-003` | Required scope columns; PostgreSQL USER RLS tests or external DuckDB enforcement. |
| `INV-MEMORY-005` | Shared versioned temporal templates and checks. |
| `INV-MEMORY-006` | Module minimum decision/glossary/recipe query; complete capture protocol still applies. |

Logical types follow the [platform type table](../../PLATFORM_PROFILE.md#2-type-bindings). Temporal/lifecycle fields come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and are omitted when those modules are absent.
