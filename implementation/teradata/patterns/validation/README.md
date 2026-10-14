---
title: Teradata Validation Pattern Implementation
anchor: validation
type: implementation
status: draft
version: 3.0
normative: true
implements: validation
platform: teradata
---

# Teradata: Validation

Binding of [Validation](../../../../design/patterns/validation.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Checks

Each check is a query whose every row is a defect. The `Checks:` block of [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations) names them, and [`render.py`](../../../../tooling/bindings/README.md) renders them into the manifest with test ids `{PRODUCT_CODE}-{CHECK}-{NNN}`:

| Check | Template | Rendered for | Returns |
|---|---|---|---|
| `entity metadata` | `01-entity-metadata.sql.j2` | each persisted relation (`entity`) | each placed column the table lacks or that has no comment, from `DBC.ColumnsV`. Teradata has no table constructor, so the expected columns are a union of one-row selects from `DBC.DBCInfoV` |
| `entity temporal` | `02-entity-temporal.sql.j2` | each persisted relation (`entity`) | identities with an empty interval, a current flag that disagrees with the open ends, overlapping versions (both axes when bitemporal), or a deletion flag without its instant |
| `relationship reference` | `03-relationship-reference.sql.j2` | each entry in `relationships` (`relationship`) | current source references with no current target, read through the consumer views (the tables where no view is placed); an optional reference may be null; a generic reference is checked only where its discriminator names this target |
| `module semantic` | [`modules/semantic/validation.sql.j2`](../../modules/semantic/README.md) | the Semantic module | unregistered tables |
| `module memory` | [`modules/memory/validation.sql.j2`](../../modules/memory/README.md) | the Memory module | modules below the capture floor |
| `contract identity`, `contract keys`, `contract relationships`, `contract access-columns`, `contract composition` | [`modules/semantic/contract/`](../../modules/semantic/README.md) | once, for the Semantic module (`contract` scope); rendered as `contract-identity` and so on | the defects of the Semantic metadata contract (`INV-SEMANTIC-016` to `020`), as `object_identity` and `defect` |
| `product comment-coverage` | `05-comment-coverage.sql.j2` | once, for the product (`product` scope) | each database, table, view, macro, procedure, function and table or view column with no comment, read from `DBC.DatabasesV`, `DBC.TablesV` and `DBC.ColumnsV` over the containers the product creates (databases) and those that hold objects (objects and columns); an adopted container is not swept |

The reference check is current-surface coverage, not historical proof, and compares the first target column only.

## Trust map

`04-trust-map.sql.j2` is a phase, not a check. Where the product places `TrustMap`, `ValidationRun`, `ValidationArea` and the product registry, it creates one `TrustMap` view with the same columns as every binding's:

- evidence is the area records joined to their run, plus one PRODUCT entry for each run at a registered legacy wire version (`quality.legacy_wire_versions`) with no area records, graded on the run's counts by Validation §4.3 and never above `partial` (`no-evidence` and `unknown` if the run had no checks);
- the registry's designated producer, where one is set, is the only producer read;
- the latest entry per producer and area wins (`QUALIFY`, latest completion, then run id); it is read at `unknown` confidence once past the run's `evidence_expires_dts`, or, without one, past its completion plus the product's evidence window (`quality.evidence_window_days`, which the resolver defaults to 7 days), written exactly as an `INTERVAL DAY(4) TO SECOND`;
- where no producer is designated, the most cautious producer's entry stands for each area;
- a product with no evidence at all reads `no-evidence` and `unknown`.

Teradata views take no `WITH` clause and no `ORDER BY`, so each step is a derived table, and a `NULL` in a union branch is cast to its column's type. The view and each of its columns carry a comment.

## Validator

[`validate.py`](../../../../tooling/bindings/README.md) connects with the teradatasql parameters in `TERADATA_DSN`, runs each check (a failed request rolls back only itself) and records an erroring check as `ERROR`, never as zero defects. Where the manifest places `ValidationRun` and `ValidationArea`, it appends one run and one area record per entity, module and the product in one transaction (wire schema 2.1). Failed `ERROR` or `CRITICAL` checks give weak confidence; a failed `WARNING` leaves partial. The gaps the manifest reports cap the PRODUCT area at partial. This is a structural profile, not a certification of business rules; add design-specific checks in the product workspace with explicit scope and provenance.

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
