# Teradata — Prediction Module Implementation

Teradata binding of [`design/modules/prediction.md`](../../../../design/modules/prediction.md). The
feature store: engineered features, model predictions, point-in-time training data. Hard-depends on
Domain. Read the design document first. Replace `{{ product }}`; tables live in `{{ product }}_Prediction`.

## Files

| File | Purpose |
|------|---------|
| `01-feature-group.sql.j2` | Wide-format feature group table (dense engineered features, SCD2). |
| `02-feature-value.sql` | Tall-format feature-value table (sparse/dynamic/mixed-type features, SCD2). |
| `03-model-prediction.sql` | Model prediction outputs with confidence and reproducibility linkage. |
| `04-views.sql.j2` | `v_{entity}_features_current` / `_enriched` / `_pit` (`AccessView`). |
| `validation.sql` | Invariant checks (no raw-copy columns; point-in-time columns present). |

## Capability bindings

| Capability (design) | Teradata binding |
|---------------------|------------------|
| `EntityJoinBack` *(hard → Domain)* | `INNER JOIN Domain.{Entity}_H ON entity_id`, current-filtered. Prediction cannot deploy without Domain. |
| `PointInTimeReconstruction` | `observation_dts` + the temporal-lifecycle validity predicate. |
| `CurrentStateFilter` | `WHERE is_current = 1`. |
| `AccessView` | `v_{entity}_features_current` / `_enriched` / `_pit`. |
| `RichMetadata` | `COMMENT ON TABLE` / `COMMENT ON COLUMN`. |
| `SemanticRegistration` *(soft)* | Feature *definitions* registered in `{{ product }}_Semantic.column_metadata`; feature *values* here. |

## Logical-type bindings used here

| Logical type | Teradata type |
|--------------|---------------|
| `Identifier` | `INTEGER GENERATED ALWAYS AS IDENTITY` |
| `Reference -> E` | `BIGINT` |
| `Decimal(p,s)` | `DECIMAL(p,s)` (normalised features `DECIMAL(5,4)`) |
| `Json` | `JSON` |
| `Enum{…}` | `VARCHAR(n)` with a documented value set |
| `Timestamp` | `TIMESTAMP(6) WITH TIME ZONE` |
| `Flag` | `BYTEINT` |

Temporal columns (`valid_from_dts`/`valid_to_dts`/`is_current`) follow the
[temporal-lifecycle pattern](../../patterns/temporal-lifecycle-metadata/) `SCD2_HISTORY` profile.

## Invariants → checks

| Invariant | Check |
|-----------|-------|
| `INV-PRED-001` (engineered, not raw copies) | `validation.sql` §1 — no raw domain-content column names on feature tables. |
| `INV-PRED-002` (point-in-time) | `validation.sql` §2 — `observation_dts` + validity columns present. |
| `INV-PRED-003` (join-back, no dup) | Enforced by schema + reviewed at design time. |
