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

Binding of [Memory](../../../../design/modules/memory.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[schema.sql](schema.sql) separates versioned documentation from private runtime process state. `DocumentationCapture` generates decisions, glossary, cookbook, release notes and provenance for every module. `AgentContinuity` stores scoped sessions, interactions, strategies, preferences and patterns; it does not store business result rows.

Documentation uses SCD2 current views. Runtime uses CURRENT_STATE and has no public passthrough views. Native row policies bind USER scope to authenticated `session_user`; caller-set configuration variables are never trusted identities. AGENT may read/insert/update only its own USER rows. TEAM, ORGANIZATION and AGENT scope sharing is deliberately denied until a membership policy is implemented. READ cannot reach runtime tables. ADMIN, owners and superusers are privileged.

`DOC`, `MEM-SCOPE`, `BOUNDARY` and metadata checks cover registration and minimum content. Integration tests exercise authenticated scope, denied owner changes and denied deletes. Separate login identities are required; pooling all end users through one login requires a separately designed authentication boundary.
