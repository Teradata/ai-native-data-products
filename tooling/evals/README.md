# tooling/evals: design specification validation

`design_lint` checks that the **standards** are well formed. `spec_lint` checks that a **design specification written against them** is complete and conformant. That is the other half of the question, and the one a designer actually faces.

## Two tests, one of them automated

Testing the standards means answering two different questions, and only one of them is deterministic.

**Does a design specification comply?** Pure structure. No model involved, runs in the test suite in milliseconds, gives a yes or no. That is `spec_lint`.

**Does the design skill produce a good design?** Needs a model, is not reproducible, and no scoring rubric turns it into a verdict you would trust. That stays a human job.

The second is made cheap by the first. After a material change to `design/`, run the design skill against the reference product, put its output through `spec_lint`, and read the diff against the fixture. The validator catches everything mechanical, so the reading time goes on judgement rather than on checking that thirty-six invariants were listed.

## Run it

```bash
python tooling/evals/spec_lint.py tooling/evals/reference/customer-orders.md
```

Exit code is `0` when the specification conforms, `1` when it does not. The reference specification is also asserted clean by the test suite, so a change to `design/` that invalidates it fails the build.

## What it checks

| Rule | Fails when… |
|------|-------------|
| `spec-frontmatter` | the specification has no frontmatter, omits a required key, carries an unrecognised key, or has a `product_code` that is not identifier-safe. Keys come from the [Design Specification Standard](../../design/core/DESIGN_SPECIFICATION.md). |
| `platform-reference` | the specification carries a `platform` key or names a platform anywhere. |
| `unknown-module` | a chosen module does not exist in `design/modules/`. |
| `invalid-composition` | a module's `[hard]` requirement is not met by a `Provides` inside the composition. Requirements met by `self`, `platform`, or `external` are satisfied by definition. |
| `unsettled-decision` | a decision the chosen modules raise is not settled, or is listed without a choice. |
| `unknown-decision` | a settled decision is not in the catalogue. |
| `invalid-choice` | a choice is not one of that decision's options. |
| `unjustified-choice` | a choice departs from the advocated option without a `because`. |
| `identity-shape` | a `[kind: History]` entity declares no `Identifier` or no `NaturalKey`. |
| `no-entities` | the specification models nothing. |
| `unacknowledged-invariant` | an invariant declared by a chosen module is not named in the specification. |
| `missing-profile` | an entity declares no temporal profile. |
| `unrecorded-departure` | an entity's profile falls outside its kind's defaults, or its allocation differs from the product's, with no `Decision:` applying to it. |
| `unresolved-reference` | a reference target is neither in the specification nor defined by an included module. |
| `missing-discriminator` | a reference with several targets has no `Enum` discriminator listing them. |
| `invalid-expression` | a `[derive:]` expression uses a function outside the vocabulary, an aggregate in a row context, or an attribute that does not resolve. |
| `timestamp-name` / `prohibited-name` | a `Timestamp` is not named `<event>_dts`, or an attribute takes a name the temporal pattern prohibits. |
| `missing-section` | an entity lacks a section its kind requires (`Volume:`), or a feature group lacks `Features:`. |
| `missing-block` | an included module or facet has no block it requires. |
| `missing-field` / `unknown-field` / `invalid-value` | a block or section field is missing, not in the standard's table, or invalid for its declared type. |
| `duplicate-block` | the same block is declared twice. |
| *(all `design_lint` rules)* | the specification contains platform SQL. A design specification is platform-agnostic, exactly as `design/` is. |

**Nothing about the standards is hardcoded here.** The capability graph comes from the module Provides/Requires tables, the decisions from the Decisions-to-settle tables and the catalogue, the invariants from each module's Invariants section. The notation rules (fields, types, enumerations, module requirements, the expression vocabulary) come from the tables of the Design Specification Standard, read by `spec_notation.py`, and the temporal profiles and names from the temporal pattern. Add a module, a capability, or a decision to `design/` and the validator expects it without being edited. That is the same trick the linter and the catalogue generator use, and it is what stops this becoming a second place to maintain the standards.

## The reference product

[`reference/customer-orders.md`](reference/customer-orders.md) is the fixture: one small product designed against the full AI-Native composition, re-validated on every test run.

It is deliberately dull. Four business entities, no domain complexity worth arguing about, chosen so that review attention goes to the standards rather than to the modelling. What it does cover is deliberate:

- **All four Domain entity kinds**: History, Reference, Relationship, Keymap.
- **The full composition**, so every module's contracts and all thirty-six invariants are exercised.
- **A `[pii]` attribute**, so the sensitivity path is live.
- **Embeddable text and an engineered feature**, so Search and Prediction are more than declarations.
- **One decision taken against the advocated option**, with its reason. Without this the `because` requirement would never be exercised and could rot untested.

That last point generalises. A fixture that only ever walks the happy path tests less than it appears to, so when adding to it, prefer the case that exercises a rule over the case that illustrates a concept.

## Adding a case

Cases live under `reference/`. A new one earns its place by exercising something the existing fixture does not: a partial composition, a soft requirement going unmet, an entity kind combination that is currently untested. Another full-composition product would cost a test run and prove nothing new.
