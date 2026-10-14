---
title: DuckDB Memory Module Implementation
anchor: memory
type: implementation
status: standard
version: 2.0
normative: true
implements: memory
platform: duckdb
---

# DuckDB Memory

Binding of [Memory](../../../../design/modules/memory.md). [schema.sql](schema.sql) implements both facets without mixing their data or access surfaces.

**Provides:**

| Capability | Binding |
|---|---|
| `DocumentationCapture` | Six versioned documentation entities, with author/source/instant provenance. |
| `AgentContinuity` | Scoped runtime process state; privacy enforcement is external. |

Documentation includes module registry, decisions, glossary, cookbook, implementation notes and change log. Each deployed module has at least three decisions, three glossary terms, a recipe and an initial release; every module pair has a cross-module recipe. Required DD-ACCESS-001, DD-DISCOVERY-001 and QC-SEMANTIC-002 are present. Records explain choices and use, rather than copying Semantic's catalogue. Corrections supersede through the shared temporal writer.

Runtime includes agent_session, agent_interaction, learned_strategy, user_preference and discovered_pattern. All require scope_level and scope_identifier; none is registered agent-consumable or given a public view. They hold process context, SQL patterns and counts, not customer ids from results or business content. User keys are pseudonymous actor identities, not Domain customer joins. Empty learning stores mean no learning evidence, not omitted structures.

The [access boundary](../../patterns/access-layer/) is essential: a direct file reader can inspect all synthetic runtime records. A real deployment requires authenticated host filtering or a separate protected runtime file. No parameterized SQL filter alone is claimed as identity enforcement. `C360-DOC-*`, runtime scope checks, history tests and cookbook execution verify storage/capture contracts; external privacy remains explicitly unknown.
