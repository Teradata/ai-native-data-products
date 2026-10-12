---
title: PostgreSQL Platform Profile
anchor: postgres
type: platform-profile
status: draft
version: 2.0
normative: false
platform: postgres
---

# PostgreSQL platform profile

## 1. Scope

Target PostgreSQL 16+. The module and pattern directories bind platform-neutral contracts through Jinja; no product model is selected by this profile.

## 2. Type bindings

| Logical type | Physical binding |
|---|---|
| Identifier / Reference | BIGINT |
| NaturalKey / Code / Text | VARCHAR or TEXT |
| Integer / Decimal | INTEGER / DECIMAL(p,s) |
| Flag | BOOLEAN |
| Timestamp / Date | TIMESTAMPTZ / DATE; UTC sessions |
| Vector[n] | DOUBLE PRECISION[] with explicit dimension checks |
| Process JSON | JSONB |

## 3. Temporal integrity

Half-open valid and optional knowledge intervals; infinity is confined to interval boundaries. GiST exclusion with btree_gist enforces non-overlap across both axes. Partial unique indexes enforce one current row. Bitemporal history retains old knowledge; it cannot be replaced with ordinary SCD2 when the design requires correction semantics.

## 4. Physical storage

Start with native storage and unpartitioned small tables. Index and partition only from measured workload requirements; establish backup/restore and operational evidence separately.

## 5. Access boundary

Native roles, view grants and USER RLS are emitted. Identity is session_user; owners/superusers remain privileged. Shared scopes require a separate membership policy.

## 6. Capabilities and gaps

Exact cosine retrieval joins vectors back to Domain. Encoder/model execution and predictive quality require explicit product implementations; approximate indexing is optional. Runtime identity, storage operations and performance are not certified by schema checks. See CONFORMANCE.md.

## 7. SQL Idioms and Driver Constraints

Use quoted identifiers and escaped literals through the documented filters. Use Psycopg %s parameters for data values and savepoints after query errors. Arrays do not enforce declared dimensions without checks. JSONB supports equality used by conformance. Historical surfaces are SQL functions with typed timestamp arguments; bitemporal surfaces take both valid_at and known_at. Render StrictUndefined templates with a loader rooted at this platform directory. Type/constraint expressions are builder-authored SQL, not user data.

Runtime versions tested are recorded in CONFORMANCE.md; a target version is not itself proof of a native execution matrix.

---

## Binding declarations

The declarations the build-context resolver reads for this platform ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §5.1): quoting, the object roles this binding emits beyond tables and views, its physical type for each logical type, and its SQL for each expression function. A function with no line is not rendered by this binding; an expression that uses one is carried unrendered and reported as a gap.

```
Binding: -
  Identifier quote: "
  Literal quote:    '
  Principals:       native
  Emits:
    function: SCD2_HISTORY, ASSOCIATION_SCD2, SCD2_BITEMPORAL
```

```
Types: -
  Identifier: BIGINT
  Reference:  BIGINT
  NaturalKey: VARCHAR
  Code:       VARCHAR
  ShortText:  VARCHAR
  Text:       TEXT
  LongText:   TEXT
  Json:       JSONB
  Enum:       VARCHAR
  Integer:    INTEGER
  Decimal:    DECIMAL({p},{s})
  Timestamp:  TIMESTAMPTZ
  Date:       DATE
  Flag:       BOOLEAN
  Vector:     DOUBLE PRECISION[]
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
  length: CHAR_LENGTH({0})
  hours_between: EXTRACT(EPOCH FROM ({1} - {0})) / 3600.0
  days_between: EXTRACT(EPOCH FROM ({1} - {0})) / 86400.0
  hour_of_day: EXTRACT(HOUR FROM {0} AT TIME ZONE 'UTC')
  day_of_week: (EXTRACT(ISODOW FROM {0} AT TIME ZONE 'UTC') - 1)
  as_flag: ({0})
  duration: INTERVAL '{n} {unit}'
  true: TRUE
  false: FALSE
```
