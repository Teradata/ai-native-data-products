# Memory Module — Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Memory module — agent state and learning (runtime), and design memory (documentation) |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | [`implementation/teradata/modules/memory/`](../../implementation/teradata/modules/memory/) |

Memory is the module that **provides `DocumentationCapture`** — the capability every other module
soft-requires to record its design decisions. It is also the store of agent runtime state.

---

## 1. Purpose

Memory enables agent **learning, continuity, and collaboration** across sessions, users, and agent
instances, and it holds the product's **design memory** — the decisions, glossary, and change
history that make the product self-describing.

| AI-native characteristic | Purpose |
|--------------------------|---------|
| **Session continuity** | Agents remember context across interactions. |
| **Cross-agent learning** | Agents share strategies that worked. |
| **Preference learning** | Agents adapt to user and business preferences. |
| **Meta-learning** | Agents learn what works and improve over time. |
| **Privacy-aware** | Every runtime record is scoped (user, team, organisation, agent). |
| **Design memory** | Captures decisions, rationale, glossary, and change history via the documentation facet. |

---

## 2. Facets

Memory is one module with two **facets** (see the
[composition mechanism](../core/DESIGN_LANGUAGE.md#62-provision-requirement-and-composition)),
enabled independently:

| Facet | Holds | Provides |
|-------|-------|----------|
| **`documentation`** (design memory) | Module registry, design decisions, glossary, query cookbook, implementation notes, change log. | `DocumentationCapture` — consumed by every module. |
| **`runtime`** (agent state) | Sessions, interactions, learned strategies, preferences, discovered patterns. | Agent continuity and learning, consumed by agents. |

A **Data Asset** takes the `documentation` facet only (Domain + Memory[`documentation`] + Access
Layer). An **AI-Native Data Product** takes both. Neither facet has a hard dependency on another
module, so Memory can be deployed alongside Domain alone.

---

## 3. Scope and Boundaries

Two principles govern what Memory stores:

**Entity = table, not instance.** Memory references **entities (tables)**, never the individual
instance keys or rows from a query's results (`INV-MEMORY-001`).

**Big questions, small answers.** Agents process millions of records; Memory stores the *metadata*
about those processes — the query run, the tables involved, the outcome, the counts — never the
result data (`INV-MEMORY-002`). Memory holds thousands to tens of thousands of rows, not millions.

**In scope:** agent interaction metadata (what was asked, what query ran, which tables, the
outcome), agent learning metadata (strategies, patterns, success rates), preferences, session
state, and — via the documentation facet — design decisions, glossary, cookbook, registry, and
change history.

**Out of scope:** business domain data (→ Domain), query results (→ Domain or temporary tables),
individual record keys/ids, and detailed personal profiles (→ Domain, referenced by key).

---

## 4. Runtime Facet — Entity Model

Runtime entities are append-oriented operational records. Every one carries a **privacy scope**
(Section 6). None stores business content — table references are table-level, and content is
obtained by join-back to Domain.

```
Entity: AgentSession              [kind: Record]
  session_id       : Identifier                          — surrogate key
  session_key      : NaturalKey [required]               — business session identifier
  agent_key        : ShortText [required]                — which agent instance
  user_key         : ShortText [optional]                — which user
  session_start    : Timestamp [required]
  session_end      : Timestamp [optional]                — null while active
  session_status   : Enum{ACTIVE|COMPLETED|ABANDONED}
  session_goal     : Text [optional]
  session_context  : Json [optional]                     — flexible context, processed by the consumer
  scope_level      : Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier : ShortText [required]                — user/team/org/agent key matching scope_level

Entity: AgentInteraction          [kind: Record]
  interaction_id     : Identifier
  session_id         : Reference [required] [-> AgentSession]
  interaction_seq    : Integer [required]                — order within the session
  interaction_type   : Enum{QUERY|ACTION|DECISION|EXPLANATION}
  interaction_at     : Timestamp [required]
  user_input         : Text [optional]
  agent_response     : Text [optional]
  action_taken       : Text [optional]
  referenced_tables  : Text [optional]                   — qualified table names, comma-separated; TABLE-LEVEL only (INV-MEMORY-001)
  query_executed     : Text [optional]                   — the query text, not its results
  query_result_count : Integer [optional]                — aggregate count only, never the ids
  execution_time_ms  : Integer [optional]
  outcome_status     : Enum{SUCCESS|PARTIAL|FAILED}
  user_feedback      : Enum{POSITIVE|NEUTRAL|NEGATIVE} [optional]
  scope_level        : Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier   : ShortText [required]

Entity: LearnedStrategy           [kind: Record]
  strategy_id       : Identifier
  strategy_name     : ShortText [required]
  strategy_category : Enum{QUERY_OPTIMIZATION|FEATURE_SELECTION|ERROR_HANDLING} 
  strategy_pattern  : Text [optional]                    — the pattern/approach, described
  strategy_metadata : Json [optional]
  success_rate      : Decimal(5,4) [optional]            — 0.0–1.0
  times_used        : Integer [optional]
  is_active         : Flag
  is_validated      : Flag
  scope_level       : Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier  : ShortText [required]

Entity: UserPreference            [kind: Record]
  preference_id      : Identifier
  user_key           : ShortText [required]
  preference_category: Enum{REPORT_FORMAT|DATA_FILTER|AGGREGATION_LEVEL|VISUALIZATION_TYPE}
  preference_name    : ShortText [required]
  preference_value   : Text [optional]
  preference_json    : Json [optional]
  confidence         : Decimal(5,4) [optional]
  is_active          : Flag
  scope_level        : Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier   : ShortText [required]

Entity: DiscoveredPattern         [kind: Record]
  pattern_id            : Identifier
  pattern_name          : ShortText [required]
  pattern_type          : Enum{CORRELATION|TEMPORAL|TABLE_RELATIONSHIP|ANOMALY}
  pattern_definition    : Json [optional]
  sample_size           : Integer [optional]             — how many records analysed (summary, not the records)
  confidence_score      : Decimal(5,4) [optional]
  involved_tables       : Text [optional]                — TABLE-LEVEL references only (INV-MEMORY-001)
  is_validated          : Flag
  scope_level           : Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier      : ShortText [required]
```

All runtime entities `Apply patterns: object-placement, access-layer` and `Require: RichMetadata`.

---

## 5. Documentation Facet — Design Memory

The documentation facet **is** design memory: it records *why* a product is the way it is, *how*
to use it, and *what changed* — the counterpart to runtime memory's record of what agents did.

**Boundary with Semantic.** Semantic stores *what exists and how it connects* (tables, columns,
join paths); documentation stores *why it exists, how to use it, and what changed*. Documentation
never duplicates Semantic metadata (`INV-MEMORY-004`).

### 5.1 Documentation entities

Documentation entities are temporally versioned (they apply `temporal-lifecycle-metadata`);
corrections supersede prior versions rather than overwriting them (`INV-MEMORY-005`).

```
Entity: ModuleRegistry            [kind: History]
  module_registry_id : Identifier
  module_name        : Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [required]
  container_name     : ShortText [required]              — where the module is deployed
  deployment_status  : Enum{DEPLOYED|PLANNED|DEPRECATED} [required]
  module_version     : ShortText [required]
  module_purpose     : LongText [required]
  key_entities       : Text [optional]
  dependencies       : Text [optional]

Entity: DesignDecision            [kind: History]
  decision_id          : NaturalKey [required]           — DD-{MODULE}-{NNN}
  decision_version     : Integer [required]
  decision_title       : ShortText [required]
  context              : LongText [optional]
  alternatives         : LongText [optional]
  rationale            : LongText [optional]
  consequences         : LongText [optional]
  decision_status      : Enum{PROPOSED|ACCEPTED|SUPERSEDED|DEPRECATED} [required]
  decision_category    : Enum{ARCHITECTURE|SCHEMA|NAMING|PERFORMANCE|SECURITY|INTEGRATION|OPERATIONAL} [required]
  source_module        : ShortText [required]
  superseded_by        : NaturalKey [optional]

Entity: BusinessGlossary          [kind: History]
  term            : ShortText [required]
  term_category   : Enum{ENTITY|ATTRIBUTE|METRIC|BUSINESS_RULE|CLASSIFICATION|REFERENCE_CODE} [required]
  definition      : LongText [required]
  source_module   : ShortText [required]

Entity: QueryCookbook             [kind: History]
  recipe_id       : NaturalKey [required]                — QC-{MODULE}-{NNN}
  recipe_title    : ShortText [required]
  use_case        : ShortText [required]
  target_module   : Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY|CROSS} [required]
  query_template  : LongText [required]                  — parameterised query, consumed by agents
  complexity      : Enum{SIMPLE|MODERATE|COMPLEX|ADVANCED} [required]
  is_batch        : Flag                                 — 1 = batch only; 0 = safe for interactive agent use
  source_module   : ShortText [required]

Entity: ImplementationNote        [kind: History]
  note_id         : NaturalKey [required]                — IN-{MODULE}-{NNN}
  note_title      : ShortText [required]
  note_content    : LongText [required]
  note_category   : Enum{DEPLOYMENT|WORKAROUND|KNOWN_ISSUE|PERFORMANCE_TIP|OPERATIONAL|SECURITY} [required]
  severity        : Enum{LOW|MEDIUM|HIGH|CRITICAL} [optional]
  source_module   : ShortText [required]

Entity: ChangeLog                 [kind: History]
  change_id           : NaturalKey [required]            — CL-{MODULE}-{NNN}
  version_number      : ShortText [required]
  change_title        : ShortText [required]
  change_type         : Enum{INITIAL_RELEASE|SCHEMA_CHANGE|FEATURE_ADDITION|BUG_FIX|PERFORMANCE|DEPRECATION} [required]
  source_module       : ShortText [required]
  related_decision_id : NaturalKey [optional] [-> DesignDecision]
```

Use `source_module` on every documentation entity except `ModuleRegistry` (which uses
`module_name` to identify the registered module). Never add `module_name` to the other entities.

### 5.2 Capture protocol (the `DocumentationCapture` contract)

When any module is designed for the product, it records its documentation here. Each deployed
module must produce, at minimum:

| Record | Minimum | Id convention |
|--------|---------|---------------|
| Module registry entry | 1 per module *considered* (with `deployment_status`) | — |
| Design decision | 3 per deployed module | `DD-{MODULE}-{NNN}` |
| Change-log entry | 1 (initial release) | `CL-{MODULE}-{NNN}` |
| Business-glossary term | 3 | — |
| Query-cookbook recipe | 1 per deployed module; 1 cross-module recipe per deployed pair | `QC-{MODULE}-{NNN}` |
| Implementation note | as needed | `IN-{MODULE}-{NNN}` |

`{MODULE}` is the short module name (`DOMAIN`, `SEARCH`, …). Additional required records: a design
decision for every *deferred or deprecated* module; a design decision for **every deviation** from
a design standard (category `ARCHITECTURE`); and the ERD recipe `QC-SEMANTIC-002` when Semantic is
present. This protocol is the provider side of `INV-MASTER-002` — it is what Domain's Section 11
and Search's Section 12 point at.

---

## 6. Privacy and Scoping

Every **runtime** record carries a privacy scope — both a `scope_level`
(`USER`/`TEAM`/`ORGANIZATION`/`AGENT`) and a `scope_identifier` — with no exceptions
(`INV-MEMORY-003`). Retrieval always filters on scope, so a user sees only their own records, a
team its shared records, and so on.

**Data minimisation.** Store the `user_key` (an identifier), never names, emails, or demographics —
those are obtained by join-back to Domain when genuinely needed.

---

## 7. Applied Patterns

| Pattern | Contribution to Memory |
|---------|------------------------|
| `temporal-lifecycle-metadata` | Version-chains the documentation entities; corrections supersede, never overwrite. |
| `object-placement` | Which container the Memory tables and views are created in, and who may reach them. |
| `access-layer` | Standard views over sessions, interactions, current decisions, active recipes, etc. |
| `validation` | The conformance checks run before the module is declared done. |

---

## 8. Capabilities and Composition

Memory is **cross-cutting and soft**: nothing hard-depends on it, and it hard-depends on nothing —
so it composes with any product, and either facet can be deployed alone. See the
[composition mechanism](../core/DESIGN_LANGUAGE.md#62-provision-requirement-and-composition).

**Provides:**

| Capability | Facet | Made available to |
|------------|-------|-------------------|
| `DocumentationCapture` | `documentation` | Every module, to record its design memory. |
| Agent continuity and learning | `runtime` | Agents, across sessions and instances. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on every object and attribute. |
| `DocumentationCapture` | `[soft]` | `self` (`documentation` facet) | Memory records its own design decisions. |
| `SemanticRegistration` | `[soft]` | `module:Semantic` | Register Memory's entities in the Semantic map when present (`INV-MASTER-002`). |
| `EntityJoinBack` | `[soft]` | `module:Domain` | Resolve a referenced table to Domain entity context when needed. |
| Learning inputs | `[soft]` | `module:Observability` | Learn strategies from observed outcomes when Observability is present. |
| Similarity retrieval | `[soft]` | `module:Search` | Find similar past sessions when Search is present. |

---

## 9. Integration with Other Modules

- **Observability → Memory** — Memory learns strategies from observed outcomes (which query
  patterns performed well). Soft: absent Observability simply means no outcome-driven learning.
- **Memory + Search** — find similar historical sessions via Search's `NearestNeighbors`. Soft.
- **Memory + Semantic** — apply learned rules alongside Semantic's business rules; register Memory's
  own entities in the Semantic map. Soft.
- **Memory + Domain** — table-level references resolve to Domain entity context by join-back when
  needed. Memory never copies Domain content.

---

## 10. Invariants

- `INV-MEMORY-001`: Memory references entities at the table level (qualified names); it never stores individual instance keys/ids from query results.
- `INV-MEMORY-002`: Memory stores process metadata (query text, patterns, outcomes, counts), never result data or business content; content is obtained by join-back to Domain.
- `INV-MEMORY-003`: every runtime record carries a privacy scope (`scope_level` and `scope_identifier`).
- `INV-MEMORY-004`: documentation records *why/how/what-changed*; they never duplicate Semantic's *what-exists/how-connects* metadata.
- `INV-MEMORY-005`: documentation records are temporally versioned — corrections supersede prior versions rather than overwriting them.
- `INV-MEMORY-006`: *when the documentation facet is present*, every deployed module records its documentation here per the Section 5.2 capture protocol (the provider side of `INV-MASTER-002`).

---

## 11. Designer Responsibilities

**Designers supply:**

| Element | Example |
|---------|---------|
| Agent types | analytics agent, customer-service agent |
| Session patterns | query session, analysis session |
| Learning categories | query patterns, feature importance, preferences |
| Privacy scoping | which scope levels are in use |
| Retention policies | sessions 90 days, interactions 1 year, validated strategies 2 years |
| Facets enabled | `documentation` only (Data Asset) or both (AI-native) |

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Every runtime record carries a privacy scope (`INV-MEMORY-003`).
- [ ] Table references are table-level only; no instance keys stored (`INV-MEMORY-001`, `INV-MEMORY-002`).
- [ ] Documentation records do not duplicate Semantic metadata (`INV-MEMORY-004`).
- [ ] Documentation is temporally versioned; corrections supersede, never overwrite (`INV-MEMORY-005`).
- [ ] Retention policies documented per runtime entity.
- [ ] The capture protocol (Section 5.2) is available to every module when the documentation facet is present.
- [ ] Memory's own entities registered in the Semantic map when Semantic is present (`SemanticRegistration`).
- [ ] Every invariant has a check in the implementation.
- [ ] This document passes the design linter with no ignore directive.

---

## 12. Implementation

The Teradata binding — the runtime and documentation tables, the standard views, the capture-protocol
templates, and the invariant checks — lives in
[`implementation/teradata/modules/memory/`](../../implementation/teradata/modules/memory/).
Other platforms add sibling directories under `implementation/` without changing this document.

---

**End of Memory Module Design Standard**
