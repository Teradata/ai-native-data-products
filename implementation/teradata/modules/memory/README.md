# Teradata — Memory Module Implementation

Concrete Teradata binding of [`design/modules/memory.md`](../../../../design/modules/memory.md).
Read the design document first; this directory only adds Teradata specifics. Memory is one module
with two facets — `runtime` and `documentation` — deployed independently.

## Files

| File | Facet | Purpose |
|------|-------|---------|
| `01-runtime-tables.sql` | runtime | `agent_session`, `agent_interaction`, `learned_strategy`, `user_preference`, `discovered_pattern`. |
| `02-runtime-views.sql` | runtime | Standard views over sessions and interactions (`AccessView`). |
| `10-documentation-tables.sql` | documentation | The six design-memory tables (`Module_Registry`, `Design_Decision`, `Business_Glossary`, `Query_Cookbook`, `Implementation_Note`, `Change_Log`). |
| `11-documentation-views.sql` | documentation | Standard views (`v_Current_Decisions`, `v_Cookbook_Active`, …). |
| `12-capture-protocol.sql` | documentation | The `DocumentationCapture` binding — the `INSERT` templates every module uses to register and record its design memory, plus the standard ERD recipe. |
| `validation.sql` | both | Runnable checks for the module's invariants. |

A **Data Asset** deploys `10`–`12` only (documentation facet). An **AI-Native** product deploys all.
Replace `{{ product }}` with the data product name; all tables live in `{{ product }}_Memory`.

## Capability bindings

| Capability (design) | Teradata binding |
|---------------------|------------------|
| `DocumentationCapture` | `INSERT` into the six documentation tables per `12-capture-protocol.sql`; version chain via `is_current` + `valid_from`/`valid_to`. |
| Agent continuity / learning | The five runtime tables + views. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN`. |
| `SemanticRegistration` *(soft)* | When Semantic is present: register Memory's entities in `{{ product }}_Semantic`. |
| `EntityJoinBack` *(soft → Domain)* | Resolve a table reference to Domain content by join when needed. |

## Logical-type bindings used here

| Logical type (design) | Teradata type |
|-----------------------|---------------|
| `Identifier` | `INTEGER` / `BIGINT` `GENERATED ALWAYS AS IDENTITY` |
| `NaturalKey` | `VARCHAR(n)` |
| `ShortText` / `Text` | `VARCHAR(n)` |
| `LongText` | `CLOB` |
| `Json` | `JSON` |
| `Enum{…}` | `VARCHAR(n)` with a documented value set |
| `Integer` | `INTEGER` |
| `Decimal(p,s)` | `DECIMAL(p,s)` |
| `Timestamp` | `TIMESTAMP(6) WITH TIME ZONE` |
| `Date` | `DATE` |
| `Flag` | `BYTEINT` |

## Invariants → checks

| Invariant | Check |
|-----------|-------|
| `INV-MEMORY-001` (table-level refs) | `validation.sql` §1 — no instance-key columns on runtime tables. |
| `INV-MEMORY-002` (metadata not results) | Enforced by schema: no result-set columns; reviewed at design time. |
| `INV-MEMORY-003` (privacy scope) | `validation.sql` §2 — every runtime table has `scope_level` + `scope_identifier`. |
| `INV-MEMORY-004` (no Semantic dup) | Reviewed at design time; documentation holds rationale, not join paths. |
| `INV-MEMORY-005` (versioned docs) | `validation.sql` §3 — documentation tables carry `is_current`/`valid_from`/`valid_to`. |
| `INV-MEMORY-006` (capture protocol) | `validation.sql` §4 — minimum documentation records present per deployed module. |
