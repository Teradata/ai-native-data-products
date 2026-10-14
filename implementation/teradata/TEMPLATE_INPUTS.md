<!-- design-lint: ignore-file (template interface, not a design document) -->

# Template input contract

Every artefact in this binding is a Jinja template (`*.sql.j2`). Render with a `FileSystemLoader` rooted at `implementation/teradata/` and `StrictUndefined`: a value a template reads and the caller does not supply is an error, never an empty string. Templates read only these context values. They do not build a container or role name from another, and they carry no product, organisation, container or principal literal; the names arrive resolved from the build context ([Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) section 6).

`tooling/validation/tests/td_context.py` holds a representative context and `render()`; `test_templates_render.py` renders every template with it, and `test_teradata_templates.py` checks that every variable a template reads is listed here.

## Shared values

| Value | Meaning |
|---|---|
| `product` | The product name, used in comments and descriptions. |
| `modules` | Anchors of the modules in the composition. Search and Prediction grants render only when listed. |
| `semantic_db`, `memory_db`, `domain_db`, `observability_db`, `search_db`, `prediction_db`, `access_db` | The container the build context places for each module, and for the access layer. |
| `governance_db` | The shared governance container holding the product registry and the catalogue feeds. |
| `db` | The one container a pattern template targets (the Observability container for the validation pattern; the table's container for the temporal specimens). |
| `stage` | The container the build stages a release's container and interface declarations in. |
| `role_read`, `role_agent`, `role_admin` | The physical role for each standard access tier. |
| `agent_service_account`, `analyst_user_or_group_role`, `product_owner_user` | Principals the access-layer DCL names in its role-assignment comments. |

## Temporal pattern specimens

| Value | Meaning |
|---|---|
| `entity` | Table name (a string in the pattern templates; a structured record in the Domain, Prediction and Search templates, below). |
| `natural_key`, `surrogate_key` | Key columns of the worked SCD2 table. |
| `governed_view`, `current_view` | The names of the governed full-contract view and the default current access view. |
| `attributes` | Business attributes: `{ name, type, comment }`. |
| `supports_deletion` | Whether the table carries `is_deleted` and `deleted_dts`. |

## Documentation capture (`modules/memory/12-capture-protocol.sql.j2`)

`registered_modules`, `decisions`, `superseded`, `changes`, `glossary_terms` and `recipes` are the design's own records. An empty list renders no statement; the template invents none. Identifiers such as `DD-ACCESS-001` arrive whole.

## Module templates with their own structured inputs

| Template | Values |
|---|---|
| Domain `01` to `05` | `database`, `entity` (`name`, `lower`, `natural_key_len`, `table_comment`, `attributes`, `columns`, `enriched`), `reference`, `rel`. |
| Observability graph facet | `graph_key`; the catalogue seed and lineage load also take `description`, `display_name`, `sort_order` and `column_lineage_enabled`. |
| Prediction | `group`, `pred_db`, `domain_db`, `entity`. |
| Search | `entity_kinds`, `metric`, `top_k`, `rag_k`, `entity` (`content_columns`, `kind`). |

Macro-internal names (`_`, `comma`, `width`) are not inputs.

Known gaps against section 6: the Domain, Prediction, Search and Semantic templates still compose container names as `product` plus a module suffix, and `03-similarity.sql.j2` supplies defaults for `metric`, `top_k` and `rag_k`. They are reported as gaps, not as conformance.
