# Simplification design: keeping the skill under its file limit

**Status:** draft for review (Nathan, Paul). Nothing in this document has been changed in the repository yet.
**Tracks:** [issue #80](https://github.com/Teradata/ai-native-data-products/issues/80), repository over the skill file limit.
**Measured on:** the head of PR #76 (`feat/metadata-contract-2-0`), 2026-10-21.

## 1. The problem

The repository is the skill. An install receives the tracked files of one commit, and a skill
upload stops at 200 files. PR #76's head tracks **250**. `main` tracks 218, so we are over the
limit on `main` as well, not only on the PR.

The count is rising fast: 120 files on 2026-08-12, 263 on 2026-10-14, 250 today. Cutting files
once fixes nothing for long. The growth comes from how the repository is shaped, and this
document is mostly about changing that shape.

The workaround in #80 (delete the platforms you don't need before you upload) works, but it
asks every user to edit the standard before they can install it. It also stops working on the
day the core alone passes 200.

## 2. Where the files are

| Area | Files | Notes |
|---|---:|---|
| `implementation/teradata` | 62 | |
| `implementation/postgres` | 45 | |
| `implementation/duckdb` | 44 | |
| `tooling/` | 37 | 14 of them are tests |
| `design/` | 23 | 3 are `.gitkeep` in directories that already have files |
| `examples/` | 16 | 4 organisation profiles, one per platform variant |
| `release/` | 6 | |
| `roles/`, `prompts/` | 8 | 4 each, one for each role |
| `docs/` | 2 | |
| Root and `.github/` | 7 | |
| **Total** | **250** | |

`implementation/` holds 151 of the 250 files (60%). Each platform costs about 45 files, so
**adding a platform is what moves the count**, and we plan to add more. At the current shape,
the roughly 100 non-binding files leave room for two platforms, and we have three.

### 2.1 Why a binding costs about 45 files

Each binding has:

- **4 fixed files**: `README.md`, `PLATFORM_PROFILE.md`, `CONFORMANCE.md`, `deploy.sql.j2`.
- **11 area READMEs**: one per module (6) and one per pattern (5). Across the three platforms
  that makes 37 READMEs, a quarter of `implementation/`. They follow one shape (templates,
  capability bindings, invariants and checks) and are 20 to 80 lines each.
- **About 29 templates**, one file for each phase or check.

The template count is high for three reasons, and each one points at a fix:

1. **Stub files.** Every module has a `01-tables.sql.j2` that does nothing except call
   `module_tables('<module>')`. That is 6 one- or two-line files per platform, 18 in all.
2. **One check, one file.** The five metadata-contract checks (`contract/*.sql.j2`), the five
   validation checks and their macros are each a file of 8 to 90 lines.
3. **Byte-identical copies across bindings.** 13 of DuckDB's 29 templates are identical to
   Postgres's. Two of them, `modules/semantic/02-registration.sql.j2` (188 lines) and
   `patterns/validation/03-relationship-reference.sql.j2`, are identical on all three
   platforms. Most of the other DuckDB/Postgres templates differ by fewer than 25 lines.

The standard asks for this layout. `IMPLEMENTATION_AUTHORING.md` §5 requires "a directory per
supported module and pattern, mirroring `design/` by anchor". That rule makes per-platform
growth part of the design, and it is the rule this document proposes to change.

### 2.2 Files that ship but are never read in a session

An agent working through the skill never opens the tests, `.github/`, `.gitignore`, the
`.gitkeep` files, `REMAINING_WORK.md` or `docs/`. No role file routes to them. They make up
about 25 files.

## 3. Principles for the pass

These are the constraints I've assumed. Please challenge any you disagree with.

1. **The repository stays the skill, with nothing generated.** `tooling/skill/README.md` gives
   the reason: a generated bundle drifts from the corpus, and the compiled packages that came
   before shipped dangling routes. A filter on what ships is fine. A rewrite of what ships is
   not.
2. **No platform exceptions.** Whatever structure we choose, every binding follows it. None
   is the reference that the others are measured against.
3. **`design/` stays platform-agnostic.** None of the options below touches that.
4. **Rendered output must not change.** A simplification pass that changes the DDL is a
   feature change hidden inside a refactor. Each step is accepted on the evidence that the
   IT Service Desk example renders byte-identical before and after, on every platform.
5. **Progressive disclosure still works.** Fewer files must not mean that an agent loads a
   2,000-line file to read one module. The routes cite sections, and file sizes have a
   budget too.
6. **Every limit has a gate.** If a constraint is not checked in CI, it will slowly stop
   being met.

## 4. Options

The levers fall into four groups. They can be combined, and the recommendation in §5 does
combine them.

### A. Filter what ships (one-time saving of about 25 files)

Mark the files that are not needed at runtime `export-ignore` in a `.gitattributes`. GitHub's
"Download ZIP" and `git archive` both honour it, and `verify_skill.py --package` already
builds its package with `git archive`, so the existing gate checks the filtered package
without any change.

- **Ships out:** `tooling/**/tests/`, `.github/`, `.gitignore`, `.gitattributes`, `docs/`,
  `REMAINING_WORK.md`. The `.gitkeep` files are deleted outright.
- **For:** a few lines, no change to the layout, nothing generated, and the gate already
  covers it.
- **Against:** it is a one-time saving and does nothing about the slope. A `git clone` install
  ignores `export-ignore`, so the install instructions need to say "upload the ZIP".
- **To check:** whether Claude Code's skill or plugin install path has the same 200 limit and
  installs from a clone. If it does, this option helps claude.ai only.

### B. Consolidate within a binding (per-platform cost from about 45 files to about 14)

Change the unit of a binding from *a directory per area* to *a document per platform and a
template per area*.

- **B1. One binding document per platform.** Merge `README.md` and the 11 area READMEs into a
  single `implementation/{platform}/README.md` (or `BINDING.md`), with one numbered section
  per module and pattern. The content stays the same. Only its container changes. Routes go
  from `implementation/{platform}/modules/{module}/` to `implementation/{platform}/README.md §N`,
  and `verify_skill` already checks `§N` citations. Saving: 33 files today, 11 for each new
  platform.
- **B2. Address macros, not files, from `Phases:` and `Checks:`.** Allow a declaration of the
  form `<template>#<macro>` (for example `01-memory.sql: modules/tables.sql.j2#memory`, or
  `contract identity: checks/contract.sql.j2#identity`). Then the stubs, the five contract
  checks and the five validation checks each collapse into one file. `render.py` needs a small
  change to call a macro on a template module. Templates already live behind declarations,
  because `PLATFORM_PROFILE.md` maps phases to files, so the directory layout is not
  load-bearing.
- **Target shape for one binding:** `README.md`, `PLATFORM_PROFILE.md`, `CONFORMANCE.md`,
  `deploy.sql.j2`, plus about one template per module that has phases and one per pattern.
  That is roughly **12 to 15 files**.
- **For:** fixes the slope where it starts, needs no new concepts, and each platform stays
  self-contained.
- **Against:** it changes `IMPLEMENTATION_AUTHORING.md` §5, touches every route into
  `implementation/`, and conflicts with any PR that edits binding files while it is in flight.
  The files get larger, which is why there is a size budget in §6.

### C. Share across bindings (removes the duplication and the drift that comes with it)

Let a binding resolve a template it does not hold from a shared layer.

- **C1. A portable layer.** `implementation/_portable/` (no `PLATFORM_PROFILE.md`, so platform
  discovery already skips it) holds templates written to portable SQL. The Jinja loader
  searches `[implementation/{platform}, implementation/_portable]`, and a binding overrides a
  template by holding its own copy. The same rule applies to every platform, so it is not an
  exception. The two templates identical on all three platforms move there first.
- **C2. Declared inheritance.** A binding declares `Extends: postgres` in its `Binding:` block,
  and the loader chain becomes `[duckdb, postgres]`. DuckDB would then hold only the templates
  that differ. Most of those differ by a handful of lines, and some of that could become
  `Functions:` fragments or settings, which take the differences out of SQL and put them in
  data.
- **For:** the cheapest platform to add is one close to an existing one, which covers several
  of the likely next ones (other Postgres-family engines, ANSI-leaning warehouses). It also
  stops the copies drifting, which they will otherwise do.
- **Against:** a binding is no longer readable on its own, because you need the layer below
  to see what it renders. A change to the shared layer affects every binding that inherits
  it. C2 also makes one binding depend on another, which sits uneasily with principle 2 and
  makes option D harder. Teradata differs too much to gain anything yet.

### D. Split the skill (removes the ceiling)

Ship a core skill (`SKILL.md`, roles, `design/`, tooling, examples) and one skill per platform
binding. A user installs the core plus the platforms they use, which is #80's workaround made
official.

- **For:** each package has its own 200-file budget, so adding a platform never threatens the
  core.
- **Against:** routes cross package boundaries. `roles/build.md` points at
  `implementation/{platform}/` and `tooling/` points at the bindings, and in separate installs
  those paths no longer line up. It also means two installs instead of one, version skew
  between the core and a binding, and two `SKILL.md` descriptions competing to trigger.
- **When:** not now. It is the scale-out path for when the number of platforms outgrows B and
  C. If we keep each binding in one directory and give it no dependency on another binding,
  the split stays a packaging change and not a redesign. That is a point against C2.

### Options considered and not recommended

- **A generated bundle** (concatenate or zip the corpus at release time). This reverses the
  decision recorded in `tooling/skill/README.md` and brings back the drift problem.
- **Fetching bindings at runtime** from GitHub or an MCP resource. This breaks "never assume
  filesystem access" and makes an offline build impossible.
- **Fewer platforms.** It hides the problem without solving it.

## 5. Recommendation

**A now, B as the main pass, C1 only where files are already identical, D designed for but
not built.** C2 is held back until a fourth platform shows whether inheritance pays its way.

Rough count after A, B and C1:

| | Files |
|---|---:|
| Core after A (design 20, roles 4, tooling about 23, examples 16, release 6, root 5, prompts 4) | about 78 |
| `_portable/` | about 3 |
| 3 bindings at about 14 | about 42 |
| **Shipped total** | **about 123** |
| Headroom to a 180 budget | about 57, or 4 more platforms at 14 |

Folding `prompts/` into the role files (they are 35 to 39 lines each and mostly point at the
role) would save 4 more files. It is listed as an open question, not part of the
recommendation.

## 6. Guardrails against creep

A one-time cut lasts only as long as nothing checks it. These gates make creep fail in CI, not
in a user's upload. All of them belong in `verify_skill.py` or `design_lint.py`, which already
run in CI.

| Gate | Fails when | Why |
|---|---|---|
| `package-budget` | the shipped package (after `export-ignore`) passes **180** files; warns at 160 | keeps headroom under the hard 200, and the failure lists the largest areas |
| `binding-budget` | one `implementation/{platform}` passes **16** files | puts the limit on the slope, where growth happens |
| `duplicate-template` | two bindings hold byte-identical templates (after whitespace normalisation) | the copy belongs in `_portable/`; this stops the drift that C1 removes |
| `stub-template` | a template has fewer than 3 non-comment lines | the content belongs in a macro, addressed per B2 |
| `doc-size` | a binding or design document passes about 600 lines | keeps progressive disclosure working once files are merged |

Two rules for `IMPLEMENTATION_AUTHORING.md` and the PR checklist:

- **A new file has to justify itself.** It earns a file only if an agent loads it on its own
  (a separate route), or if a tool addresses it as a file and cannot address it as a section
  or macro. Otherwise it is a section.
- **PR descriptions report the net change in shipped files.** It costs nothing to write, and
  reviewers see the trend.

## 7. Process

Each phase is its own PR, merged in order, starting after #76 merges so the pass runs on a
clean base. Every PR that touches `implementation/` carries the same evidence: the IT Service
Desk example renders byte-identical on all three platforms before and after, the test suite
passes, and `verify_skill.py --package` passes.

| Phase | Change | Shipped files after (approx.) | Depends on |
|---|---|---:|---|
| 0 | Agree this document. Confirm the limit (§9, Q1). Add `package-budget` in report-only mode | 250 | review |
| 1 | Option A: `.gitattributes` and delete the `.gitkeep` files; update the install instructions | about 225 | 0 |
| 2 | B1: one binding document per platform; update §5 of the authoring standard and the routes | about 192 | 1 |
| 3 | B2: macro-addressed phases and checks in `render.py` and `binding.py`; collapse stubs and checks | about 135 | 2 |
| 4 | Configuration as data (§8): `binding.toml` per platform, then the organisation's two configuration files | about 132 | 3, Q8 to Q10 |
| 5 | C1: `_portable/` and loader chain; move the identical templates | about 120 | 4, Q3 |
| 6 | Turn every gate in §6 on in failing mode | about 120 | 5 |
| Later | D when the platform count calls for it; C2 if a fourth platform shows it pays | | trigger |

Phase 2 is the first that gets us under 200. If we need to be under the limit sooner, phases 1
and 2 can go out together.

## 8. Configuration as data

Platform profiles and organisation profiles are markdown documents. Their values sit in
`Block: -` notation inside fenced code blocks, which `spec_notation.py` parses, and the prose
around them is never read by a build. They really are configuration: each one sets variables
for the resolver. This section proposes making them configuration files, and giving an
organisation one place to change how the standard behaves for them.

### 8.1 Two kinds of profile, with different owners

The word "profile" covers two things that need different treatment:

| | Platform profile (`implementation/{platform}/PLATFORM_PROFILE.md`) | Organisation profile (`examples/.../profiles/*.md`) |
|---|---|---|
| Owner | us, the binding authors | the user's organisation |
| Holds | what the platform *is*: quoting, types, functions, phases, checks, gaps, and which settings exist with their permitted values and defaults. Also prose physical-design guidance (primary index, partitioning, statistics) that the build agent reads | what the organisation *chooses*: containers, naming, placement, principals, classification, retention, environments, adoption, catalogue, setting values |
| Changes when | the binding changes | the organisation's standards change |
| Ships in the skill | yes | an example ships; the real one belongs to the user |

They should stay separate. A user customising their environment should never edit a binding's
type map, and a binding upgrade should never overwrite a user's naming rules.

### 8.2 Proposal

**Binding declarations become `implementation/{platform}/binding.toml`.** The `Binding:`,
`Types:` and `Functions:` blocks, including `Phases`, `Checks`, `Gaps` and the declared
`Settings`, are already pure data that `binding.py` parses. As TOML they need no custom
parser and read as what they are. The prose physical-design guidance moves into the
binding's README (B1). The file count stays the same (one `.md` becomes one `.toml`), but
the line between "data the tool reads" and "guidance the agent reads" becomes a file
boundary. Platform discovery changes from "has a `PLATFORM_PROFILE.md`" to "has a
`binding.toml`".

**An organisation keeps two configuration files, not one per platform:**

- **`design.toml`: design configuration, with no platform content.**
  - `classification`: the organisation's scheme mapped onto the design's sensitivity markers.
  - `retention`: what the organisation permits.
  - `decisions`: the organisation's position on each `DEC-*` decision in
    `ADVOCATED_STANDARDS.md`.
  - The design role may read this file. `roles/design.md` forbids it from reading
    `implementation/`, so platform content must not leak into it.
- **`implementation.toml`: implementation configuration, one entry per target.**
  - Top level: what holds across platforms, such as environments and the catalogue.
  - `[targets.<name>]`: one entry per deployment target, each naming its `platform` and
    carrying that target's containers, naming, placement, principals, adoption and setting
    values.

Today classification, environments and often naming are repeated in every per-platform
profile. The ITSD Postgres profile says so in its introduction: its classification and
environments "are the same" as Teradata's. One file removes the copies.

I'd key the entries by **target**, not by platform. An organisation may run two Teradata
systems with different placement, and the example already has two Teradata profiles
(`teradata.md` and `teradata-type-grouped.md`). "Target" also avoids a clash with the
existing `Environments:` block, which means dev, test and prod.

Targets that are mostly the same share settings through an explicit key, without copying
them. `extends = "teradata-prod"` means "start from that target and override what I list
here". That keeps the "change it in one place" property inside the implementation file, and
anyone reading the line can see where the rest comes from. The resolver applies `extends`
before validation and rejects a cycle or a missing target.

### 8.3 Where the user's files live

This is the part that most affects usability. The repository is the skill, so a
`config/` directory at its root that users edit has two problems:

- **An upgrade overwrites it.** Replacing the skill with a new version replaces the user's
  standards with ours.
- **Users have to edit the package.** A claude.ai upload would mean unzipping, editing and
  re-zipping the skill to change a naming rule.

So I'd recommend:

- The skill ships `config/design.example.toml` and `config/implementation.example.toml`,
  filled in for the ITSD example organisation. They replace `examples/.../profiles/*.md`
  (4 files down to 2).
- The user's own copies live in *their* project, not the skill. Tooling takes them as
  arguments (as it takes the profile today) or finds them at a fixed path in the working
  directory. The roles tell the agent to ask for them, or to use the example.
- Precedence, lowest to highest: the standard's advocated option, the organisation's
  `design.toml`, then the product's design specification, which still records each decision
  and its reason.

### 8.4 Org-level decision policy is a new capability

Today `ADVOCATED_STANDARDS.md` says "a standard recommends, a product decides", and there is
no organisation layer in between. A `[decisions]` table in `design.toml` would add one. For
each `DEC-*`, the organisation could:

- set its own **default**, which the design role offers in place of ours, or
- **require** an option, so that `spec_lint` fails a specification that departs from it.

This fits the goal of making the standard configurable to an organisation's governance. But
it is new behaviour, not a format change, so it is listed separately (Q10). It could land
after the format change.

### 8.5 Format: TOML (decided)

**Decision (2026-10-21): configuration files are TOML.** Users edit these files by hand to
match their own standards, so the format with the fewest ways to go silently wrong is the
simplest one for them. Most people can read TOML on sight, and anyone who has set up a
modern Python project has already edited `pyproject.toml`.

TOML (Tom's Obvious, Minimal Language, version 1.0 in 2021) was designed for configuration
files that people edit by hand. Python reads it with `tomllib`, in the standard library since
3.11. CI runs 3.12. The standard library has no TOML writer, and we only need to read.

#### The same configuration in each format

The Postgres target from the ITSD example, in TOML:

```toml
# implementation.toml: how this organisation builds, one entry per target

[environments]
phases    = ["dev", "test", "prod"]
isolation = "system"

[targets.postgres]
platform         = "postgres"
platform_version = "16"

[targets.postgres.containers]
memory   = "{product_code|lower}_{module}"
semantic = "{product_code|lower}_{module}"
access   = "{product_code|lower}_access"

[targets.postgres.naming.objects]
table           = "{entity|snake}"
consumer_view   = "{entity|snake}"
function        = "at_{entity|snake}"
function_search = "similar_{entity|snake}"
```

The same in YAML, the alternative considered:

```yaml
# implementation.yaml: how this organisation builds, one entry per target

environments:
  phases: [dev, test, prod]
  isolation: system

targets:
  postgres:
    platform: postgres
    platform_version: "16"                     # unquoted, 16 becomes a number
    containers:
      memory: "{product_code|lower}_{module}"  # unquoted, { starts a mapping
      semantic: "{product_code|lower}_{module}"
      access: "{product_code|lower}_access"
    naming:
      objects:
        table: "{entity|snake}"
        consumer_view: "{entity|snake}"
        function: "at_{entity|snake}"
        function_search: "similar_{entity|snake}"
```

For comparison, today's form is a `Containers: -` block in a fenced code block inside a
markdown profile, parsed by our own `spec_notation.py`.

#### Comparison

| | TOML | YAML | Markdown blocks (today) |
|---|---|---|---|
| Strings | always quoted, so a value means what it looks like | quoting optional: unquoted `{...}` becomes a mapping, `16` a number, and `no`/`on`/`off` booleans in some loaders | unquoted text, read by our parser |
| Indentation | doesn't matter | determines structure; a wrong indent can still parse, into the wrong structure | significant inside a block |
| Our naming templates | no trap: they are strings like everything else | every template starts with `{`, so every one needs quotes, and forgetting gives a confusing error | no trap |
| Dependency | none (`tomllib`) | PyYAML, new for the resolver | none, but a custom parser to maintain |
| Comments | `#` | `#` | prose around the blocks |
| Deep nesting | longer section headers, like `[targets.postgres.naming.objects]` | indentation, which is shorter | indentation |
| Sharing between targets | not built in; we add `extends` (§8.2) | anchors (`&naming`/`*naming`) | none |
| Lists of records | `[[phases]]` blocks, the one syntax that looks odd at first | `- ` list items | `- ` list items |
| Familiarity | Python projects (`pyproject.toml`), Rust, Hugo | wider: Kubernetes, CI pipelines, Ansible | our own notation |
| Editor validation | with a schema (Even Better TOML / Taplo) | with a JSON Schema (VS Code YAML extension) | none |

**What we give up, and why it matters less here.**

- **Long headers for deep nesting.** The configuration is shallow, two or three levels under
  a target, so the headers stay readable. They also show you where you are in a file that
  holds several targets.
- **No anchors.** `extends` replaces them. It is one explicit line, where anchors are a
  feature many YAML users have never met and can easily get subtly wrong.

**Rules that follow from the choice.**

- **Order lives in arrays.** Neither TOML nor YAML guarantees that a table's keys keep their
  order, so anything where order matters, such as deployment phases, is an array (for
  example `[[phases]]` with `file` and `template`), never the key order of a table.
- **Keys are snake_case.** Field names like `Max name length` and `function search` become
  `max_name_length` and `function_search`, so that no key needs quoting.
- **Templates stay strings** in the current `{variable|filter}` syntax, and `org_profile.py`
  keeps validating them as it does today.

**The schema.** Today the field tables in `ORGANISATION_PROFILE.md` *are* the schema:
`org_profile.py` reads them at runtime, so the standard and the validator cannot drift. That
should stay true. The cheapest route keeps those tables as the source and changes only the
instance format. A JSON Schema would give users autocomplete and inline errors in their
editor, which is a real usability gain. But it is a second source of truth unless the
markdown tables give way to it (Q9).

### 8.6 What else is configuration

- **The design specification stays markdown.** It's a document the design agent writes and
  a human approves, and its rationale matters as much as its values. Its blocks stay in the
  current notation, which `spec_notation.py` keeps parsing for specifications only.
- **Lists hardcoded in tooling.** `verify_skill.py` lists `MODULES` and `PATTERNS`, and
  `design_lint.py` holds `LOGICAL_TYPES`. The corpus already declares these, in `design/`
  frontmatter and in `DESIGN_LANGUAGE.md`. They should be discovered, as platforms already
  are, so that adding a module doesn't mean editing three tools. This is internal, not user
  configuration.
- **Budgets.** The gates in §6 read their limits from one place (`config/budgets.toml`, or
  constants in `verify_skill.py`). This one doesn't need to be a file.
- **Already data:** `release/v2.0.0/*.json`, `build_context.schema.json`, and test fixtures
  such as `trust_cases.json`.

### 8.7 Cost and acceptance

This touches `org_profile.py`, `build_context.py`, `binding.py`, `verify_skill.py`
(discovery), `ORGANISATION_PROFILE.md`, `IMPLEMENTATION_AUTHORING.md` §5.1, `roles/build.md`,
the examples, and most tests. It is a breaking change for anyone holding an organisation
profile today. Few people do, so converting the examples in the PR is enough, and no
converter needs to ship.

The acceptance evidence is stronger than for the other phases. For every example target, the
resolved `build_context.json` must be identical before and after, as well as the rendered
output.

## 9. Open questions for review

1. **The limit itself.** Is 200 the claude.ai upload limit, the Claude Code limit, or both?
   Do directories or hidden files count? Does Claude Code install from a clone (where
   `export-ignore` does nothing)? The answers decide how much option A is worth.
2. **B1: one binding document, or one document per module and pattern?** One file is fewer
   files. Two (`modules.md`, `patterns.md`) keep each read smaller. Teradata's would be the
   largest, about 700 lines merged.
3. **C1: is a portable layer acceptable under "no platform exceptions"?** My view is yes,
   because the rule is the same for every binding. But it does mean not all platform SQL sits
   in the platform's own directory.
4. **`CONFORMANCE.md`:** keep it in the binding (it is evidence the review role reads), or
   publish it as a CI artefact and the release bundle?
5. **`prompts/`:** fold the starters into the role files or the README?
6. **Example organisation profiles** (one per platform variant): keep one file per platform,
   or use one profile with per-platform blocks so that examples stop growing with each
   platform?
7. **Budgets:** are 180 total and 16 per binding the right numbers?
8. **Configuration location** (§8.3): do the user's files live in their own project, passed
   to the tooling, with only `*.example.toml` in the skill? (The format is decided: TOML,
   §8.5.)
9. **Schema source** (§8.5): keep the markdown field tables as the schema, or move to a
   schema file for editor validation and make the tables point to it?
10. **Org-level decision policy** (§8.4): should `design.toml` be able to set defaults for,
    or require, `DEC-*` options? And should it be in this pass or follow it?

## Appendix: measurements

Template overlap with DuckDB, counted as lines differing in `diff`, where 0 means identical:

| Template | DuckDB lines | vs Postgres | vs Teradata |
|---|---:|---:|---:|
| `modules/semantic/02-registration.sql.j2` | 188 | 0 | 0 |
| `patterns/validation/03-relationship-reference.sql.j2` | 8 | 0 | 0 |
| `modules/memory/02-capture.sql.j2` | 77 | 0 | 150 |
| `modules/semantic/contract/composition.sql.j2` | 40 | 0 | 31 |
| `modules/*/01-tables.sql.j2` (6 stubs) | 4 | 0 | 5 |
| `patterns/temporal-lifecycle-metadata/02-comments.sql.j2` | 8 | 0 | 17 |
| `modules/memory/validation.sql.j2` | 9 | 0 | 18 |
| `modules/semantic/contract/00-macros.sql.j2` | 9 | 0 | 14 |
| `deploy.sql.j2` | 8 | 0 | 14 |
| `modules/semantic/03-discovery.sql.j2` | 156 | 14 | 178 |
| `patterns/temporal-lifecycle-metadata/00-macros.sql.j2` | 126 | 17 | 112 |
| `patterns/validation/04-trust-map.sql.j2` | 92 | 4 | 177 |
| `patterns/validation/05-comment-coverage.sql.j2` | 31 | 48 | 55 |

File count over time (all tracked files / `implementation/`): 2026-08-12 120 / 69,
2026-10-14 263 / 162, 2026-10-21 250 / 151.
