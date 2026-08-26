---
title: Teradata Validation Pattern Implementation
anchor: validation
type: implementation
status: standard
version: 2.1
normative: true
implements: validation
platform: teradata
---

# Teradata: Validation Implementation

Teradata binding of [`design/patterns/validation.md`](../../../../design/patterns/validation.md). Validation results are operational evidence and live in the **Observability** module, alongside its other run/event tables. Wire schema 2.1 is canonical (additive over 2.0); 1.0 is a registered legacy binding.

## Files

| File | Purpose |
|------|---------|
| `01-validation-run.sql` | The `validation_run` append-only history table (profile `EVENT_APPEND_ONLY`) and its statistics: the run-level summary. |
| `02-views.sql` | `validation_latest`: the latest-per-(product, producer) run projection. |
| `03-validation-area.sql` | The `validation_area` append-only trust map: one row per run per area, with its vocabularies CHECK-constrained. |
| `04-trust-map-views.sql` | `validation_trust_map`: the latest entry per (product, producer, area), coverage and staleness derived on read against each area's own run, plus the derived `PRODUCT` entry for a 2.0/1.0 producer. |
| `consumer-queries.sql` | The map read before analytical use (reconciled against the caller's requested scopes, so a missing area reads as explicit `no-evidence` rather than disappearing), the whole map, the most-cautious composite, run-level evidence-age context, advisory summary, failure detail, per-area and run trends. |
| `conformance-queries.sql` | `DBC`/data checks for the VAL conformance rules. `{sem}` tags the product's Semantic container where `PRODUCT`, `MODULE`, and `ENTITY` scopes are resolved; `PATTERN`/`CAPABILITY` have no deployed catalogue and are a producer build-time assertion instead. |

Deploy in file order: the views project the tables above them.

## Type bindings

| Contract element | Teradata binding |
|------------------|------------------|
| `*_dts` run instants | `TIMESTAMP(6) WITH TIME ZONE`, persisted UTC (schema 2.0 onward: typed, so latest-run ordering is chronological). |
| `agent_use_allowed` | `BYTEINT` 0/1, CHECK-constrained. Deprecated at 2.1: published as 1, never read. |
| Scores | `INTEGER` nullable (null = not assessed). |
| JSON blobs | `JSON(32000) CHARACTER SET UNICODE`, cap discipline applied before truncation. |
| `scope_kind`, `area_status`, `confidence` | `VARCHAR` CHARACTER SET LATIN with a CHECK constraint per closed vocabulary, so an invalid value fails at insert rather than at read. |
| `open_gaps`, `recommended_action` | `VARCHAR(1000) CHARACTER SET UNICODE`: prose an agent reports verbatim. |
| Coverage ratio | Derived in `validation_trust_map` as `DECIMAL(9,4)`, never stored: one copy of the fact. |

## Publish semantics

Append, never replace: each run inserts exactly one `validation_run` row (VAL-09) and one `validation_area` row per area its profile covers, including the areas it could not check (VAL-18). `run_id` is deterministic (first 32 hex of a SHA-256 over `prefix|producer_id|started_iso|completed_iso|result_count`) and is what ties the area rows to their run. Consumers read through `LOCKING ROW FOR ACCESS` views, never the base tables.

The authoritative map is the set of rows whose `producer_id` matches the trust-authoritative producer designated in the product's orientation metadata; other producers' rows are evidence. Nothing in either relation withholds use of the product: a consumer reads the areas it is about to query, proceeds, and discloses their confidence and gaps.

## Regression tests

The read path is logic, and the review of this pattern's #57 revision found three defects in it that inspection had missed: staleness graded against the wrong run, a legacy fallback that swallowed a malformed run, and a requested area that vanished instead of reporting itself unknown. [`tooling/validation/tests/test_trust_map.py`](../../../../tooling/validation/tests/test_trust_map.py) states each as a behaviour and executes it:

```bash
python -m unittest discover -s tooling/validation/tests
```

The SQL is **read from the files in this directory**, never retyped, and translated onto stdlib `sqlite3` by [`td_sqlite.py`](../../../../tooling/validation/tests/td_sqlite.py) so nothing in `tooling/` needs a live platform. Reverting a fix here fails those tests. Two consequences worth knowing before changing anything in this directory:

- **A new Teradata construct breaks the harness loudly.** The translator handles an explicit, narrow set of rewrites and raises `UntranslatedSql` on anything else, rather than dropping the clause it was load-bearing in. Extend it in the same commit.
- **It does not test Teradata's semantics.** `QUALIFY` becomes a wrapped `ROW_NUMBER`, `INTERVAL` becomes date arithmetic, and a zone-qualified timestamp becomes ISO text: faithful for the comparisons the map makes, not in general. Platform conformance stays `conformance-queries.sql` run against the deployed product; the suite is the net underneath it.

## Legacy binding (wire schema 1.0)

1.0 publishes the same status/count/score/JSON columns without the producer-identity, `source_format`, `payload_schema_version`, or audit columns, with run timestamps as `VARCHAR(40)` ISO-8601 (`started_at`/`completed_at`) under producer-specific object names in the **Semantic** module (`trust_engine_run` / `trust_engine_latest`). Migration is a re-publish (start inserting into `validation_run` with identity populated; repoint orientation), not a rename.

## Check sources lifted into validator profiles

Scope comes from ownership: a check belongs to the area of the document or directory that states it, so these suites acquire their scope without being rewritten (design §12).

| Source | Checks | Category / severity | Area |
|--------|--------|---------------------|------|
| Temporal & lifecycle pattern | TLM-04/05/06 dictionary; TLM-08/09/10/11 data invariants | STRUCTURAL / `[B]` → CRITICAL | `PATTERN:temporal-lifecycle-metadata`, or the entity a data check resolves |
| Semantic module | Orphan modules, missing objects, invalid roles, kind mismatches, duplicate registrations | SEMANTIC / STRUCTURAL, ERROR-CRITICAL | `MODULE:semantic` |
| Object-placement pattern | Container and naming conformance | STRUCTURAL, WARNING-ERROR | `PATTERN:object-placement` |
| Each module's `INV-*` checks | The per-module `validation.sql.j2` invariant checks | per the module | `MODULE:{module}` |
| This pattern's own conformance queries | The VAL rules above | STRUCTURAL, ERROR | `PATTERN:validation` |

An area whose only check is unwritten is published at `checks_expected = 0`, which reads as `no-evidence`: Observability, object-placement and physical-storage ship none today, and the map is where that becomes visible rather than assumed clean.
