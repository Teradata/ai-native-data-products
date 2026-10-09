---
title: DuckDB Validation Implementation
anchor: validation
type: implementation
status: draft
version: 2.0
normative: true
implements: validation
platform: duckdb
---

# DuckDB: Validation

Binding of [Validation](../../../../design/patterns/validation.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

`01-entity-check.sql.j2` returns physical-metadata defects (read from `duckdb_columns()`) and temporal defects; `02-relationship-check.sql.j2` checks current-surface reference coverage. Module validation templates add inventory and documentation coverage. The helper renders a check manifest for the actual product instead of a fixed test inventory. Each check is a query whose every row is a defect.

`04-trust-map.sql.j2` retains wire-schema 2.1 semantics: designated producer, latest evidence per area, expiry, cautious fallback and no-evidence/unknown. It requires Semantic and Observability. Other compositions can execute checks without persisting evidence; absence of a module must not create dangling SQL.

`tooling/bindings/validate.py` records errors without treating them as zero defects. DuckDB runs individual checks outside a caller transaction and publishes the run, area and check evidence in one transaction. Summaries are severity aware: failed ERROR or CRITICAL checks give weak confidence, a failed WARNING leaves partial. The shared fixture `tooling/bindings/tests/trust_cases.json` exercises the producer, and the trust-map view consumes the published areas in tests. It is a structural profile, not a certification of arbitrary business rules. Required documentation and unverified model or operational capabilities remain visible gaps. Add design-specific checks to the generated manifest in the product workspace, with explicit scope and provenance.

See [template inputs](../../TEMPLATE_INPUTS.md) and [conformance scope](../../CONFORMANCE.md). Every SQL template is rendered with StrictUndefined; SQL types, predicates and constraints are trusted builder-authored inputs.
