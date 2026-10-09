# tooling/build: organisation profiles and the build context

A build has three inputs: a **design specification** (what the product is), an
**organisation profile** (where it lives and what it is called in this organisation), and a
**platform binding** (how it is realised on this platform). This directory holds the shared
step between the first two and the third: it validates a profile and resolves a
specification and a profile into one **build context**, the only thing a binding's templates
read. See the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md) §3.

Stdlib only, Python 3.8+.

## Check a profile

```bash
python tooling/build/org_profile.py examples/it-service-desk-data-product/organisation-profile.md
```

Rules come from the tables of the [Organisation Profile Standard](../../design/core/ORGANISATION_PROFILE.md):
required headings and blocks, field types and enumerations, template variables and filters,
object roles, one-to-one standard-name mappings, classification and protection, and the
profile's own worked derivation examples, which are re-derived and must agree.

## Check the platform layouts

```bash
python tooling/build/platform_layout.py            # check every platform profile
python tooling/build/platform_layout.py --json     # export every layout as JSON
```

Each `implementation/{platform}/PLATFORM_PROFILE.md` declares a `Layout:` block under a `Layout`
heading. Its fields, types and permitted values are read from the field table of the
[Platform Layout Standard](../../design/core/PLATFORM_LAYOUT.md) §4.1. Platforms are discovered
from `implementation/`, so a new platform that omits the block fails. The JSON export is the
machine-readable platform layout that evaluators load.

## Resolve a build context

```bash
python tooling/build/build_context.py SPEC.md PROFILE.md [--environment PHASE] [--out context.json]
```

The specification is checked by [`spec_lint`](../evals/) and the profile by `org_profile`
first; resolution does not start on an invalid input. Resolution then:

- assigns every entity to its module and places its table, governed view and consumer view;
- places the standard-owned relations of each included module (the table in the Design
  Specification Standard §4.1 says which), by facet where the module has them;
- names attributes, applying the organisation's mapping of standard-owned names;
- names or binds the principal for each access tier;
- maps sensitivity markers to the organisation's classes and protection;
- substitutes adopted containers and entities;
- applies the environment's container template where phases share a system;
- checks names against the platform's length limit and reserved words, checks for
  collisions, and checks audit retention against the organisation's bounds;
- records the Master Design version as `standard_version`, which a binding writes with the platform name to the product registry ([Platform Layout Standard](../../design/core/PLATFORM_LAYOUT.md) §5);
- records every default it applied in `defaults_applied`.

Any problem fails the run with a message naming the fact and the input it belongs to, and
no context is written.

The context's shape is fixed by [`build_context.schema.json`](build_context.schema.json),
the same for every platform. A binding reads names from it and never derives one: no
concatenated container names, no in-template defaults (Authoring Standard §6).

## Worked inputs

| Specification | Profiles |
|---|---|
| [`examples/it-service-desk-data-product/design-output/design_specification.md`](../../examples/it-service-desk-data-product/design-output/design_specification.md) | [`organisation-profile.md`](../../examples/it-service-desk-data-product/organisation-profile.md) (one database per module, `ITSD_*`), [`organisation-profile-type-grouped.md`](../../examples/it-service-desk-data-product/organisation-profile-type-grouped.md) (type-grouped, snake case, mapped column names, an adopted entity, container-isolated environments) |
| [`tooling/evals/reference/customer-orders.md`](../evals/reference/customer-orders.md) | either |
