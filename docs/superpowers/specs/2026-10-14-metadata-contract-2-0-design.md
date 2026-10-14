# Metadata contract 2.0.0: design

Status: approved in conversation 2026-10-14; implementation proceeds from this document.

## Purpose

Sub-project **B**. [The release contract design](2026-10-14-release-contract-design.md) (A) published
a versioned bundle and a declared standard version, and listed four limitations of the metadata an
agent reads from a deployed product. B removes them in one breaking release, **2.0.0**:

| Limitation in 1.x | Resolution in 2.0.0 |
|---|---|
| Object identity embeds the physical container | Logical, placement-independent identities; location in separate columns |
| One surrogate and one natural key column per entity | Key definitions with ordered key columns |
| One column pair per relationship, no grouping | A relationship is a join group of ordered column pairs |
| Join paths are concatenated strings that differ by platform | Paths are rows with hop and key position; the agent assembles the SQL |
| No record of where an access-view column comes from | One mapping row per output column of an access object |

The prepared, untagged 1.1.0 release (declaration, comment coverage, release bundle) folds into
2.0.0. 1.1.0 is never tagged.

## Decisions

| Decision | Choice |
|---|---|
| Scope | Metadata contract only. The Domain module's key allocation, keymaps and temporal mechanics do not change |
| Platforms | All three: Teradata, Postgres, DuckDB. Every implementation is a Jinja template; the Python DuckDB generator is superseded |
| Identity | Logical and placement-independent, with physical location in separate columns |
| Ordered groups | Normalised child tables with an explicit ordinal. No arrays, lists or delimited strings |
| Migration | A written note and re-registration. No migration scripts |
| Release | One bump to 2.0.0 covering 1.1.0's content and B |

## Identity grammar

| Kind | Form | Example |
|---|---|---|
| Entity | `module.entity` | `domain.ticket` |
| Entity surface | `module.entity:surface`, surface `base` or `current` | `domain.ticket:current` |
| Module-owned object that is not an entity | `module:object` | `observability:trust_map` |
| Composite access object | `composite:name` | `composite:ticket_enriched` |

`module` is the module anchor (`domain`, `semantic`, ...). `entity` and `object` are lower-case logical
names with no container, product prefix or object-type affix. An identity never changes when a
container is renamed or the same design is deployed with a different placement.

Physical location is separate: `container_name` and `table_name` on `entity_metadata`, and
`container_name` and `object_name` on `access_object`. `data_product_orientation` and
`primary_object` use a verbatim `object_location` (`container.object`) where a consumer needs the
physical name; they otherwise reference the logical identity.

Entity identity today differs on every platform (`Party` on Teradata, `itsd_domain.ticket` on
Postgres and DuckDB, `domain.Ticket` in the validation rules). 2.0.0 makes it one form.

## Metadata model

All tables are `CURRENT_STATE`. A key marked synthetic is `parent_id:ordinal` so a child row has the
single-column key the binding contract requires.

| Table | Status | Content |
|---|---|---|
| `entity_metadata` | changed | `entity_name` is the logical identity. `surrogate_key_column` and `natural_key_column` are removed |
| `key_definition` | new | `key_id` (`entity_name#role`), `entity_name`, `key_role` (`SURROGATE`, `NATURAL`, `ALTERNATE`) |
| `key_column` | new | Synthetic `key_column_id`, `key_id`, `ordinal`, `column_name` |
| `table_relationship` | changed | `relationship_id`, `source_entity`, `target_entity`, `cardinality`, `relationship_type`, `is_mandatory`. `source_column` and `target_column` are removed |
| `relationship_column` | new | Synthetic id, `relationship_id`, `ordinal`, `source_column`, `target_column` |
| `access_object` | changed | `object_identity` is the logical identity. Adds `container_name` and `object_name` |
| `access_composition` | changed | `join_path` is replaced by `via_relationship_id` and `via_direction` (`FORWARD`, `REVERSE`). Adds `member_seq` |
| `access_column` | new | Synthetic id, `object_identity`, `ordinal`, `column_name`, `source_entity`, `source_column`, `mapping_kind` (`PASSTHROUGH`, `RENAMED`, `DERIVED`), `derivation_note` |
| `primary_object` | changed | References the logical `object_identity` |
| `data_product_orientation` | changed | `object_identity` becomes `object_location` |

A composite key is the ordered rows of its `key_column`. An entity that today has one natural key
column has a `NATURAL` key with one row. When the physical natural key is built from several business
columns, the definition lists those components in order. Nothing about how rows are keyed or
allocated changes.

Every identity-bearing reference (`source_entity`, `target_entity`, `member_entity`,
`represents_entity`, `resolves_to_object`, `metric_dataset.entity_name`, `semantic_synonym.object_name`,
`column_metadata` keys) uses the logical identity.

### Access surface

`relationship_edges` has one row per direction per key position: relationship, key ordinal, from
entity and column, to entity and column. `relationship_paths` has one row per path hop per key position:

| Column | Meaning |
|---|---|
| `path_id` | The ordered relationship ids with direction, for example `REL-1>REL-3<` |
| `hop` | Position of the step in the path, from 1 |
| `key_ordinal` | Position of the column pair within the join group |
| `from_entity`, `from_column`, `to_entity`, `to_column` | One pair of the join |
| `relationship_id`, `direction` | The relationship the step traverses and the way it is crossed |

Paths remain bounded to four hops and cycle-free. The concatenated `join_path` and `path_joins`
strings are removed on every platform.

## Conformance checks

New invariants, each a runnable check on all three platforms, zero rows meaning a pass:

| Id | Rule |
|---|---|
| `INV-SEMANTIC-016` | Every entity and access identity matches the grammar and contains no container name; entity identities are unique |
| `INV-SEMANTIC-017` | Every entity has a `SURROGATE` key definition; key column ordinals run 1..n without gaps; each column exists on the entity |
| `INV-SEMANTIC-018` | Every relationship has at least one column row; ordinals run 1..n without gaps; each column exists on its entity |
| `INV-SEMANTIC-019` | Every agent-consumable access object has exactly one `access_column` row per output column; each non-derived source exists |
| `INV-SEMANTIC-020` | Each composite has exactly one `ANCHOR`; `member_seq` runs 1..n; each `via_relationship_id` exists and joins the member to a prior member |

Existing checks that referenced the removed columns are rewritten, not deleted.

## Release and documentation

- `VERSION` becomes `2.0.0`. `release/v1.1.0/` and `release/migrations/v1.1.0.md` are replaced by
  `release/v2.0.0/` and `release/migrations/v2.0.0.md`. The 2.0.0 note carries 1.1.0's changes.
- `COMPATIBILITY.md`: the known-limitations table is emptied and the four resolved items move to the
  release index. The stability section gains the identity grammar. All three platforms declare the
  version.
- The migration note gives the old-to-new identity rule for each platform, the DDL delta, and a
  verification query. A 1.x deployment re-runs registration. Authored rows that reference identities
  (metrics, synonyms) are re-captured from the design or rewritten with the rule; no script does it.
- `design/modules/semantic.md` and `domain.md`, the platform READMEs and `TEMPLATE_INPUTS.md` change in
  step with the code (documentation moves with code).
- DuckDB and Postgres get `standard_declaration`, the comment-coverage check and comment parity
  (views, view columns, macros or functions, sequences, schemas where supported), as 1.1.0 intended.
  Teradata gets `standard_declaration`.

## Platform notes

| Platform | Notes |
|---|---|
| Postgres, DuckDB | Share the renderer in `tooling/bindings/render.py` and the context contract. `entities.json` per platform is the single declaration of the Semantic tables; templates register rows from the context |
| Teradata | Hand-authored Semantic DDL and views with `{{ product }}_Semantic` composition. Registration is a builder step, so the templates change tables, views and validation, and the examples' registration SQL changes with them |
| Inputs | Relationship inputs carry an ordered `columns` list of pairs; key inputs carry ordered column lists. Existing single-column inputs remain valid as the one-element case |

## Testing

- Renderer unit tests: identity grammar, ordinal checks, context validation, both new and legacy
  input shapes.
- DuckDB: full execution here. Deploy the reference products, run every check, and mutation tests
  that break one rule at a time and expect the matching check to fail.
- Postgres: render and static tests here. The execution tests are written and need `POSTGRES_TEST_DSN`;
  they will not have run.
- Teradata: render tests here; execution on the user's live system, with their agreement on the
  target database before anything is created.
- Release tests: bundle current, migration note and compatibility row present, bundle not a module.

## Out of scope

- Domain key allocation, keymaps and multi-column physical keys.
- Automated migration of existing deployments.
- Tagging or publishing 2.0.0.
- Machine verification that a declaration is true; the trust map remains the evidence.

## Risks

- Teradata cannot be executed here. Its DDL and views are verified only by rendering until the live run.
- The identity change touches every reference column and the validation SQL on three platforms; a
  missed reference fails only the check that covers it.
- The breaking change is large for a standard with one tag. The release-index entry and migration note
  must state it plainly.
