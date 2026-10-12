<!-- design-lint: ignore-file (template interface, not a design document) -->

# Template input contract

The optional helper accepts a JSON product context and a separate JSON placement overlay. See the shared ITSD inputs for a complete example. For direct Jinja use, `tooling.bindings.render.prepare(context, platform)` supplies a normalised context and `environment(platform)` configures StrictUndefined plus safe `ident` and `literal` filters. No template parses rendered DDL or introspects a completed product to guess the design.

| Input | Contract |
|---|---|
| product | id, version, owner, explicit consumer entrypoint, authoritative validator; optional evidence_days |
| modules | Explicit nonempty subset of module anchors; Search/Prediction require Domain |
| containers | Exact schema for every selected module, plus access; no inferred environment/product naming |
| roles | Unsupported. DuckDB has no roles or grants; supplying roles fails the build with an unsupported-setting error |
| entities | Business/extension entity declarations: module, name, description, key, columns, profile, allocation |
| entity.columns | name, bound SQL type, nullable, authored comment; optional check expression, pii and classification |
| entity.profile | CURRENT_STATE, EVENT_APPEND_ONLY, OPERATIONAL_LOG, ASSOCIATION_CURRENT, SCD2_HISTORY, ASSOCIATION_SCD2 or SCD2_BITEMPORAL |
| entity.allocation | supplied, inline, or keymap; keymap additionally requires explicit keymap name and natural_key |
| entity.supports_deletion | Explicit lifecycle option; defaults on for versioned profiles |
| entity.current_view / history_function | Optional explicit names; documented defaults v_<entity> and at_<entity> |
| runtime_memory | Whether to include standard runtime tables; independent of documentation |
| relationships | Declared source/target module.entity, source/target columns and mandatory flag |
| searches | Source Domain and embedding Search entity references, function name, vector column/dimensions, model/version, source facet and content projection |
| documentation | Authored decision records with id, title, context, alternatives, rationale, consequences, category, module and source |

Business history profiles are never inferred. Category/reference tables can select CURRENT_STATE while other entities select bitemporal history. VECTOR(n) is a helper-level bound-type shorthand: it becomes a fixed-size FLOAT[n] array. Other accepted types include BIGINT, INTEGER, VARCHAR(n), TEXT, BOOLEAN, DATE, TIMESTAMPTZ, DECIMAL(p,s) and JSON. SQL type/check/constraint expressions are trusted authored code, not untrusted end-user strings.

Normalisation adds qualified identities, current-view identities, the applicable temporal_columns, and all_columns for comments/validation. It resolves the allocator sequence name (`key_sequence`, explicit or `<keymap or entity>_seq`) and column `pii` and `classification` defaults, so templates read these values rather than defaulting them. Manifest checks may carry `severity` (ERROR, WARNING or CRITICAL) and `category`. It expands standard-owned metadata definitions from the selected module's entities.json and represents keymaps in the governed inventory. The SQL templates remain the source of physical DDL, view, search, access and validation behavior.

A standalone module template expects module_entities plus the normalised context. Render comments, views, soft-dependency registration and grants in dependency order. Direct template authors must supply the same contract; missing inputs fail, rather than becoming empty SQL.

The output includes ordered phase SQL, deploy.sql and manifest.json containing the resolved objects and scoped violation queries. The manifest is trusted build output and must not be executed from an untrusted source. It belongs with the built product, not inside the skill.
