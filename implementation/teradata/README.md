# Teradata implementation

Reusable binding for **any conforming data product** on Teradata Vantage. Target: Teradata 17.20 or later; tested on 20.00.24 (see [CONFORMANCE.md](CONFORMANCE.md)). These are Jinja templates and binding documents, not a finished deployment or a compiler.

## How a build reads this binding

A build has three inputs: a **design specification** (the product, platform-agnostic), an **organisation profile** (placement, naming, principals and classification for one organisation on Teradata) and this **binding**. [`tooling/build/build_context.py`](../../tooling/build/README.md) resolves the specification, the profile and the binding's declarations into one build context, whose shape is fixed by [`build_context.schema.json`](../../tooling/build/build_context.schema.json) ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3).

The templates read only the build context, and derive no names: every database, object, column and role name arrives resolved. Standard-owned relations (the Semantic catalogue, the Observability and Memory stores, the validation relations and the discovery and trust-map views) are defined by the module and pattern standards under [`design/`](../../design/) and placed by the resolver. This directory carries no input contract or entity declarations of its own.

Read [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md) first, and its §7 before writing any SQL by hand: it lists, by error code, the constructs Teradata rejects. Then [`binding.toml`](binding.toml), which lists the phase files in order with the template that renders each, the deploy template, the checks, and the physical type and SQL fragment for each logical type and expression function. Then read the sections below: one per module and pattern, in deployment order, each saying what its templates emit, which build-context fields they read and where its templates are. The index gives the line each section starts on.

<!-- index:start -->
| Line | Section | Covers |
|---:|---|---|
| 34 | [Render, deploy and validate](#render-deploy-and-validate) | Rendering the worked example, deploying it, running the validator; what the renderer writes |
| 57 | [Verification](#verification) | The test and lint commands for this binding |
| 69 | [1. Object Placement pattern (`object-placement`)](#1-object-placement-pattern-object-placement) | Databases, parents first, with their permanent space |
| 87 | [2. Temporal Lifecycle Metadata pattern (`temporal-lifecycle-metadata`)](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata) | Shared macros, comments, governed base views and consumer views, statistics, caller-rendered maintenance |
| 139 | [3. Memory module (`memory`)](#3-memory-module-memory) | Tables; design-memory capture |
| 184 | [4. Semantic module (`semantic`)](#4-semantic-module-semantic) | Tables; registration; discovery views; the metadata-contract checks |
| 259 | [5. Domain module (`domain`)](#5-domain-module-domain) | Tables; key allocation |
| 304 | [6. Observability module (`observability`)](#6-observability-module-observability) | Tables |
| 346 | [7. Search module (`search`)](#7-search-module-search) | Tables; similarity procedures |
| 389 | [8. Prediction module (`prediction`)](#8-prediction-module-prediction) | Tables |
| 423 | [9. Validation pattern (`validation`)](#9-validation-pattern-validation) | Metadata, temporal, reference and comment-coverage checks; the trust-map view |
| 463 | [10. Access Layer pattern (`access-layer`)](#10-access-layer-pattern-access-layer) | The implied grants between databases; roles and tier grants |
| 494 | [11. Physical Storage pattern (`physical-storage`)](#11-physical-storage-pattern-physical-storage) | None: object storage is not rendered |
| 504 | [Catalogue](#catalogue) | The binding's design documents (generated) |
<!-- index:end -->

The graph-lineage exposure and the catalogue interface have no binding: their templates, written for the flat context that preceded the build context, were retired, and their last versions are in the history at commit `5fe4803`. A specification or profile that asks for either has it reported as a gap.

## Render, deploy and validate

The worked inputs are the [IT Service Desk specification](../../examples/it-service-desk-data-product/design-output/design_specification.md) with either Teradata profile: [`teradata.md`](../../examples/it-service-desk-data-product/profiles/teradata.md) (a database per module, upper-case names, roles created per product) or [`teradata-type-grouped.md`](../../examples/it-service-desk-data-product/profiles/teradata-type-grouped.md) (type-grouped databases under a parent, snake-case names, an adopted entity, container-isolated environments). The [customer-orders reference](../../tooling/evals/reference/customer-orders.md) builds under both.

```sh
python -m pip install -r tooling/bindings/requirements.txt teradatasql
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md examples/it-service-desk-data-product/profiles/teradata.md --output build/itsd-teradata
TERADATA_DSN='{"host": "...", "user": "...", "password": "..."}' python tooling/bindings/validate.py build/itsd-teradata/manifest.json
```

The profile names the platform. `--environment PHASE` places the product for one lifecycle phase; `--version V` supplies the product version where the specification leaves it open. The output directory must be empty and outside `design/`, `implementation/`, `examples/`, `roles/` and `tooling/`. The renderer writes:

- one SQL file per declared phase that renders something for this composition;
- `deploy.sql`, the phases in order;
- `manifest.json`: the checks, each with a test id `{PRODUCT_CODE}-{CHECK}-{NNN}`, where validation evidence is placed, the gaps the binding reports and the defaults the resolver applied;
- `context.json`, the resolved build context.

Rendering does not connect to a database. Rendered SQL is not checked into this repository.

**Deploying.** Run `deploy.sql` with a client that stops at the first error and sends one statement per request, keeping each stored procedure whole through its closing `END;`. `tooling/bindings/engines.py` (`statements`) splits a rendered script that way for a driver such as teradatasql. BTEQ splits a script at every semicolon, so with BTEQ run the similarity procedures (`10-similarity.sql`) with `.COMPILE FILE` and the other phases as scripts. Teradata commits each DDL statement on its own, so a deployment cannot be rolled back: a failed one leaves what ran, and is cleared by dropping the product's databases before deploying again. Consecutive row writes and comments may be sent as one multi-statement request, which is much faster than one request each. The deploying user needs `CREATE DATABASE` with enough permanent space for the `Container space` setting per database, `CREATE ROLE` where the profile says `create`, and `CREATE PROCEDURE` on each database that holds a similarity procedure, which a database's creator is not granted: name the deploying user in the profile's `Deploying user` setting and the build grants it. Roles carry rights only; granting them to users is an operator step.

**Validating.** The validator connects with the teradatasql parameters in `TERADATA_DSN`, runs each check (each request commits or fails on its own) and, where the product places `ValidationRun` and `ValidationArea`, appends one run and its area records in one transaction (wire schema 2.1). `--producer` publishes under a producer id other than the product's designated one. The manifest contains trusted generated SQL: never run one from an untrusted source. Gaps the manifest reports cap the PRODUCT area at `partial`.

## Verification

```sh
python -m unittest discover -s tooling/bindings/tests -v
python -m unittest discover -s tooling/validation/tests -v
python tooling/validation/design_lint.py design implementation
python tooling/catalogue/build_catalogue.py --check
python tooling/skill/verify_skill.py
```

`tooling/bindings/tests/test_teradata_dialect.py` holds every rendered statement to the §7 rules, with no engine. The engine tests need `teradatasql` and `TERADATA_TEST_DSN`, the connection parameters as JSON, for a disposable system where the user may create databases and roles. They deploy each reference specification once, under databases and roles prefixed `anptest_`, reset the rows between tests, and drop everything with that prefix, and nothing else, before and after. Without the variable or the driver the Teradata engine tests skip, and a skip is a gap. See [CONFORMANCE.md](CONFORMANCE.md) for coverage and remaining gaps.

## 1. Object Placement pattern (`object-placement`)

Templates: [`patterns/object-placement/`](patterns/object-placement/).

Binding of [Object Placement](../../design/patterns/object-placement.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Template

`01-containers.sql.j2` is the first phase. It creates one database for each entry in the context's `containers` that is not adopted: parents first, then each child `FROM` its parent. Adopted containers already exist and are never created. A database that holds objects gets the `Container space` binding setting as permanent space (the organisation profile's `Settings:`, or the binding's declared default of 1 GB, recorded in `defaults_applied`); a parent that holds no objects gets enough to allocate its children. `CREATE DATABASE` fails on an existing name, so accidental reuse fails rather than blending two products. Each database it creates carries a `COMMENT ON DATABASE`, which the `comment-coverage` product check requires.

Every database name, and the database of every object, comes from the organisation profile through the resolver: the profile is the organisation's object-placement implementation ([Organisation Profile Standard](../../design/core/ORGANISATION_PROFILE.md) §1). No name is inferred from a product prefix, and the example profiles are two possible placements, not a required convention.

A view in one database that reads another compiles only once its database holds `SELECT WITH GRANT OPTION` on the database it reads. Those implied grants are the second phase, computed from the placement ([access-layer](#10-access-layer-pattern-access-layer)); the profile never declares them.

The phase order in [`binding.toml`](binding.toml) creates databases, the implied grants, then Memory, Semantic, Domain, Observability, Search and Prediction tables, then comments, views, registration, discovery, the trust map, documentation capture, statistics and, last, roles and grants. Teradata commits each DDL statement on its own, so deploying phase files separately must keep that order, and a failed deployment is cleared by dropping its databases.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 2. Temporal Lifecycle Metadata pattern (`temporal-lifecycle-metadata`)

Templates: [`patterns/temporal-lifecycle-metadata/`](patterns/temporal-lifecycle-metadata/).

Binding of [Temporal Lifecycle Metadata](../../design/patterns/temporal-lifecycle-metadata.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`00-macros.sql.j2` holds the macros every other template imports. Each takes a relation from the context (an entity or a standard-owned relation, with its `columns`, `column_names`, `key_columns`, `version_columns` and placed `objects`) and composes no name:

| Macro | Emits |
|---|---|
| `sentinel` | The open end of an interval, `TIMESTAMP '9999-12-31 23:59:59.999999+00:00'`, written by every statement that opens a version and never as a `DEFAULT` (PLATFORM_PROFILE §7) |
| `cols`, `column`, `unicode`, `vector_pattern` | A quoted column list; one column definition with type, `CHARACTER SET UNICODE` for text, identity, `NOT NULL`, `UNIQUE`, and Enum, flag and vector-dimension checks |
| `primary_index`, `uniqueness`, `constraints` | The primary index chosen from the access path; uniqueness of each version (or a keymap's key); interval-order checks |
| `current` | The current-row predicate |
| `table` | `CREATE MULTISET TABLE`, the keymap foreign key (`WITH NO CHECK OPTION`) and the primary index |
| `module_tables` | Every persisted, defined, non-adopted relation of one module, keymaps first |
| `value`, `ref`, `insert`, `member` | A Python value as SQL; a subquery for a current row's key; an insert by logical attribute name with open-row values for temporal columns; whether an Enum permits a value |
| `comment` | A comment literal held to the dictionary's 255 characters |

`02-comments.sql.j2` applies `COMMENT ON TABLE` and `COMMENT ON COLUMN` to every persisted relation from its `description` and each column's description (or its logical name), after the tables and before anything depends on them.

`03-access-views.sql.j2` creates two views per persisted relation, each with `REPLACE VIEW` and `LOCKING ROW FOR ACCESS`, so a consumer never blocks a load:

- the **governed base view**, for every relation with a `base_view` object (this binding emits `base_view: all`): every column and every row, the full temporal contract. Teradata SQL has no table functions, so a read as at an instant applies the profile's predicates to this view. For versioned relations it is granted to the read and agent tiers ([access-layer](#10-access-layer-pattern-access-layer));
- the **consumer view**, for every relation with a `consumer_view` object: its current rows (the `current` macro) over the base view, carrying the context's `view_columns` (every column except the open interval ends `valid_to_dts` and `transaction_to_dts`). Semantic registers the same list as the view's `AccessColumn` rows, so the two cannot drift. Runtime relations have no consumer view.

Both views are created with a column list, and the view and each of its columns is commented from the entity description and the table column's description (or its logical name), each held to 255 characters.

`04-maintenance.sql.j2` is caller-rendered with `entity`, `stable_key`, `effective_at`, `recorded_at` and `replacement_rows` (each keyed by physical column name). It is a transaction body: the caller controls the transaction and runs the checks before ending it. It:

- for a bitemporal relation, closes every open knowledge interval of the identity at `recorded_at` and clears its current flag;
- otherwise, closes the version whose validity covers `effective_at` at that instant;
- inserts every replacement row with every column: an open end given as `infinity` is written as the sentinel, an instant is cast to its timestamp type, and any other value goes through the literal filter.

It is not a change planner. The caller supplies complete, non-overlapping intervals (for a bitemporal correction, the whole new known timeline), detects unchanged replay, preserves unaffected segments and tombstones, and rejects non-monotonic correction instants. Teradata enforces none of the cross-row rules in its schema; the `entity temporal` check finds them.

`05-statistics.sql.j2` collects statistics on every persisted relation's key and version columns and its currency, deletion and interval-start columns (PLATFORM_PROFILE §6).

Validity and knowledge intervals are half-open; the sentinel appears only as an open end. For bitemporal history, overlap is prohibited only where both axes overlap. The current flag is true exactly when every applicable end is open.

### Capability bindings

| Capability | Binding |
|---|---|
| `CurrentStateFilter` | `current` macro behind the consumer views and reference checks. |
| `PointInTimeReconstruction` | The governed base view, granted to the read and agent tiers; the profile's predicates select the rows at an instant. |
| `SoftDelete` | `is_deleted` and `deleted_dts`; the `entity temporal` check finds a disagreement; deleted rows are excluded from current reads. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 3. Memory module (`memory`)

Templates: [`modules/memory/`](modules/memory/).

Binding of [Memory](../../design/modules/memory.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('memory')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The relations are those the Memory standard defines and the resolver places: the documentation relations (module registry, design decisions, glossary, cookbook, implementation notes, change log), versioned with governed and consumer views, and the runtime relations the context includes, which have no consumer view. Text is `CHARACTER SET UNICODE`, so prose with typographic characters is stored as written.

`02-capture.sql.j2` writes the design-memory records the build context settles in `capture`, one insert per record, by logical attribute name through the `insert` macro:

- `capture.modules` into the module registry, with `product.version`;
- `capture.decisions` into design decisions, each with its settled `DD-{MODULE}-{NNN}` id, version 1 and status `ACCEPTED`;
- `capture.glossary`, `capture.notes` and `capture.change_log` into their relations;
- `capture.cookbook` into the cookbook, with each recipe's query rendered here in the Teradata dialect from its `kind`: a metric's measure and filter over its dataset's consumer view (`metrics`); a `CALL` of the similarity procedure with a `?` parameter, where the binding emits one (`embeddings`); a join of a relationship's source and target consumer views (`relationships`); a catalogue lookup of entity metadata for the named modules; otherwise the named relation's consumer view. A stored query never holds a `:name` parameter, which the MCP driver would try to bind (PLATFORM_PROFILE §7).

A record the context does not carry is not written. What capture could not settle is listed in `capture.gaps` and reported in the manifest.

`validation.sql.j2` is the `module memory` check. Every row it returns is a registered module below the capture floor: three design decisions, three glossary terms and one cookbook recipe.

### Access

The [access-layer template](#10-access-layer-pattern-access-layer) grants the agent tier `SELECT`, `INSERT` and `UPDATE` on each runtime relation. Teradata has no row-level security in SQL, so the binding declares `Runtime scope: unsupported`: runtime records are not restricted to the requesting identity's scope, and every build with runtime relations reports it as a gap.

### Capability bindings

| Capability | Binding |
|---|---|
| `DocumentationCapture` | Versioned documentation relations; `02-capture.sql.j2` writes the settled records; `validation.sql.j2` reports modules below the floor. |
| `AgentContinuity` | Runtime relations with required scope columns and no consumer view. Scope enforcement is a reported gap. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-MEMORY-001,002,004` | Standard-owned structures separate process and design context; producer payload review remains necessary. |
| `INV-MEMORY-003` | Required scope columns. Enforcement at the access surface is not rendered (`Runtime scope: unsupported`), and reported. |
| `INV-MEMORY-005` | Shared versioned temporal macros and the `entity temporal` check. |
| `INV-MEMORY-006` | `module memory` check of the capture floor; the reference specifications meet it on the engine. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 4. Semantic module (`semantic`)

Templates: [`modules/semantic/`](modules/semantic/).

Binding of [Semantic](../../design/modules/semantic.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('semantic')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata) for the catalogue relations the Semantic standard defines and the resolver places.

`02-registration.sql.j2` writes the product's description of itself, each block only where its relation is placed:

- the product registry row from `product` (code, name, description, domain, version, owner, trust producer) and `orientation.access_mode`, with the manifest's consumer view as the approved entry point;
- the module map from `module_containers`, for object types the relation's vocabulary permits;
- the standard declaration: one `StandardDeclaration` row each for the standard, every deployed module and every applied pattern, from `standard.declarations`, with the platform and `standard.version`;
- entity and column metadata for every placed relation in `entities` and `relations`: the logical identity (`module.entity`, from `logical_id`, never a container or a prefix) as `entity_name`, placement, kind, profile, current and deleted flag columns, and per column the logical name, description, sensitivity marker, `classification`, `required`, declared type and Enum members;
- a `KeyDefinition` row for each of an entity's `key_defs` (surrogate, natural) and a `KeyColumn` row per ordered column, so a composite key is ordered rows and no delimited list;
- table relationships from `relationships`, between the logical identities of the source and target entities, and a `RelationshipColumn` row per ordered column pair (`pairs`). A nested `m.ref` is not supported inside a match, so the key of an entity is found by an explicit subselect (`key_ref`);
- access objects for every placed object of each relation, each with its `object_identity` (`module.entity:base`, `:governed` or `:current`; `module:object` for a similarity procedure), the logical `represents_entity` and `resolves_to_object`, with consumer views marked agent-consumable, and an `AccessColumn` row per column of each consumer view, from the same `view_columns` list the view selects;
- primary objects for every placed object with a `primary_role`;
- the orientation sequence from `orientation.resources`;
- metrics from `metrics`, with the rendered measure and filter as a Teradata expression and the dataset's consumer view;
- entity and column synonyms;
- naming standards from `naming`: each object template, the attribute template and each standard-name mapping.

Composite access objects (`access_objects`) are not registered; the manifest reports each as a gap.

`03-discovery.sql.j2` creates the standard-owned discovery views with `REPLACE VIEW` and `LOCKING ROW FOR ACCESS`, each only where the composition places it and the relations it reads:

- `ColumnCatalogue`: `DBC.ColumnsV` for the product's databases, left-joined to column metadata, with `description_source` `authored` or `missing`;
- `DataProductManifest`: the active registry row with one column per orientation resource role;
- `RelationshipPaths`: rows, one per step and key position, in the standard's column order (`path_id`, `origin_entity`, `destination_entity`, `hop_count`, `hop`, `key_ordinal`, `from_entity`, `from_column`, `to_entity`, `to_column`, `relationship_id`, `direction`). A leg is the relationship id followed by `>` (forward) or `<` (reverse) and `path_id` is the legs joined; the bound is `max_hops` (four) and a path never revisits an entity. Teradata views take no recursion or `WITH` clause and have no arrays, so each (path length, position) is its own branch of a `UNION ALL`, unrolled from the context's bound, with `path_id` built as text by concatenating each step's leg. Paths join the logical entities; resolve them through the access objects before issuing consumer SQL;
- `DataProductManifest` ends with `standard_version`, the version of the active `STANDARD` declaration row;
- `LineageGraph` and `LineageRunLatest` over Observability's active lineage definitions and their runs, the latest run chosen with `QUALIFY`.

Every text column a union produces is cast, because a union takes its column types from its first branch. Every view and every view column carries a comment.

`contract/` holds the five metadata-contract checks, declared as `contract <kind>` in the platform profile and rendered once for the Semantic module. Each returns one row per defect, as `object_identity` and `defect`:

| Check | Template | Returns |
|---|---|---|
| `contract-identity` | `contract/identity.sql.j2` | an entity identity outside the `module.entity` grammar (`REGEXP_SIMILAR`, case-sensitive) or outside its own module, a duplicate identity, an access identity that breaks the grammar or does not match its entity and surface (`INV-SEMANTIC-016`) |
| `contract-keys` | `contract/keys.sql.j2` | an entity with no key, a key with no columns, ordinals not running 1 to n, a key column absent from the entity (`INV-SEMANTIC-017`) |
| `contract-relationships` | `contract/relationships.sql.j2` | a relationship with no column pair, ordinals not running 1 to n, an unregistered entity, a pair column absent from its entity (`INV-SEMANTIC-018`) |
| `contract-access-columns` | `contract/access-columns.sql.j2` | a consumer view column with no mapping, a mapping naming no column or repeated, ordinals not running 1 to n, an absent non-derived source (`INV-SEMANTIC-019`) |
| `contract-composition` | `contract/composition.sql.j2` | a composite without exactly one anchor, members not ordered 1 to n, a member not joined to a prior member, an anchor carrying a join (`INV-SEMANTIC-020`) |

Columns of tables and views are read from `DBC.ColumnsV`; the shared macros are in `contract/00-macros.sql.j2`. The build does not execute Teradata, so these are verified by rendering, and by the shared engine tests when a system is attached.

`validation.sql.j2` is the `module semantic` check: every table in a database the product places objects in (`DBC.TablesV`, kinds `T` and `O`), keymaps included, is registered in entity metadata.

Registration uses the placement and relationships the context carries, never name inference. Structural facts come from the `DBC` dictionary views; meanings come from the specification.

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
| `INV-SEMANTIC-016..020` | The five `contract-*` checks, one mutation test each in the shared engine tests (skipped without a Teradata system). |
| `INV-SEMANTIC-013..015` | Metrics and synonyms registered from the specification; metric recipes execute in engine tests. Reference checks over the registrations remain to be written. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 5. Domain module (`domain`)

Templates: [`modules/domain/`](modules/domain/).

Binding of [Domain](../../design/modules/domain.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('domain')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). It emits one `CREATE MULTISET TABLE` per persisted Domain relation in the context's `entities` and `relations`, keymaps first so references to them resolve, and skips any the context marks `adopted` or not `defined`. It reads each relation's `objects.table`, `columns` (physical name and type, `required`, `unique`, `members`, `dimensions`), `kind`, `key_columns`, `natural_columns`, `version_columns`, `column_names`, `history`, `bitemporal`, `supports_deletion`, `generated_key` and `identity.keymap`.

- The primary index follows the access path: a keymap is read by its natural key (`UNIQUE PRIMARY INDEX`), a versioned table keeps every version of an identity on one AMP (`PRIMARY INDEX` on the version columns), and anything else is read by its key (`UNIQUE PRIMARY INDEX`).
- A relation with `generated_key` gets an identity column (`GENERATED BY DEFAULT AS IDENTITY`). Teradata allocates identity values in ranges per AMP, so they are unique but neither dense nor ordered.
- A versioned table is unique on its version columns plus `valid_from_dts` (and `transaction_from_dts` when bitemporal), and checks each interval is non-empty. Teradata has no exclusion constraint and no partial unique index, so one open version per identity and non-overlapping intervals are held by the `entity temporal` check, not by the schema.
- An entity with a keymap gets `FOREIGN KEY ... REFERENCES WITH NO CHECK OPTION` to the keymap: declared for the optimiser and for discovery, not enforced.
- An Enum attribute gets a `CHECK` over its members; a `Flag` is `BYTEINT` with a `CHECK (... IN (0, 1))`; text is `CHARACTER SET UNICODE`.

`02-key-allocation.sql.j2` is caller-rendered with `keymap` (a Keymap entity from the context) and `natural_value`. It renders two statements: a `MERGE` on the keymap's natural-key primary index, which Teradata requires a `MERGE` to match on, inserting the natural value only when it is new; then the `SELECT` of the stable identifier. Given `staged` instead, `{container, name, column}` naming a table the caller has written a set of natural values to (`container` null for a session-local table), it allocates the whole set in one `MERGE` over the staged set, still matched on the primary index, ignoring NULLs and duplicates and keeping every existing identifier, then returns each staged value with its identifier. Load a batch this way rather than one value at a time. Teradata is a set engine, and one value per request costs a round trip and a parse each. Only the first natural-key attribute (`identity.natural[0]`) is used. The caller runs both in one transaction.

Comments, governed and consumer views and statistics come from the temporal pattern; registration from Semantic; checks from Validation.

### Capability bindings

| Capability | Binding |
|---|---|
| `SurrogateKeyAllocation` | Identity column on each keymap or inline-keyed table; `02-key-allocation.sql.j2` returns the permanent identifier. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `PointInTimeReconstruction` | The governed base view carries the full temporal contract and is granted to the read and agent tiers; a read as at an instant applies the profile's predicates to it. Teradata SQL has no table functions, so there is no parameterised call. |
| `NaturalKeyLookup` | Unique primary index on each keymap's natural key; consumer views carry the stable identifier. |
| `EntityJoinBack` | Search and Prediction rows carry the Domain identifier; consumers join to the Domain consumer view. |
| `AccessView` | One consumer view per relation with a `consumer_view` object. |
| `RichMetadata` | `COMMENT ON` for every table and column, held to 255 characters, plus Semantic registration. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-DOMAIN-001` | `entity metadata` check: every placed column exists and carries a comment. |
| `INV-DOMAIN-002,006` | Current predicate in the consumer views; `entity temporal` check; engine test of a bitemporal correction read at two knowledge times through the governed view. |
| `INV-DOMAIN-003,004` | Permanent keymap with a declared foreign key; allocation test. Retention is operational. |
| `INV-DOMAIN-005,007` | Review the specification's attributes and relationships; no generic duplication detector is claimed. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 6. Observability module (`observability`)

Templates: [`modules/observability/`](modules/observability/).

Binding of [Observability](../../design/modules/observability.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('observability')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The relations are those the Observability standard defines and the resolver places: change events, quality metrics, lineage definitions and runs, model performance, agent outcomes, and the validation relations `ValidationRun` and `ValidationArea`. Event relations are append-only by profile; lineage definitions are current-state. Each gets a governed and a consumer view from the temporal pattern.

The module's views are rendered elsewhere: `LineageGraph` and `LineageRunLatest` by [Semantic discovery](#4-semantic-module-semantic), and `TrustMap` by [Validation](#9-validation-pattern-validation).

Capture is a producer obligation: deployers wire their ingestion, temporal writer and agent runtime to these stores. No trigger or synthetic quality score is emitted. The [access-layer template](#10-access-layer-pattern-access-layer) grants the agent tier `INSERT` on agent outcomes, the write target the context marks; validation evidence is written by [`validate.py`](../../tooling/bindings/README.md) using the placement the manifest carries. Privileged administration can bypass append-only intent. Retention is a settled design decision and an operator-managed process; no template deletes records.

### Capability bindings

| Capability | Binding |
|---|---|
| `ChangeEventCapture` | Append-only change-event table; the writer must emit events. |
| `AgentOutcomeCapture` | Append-only agent-outcome table; the agent tier may insert. |
| `LineageCapture` | Separate definition and run tables, with the lineage graph and latest-run views over active definitions. |
| `QualityScore` | Quality-metric time series, separate from validation evidence. |
| `GraphNativeLineageTraversal` | Not rendered: see below. A specification enabling `observability:graph-lineage` has it reported as a gap. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-OBS-001,002` | Standard-owned event structures hold table-level references and counts; producer payload review required. |
| `INV-OBS-003,006` | Separate definition and run tables; lineage views read active definitions only. |
| `INV-OBS-004` | Retention is a settled decision; operators prove enforcement. |
| `INV-OBS-005` | Wire 2.1 run and area records appended by the validator; engine tests of failures, errors, staleness, legacy runs and producer selection. |
| `INV-OBS-007..009` | Optional graph-native facet not rendered; no graph identity guarantee claimed. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

### Graph-lineage facet

Not bound. The templates for it, written for the flat template context that preceded the build context, were retired with the catalogue-interface binding; their last versions are in the history at commit `5fe4803`. A product that enables the facet has the exposure reported as a gap.

## 7. Search module (`search`)

Templates: [`modules/search/`](modules/search/).

Binding of [Search](../../design/modules/search.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('search')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). The embedding store holds identifiers, vectors and provenance, never source content.

A `Vector[n]` binds to `VARBYTE(n × 8)`: its elements as little-endian 8-byte floats, with a `CHECK (BYTES(...) = n × 8)` so a vector of the wrong dimension is refused. That is the encoding `TD_VECTORDISTANCE` reads directly; 4-byte floats in the same column are misread without an error (PLATFORM_PROFILE §7, Vectors). A producer packs a vector as `numpy.asarray(v, dtype="<f8").tobytes()` or `struct.pack(f"<{n}d", *v)` and binds it as a `VARBYTE` parameter.

`02-similarity.sql.j2` emits one stored procedure per `Embedding:` block in the context's `embeddings` that has an `objects.procedure`. It reads the block's `store` (through `named`), `vector_column`, `dimensions`, `similarity`, `threshold`, `name` and, where present, `model`, and the `Deploying user` binding setting. The procedure `(query_vector VARBYTE(n × 8), result_limit INTEGER)`:

- reads the store's consumer view, so only current vectors are ranked, restricted to rows whose source attribute is the block's name (and to its model, where the block names one);
- scores through `TD_VECTORDISTANCE`, with the store as the target table and the query as a one-row dimension, by the declared similarity, as every binding scores it: cosine and dot as `1 - distance` (the function's distances are `1 - cosine` and `1 - dot`), euclidean and manhattan as `1 / (1 + distance)`;
- returns no rows unless the query vector is exactly `n × 8` bytes and the limit is positive;
- keeps scores at or above the declared threshold and returns one result set of `(entity_id, similarity)`, ordered by score, then identifier, with the limit clamped to 0..1000.

`TD_VECTORDISTANCE` is a table operator: it cannot sit in a view or a SQL function, and it takes no bind or macro parameter inside its `ON` clauses. So the procedure writes the query vector into the request as a hex literal, left-padded because `FROM_BYTES` drops leading zero digits, and runs it as dynamic SQL. Each procedure carries a `COMMENT ON PROCEDURE`. A database's creator is not granted `CREATE PROCEDURE` on it, so where the profile names the `Deploying user`, the phase grants it on each database that holds a procedure. The access layer grants the read and agent tiers `EXECUTE PROCEDURE`; the procedure returns identifiers only, and join-back to Domain is the caller's (the cookbook's similarity recipe calls it with a `?` vector).

Vectors come from the encoder the specification declares, outside the database or in it; no encoder is substituted. An in-database encoder's output must be converted to 8-byte floats first: `mldb.ONNXEmbeddings`' `VARBYTE` output is 4-byte floats. Validate query vectors for finite elements and nonzero norm at the encoder and query boundary.

### Capability bindings

| Capability | Binding |
|---|---|
| `NearestNeighbors` | Exact ranking over current vectors through `TD_VECTORDISTANCE`, by the declared similarity and threshold. |
| `EntityJoinBack` | Results carry the Domain identifier; consumers join to the Domain consumer view. |
| `CurrentStateFilter` | The procedure reads the store's consumer view. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-SEARCH-001,003` | Review the declared embedding and model provenance; the vector `CHECK` enforces the dimension, with an engine test that a wrong one is refused. |
| `INV-SEARCH-002,004` | Engine test that the procedure ranks current vectors of its embedding and applies the threshold. |
| `INV-SEARCH-005` | Shared temporal macros and the `entity temporal` check. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 8. Prediction module (`prediction`)

Templates: [`modules/prediction/`](modules/prediction/).

Binding of [Prediction](../../design/modules/prediction.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`01-tables.sql.j2` calls `module_tables('prediction')` from the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata). It creates the feature and prediction entities the specification assigns to Prediction, with the columns, keys and temporal profile the context resolves for each. The temporal pattern adds their governed and consumer views.

No template computes features or scores. Product feature SQL must apply both effective and knowledge-time cutoffs to each source and respect observation and availability time. Definitions belong to Semantic and monitoring to Observability; Domain context is reached by identifier join-back, not copied into feature or prediction rows. Prediction tables begin empty: no score or model quality is fabricated.

Feature derivations the specification declares are rendered in the Teradata dialect where the binding declares every function they use. `hours_between` and `days_between` take both instants in UTC and are exact to the microsecond; `as_of` is not declared on any binding, so derivations using it are carried unrendered and reported.

### Capability bindings

| Capability | Binding |
|---|---|
| `PointInTimeReconstruction` | The governed base view carries the full temporal contract and is granted to the read and agent tiers; reads as at an instant apply the profile's predicates to it. Cutoff correctness is a product obligation. |
| `CurrentStateFilter` | Consumer view over current, undeleted rows. |
| `AccessView` | One consumer view per relation with a `consumer_view` object. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

### Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-PRED-001,003` | Review the specification's features; only engineered values and Domain identifiers belong here. |
| `INV-PRED-002` | The governed views support reconstruction; the product's feature pipeline must prove cutoff correctness. |
| `INV-PRED-004,005` | Semantic and Observability stores are separate; product capture and lineage checks remain required. |

Physical types come from the `[types]` table of [`binding.toml`](binding.toml). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.

## 9. Validation pattern (`validation`)

Templates: [`patterns/validation/`](patterns/validation/).

Binding of [Validation](../../design/patterns/validation.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Checks

Each check is a query whose every row is a defect. The `checks` of [`binding.toml`](binding.toml) names them, and [`render.py`](../../tooling/bindings/README.md) renders them into the manifest with test ids `{PRODUCT_CODE}-{CHECK}-{NNN}`:

| Check | Template | Rendered for | Returns |
|---|---|---|---|
| `entity metadata` | `01-entity-metadata.sql.j2` | each persisted relation (`entity`) | each placed column the table lacks or that has no comment, from `DBC.ColumnsV`. Teradata has no table constructor, so the expected columns are a union of one-row selects from `DBC.DBCInfoV` |
| `entity temporal` | `02-entity-temporal.sql.j2` | each persisted relation (`entity`) | identities with an empty interval, a current flag that disagrees with the open ends, overlapping versions (both axes when bitemporal), or a deletion flag without its instant |
| `relationship reference` | `03-relationship-reference.sql.j2` | each entry in `relationships` (`relationship`) | current source references with no current target, read through the consumer views (the tables where no view is placed); an optional reference may be null; a generic reference is checked only where its discriminator names this target |
| `module semantic` | [`modules/semantic/validation.sql.j2`](#4-semantic-module-semantic) | the Semantic module | unregistered tables |
| `module memory` | [`modules/memory/validation.sql.j2`](#3-memory-module-memory) | the Memory module | modules below the capture floor |
| `contract identity`, `contract keys`, `contract relationships`, `contract access-columns`, `contract composition` | [`modules/semantic/contract/`](#4-semantic-module-semantic) | once, for the Semantic module (`contract` scope); rendered as `contract-identity` and so on | the defects of the Semantic metadata contract (`INV-SEMANTIC-016` to `020`), as `object_identity` and `defect` |
| `product comment-coverage` | `05-comment-coverage.sql.j2` | once, for the product (`product` scope) | each database, table, view, macro, procedure, function and table or view column with no comment, read from `DBC.DatabasesV`, `DBC.TablesV` and `DBC.ColumnsV` over the containers the product creates (databases) and those that hold objects (objects and columns); an adopted container is not swept |

The reference check is current-surface coverage, not historical proof. A join of several columns resolves only when every pair matches, so the check tests all of them.

### Trust map

`04-trust-map.sql.j2` is a phase, not a check. Where the product places `TrustMap`, `ValidationRun`, `ValidationArea` and the product registry, it creates one `TrustMap` view with the same columns as every binding's:

- evidence is the area records joined to their run, plus one PRODUCT entry for each run at a registered legacy wire version (`quality.legacy_wire_versions`) with no area records, graded on the run's counts by Validation §4.3 and never above `partial` (`no-evidence` and `unknown` if the run had no checks);
- the registry's designated producer, where one is set, is the only producer read;
- the latest entry per producer and area wins (`QUALIFY`, latest completion, then run id); it is read at `unknown` confidence once past the run's `evidence_expires_dts`, or, without one, past its completion plus the product's evidence window (`quality.evidence_window_days`, which the resolver defaults to 7 days), written exactly as an `INTERVAL DAY(4) TO SECOND`;
- where no producer is designated, the most cautious producer's entry stands for each area;
- a product with no evidence at all reads `no-evidence` and `unknown`.

Teradata views take no `WITH` clause and no `ORDER BY`, so each step is a derived table, and a `NULL` in a union branch is cast to its column's type. The view and each of its columns carry a comment.

### Validator

[`validate.py`](../../tooling/bindings/README.md) connects with the teradatasql parameters in `TERADATA_DSN`, runs each check (a failed request rolls back only itself) and records an erroring check as `ERROR`, never as zero defects. Where the manifest places `ValidationRun` and `ValidationArea`, it appends one run and one area record per entity, module and the product in one transaction (wire schema 2.1). Failed `ERROR` or `CRITICAL` checks give weak confidence; a failed `WARNING` leaves partial. The gaps the manifest reports cap the PRODUCT area at partial. This is a structural profile, not a certification of business rules; add design-specific checks in the product workspace with explicit scope and provenance.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 10. Access Layer pattern (`access-layer`)

Templates: [`patterns/access-layer/`](patterns/access-layer/).

Binding of [Access Layer](../../design/patterns/access-layer.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

### Templates

`00-implied-grants.sql.j2` is the second phase, before any view. A view in one database compiles, and serves its readers, only once that database holds `SELECT WITH GRANT OPTION` on the database it reads; without it view creation fails with `[5315]`. The template derives each pair from what a view reads, from `entities`, `relations` and their placed `objects`: a base view reads its table; a consumer view reads its base view, or its table where there is none; a discovery view reads the Semantic and Observability tables it is built over. It grants nothing else, and never a database to itself.

`01-grants.sql.j2` is the last phase. It reads `principals` (the name of each of `ROLE_READ`, `ROLE_AGENT` and `ROLE_ADMIN`, and whether the build creates it), `product.name`, `grant_level`, `containers`, `module_containers` and the placed objects of `entities` and `relations`. In order it:

1. creates each principal the profile says to `create` as a role, with a comment naming who it is for, never what it reaches; an `existing` principal is used by name and not altered;
2. grants the admin tier `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, `DROP TABLE`, `CREATE VIEW`, `DROP VIEW` and `STATISTICS` on every database the product owns (never an adopted one) that holds objects (`ALL` carries `CREATE USER`, which Teradata grants to no role);
3. grants `SELECT` on consumer views to the read and agent tiers: per view at grant level `object`; at grant level `container`, on each database that holds consumer views and no tables, and per view where a database holds both, so a grant never reaches a table;
4. grants `SELECT` on the governed base view of every versioned relation with a consumer view to the read and agent tiers, one view at a time, so history is reachable as other bindings make it reachable through point-in-time functions (temporal-lifecycle-metadata §9); base views can share a database with tables, so these are never database grants;
5. for each table whose primary role is `WRITE_TARGET`: on a runtime Memory relation, `SELECT`, `INSERT` and `UPDATE` for the agent tier; on any other write target (agent outcomes), `INSERT`.

Runtime Memory is not restricted to the requesting identity's scope: Teradata has no row-level security in SQL, so the binding declares `Runtime scope: unsupported` and every build with runtime relations reports it.

The deploy script does not create users, assign passwords or grant roles to users; those are operator steps. Creating roles needs the `CREATE ROLE` right. Review the members of an `existing` role before binding a product to it.

### Capability bindings

| Capability | Binding |
|---|---|
| `AccessView` | Consumer views, and the governed views that carry history, are the read and agent tiers' only table-like surfaces; the engine tests read the read role's rights from `DBC.AllRoleRightsV`. |
| `ProductRoleAccess` | Roles named by the profile; grants per object or per database. Runtime scope enforcement is a reported gap. |

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## 11. Physical Storage pattern (`physical-storage`)

Binding of [Physical Storage](../../design/patterns/physical-storage.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

This pattern has no template. Every table is created in Teradata's own block storage: a `MULTISET` table with the primary index the [shared macros](#2-temporal-lifecycle-metadata-pattern-temporal-lifecycle-metadata) choose from its access path, and statistics collected on its key, versioning and temporal columns after deployment. No secondary, join or partitioned primary index, column partitioning or compression is emitted; those are chosen from measured workloads, following the advice in [PLATFORM_PROFILE.md](PLATFORM_PROFILE.md) §§1 to 6.

No table is placed in object storage. An organisation profile with the `Storage Section` headings (object storage under an open table format) is honoured by no template: the build creates its tables in block storage and reports the storage placement in the manifest as a gap.

Templates read only the build context: see [tooling/build](../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [`binding.toml`](binding.toml); coverage and gaps are in [CONFORMANCE.md](CONFORMANCE.md). Rendering uses StrictUndefined.

## Catalogue

<!-- catalogue:start -->

### Platform profile

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [Teradata Platform Profile](PLATFORM_PROFILE.md) *(advisory)* | `teradata` | draft | - | - | - |

<!-- catalogue:end -->
