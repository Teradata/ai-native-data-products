---
title: PostgreSQL Validation Implementation
anchor: validation
type: implementation
status: draft
version: 2.0
normative: true
implements: validation
platform: postgres
---

# PostgreSQL: Validation

Binding of [Validation](../../../../design/patterns/validation.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Checks

Each check is a query whose every row is a defect. The `Checks:` block of [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations) names them, and [`render.py`](../../../../tooling/bindings/README.md) renders them into the manifest with test ids `{PRODUCT_CODE}-{CHECK}-{NNN}`:

| Check | Template | Rendered for | Returns |
|---|---|---|---|
| `entity metadata` | `01-entity-metadata.sql.j2` | each persisted relation (`entity`) | each placed column the table lacks or that has no comment, from `information_schema.columns` and `col_description` |
| `entity temporal` | `02-entity-temporal.sql.j2` | each persisted relation (`entity`) | identities with an empty interval, a current flag that disagrees with the open ends, overlapping versions (both axes when bitemporal), a deletion flag without its instant, or a non-finite timestamp outside the interval ends |
| `relationship reference` | `03-relationship-reference.sql.j2` | each entry in `relationships` (`relationship`) | current source references with no current target, read through the consumer views (the tables where no view is placed); an optional reference may be null |
| `module semantic` | [`modules/semantic/validation.sql.j2`](../../modules/semantic/README.md) | the Semantic module | unregistered base tables |
| `module memory` | [`modules/memory/validation.sql.j2`](../../modules/memory/README.md) | the Memory module | modules below the capture floor |
| `contract identity` | [`modules/semantic/contract/identity.sql.j2`](../../modules/semantic/README.md) | the Semantic module | identities that break the grammar, carry the wrong module qualifier or are registered twice |
| `contract keys` | `modules/semantic/contract/keys.sql.j2` | the Semantic module | entities with no key, keys with no columns, ordinals that do not run 1 to n, and key columns the entity lacks |
| `contract relationships` | `modules/semantic/contract/relationships.sql.j2` | the Semantic module | relationships with no column pair, gaps in the ordinals, unregistered entities and columns the entities lack |
| `contract access-columns` | `modules/semantic/contract/access-columns.sql.j2` | the Semantic module | consumer-view columns with no mapping row, mappings for columns the view lacks, repeated or gapped ordinals, and absent sources |
| `contract composition` | `modules/semantic/contract/composition.sql.j2` | the Semantic module | composites without exactly one anchor, gapped member order, and members not joined to a prior member through a registered relationship |
| `product comment-coverage` | `05-comment-coverage.sql.j2` | the product | every container, object and column of the product's containers with no comment (the catalogue-wide `MetadataCoverageCheck`) |

The reference check is current-surface coverage, not historical proof. A join of several columns resolves only when every pair matches, so the check tests all of them.

## Trust map

`04-trust-map.sql.j2` is a phase, not a check. Where the product places `TrustMap`, `ValidationRun`, `ValidationArea` and the product registry, it creates one `TrustMap` view:

- evidence is the area records joined to their run, plus one PRODUCT entry for each run at a registered legacy wire version (`quality.legacy_wire_versions`) with no area records, graded on the run's counts by Validation §4.3 and never above `partial` (`no-evidence` and `unknown` if the run had no checks);
- the registry's designated producer, where one is set, is the only producer read;
- the latest entry per producer and area wins; it is read at `unknown` confidence once past the run's `evidence_expires_dts`, or, without one, past its completion plus the product's evidence window (`quality.evidence_window_days`, which the resolver defaults to 7 days);
- where no producer is designated, the most cautious producer's entry stands for each area;
- a product with no evidence at all reads `no-evidence` and `unknown`.

## Validator

[`validate.py`](../../../../tooling/bindings/README.md) connects through `POSTGRES_DSN`, runs each check in its own savepoint and records an erroring check as `ERROR`, never as zero defects. Where the manifest places `ValidationRun` and `ValidationArea`, it appends one run and one area record per entity, module and the product (wire schema 2.1). Failed `ERROR` or `CRITICAL` checks give weak confidence; a failed `WARNING` leaves partial. The gaps the manifest reports cap the PRODUCT area at partial. This is a structural profile, not a certification of business rules; add design-specific checks in the product workspace with explicit scope and provenance.

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.
