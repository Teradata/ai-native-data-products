---
title: DuckDB Platform Profile
anchor: duckdb
type: platform-profile
status: draft
version: 3.0
normative: false
platform: duckdb
---

# DuckDB platform binding

This binds the [design language](../../design/core/DESIGN_LANGUAGE.md) and the [implementation authoring standard](../../design/core/IMPLEMENTATION_AUTHORING.md) without changing them. The module and pattern directories bind platform-neutral contracts through Jinja; no product model is selected by this profile.

## 1. Engine versions and driver constraints

Target DuckDB 1.4 or later. The suite has been run against DuckDB **1.5.6** through the Python driver; other versions are untested, and a target version is not itself proof of a native execution matrix. Tooling needs Python 3.10+ and Jinja2 3.1. Match client and driver engine versions and test reopening a file after any upgrade. Record the versions tested in [CONFORMANCE.md](CONFORMANCE.md).

## 2. Binding settings

| Setting | Values | Default | Notes |
|---|---|---|---|
| containers | One DuckDB schema per selected module plus an access schema | None; required | Supplied by placement. No names are inferred. |
| roles | Not supported | None | DuckDB has no roles or grants. Supplying `roles` fails the build as an unsupported setting. |
| key_sequence (per entity) | Identifier-safe name | `<keymap or entity name>_seq` | Resolved by the build tooling. |
| runtime_memory | true, false | false | Whether the standard Memory runtime tables are rendered. |

## 3. Deployment and lifecycle

DuckDB is an embedded analytical engine. The host opens a database file, writes transactions, checkpoints and closes it; clients then open the resulting file. One product owns one file and one schema per module plus an access schema. The file stem becomes the catalogue name: do not name it after a module (especially `memory`).

Use one writer process. Multiple threads within it can participate in optimistic concurrency; applications must retry conflicts. Independent reader processes open read-only after the writer closes. Do not share a writable file between processes or treat a network filesystem as a database server. Promote a closed, checkpointed file to an environment-specific directory and keep an immutable prior release for rollback. These choices follow DuckDB's [concurrency model](https://duckdb.org/docs/stable/connect/concurrency).

Structure is inspected through `information_schema`, `duckdb_tables()`, `duckdb_views()`, `duckdb_columns()` and `duckdb_functions()`; always restrict to `current_database()`. Table, view and column comments carry authored meaning. Schemas and databases cannot be commented, and dependencies can block comment changes, so comments are applied after the tables and before dependent objects. Semantic stores module descriptions and curated meaning. See [COMMENT ON](https://duckdb.org/docs/current/sql/statements/comment_on).

## 4. Type bindings

| Logical type | Physical binding | Constraints |
|---|---|---|
| Identifier / Reference | BIGINT | Permanent keymap allocation by sequence; never regenerate an id per version or recycle it. |
| NaturalKey / Code / Text | VARCHAR | VARCHAR(n) does not enforce n; use a CHECK on length where a limit matters. |
| Enum | VARCHAR plus CHECK | Closed vocabulary declared as an entity column check. |
| Integer / Decimal | INTEGER / DECIMAL(p,s) | Exact precision and scale; maximum precision 38. |
| Flag | BOOLEAN | NOT NULL; two values only. |
| Date | DATE | Calendar date, never a validity instant. |
| Timestamp | TIMESTAMPTZ | Microsecond instant; UTC sessions (`deploy.sql` sets `TimeZone`). Stores the instant, not a zone name. |
| Vector[n] | FLOAT[n] | Fixed-size array; one dimension per model family. Compare vectors only within one model space. |
| Process JSON | JSON | Flexible documents. |

All validity ends use `'infinity'::TIMESTAMPTZ`; event instants are null until the event occurs. The Python driver converts infinity to a finite datetime, so pass open ends as the text `infinity` rather than round-tripping them.

## 5. Temporal integrity

Half-open valid and optional knowledge intervals; infinity is confined to interval boundaries. DuckDB has no exclusion constraints and no partial unique indexes, so non-overlap and "one current row" are checked, not enforced: generated checks detect violations, and writers must be serialized. Bitemporal history retains old knowledge; it cannot be replaced with ordinary SCD2 when the design requires correction semantics. Primary keys include `valid_from_dts` and, for bitemporal, `transaction_from_dts`.

## 6. Physical storage

Native columnar storage in one file. Start unindexed beyond key constraints and choose layout from measured workload. Parquet, httpfs or other extension-based storage is not rendered and, if adopted, is an external dependency with its own version, credential and validation obligations.

## 7. Access boundary

Native roles, grants, view-only access and row isolation are **unsupported**. The process identity governs file and network access. Read-only mode protects writes, not confidentiality. An authenticated serving application must authorise queries, control external access, bound append rights and protect private Memory; direct-file clients see everything. See [Access Layer](patterns/access-layer/README.md) and DuckDB's [security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview).

## 8. Extensions

Extensions execute code in the host: pin and approve packages and restrict loading in a serving process. The templates neither install nor load any extension and download no model. DuckDB documents [persistent HNSW as experimental](https://duckdb.org/docs/current/core_extensions/vss#persistence); an optional approximate index would be a separate, rebuildable in-memory cache and is not emitted.

## 9. Capabilities and gaps

| Capability | Binding | Support |
|---|---|---|
| Rich metadata | COMMENT ON plus curated Semantic registration | adapted |
| Surrogate keys | Sequence-backed permanent keymaps; serial writer | adapted |
| Current state, as-of, soft delete | Explicit views and half-open table macros | native |
| Exact similarity | `list_cosine_similarity` table macro with Domain join-back | native |
| Approximate similarity index | Not emitted | unsupported |
| Embedding and model execution | A separate product implementation | external |
| Change, outcome and lineage capture | Stores only; producers write them | external |
| Validation evidence | Wire 2.1 append by `tooling/bindings/validate.py`; SQL trust-map consumer | adapted |
| Role access and runtime privacy | None in the engine | unsupported |
| Graph-native and column-grain lineage facets | Not selected | unsupported |

## 10. SQL idioms and driver constraints

Use quoted identifiers and escaped literals through the documented filters. Use `?` parameters for data values through the driver. History surfaces are table macros with untyped parameters; pass typed timestamps. Fixed-size arrays enforce their dimension at insert. Render StrictUndefined templates with a loader rooted at this platform directory. Type and constraint expressions are builder-authored SQL, not user data. Run DuckDB checks in autocommit mode so that one failed query does not poison the following checks.

---

## Binding declarations

The declarations the build-context resolver reads for this platform ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §5.1): quoting, the object roles this binding emits beyond tables and views, its physical type for each logical type, and its SQL for each expression function. A function with no line is not rendered by this binding; an expression that uses one is carried unrendered and reported as a gap.

```
Binding: -
  Identifier quote: "
  Literal quote:    '
  Principals:       unsupported
  Emits:
    sequence: keymap, inline
    function: SCD2_HISTORY, ASSOCIATION_SCD2, SCD2_BITEMPORAL
```

```
Types: -
  Identifier: BIGINT
  Reference:  BIGINT
  NaturalKey: VARCHAR
  Code:       VARCHAR
  ShortText:  VARCHAR
  Text:       VARCHAR
  LongText:   VARCHAR
  Json:       JSON
  Enum:       VARCHAR
  Integer:    INTEGER
  Decimal:    DECIMAL({p},{s})
  Timestamp:  TIMESTAMPTZ
  Date:       DATE
  Flag:       BOOLEAN
  Vector:     FLOAT[{dim}]
```

```
Functions: -
  sum: SUM({0})
  avg: AVG({0})
  min: MIN({0})
  max: MAX({0})
  count: COUNT({0})
  count_distinct: COUNT(DISTINCT {0})
  count_rows: COUNT(*)
  ratio: ({0}) / NULLIF({1}, 0)
  completeness/1: AVG(CASE WHEN {0} IS NOT NULL THEN 1.0 ELSE 0.0 END)
  completeness/2: AVG(CASE WHEN {1} THEN CASE WHEN {0} IS NOT NULL THEN 1.0 ELSE 0.0 END END)
  validity: AVG(CASE WHEN {0} THEN 1.0 ELSE 0.0 END)
  consistency: AVG(CASE WHEN {0} THEN 1.0 ELSE 0.0 END)
  map/2: CASE {0} {cases} ELSE NULL END
  map case: WHEN {key} THEN {value}
  when: CASE WHEN {0} THEN {1} ELSE {2} END
  coalesce: COALESCE({args})
  is_null: ({0} IS NULL)
  is_not_null: ({0} IS NOT NULL)
  null: NULL
  concat: CONCAT_WS(' ', {args})
  length: length({0})
  hours_between: date_diff('second', {0}, {1}) / 3600.0
  days_between: date_diff('second', {0}, {1}) / 86400.0
  hour_of_day: hour(timezone('UTC', {0}))
  day_of_week: (isodow(timezone('UTC', {0})) - 1)
  as_flag: ({0})
  duration: INTERVAL '{n} {unit}'
  true: TRUE
  false: FALSE
```
