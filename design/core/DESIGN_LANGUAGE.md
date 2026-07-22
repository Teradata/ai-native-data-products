<!-- design-lint: ignore-file (meta document: necessarily names SQL keywords and shows platform bindings to define the boundary) -->

# Design Language

## AI-Native Data Product Architecture — Foundational Notation

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Core (Foundational Notation) |
| **Scope** | All `design/` documents — modules and patterns |
| **Audience** | Designers authoring design standards; builders binding them to a platform; the validation linter |

---

## 1. Purpose

This document defines the **notation and vocabulary** used by every document under `design/`. It exists so that design standards can describe **what** a module or pattern must be and **why**, without committing to **how** any one platform implements it.

`design/` is platform-agnostic. `implementation/{platform}/` is platform-specific. This document is the contract between the two: it defines the logical vocabulary that design documents write in, and that each platform implementation binds to concrete syntax.

The three building blocks are:

1. **Logical types** — a fixed vocabulary of attribute types with platform-neutral *semantics* (Section 4).
2. **Capability contracts** — named *operations* a design requires, which each platform binds to its own mechanism (Section 6).
3. **Invariants** — testable, platform-neutral *rules* a conforming implementation must satisfy (Section 7).

Design documents are written as **interface specifications** — they declare what an implementation must provide. Implementation documents are **conforming implementations** — they provide it. This mirrors the style already established by the pattern specs (`object-placement`, `physical-storage`).

---

## 2. The Design / Implementation Boundary

Every sentence in a design document must pass one test:

> **Would this sentence change if the target platform changed from Teradata to Postgres to DuckDB?**
>
> - **No** — it stays true on every platform → it belongs in `design/`.
> - **Yes** — it changes with the platform → it belongs in `implementation/{platform}/`.

The one-line rule: **semantics stay, syntax moves.**

| Belongs in `design/` (semantics) | Belongs in `implementation/` (syntax) |
|---|---|
| "Store the entity reference only; join back to Domain for content." | The concrete `INNER JOIN ... ON ...` query. |
| "Cosine is the default distance metric for text embeddings." | The `TD_VectorDistance(...)` call, or pgvector's `<=>` operator. |
| "Every attribute carries descriptive metadata." | `COMMENT ON COLUMN ...`. |
| "A surrogate key is stable across all versions of an entity." | `BIGINT` + keymap DDL, or `GENERATED ALWAYS AS IDENTITY`. |
| "The current version is retrievable by a single predictable filter." | `WHERE is_current = 1 AND is_deleted = 0`. |

### 2.1 The enforceable inclusion test

The boundary is enforced automatically: **a `design/` document must contain no platform SQL.** This is checked by the validation linter (`tooling/validation`) and defined precisely in Section 8. If a design document needs to show SQL to make its point, that SQL belongs in the matching implementation document instead.

---

## 3. Document Types

| Layer | Path | Written as | Contains |
|---|---|---|---|
| **Core** | `design/core/` | Foundational reference | This notation, the glossary, advocated standards, the master design. |
| **Module** | `design/modules/<name>.md` | Interface spec | Logical entity model + capabilities + invariants for one module. |
| **Pattern** | `design/patterns/<name>.md` | Interface spec | A cross-cutting concern that requires a platform binding (temporal lifecycle, object placement, physical storage, validation, access layer). |
| **Implementation** | `implementation/<platform>/{modules,patterns}/<name>/` | Conforming implementation | The concrete DDL, queries, and bindings that satisfy the matching design document. |

**Anchor-name parity is required.** `design/modules/search.md` is implemented by `implementation/teradata/modules/search/`. A reviewer must be able to diff a design document against its binding one-to-one by name.

**Patterns are referenced, not re-encoded.** When a module depends on a cross-cutting concern (temporal columns, object placement), it *references the pattern* (Section 5) rather than restating it. Re-stating a pattern inline in every module is the duplication this structure exists to remove.

---

## 4. Logical Type Vocabulary

Design documents describe attributes using these logical types only. Each has fixed semantics here; each platform declares its concrete binding in `implementation/{platform}/patterns/type-bindings/` (or its equivalent). Design documents never write a platform data type.

| Logical type | Semantics | Notes |
|---|---|---|
| `Identifier` | System-generated surrogate key. Unique, stable, never reused, never recycled. | For entities that are reference targets, allocated via the **surrogate-key-allocation** pattern so the value is stable across all versions — not by inline auto-increment. |
| `NaturalKey` | Business identifier sourced from an originating system. User- and report-facing. | Distinct from `Identifier`: `NaturalKey` comes from the source; `Identifier` is assigned internally. |
| `Reference -> <Entity>` | A pointer to another entity instance. | Names its target. Carries no content of the target — content is obtained by joining back (see `EntityJoinBack` capability). |
| `Code` | A short controlled-vocabulary value drawn from a reference set. | e.g. a type or status code. Backed by a Reference entity. |
| `ShortText` | Bounded human-readable string, short (names, labels). | Bound length is an implementation choice. |
| `Text` | Bounded human-readable string, medium (descriptions, notes). | |
| `LongText` | Large human-readable string (documents, content bodies). | |
| `Json` | A structured document value with a nested or flexible schema, stored whole and processed by the consumer rather than decomposed into columns. | Use for genuinely variable or nested context; never to avoid modelling stable attributes that deserve their own logical types. |
| `Enum{A\|B\|C}` | A value from a small closed set fixed at design time. | Lists its members inline. Use `Code` instead when the set is data-driven or governed as reference data. |
| `Integer` | Whole number (counts, ordinals, dimensions). | |
| `Decimal(p,s)` | Exact fixed-point number (money, rates). | Precision/scale are semantic and stay in design. |
| `Timestamp` | A point in time. Time-zone-aware unless stated otherwise. | Precision is an implementation choice. |
| `Date` | A calendar date with no time component. | |
| `Flag` | A two-state indicator (yes/no, current/superseded, active/deleted). | Binds to whatever boolean-like type the platform prefers. |
| `Vector[dim]` | A dense numeric embedding of fixed dimensionality `dim`. | `dim` is semantic (tied to the embedding model) and stays in design; the storage format is an implementation choice. |

The vocabulary is intentionally small and closed. If a design genuinely needs a type not listed here, add it to this table first (with semantics), so the linter and every implementation can recognise it.

---

## 5. Entity Notation

Design documents declare structure in a keyword-free pseudo-notation. It carries logical structure — entities, attributes, keys, references, applied patterns, invariants, capabilities — and deliberately cannot express a physical table.

```
Entity: <Name>                    [kind: History | Reference | Relationship | Keymap]
  <attribute>  : <LogicalType> [qualifiers]      — <business description>
  ...

  Keys:
    surrogate: <attribute>
    natural:   <attribute>

  Applies patterns:
    - <pattern-name>
    ...

  Requires capabilities:
    - <CapabilityName>
    ...

  Invariants:
    - INV-<MODULE>-<NNN>: <testable statement>
    ...
```

**Qualifiers** (zero or more per attribute):

| Qualifier | Meaning |
|---|---|
| `[required]` | Must be present (non-null). |
| `[optional]` | May be absent. |
| `[unique]` | Unique within the entity (within the current version set, for versioned entities). |
| `[-> <Entity>]` | For a `Reference`: names the target entity. |
| `[pii]` | Carries personal or sensitive data; implementations must apply the platform's protection binding. |
| `[current-flag]` / `[deleted-flag]` | Marks the indicator used by the `CurrentStateFilter` capability. |

**Entity kinds** map to recurring shapes: `History` (a versioned business entity), `Reference` (a controlled vocabulary / lookup set), `Relationship` (an association between two entities), `Keymap` (a surrogate-key allocation table), `Record` (an append-oriented operational log or state entry, not SCD-versioned). Kinds are semantic labels, not table types.

### 5.1 Worked shape

```
Entity: Party                     [kind: History]
  party_id     : Identifier                       — surrogate, stable across all versions
  party_key    : NaturalKey [required] [unique]   — business identifier from source system
  legal_name   : ShortText [optional]             — registered legal name
  tax_id       : ShortText [optional] [pii]       — tax identifier

  Keys:
    surrogate: party_id
    natural:   party_key

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - CurrentStateFilter
    - NaturalKeyLookup
    - SurrogateKeyAllocation
    - RichMetadata

  Invariants:
    - INV-DOMAIN-001: every attribute carries descriptive metadata.
    - INV-DOMAIN-002: the current version of an entity is retrievable by a single predictable filter.
```

Notice what is *absent*: no data types, no `CREATE`, no index clause, no temporal columns. The temporal columns come from the referenced `temporal-lifecycle-metadata` pattern; the physical index comes from `object-placement` / the platform. Those live in `implementation/teradata/modules/domain/`.

---

## 6. Capability Contracts

A capability is a named **operation a design requires**, declared abstractly. The design says *what must be possible*; each platform implementation says *how*. Capabilities are where otherwise platform-specific behaviour (vector search, in-database embedding) becomes platform-neutral in design.

A design document lists the capabilities it requires. Each platform implementation provides a **binding table** mapping each capability to its concrete mechanism.

### 6.1 Standard capability catalogue

| Capability | Contract | Illustrative bindings (implementation-owned) |
|---|---|---|
| `CurrentStateFilter` | Retrieve only current, non-deleted versions of an entity via a single predictable filter. | current/deleted flag predicate. |
| `PointInTimeReconstruction` | Retrieve an entity's state as it was at a given `Timestamp`. | temporal-range predicate; snapshot / time-travel. |
| `SurrogateKeyAllocation` | Allocate an `Identifier` that is stable across all versions of the same real-world entity. | keymap table; central sequence; managed identity. |
| `NaturalKeyLookup` | Retrieve an entity by its `NaturalKey`. | indexed equality lookup. |
| `EntityJoinBack` | From a row in any module, obtain the referenced Domain entity's content. | foreign-key join to the Domain entity. |
| `RichMetadata` | Attach descriptive, agent-readable metadata to every object and attribute. | column/table comments; catalogue metadata. |
| `AccessView` | Expose a predictable, named view of current (and optionally enriched) records with an explicit column contract. | view with declared column list. |
| `MetadataCoverageCheck` | Confirm programmatically that every attribute carries metadata. | catalogue query returning uncommented columns. |
| `SemanticRegistration` | Register the module's entities, columns, and relationships in the product's Semantic map so agents can discover them. | inserts into the Semantic discovery entities. |
| `DocumentationCapture` | Record the module's design decisions, glossary terms, and change history in the product's Memory store. | inserts into the Memory documentation entities. |
| `NearestNeighbors(query, candidates, metric, k)` | Return the `k` candidates most similar to `query` under a distance `metric`, as ranked `(id, distance)`. | vector-distance function; nearest-neighbour operator. |
| `ApproxIndex{IVF\|HNSW}` | *(Optional)* Accelerate `NearestNeighbors` with an approximate index of the named family. | IVF/KMEANS index; HNSW graph index. |
| `Embed(text, model)` | Produce a `Vector[dim]` for `text` using the named embedding `model`. | in-database embedding; external embedding API. |

A capability marked *optional* (like `ApproxIndex`) may be unsatisfied on a given platform without breaking conformance — the design must not assume it is always present. This matters where platforms genuinely differ (e.g. in-database `Embed` exists on some platforms and is API-only on others): declare such capabilities optional or pluggable rather than assumed, so a "platform-agnostic" design does not quietly encode one platform's assumptions.

Capabilities not in this catalogue may be introduced by a design document, but must be defined there with the same contract shape (name, inputs, outputs, guarantee) so implementations can bind them unambiguously.

### 6.2 Provision, requirement, and composition

The framework is a **library of modules** that compose into different data design patterns — a
minimal governed data asset, a traditional data product, a full AI-native data product, or an
add-on to something that already exists. Modules must therefore function independently and in
any valid combination. This works because every module declares both sides of its capability
relationships.

A module design document declares, at module level:

- **Provides** — capabilities the module makes available to other modules or to agents (Domain
  provides `EntityJoinBack`; Search provides `NearestNeighbors`; Semantic provides
  `SemanticRegistration`; Memory provides `DocumentationCapture`).
- **Requires** — capabilities the module consumes, each tagged with a **strength** and a
  **provider**:
  - Strength — `[hard]` (the module cannot function without it; its absence makes the module
    undeployable) or `[soft]` (used when available; its absence disables the dependent feature,
    but the module still functions).
  - Provider — `self` (the module and its platform binding), `module:<Name>` (another module in
    the composition), `platform`, or `external`.

**Facets.** A module may expose named **facets** that can be enabled independently — for example
Memory's `documentation` facet (the design-memory / documentation store) versus its `runtime`
facet (agent state and learning). A capability may be provided by a facet; enabling the facet
enables the capability. A composition may include a module with only some of its facets.

**Composition.** A composition is a chosen set of modules (and facets) assembled into a data
design pattern. A composition is **valid** if and only if every `[hard]` requirement is
satisfied by a `Provides` within the composition (or by `platform`). An unmet `[soft]`
requirement never invalidates a composition — it simply disables that feature (graceful
degradation). The named standard compositions, and the modules each includes, are catalogued in
the [Master Design](MASTER_DESIGN.md#4-compositions).

---

## 7. Invariants

An invariant is a rule that every conforming implementation must satisfy, written so it can be **checked**. Invariants replace prose principles ("store IDs only") with testable statements.

**ID convention:** `INV-<MODULE>-<NNN>`, e.g. `INV-SEARCH-001`. `<MODULE>` is the uppercase module or pattern anchor name; `<NNN>` is a zero-padded sequence unique within that document.

**Writing invariants:**

- State a condition that is true or false of an implementation — not a recommendation.
- Keep it platform-neutral (it must hold on every platform).
- Prefer statements a query or a test can evaluate.

Examples:

- `INV-SEARCH-001`: an embedding record contains no attribute owned by the Domain module (keys only — no content duplication).
- `INV-SEARCH-002`: every embedding references exactly one current Domain entity.
- `INV-DOMAIN-001`: every attribute of every entity carries descriptive metadata.
- `INV-DOMAIN-002`: the current version of an entity is retrievable by a single predictable filter.

Each invariant should have a corresponding check in the module's implementation (a `MetadataCoverageCheck`-style query, a linter rule, or a unit test) so "is this implementation conforming?" becomes a green/red result rather than a judgement call.

---

## 8. The No-Platform-SQL Rule (enforceable)

A `design/` document must contain no platform SQL. The validation linter enforces this. The rule is defined to catch real entanglement while not flagging ordinary English (the words "table", "view", "date", "index" are fine in prose).

A design document **fails** the linter if any of the following appear:

1. **A SQL-tagged fenced code block.** Fenced blocks tagged ` ```sql ` (or `tsql`, `plsql`, `psql`) are prohibited outright — design shows pseudo-notation, not SQL.
2. **SQL statements inside any fenced block.** Within any code block, a line beginning with a SQL statement keyword — `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `GRANT`, `REVOKE` — is a violation. (The pseudo-notation in Section 5 uses none of these, so it passes.)
3. **Platform data types or vendor tokens, anywhere.** High-precision tokens that are never ordinary English and only ever appear in SQL: `VARCHAR`, `BIGINT`, `BYTEINT`, `SMALLINT`, `DECIMAL(`, `FLOAT32`, `TIMESTAMP(`, `PRIMARY INDEX`, `UNIQUE PRIMARY INDEX`, `GENERATED ALWAYS AS IDENTITY`, `NOT NULL`, `DEFAULT `, `COMMENT ON`, and any `TD_`-prefixed function. Use the logical types of Section 4 instead.

**Escape hatch.** A core/meta document that must legitimately name SQL (this document; the linter's own README) carries an ignore directive on its first line:

```
<!-- design-lint: ignore-file (reason) -->
```

Module and pattern documents must never use the ignore directive — they are the content the rule exists to keep clean.

The exact token lists live with the linter (`tooling/validation`) so the linter and this document stay in agreement; Section 8 is the human-readable statement of what that linter enforces.

---

## 9. Authoring Checklist

Before a design document is considered conforming:

- [ ] Every attribute uses a logical type from Section 4 (no platform types).
- [ ] Structure is expressed in the Section 5 notation (no `CREATE`/`SELECT`).
- [ ] Cross-cutting concerns are **referenced** as patterns, not restated inline.
- [ ] Every required behaviour is expressed as a capability (Section 6), not as a concrete query.
- [ ] Principles are written as testable invariants with `INV-<MODULE>-<NNN>` ids (Section 7).
- [ ] The matching `implementation/{platform}/…/<name>/` provides a binding for every capability and satisfies every invariant.
- [ ] The document passes the validation linter (Section 8) with no ignore directive.

---

## Appendix A — Illustrative Platform Bindings

This appendix is illustrative only. Authoritative bindings live in each platform's implementation. It is here to make the boundary concrete; it is why this document carries the `ignore-file` directive.

| Logical type | Teradata | Postgres | DuckDB |
|---|---|---|---|
| `Identifier` | `BIGINT` via keymap (stable across versions) | `BIGINT` + identity/keymap | `BIGINT` + sequence |
| `NaturalKey` | `VARCHAR(n)` | `VARCHAR(n)` / `TEXT` | `VARCHAR` |
| `Reference -> E` | `BIGINT` | `BIGINT` | `BIGINT` |
| `ShortText` / `Text` / `LongText` | `VARCHAR(n)` / `CLOB` | `VARCHAR(n)` / `TEXT` | `VARCHAR` |
| `Json` | `JSON` | `JSONB` | `JSON` / `STRUCT` |
| `Decimal(p,s)` | `DECIMAL(p,s)` | `NUMERIC(p,s)` | `DECIMAL(p,s)` |
| `Timestamp` | `TIMESTAMP(6) WITH TIME ZONE` | `TIMESTAMPTZ` | `TIMESTAMPTZ` |
| `Date` | `DATE` | `DATE` | `DATE` |
| `Flag` | `BYTEINT` | `BOOLEAN` | `BOOLEAN` |
| `Vector[dim]` | native `VECTOR` (`FLOAT32(dim)`) | `vector(dim)` (pgvector) | `FLOAT[dim]` (vss) |

| Capability | Teradata | Postgres | DuckDB |
|---|---|---|---|
| `NearestNeighbors` | `TD_VectorDistance` | `ORDER BY emb <=> q LIMIT k` (pgvector) | `array_cosine_similarity` / vss |
| `ApproxIndex{IVF\|HNSW}` | KMEANS / HNSW via Vector Store | `ivfflat` / `hnsw` index | vss HNSW |
| `Embed(text, model)` | in-database ONNX embedding | external API | external API |
| `CurrentStateFilter` | flag predicate | flag predicate | flag predicate |

---

**End of Design Language**
