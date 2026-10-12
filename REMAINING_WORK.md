# Remaining work: portable design standards

Handoff notes for `feat/portable-design-standards`. Delete this file before the branch merges.

## Where things stand

The branch implements the three-input build: a **design specification** (the design agent's
output, platform- and organisation-agnostic), an **organisation profile** (one per
organisation per platform), and a **platform binding**. `tooling/build/build_context.py`
resolves the specification, the profile and the binding's declarations into one build
context. Every binding's Jinja templates read only that context.

| Area | State |
|---|---|
| Standards | `design/core/IMPLEMENTATION_AUTHORING.md`, `DESIGN_SPECIFICATION.md` and `ORGANISATION_PROFILE.md`, with the module and pattern standards made consistent with them |
| Tooling | `spec_lint`, `org_profile` and `build_context` (resolver), plus `tooling/bindings/render.py` and `validate.py` |
| PostgreSQL binding | On the build context. Both reference specifications deploy on PostgreSQL 16.4 and every rendered check passes |
| DuckDB binding | On the build context. Both reference specifications deploy on DuckDB 1.5 and every rendered check passes |
| Teradata binding | **Not migrated on this branch.** The old templates are still in place, and partial new work is parked on the local branch `wip/teradata-build-context` (see below) |
| Tests | `tooling/validation/tests`: 282 pass. `tooling/bindings/tests`: 41 pass on DuckDB and PostgreSQL, none skipped |

Nothing has been pushed since the earlier review push. This branch is ahead of `origin` by the
PR #72/#74 merge, the binding-conflict commits and this commit.

## Running the checks

```bash
python -m unittest discover -s tooling/validation/tests
pip install jinja2 duckdb pytz "psycopg[binary]"
POSTGRES_TEST_DSN="host=localhost port=5432 user=postgres dbname=scratch" python -m unittest discover -s tooling/bindings/tests
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md examples/it-service-desk-data-product/profiles/postgres.md --output build/itsd-postgres
```

The PostgreSQL tests need a disposable database whose role can create roles and schemas. Each
test runs inside a transaction that is rolled back. On Windows without PostgreSQL, the
EnterpriseDB binaries zip (`postgresql-16.x-windows-x64-binaries.zip`) is enough: run
`initdb -A trust`, then `pg_ctl start`.

CI (`.github/workflows/validate.yml`) already runs both suites with a PostgreSQL service and
fails on any skip. Making it a required check is a repository-admin setting.

## Remaining tasks, in order

### 1. Teradata binding onto the build context (Phase 3)

Partial work is committed on the local branch `wip/teradata-build-context`. It is not pushed
and its tests fail. It holds new templates mirroring the PostgreSQL set:
- `00-macros` (MULTISET, PI choice, BYTEINT flags, sentinel, 255-character comments, identity)
- containers (`CREATE DATABASE ... AS PERM`, parents first)
- tables
- comments
- base and consumer views (`LOCKING ROW FOR ACCESS`)
- maintenance
- statistics
- key allocation (`MERGE` on the keymap's natural-key UPI, then `SELECT`)
- registration and capture
- discovery (relationship paths unrolled to three hops; no recursion or CTEs)
- trust map (`QUALIFY`, derived tables)
- entity, temporal and reference checks via `DBC`
- grants, with implied `WITH GRANT OPTION` grants computed from placement
- the `PLATFORM_PROFILE.md` `Phases`, `Deploy`, `Checks` and `Settings` (`Container space`)

ITSD renders on both Teradata example profiles, and sqlglot parses everything except
`REFERENCES WITH NO CHECK OPTION`, which is valid Teradata that sqlglot does not know.

To finish:
- **Merge the review fixes.** Bring this branch's fixes into the WIP: the registration
  manifest guard, the discriminator-aware reference check, the container-grant rule and
  `Runtime scope: unsupported`. The WIP copies predate them.
- **Narrow the implied grants** in `patterns/access-layer/01-grants.sql.j2`. They are over-broad
  (every module database to every view database). Derive the pairs from which view reads which
  container: base view ← table; consumer view ← base view or table; discovery views ← the
  Semantic and Observability table containers.
- **Retire the old templates** that read the old flat context:
  - `modules/*/0[1-9]-*.sql.j2` other than the new `01-tables` and `02-*`
  - `patterns/temporal-lifecycle-metadata/00-temporal-macros`, `01-ddl-template`, `02-dml-maintenance`, `04-statistics`, `conformance-queries`
  - `patterns/validation/01-validation-run`, `02-views`, `03-validation-area`, `04-trust-map-views`, `conformance-queries`, `consumer-queries`
  - `patterns/access-layer/access-layer.dcl.sql.j2` and `dd-access-001.sql.j2` (DD-ACCESS-001 is now a `Decision:` block in the specification, captured into Memory)
  - `modules/semantic/06-orientation.md`
  - `TEMPLATE_INPUTS.md`
- **Decide on the extras** with Paul: port or retire. Neither reference specification uses them, and `render.py` already reports them as gaps when a specification or profile asks for them:
  - graph lineage: `modules/observability/05-graph-*` to `10-access.dcl`, `04-openlineage.md`, `09-load-lineage`
  - catalogue interface: `patterns/catalogue-interface/*`
- **Similarity on Teradata.** `TD_VECTORDISTANCE` cannot sit in a view or SQL function. The
  resolver already supports `Emits: procedure: embedding` (a stored procedure with a dynamic
  result set), but it cannot be verified without an engine, so for now it is reported as a gap.
- **Replace the old Teradata tests**:
  - `tooling/validation/tests/td_context.py`, `td_sqlite.py`, `test_teradata_templates.py`, `test_templates_render.py` and `test_trust_map.py` exercise the old templates.
  - The trust-map behaviours they encode (per-area staleness, legacy fallback scoped to `1.0`/`2.0`, deterministic tie-break, requested areas answering `unknown`) are now covered on PostgreSQL and DuckDB by `tooling/bindings/tests`.
  - Keep a Teradata render test for the `PLATFORM_PROFILE.md` §7 idioms: no comment over 255 characters even with a long product name, no `ORDER BY` in a view, no zone-qualified literal in a `DEFAULT`, no FROM-less `SELECT` in a union, no `:name` inside stored strings, and no unrendered `{{`.
  - The SQLite translation harness can be ported to the new trust map if Teradata-dialect regression coverage is wanted.
- **Update the Teradata docs**: README, module and pattern READMEs, and a `CONFORMANCE.md` (required by `test_binding_package.py`).
- **Engine coverage gap.** There is no Teradata engine here, so engine coverage is a reported
  gap until it runs against a real system (for example ClearScape).

### 2. Conformance tests (task 7)
- Generate each binding's conformance report from the tests, replacing the hand-maintained
  `implementation/{postgres,duckdb}/CONFORMANCE.md` (Authoring Standard §8.1). The report
  should list every manifest gap and every skipped engine.
- Add a cross-platform test: the same specification renders on every binding with the same
  relation set and the same check ids.
- Add a `design_lint` rule against platform names in `design/`.
- Package the skill and check what it contains.

### 3. CI (task 8)
The workflow exists and installs `pytz`. Remaining: make it a required check (admin setting)
and add Teradata coverage when an engine is available.

### 4. Adoption modes
Adopted entities and containers resolve, but no engine test deploys over an existing table.
Add one per binding.

### 5. Review, push, PR
Ask Paul to review. Push the branch and raise a PR into `main`; it includes PR #74. Then update
PR #75 (layout standard) or withdraw it: the organisation profile now covers layout and naming.

## Known gaps the builds report (in each manifest's `gaps`)
- Expressions using `as_of`, `integrity` or `freshness`, which no binding declares a fragment
  for.
- Composite access objects (`AccessObject:` blocks, such as ITSD's `TicketDetail`). The
  resolver should place the composite view and settle its column names before any binding can
  render one.
- Runtime Memory scope on DuckDB and Teradata (`Runtime scope: unsupported`). PostgreSQL
  enforces it with row-level security.
- The graph-lineage exposure and the catalogue registration, when a specification or profile
  asks for them.

## Open questions and review notes
- **History for consumers.** Point-in-time functions (PostgreSQL `SECURITY DEFINER`, DuckDB
  macros) are granted to the read and agent tiers, following access-layer §143 (the governed
  full-contract surface is a consumer surface). Confirm that is intended, since it exposes full
  history including personal-data columns.
- **Fixed view column names.** The output columns of the discovery views (`ColumnCatalogue`,
  `TrustMap`, `LineageRunLatest`, the manifest's per-role columns) are fixed in templates. If
  organisations must rename them, the module standards need to define the views' columns so the
  resolver can map them.
- **Partial key coverage.** Key allocation and the reference check use only the first natural
  or target column; composite keys are not covered.
- **Non-scalar values in maintenance.** `04-maintenance` writes values through `literal`, so
  vector and JSON values need a typed path.
- **Generic cross-module recipes.** Cookbook recipes for module pairs with no relationship
  fall back to a catalogue lookup; they meet Memory §5.2's count but say little.

## Decisions made in this pass (now in the standards)
- A `Decision:` block's `Module` must be one of the product's modules; a pattern's decision is
  recorded against the module it governs (Memory §5.2). ITSD's `DD-ACCESS-001` is now recorded
  against Memory.
- An embedding entity must carry the Search standard's required attributes. Its identity is
  `entity_kind, entity_id, source_attribute`, and a new model is a new version, not a new
  identity (new lint rule `embedding-shape`). ITSD and Customer Orders were corrected.
- The Memory capture floor (3 decisions and 3 glossary terms per module) is checked at design
  time (`capture-floor`). Customer Orders gained glossary terms and two Semantic decisions.
- The profile standard gains a principal form, `outside <how>`, for platforms without
  principals. The resolver rejects `create`/`existing` on such a binding.
- Binding declarations gain `Runtime scope`, `Deploy`, the `<scope> <check>` form of `Checks`,
  and `procedure: embedding`. Settings take the binding's declared defaults (recorded in
  `defaults_applied`), and undeclared settings fail.
- Semantic's `NamingStandard.applies_to` and `DataProductMap.object_type` include `SEQUENCE`.
- The product's `DataProductRegistry` stays in its own Semantic store. The Teradata example
  profiles no longer route it to the shared governance database.
- Consumer views carry every column except the open interval ends.
- The trust map's derived PRODUCT entry is limited to the registered legacy wire versions
  (`1.0`, `2.0`).
