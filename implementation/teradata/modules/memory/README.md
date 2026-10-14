---
title: Teradata Memory Module Implementation
anchor: memory
type: implementation
status: standard
version: 2.0
normative: true
implements: memory
platform: teradata
---

# Teradata: Memory Module Implementation

Concrete Teradata binding of [`design/modules/memory.md`](../../../../design/modules/memory.md). Read the design document first; this directory only adds Teradata specifics. Memory is one module with two facets, `runtime` and `documentation`, deployed independently.

## Files

| File | Facet | Purpose |
|------|-------|---------|
| `01-runtime-tables.sql.j2` | runtime | `agent_session`, `agent_interaction`, `learned_strategy`, `user_preference`, `discovered_pattern`. |
| `02-runtime-views.sql.j2` | runtime | Standard views over sessions and interactions (`AccessView`). |
| `10-documentation-tables.sql.j2` | documentation | The six design-memory tables (`Module_Registry`, `Design_Decision`, `Business_Glossary`, `Query_Cookbook`, `Implementation_Note`, `Change_Log`). |
| `11-documentation-views.sql.j2` | documentation | Standard views (`v_Current_Decisions`, `v_Cookbook_Active`, …). |
| `12-capture-protocol.sql.j2` | documentation | The `DocumentationCapture` binding: the `INSERT` templates every module uses to register and record its design memory, plus the standard ERD recipe. |
| `validation.sql.j2` | both | Runnable checks for the module's invariants. |

A **Data Asset** deploys `10`-`12` only (documentation facet). An **AI-Native** product deploys all. Replace `{{ product }}` with the data product name; all tables live in `{{ product }}_Memory`.

## Applying column comments

`RichMetadata` is a hard requirement of every module, and column comments are how it is satisfied. They are also the step most easily lost, because they trail the `CREATE TABLE` in the same file.

The failure has a shape worth naming: **any step bundled behind a step that can require intervention is a step that can be skipped.** When a table creation stalls and needs investigating, attention goes to the table; the session fixes it, moves on, and the comment block below it is never submitted. The comments are then present in the artefact and absent from the database, which no reading of the file will reveal.

So treat comments as their own deployment unit, not as lines appended to a table:

1. Apply `CREATE TABLE` and `COMMENT ON TABLE`.
2. Apply the `COMMENT ON COLUMN` statements.
3. **Verify before moving on**, and expect zero rows:

```sql
SELECT DatabaseName, TableName, ColumnName
FROM DBC.ColumnsV
WHERE DatabaseName = '{{ product }}_Memory'
  AND (CommentString IS NULL OR TRIM(CommentString) = '');
```

The same sequence applies to every module: the gate is what makes the step recoverable, because a skipped comment block is otherwise discovered by a conformance run days later, against a whole module at once.

## Capability bindings

| Capability (design) | Teradata binding |
|---------------------|------------------|
| `DocumentationCapture` | `INSERT` into the six documentation tables per `12-capture-protocol.sql.j2`; version chain via `is_current` + `valid_from_dts`/`valid_to_dts`. |
| Agent continuity / learning | The five runtime tables + views. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN`, applied and verified as their own step (below). |
| `SemanticRegistration` *(soft)* | When Semantic is present: register Memory's entities in `{{ product }}_Semantic`. |
| `EntityJoinBack` *(soft → Domain)* | Resolve a table reference to Domain content by join when needed. |

## Logical-type bindings used here

| Logical type (design) | Teradata type |
|-----------------------|---------------|
| `Identifier` | `INTEGER` / `BIGINT` `GENERATED ALWAYS AS IDENTITY` |
| `NaturalKey` | `VARCHAR(n)` |
| `ShortText` / `Text` | `VARCHAR(n) CHARACTER SET UNICODE` |
| `LongText` | `CLOB CHARACTER SET UNICODE` |
| `Json` | `JSON` |
| `Enum{…}` | `VARCHAR(n) CHARACTER SET UNICODE` with a documented value set |
| `Integer` | `INTEGER` |
| `Decimal(p,s)` | `DECIMAL(p,s)` |
| `Timestamp` | `TIMESTAMP(6) WITH TIME ZONE` |
| `Date` | `DATE` |
| `Flag` | `BYTEINT` |

## Migrating a deployed documentation facet

The documentation tables previously carried `created_timestamp`/`updated_timestamp` and a DATE-grain `valid_from`/`valid_to` pair. All four are prohibited generic names (TLM-04) with exactly one canonical replacement each, and the validity pair widens to `TIMESTAMP(6) WITH TIME ZONE` because validity bounds are always timestamps (pattern section 4.1). A new product deploys `10-documentation-tables.sql.j2` as it stands and needs nothing here.

A deployed product migrates on the path the pattern already prescribes (section 11), not a local one:

**1. Project the canonical names first.** Consumers move to the canonical names before the base tables are regenerated, so nothing downstream ever has to read both dialects:

```sql
REPLACE VIEW {{ product }}_Memory.v1_Design_Decision
AS
LOCKING ROW FOR ACCESS
SELECT
      decision_id, decision_version, decision_title, decision_status
    , decision_category, source_module, rationale, decided_by, decided_date
    , CAST(valid_from AS TIMESTAMP(6) WITH TIME ZONE) AS valid_from_dts
    , CAST(valid_to   AS TIMESTAMP(6) WITH TIME ZONE) AS valid_to_dts
    , is_current
    , created_timestamp AS created_dts
    , updated_timestamp AS updated_dts
FROM {{ product }}_Memory.Design_Decision;
```

The projection is versioned (`v1_`) because it is a stated compatibility surface with an end, not a permanent alias. Retire it once the base tables are regenerated and consumers read them directly.

**2. Regenerate the base tables**, then repoint the projection at the canonical columns or drop it.

**What the widening cannot recover.** Migrated historical rows were captured at DATE grain, so every version boundary for them lands at midnight. **Intra-day ordering is unavailable for historical rows**: two versions of the same `decision_id` superseded on the same day are indistinguishable in time order after migration, and `decision_version` is the only thing that separates them. Widening the type does not recover a precision that was never recorded. Rows captured after migration carry the real instant, since `12-capture-protocol.sql.j2` closes a version at `CURRENT_TIMESTAMP(6)`.

## Invariants → checks

| Invariant | Check |
|-----------|-------|
| `INV-MEMORY-001` (table-level refs) | `validation.sql.j2` §1: no instance-key columns on runtime tables. |
| `INV-MEMORY-002` (metadata not results) | Enforced by schema: no result-set columns; reviewed at design time. |
| `INV-MEMORY-003` (privacy scope) | `validation.sql.j2` §2: every runtime table has `scope_level` + `scope_identifier`. |
| `INV-MEMORY-004` (no Semantic dup) | Reviewed at design time; documentation holds rationale, not join paths. |
| `INV-MEMORY-005` (versioned docs) | `validation.sql.j2` §3: documentation tables carry `is_current`/`valid_from_dts`/`valid_to_dts`. |
| `INV-MEMORY-006` (capture protocol) | `validation.sql.j2` §4: minimum documentation records present per deployed module. |
