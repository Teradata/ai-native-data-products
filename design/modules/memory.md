---
title: Memory Module
anchor: memory
type: module
status: standard
version: 2.0
normative: true
---

# Memory Module: Design Standard

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Module Design Standard (platform-agnostic) |
| **Scope** | Memory module: agent state and learning (runtime), and design memory (documentation) |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | `implementation/{platform}/modules/memory/`, one per platform |

Memory is the module that **provides `DocumentationCapture`**: the capability every other module soft-requires to record its design decisions. It is also the store of agent runtime state.

---

## 1. Purpose

Memory enables agent **learning, continuity, and collaboration** across sessions, users, and agent instances, and it holds the product's **design memory**: the decisions, glossary, and change history that make the product self-describing.

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

Memory is one module with two **facets** (see the [composition mechanism](../core/DESIGN_LANGUAGE.md)), enabled independently:

| Facet | Holds | Provides |
|-------|-------|----------|
| **`documentation`** (design memory) | Module registry, design decisions, glossary, query cookbook, implementation notes, change log. | `DocumentationCapture`: consumed by every module. |
| **`runtime`** (agent state) | Sessions, interactions, learned strategies, preferences, discovered patterns. | Agent continuity and learning, consumed by agents. |

A **Data Asset** takes the `documentation` facet only (Domain + Memory[`documentation`] + Access Layer). An **AI-Native Data Product** takes both. Neither facet has a hard dependency on another module, so Memory can be deployed alongside Domain alone.

---

## 3. Scope and Boundaries

Two principles govern what Memory stores:

**Entity, not instance.** Memory references **entities**, by their logical names (`<product_code>.<Entity>`), never the individual instance keys or rows from a query's results (`INV-MEMORY-001`). A logical name is resolved to the physical object through Semantic, or, without Semantic, through the logical-to-physical names the build records in object metadata; Memory never stores a physical name, which belongs to one organisation's profile and one platform.

**Big questions, small answers.** Agents process millions of records; Memory stores the *metadata* about those processes (the query run, the entities involved, the outcome, the counts) and never the result data (`INV-MEMORY-002`). Memory holds thousands to tens of thousands of rows, not millions.

**In scope:** agent interaction metadata (what was asked, what query ran, which entities, the outcome), agent learning metadata (strategies, patterns, success rates), preferences, session state, and, via the documentation facet, design decisions, glossary, cookbook, registry, and change history.

**Out of scope:** business domain data (→ Domain), query results (→ Domain or temporary tables), individual record keys/ids, and detailed personal profiles (→ Domain, referenced by key).

### 3.1 Process context against result data

`INV-MEMORY-001` is the invariant designs violate most often, and they violate it in good faith. Session continuity naturally suggests storing what the agent last found, and the line between *what the agent is doing* and *what a query returned* is genuinely not obvious from the prohibition alone. It is worth stating from the compliant side.

**Process context (store it).** A record of what the agent is doing. "The agent is investigating agreement `AGR-00042`" is process context: store `current_entity_key`. So is "the last similarity search asked for overdue renewals and matched 37 rows": store the query text and the count.

**Result data (do not store it).** A record of what a query returned. "The last search matched `AGR-00001`, `AGR-00042`, `AGR-00099`" is result data, whatever it is called. Storing that key list makes Memory a result cache, and a stale one, since nothing invalidates it when the underlying rows change. If the agent needs those keys again it re-executes the search, which is cheap and always correct.

The test is not what the attribute is named but what it holds: an attribute holding one key the agent chose to work on is context; an attribute holding the set a query produced is a cached result. `retrieved_*_keys`, `*_key_list`, and `result_*` are the shapes this failure takes.

The same distinction governs counts: `query_result_count` is an aggregate about the process and belongs here; the ids it counted do not.

---

## 4. Entity Model: Runtime Facet

Runtime entities are operational records. Interactions are appended; sessions, strategies, preferences and patterns are updated in place as they progress, and each entity declares the profile that matches. A `Record` has no default profile, so every one states it. Every runtime entity carries a **privacy scope** (see Privacy and Scoping). None stores business content: references are entity-level, by logical name, and content is obtained by join-back to Domain.

Runtime entities do not version, so an identifier allocated as the row is written is already stable: `AgentSession`, the one runtime entity others reference, allocates `inline` and carries both its `Identifier` and its business session key.

```
Entity: AgentSession              [kind: Record] [profile: CURRENT_STATE] [allocation: inline]
  session_id: Identifier  // surrogate key
  session_key: NaturalKey [required]  // business session identifier
  agent_key: ShortText [required]  // which agent instance
  user_key: ShortText [optional]  // which user
  session_start_dts: Timestamp [required]
  session_end_dts: Timestamp [optional]  // null while active
  session_status: Enum{ACTIVE|COMPLETED|ABANDONED}
  session_goal: Text [optional]
  session_context: Json [optional]  // flexible context, processed by the consumer
  scope_level: Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier: ShortText [required]  // user/team/org/agent key matching scope_level

  Keys:
    surrogate: session_id
    natural:   session_key

Entity: AgentInteraction          [kind: Record] [profile: EVENT_APPEND_ONLY]
  interaction_id: Identifier
  session_id: Reference [required] [-> AgentSession]
  interaction_seq: Integer [required]  // order within the session
  interaction_type: Enum{QUERY|ACTION|DECISION|EXPLANATION}
  interaction_dts: Timestamp [required]
  user_input: Text [optional] [pii-incidental]  // what the user asked, as written
  agent_response: Text [optional] [pii-incidental]
  action_taken: Text [optional]
  referenced_tables: Text [optional]  // logical entity names (<product_code>.<Entity>), comma-separated; ENTITY-LEVEL only, resolved through Semantic (INV-MEMORY-001)
  query_executed: Text [optional]  // the query text, not its results
  query_result_count: Integer [optional]  // aggregate count only, never the ids
  execution_time_ms: Integer [optional]
  outcome_status: Enum{SUCCESS|PARTIAL|FAILED}
  user_feedback: Enum{POSITIVE|NEUTRAL|NEGATIVE} [optional]
  scope_level: Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier: ShortText [required]

Entity: LearnedStrategy           [kind: Record] [profile: CURRENT_STATE]
  strategy_id: Identifier
  strategy_name: ShortText [required]
  strategy_category: Enum{QUERY_OPTIMIZATION|FEATURE_SELECTION|ERROR_HANDLING}  // fixed by this standard
  strategy_pattern: Text [optional]  // the pattern/approach, described
  strategy_metadata: Json [optional]
  success_rate: Decimal(5,4) [optional]  // 0.0-1.0
  times_used: Integer [optional]
  is_active: Flag  // lifecycle state: the strategy is offered to agents; cleared when retired
  is_validated: Flag  // the strategy has been confirmed against observed outcomes
  scope_level: Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier: ShortText [required]

Entity: UserPreference            [kind: Record] [profile: CURRENT_STATE]
  preference_id: Identifier
  user_key: ShortText [required]
  preference_category: Enum{REPORT_FORMAT|DATA_FILTER|AGGREGATION_LEVEL|VISUALIZATION_TYPE}
  preference_name: ShortText [required]
  preference_value: Text [optional]
  preference_json: Json [optional]
  confidence: Decimal(5,4) [optional]
  is_active: Flag  // lifecycle state: the preference is applied; cleared when the user withdraws it
  scope_level: Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier: ShortText [required]

Entity: DiscoveredPattern         [kind: Record] [profile: CURRENT_STATE]
  pattern_id: Identifier
  pattern_name: ShortText [required]
  pattern_type: Enum{CORRELATION|TEMPORAL|TABLE_RELATIONSHIP|ANOMALY}
  pattern_definition: Json [optional]
  sample_size: Integer [optional]  // how many records analysed (summary, not the records)
  confidence_score: Decimal(5,4) [optional]
  involved_tables: Text [optional]  // logical entity names only, resolved through Semantic (INV-MEMORY-001)
  is_validated: Flag  // the pattern has been confirmed
  scope_level: Enum{USER|TEAM|ORGANIZATION|AGENT} [required]
  scope_identifier: ShortText [required]
```

All runtime entities apply `temporal-lifecycle-metadata`, `object-placement` and `access-layer`, and require `RichMetadata`.

---

## 5. Entity Model: Documentation Facet

The documentation facet **is** design memory: it records *why* a product is the way it is, *how* to use it, and *what changed*. Runtime memory records what agents did; this records what the designers decided.

**Boundary with Semantic.** Semantic stores *what exists and how it connects* (tables, columns, join paths); documentation stores *why it exists, how to use it, and what changed*. Documentation never duplicates Semantic metadata (`INV-MEMORY-004`).

### 5.1 Documentation entities

Documentation entities are temporally versioned (they apply `temporal-lifecycle-metadata`); corrections supersede prior versions rather than overwriting them (`INV-MEMORY-005`). They declare `SCD2_HISTORY`, which a History entity may take whatever the product's `DEC-TEMPORAL-PATTERN` (see Decisions to settle).

Each has one identity, declared in its `Keys:` section. A record whose business id is immutable and never reused (a decision, a recipe, a note, a change, a glossary term) uses that id as its identity under `natural-key` allocation, and a reference to it, such as a change-log entry's decision, holds that id. The module registry, keyed on the module, allocates `inline`. These allocations are the standard's, fixed for every product, not a product's departure from its `DEC-SURROGATE-ALLOCATION` choice.

```
Entity: ModuleRegistry            [kind: History] [profile: SCD2_HISTORY] [allocation: inline]
  module_registry_id: Identifier
  module_name: Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY} [required]
  container_name: ShortText [required]  // where the module is deployed; filled by the build from the build context, never by the design
  deployment_status: Enum{DEPLOYED|PLANNED|DEPRECATED} [required]
  module_version: ShortText [required]
  module_purpose: LongText [required]
  key_entities: Text [optional]  // logical entity names
  dependencies: Text [optional]

  Keys:
    surrogate: module_registry_id
    natural:   module_name

Entity: DesignDecision            [kind: History] [profile: SCD2_HISTORY] [allocation: natural-key]
  decision_id: NaturalKey [required]  // DD-{MODULE}-{NNN}
  decision_version: Integer [required]  // revision number; increases with each superseding version
  decision_title: ShortText [required]
  context: LongText [optional]
  alternatives: LongText [optional]
  rationale: LongText [optional]
  consequences: LongText [optional]
  decision_status: Enum{PROPOSED|ACCEPTED|SUPERSEDED|DEPRECATED} [required]
  decision_category: Enum{ARCHITECTURE|SCHEMA|NAMING|PERFORMANCE|SECURITY|INTEGRATION|OPERATIONAL} [required]
  source_module: ShortText [required]
  superseded_by: Reference [optional] [-> DesignDecision]  // the superseding decision's id

  Keys:
    natural: decision_id

Entity: BusinessGlossary          [kind: History] [profile: SCD2_HISTORY] [allocation: natural-key]
  term: NaturalKey [required]  // the Glossary block's name
  term_category: Enum{ENTITY|ATTRIBUTE|METRIC|BUSINESS_RULE|CLASSIFICATION|REFERENCE_CODE} [required]
  definition: LongText [required]
  source_module: ShortText [required]

  Keys:
    natural: term

Entity: QueryCookbook             [kind: History] [profile: SCD2_HISTORY] [allocation: natural-key]
  recipe_id: NaturalKey [required]  // QC-{MODULE}-{NNN}
  recipe_title: ShortText [required]
  use_case: ShortText [required]
  target_module: Enum{DOMAIN|SEARCH|PREDICTION|OBSERVABILITY|SEMANTIC|MEMORY|CROSS} [required]
  query_template: LongText [required]  // parameterised query in the platform's dialect, generated by the binding; consumed by agents
  complexity: Enum{SIMPLE|MODERATE|COMPLEX|ADVANCED} [required]
  is_batch: Flag  // set: batch only; clear: safe for interactive agent use
  source_module: ShortText [required]

  Keys:
    natural: recipe_id

Entity: ImplementationNote        [kind: History] [profile: SCD2_HISTORY] [allocation: natural-key]
  note_id: NaturalKey [required]  // IN-{MODULE}-{NNN}
  note_title: ShortText [required]
  note_content: LongText [required]
  note_category: Enum{DEPLOYMENT|WORKAROUND|KNOWN_ISSUE|PERFORMANCE_TIP|OPERATIONAL|SECURITY} [required]
  severity: Enum{LOW|MEDIUM|HIGH|CRITICAL} [optional]
  source_module: ShortText [required]

  Keys:
    natural: note_id

Entity: ChangeLog                 [kind: History] [profile: SCD2_HISTORY] [allocation: natural-key]
  change_id: NaturalKey [required]  // CL-{MODULE}-{NNN}
  version_number: ShortText [required]
  change_title: ShortText [required]
  change_type: Enum{INITIAL_RELEASE|SCHEMA_CHANGE|FEATURE_ADDITION|BUG_FIX|PERFORMANCE|DEPRECATION} [required]
  source_module: ShortText [required]
  related_decision_id: Reference [optional] [-> DesignDecision]  // the decision's id

  Keys:
    natural: change_id
```

Use `source_module` on every documentation entity except `ModuleRegistry` (which uses `module_name` to identify the registered module). Never add `module_name` to the other entities. `source_module` holds one registered module name; the capture protocol below states why that matters and what to do with a decision that spans several.

### 5.2 Capture protocol (the `DocumentationCapture` contract)

When the product is built, the build records each module's documentation here, from the design specification, the composition and the build itself. Each deployed module must produce, at minimum:

| Record | Minimum | Id convention | Source |
|--------|---------|---------------|--------|
| Module registry entry | 1 per module *considered* (with `deployment_status`) | - | The composition, written by the build. |
| Design decision | 3 per deployed module | `DD-{MODULE}-{NNN}` | The specification's frontmatter `decisions` (one record per catalogued decision per module that raises it) and its `Decision:` blocks. |
| Change-log entry | 1 (initial release) | `CL-{MODULE}-{NNN}` | Written by the build. |
| Business-glossary term | 3 | - | The specification's `Glossary:` blocks. |
| Query-cookbook recipe | 1 per deployed module; 1 cross-module recipe per deployed pair | `QC-{MODULE}-{NNN}` | Generated by the binding, in the platform's dialect, from the specification's metrics, access objects and relationships. The specification never holds query text. |
| Implementation note | as needed | `IN-{MODULE}-{NNN}` | Written by the build. A note may record a risk the specification flags, such as an attribute marked `[pii-incidental]`. |

`{MODULE}` is the module's name or a recognisable short form of it (`DOMAIN`, `SEARCH`, `PRED`, …), used consistently across the product. Additional required records: a design decision for every *deferred or deprecated* module; a design decision for **every deviation** from a design standard (category `ARCHITECTURE`); and the ERD recipe `QC-SEMANTIC-002` when Semantic is present. This protocol is the provider side of `INV-MASTER-002`: it is what the other modules' Designer Responsibilities sections point at.

**What counts toward the three, and what `source_module` may hold.** Two different things are both called decisions, and reading one as the other is how a module ends up appearing under its minimum, or above it, without anyone being wrong:

- A **catalogued decision** (`DEC-TEMPORAL-PATTERN`, `DEC-DELETE-STRATEGY`, …) is a *question* a module obliges a designer to settle, listed under Designer Responsibilities. It is part of this standard.
- A **design decision** (`DD-{MODULE}-{NNN}`) is a *record* written here. It is part of the product.

The three-per-module minimum counts records, not questions. A product settles each catalogued decision once, in its specification's frontmatter; the build then writes one `DD-` record naming the `DEC-` id for each module that raises it, and it is those records which count. Where the designer writes a `Decision:` block whose `Settles` field names the catalogued decision, the build uses that block, with its rationale, as the record for the block's module instead of generating one. A module that raises three catalogued decisions therefore meets its minimum, but through three records rather than by pointing at three rows of a table it did not write.

Two rules follow, and both are checkable:

1. **`source_module` names a module registered in `ModuleRegistry` for this product.** A value naming anything else, a pattern, a layer, a concern, resolves to no module, so the record counts toward nothing and the shortfall is reported against a module that looks compliant. Access-layer and other pattern decisions are recorded against the module whose behaviour they govern.
2. **A decision affecting several modules is recorded once per module**, each with the rationale that applies to *that* module. A single blended record under one `source_module` under-counts every other module it governs, and loses the per-module reasoning that made it worth recording. Where the reasoning is genuinely identical, say so; where it differs, as the temporal choice does between design memory and a feature store, the difference is the substance.

---

## 6. Privacy and Scoping

Every **runtime** record carries a privacy scope, both a `scope_level` (`USER`/`TEAM`/`ORGANIZATION`/`AGENT`) and a `scope_identifier`, with no exceptions (`INV-MEMORY-003`). Retrieval always filters on scope, so a user sees only their own records, a team its shared records, and so on.

**The filter lives in the access surface, not in the consumer.** Carrying a scope and enforcing one are different things, and a scope enforced only by whatever queries the table is not enforced. The consumer grant reaches a view that applies the scope predicate; the runtime base tables are not part of the consumer surface. This matters most where both facets share a container, because the grant that makes documentation readable is the grant that reaches session records: see the [access-layer pattern](../patterns/access-layer.md).

**Data minimisation.** Store the `user_key` (an identifier), never names, emails, or demographics: those are obtained by join-back to Domain when genuinely needed.

---

## 7. Applied Patterns

| Pattern | Contribution to Memory |
|---------|------------------------|
| `temporal-lifecycle-metadata` | Version-chains the documentation entities, so corrections supersede, never overwrite; gives every runtime entity its declared profile. |
| `object-placement` | Where the Memory tables and views are placed, what they are called, and who may reach them: all from the organisation profile, never from the design. |
| `access-layer` | Standard views over sessions, interactions, current decisions, active recipes, etc. |
| `validation` | The conformance checks run before the module is declared done. |

---

## 8. Capabilities and Composition

Memory is **cross-cutting and soft**: nothing hard-depends on it, and it hard-depends on nothing, so it composes with any product and either facet can be deployed alone. See the [composition mechanism](../core/DESIGN_LANGUAGE.md).

**Provides:**

| Capability | Facet | Made available to |
|------------|-------|-------------------|
| `DocumentationCapture` | `documentation` | Every module, to record its design memory. |
| `AgentContinuity` | `runtime` | Agents, across sessions and instances: prior sessions, interactions, learned strategies, and preferences. |

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `RichMetadata` | `[hard]` | `self` / `platform` | Agent-readable metadata on every object and attribute. |
| `DocumentationCapture` | `[soft]` | `self` (`documentation` facet) | Memory records its own design decisions. |
| `SemanticRegistration` | `[soft]` | `module:Semantic` | Register Memory's entities in the Semantic map when present (`INV-MASTER-002`). |
| `EntityJoinBack` | `[soft]` | `module:Domain` | Resolve a referenced entity to Domain entity context when needed. |
| `QualityScore` | `[soft]` | `module:Observability` | Learn strategies from observed outcomes and quality evidence when Observability is present. |
| `NearestNeighbors` | `[soft]` | `module:Search` | Find similar past sessions when Search is present. |

---

## 9. Integration with Other Modules

- **Observability → Memory**. Memory learns strategies from observed outcomes (which query patterns performed well). Soft: absent Observability simply means no outcome-driven learning.
- **Memory + Search**: find similar historical sessions via Search's `NearestNeighbors`. Soft.
- **Memory + Semantic**: apply learned rules alongside Semantic's business rules; register Memory's own entities in the Semantic map. Soft.
- **Memory + Domain**: entity-level references resolve to Domain entity context by join-back when needed. Memory never copies Domain content.

---

## 10. Invariants

- `INV-MEMORY-001`: Memory references entities at the entity level, by logical name (`<product_code>.<Entity>`) resolved to physical objects through Semantic; it never stores a physical name, nor individual instance keys/ids from query results.
- `INV-MEMORY-002`: Memory stores process metadata (query text, patterns, outcomes, counts), never result data or business content; content is obtained by join-back to Domain.
- `INV-MEMORY-003`: every runtime record carries a privacy scope (`scope_level` and `scope_identifier`).
- `INV-MEMORY-004`: documentation records *why/how/what-changed*; they never duplicate Semantic's *what-exists/how-connects* metadata.
- `INV-MEMORY-005`: documentation records are temporally versioned; corrections supersede prior versions rather than overwriting them.
- `INV-MEMORY-006`: *when the documentation facet is present*, every deployed module records its documentation here per the capture protocol (the provider side of `INV-MASTER-002`).

---

## 11. Designer Responsibilities

**Designers supply:**

| Element | Recorded as | Example |
|---------|-------------|---------|
| Facets enabled | The specification's frontmatter `facets` | `memory:documentation` only (Data Asset), or with `memory:runtime` (AI-native) |
| Agent types | Prose in the specification; not a build fact | analytics agent, customer-service agent |
| Session patterns | Prose in the specification; not a build fact | query session, analysis session |
| Learning categories | Fixed by this standard: `strategy_category` is `QUERY_OPTIMIZATION`, `FEATURE_SELECTION` or `ERROR_HANDLING`. Which of them a product's agents learn is prose. | query optimisation and error handling |
| Privacy scoping | The `Runtime:` block's `Scope levels` | `USER, TEAM` |
| Session timeout | The `Runtime:` block's `Session timeout` | `2 hours` |
| Retention policies | The `Retention:` block, one line per runtime entity | `AgentSession: 90 days`, `AgentInteraction: 12 months`, `LearnedStrategy: 2 years` |

Retention applies to the runtime facet only. The documentation facet is retained for the life of the product and takes no `Retention:` line. Runtime entities hold records about people, so their retention is bounded by the organisation profile's `Personal data maximum`, and a line outside it fails the build.

**Design review checklist:**

- [ ] Every attribute uses a logical type; no platform types leak into this document.
- [ ] Every runtime record carries a privacy scope (`INV-MEMORY-003`).
- [ ] Entity references are logical names at entity level only; no physical names and no instance keys stored (`INV-MEMORY-001`, `INV-MEMORY-002`).
- [ ] Every entity header declares its `profile`; entities updated in place or carrying lifecycle flags are not `EVENT_APPEND_ONLY`.
- [ ] Documentation records do not duplicate Semantic metadata (`INV-MEMORY-004`).
- [ ] Documentation is temporally versioned; corrections supersede, never overwrite (`INV-MEMORY-005`).
- [ ] With the runtime facet, the `Runtime:` block states the session timeout and the `Retention:` block has a line per runtime entity, within the organisation profile's `Personal data maximum`. The reasoning for retaining user-scoped data is recorded as a design decision: retention of user data is a governance choice with compliance consequences, not an operational detail, so it belongs where a reviewer can find the reasoning.
- [ ] The capture protocol is available to every module when the documentation facet is present.
- [ ] Every module's `DD-` records reach the three-per-module minimum, and every `source_module` resolves to a registered module (the capture protocol).
- [ ] Memory's own entities registered in the Semantic map when Semantic is present (`SemanticRegistration`).
- [ ] Every invariant has a check in the implementation.
- [ ] This document passes the design linter with no ignore directive.

---

### 11.1 Decisions to settle

These are the catalogued decisions a Memory module design must settle. The recommendation is this standard's default; the question is what shifts it. The design skill walks a designer through each one at design time and records the answer in the product's own design.


| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-TEMPORAL-PATTERN` | `bi-temporal` | This is one product-wide choice, settled for the product's History entities. Memory's documentation entities declare `[profile: SCD2_HISTORY]` on their own definitions, which History allows under either option: design memory is superseded by a later version rather than corrected retrospectively, so there is no transaction-time question to answer. A product that must reconstruct what it recorded as of a past instant declares the entity itself with `SCD2_BITEMPORAL`, which replaces the standard's. |
| `DEC-DELETE-STRATEGY` | `soft-delete` | Is a withdrawn decision or retired glossary term still evidence? |
| `DEC-TIMESTAMP-ZONE` | `zone-aware` | Do agent sessions span regions? |

---

## 12. Implementation

Each platform binding provides the runtime and documentation tables, the standard views, the capture-protocol templates, and the invariant checks, in `implementation/{platform}/modules/memory/`, and conforms to the [Platform Implementation Authoring Standard](../core/IMPLEMENTATION_AUTHORING.md). Adding a platform changes nothing in this document.

---

**End of Memory Module Design Standard**
