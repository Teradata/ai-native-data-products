# PostgreSQL implementation

Reusable binding for **any conforming data product**, following the module and pattern layout of the Teradata reference. Target: PostgreSQL 16 or later; tested on 16.4 (see [CONFORMANCE.md](CONFORMANCE.md)). These are Jinja templates and binding documents, not a finished deployment or a compiler.

## How a build reads this binding

A build has three inputs: a **design specification** (the product, platform-agnostic), an **organisation profile** (placement, naming, principals and classification for one organisation on PostgreSQL) and this **binding**. [`tooling/build/build_context.py`](../../tooling/build/README.md) resolves the specification, the profile and the binding's declarations into one build context, whose shape is fixed by [`build_context.schema.json`](../../tooling/build/build_context.schema.json) ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3).

The templates read only the build context, and derive no names: every container, object, column and principal name arrives resolved. Standard-owned relations (the Semantic catalogue, the Observability and Memory stores, the validation relations and the discovery and trust-map views) are defined by the module and pattern standards under [`design/`](../../design/) and placed by the resolver. This directory carries no input contract or entity declarations of its own.

Read [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md) first. Then [`binding.toml`](binding.toml), which lists the phase files in order with the template that renders each, the deploy template, the checks, and the physical type and SQL fragment for each logical type and expression function. Then read the sections below: one per module and pattern, in deployment order, each saying what its templates emit, which build-context fields they read and where its templates are. The index gives the line each section starts on.

<!-- index:start -->
| Line | Section | Covers |
|---:|---|---|
| 32 | [Render, deploy and validate](#render-deploy-and-validate) | Rendering the worked example, deploying it, running the validator; what the renderer writes |
| 54 | [Verification](#verification) | The test and lint commands for this binding |
| 66 | [1. Object Placement pattern (`object-placement`)](#1-object-placement-pattern-object-placement) | Schemas and the `btree_gist` extension |
| 84 | [2. Temporal Lifecycle Metadata pattern (`temporal-lifecycle-metadata`)](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata) | Shared macros, comments, consumer views, point-in-time functions, caller-rendered maintenance |
| 127 | [3. Memory module (`memory`)](#3-memory-module-memory) | Tables; design-memory capture |
| 172 | [4. Semantic module (`semantic`)](#4-semantic-module-semantic) | Tables; registration; discovery views; the metadata-contract checks |
| 231 | [5. Domain module (`domain`)](#5-domain-module-domain) | Tables; key allocation |
| 275 | [6. Observability module (`observability`)](#6-observability-module-observability) | Tables |
| 312 | [7. Search module (`search`)](#7-search-module-search) | Tables; similarity functions |
| 353 | [8. Prediction module (`prediction`)](#8-prediction-module-prediction) | Tables |
| 385 | [9. Validation pattern (`validation`)](#9-validation-pattern-validation) | Metadata, temporal, reference and comment-coverage checks; the trust-map view |
| 427 | [10. Access Layer pattern (`access-layer`)](#10-access-layer-pattern-access-layer) | Roles, grants and row-level security |
| 456 | [11. Physical Storage pattern (`physical-storage`)](#11-physical-storage-pattern-physical-storage) | None: object storage is not rendered |
| 466 | [Catalogue](#catalogue) | The binding's design documents (generated) |
<!-- index:end -->

## Render, deploy and validate

The worked inputs are the [IT Service Desk specification](../../examples/it-service-desk-data-product/design-output/design_specification.md) under the `postgres` target of the [example configuration](../../config/implementation.example.toml). The [customer-orders reference](../../tooling/evals/reference/customer-orders.md) builds under the same target.

```sh
python -m pip install -r tooling/bindings/requirements.txt "psycopg[binary]"
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md config/implementation.example.toml --target postgres --output build/itsd-postgres
psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -f build/itsd-postgres/deploy.sql
python tooling/bindings/validate.py build/itsd-postgres/manifest.json
```

The target names the platform; `--design` names the design configuration where it is not the implementation file's sibling. `--environment PHASE` places the product for one lifecycle phase; `--version V` supplies the product version where the specification leaves it open. The output directory must be empty and outside `config/`, `design/`, `implementation/`, `examples/`, `roles/` and `tooling/`. The renderer writes:

- one SQL file per declared phase that renders something for this composition;
- `deploy.sql`, every phase in one transaction;
- `manifest.json`: the checks, each with a test id `{PRODUCT_CODE}-{CHECK}-{NNN}`, where validation evidence is placed, the gaps the binding reports and the defaults the resolver applied;
- `context.json`, the resolved build context.

Rendering does not connect to a database. Rendered SQL is not checked into this repository. Deploying needs privileges to create schemas, the `btree_gist` extension and, where the profile says `create`, the roles. The roles are `NOLOGIN`; login users and memberships are an operator step.

The validator connects through `POSTGRES_DSN`, runs each check in its own savepoint and, where the product places `ValidationRun` and `ValidationArea`, appends one run and its area records (wire schema 2.1). `--producer` publishes under a producer id other than the product's designated one. The manifest contains trusted generated SQL: never run one from an untrusted source. Gaps the manifest reports, such as an expression using a function this binding has no fragment for or a composite access object, cap the PRODUCT area at `partial`.

## Verification

```sh
python -m unittest discover -s tooling/bindings/tests -v
python -m unittest discover -s tooling/validation/tests -v
python tooling/validation/design_lint.py design implementation
python tooling/catalogue/build_catalogue.py --check
python tooling/skill/verify_skill.py
```

Set `POSTGRES_TEST_DSN` to a disposable database where the test role may create schemas, roles and the `btree_gist` extension. Each PostgreSQL test runs in one transaction that is rolled back. Without the variable or the `psycopg` package the PostgreSQL engine tests skip, and a skip is a gap. See [CONFORMANCE.md](CONFORMANCE.md) for coverage and remaining gaps.

## 1. Object Placement pattern (`object-placement`)

Templates: [`patterns/object-placement/`](patterns/object-placement/).

Binding of [Object Placement](../../design/patterns/object-placement.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Template

`01-containers.sql.j2` is the first phase. It creates the `btree_gist` extension if absent, which the history tables' exclusion constraints need, then one schema for each entry in the context's `containers` that holds objects and is not adopted. Adopted containers already exist; parent containers hold no objects on this platform. Schema creation does not use `IF NOT EXISTS`, so accidental reuse fails rather than blending two products.

Every container name, and the container of every object, comes from the organisation profile through the resolver. No name is inferred from a product prefix, and the example profile is one possible placement, not a required convention.

The phase order in [`binding.toml`](binding.toml) creates containers, then Memory, Semantic, Domain, Observability, Search and Prediction tables, then comments, views and functions, registration, discovery, the trust map, documentation capture and, last, access. `deploy.sql` applies them in one transaction; deploying phase files separately must keep that order.

PostgreSQL roles are cluster-wide and are provisioned deliberately by the access-layer phase or by an operator.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 2. Temporal Lifecycle Metadata pattern (`temporal-lifecycle-metadata`)

Templates: [`patterns/temporal-lifecycle-metadata/`](patterns/temporal-lifecycle-metadata/).

Binding of [Temporal Lifecycle Metadata](../../design/patterns/temporal-lifecycle-metadata.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`00-macros.sql.j2` holds the macros every other template imports. Each takes a relation from the context (an entity or a standard-owned relation, with its `columns`, `column_names`, `key_columns`, `version_columns` and placed `objects`) and composes no name:

| Macro | Emits |
|---|---|
| `cols`, `column` | A quoted column list; one column definition with type, identity, `NOT NULL`, `UNIQUE`, Enum and vector checks |
| `primary_key`, `constraints` | The key (version columns plus interval starts for history); interval-order, current-flag and deletion-flag checks |
| `current`, `at` | The current-row predicate; the half-open point-in-time predicate on `valid_at` and, when bitemporal, `known_at` |
| `table` | `CREATE TABLE`, the keymap foreign key, and for history the partial unique index on the current row and the `btree_gist` exclusion constraint |
| `module_tables` | Every persisted, defined, non-adopted relation of one module, keymaps first |
| `value`, `ref`, `insert`, `member` | A Python value as SQL; a subquery for a current row's key; an insert by logical attribute name with open-row defaults for temporal columns; whether an Enum permits a value |

`02-comments.sql.j2` applies `COMMENT ON TABLE` and `COMMENT ON COLUMN` to every persisted relation from its `description` and each column's description (or its logical name), after the tables and before anything depends on them.

`03-access-views.sql.j2` creates, for every relation with a `consumer_view` object, a view of its current rows (the `current` macro) carrying every column except the open interval ends `valid_to_dts` and `transaction_to_dts`. Runtime relations have no consumer view. For every relation with a `function` object it creates a point-in-time function `(valid_at TIMESTAMPTZ)`, or `(valid_at, known_at)` when bitemporal, returning the table's rows at that instant; it is `SECURITY DEFINER` with `search_path` fixed to `pg_catalog, pg_temp`.

`04-maintenance.sql.j2` is caller-rendered with `entity`, `stable_key`, `effective_at`, `recorded_at` and `replacement_rows` (each keyed by physical column name). It is a transaction body: the caller controls `BEGIN` and `COMMIT` and runs the checks before committing. It takes a transaction-level advisory lock on the table and key, then:

- for a bitemporal relation, closes every open knowledge interval of the identity at `recorded_at` and clears its current flag;
- otherwise, closes the version whose validity covers `effective_at` at that instant;
- inserts every replacement row with every column, each value through the literal filter.

It is not a change planner. The caller supplies complete, non-overlapping intervals (for a bitemporal correction, the whole new known timeline), detects unchanged replay, preserves unaffected segments and tombstones, and rejects non-finite or non-monotonic correction instants.

Validity and knowledge intervals are half-open; infinity appears only as an open end. For bitemporal history, overlap is prohibited only where both axes overlap. The current flag is true exactly when every applicable end is open.

### Capability bindings

| Capability | Binding |
|---|---|
| `CurrentStateFilter` | `current` macro behind the consumer views and reference checks. |
| `PointInTimeReconstruction` | `at` macro behind the point-in-time functions. |
| `SoftDelete` | `is_deleted` and `deleted_dts` with a consistency check; deleted rows are excluded from current and point-in-time reads. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 3. Memory module (`memory`)

Templates: [`modules/memory/`](modules/memory/).

Binding of [Memory](../../design/modules/memory.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('memory')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The relations are those the Memory standard defines and the resolver places: the documentation relations (module registry, design decisions, glossary, cookbook, implementation notes, change log), versioned with consumer views and point-in-time functions, and the runtime relations the context includes, which have no consumer view.

`02-capture.sql.j2` writes the design-memory records the build context settles in `capture`, one insert per record, by logical attribute name through the `insert` macro:

- `capture.modules` into the module registry, with `product.version`;
- `capture.decisions` into design decisions, each with its settled `DD-{MODULE}-{NNN}` id, version 1 and status `ACCEPTED`;
- `capture.glossary`, `capture.notes` and `capture.change_log` into their relations;
- `capture.cookbook` into the cookbook, with each recipe's query rendered here in the PostgreSQL dialect from its `kind`: a metric's measure and filter over its dataset's consumer view (`metrics`); a call to a similarity function with `$1` and a limit of 10, joined to the entity's consumer view where the recipe asks (`embeddings`); a join of a relationship's source and target consumer views (`relationships`); a catalogue lookup of entity metadata for the named modules; otherwise the named relation's consumer view.

A record the context does not carry is not written. What capture could not settle is listed in `capture.gaps` and reported in the manifest.

`validation.sql.j2` is the `module memory` check. Every row it returns is a registered module below the capture floor: three design decisions, three glossary terms and one cookbook recipe.

### Access

The [access-layer template](#10-access-layer-pattern-access-layer) enables row-level security on each runtime relation. The agent tier may select, insert and update only rows whose `scope_level` is `USER` and whose `scope_identifier` equals `session_user`; the admin tier has an unrestricted policy. Shared scopes are not granted to the agent tier. Owners, superusers and `BYPASSRLS` principals remain privileged, and a pooled login shared by several end users cannot tell them apart.

### Capability bindings

| Capability | Binding |
|---|---|
| `DocumentationCapture` | Versioned documentation relations; `02-capture.sql.j2` writes the settled records; `validation.sql.j2` reports modules below the floor. |
| `AgentContinuity` | Runtime relations with required scope columns, no consumer view and `USER` row-level security. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-MEMORY-001,002,004` | Standard-owned structures separate process and design context; producer payload review remains necessary. |
| `INV-MEMORY-003` | Required scope columns; engine test that the agent tier cannot write a row scoped to another user. |
| `INV-MEMORY-005` | Shared versioned temporal macros and the `entity temporal` check. |
| `INV-MEMORY-006` | `module memory` check of the capture floor; the reference specifications meet it. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 4. Semantic module (`semantic`)

Templates: [`modules/semantic/`](modules/semantic/).

Binding of [Semantic](../../design/modules/semantic.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('semantic')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata) for the catalogue relations the Semantic standard defines and the resolver places.

`02-registration.sql.j2` writes the product's description of itself, each block only where its relation is placed:

- the product registry row from `product` (code, name, description, domain, version, owner, trust producer) and `orientation.access_mode`, with the manifest's consumer view as the approved entry point;
- the module map from `module_containers`, for object types the relation's vocabulary permits;
- entity and column metadata for every placed relation in `entities` and `relations`: placement, kind, profile, surrogate and natural columns, current and deleted flag columns, and per column the logical name, description, sensitivity marker, `classification`, `required`, declared type and Enum members;
- table relationships from `relationships`, by base table;
- access objects for every placed object of each relation and for each similarity function in `embeddings`, with consumer views and functions marked agent-consumable;
- primary objects for every placed object with a `primary_role`;
- the orientation sequence from `orientation.resources`;
- metrics from `metrics`, with the rendered measure and filter as a PostgreSQL expression and the dataset's consumer view;
- entity and column synonyms;
- naming standards from `naming`: each object template, the attribute template and each standard-name mapping.

Composite access objects (`access_objects`) are not registered; the manifest reports each as a gap.

`03-discovery.sql.j2` creates the standard-owned discovery views, each only where the composition places it and the relations it reads:

- `ColumnCatalogue`: `information_schema.columns` for the product's containers, left-joined to column metadata, with `description_source` `authored` or `missing`;
- `DataProductManifest`: the active registry row with one column per orientation resource role;
- `RelationshipPaths`: a recursive view over active table relationships in both directions, up to the Semantic standard's bound of four hops (the context's `max_hops`) without revisiting a table. Paths join base tables; resolve them through the access objects before issuing consumer SQL;
- `LineageGraph` and `LineageRunLatest` over Observability's active lineage definitions and their runs.

`validation.sql.j2` is the `module semantic` check: every base table in a container the product places objects in, keymaps included, is registered in entity metadata.

**The metadata contract (release 2.0.0).** Registration writes the logical identity of each entity (`module.entity`) and, beside it, its location; the key definitions and their ordered key columns; one relationship column pair per join column; one access object per placed object, identified by entity and surface; one access-column mapping row per output column of each consumer view over an entity (the context's `view_columns`, which the view itself selects); and the `StandardDeclaration` rows from `standard`. `RelationshipPaths` returns one row per path step and key position, bounded to four hops. The manifest's last column is `standard_version`. The five checks under [`contract/`](modules/semantic/contract/) test `INV-SEMANTIC-016` to `020`; they are declared as `contract` checks and read only registered metadata and the catalogue.

Registration uses the placement and relationships the context carries, never name inference. Structural facts come from `information_schema`; meanings come from the specification.

### Capability bindings

| Capability | Binding |
|---|---|
| `SemanticRegistration` | Registration inserts for the product, modules, entities, columns, relationships, access and primary objects, orientation, metrics, synonyms and naming standards. |
| `RichMetadata` | `COMMENT ON` for physical objects, plus authored entity and column metadata and the hybrid column catalogue. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEMANTIC-001,002` | Standard-owned catalogue structures; registries hold datasets, never business instances. |
| `INV-SEMANTIC-003,006` | Registration at deployment; `module semantic` check, with an engine test that an unregistered table is found. |
| `INV-SEMANTIC-004,011,012` | Manifest view over the registry and orientation sequence; consumer workflow verification remains required. |
| `INV-SEMANTIC-005,007..010` | Declared relationships and access objects; composite access objects are not rendered. |
| `INV-SEMANTIC-013..015` | Metrics and synonyms registered from the specification; metric recipes execute in engine tests. Reference checks over the registrations remain to be written. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 5. Domain module (`domain`)

Templates: [`modules/domain/`](modules/domain/).

Binding of [Domain](../../design/modules/domain.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('domain')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). It emits one `CREATE TABLE` per persisted Domain relation in the context's `entities` and `relations`, keymaps first so references to them resolve, and skips any the context marks `adopted` or not `defined`. It reads each relation's `objects.table`, `columns` (physical name and type, `required`, `unique`, `members`), `key_columns`, `version_columns`, `column_names`, `history`, `bitemporal`, `supports_deletion`, `generated_key` and `identity.keymap`.

- A relation with `generated_key` gets an identity column (`GENERATED BY DEFAULT AS IDENTITY`).
- An entity with a keymap gets a foreign key from its key columns to the keymap's table.
- An Enum attribute gets a `CHECK` over its members.
- A history table's primary key is its version columns plus `valid_from_dts` (and `transaction_from_dts` when bitemporal). It gets a partial unique index on the version columns where the row is current (one open version) and a `btree_gist` exclusion constraint over the validity interval, and the knowledge interval when bitemporal (non-overlap).

`02-key-allocation.sql.j2` is caller-rendered with `keymap` (a Keymap entity from the context) and `natural_value`. It inserts the natural value and returns the stable identifier; an existing natural value returns its existing identifier through `ON CONFLICT`. Given `staged` instead, `{container, name, column}` naming a table the caller has written a set of natural values to (`container` null for a session-local table), it allocates the whole set in one `INSERT ... SELECT ... ON CONFLICT DO NOTHING`, ignoring NULLs and duplicates and keeping every existing identifier, then returns each staged value with its identifier. Load a batch this way rather than one value at a time. Only the first natural-key attribute (`identity.natural[0]`) is used. The caller opens the transaction.

Comments, consumer views and point-in-time functions come from the temporal pattern; registration from Semantic; checks from Validation.

### Capability bindings

| Capability | Binding |
|---|---|
| `SurrogateKeyAllocation` | Identity column on each keymap or inline-keyed table; `02-key-allocation.sql.j2` returns the permanent identifier. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `PointInTimeReconstruction` | `SECURITY DEFINER` SQL function `(valid_at)` or `(valid_at, known_at)` per relation the context gives a `function` object. |
| `NaturalKeyLookup` | Unique natural key on each keymap; consumer views carry the stable identifier. |
| `EntityJoinBack` | Search and Prediction rows carry the Domain identifier; consumers join to the Domain consumer view. |
| `AccessView` | One consumer view per relation with a `consumer_view` object. |
| `RichMetadata` | `COMMENT ON` for every table and column, plus Semantic registration. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-DOMAIN-001` | `entity metadata` check: every placed column exists and carries a comment. |
| `INV-DOMAIN-002,006` | Current and point-in-time macros; `entity temporal` check; engine test of a bitemporal correction read at two knowledge times. |
| `INV-DOMAIN-003,004` | Permanent keymap with foreign key; allocation test. Retention is operational. |
| `INV-DOMAIN-005,007` | Review the specification's attributes and relationships; no generic duplication detector is claimed. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 6. Observability module (`observability`)

Templates: [`modules/observability/`](modules/observability/).

Binding of [Observability](../../design/modules/observability.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('observability')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The relations are those the Observability standard defines and the resolver places: change events, quality metrics, lineage definitions and runs, model performance, agent outcomes, and the validation relations `ValidationRun` and `ValidationArea`. Event relations are append-only by profile; lineage definitions are current-state. Each gets a consumer view from the temporal pattern.

The module's views are rendered elsewhere: `LineageGraph` and `LineageRunLatest` by [Semantic discovery](#4-semantic-module-semantic), and `TrustMap` by [Validation](#9-validation-pattern-validation).

Capture is a producer obligation: deployers wire their ingestion, temporal writer and agent runtime to these stores. No trigger or synthetic quality score is emitted. The [access-layer template](#10-access-layer-pattern-access-layer) grants the agent tier `INSERT` on agent outcomes, the write target the context marks; validation evidence is written by [`validate.py`](../../tooling/bindings/README.md) using the placement the manifest carries. Privileged administration can bypass append-only intent. Retention is a settled design decision and an operator-managed process; no template deletes records.

### Capability bindings

| Capability | Binding |
|---|---|
| `ChangeEventCapture` | Append-only change-event table; the writer must emit events. |
| `AgentOutcomeCapture` | Append-only agent-outcome table; the agent tier may insert. |
| `LineageCapture` | Separate definition and run tables, with the lineage graph and latest-run views over active definitions. |
| `QualityScore` | Quality-metric time series, separate from validation evidence. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-OBS-001,002` | Standard-owned event structures hold table-level references and counts; producer payload review required. |
| `INV-OBS-003,006` | Separate definition and run tables; lineage views read active definitions only. |
| `INV-OBS-004` | Retention is a settled decision; operators prove enforcement. |
| `INV-OBS-005` | Wire 2.1 run and area records appended by the validator; engine tests of failures, errors, staleness and producer selection. |
| `INV-OBS-007..009` | Optional graph-native facet not rendered; no graph identity guarantee claimed. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 7. Search module (`search`)

Templates: [`modules/search/`](modules/search/).

Binding of [Search](../../design/modules/search.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('search')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The embedding store holds identifiers, vectors and provenance, never source content. A `Vector` column binds to `DOUBLE PRECISION[]` with a `CHECK` that it has one dimension, the declared cardinality and no null elements.

`02-similarity.sql.j2` emits one SQL function per `Embedding:` block in the context's `embeddings` that has an `objects.function`. It reads the block's `store` (through `named`), `vector_column`, `dimensions`, `similarity`, `threshold`, `name` and, where present, `model`. The function `(query_vector DOUBLE PRECISION[], result_limit INTEGER)`:

- reads the store's consumer view, so only current vectors are ranked, restricted to rows whose source attribute is the block's name (and to its model, where the block names one);
- scores by the declared similarity: cosine, dot product, or `1 / (1 + distance)` for euclidean and manhattan;
- returns no rows unless the query vector is one-dimensional, of the declared length and free of nulls;
- keeps scores at or above the declared threshold and returns `(entity_id, similarity)` ordered by score, then identifier, with the limit clamped to 0..1000.

The function returns identifiers only. Join-back to Domain is the caller's: the cookbook's similarity recipes join the function to the entity's consumer view. It runs with invoker rights; the read and agent tiers reach it through `EXECUTE` and their `SELECT` on the store's consumer view.

Vectors come from the encoder the specification declares, outside the database; no encoder is substituted. Approximate indexing (for example pgvector) is not emitted. Validate query vectors for finite elements and nonzero norm at the encoder and query boundary.

### Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Exact ranking over current vectors by the declared similarity and threshold. |
| `EntityJoinBack` | Results carry the Domain identifier; recipes join to the Domain consumer view. |
| `CurrentStateFilter` | The function reads the store's consumer view. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review the declared embedding and model provenance; the vector `CHECK` enforces the dimension. |
| `INV-SEARCH-002,004` | Engine test that the function ranks current vectors of its embedding and applies the threshold. |
| `INV-SEARCH-005` | Shared temporal macros and the `entity temporal` check. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 8. Prediction module (`prediction`)

Templates: [`modules/prediction/`](modules/prediction/).

Binding of [Prediction](../../design/modules/prediction.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('prediction')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). It creates the feature and prediction entities the specification assigns to Prediction, with the columns, keys and temporal profile the context resolves for each. The temporal pattern adds their consumer views and point-in-time functions.

No template computes features or scores. Product feature SQL must apply both effective and knowledge-time cutoffs to each source and respect observation and availability time. Definitions belong to Semantic and monitoring to Observability; Domain context is reached by identifier join-back, not copied into feature or prediction rows. Prediction tables begin empty: no score or model quality is fabricated.

### Capability bindings

| Capability | Binding |
|---|---|
| `PointInTimeReconstruction` | Point-in-time function per versioned feature or prediction relation. Cutoff correctness is a product obligation. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `AccessView` | One consumer view per relation with a `consumer_view` object. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-PRED-001,003` | Review the specification's features; only engineered values and Domain identifiers belong here. |
| `INV-PRED-002` | Point-in-time functions support reconstruction; the product's feature pipeline must prove cutoff correctness. |
| `INV-PRED-004,005` | Semantic and Observability stores are separate; product capture and lineage checks remain required. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 9. Validation pattern (`validation`)

Templates: [`patterns/validation/`](patterns/validation/).

Binding of [Validation](../../design/patterns/validation.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Checks

Each check is a query whose every row is a defect. The `checks` of [`binding.toml`](binding.toml) names them, and [`render.py`](../../tooling/bindings/README.md) renders them into the manifest with test ids `{PRODUCT_CODE}-{CHECK}-{NNN}`:

| Check | Template | Rendered for | Returns |
|---|---|---|---|
| `entity metadata` | `01-entity-metadata.sql.j2` | each persisted relation (`entity`) | each placed column the table lacks or that has no comment, from `information_schema.columns` and `col_description` |
| `entity temporal` | `02-entity-temporal.sql.j2` | each persisted relation (`entity`) | identities with an empty interval, a current flag that disagrees with the open ends, overlapping versions (both axes when bitemporal), a deletion flag without its instant, or a non-finite timestamp outside the interval ends |
| `relationship reference` | `03-relationship-reference.sql.j2` | each entry in `relationships` (`relationship`) | current source references with no current target, read through the consumer views (the tables where no view is placed); an optional reference may be null |
| `module semantic` | [`modules/semantic/validation.sql.j2`](#4-semantic-module-semantic) | the Semantic module | unregistered base tables |
| `module memory` | [`modules/memory/validation.sql.j2`](#3-memory-module-memory) | the Memory module | modules below the capture floor |
| `contract identity` | [`modules/semantic/contract/identity.sql.j2`](#4-semantic-module-semantic) | the Semantic module | identities that break the grammar, carry the wrong module qualifier or are registered twice |
| `contract keys` | `modules/semantic/contract/keys.sql.j2` | the Semantic module | entities with no key, keys with no columns, ordinals that do not run 1 to n, and key columns the entity lacks |
| `contract relationships` | `modules/semantic/contract/relationships.sql.j2` | the Semantic module | relationships with no column pair, gaps in the ordinals, unregistered entities and columns the entities lack |
| `contract access-columns` | `modules/semantic/contract/access-columns.sql.j2` | the Semantic module | consumer-view columns with no mapping row, mappings for columns the view lacks, repeated or gapped ordinals, and absent sources |
| `contract composition` | `modules/semantic/contract/composition.sql.j2` | the Semantic module | composites without exactly one anchor, gapped member order, and members not joined to a prior member through a registered relationship |
| `product comment-coverage` | `05-comment-coverage.sql.j2` | the product | every container, object and column of the product's containers with no comment (the catalogue-wide `MetadataCoverageCheck`) |

The reference check is current-surface coverage, not historical proof. A join of several columns resolves only when every pair matches, so the check tests all of them.

### Trust map

`04-trust-map.sql.j2` is a phase, not a check. Where the product places `TrustMap`, `ValidationRun`, `ValidationArea` and the product registry, it creates one `TrustMap` view:

- evidence is the area records joined to their run, plus one PRODUCT entry for each run at a registered legacy wire version (`quality.legacy_wire_versions`) with no area records, graded on the run's counts by Validation §4.3 and never above `partial` (`no-evidence` and `unknown` if the run had no checks);
- the registry's designated producer, where one is set, is the only producer read;
- the latest entry per producer and area wins; it is read at `unknown` confidence once past the run's `evidence_expires_dts`, or, without one, past its completion plus the product's evidence window (`quality.evidence_window_days`, which the resolver defaults to 7 days);
- where no producer is designated, the most cautious producer's entry stands for each area;
- a product with no evidence at all reads `no-evidence` and `unknown`.

### Validator

[`validate.py`](../../tooling/bindings/README.md) connects through `POSTGRES_DSN`, runs each check in its own savepoint and records an erroring check as `ERROR`, never as zero defects. Where the manifest places `ValidationRun` and `ValidationArea`, it appends one run and one area record per entity, module and the product (wire schema 2.1). Failed `ERROR` or `CRITICAL` checks give weak confidence; a failed `WARNING` leaves partial. The gaps the manifest reports cap the PRODUCT area at partial. This is a structural profile, not a certification of business rules; add design-specific checks in the product workspace with explicit scope and provenance.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 10. Access Layer pattern (`access-layer`)

Templates: [`patterns/access-layer/`](patterns/access-layer/).

Binding of [Access Layer](../../design/patterns/access-layer.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Template

`01-grants.sql.j2` is the last phase. It reads `principals` (the name of each of `ROLE_READ`, `ROLE_AGENT` and `ROLE_ADMIN`, and whether the build creates it), `grant_level`, `containers`, `module_containers`, the placed objects of `entities` and `relations`, and `embeddings`. In order it:

1. creates each principal the profile says to `create`, as a `NOLOGIN` role; an `existing` principal is used by name and not altered;
2. for every container the product owns (never an adopted one), revokes schema access and function execution from `PUBLIC` (including default privileges for new functions), grants `USAGE` to all three tiers, and grants the admin tier all privileges on tables, sequences and functions;
3. grants `SELECT` on consumer views to the read and agent tiers: per view at grant level `object`, or on every table and view in each container that holds consumer views at grant level `container`;
4. grants `EXECUTE` on every point-in-time function and similarity function to the read and agent tiers;
5. for each table whose primary role is `WRITE_TARGET`: on a runtime Memory relation, enables row-level security with a policy limiting the agent tier to rows with `scope_level = 'USER'` and `scope_identifier = session_user`, an unrestricted policy for the admin tier, and `SELECT`, `INSERT` and `UPDATE` for the agent tier; on any other write target (agent outcomes), `INSERT` for the agent tier.

Point-in-time functions are `SECURITY DEFINER` with a fixed `search_path`, so the read and agent tiers reach history through them without a grant on the base table. Similarity functions run with invoker rights over consumer views. At grant level `container`, every table in a consumer-view container becomes readable, so such a container should hold consumer views only.

The deploy script does not create login users, assign passwords or grant role membership; those are operator steps. Object owners and superusers remain trusted administrators. Review the memberships of an `existing` role before binding a product to it.

### Capability bindings

| Capability | Binding |
|---|---|
| `AccessView` | Consumer views are the read and agent tiers' only table-like surface. |
| `ProductRoleAccess` | Native roles named by the profile; grants per object or per container; `USER` row-level security on runtime Memory. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 11. Physical Storage pattern (`physical-storage`)

Binding of [Physical Storage](../../design/patterns/physical-storage.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

This pattern has no template. The baseline is native, unpartitioned storage. The only indexes emitted are those the shared table macro creates: primary keys, unique keys, and for each history table a partial unique index on the current row and a GiST exclusion constraint over its intervals. Further indexing, statistics, vacuum and checkpoint settings, partitioning and storage layout are chosen from measured workloads; review the exclusion constraints before partitioning a history table. No external file, foreign table, object-store mount or approximate vector index is emitted.

The validator does not establish backup and restore, durability, replication, disaster recovery or performance. Publish operator evidence separately. Rendered SQL and deployment packages belong in the user's output location, not this repository.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## Catalogue

<!-- catalogue:start -->

### Platform profile

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [PostgreSQL Platform Profile](PLATFORM_PROFILE.md) *(advisory)* | `postgres` | draft | - | - | - |

<!-- catalogue:end -->
