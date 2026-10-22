# Design: generate platform code from Python dialects, not Jinja templates

**Status:** proposal for review (Nathan, Paul). Nothing here has been built.
**Relates to:** [issue #80](https://github.com/Teradata/ai-native-data-products/issues/80) and
[`simplification-design.md`](simplification-design.md). If adopted, this replaces options B2
and C1 there.
**Measured on:** `main` after PR #76, with the A and B1 changes on `simplify/80-file-count`.

## 0. Verdict

**Do it, but not exactly as first proposed.** Replacing the Jinja templates with one Python
generator and a dialect class per platform, where each class overrides shared defaults, is a
better end state than consolidating the templates (B2) and sharing them across platforms (C1).
It fixes the file count for good, it removes the duplication between platforms, and it moves
the logic that has built up in Jinja into a language that suits it.

Three parts of the original idea should change:

1. **Determinism is not the reason to do this.** Code generation is already deterministic.
   `render.py` is a pure function of the specification, the organisation profile and the
   binding, and it renders under `StrictUndefined`. No agent writes SQL in the build today.
   The case rests on maintainability and on making new platforms cheap. If it were sold as a
   determinism fix, it would be judged against a problem we don't have.
2. **Per-platform behaviour lives in a dialect class, not in subclasses of the specification's
   objects.** "Features of the objects become methods, overridden per implementation" puts the
   inheritance on two axes at once: object kind and platform. That means a `TeradataEntity`,
   a `TeradataRelationship`, a `TeradataEmbedding`, and so on. Instead, the specification's
   objects are a read-only model with no platform in it. The platform is one class with one
   method per feature of an object (`create_table(entity)`, `consumer_view(entity)`, and so
   on). That is one inheritance axis, and every platform difference sits in one file.
3. **One process per product, not one per object.** Generating an object needs the whole
   product:
   - phase order: Memory and Semantic first, keymaps before the tables that reference them;
   - the registration rows and discovery views, which list every object;
   - the trust map and the product-scope checks;
   - the single deploy transaction;
   - the manifest's sequential test ids;
   - name-collision checks, which span the whole container.

   One process per object would resolve the whole product N times and still need a step to
   stitch the outputs together. It adds no isolation that pure functions don't already give.
   Generating a single object, for debugging or an incremental change, is a `--object` filter
   on the one process.

It only pays off if two things come first. A **golden-output harness** has to prove the new
generator emits byte-identical SQL. And the **Teradata port-or-retire decision** has to be
made, because 1,974 of the 3,212 lines of Teradata Jinja are the unmigrated graph-lineage and
catalogue-interface templates. If we do neither, this becomes a big-bang rewrite with nothing
to tell us whether it regressed, and in that case B2 and C1 are the safer choice.

## 1. What exists today

```
design specification ─┐
organisation profile ─┼─► build_context.py (resolver) ─► build context (JSON, schema'd)
binding declarations ─┘                                         │
                                                                ▼
                                    render.py + implementation/{platform}/**/*.sql.j2
                                                                │
                                                                ▼
                                          phase SQL files, deploy.sql, manifest.json
```

- **The resolver** (`tooling/build/build_context.py`, 1,030 lines) already does the hard part.
  It works out placement, names, physical types, keys, temporal columns, expression SQL
  fragments (from each binding's `Functions:` block), capture records and gaps. Its output,
  the build context, is the contract, fixed by `build_context.schema.json`.
- **The templates** turn the context into SQL:

  | Binding | Templates | Lines | Jinja control statements |
  |---|---:|---:|---:|
  | DuckDB | 30 | 1,049 | 269 |
  | Postgres | 31 | 1,109 | 286 |
  | Teradata | 45 | 3,212 | 339 |
  | — of which unmigrated (graph lineage, catalogue interface) | 12 | 1,974 | |

- **Logic has built up in Jinja.** For example, a macro returns a string and the caller tests
  `required(col) == 'True'`. Values are rendered by macros that switch on Python types, and
  inserts are keyed by logical name inside macros. This is ordinary code written in a
  language with no types, no unit tests and no debugger.
- **The duplication is real.** 13 of DuckDB's 29 templates are byte-identical to Postgres's,
  and two are identical on all three platforms.
- **Platform SQL lives in three places**: the `Types:` and `Functions:` blocks (data), the
  templates, and the resolver's substitution of those fragments.

## 2. Goals and non-goals

**Goals**

| # | Goal | Measure |
|---|---|---|
| G1 | File count stays bounded as platforms are added | about 4 files per platform; package below 100 with three platforms |
| G2 | Every piece of platform SQL in one place, with shared defaults and platform overrides | no SQL repeated across dialects; the duplicate check in §6 |
| G3 | Generation logic in a typed, unit-testable language | each dialect method has unit tests; no string-typed booleans |
| G4 | Generation stays deterministic | the golden test: identical inputs give byte-identical outputs, on any supported Python version |
| G5 | The build runs with the standard library only | Jinja2 removed from `requirements.txt` |
| G6 | A new platform is a subclass plus overrides | a Postgres-family engine adds one dialect module and its declarations |
| G7 | No change to deployed SQL during the migration | golden outputs identical before and after every step |

**Non-goals**

- Changing `design/`, the design specification format, or the build context schema.
- Changing the resolver's responsibilities. It still resolves; the generator only emits.
- Changing what any binding deploys. Behaviour changes come in separate PRs after migration.
- Introducing an SQL builder, ORM or transpiler (§8).

## 3. Architecture

```
build context (unchanged)
      │
      ▼
model.py      read-only typed objects over the context:
              Product, Module, Relation, Column, Relationship, Embedding, Metric, Principal…
      │
      ▼
generate.py   one run per product: picks the dialect, walks phases in order,
              collects statements, assigns test ids, writes the same outputs as today
      │  calls
      ▼
Dialect       abstract: what every platform must define
  └─ PortableDialect        implementation/portable/dialect.py   ANSI-leaning defaults
       ├─ PostgresDialect   implementation/postgres/dialect.py   overrides
       ├─ DuckDBDialect     implementation/duckdb/dialect.py     overrides
       └─ TeradataDialect   implementation/teradata/dialect.py   overrides
```

### 3.1 The object model (`tooling/build/model.py`)

The model is a thin, read-only, typed view of the build context: dataclasses built from the
JSON, with no platform knowledge and no SQL. Accessing a missing value raises an error, which
replaces `StrictUndefined`. Derived conveniences that templates compute today belong here, as
long as they are platform-neutral: `relation.history`, `relation.version_columns`,
`product.persisted()` (the current `render.persisted`), `product.relations_in(module)`.

The model does not resolve anything. If a value isn't in the context, the resolver is
missing a field. The fix goes in the resolver and the schema, never in the model.

### 3.2 Dialects

A dialect is a class whose methods emit SQL for one feature of one object. The base class
fixes the method set, so every platform answers the same questions:

| Area | Methods (illustrative) |
|---|---|
| Primitives | `ident(name)`, `literal(value)`, `qualified(obj)`, `physical_type(column)` |
| Containers | `create_container(container)` |
| Tables | `create_table(relation)`, `column_definition(relation, column)`, `primary_key(relation)`, `table_constraints(relation)`, `sequence(relation)` |
| Temporal | `current_predicate(relation, alias)`, `point_in_time_predicate(relation, alias)`, `consumer_view(relation)`, `point_in_time(relation)`, `maintenance(relation, …)` |
| Metadata | `comments(relation)`, `registration(product)`, `discovery_views(product)`, `capture(product)` |
| Search | `similarity(embedding)` |
| Access | `grants(product)` |
| Checks | one method per check, tagged with its scope: `@check("entity", "metadata")`, `@check("contract", "keys")`, … |
| Phases | `phases()`: the ordered list of `(file name, method)` |

Rules:

- **Methods are pure.** A method takes model objects and returns SQL text. No I/O, clock,
  environment, randomness or global state.
- **A platform overrides only what differs.** If an override would repeat the parent's SQL,
  delete it. The duplicate check in §6 enforces this.
- **Platforms extend `PortableDialect` directly.** Code shared by two platforms but not
  portable goes in a named mixin in the portable module, never in one platform inheriting
  another. This keeps each platform self-contained, which matters if the skill is ever split
  per platform (option D in the simplification design). Allowing `DuckDBDialect(PostgresDialect)`
  instead is open question Q3.
- **SQL stays readable.** Write it as multi-line string literals laid out like the SQL they
  produce, with small helpers (`ident`, `literal`, `join`). Composing SQL from builder calls
  is not allowed.
- **Phases and checks move into code.** `Phases:`, `Checks:` and `Deploy:` in the binding
  declarations exist only to name templates, so they become `phases()` and `@check` methods.
  `Types:`, `Functions:`, the quoting characters, `Principals`, `Runtime scope`, `Settings`
  and `Gaps` stay as data, because the resolver reads them and the conformance report lists
  them. They move to `binding.toml` if the configuration change in the simplification design
  goes ahead.
- **The default phase order comes from MASTER_DESIGN §10** and is defined once in the base
  class. A platform adds a phase (Teradata's statistics) or drops one (DuckDB has no access
  phase) by overriding `phases()`.

### 3.3 The generator (`tooling/build/generate.py`)

`generate.py` replaces `render.py`, with the same command line, the same output directory
rules and the same outputs: phase files, `deploy.sql`, `manifest.json` and `context.json`.
The build role changes only the script name. `--object NAME` limits output to one object's
statements, for debugging.

**Caller-rendered SQL** (key allocation and maintenance, used by a product's own pipelines)
becomes public dialect methods with stable signatures. A thin command-line form,
`generate.py maintenance …`, serves callers that aren't written in Python.

**Determinism** is guaranteed by construction and checked by test:

- iteration follows the context's own order, or an explicit sort, never set or hash order;
- output uses `\n` line endings and the current whitespace tidy;
- the only inputs are the three build inputs and the command-line options;
- the golden test (§5) runs on every supported Python version in CI.

### 3.4 What a binding directory holds afterwards

```
implementation/{platform}/
  README.md            how the binding realises each module and pattern (sections, as now)
  PLATFORM_PROFILE.md  physical-design guidance + declarations (binding.toml later)
  CONFORMANCE.md       generated
  dialect.py           the platform's overrides
```

That is four files per platform, against 37 to 45 today. A dialect larger than about 1,500
lines may be split into at most three modules. `implementation/portable/` holds one module.

## 4. What changes in the standard

| Where | Today | Afterwards |
|---|---|---|
| `IMPLEMENTATION_AUTHORING.md` §6 | "Jinja is the only template language" | A binding is a dialect module that subclasses `PortableDialect`. The rules carry over unchanged in substance: read only the build context, derive no names, no product or organisation literals, missing values fail, identifiers and literals go through the dialect's primitives, composition is honoured, the binding emits and never executes |
| `IMPLEMENTATION_AUTHORING.md` §7 | "Platform directories contain … templates, not product-specific compilers" | Platform directories contain documentation, declarations and one dialect module. It is generic, not a product compiler. Platform SQL lives only in dialect modules; `tooling/` holds none |
| `IMPLEMENTATION_AUTHORING.md` §5.1 | `Phases`, `Checks`, `Deploy` declared as data | Declared in the dialect class; the remaining declarations stay data |
| `test_binding_package.py` | "no `.py` in a binding"; Jinja-only substitution; templates reached by a phase | Exactly one dialect module (or up to three). An AST check that it imports only the standard library and the core library, makes no I/O calls, and contains no product literals. Every public method is reached by a phase, a check or the documented caller API |
| README sections (B1) | each names its template directory | each names its dialect methods |
| Roles | `roles/build.md` names `render.py` | names `generate.py` |

The principle behind the old rules was that platform SQL stays reviewable and in one place,
and that no product-specific code creeps in. That principle still holds. The mechanism
enforcing it changes.

## 5. Migration

The migration replaces the templates one phase at a time and checks each step against
golden outputs. There is no big-bang switchover, and each step is a mergeable PR.

| Step | Work | Accepted when |
|---|---|---|
| 0 | **Decide the Teradata port-or-retire question** for graph lineage and the catalogue interface (1,974 lines). Retire, or port onto the build context in Jinja first. Freeze B2 and C1 | decision recorded |
| 1 | **Golden harness.** Render every example and profile combination (ITSD and customer-orders, under all four profiles), the caller-rendered SQL and the manifests. Store them under `tooling/build/tests/golden/` (export-ignored) and assert byte-identical | the harness passes on `main` and fails on any template change |
| 2 | **Core.** `model.py`, `generate.py`, `Dialect` and an empty `PortableDialect`. The generator **delegates any phase without a method to the existing Jinja template**, so ported and unported phases coexist | golden identical with nothing ported |
| 3 | **Postgres**, phase by phase. It is the contract platform. Each phase is written in `PortableDialect` when portable, otherwise in `PostgresDialect` | golden identical, Postgres engine tests green in CI, per phase |
| 4 | **DuckDB.** Mostly inherits, overriding the differences | as step 3 |
| 5 | **Teradata.** The migrated 1,238 lines, plus whatever step 0 kept | as step 3, plus a live run |
| 6 | **Remove** the templates, the Jinja bridge, `render.py` and the Jinja2 dependency. Update the standard, tests, roles and README sections | full suite, golden identical, package gate |

The golden snapshots also make review better. A PR that changes a dialect shows its effect as
an SQL diff in the snapshots, which is more than a template diff shows today. Committing
rendered SQL as test fixtures is a change of policy; see Q5.

**Size.** About 3,400 lines of migrated Jinja, or 5,370 if nothing is retired, become an
estimated 2,500 to 3,500 lines of Python across the core and three dialects. Removing the
duplication shrinks it; method signatures and docstrings grow it. Postgres plus the portable
base is the largest single piece. DuckDB should be small. Teradata depends on step 0.

**File count.** `implementation/` goes from 117 files to about 13. The package goes from 194
to about 95. Each new platform adds about 4.

## 6. Guardrails

These replace the template-specific gates in the simplification design (§6 there):

| Gate | Fails when |
|---|---|
| `golden` | any rendered output differs from its snapshot without the snapshot being updated in the same PR |
| `dialect-purity` | a dialect imports outside the standard library and core, calls I/O, reads the clock or environment, or holds a product literal (AST check) |
| `dialect-duplicate` | an override's rendered output equals its parent's for every golden input, which means it repeats the parent |
| `dialect-coverage` | a public method is reached by no phase, check or documented caller API |
| `binding-budget` | a binding directory holds more than 6 files |
| `package-budget` | as in the simplification design |

## 7. Risks

| Risk | Mitigation |
|---|---|
| A rewrite silently changes deployed SQL | Golden snapshots from step 1, byte-identical at every step; engine tests in CI |
| SQL embedded in Python is harder for an SQL reviewer to read than a template | SQL laid out as multi-line literals; snapshots show the actual SQL in every PR |
| Fragile base class: a change to a portable default silently changes every platform | Golden tests per platform catch it; a portable change must update every platform's snapshots, which makes the reach visible |
| Inheritance sprawl | Platforms extend `PortableDialect` only (Q3); mixins named and kept in the portable module |
| The skill's runtime can't run the generator | Standard library only (Python 3.11 or later), which also removes the Jinja2 install the build needs today |
| Caller-rendered SQL breaks external pipelines | Stable public method signatures, a command-line form, and covered by golden tests |
| Contributors who know SQL but not Python | One worked example per method in the portable module; overriding is copy and edit |
| Migration stalls halfway, leaving two mechanisms | The Jinja bridge is temporary by design; step 6 is part of the plan's definition of done; the bridge is deleted with the last template |

## 8. Alternatives considered

| Alternative | Why not |
|---|---|
| **Keep Jinja, do B2 and C1** | Cheaper and safe, and it gets to about 120 files. But the logic stays in Jinja, sharing needs a loader chain and a duplicate check, and each platform still costs about 14 files. It is the right fallback if this design is rejected |
| **One process per object** | §0, point 3 |
| **Subclass each specification object per platform** | §0, point 2: two inheritance axes, and a class per platform for every object kind |
| **sqlglot** (write once, transpile to each dialect) | We stop controlling the exact output, Teradata coverage is partial, and an upstream release can change deployed SQL. That fails G4 and G7 |
| **SQLAlchemy Core** for DDL | A dependency (fails G5). Poor coverage of what we emit: Teradata primary indexes, `LOCKING`, comment syntax, temporal constraints. The output isn't laid out for review |
| **Generate the templates from Python** | Two mechanisms, and generated files in the repository |

## 9. Open questions for review

1. **Go or no go.** Adopt this and stop B2 and C1, or keep Jinja and do B2 and C1?
2. **Teradata port-or-retire** for graph lineage and the catalogue interface. This decides
   most of the Teradata effort, and it is needed whichever way Q1 goes.
3. **Inheritance between platforms.** Platforms extend only `PortableDialect` (recommended),
   or may DuckDB extend Postgres directly?
4. **Where `PortableDialect` lives.** `implementation/portable/`, so platform SQL stays out of
   `tooling/` (recommended), or `tooling/build/`?
5. **Golden snapshots of rendered SQL** committed as test fixtures, export-ignored. This
   reverses "rendered SQL is not checked into this repository" for tests only. Acceptable?
6. **Order against the configuration change** (TOML). Do the configuration change first,
   because it is smaller and touches the resolver, or after the generator, because both
   rewrite `test_binding_package` and the authoring standard?
