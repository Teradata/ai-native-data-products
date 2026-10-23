# DuckDB implementation

Reusable binding for **any conforming data product**, following the module and pattern layout of the other platforms. Target: DuckDB 1.4 or later; tested on 1.5 (see [CONFORMANCE.md](CONFORMANCE.md)). These are Jinja templates and binding documents, not a finished deployment or a compiler. There is no plain SQL, Python or JSON in this directory: rendering, validation and the tests live under [`tooling/`](../../tooling/bindings/README.md), shared with the other Jinja bindings.

## How a build reads this binding

A build has three inputs: a **design specification** (the product, platform-agnostic), an **organisation profile** (placement, naming, access tiers and classification for one organisation on DuckDB) and this **binding**. [`tooling/build/build_context.py`](../../tooling/build/README.md) resolves the specification, the profile and the binding's declarations into one build context, whose shape is fixed by [`build_context.schema.json`](../../tooling/build/build_context.schema.json) ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3).

The templates read only the build context, and derive no names: every container, object, sequence and column name arrives resolved. Standard-owned relations (the Semantic catalogue, the Observability and Memory stores, the validation relations and the discovery and trust-map views) are defined by the module and pattern standards under [`design/`](../../design/) and placed by the resolver. This directory carries no input contract or entity declarations of its own.

DuckDB has no principals. The binding declares `Principals: unsupported`, so the organisation profile declares each access tier as `outside <how it is enforced>`, the resolver rejects a tier the profile says to `create` or bind to an `existing` principal, and there is no grants template and no access phase.

Read [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md) first. Its **Binding declarations** section lists the phase files in order with the template that renders each, the deploy template, the checks, and the physical type and SQL fragment for each logical type and expression function. Then read the sections below: one per module and pattern, in deployment order, each saying what its templates emit, which build-context fields they read and where its templates are. The index gives the line each section starts on.

<!-- index:start -->
| Line | Section | Covers |
|---:|---|---|
| 34 | [Render, deploy and validate](#render-deploy-and-validate) | Rendering the worked example, deploying it, running the validator; what the renderer writes |
| 60 | [Verification](#verification) | The test and lint commands for this binding |
| 72 | [1. Object Placement pattern (`object-placement`)](#1-object-placement-pattern-object-placement) | Schemas |
| 90 | [2. Temporal Lifecycle Metadata pattern (`temporal-lifecycle-metadata`)](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata) | Shared macros, comments, consumer views, point-in-time table macros, caller-rendered maintenance |
| 135 | [3. Memory module (`memory`)](#3-memory-module-memory) | Sequences and tables; design-memory capture |
| 180 | [4. Semantic module (`semantic`)](#4-semantic-module-semantic) | Sequences and tables; registration; discovery views; the metadata-contract checks |
| 239 | [5. Domain module (`domain`)](#5-domain-module-domain) | Sequences and tables; key allocation |
| 283 | [6. Observability module (`observability`)](#6-observability-module-observability) | Sequences and tables |
| 320 | [7. Search module (`search`)](#7-search-module-search) | Sequences and tables; similarity macros |
| 361 | [8. Prediction module (`prediction`)](#8-prediction-module-prediction) | Sequences and tables |
| 393 | [9. Validation pattern (`validation`)](#9-validation-pattern-validation) | Metadata, temporal, reference and comment-coverage checks; the trust-map view |
| 435 | [10. Access Layer pattern (`access-layer`)](#10-access-layer-pattern-access-layer) | None: the access boundary is outside the engine |
| 456 | [11. Physical Storage pattern (`physical-storage`)](#11-physical-storage-pattern-physical-storage) | None: object storage is not rendered |
| 468 | [Catalogue](#catalogue) | The binding's design documents (generated) |
<!-- index:end -->

## Render, deploy and validate

The worked inputs are the [IT Service Desk specification](../../examples/it-service-desk-data-product/design-output/design_specification.md) with its [DuckDB profile](../../examples/it-service-desk-data-product/profiles/duckdb.md). The [customer-orders reference](../../tooling/evals/reference/customer-orders.md) builds under the same profile.

```sh
python -m pip install -r tooling/bindings/requirements.txt duckdb pytz
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md examples/it-service-desk-data-product/profiles/duckdb.md --output build/itsd-duckdb
duckdb build/itsd.duckdb < build/itsd-duckdb/deploy.sql
python tooling/bindings/validate.py build/itsd-duckdb/manifest.json --database build/itsd.duckdb
```

The profile names the platform. `--environment PHASE` places the product for one lifecycle phase; `--version V` supplies the product version where the specification leaves it open. The output directory must be empty and outside `design/`, `implementation/`, `examples/`, `roles/` and `tooling/`. The renderer writes:

- one SQL file per declared phase that renders something for this composition;
- `deploy.sql`, every phase in one transaction with the session time zone set to UTC;
- `manifest.json`: the checks, each with a test id `{PRODUCT_CODE}-{CHECK}-{NNN}`, where validation evidence is placed, the gaps the binding reports and the defaults the resolver applied;
- `context.json`, the resolved build context.

Rendering does not connect to a database. Rendered SQL is not checked into this repository.

Deploy into a **new, empty** database file. The file stem becomes the catalogue name: do not name it after a module (especially `memory`). Use one writing process; close and checkpoint the file before opening readers with `read_only`.

The validator needs an existing file (`--database`). It runs every check in autocommit, so one failing query does not affect the next, and where the product places `ValidationRun` and `ValidationArea` it appends one run and its area records (wire schema 2.1) in a single transaction. `--producer` publishes under a producer id other than the product's designated one. The manifest contains trusted generated SQL: never run one from an untrusted source. Gaps the manifest reports, such as an expression using a function this binding has no fragment for or a composite access object, cap the PRODUCT area at `partial`. A freshly deployed product reads `no-evidence` in the trust map until the validator has published.

**Direct access to the file exposes all data**: views and read-only mode are not access control.

## Verification

```sh
python -m pip install jinja2 duckdb pytz
python -m unittest discover -s tooling/bindings/tests -v
python -m unittest discover -s tooling/validation/tests -v
python tooling/validation/design_lint.py design implementation
python tooling/catalogue/build_catalogue.py --check
```

The DuckDB engine tests need the `duckdb` and `pytz` packages. Without `duckdb` they skip, and a skip is a gap. See [CONFORMANCE.md](CONFORMANCE.md) for coverage and declared gaps.

## 1. Object Placement pattern (`object-placement`)

Templates: [`patterns/object-placement/`](patterns/object-placement/).

Binding of [Object Placement](../../design/patterns/object-placement.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Template

`01-containers.sql.j2` is the first phase. It creates one schema, inside the database the deployer has opened, for each entry in the context's `containers` that holds objects and is not adopted. Adopted containers already exist; parent containers hold no objects on this platform. Schema creation does not use `IF NOT EXISTS`, so accidental reuse fails rather than blending two products.

Every container name, and the schema of every object and sequence, comes from the organisation profile through the resolver. No name is inferred from a product prefix, and the example profile is one possible placement, not a required convention. The database file and its location are a deployment choice outside the templates.

The phase order in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations) creates schemas, then Memory, Semantic, Domain, Observability, Search and Prediction sequences and tables, then comments, views and macros, registration, discovery, the trust map and documentation capture. There is no access phase. `deploy.sql` applies them in one transaction; deploying phase files separately must keep that order.

DuckDB schemas are logical groupings, not security containers. Discovery and validation queries filter by schema name, not by `current_database()`, so attach no other database with same-named schemas to a session that runs them. Do not name the database file after a module; in particular the catalogue `memory` collides with DuckDB's default in-memory catalogue.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 2. Temporal Lifecycle Metadata pattern (`temporal-lifecycle-metadata`)

Templates: [`patterns/temporal-lifecycle-metadata/`](patterns/temporal-lifecycle-metadata/).

Binding of [Temporal Lifecycle Metadata](../../design/patterns/temporal-lifecycle-metadata.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`00-macros.sql.j2` holds the macros every other template imports. Each takes a relation from the context (an entity or a standard-owned relation, with its `columns`, `column_names`, `key_columns`, `version_columns` and placed `objects`) and composes no name:

| Macro | Emits |
|---|---|
| `cols`, `column` | A quoted column list; one column definition with type, sequence default, `NOT NULL`, `UNIQUE` and Enum check |
| `primary_key`, `constraints` | The key (version columns plus interval starts for history); interval-order, current-flag and deletion-flag checks |
| `current`, `at` | The current-row predicate; the half-open point-in-time predicate on `valid_at` and, when bitemporal, `known_at` |
| `table` | `CREATE TABLE` with the keymap foreign key |
| `module_tables` | Every persisted, defined, non-adopted relation of one module, keymaps first, each preceded by `CREATE SEQUENCE` where it has an `objects.sequence` |
| `value`, `ref`, `insert`, `member` | A Python value as SQL; a subquery for a current row's key; an insert by logical attribute name with open-row defaults for temporal columns; whether an Enum permits a value |

DuckDB has no partial unique indexes or exclusion constraints, so `table` emits neither: one open version per identity and non-overlapping intervals are proved by the `entity temporal` check and by serialised writer discipline. A direct SQL write can violate them until the check runs.

`02-comments.sql.j2` applies `COMMENT ON TABLE` and `COMMENT ON COLUMN` to every persisted relation from its `description` and each column's description (or its logical name), after the tables and before anything depends on them; DuckDB dependencies can block a later comment change.

`03-access-views.sql.j2` creates, for every relation with a `consumer_view` object, a view of its current rows (the `current` macro) carrying every column except the open interval ends `valid_to_dts` and `transaction_to_dts`. Runtime relations have no consumer view. For every relation with a `function` object it creates a point-in-time table macro `(valid_at)`, or `(valid_at, known_at)` when bitemporal, returning the table's rows at that instant. Macro parameters are untyped: pass `TIMESTAMPTZ` values.

`04-maintenance.sql.j2` is caller-rendered with `entity`, `stable_key`, `effective_at`, `recorded_at` and `replacement_rows` (each keyed by physical column name). It is a transaction body: the caller controls `BEGIN` and `COMMIT` on the single writing connection, retries a transaction conflict and runs the checks before committing. It:

- for a bitemporal relation, closes every open knowledge interval of the identity at `recorded_at` and clears its current flag;
- otherwise, closes the version whose validity covers `effective_at` at that instant;
- inserts every replacement row with every column, each value through the literal filter.

It is not a change planner. The caller supplies complete, non-overlapping intervals (for a bitemporal correction, the whole new known timeline), detects unchanged replay, preserves unaffected segments and tombstones, and rejects non-finite or non-monotonic correction instants. Pass an open end as the text `infinity`; the Python driver turns infinity into a finite datetime.

Validity and knowledge intervals are half-open; infinity appears only as an open end. For bitemporal history, overlap is prohibited only where both axes overlap. The current flag is true exactly when every applicable end is open.

### Capability bindings

| Capability | Binding |
|---|---|
| `CurrentStateFilter` | `current` macro behind the consumer views and reference checks. |
| `PointInTimeReconstruction` | `at` macro behind the point-in-time table macros. |
| `SoftDelete` | `is_deleted` and `deleted_dts` with a consistency check; deleted rows are excluded from current and point-in-time reads. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 3. Memory module (`memory`)

Templates: [`modules/memory/`](modules/memory/).

Binding of [Memory](../../design/modules/memory.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('memory')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The relations are those the Memory standard defines and the resolver places: the documentation relations (module registry, design decisions, glossary, cookbook, implementation notes, change log), versioned with consumer views and point-in-time table macros, and the runtime relations the context includes, which have no consumer view. Process context uses the DuckDB `JSON` type.

`02-capture.sql.j2` writes the design-memory records the build context settles in `capture`, one insert per record, by logical attribute name through the `insert` macro:

- `capture.modules` into the module registry, with `product.version`;
- `capture.decisions` into design decisions, each with its settled `DD-{MODULE}-{NNN}` id, version 1 and status `ACCEPTED`;
- `capture.glossary`, `capture.notes` and `capture.change_log` into their relations;
- `capture.cookbook` into the cookbook, with each recipe's query rendered here in the DuckDB dialect from its `kind`: a metric's measure and filter over its dataset's consumer view (`metrics`); a call to a similarity macro with `$1` and a limit of 10, joined to the entity's consumer view where the recipe asks (`embeddings`); a join of a relationship's source and target consumer views (`relationships`); a catalogue lookup of entity metadata for the named modules; otherwise the named relation's consumer view.

A record the context does not carry is not written. What capture could not settle is listed in `capture.gaps` and reported in the manifest.

`validation.sql.j2` is the `module memory` check. Every row it returns is a registered module below the capture floor: three design decisions, three glossary terms and one cookbook recipe.

### Access

DuckDB has no row-level security or principals. Runtime rows carry the required `scope_level` and `scope_identifier` columns, but nothing in the engine filters by caller, and read-only mode does not hide them. The organisation profile declares how each access tier is enforced outside the database. Privacy needs an authenticated serving application that derives scope from identity, or separate protected storage. Direct access to the database file exposes runtime data.

### Capability bindings

| Capability | Binding |
|---|---|
| `DocumentationCapture` | Versioned documentation relations; `02-capture.sql.j2` writes the settled records; `validation.sql.j2` reports modules below the floor. |
| `AgentContinuity` | Runtime relations with required scope columns and no consumer view. Scope enforcement is outside DuckDB. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-MEMORY-001,002,004` | Standard-owned structures separate process and design context; producer payload review remains necessary. |
| `INV-MEMORY-003` | Required scope columns and no consumer view. Runtime privacy enforcement is a declared gap. |
| `INV-MEMORY-005` | Shared versioned temporal macros and the `entity temporal` check. |
| `INV-MEMORY-006` | `module memory` check of the capture floor; the reference specifications meet it. |

Physical types come from the `Types:` block of the [binding declarations](PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

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
- access objects for every placed object of each relation and for each similarity macro in `embeddings`, with consumer views and macros marked agent-consumable;
- primary objects for every placed object with a `primary_role`;
- the orientation sequence from `orientation.resources`;
- metrics from `metrics`, with the rendered measure and filter as a DuckDB expression and the dataset's consumer view;
- entity and column synonyms;
- naming standards from `naming`: each object template, the attribute template and each standard-name mapping.

Composite access objects (`access_objects`) are not registered; the manifest reports each as a gap. DuckDB cannot comment on schemas, so module descriptions live in Semantic rows.

`03-discovery.sql.j2` creates the standard-owned discovery views, each only where the composition places it and the relations it reads:

- `ColumnCatalogue`: `information_schema.columns` for the product's schemas, left-joined to column metadata, with `description_source` `authored` or `missing`;
- `DataProductManifest`: the active registry row with one column per orientation resource role;
- `RelationshipPaths`: a recursive view, using DuckDB list functions, over active table relationships in both directions, up to the Semantic standard's bound of four hops (the context's `max_hops`) without revisiting a table. Paths join base tables; resolve them through the access objects before issuing consumer SQL;
- `LineageGraph` and `LineageRunLatest` over Observability's active lineage definitions and their runs.

`validation.sql.j2` is the `module semantic` check: every base table in a schema the product places objects in, keymaps included, is registered in entity metadata.

**The metadata contract (release 2.0.0).** Registration writes the logical identity of each entity (`module.entity`) and, beside it, its location; the key definitions and their ordered key columns; one relationship column pair per join column; one access object per placed object, identified by entity and surface; one access-column mapping row per output column of each consumer view over an entity (the context's `view_columns`, which the view itself selects); and the `StandardDeclaration` rows from `standard`. `RelationshipPaths` returns one row per path step and key position, bounded to four hops. The manifest's last column is `standard_version`. The five checks under [`contract/`](modules/semantic/contract/) test `INV-SEMANTIC-016` to `020`; they are declared as `contract` checks and read only registered metadata and the catalogue.

Registration uses the placement and relationships the context carries, never name inference. Structural facts come from `information_schema`, filtered by schema name only, not by `current_database()`; meanings come from the specification.

### Capability bindings

| Capability | Binding |
|---|---|
| `SemanticRegistration` | Registration inserts for the product, modules, entities, columns, relationships, access and primary objects, orientation, metrics, synonyms and naming standards. |
| `RichMetadata` | `COMMENT ON` for physical objects, plus authored entity and column metadata and the hybrid column catalogue. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEMANTIC-001,002` | Standard-owned catalogue structures; registries hold datasets, never business instances. |
| `INV-SEMANTIC-003,006` | Registration at deployment; `module semantic` check, with an engine test that an unregistered table is found. |
| `INV-SEMANTIC-004,011,012` | Manifest view over the registry and orientation sequence; consumer workflow verification remains required. |
| `INV-SEMANTIC-005,007..010` | Declared relationships and access objects; composite access objects are not rendered. |
| `INV-SEMANTIC-013..015` | Metrics and synonyms registered from the specification; metric recipes execute in engine tests. Reference checks over the registrations remain to be written. |

Physical types come from the `Types:` block of the [binding declarations](PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 5. Domain module (`domain`)

Templates: [`modules/domain/`](modules/domain/).

Binding of [Domain](../../design/modules/domain.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('domain')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). It emits one `CREATE TABLE` per persisted Domain relation in the context's `entities` and `relations`, keymaps first so references to them resolve, and skips any the context marks `adopted` or not `defined`. It reads each relation's `objects.table`, `objects.sequence`, `columns` (physical name and type, `required`, `unique`, `members`), `key_columns`, `version_columns`, `column_names`, `history`, `bitemporal`, `supports_deletion` and `identity.keymap`.

- A relation with an `objects.sequence` (a keymap, or an inline-keyed table such as a Reference entity) gets `CREATE SEQUENCE` with the name and schema the profile places, and its key column defaults to `nextval` of it.
- An entity with a keymap gets a foreign key from its key columns to the keymap's table.
- An Enum attribute gets a `CHECK` over its members.
- A history table's primary key is its version columns plus `valid_from_dts` (and `transaction_from_dts` when bitemporal). DuckDB has no partial unique indexes or exclusion constraints, so one open version per identity and non-overlapping intervals are proved by the `entity temporal` check, not enforced by the engine.

`02-key-allocation.sql.j2` is caller-rendered with `keymap` (a Keymap entity from the context) and `natural_value`. It inserts the natural value and returns the stable identifier; an existing natural value returns its existing identifier unchanged through `ON CONFLICT`. Only the first natural-key attribute (`identity.natural[0]`) is used. The caller opens the transaction on the single writing connection and retries a transaction conflict. An allocation that meets an existing mapping can still consume a sequence value, so identifiers are unique and never reused but not contiguous.

Comments, consumer views and point-in-time table macros come from the temporal pattern; registration from Semantic; checks from Validation.

### Capability bindings

| Capability | Binding |
|---|---|
| `SurrogateKeyAllocation` | Sequence default on each keymap or inline-keyed table; `02-key-allocation.sql.j2` returns the permanent identifier. Serial writer; administrative SQL can bypass it. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `PointInTimeReconstruction` | Table macro `(valid_at)` or `(valid_at, known_at)` per relation the context gives a `function` object. |
| `NaturalKeyLookup` | Unique natural key on each keymap; consumer views carry the stable identifier. |
| `EntityJoinBack` | Search and Prediction rows carry the Domain identifier; consumers join to the Domain consumer view. |
| `AccessView` | One consumer view per relation with a `consumer_view` object; an interface, not a security boundary. |
| `RichMetadata` | `COMMENT ON` for every table and column, plus Semantic registration. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-DOMAIN-001` | `entity metadata` check: every placed column exists and carries a comment in `duckdb_columns()`. |
| `INV-DOMAIN-002,006` | Current and point-in-time macros; `entity temporal` check; engine test of a bitemporal correction read at two knowledge times. |
| `INV-DOMAIN-003,004` | Permanent keymap with foreign key; allocation test. Retention is operational. |
| `INV-DOMAIN-005,007` | Review the specification's attributes and relationships; no generic duplication detector is claimed. |

Physical types come from the `Types:` block of the [binding declarations](PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 6. Observability module (`observability`)

Templates: [`modules/observability/`](modules/observability/).

Binding of [Observability](../../design/modules/observability.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('observability')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The relations are those the Observability standard defines and the resolver places: change events, quality metrics, lineage definitions and runs, model performance, agent outcomes, and the validation relations `ValidationRun` and `ValidationArea`. Event relations are append-only by profile; lineage definitions are current-state. Each gets a consumer view from the temporal pattern.

The module's views are rendered elsewhere: `LineageGraph` and `LineageRunLatest` by [Semantic discovery](#4-semantic-module-semantic), and `TrustMap` by [Validation](#9-validation-pattern-validation).

Capture is a producer obligation: deployers wire their ingestion, temporal writer and agent runtime to these stores. No trigger or synthetic quality score is emitted, and the maintenance template emits no change event. DuckDB cannot make a table append-only for one writer, so append-only intent is a convention of the writing application. Validation evidence is written by [`validate.py`](../../tooling/bindings/README.md) using the placement the manifest carries. Retention is a settled design decision and an operator-managed process; no template deletes records.

### Capability bindings

| Capability | Binding |
|---|---|
| `ChangeEventCapture` | Append-only change-event table; the writer must emit events. |
| `AgentOutcomeCapture` | Append-only agent-outcome table; the host supplies actor identity and redacts parameters. |
| `LineageCapture` | Separate definition and run tables, with the lineage graph and latest-run views over active definitions. |
| `QualityScore` | Quality-metric time series, separate from validation evidence. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-OBS-001,002` | Standard-owned event structures hold table-level references and counts; producer payload review required. |
| `INV-OBS-003,006` | Separate definition and run tables; lineage views read active definitions only. |
| `INV-OBS-004` | Retention is a settled decision; operators prove enforcement. |
| `INV-OBS-005` | Wire 2.1 run and area records appended by the validator; engine tests of failures, errors, staleness and producer selection. |
| `INV-OBS-007..009` | Optional graph-native facet not rendered; no graph identity guarantee claimed. |

Physical types come from the `Types:` block of the [binding declarations](PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 7. Search module (`search`)

Templates: [`modules/search/`](modules/search/).

Binding of [Search](../../design/modules/search.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('search')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The embedding store holds identifiers, vectors and provenance, never source content. A `Vector` column binds to a fixed-size `FLOAT[n]` array, which rejects a vector of the wrong dimension on insert.

`02-similarity.sql.j2` emits one table macro per `Embedding:` block in the context's `embeddings` that has an `objects.function`. It reads the block's `store` (through `named`), `vector_column`, `dimensions`, `similarity`, `threshold`, `name` and, where present, `model`. The macro `(query_vector, result_limit)`:

- casts the query vector to `FLOAT[n]` of the declared dimension, so a vector of another length is an error;
- reads the store's consumer view, so only current vectors are ranked, restricted to rows whose source attribute is the block's name (and to its model, where the block names one);
- scores by the declared similarity: `array_cosine_similarity`, `array_inner_product`, or `1 / (1 + distance)` for euclidean (`array_distance`) and manhattan;
- keeps scores at or above the declared threshold and returns `(entity_id, similarity)` ordered by score, then identifier, with the limit clamped to 0..1000.

The macro returns identifiers only. Join-back to Domain is the caller's: the cookbook's similarity recipes join the macro to the entity's consumer view.

Vectors come from the encoder the specification declares, outside the database; no encoder is substituted. The templates install and load no extension; the VSS extension and its HNSW index are not emitted, and DuckDB documents its persistent form as experimental. Validate query vectors for finite elements and nonzero norm at the encoder and query boundary.

### Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Exact ranking over current vectors by the declared similarity and threshold. |
| `EntityJoinBack` | Results carry the Domain identifier; recipes join to the Domain consumer view. |
| `CurrentStateFilter` | The macro reads the store's consumer view. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review the declared embedding and model provenance; engine test that the fixed-size array rejects the wrong dimension. |
| `INV-SEARCH-002,004` | Engine test that the macro ranks current vectors of its embedding and applies the threshold. |
| `INV-SEARCH-005` | Shared temporal macros and the `entity temporal` check. |

Physical types come from the `Types:` block of the [binding declarations](PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 8. Prediction module (`prediction`)

Templates: [`modules/prediction/`](modules/prediction/).

Binding of [Prediction](../../design/modules/prediction.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('prediction')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). It creates the feature and prediction entities the specification assigns to Prediction, with the columns, keys, sequences and temporal profile the context resolves for each. The temporal pattern adds their consumer views and point-in-time table macros.

No template computes features or scores. Product feature SQL must apply both effective and knowledge-time cutoffs to each source and respect observation and availability time. Definitions belong to Semantic and monitoring to Observability; Domain context is reached by identifier join-back, not copied into feature or prediction rows. Prediction tables begin empty: no score or model quality is fabricated. A point-in-time training function and a retrospective-rewrite guard are not rendered; see [conformance scope](CONFORMANCE.md).

### Capability bindings

| Capability | Binding |
|---|---|
| `PointInTimeReconstruction` | Point-in-time table macro per versioned feature or prediction relation. Cutoff correctness is a product obligation. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `AccessView` | One consumer view per relation with a `consumer_view` object. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-PRED-001,003` | Review the specification's features; only engineered values and Domain identifiers belong here. |
| `INV-PRED-002` | Point-in-time macros support reconstruction; the product's feature pipeline must prove cutoff correctness. |
| `INV-PRED-004,005` | Semantic and Observability stores are separate; product capture and lineage checks remain required. |

Physical types come from the `Types:` block of the [binding declarations](PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 9. Validation pattern (`validation`)

Templates: [`patterns/validation/`](patterns/validation/).

Binding of [Validation](../../design/patterns/validation.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Checks

Each check is a query whose every row is a defect. The `Checks:` block of [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations) names them, and [`render.py`](../../tooling/bindings/README.md) renders them into the manifest with test ids `{PRODUCT_CODE}-{CHECK}-{NNN}`:

| Check | Template | Rendered for | Returns |
|---|---|---|---|
| `entity metadata` | `01-entity-metadata.sql.j2` | each persisted relation (`entity`) | each placed column the table lacks or that has no comment, from `duckdb_columns()` |
| `entity temporal` | `02-entity-temporal.sql.j2` | each persisted relation (`entity`) | identities with an empty interval, a current flag that disagrees with the open ends, overlapping versions (both axes when bitemporal), more than one current version, a deletion flag without its instant, or a non-finite timestamp outside the interval ends |
| `relationship reference` | `03-relationship-reference.sql.j2` | each entry in `relationships` (`relationship`) | current source references with no current target, read through the consumer views (the tables where no view is placed); an optional reference may be null |
| `module semantic` | [`modules/semantic/validation.sql.j2`](#4-semantic-module-semantic) | the Semantic module | unregistered base tables |
| `module memory` | [`modules/memory/validation.sql.j2`](#3-memory-module-memory) | the Memory module | modules below the capture floor |
| `contract identity` | [`modules/semantic/contract/identity.sql.j2`](#4-semantic-module-semantic) | the Semantic module | identities that break the grammar, carry the wrong module qualifier or are registered twice |
| `contract keys` | `modules/semantic/contract/keys.sql.j2` | the Semantic module | entities with no key, keys with no columns, ordinals that do not run 1 to n, and key columns the entity lacks |
| `contract relationships` | `modules/semantic/contract/relationships.sql.j2` | the Semantic module | relationships with no column pair, gaps in the ordinals, unregistered entities and columns the entities lack |
| `contract access-columns` | `modules/semantic/contract/access-columns.sql.j2` | the Semantic module | consumer-view columns with no mapping row, mappings for columns the view lacks, repeated or gapped ordinals, and absent sources |
| `contract composition` | `modules/semantic/contract/composition.sql.j2` | the Semantic module | composites without exactly one anchor, gapped member order, and members not joined to a prior member through a registered relationship |
| `product comment-coverage` | `05-comment-coverage.sql.j2` | the product | every container, object and column of the product's containers with no comment (the catalogue-wide `MetadataCoverageCheck`) |

Because DuckDB enforces neither one open version nor non-overlap in its schema, the temporal check is the only proof of both. The reference check is current-surface coverage, not historical proof. A join of several columns resolves only when every pair matches, so the check tests all of them.

### Trust map

`04-trust-map.sql.j2` is a phase, not a check. Where the product places `TrustMap`, `ValidationRun`, `ValidationArea` and the product registry, it creates one `TrustMap` view:

- evidence is the area records joined to their run, plus one PRODUCT entry for each run at a registered legacy wire version (`quality.legacy_wire_versions`) with no area records, graded on the run's counts by Validation §4.3 and never above `partial` (`no-evidence` and `unknown` if the run had no checks);
- the registry's designated producer, where one is set, is the only producer read;
- the latest entry per producer and area wins; it is read at `unknown` confidence once past the run's `evidence_expires_dts`, or, without one, past its completion plus the product's evidence window (`quality.evidence_window_days`, which the resolver defaults to 7 days);
- where no producer is designated, the most cautious producer's entry stands for each area;
- a product with no evidence at all reads `no-evidence` and `unknown`.

### Validator

[`validate.py`](../../tooling/bindings/README.md) opens the file given by `--database`, runs each check in autocommit so that one failing query does not affect the next, and records an erroring check as `ERROR`, never as zero defects. Where the manifest places `ValidationRun` and `ValidationArea`, it appends one run and one area record per entity, module and the product (wire schema 2.1) in one transaction. Failed `ERROR` or `CRITICAL` checks give weak confidence; a failed `WARNING` leaves partial. The gaps the manifest reports cap the PRODUCT area at partial. The shared fixture `tooling/bindings/tests/trust_cases.json` exercises the summaries. This is a structural profile, not a certification of business rules; add design-specific checks in the product workspace with explicit scope and provenance.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 10. Access Layer pattern (`access-layer`)

Binding of [Access Layer](../../design/patterns/access-layer.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

DuckDB has no roles, `GRANT`, `REVOKE` or row-level security. The binding declares `Principals: unsupported` in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations), so this pattern has **no template and no access phase**, and nothing simulates privilege statements.

The organisation profile declares each tier (`ROLE_READ`, `ROLE_AGENT`, `ROLE_ADMIN`) as `outside <how it is enforced>`, for example read-only file access for the read tier. The resolver records that text in the context's `principals` and rejects a profile that asks the build to `create` a principal or bind an `existing` one for this binding. The tiers are an external obligation: the binding does not claim that any tier is enforced.

Opening the database file read-only prevents writes. It does not hide base tables, point-in-time macros, runtime Memory or PII, nor does it constrain host file or network access. Schema separation and naming are not authorisation; direct file users see everything. See DuckDB's [security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview). A production service must authorise queries, derive runtime scope from authenticated identity, bound append rights and expose no arbitrary SQL channel; private runtime data belongs in separate protected storage.

No check covers access, and no evidence is published for it. This is declared in [conformance scope](CONFORMANCE.md), not reported as conformance.

### Capability bindings

| Capability | Binding |
|---|---|
| `AccessView` | Consumer views in the containers the profile places (see temporal-lifecycle-metadata). Not a security boundary. |
| `ProductRoleAccess` | Unsupported natively; enforced outside the engine as the profile declares. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 11. Physical Storage pattern (`physical-storage`)

Binding of [Physical Storage](../../design/patterns/physical-storage.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

This pattern has no template. The baseline is DuckDB's native columnar storage in one database file. Tables carry only their key constraints; further indexing and storage layout are chosen from measured workloads. No external file, Parquet path, object-store mount, `httpfs` extension or approximate vector index is emitted, and no template installs or loads an extension.

DuckDB supports one writing process. Close and checkpoint a file before promoting it, and open readers read-only. Do not copy an active file without a consistent backup protocol. External storage, if an organisation adopts it, is a deployment dependency with its own credentials, extension versions and validation obligations; this binding does not render it.

The validator does not establish backup and restore, durability, replication, disaster recovery or performance. Publish operator evidence separately. Database files and rendered SQL belong in the user's output location, not this repository.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## Catalogue

<!-- catalogue:start -->

### Platform profile

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [DuckDB Platform Profile](PLATFORM_PROFILE.md) *(advisory)* | `duckdb` | draft | - | - | - |

<!-- catalogue:end -->
