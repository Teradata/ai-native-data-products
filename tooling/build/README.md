# tooling/build: organisation profiles and the build context

A build has three inputs: a **design specification** (what the product is), an
**organisation profile** (where it lives and what it is called in this organisation), and a
**platform binding** (how it is realised on this platform). This directory holds the shared
step between the first two and the third: it validates a profile and resolves a
specification and a profile into one **build context**, the only thing a binding's dialect
read. See the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3.

Stdlib only, Python 3.11 or later (for `tomllib`).

## Check a configuration

```bash
python tooling/build/org_profile.py config/implementation.example.toml
```

It lints every target, each with the design file beside it (`--target` for one, `--design` for a
design file elsewhere).

Rules come from the tables of the [Organisation Profile Standard](../../design/core/ORGANISATION_PROFILE.md):
required headings and blocks, field types and enumerations, template variables and filters,
object roles, one-to-one standard-name mappings, classification and protection, and the
profile's own worked derivation examples, which are re-derived and must agree.

## Resolve a build context

```bash
python tooling/build/build_context.py SPEC.md PROFILE.md [--environment PHASE] [--out context.json]
```

The specification is checked by [`spec_lint`](../evals/) and the profile by `org_profile`
first; resolution does not start on an invalid input. Resolution then:

- assigns every entity to its module and places its table, consumer view and whatever else
  the binding declares it emits (base views, sequences, point-in-time and similarity
  functions);
- places the standard-owned relations of each included module (the table in the Design
  Specification Standard §4.1 says which), by facet where the module has them;
- names attributes, applying the organisation's mapping of standard-owned names;
- names or binds the principal for each access tier, or records how a tier is enforced
  outside a platform that has no principals;
- maps sensitivity markers to the organisation's classes and protection;
- substitutes adopted containers and entities;
- applies the environment's container template where phases share a system;
- checks names against the platform's length limit and reserved words, checks for
  collisions, and checks audit retention against the organisation's bounds;
- renders every derivation, metric, condition and quality rule through the binding's
  declared SQL fragments, carrying unrenderable ones as reported gaps;
- settles what the build captures into Memory (decision, cookbook, note and change-log ids)
  and the orientation resources Semantic publishes, so every binding writes the same records;
- records every default it applied in `defaults_applied`.

Any problem fails the run with a message naming the fact and the input it belongs to, and
no context is written.

The context's shape is fixed by [`build_context.schema.json`](build_context.schema.json),
the same for every platform. A binding reads names from it and never derives one: no
concatenated container names, no defaults in a dialect (Authoring Standard §6).

## Worked inputs

| Specification | Configurations |
|---|---|
| [`examples/it-service-desk-data-product/design-output/design_specification.md`](../../examples/it-service-desk-data-product/design-output/design_specification.md) | any target of [`config/implementation.example.toml`](../../config/implementation.example.toml) (`teradata`: one database per module, `ITSD_*`; `postgres`; `duckdb`), or of [`examples/it-service-desk-data-product/contrasting/implementation.toml`](../../examples/it-service-desk-data-product/contrasting/implementation.toml) (type-grouped, snake case, mapped column names, an adopted entity, container-isolated environments) |
| [`tooling/evals/reference/customer-orders.md`](../evals/reference/customer-orders.md) | any of them: every name derives from the specification's `product_code` |

To render a binding from a resolved context, see [`tooling/bindings`](../bindings/).
