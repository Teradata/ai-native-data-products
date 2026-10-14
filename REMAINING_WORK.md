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
| Teradata binding | On the build context. Both reference specifications deploy on Teradata 20.00.24 (ClearScape) and every rendered check passes. The graph-lineage and catalogue-interface templates are not migrated and await a decision (task 1a) |
| Tests | `tooling/validation/tests`: 253 of 255 pass; the 2 failures are the untouched Teradata extras (task 1a). `tooling/bindings/tests`: 75 pass (20 engine tests each on DuckDB, PostgreSQL and Teradata, 11 rendering, 4 Teradata dialect), none skipped. Each binding's `CONFORMANCE.md` is generated from them (`tooling/bindings/conformance.py`) |

Nothing has been pushed since the earlier review push. This branch is ahead of `origin` by the
PR #72/#74 merge, the binding-conflict commits, the Teradata WIP and the Teradata migration.

## Running the checks

```bash
python -m unittest discover -s tooling/validation/tests
pip install jinja2 duckdb pytz "psycopg[binary]" teradatasql
POSTGRES_TEST_DSN="host=localhost port=5432 user=postgres dbname=scratch" TERADATA_TEST_DSN="$(cat ~/teradata_test.json)" python -m unittest discover -s tooling/bindings/tests
python tooling/bindings/render.py examples/it-service-desk-data-product/design-output/design_specification.md examples/it-service-desk-data-product/profiles/postgres.md --output build/itsd-postgres
```

The PostgreSQL tests need a disposable database whose role can create roles and schemas. Each
test runs inside a transaction that is rolled back. On Windows without PostgreSQL, the
EnterpriseDB binaries zip (`postgresql-16.x-windows-x64-binaries.zip`) is enough: run
`initdb -A trust`, then `pg_ctl start`.

The Teradata tests need `TERADATA_TEST_DSN`, the teradatasql connection parameters as JSON
(`{"host": ..., "user": ..., "password": ...}`), for a disposable system where the user may
create databases and roles. They deploy each reference specification once under databases and
roles prefixed `anptest_`, reset its rows between tests, and drop everything with that prefix,
and nothing else, before and after. A full Teradata run takes 17 to 55 minutes on ClearScape,
most of it DDL, depending on the system's load (CI allows 60). If a run is killed, its session can keep dictionary locks: abort it with
`SELECT SYSLIB.AbortSessions(1, 'DEMO_USER', <session>, 'Y', 'Y')` before the next run.

CI (`.github/workflows/validate.yml`) runs both suites with a PostgreSQL service and fails on
any skip. It now also installs teradatasql and reads `TERADATA_TEST_DSN` from a repository
secret, so **CI fails until that secret is set**: missing engine coverage is a gap. Runs are
serialised across branches because they share the `anptest_` prefix on one system. Setting the
secret and making the check required are repository-admin settings.

## Remaining tasks, in order

### 1. Teradata binding onto the build context (Phase 3) — done

The WIP is merged. The review fixes it was said to lack (registration manifest guard,
discriminator-aware reference check, container-grant rule, `Runtime scope: unsupported`) were
already in it. Done in this pass:

- **Engine-tested on Teradata 20.00.24.** Both reference specifications deploy and every check
  passes; the shared engine tests run on Teradata as on DuckDB and PostgreSQL. They are written
  once, against the build context; each engine only says how it writes a flag, an open interval
  end, a vector and reads history.
- **Fixes the engine found:** no `VECTOR` type on 17.20 or 20.00.24 (vectors are now LATIN JSON
  arrays with a `REGEXP_SIMILAR` dimension check); `GRANT ALL` to a role fails (`CREATE USER`),
  so the admin tier gets an explicit list; tier grants ran before their objects existed, so the
  grants are split into implied grants (phase 01) and tier grants (last); an interval literal
  takes no precision; an untyped `NULL` in a union branch fails when the view is queried
  (`[3654]`, now a §7 row and a dialect rule); timestamps in maintenance are cast.
- **Implied grants narrowed** to what each view reads (`patterns/access-layer/00-implied-grants`).
- **Old templates and tests retired**, apart from the extras below. `test_teradata_dialect.py`
  holds every rendered statement to the §7 rules, each rule shown to catch its construct.
- **`hours_between` and `days_between`** are now declared on Teradata, exact to the microsecond.
- **Docs**: Teradata README, module and pattern READMEs, `CONFORMANCE.md`; statuses are `draft`
  (§8.1). The skill's `roles/` now point at the build manifest's checks instead of retired files.
- `tooling/bindings/engines.py` gives `validate.py` and the tests one driver per engine, so no
  tool branches on `platform == "postgres"`.

Conflicts between bindings found and fixed, each with a test so it cannot come back:

- **Relationship-path bound.** PostgreSQL and DuckDB walked four hops, the Teradata WIP three, and
  Semantic §5 said only "bounded". The standard now says four, the resolver carries it as
  `RelationshipPaths.max_hops`, and every binding reads it. Tests: every binding's output changes
  with the bound; on every engine the path count per hop equals a walk done in Python.
- **Legacy-run trust entry.** PostgreSQL and DuckDB read a legacy run's PRODUCT entry as `partial`
  even with ERROR failures. Validation §10 applies §4.3, capped at `partial`, so it is `weak`.
  All three now agree; engine test on every binding.
- **Unreported gaps.** A profile's `mask`/`exclude` protection, object-storage placement, and a
  versioned relation with no history surface consumers can be granted are now reported by
  `render.py` for every binding.

#### 1a. Still open on Teradata

- **Graph lineage and catalogue interface: decision needed (Paul).** Left untouched at the user's
  request: `modules/observability/04-openlineage.md` and `05-graph-tables` to `10-access.dcl`,
  and `patterns/catalogue-interface/*`. They read the old flat context, and **two
  `test_binding_package` tests fail on them alone**: every template reached by a phase, and
  Jinja-only hygiene (`:event_dts` in `catalogue-interface/02-lifecycle-dml`). With them set
  aside the package tests pass. Port or retire,
  then those tests go green.
- **Vectors and similarity: done.** A `Vector[n]` is `VARBYTE(n × 8)`, little-endian 8-byte
  floats checked to that length, because the engine showed `TD_VECTORDISTANCE` reads VARBYTE as
  8-byte floats: with 4-byte floats every distance was wrong, without an error. Similarity is a
  stored procedure per `Embedding:` block (`Emits: procedure: embedding`) that runs
  `TD_VECTORDISTANCE` as dynamic SQL, since the operator takes no parameters; engine-tested for
  ranking, threshold, limit and a wrong-dimension query. A database's creator is not granted
  `CREATE PROCEDURE`, so a new `Deploying user` setting renders the grant. Open: whether
  `mldb.ONNXEmbeddings` can emit 8-byte floats (its `VARBYTE` output is 4-byte); the earlier
  in-database product this followed stored 4-byte floats and scored them with this function.
- **History for consumers: simple fix done, broader change pending.** Teradata now grants the
  governed base view of every versioned relation to the read and agent tiers, per view, as
  PostgreSQL grants its point-in-time functions, so history reaches the same tiers on every
  binding. There is no parameterised call (no table functions); a macro per relation would add
  one. The broader change is its own PR (see open questions).
- **Comment speed.** Column comments can take seconds each when other sessions touch the
  dictionary. Batching them into multi-statement requests (as the tests do) helps; a
  BTEQ-friendly `deploy.sql` cannot batch.

### 2. Conformance tests (task 7) — done

- **Generated conformance reports.** `tooling/bindings/conformance.py` runs the binding and
  package tests once, attributes every outcome to the binding it evidences (an engine class's
  `platform`, or a subtest's `platform` parameter; the platform loops now use subtests), renders
  both reference specifications under every example profile per platform, and writes each
  `CONFORMANCE.md`: outcomes, failures, skips, every gap the builds report, and the gaps the
  binding declares in a new `Gaps` field of its `Binding:` block (Authoring §5.1). Engine
  versions are recorded by a new engine test. `--check` fails when a committed report is out of
  date and names any gap it does not carry; CI runs it instead of the plain binding suite and
  uploads the regenerated reports. A package test requires each report to be generated and
  forbids `status: standard` in a binding whose report is `draft`.
- **Cross-platform test.** One specification, under each platform's example profile, places the
  same relations and renders the same checks (ids and scopes) on every binding.
- **`platform-name` lint rule.** No document under `design/` names a platform, with no
  `ignore-file` escape. The known-platform list moved into the linter (spec_lint reads it there).
  The Design Language's stale Appendix A (a copy of the bindings' types that had drifted) now
  points at the bindings' declarations.
- **Skill package.** `verify_skill.py --package` builds what an install receives (`git archive
  HEAD`) and checks the routing against it, the entry files, and that nothing the `.gitignore`
  excludes ships. `{platform}` routes must now resolve on every binding; the platforms are
  discovered (they were hard-coded to Teradata). A test holds this repository to it.

Found on the way, not done:
- `design_lint.py` checks the 255-character comment limit only `if "teradata" in sql.parts`: a
  platform special case in tooling. The limit belongs in the binding's declarations (or the
  static check can go, since `test_teradata_dialect.py` checks rendered comments).
- `examples/alation-interface/` ships `.sql` files, which the "examples hold inputs, not
  generated output" rule (Authoring §7) checks only for the ITSD example.

### 3. CI (task 8) — guide written; admin steps outstanding
The workflow installs every driver, runs all three engines and checks the conformance reports.
What is left are repository-admin and system steps, written up in `docs/ci-setup.md`: a
dedicated Teradata system and CI user, the `TERADATA_TEST_DSN` secret, a first run (committing
the reports CI regenerates), and making `validate` a required check. CI cannot go green until
the task 1a decision removes the two failing package tests.

### 4. Adoption modes — reference mode done

One engine test per binding, written once (`test_an_adopted_entity_is_used_where_it_stands`):
the profile binds ITSD's `Category` to `<existing container>.category_master`; the test creates
that container, the table and an unrelated table beside it, with a row in each, before the
product exists. The build must create nothing in the table's place and change nothing on it,
serve its row through the product's views, register it in `EntityMetadata` as the product's own,
pass every check, and leave the unrelated table alone. Passes on DuckDB, PostgreSQL and
Teradata.

It found three ways every binding treated an adopted container as its own, now fixed with one
`in_product` macro per binding: PostgreSQL revoked and re-granted privileges on an adopted schema
(`GRANT ALL ON ALL TABLES` to the admin tier included), and Teradata granted admin rights on an
adopted database; the `module semantic` check flagged the organisation's other tables in an
adopted container as unregistered; and `ColumnCatalogue` published their metadata.

Still open (declared in each binding's `Gaps`):
- **Wrap and migrate modes**, and presenting canonical names over an adopted entity's
  `Column aliases`, are not rendered. Authoring §4.3 says the modes are "defined separately";
  they are not yet, so define them in the standard first.
- **Adopted databases on Teradata**: the implied grant on an adopted database is emitted, so the
  deploying user needs its owner's rights. Access-layer §4 has the owner provision it and the
  build report it as outstanding; the manifest has no place for outstanding steps yet.
- No check covers an adopted table's shape (its columns and descriptions): the `entity
  metadata` and `entity temporal` checks render only for tables the product creates.

### 5. Review, push, PR
Ask Paul to review. Push the branch and raise a PR into `main`; it includes PR #74. Then update
PR #75 (layout standard) or withdraw it: the organisation profile now covers layout and naming.

## Known gaps the builds report (in each manifest's `gaps`; each `CONFORMANCE.md` lists them per binding)
- Expressions using `as_of`, `integrity` or `freshness`, which no binding declares a fragment
  for.
- Composite access objects (`AccessObject:` blocks, such as ITSD's `TicketDetail`). The
  resolver should place the composite view and settle its column names before any binding can
  render one.
- Runtime Memory scope on DuckDB and Teradata (`Runtime scope: unsupported`). PostgreSQL
  enforces it with row-level security.
- Classification protection (`mask`, `exclude`) and object-storage placement, on every binding,
  when a profile asks for them (the Teradata type-grouped example does).
- The graph-lineage exposure and the catalogue registration, when a specification or profile
  asks for them.

## Open questions and review notes
- **History for consumers, and tables apart from views (separate PR).** Every binding now grants
  history to the read and agent tiers: PostgreSQL through `SECURITY DEFINER` point-in-time
  functions, DuckDB through macros, Teradata through per-view grants on its governed views.
  Still to settle: (1) the access-layer grant matrix never names the governed full-contract
  surface, so add a row for it, and confirm exposing full history (personal-data columns
  included) is intended; (2) Teradata best practice keeps tables and views in separate
  databases, so maintainers and consumers never touch a table and grants can be database-level.
  Do this on PostgreSQL and DuckDB too, so the placement looks the same everywhere, then move
  Teradata's governed views out of the table databases; (3) rename the example profile's
  `{entity}_Current` base views, which hold full history.
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
- Semantic §5 bounds path discovery at four hops, and a path never revisits an entity. The
  resolver carries the bound (`RelationshipPaths.max_hops`); no binding fixes its own.
- A legacy run's derived PRODUCT entry is graded by Validation §4.3 on the run's counts, then
  capped at `partial`, on every binding.
- On Teradata a `Vector[n]` is LATIN JSON-array text with a dimension check, because neither
  17.20 nor 20.00.24 has a vector type; the admin tier's rights are listed, since `ALL` cannot go
  to a role; and the implied grants are only those the views read.
- On Teradata a vector is `VARBYTE(n × 8)` of 8-byte floats, the encoding `TD_VECTORDISTANCE`
  reads, and similarity is a stored procedure per embedding. `Types:` declarations may size a
  type as `{dim*n}`.
