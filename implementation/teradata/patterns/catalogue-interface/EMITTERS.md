# Emitter specification

Two renderers that turn the extraction in `05-semantic-model-export.sql` into the artefacts an enterprise catalogue ingests. This document is the contract they implement; it is supporting material for the [catalogue-interface binding](README.md), not a design document.

The renderers belong with whatever release packaging tooling already builds a product's deployment package and emits its per-catalogue metadata bundles. They are pure projections of a neutral product-metadata model, with no live connectivity and nothing fabricated, which is the rule the catalogue renderers beside them follow.

| Emitter | Produces | Target format |
|---|---|---|
| `semantic_model.py` | `semantic_model.yaml` | Open Semantic Interchange (Apache Ossie), YAML with JSON-schema validation |
| `data_product.py` | `data_product.yaml` | the catalogue's own data-product schema, derived from the Open Data Product Specification |

## Why YAML rather than a connector

A connector reads a native database object. Snowflake has `SEMANTIC VIEW`; Teradata has no equivalent, so there is nothing of that shape for a connector to extract, and the Teradata connector correspondingly has no semantic-model support at any released version. The catalogue's own ingestion accepts semantic definitions as YAML from any platform, which is the route that does not depend on a connector roadmap. The product emits; the catalogue ingests.

## `semantic_model.py`

### Mapping

| Target construct | Source | Notes |
|---|---|---|
| `name` | product identifier | one model per product per version |
| `version` | the format's own schema version | not the product version; that goes in the descriptor and in an extension field |
| `datasets[].name` | `entity_name` | business name, not the table name |
| `datasets[].source` | `source_container` + `source_object` | the consumer exposure where one is declared, base table otherwise |
| `datasets[].primary_key` | `surrogate_key_column`, else `natural_key_column` | omitted when neither is declared |
| `datasets[].description` | `entity_description` | |
| `datasets[].fields[].name` | `column_name` | |
| `datasets[].fields[].expression` | the column name, in the configured dialect | a field maps to a physical column; only metrics carry real expressions |
| `datasets[].fields[].datatype` | `data_type`, mapped | see the type map below |
| `datasets[].fields[].dimension.is_time` | `is_time` from query 2 | resolved from the declared type, never the column name |
| `relationships[]` | query 3 | direction per `emit_direction`; see below |
| `metrics[].name` / `.description` / `.datatype` | query 4 | |
| `metrics[].expression.dialects[]` | query 5 | one entry per declared dialect |
| `ai_context.synonyms` | query 6 | grouped onto the entity, field or metric it resolves to |

### Type mapping

Teradata declared types map to the format's small closed set. Anything unmatched maps to `Opaque` rather than being guessed — a field typed as a string that is really a decimal produces a model that computes wrong answers, and `Opaque` produces one that declines to compute.

| Declared type | Emitted |
|---|---|
| `CHAR`, `VARCHAR`, `CLOB` | `String` |
| `BYTEINT`, `SMALLINT`, `INTEGER`, `BIGINT` | `Integer` |
| `DECIMAL`, `NUMERIC` | `Decimal` |
| `FLOAT`, `REAL`, `DOUBLE PRECISION` | `Float` |
| `DATE` | `Date` |
| `TIME`, `TIME WITH TIME ZONE` | `Time` |
| `TIMESTAMP` | `DateTime` |
| `TIMESTAMP WITH TIME ZONE` | `DateTimeTz` |
| anything else | `Opaque`, with a warning |

A `BYTEINT` flag maps to `Integer` rather than `Boolean`, because the corpus represents flags as a constrained integer and the type is what it is. Where the format offers a boolean and the column carries a `CHECK` restricting it to 0 and 1, emitting `Boolean` is a legitimate configuration choice; it is not the default, since the emitter does not read constraints.

### Relationship direction

Query 3 returns `emit_direction`, so the emitter does not interpret the cardinality vocabulary itself:

- `AS_DECLARED` — emit `from` = source, `to` = target, with `from_columns` / `to_columns` in that order.
- `INVERT` — emit `from` = target, `to` = source, columns swapped. The declared relationship runs one-to-many, so the reference is held by the entity recorded as the target.
- `REPORT` — do not emit. Add a warning naming the relationship and its cardinality. A many-to-many relationship has no single-direction expression; the fix is registering the bridging entity, which the emitter cannot invent.

A relationship whose source or target entity is not in the emitted dataset set is also skipped with a warning: a relationship to a dataset that is not in the model is a dangling edge, and a catalogue validating the model will reject the whole file for it.

### Completeness and warnings

The emitter never fills a gap. It warns and omits, following `INV-CATALOGUE-011` and the `strict` flag the existing extractor already carries:

| Condition | Behaviour |
|---|---|
| No metrics registered | Emit the model with no `metrics` key. Warn once. |
| Metric has no expression in the configured dialect | Omit the metric. Warn, naming the metric and the dialects that are available. |
| Metric reads a dataset not in the model | Omit the metric. Warn. |
| Entity has no registered columns | Emit the dataset with no fields. Warn. |
| No synonyms registered | Emit no `ai_context.synonyms`. No warning; synonyms are optional enrichment. |
| Declared type unmatched | Emit `Opaque`. Warn, naming column and type. |

Under `strict`, any warning in the first four rows fails the emit instead.

### Validation

The format publishes a JSON schema. Validate the rendered document against it before writing, and fail the emit on a schema error rather than shipping a file the catalogue will reject on upload — the error is far cheaper to read here than in an ingestion log.

## `data_product.py`

### Mapping

| Target field | Source |
|---|---|
| `productId` | `product_id` |
| `version` | `product_version` |
| `name` | `product_name` |
| `description` | `product_description` |
| `status` | `product_status` |
| `domain` | `product_domain` |
| `contactName` | `contact_name` |
| `contactEmail` | `contact_email` |
| output objects | `qualified_object_name` per row of query 7's second result set |
| documentation links | the `*_uri` columns, where populated |

The catalogue's schema is served by the customer's own instance, and the document carries a `schema` property naming it. **Validate against that URL, do not hard-code a field list.** The public specifications this schema derives from have several live major versions and the vendor's profile of them is its own; a renderer built against a public spec and shipped without validating against the instance is a renderer that fails at upload on somebody else's release cadence.

Fields the target schema does not define are carried as custom properties under the `x-` prefix the schema permits:

| Custom property | Source | Why it is worth carrying |
|---|---|---|
| `x-approved-entrypoint` | `approved_entrypoint`, `approved_access_mode` | the object the product wants consumers to start at |
| `x-containers` | container feed | module and layer placement, for the physical mapping |
| `x-object-roles` | `object_role` per interface row | how each object is meant to be used |
| `x-temporal-profile` | `temporal_pattern` per entity | whether an entity carries history |
| `x-data-classification` | `data_classification`, `is_pii` per column | classification the catalogue can act on |
| `x-version-from` | `version_from_dts` | the instant this version became current |

### Contacts

`contact_name` and `contact_email` are already resolved by the product feed — business owner first, technical contact as fallback. The emitter takes them as given and does not re-derive the preference. Where both are absent the fields are omitted; the product then fails `INV-CATALOGUE-007` and that is the signal to fix, rather than something for the emitter to paper over.

## Running the emitters

One invocation per product version, at release. The natural trigger is the lifecycle feed: a `VERSION_RELEASE` or `REGISTERED` transition is a product whose export is stale.

```
for each transition in data_product_lifecycle where version_from_dts > watermark:
    if transition_type in (REGISTERED, VERSION_RELEASE):
        emit semantic_model.yaml and data_product.yaml for that product version
    if transition_type in (STATUS_CHANGE, METADATA_CHANGE):
        emit data_product.yaml only
    if transition_type = RETIRED:
        emit data_product.yaml with the retired status; emit no semantic model
```

A status change does not alter the model, so re-emitting it would produce an identical file and, in a catalogue that drafts on change, an empty draft for somebody to review and dismiss. Retirement emits a descriptor because the catalogue needs to know; it emits no model because there is no longer a surface the model describes.

Both artefacts are written into the release bundle beside the existing catalogue bundles, under the product version, so the previous version's export remains available to difference against.

## Open questions before implementation

1. **Is there an API for semantic-model upload, or is it interface-only?** The data-product publish API is documented; an equivalent for semantic models was not found. If the upload is manual, the emitter still earns its place — it removes the authoring, not the upload — but the sync is not unattended, and that should be known before anyone promises otherwise.
2. **Does the target accept several dialects per metric, or one?** The interchange format does; the vendor's ingestion of it may flatten to one. This decides whether the dialect is emitter configuration or emitted in full.
3. **What happens on re-upload of the same product?** Draft-on-change is documented for connector-sourced models. Whether a YAML re-upload creates a draft, replaces in place, or duplicates is the difference between an automated sync and a manual one.

These are questions for the catalogue vendor, not design decisions this repository can settle. The mapping above holds either way.
