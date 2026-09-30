---
title: PostgreSQL Domain Implementation
anchor: domain
type: implementation
status: draft
version: 2.0
normative: true
implements: domain
platform: postgres
---

# PostgreSQL: Domain

Binding of [Domain](../../../../design/modules/domain.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[schema.sql](schema.sql) provides four permanent keymaps and SCD2 histories for Customer, Product, Account and Transaction. Identity sequences allocate keys only in keymaps; a composite foreign key binds each history row to its permanent id and natural key. `allocate_key` in [temporal.py](../../temporal.py) uses atomic upsert; keys are never recycled. Maintainers must retain keymaps for product life.

`CurrentStateFilter` uses explicit `v_*` projections, `is_current`, open validity and non-deletion. `NaturalKeyLookup` queries these views. `PointInTimeReconstruction` uses `at_*(timestamptz)` SQL functions with half-open containment. These full-history functions require ADMIN privileges. `EntityJoinBack` resolves ids to current or as-of Domain; enhancement modules do not copy content. `AccessView` is enforced by grants.

`RichMetadata` uses table and column comments. `MetadataCoverageCheck` compares `pg_catalog` facts with authored Semantic metadata. `SemanticRegistration` and `DocumentationCapture` are generated after dependencies deploy. `DOM-KEY`, `JOIN`, `META`, `BOUNDARY` and `TLM` checks cover this fixture; native exclusion constraints reject overlapping versions. Tests exercise boundaries, replay, late changes and rollback. Business-time SCD2 does not provide as-known reconstruction.
