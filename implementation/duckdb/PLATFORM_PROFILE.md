---
title: DuckDB Platform Profile
anchor: duckdb
type: platform-profile
status: standard
version: 2.0
normative: false
platform: duckdb
---

# DuckDB platform binding

This binds the [design language](../../design/core/DESIGN_LANGUAGE.md) without changing it. Minimum **tested** engine: DuckDB **1.4.3**, pinned by the example. Other versions require the same build gates; no claim of forward compatibility replaces those gates.

## Deployment and lifecycle

DuckDB is an embedded analytical engine. The host opens a database file, writes transactions, checkpoints and closes it; clients then open the resulting file. One product owns one file and six module schemas. The file stem becomes the catalogue name: do not name it after a module (especially `memory`). A database can instead be transient; for in-memory experiments attach `':memory:' AS customer360`, select it, and detach the initial empty `memory` catalogue before deploying the Memory schema. The reference builder uses persistent files.

Use one writer process. Multiple threads within it can participate in optimistic concurrency; applications must retry conflicts. Multiple independent reader processes open read-only after the writer closes. Do not share a writable file between independent processes or treat a network filesystem as a database server. Promote a closed, checkpointed file to an environment-specific directory; retain an immutable prior release for rollback. Do not copy an active file without a consistent backup protocol. These choices follow DuckDB's [concurrency model](https://duckdb.org/docs/stable/connect/concurrency).

Inspect structure through `information_schema`, `duckdb_tables()`, `duckdb_views()`, `duckdb_columns()` and `duckdb_functions()`. Table and column comments carry authored meaning. Schemas/databases cannot be commented, and dependencies can prevent comment changes; apply comments before dependent objects. Semantic stores module descriptions and curated view-column meaning, so it does not depend on PostgreSQL comment behaviour. See [COMMENT ON](https://duckdb.org/docs/current/sql/statements/comment_on).

## Logical type bindings

| Design type | DuckDB type | Semantic constraints |
|---|---|---|
| Identifier | BIGINT | Permanent keymap allocation; never regenerate an id per version or recycle it. |
| Reference | BIGINT | Same physical type as target; generic references include a checked kind discriminator. |
| NaturalKey | VARCHAR | Required, immutable originating key; unique in keymap. |
| Code | VARCHAR | Validate against its registered Domain reference set. |
| ShortText / Text / LongText | VARCHAR | Product chooses limits with CHECK(length(...)); VARCHAR(n) does not enforce n. The demo has no arbitrary display-length cap. |
| Enum | VARCHAR + CHECK | Closed vocabulary; extend only through a reviewed model migration. |
| Flag / Boolean | BOOLEAN NOT NULL | Two values; null is not a third state. |
| Integer | INTEGER | BIGINT for counts that can exceed signed 32-bit; SMALLINT/TINYINT only after range proof. |
| Decimal(p,s) | DECIMAL(p,s) | Exact precision/scale; max precision 38. Scores add range checks. |
| Date | DATE | Calendar date, never substituted for a validity instant. |
| Timestamp | TIMESTAMPTZ | Microsecond instant; UTC session rendering. Stores the instant, not the original zone name. |
| Explicit zone-naive exception | TIMESTAMP | Only with a recorded decision and assumed zone in entity metadata; not used here. |
| Json | JSON | Flexible document values; STRUCT for stable typed structures in a specialised binding. |
| Vector[dim] | FLOAT[dim] | Separate physical table per dimension/model family; validate recorded dimensions and finite, nonzero vectors. |

All validity ends use `'infinity'::TIMESTAMPTZ`; event instants use null until the event occurs. The temporal writer preserves infinity through SQL instead of Python's finite `datetime.max` conversion.

## Capability matrix

Support describes the binding, not a promise that the standalone engine enforces application policy.

| Capability | DuckDB binding | Support | Limits / evidence |
|---|---|---|---|
| RichMetadata | COMMENT ON plus curated Semantic metadata | adapted | Schema and view-column meanings in explicit registries; META checks. |
| MetadataCoverageCheck | Catalogue anti-joins against authored columns | native | Checks physical comments and registration. |
| SurrogateKeyAllocation | Permanent keymaps and transactional serial writer | adapted | Host prevents keymap deletion; arbitrary admin SQL can bypass. |
| NaturalKeyLookup | Keymap uniqueness + current views | native | Stable identity across all history. |
| CurrentStateFilter | Explicit views over open validity, current flag and deletion | native | No lifecycle flag substitutes for currency. |
| PointInTimeReconstruction | Half-open table macros | adapted | Effective SCD2 history; as-known transaction-time correction is not provided. |
| SoftDelete | Tombstone successor, retained predecessors | adapted | Transactional writer, not automatic triggers. |
| EntityJoinBack | Identifier joins with checked kind | native | Search and Prediction keep no Domain content. |
| AccessView | Explicit projections, registered passthroughs/composites | native | A view is an interface, not a security boundary. |
| SemanticRegistration | Generated deployment inserts from model | adapted | No consumer-time DDL parsing. |
| DocumentationCapture | Six versioned documentation entities | adapted | Writer + capture minimum and provenance checks. |
| AgentContinuity | Scoped sessions, interactions, strategies, preferences, patterns | external/application-enforced | Privacy filtering/authentication belongs in host; no unrestricted runtime access surface. |
| NearestNeighbors / VectorSimilarity | array_cosine_similarity, ORDER BY, LIMIT | native | Exact scan; deterministic ties. |
| Embed | SQL toy lexical encoder; production model in host | adapted | Demonstrates the contract, not learned semantic quality. |
| ApproxIndex{IVF\|HNSW} | Optional VSS HNSW | unsupported in baseline | No IVF implementation; persistent HNSW excluded. |
| ChangeEventCapture | Append table-level change events | external/application-enforced | Writer must emit events; DuckDB has no automatic audit trigger here. |
| LineageCapture | Flow definitions + separate execution records | adapted | Table grain, independent retention. |
| AgentOutcomeCapture | Append aggregate outcomes | external/application-enforced | Host supplies actor identity and redacts query parameters. |
| QualityScore | Independent quality time series | native | No conflation with validation coverage. |
| ValidationResult | Append run/check/area evidence, wire 2.1 | adapted | Python runner catches execution errors; SQL consumers read published evidence. |
| ProductRoleAccess | Three logical tier records | external/application-enforced | Native roles/grants and row isolation unsupported. |
| GraphNativeLineageTraversal | Optional graph-lineage facet | unsupported | Not selected; active tabular edges remain available. |
| ColumnGrainLineageTraversal | Optional column-lineage facet | unsupported | Not selected; no external Graph Explorer dependency. |

## Security and extensions

The process identity governs file and network access. Read-only mode protects database writes, **not** table confidentiality or all host-side SQL effects. No native role DDL, grants, identity-aware privacy filtering or view-only access is claimed. An authenticated serving application must authorize queries, control external file/network access and append rights, and protect private Memory. Direct-file clients see all synthetic data. See [Access Layer](patterns/access-layer/) and DuckDB's [security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview).

Extensions execute code in the host. Pin and approve packages and repositories; restrict extension installation/loading and external access in a serving process. Baseline SQL neither installs VSS nor downloads models. DuckDB documents [persistent HNSW as experimental](https://duckdb.org/docs/current/core_extensions/vss#persistence); optional acceleration is a separate, rebuildable in-memory cache, never the authoritative file.

## Storage and portability

Internal columnar storage keeps the example self-contained. DuckDB can read/write Parquet and query remote objects through approved extensions such as httpfs; those assets, credentials and extension versions become external deployment dependencies. Do not assume a view over a Parquet path embeds its data. [Physical storage](patterns/physical-storage/) declares the optional export convention and external validation obligations. Match client/driver engine compatibility and test reopening after upgrades; no Teradata indexes, dictionary queries, locking clauses or database grants are translated.

## Settled design questions

One file/six schemas is the default; private runtime may require a separate protected file. Comments hold compact object/field meaning; explicit Semantic rows hold relationships, roles and orientation. SCD2 uses native timestamps and transactions; the host writer handles late splits and replay. Prediction rejects retrospective corrections instead of claiming bitemporal support. Fixed arrays use one dimension per table. Exact scans are portable; VSS is optional. External storage is an opt-in lifecycle dependency. A small explicit Python model renders checked plain SQL, so deployment requires no template engine. Catalogue generation now discovers platforms; Teradata's comment limit is applied only to that platform. The example captures these choices as Memory decisions, including the security and temporal departures.
