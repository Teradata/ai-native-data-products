---
title: Platform Implementation Authoring Standard
anchor: implementation-authoring
type: core
status: draft
version: 1.0
normative: true
---

# Platform Implementation Authoring Standard

## 1. Purpose and scope

One design specification, built with any conforming platform binding under any conforming organisation profile, must produce a working, conforming data product. This standard defines what a platform binding must do to make that true, and how conformance is shown.

It applies equally to every directory under `implementation/`. No platform is exempt and none is special. A binding that does not yet meet a requirement is **non-conforming**, and its gaps are reported as such; a gap is never reclassified as an exception.

The [Design Language](DESIGN_LANGUAGE.md) remains the authority for the design/implementation boundary. This document is a repository authoring contract, not a product-level choice in the [Advocated Standards](ADVOCATED_STANDARDS.md) catalogue.

## 2. The three build inputs

A build has exactly three inputs. A platform binding may depend on nothing else.

| Input | Produced by | Scope | Holds | Must not hold |
|---|---|---|---|---|
| **Design specification** | The design agent, approved by the designer | One product | Composition, entity models, settled decisions, module configuration, sensitivity, volumes and workload | Platform, container, role or physical names; platform types; SQL; organisation conventions |
| **Organisation profile** | The organisation's platform or data team | One organisation, reused by every product | Placement, naming, access model, classification and protection policy, retention constraints, environments, existing structures to adopt, permitted physical overrides | Product design |
| **Platform binding** | Binding authors, under `implementation/{platform}/` | One platform | Templates, platform profile, declared settings and defaults, coverage | Product or organisation specifics |

The **design brief** is the design agent's input and is not a build input. The target platform is selected at build time; a design specification does not choose it and must build on every platform whose binding covers its composition.

Each input answers one question. The specification decides *what* the product is. The profile decides *where it lives and what it is called* in this organisation. The binding decides *how* it is realised on this platform. Where they conflict:

- A specification that departs from a profile setting records the departure as a design decision with its reason. It never does so silently.
- A profile setting the binding does not support fails the build with a reported gap. It is never ignored.
- A specification fact the binding cannot realise is reported as a coverage gap for that binding. It is never approximated.

### 2.1 What the design specification must carry

Every fact a build needs from the product design must be present in a structured, machine-readable part of the specification: its frontmatter or a notation block defined by the Design Language. Prose explains and justifies; it is never the only statement of a fact a build consumes. A builder that has to interpret prose to decide what to generate will make different choices on different platforms, and the products will differ.

The specification must not name containers, principals, physical objects or a platform. Those come from the organisation profile and the binding, which is what lets one specification serve every organisation and every platform. The content and notation are defined by the [Design Specification Standard](DESIGN_SPECIFICATION.md) and validated by the specification linter, not restated here.

## 3. The build context

Shared tooling under `tooling/` resolves the design specification and the organisation profile into a single **build context**: one document, validated against one schema maintained in this repository. Every binding consumes the same build context. No binding defines its own input contract.

Resolution happens once, before any template renders:

- **Placement.** Every object's container is derived from the profile's placement rules.
- **Names.** Every physical name is derived from the profile's naming rules, including the physical names the organisation maps to standard-owned logical names (section 4.2).
- **Principals.** Access principals are named, or bound to existing principals, from the profile's access model.
- **Classification.** The specification's sensitivity markers are mapped to the organisation's classification scheme and protection policy.
- **Adoption.** Specification entities, containers and principals that the profile binds to existing structures are marked as adopted (section 4.3).
- **Validation.** Names are checked against the target platform's declared limits: length, permitted characters, reserved words. Retention decisions are checked against the profile's constraints. Composition dependencies are checked.

A required fact that is absent fails resolution, and the failure names the missing fact and the input it should come from. A default is applied only where a standard document defines an advocated default or a binding declares one, and the build context records every default it applied.

The build context schema is platform-independent: its *shape* is the same for every platform, even though the resolved names it carries are specific to one organisation and one target. It covers product identity, including an identifier-safe product code; composition, modules and facets; settled decisions; entities with their attributes, keys, references, temporal profile, surrogate allocation and classification; per-module configuration; resolved placement, names, principals and adoptions; environment; volumes and workload; and the binding settings the profile selects.

## 4. Organisation configuration

The organisation profile is how an organisation adapts the standard to its own environment without editing a standard or a template. It is machine-readable and validated before resolution; its format is defined by the [Organisation Profile Standard](ORGANISATION_PROFILE.md).

### 4.1 Required coverage

| Area | The profile declares |
|---|---|
| Placement | A conforming [object-placement](../patterns/object-placement.md) implementation, with its derivation expressed in a form the resolution tooling executes rather than interprets. Where object storage is used, a conforming [physical-storage](../patterns/physical-storage.md) implementation. |
| Naming | Object and attribute naming rules (case, separators, abbreviations, length) and the physical name for each standard-owned logical name it chooses to map. |
| Access | The physical principal for each standard access tier, any existing principals to reuse, and the grant level. |
| Classification | The organisation's classification scheme, the mapping from the specification's sensitivity markers to it, and the protection mechanism each class requires. |
| Retention and compliance | Bounds a product's retention decisions must satisfy. A specification decision outside a bound fails resolution. |
| Environments | The lifecycle phases and how placement varies between them. Object names stay environment-agnostic (`INV-MASTER-006`). |
| Existing structures | The adoption map (section 4.3). |
| Binding settings | Values for physical settings a binding declares as configurable, within the values it permits. |

### 4.2 Standard-owned names

The standards own the *logical* names of the structures they define: metadata relations, temporal and lifecycle attributes, and the standard access tiers. An organisation may map any of them to a physical name of its own. A binding takes every physical name from the build context, never from a literal, and registers the logical-to-physical mapping in the product's Semantic metadata, so an agent discovers objects through metadata rather than by assuming a name. Object names are not a contract ([Master Design](MASTER_DESIGN.md) §7).

How an agent first locates a product's discovery entry point is the one name an agent must resolve before it can read metadata. It is resolved through the organisation's catalogue, per the [catalogue-interface pattern](../patterns/catalogue-interface.md), and is never a fixed name.

### 4.3 Existing structures

An organisation's environment already contains data, containers and principals. The adoption map lets the profile bind a specification entity, a container or a principal to an existing object instead of creating one. A binding must either honour an adoption, creating nothing that conflicts with the existing object and registering it as the product's own, or report the adoption as unsupported. It must never create a duplicate alongside it.

The modes of adoption (referencing an existing object, wrapping it, or migrating from it) and the conformance obligations of each are defined separately. Until they are, a binding reports any adoption it cannot honour as a gap.

## 5. Required binding structure

Each platform directory provides:

- **`README.md`**: supported compositions, deployment order and limitations, then **one numbered section per supported module and pattern**, headed with its design anchor, as in ``## 5. Domain module (`domain`)``. Each section maps capabilities to bindings, logical types to physical representations, and invariants to executable checks or explicitly reported gaps, lists the build-context fields its templates read, and names the directory its templates are in. The sections are numbered in deployment order: object placement, temporal lifecycle metadata, then Memory, Semantic, Domain, Observability, Search and Prediction, then validation, access layer and physical storage, then any further pattern. The numbers are the same on every binding, because the role files cite them.
- **`PLATFORM_PROFILE.md`**: supported engine versions, driver constraints, physical defaults, naming limits, and every **binding setting** the organisation profile may supply, with its permitted values and default.
- **A template directory per module and pattern that renders something**, mirroring `design/` by anchor: `modules/{module}/` and `patterns/{pattern}/`. A module or pattern with nothing to render has its README section and no directory. A binding's documentation is that one README: a new module or pattern adds a section, not a file, because the skill ships under a file limit.
- **Templates** for every deployment, access, maintenance, discovery and validation artefact the binding produces, with ordering and dependencies documented.

Unsupported capabilities, compositions, profile settings and adoption modes are declared explicitly. An absent binding, a skipped check or an unexecuted engine test is never reported as conformance. Support for a minimal composition does not imply support for every module.

### 5.1 Binding declarations

A binding's `PLATFORM_PROFILE.md` carries three blocks the resolver reads when it builds a context for that platform. They are how platform SQL reaches the context without tooling holding any: the binding states its types, functions and quoting once, as data, and the resolver only substitutes. Each block opens `<Block>: -` in a fenced code block, as in an organisation profile.

#### `Binding:`

| Field | Required | Type | Value |
|---|---|---|---|
| `Identifier quote` | yes | text | The character that quotes an identifier. |
| `Literal quote` | yes | text | The character that quotes a text literal; it is doubled inside one. |
| `Principals` | yes | enum | `native` or `unsupported`: whether the platform grants to principals. |
| `Runtime scope` | yes | enum | `enforced` or `unsupported`: whether the binding restricts runtime Memory records to the requesting identity's scope at the access surface ([access-layer](../patterns/access-layer.md) §4). `unsupported` is reported as a gap in every build with runtime relations. |
| `Emits` | no | mappings | Object roles the binding emits beyond `table` and `consumer_view`, each with what it emits them for: `base_view: all`, `sequence: <allocations>`, or `function: <profiles>`; and `embedding` under `function` or `procedure` for one similarity search object per `Embedding:` block, as the platform can express it. |
| `Settings` | no | mappings | Each binding setting an organisation profile may set, with its permitted values and default, as `<setting>: <values>; default <value>`. |
| `Phases` | no | mappings | The deployment phases in order, each as `<file>: <template>`. A template that renders nothing for a composition emits no file. |
| `Deploy` | no | text | The template that joins the rendered phases into one deployable script. It reads `phases`, the rendered files in order, each with its `file` and `sql`. |
| `Gaps` | no | mappings | Each known gap no check can detect, as `<area>: <what is not covered>`: an untested composition or adoption mode, a constraint the engine cannot enforce, evidence the binding cannot produce. The conformance report lists them with the gaps the builds report (§8.1). |
| `Checks` | no | mappings | The validation checks a build manifest carries, each as `<scope> <check>: <template>`. Scope `entity` renders the template once per persisted relation, with `entity`; `relationship` once per relationship, with `relationship`; and `module` once, where `<check>` names a module anchor and that module is composed, with `module`. Every returned row is a defect. |

#### `Types:`

One field per logical type of the [Design Language](DESIGN_LANGUAGE.md), giving its physical type. `{p}` and `{s}` stand for a `Decimal`'s precision and scale and `{dim}` for a `Vector`'s dimension, and `{dim*n}` for the dimension times `n`, as for a binary encoding of `n` bytes an element. A logical type with no line is unsupported, and a context that needs it fails with a reported gap.

| Field | Required | Type | Value |
|---|---|---|---|
| `*` | yes | text | One line per logical type. |

#### `Functions:`

One field per function of the [Design Specification Standard](DESIGN_SPECIFICATION.md)'s expression vocabulary the binding can render, as a SQL fragment in which `{0}`, `{1}` ... stand for rendered arguments and `{args}` for all of them, comma-separated. A name may carry an arity, `name/2`, for a form that differs by argument count. `duration` renders a duration from `{n}` and `{unit}`; `map case` renders one `{key}`/`{value}` pair of a `map`; `true`, `false` and `null` render literals; and `flag test`, on a platform with no boolean type, renders a `Flag` that stands as a condition. A function with no line is unsupported: expressions using it carry no rendered SQL, and the binding reports the gap.

| Field | Required | Type | Value |
|---|---|---|---|
| `*` | yes | text | One line per function. |

## 6. Template rules

- **Jinja is the only template language.** Every platform artefact a binding maintains is a Jinja template. No other substitution convention (format placeholders, angle-bracket or brace tokens, find-and-replace markers) appears in a binding.
- **Templates read only the build context.** They contain no product, organisation, entity, container, principal or credential literal. Structure definitions owned by a standard and documented platform constants may be fixed; the names of standard-owned structures come from the context (section 4.2).
- **Templates do not derive.** They do not build container or object names by concatenation, infer placement from a naming convention, or supply their own default for a context value. Placement, names and defaults arrive resolved.
- **Missing values fail.** Rendering uses `StrictUndefined` or an equivalent that rejects a missing value.
- **Identifiers and literals are emitted through binding macros** that apply the platform's quoting and escaping. Runtime query parameters use the driver's value binding where one exists.
- **Composition is honoured.** Only included modules and facets render, and only their declared dependencies are assumed present.
- **Templates emit; they do not execute.** Rendered output is written to a product location outside this repository. Tooling may validate inputs, select templates and order phases; it must not become a second store of platform SQL.

## 7. Packaging and examples

Resolution, rendering, validation and test utilities belong under `tooling/`. Platform directories contain binding documentation, declarations and templates, not product-specific compilers or completed applications.

Examples supply inputs: a design brief, the reference design specification the design phase produces from it, one or more organisation profiles, and source data. They do not ship generated deployment SQL, populated databases or completed pipelines. The IT Service Desk example is the shared comparison case, and every binding must build it. The shared example does not limit a binding to IT Service Desk products.

Test fixtures and test-only loaders belong with the tests. Synthetic facts and model outputs are labelled as test data and never represented as source evidence.

## 8. Automated acceptance checks

Repository validation discovers platform directories directly under `implementation/`. There is no platform allowlist and no exception register; a new platform cannot escape a check by omitting a file, an example or a template.

| Check | Acceptance evidence |
|---|---|
| Input conformance | The reference specifications and organisation profiles validate against their schemas. A specification naming a platform, container, principal or physical object fails. |
| Resolution | A missing fact, invalid name, unsupported setting, retention conflict or incompatible composition fails with a message naming the fact and its source input. |
| Structure and coverage | Required documents exist. Every capability and invariant in a supported module or pattern maps to a binding and check, or to a declared gap. Every template is rendered by at least one test. |
| Template hygiene | No substitution convention other than Jinja. No product, organisation, container or principal literals. No in-template name derivation or defaults. |
| Portability | The IT Service Desk specification builds under two organisation profiles that differ in placement, naming and principals, and an unrelated product builds under one. No output contains another case's names or an unresolved expression. |
| Cross-platform | One specification and profile resolve to one build context, and every binding consumes it. Each binding reports the context fields and settings it does not support. |
| Composition | Declared minimal and larger compositions render with only their required dependencies. |
| Packaging | No generated product artefacts or product compilers in binding or example directories. |
| Engine behaviour | Rendered artefacts execute on the declared engine and version; temporal, metadata, discovery, access and invariant checks exercise actual behaviour. Engine tests use disposable environments and report the versions tested. |
| Corpus integrity | Design lint, frontmatter, catalogue and skill-package validation remain clean. |

Static naming and file-extension checks alone cannot establish portability. Review must also assess whether generated behaviour satisfies the design contracts. A skipped test is a gap, even when every other check passes.

### 8.1 Conformance status follows evidence

The checks produce a conformance report per binding: what passes, what fails, and each gap. A binding document, and the binding as a whole, may carry `status: standard` only when its report shows no gaps; otherwise it is `draft`. The report is generated from the checks, never maintained by hand: `tooling/bindings/conformance.py` runs the tests, renders the reference builds, and writes each binding's `CONFORMANCE.md` with every outcome, every gap the builds report, every gap the binding declares (`Gaps`, §5.1) and every skipped engine.

A pull request must not increase any binding's reported gaps. A binding with gaps can still be improved, used and merged into; it cannot be described as conforming. The same rule applies to every platform, existing and new.

## 9. Review and merge requirements

Pull requests that add or change a binding identify the compositions, profile settings and engine versions they affect, show the portability builds, and report the conformance results and remaining gaps.

The section 8 checks must run in pull-request CI, and branch protection or an equivalent ruleset must make them required before merge. A failed required check blocks merge; missing engine coverage is reported as a gap, never as a successful run. Where CI cannot reach an engine, its engine evidence may come from the committed report of a clean live run: CI still regenerates and compares everything else, fails on any engine test that report does not cover, and states that it trusted it. Changes to the checks themselves are reviewed alongside the bindings they affect.

This document specifies the policy; it does not install CI or configure branch protection. Until both exist, maintainers record the checks as manual evidence and describe enforcement as manual. Local checks alone do not prevent a merge.

## 10. Authoring completion checklist

Before presenting a binding change as ready to merge, its author provides:

- [ ] Templates that read only the build context, with coverage mappings for every supported module and pattern.
- [ ] Declared binding settings, defaults and unsupported features in the platform profile.
- [ ] The IT Service Desk build under two organisation profiles, and the unrelated-product build.
- [ ] Test and engine results with honest gaps, and the binding's conformance report.
- [ ] Evidence that the required merge checks are configured, or a statement that enforcement is still manual.

The reviewer verifies the semantic design obligations in addition to the mechanical checks.
