---
title: DuckDB Validation Implementation
anchor: validation
type: implementation
status: standard
version: 2.0
normative: true
implements: validation
platform: duckdb
---

# DuckDB validation evidence

Binding of [validation](../../../../design/patterns/validation.md). [checks.py](../../checks.py) defines executable violation queries with stable test ids, owner scope, category and severity. [validate.py](../../validate.py) executes them and appends `observability.validation_run`, `validation_area` and `validation_check`. The schema is 2.1, with canonical names, producer/profile identity, actual execution instants, authoritative counts and separate status/severity axes.

The count-only producer leaves readiness scores and optional capped JSON null, and proposes no automatic repairs. Full failing counts and execution errors remain in validation_check. SQL failures become ERROR results rather than disappearing. Run and area publication is transactional; prior evidence is retained. `views.sql` selects latest-per-area deterministically by completed_dts/run_id and uses that area's parent expiry, not the newest unrelated run. Expired evidence becomes unknown with a rerun action. The product names exactly one authoritative producer.

Run `python implementation/duckdb/validate.py <database>` for persisted evidence; use [conformance.sql](conformance.sql) for read-only CLI violation counts. A nonzero count or execution error fails the fixture publication gate. This is a build integrity check, **not** a consumer access gate. `agent_use_allowed` is always `go`, retained only for compatibility; consumers do not branch on it.

The profile covers every module, temporal metadata, object placement and validation. External security, external storage operations and embedding quality have explicit no-evidence areas. Scores are not fabricated for unassessed quality. Strong means the defined checks passed, not that all possible operational risks were tested. Table-model allowlists detect new content columns outside Domain; code review must still assess the semantic meaning of newly approved fields.

Producer and consumer tests share [trust_cases.json](../../tests/trust_cases.json), testing empty, partial, warning, error and full coverage plus SQL staleness/producer selection. The module [conformance map](../../CONFORMANCE.md) distinguishes SQL checks, behavioural tests and external obligations. No golden wire 1.0/2.0 importer is shipped: this producer accepts native 2.1 only. Clients ingesting other producers must implement the standard's legacy compatibility and cautious fallback before treating those records as authoritative.
