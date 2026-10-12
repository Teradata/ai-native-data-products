---
title: Design Specification Standard
anchor: design-specification
type: core
status: draft
version: 1.0
normative: true
---

# Design Specification Standard

## 1. Purpose

A **design specification** is the design agent's output and the product-specific input to a build. This document defines what it must contain and the notation it is written in, so that one specification builds the same product on every conforming platform, under any organisation's configuration ([Platform Implementation Authoring Standard](IMPLEMENTATION_AUTHORING.md) §2).

Two rules govern everything below.

1. **Every fact a build consumes is structured.** It appears in the frontmatter or in a notation block defined here. Prose explains and justifies; a build never reads it. A fact that exists only in prose is, for a builder, absent.
2. **Nothing physical, nothing organisational.** A specification names no platform, container, principal, physical object or physical type, and contains no SQL. Placement, physical names and principals come from the organisation profile; physical realisation comes from the platform binding.

The [Design Language](DESIGN_LANGUAGE.md) remains the authority for logical types and the entity notation; this document extends that notation for product specifications. The specification linter, `tooling/evals/spec_lint.py`, reads the tables in this document and checks a specification against them, so a table here is the rule, not a description of it.

## 2. Field types

Every field below has a type from this list.

| Type | A valid value |
|---|---|
| `text` | Any text. |
| `terms` | Comma-separated business terms. |
| `integer` | A whole number. |
| `number` | A decimal number. |
| `enum` | One of the backticked values listed in the field's Value cell. |
| `module` | A module or pattern anchor. |
| `entity` | An entity declared in the specification or defined by an included module's standard. |
| `entities` | Comma-separated entities. |
| `reference` | An attribute reference, `Entity.attribute`, that resolves. |
| `expression` | A row expression in the vocabulary of section 5. |
| `condition` | A row expression yielding true or false. |
| `aggregate` | An expression whose outermost function is an aggregate. |
| `refresh` | One or more of `on load`, `on demand`, `hourly`, `daily`, `weekly`, `monthly`, comma-separated. |
| `duration` | A count and a unit: `hours`, `days`, `weeks`, `months` or `years`. |
| `growth` | A count followed by `per day`, `per month` or `per year`. |
| `retention` | A duration, optionally followed by `after <event>`; `life of product`; `indefinite`; or two tiers, `<retention> queryable, <retention> archived`. |
| `weights` | Indented lines `<dimension>: <percent>`, summing to 100. |
| `rules` | Indented lines `- <check>: <thresholds>` (section 4.7). |
| `flows` | Indented lines `- <source> -> <job> -> <entity>`. |

## 3. Frontmatter and entities

### 3.1 Frontmatter

| Key | Required | Type | Value |
|---|---|---|---|
| `product` | yes | text | The product's display name. |
| `product_code` | yes | text | Identifier-safe product code: starts with a letter; letters, digits and underscores only. The organisation profile derives physical names from it. |
| `composition` | yes | text | A composition named in the [Master Design](MASTER_DESIGN.md). |
| `modules` | yes | text | The modules included, as a list. |
| `facets` | no | text | Enabled facets, as a list of `module:facet`. |
| `decisions` | no | text | Each catalogued decision as `id`, `choice`, and `because` when the choice is not the advocated option. |

A specification must not carry a `platform` key: the target platform is chosen at build time.

### 3.2 Entity header qualifiers

Entities are declared in the Design Language entity notation, with these header qualifiers after `[kind: ...]`.

| Qualifier | Required | Type | Value |
|---|---|---|---|
| `profile` | yes | text | A temporal profile defined by the [temporal-lifecycle-metadata pattern](../patterns/temporal-lifecycle-metadata.md). |
| `allocation` | no | enum | `keymap`, `external-allocator`, `inline` or `natural-key`: the options of `DEC-SURROGATE-ALLOCATION`. Defaults to the product's choice. |
| `allocates` | no | entity | On a `Keymap` entity: the entity whose surrogate it allocates. Required on every keymap. |
| `module` | no | module | The module the entity belongs to, which decides where it is placed. Defaults to the module whose standard defines an entity of that name, otherwise `domain`. Must be included in the composition. |

A profile outside the defaults the temporal pattern gives the entity's kind, or an allocation other than the product's choice, is a departure and must be covered by a `Decision:` block whose `Applies to` names the entity.

### 3.3 Identity

Every versioned entity has one stable identity, declared in its `Keys:` section, and its shape follows its allocation:

| Allocation | `Keys:` | The entity carries |
|---|---|---|
| `keymap`, `external-allocator` | `surrogate:` | The `Identifier` only. The `NaturalKey` is declared once, on the keymap that `[allocates:]` the entity, or held by the organisation's allocator. |
| `inline` | `surrogate:` and `natural:` | Both. |
| `natural-key` | `natural:` | The `NaturalKey` only. |

Keeping the natural key on the keymap alone means a natural key that is personal data is held, and protected, in one place; `NaturalKeyLookup` resolves through the keymap. A natural key carried on a keymap-allocated entity as well is a departure and needs a covering `Decision:`.

An entity with no business identifier of its own (an embedding, a feature row, a prediction, a relationship) declares `natural:` as the comma-separated attributes that identify one versioned thing, usually its references and discriminators, and allocates `inline`. Versioning is keyed on this identity: the surrogate where one is allocated, otherwise the declared natural key.

### 3.4 Attribute qualifiers

| Qualifier | Meaning |
|---|---|
| `[-> A \| B]` | A reference whose target is one of several entities. Requires `[discriminator: <attribute>]`. |
| `[discriminator: <attribute>]` | Names the `Enum` attribute recording which target a reference points at. Its members are the target entity names in upper case. |
| `[derive: <expression>]` | The attribute is computed, in the expression vocabulary of section 5. |
| `[synonyms: <term>, <term>]` | Business terms consumers use for this attribute. |
| `[pii-incidental]` | Free text that may contain personal data although it is not designed to. Recorded as a risk; the organisation profile decides any protection. |

Every reference target must resolve to an entity declared in the specification or defined by an included module's standard. A `Timestamp` attribute is named `<event>_dts`, and no attribute takes a name the temporal pattern prohibits.

### 3.5 Entity sections

`Synonyms:` is a single line of terms. `Volume:` and `Features:` hold indented fields.

| Section | Required on |
|---|---|
| `Volume` | every entity of kind `History`, `Reference` or `Relationship` |
| `Features` | every feature group: an entity a `Model:` reads |
| `Synonyms` | none |

#### `Volume:`

| Field | Required | Type | Value |
|---|---|---|---|
| `initial` | yes | integer | Rows at first load. |
| `growth` | yes | growth | Expected growth. |
| `horizon` | yes | duration | The period the design is sized for. |

#### `Features:`

A feature group declares at least one attribute with `[derive:]`; every derived attribute is a feature.

| Field | Required | Type | Value |
|---|---|---|---|
| `subject` | yes | entity | The entity featurised. |
| `as of` | yes | reference | The point-in-time anchor every feature is computed as at. |
| `storage` | yes | enum | `wide` or `tall`. |
| `refresh` | yes | refresh | When features are recomputed. |

## 4. Blocks

Each block is a fenced code block opening with `<Block>: <name>`, like an `Entity:` block. Fields are written `Field: value`, indented two spaces, one per line; a field of type `weights`, `rules` or `flows` puts its lines below it, indented four. A block whose name is `-` takes no name.

### 4.1 Module requirements

| Module | Required blocks |
|---|---|
| `domain` | - |
| `search` | `Embedding` |
| `prediction` | `Model` |
| `semantic` | `Orientation` |
| `observability` | `Quality`, `Lineage`, `Retention` |
| `memory` | - |

Every specification also requires a `Product` block. A product with the `memory:runtime` facet also requires a `Runtime` block and a `Retention` block, a product with the `memory:documentation` facet also requires a `Glossary` block, and a product with the `observability:graph-lineage` facet also requires a `Graph` block.

#### Standard-owned relations

Relations a build creates for an included module without the specification declaring them, placed and named through the organisation profile. A specification entity of the same name replaces the standard's.

| Owner | Relations |
|---|---|
| `domain` | `none`: the specification declares every Domain entity. |
| `search` | `none`: the specification declares its embedding entities. |
| `prediction` | `none`: the specification declares its feature groups and prediction entities; `FeatureValue` is created when a feature group declares `storage: tall`. |
| `semantic` | `all` the module's entities. |
| `observability` | `all` the module's entities; the validation pattern's `ValidationRun` and `ValidationArea`; and the discovery views `LineageGraph` and `LineageRunLatest`. |
| `memory` | `by facet`: the entities of each enabled facet. |

### 4.2 `Embedding:`

One per embedded source. The block name becomes the embedding's `source_attribute`.

| Field | Required | Type | Value |
|---|---|---|---|
| `Entity` | yes | entity | The entity embedded. |
| `Source` | yes | expression | The text to embed. |
| `Where` | no | condition | Rows failing it have no embedding. |
| `Dimensions` | yes | integer | Must match the embedding entity's `Vector[dim]`. |
| `Model` | no | text | The embedding model, by its published name. |
| `Similarity` | yes | enum | `cosine`, `euclidean`, `dot` or `manhattan`. |
| `Index` | yes | enum | `exact` or `approximate`. Which approximate algorithm is used is the binding's choice. |
| `Threshold` | no | number | Similarity at or above which two items count as similar. |
| `Refresh` | yes | refresh | When embeddings are recomputed. |

### 4.3 `Model:`

| Field | Required | Type | Value |
|---|---|---|---|
| `Subject` | yes | entity | The entity scored. |
| `Features` | yes | entity | The feature group the model reads. |
| `Target` | yes | text | What the model predicts, in business terms. |
| `Output` | yes | enum | `probability`, `class`, `value` or `structured`. |
| `Scoring` | yes | refresh | When scores are produced. |

### 4.4 `Metric:`

The block name is the metric's business name.

| Field | Required | Type | Value |
|---|---|---|---|
| `Description` | yes | text | What the metric measures and excludes. |
| `Dataset` | yes | entity | The primary entity. |
| `Joins` | no | entities | Further entities the measure reads. |
| `Measure` | yes | aggregate | The calculation. |
| `Filter` | no | condition | Applied before aggregation. |
| `Grain` | yes | entities | The level the metric is defined at. |
| `Unit` | no | text | Currency, percent, count, hours, and so on. |
| `Additive` | yes | enum | `yes` or `no`. |
| `Synonyms` | no | terms | Business terms for the metric. |

### 4.5 `AccessObject:`

A consumable object that is not simply the current view of one entity. Single-entity views are registered without a block.

| Field | Required | Type | Value |
|---|---|---|---|
| `Kind` | yes | enum | `composite`. |
| `Anchor` | yes | entity | The anchor entity. |
| `Members` | yes | entities | The other member entities. |
| `Purpose` | yes | text | What a consumer uses it for. |

### 4.6 `Orientation:`

Named `-`.

| Field | Required | Type | Value |
|---|---|---|---|
| `Entrypoint` | yes | enum | `access-layer` or `semantic`: the logical surface agents query first. |
| `Access mode` | yes | enum | `VIEW`, `MCP_TOOL` or `SEMANTIC_QUERY`. |

### 4.7 `Quality:`

Named `-`. A rule's check is a quality function from section 5; its thresholds are `pass >= <n>, warn >= <n>` for a share, `warn after <duration>, fail after <duration>` for `freshness`, or `fail on any` for a count. Weight dimensions are `completeness`, `validity`, `consistency`, `accuracy` and `timeliness`.

| Field | Required | Type | Value |
|---|---|---|---|
| `Weights` | yes | weights | How the dimensions combine into a score. |
| `Rules` | yes | rules | The checks and their thresholds. |
| `Frequency` | yes | refresh | When validation runs. |
| `Maximum evidence age` | no | duration | How old the latest validation run may be before consumers treat the trust map as stale. |

Each check counts toward one dimension: `completeness` to completeness, `validity` and `uniqueness` to validity, `consistency` and `integrity` to consistency, and `freshness` to timeliness. Accuracy, agreement with the source, is assessed by reconciliation outside these rules, and its weight applies to that evidence. A rule's thresholds map onto the [validation pattern](../patterns/validation.md)'s check outcomes: a value meeting `pass` passes, one meeting only `warn` warns, and anything else, or any count under `fail on any`, fails.

### 4.8 `Lineage:`

Named `-`.

| Field | Required | Type | Value |
|---|---|---|---|
| `Flows` | yes | flows | Declared flows. Sources and jobs are identifiers; targets are entities. |
| `Scope` | no | text | What this cycle's lineage covers. |

### 4.9 `Retention:`

Named `-`. Each field is an entity of an included module, and its value is that entity's retention. Audit and execution records must satisfy the product's `DEC-AUDIT-RETENTION` choice: `regulatory` takes the two-tier form; `bounded` a single duration. Every entity holding records about people (Memory's runtime entities among them) must fall within the organisation profile's personal-data bound.

| Field | Required | Type | Value |
|---|---|---|---|
| `*` | yes | retention | One line per entity with a retention policy. |

### 4.10 `Runtime:`

Named `-`.

| Field | Required | Type | Value |
|---|---|---|---|
| `Session timeout` | yes | duration | Inactivity after which a session is abandoned. |
| `Scope levels` | no | terms | The privacy scope levels in use, from Memory's scope vocabulary. Defaults to all of them. |

### 4.11 `Decision:`

A product design decision, recorded once here and captured into Memory's `DesignDecision` at build. The block name is the decision id, `DD-<MODULE>-<NNN>`.

| Field | Required | Type | Value |
|---|---|---|---|
| `Title` | yes | text | One line. |
| `Category` | yes | enum | `ARCHITECTURE`, `SCHEMA`, `NAMING`, `PERFORMANCE`, `SECURITY`, `INTEGRATION` or `OPERATIONAL`, as Memory's `DesignDecision` defines them. |
| `Module` | yes | module | The module or pattern the decision belongs to. |
| `Applies to` | no | text | The entity or block the decision concerns. |
| `Settles` | no | text | The catalogued decision this record settles for its module, when it records one. |
| `Context` | yes | text | What prompted it. |
| `Rationale` | yes | text | Why this choice. |
| `Alternatives` | no | text | What else was considered. |

The build captures every `Decision:` block, and one record per catalogued decision per module that raises it, into Memory's `DesignDecision`.

### 4.12 `Product:`

Named `-`. Who owns the product and what it is, for the registry, the catalogue and the manifest. Version and lifecycle status are the build's, not the design's.

| Field | Required | Type | Value |
|---|---|---|---|
| `Description` | yes | text | What the product is for, in one or two sentences. |
| `Domain` | yes | text | The business domain it serves. |
| `Owner` | yes | text | The accountable owner, by role or team. |
| `Technical contact` | no | text | The engineering contact, by role or team. |
| `Catalogue contact` | no | enum | `owner` or `technical`: the contact a catalogue that accepts only one should show. Defaults to `owner`. |
| `Trust producer` | yes | text | The single producer whose trust map is authoritative for the product. |
| `Assumed zone` | no | text | The zone timestamps are assumed to be in, as an IANA zone name. Required when `DEC-TIMESTAMP-ZONE` is `zone-naive`. |

### 4.13 `Glossary:`

One per business term the product introduces. The block name is the term.

| Field | Required | Type | Value |
|---|---|---|---|
| `Definition` | yes | text | What the term means in this product. |
| `Module` | yes | module | The module the term belongs to. |
| `Related` | no | entities | Entities the term describes. |

The Memory module's capture floor counts these terms per module. Query cookbook recipes are generated by the binding from the specification's metrics, access objects and relationships, in the platform's own dialect; a specification never holds query text.

### 4.14 `Graph:`

Named `-`. Present when the `observability:graph-lineage` facet is enabled.

| Field | Required | Type | Value |
|---|---|---|---|
| `Session nodes` | yes | enum | `omit` or `include`: the `DEC-GRAPH-SESSION-NODES` choice. |
| `Load cadence` | yes | enum | `with-lineage` or `scheduled`: the `DEC-GRAPH-LOAD-CADENCE` choice. |
| `Schedule` | no | refresh | When the graph reloads. Required when `Load cadence` is `scheduled`. |
| `Because` | no | text | The reason, required when either choice is not the advocated option. |

The graph key is not a design fact: the organisation profile's naming rules derive it from the product code.

## 5. Expression vocabulary

Expressions are platform-neutral. Each binding maps every function below to its own dialect, and the linter rejects any function not listed. An expression is built from attribute references (`Entity.attribute`), literals (numbers, `'text'`, `true`, `false`, `null`, durations such as `24 hours`), map literals (`{key: value, ...}`, where a key is a bare word or `'text'`), arithmetic (`+ - * /`), comparisons (`= <> < <= > >=`), `and`, `or`, `not`, parentheses, and these functions. In a feature derivation, an attribute of an entity other than the subject is reached through the subject's single reference to that entity and read as it currently stands; `as_of` reads it as at an instant instead.

| Function | Class | Arguments | Result |
|---|---|---|---|
| `map` | row | value, `{key: result, ...}` | The result for the matching key; `null` when none matches. |
| `when` | row | condition, value, otherwise | `value` when the condition holds, else `otherwise`. |
| `coalesce` | row | value, value, ... | The first non-null value. |
| `concat` | row | text, text, ... | Texts joined with a single space; null parts skipped. |
| `length` | row | text | Character count. |
| `hours_between` | row | earlier, later | Elapsed hours as a decimal; `null` if either is null. |
| `days_between` | row | earlier, later | Elapsed days as a decimal; `null` if either is null. |
| `hour_of_day` | row | timestamp | 0 to 23, in UTC. |
| `day_of_week` | row | timestamp | 0 (Monday) to 6 (Sunday), in UTC. |
| `as_flag` | row | condition | A `Flag`. |
| `is_null` | row | value | True when the value is absent. |
| `is_not_null` | row | value | True when the value is present. |
| `as_of` | row | attribute reference, instant | The attribute's value as at the instant, reached through the subject's single reference to that entity. |
| `count_related` | row | entity, event time, window | Rows of the entity that reference the feature subject, with event time in the window before the `as of` anchor. |
| `sum_related` | row | attribute reference, event time, window | Sum of the attribute over those rows. |
| `days_since_last` | row | entity, event time | Days from the latest such row's event time to the `as of` anchor; `null` when there is none. |
| `sum` | aggregate | value | Sum. |
| `avg` | aggregate | value | Arithmetic mean. |
| `min` | aggregate | value | Minimum. |
| `max` | aggregate | value | Maximum. |
| `count` | aggregate | value | Count of non-null values. |
| `count_distinct` | aggregate | value | Count of distinct non-null values. |
| `count_rows` | aggregate | entity | Count of rows. |
| `ratio` | aggregate | numerator, denominator | Numerator over denominator; `null` when the denominator is zero. |
| `metric` | aggregate | `'Metric Name'` | Another declared metric's value, for derived metrics. |
| `completeness` | quality | attribute, optional condition | Share of rows, meeting the condition, where the attribute is present. |
| `validity` | quality | condition | Share of rows meeting the condition. |
| `consistency` | quality | condition | Share of rows where related attributes agree. |
| `integrity` | quality | reference attribute | Count of references with no target. |
| `uniqueness` | quality | attribute | Count of duplicated values among current rows. |
| `freshness` | quality | entity | Age of the newest row. |

## 6. What the linter checks

`spec_lint` reports, in addition to its composition, decision and invariant checks:

- frontmatter keys outside section 3.1, a missing or malformed `product_code`, and any `platform` key;
- a platform named anywhere in the specification: any directory under `implementation/`, or one of Teradata, Snowflake, Databricks, BigQuery, Redshift, Synapse, Oracle, SQL Server, Postgres or DuckDB;
- an entity without a valid `profile`, an invalid `allocation`, or a departure from either default with no covering `Decision:`;
- a reference whose target does not resolve, or a multi-target reference without a discriminator;
- a missing entity section, a feature group with no derived attribute, or a section field missing, unknown or invalid for its type;
- a block missing a required field, carrying a field outside its table, or holding a value invalid for its type;
- a module in the composition without its required blocks;
- an expression using a function outside section 5, of the wrong class for its field, or naming an attribute or metric that does not resolve;
- an identity whose shape does not match its allocation, a keymap that allocates for no entity or for one already served, or a keymap-allocated entity with no keymap;
- a `Timestamp` attribute not named `<event>_dts`, or a name the temporal pattern prohibits;
- an entity in the wrong module: a feature group outside `prediction`, or an entity holding a `Vector` outside `search`.
