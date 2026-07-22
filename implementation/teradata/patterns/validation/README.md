# Teradata — Validation Implementation

Teradata binding of [`design/patterns/validation.md`](../../../../design/patterns/validation.md).
Validation results are operational evidence and live in the **Observability** module, alongside its
other run/event tables. Wire schema 2.0 is canonical; 1.0 is a registered legacy binding.

## Files

| File | Purpose |
|------|---------|
| `01-validation-run.sql` | The `validation_run` append-only history table (profile `EVENT_APPEND_ONLY`) and its statistics. |
| `02-views.sql` | `validation_latest` — the latest-per-(product, producer) gate/evidence projection. |
| `consumer-queries.sql` | Gate check before analytical use, all-producer evidence summary, run-history trend. |
| `conformance-queries.sql` | `DBC`/data checks for the VAL conformance rules. |

## Type bindings

| Contract element | Teradata binding |
|------------------|------------------|
| `*_dts` run instants | `TIMESTAMP(6) WITH TIME ZONE`, persisted UTC (schema 2.0 — typed, so latest-run ordering is chronological). |
| `agent_use_allowed` | `BYTEINT` 0/1, CHECK-constrained. |
| Scores | `INTEGER` nullable (null = not assessed). |
| JSON blobs | `JSON(32000) CHARACTER SET UNICODE`, cap discipline applied before truncation. |

## Publish semantics

Append, never replace — each run inserts exactly one row (VAL-09). `run_id` is deterministic (first
32 hex of a SHA-256 over `prefix|producer_id|started_iso|completed_iso|result_count`). Consumers read
through `LOCKING ROW FOR ACCESS` views, never the base table. The product-level gate is the row whose
`producer_id` matches the gate-authoritative producer designated in the product's orientation
metadata; other rows are evidence.

## Legacy binding (wire schema 1.0)

1.0 publishes the same status/count/score/JSON columns without the producer-identity, `source_format`,
`payload_schema_version`, or audit columns, with run timestamps as `VARCHAR(40)` ISO-8601
(`started_at`/`completed_at`) under producer-specific object names in the **Semantic** module
(`trust_engine_run` / `trust_engine_latest`). Migration is a re-publish (start inserting into
`validation_run` with identity populated; repoint orientation), not a rename.

## Check sources lifted into validator profiles

| Source | Checks | Category / severity |
|--------|--------|---------------------|
| Temporal & lifecycle pattern | TLM-04/05/06 dictionary; TLM-08/09/10/11 data invariants | STRUCTURAL / blocking → CRITICAL |
| Semantic module | Orphan modules, missing objects, invalid roles, kind mismatches, duplicate registrations | SEMANTIC / STRUCTURAL, ERROR–CRITICAL |
| Object-placement pattern | Container and naming conformance | STRUCTURAL, WARNING–ERROR |
| Each module's `INV-*` checks | The per-module `validation.sql` invariant checks | per the module |
