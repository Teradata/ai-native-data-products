---
name: ai-native-data-product
description: Design, build, review, or query an AI-Native Data Product - a self-describing data asset optimised for autonomous agent discovery. Load when modelling a data product's modules, entities, capabilities and design decisions; when generating deployable platform DDL from an approved design; when assessing how far a built product can be trusted (trust map, invariants, conformance rules, validation evidence); or when accessing, discovering and querying a product that is already
deployed. Covers the module library (Domain, Search, Prediction, Observability, Semantic, Memory), composition rules, the logical design language, and the platform bindings that realise them.
---

# AI-Native Data Product Standards

This repository **is** the standard. Everything below is read on demand: open only what the
task in front of you needs.

## Pick your role first

| You are asked to… | Read next |
|---|---|
| Design a product, or extend an existing design. No platform, no SQL. | `roles/design.md` |
| Turn an approved design into deployable artefacts for a platform. | `roles/build.md` |
| Assess how far a design or a built product can be trusted. | `roles/review.md` |
| Discover and query a product that already exists. | `roles/access.md` |

If the request is ambiguous, ask. The roles read different halves of the corpus, and
guessing wrong wastes the user's time as well as yours.

Each role file gives you the working procedure and tells you which corpus files to open.
Do not read the whole corpus up front.

## What the repository holds

```
design/            platform-agnostic standards: the source of truth for what and why
  core/            MASTER_DESIGN (blueprint, compositions, deployment sequence)
                   DESIGN_LANGUAGE (the notation everything is written in)
                   ADVOCATED_STANDARDS (the decisions a design must settle)
                   GLOSSARY
  modules/         domain · search · prediction · observability · semantic · memory
  patterns/        temporal-lifecycle-metadata · object-placement · physical-storage ·
                   validation · access-layer
implementation/
  teradata/        the concrete binding: DDL templates, queries, grants, platform profile
tooling/
  validation/      design_lint.py - checks the standards are well formed
  evals/           brief_lint.py  - checks a product design against the standards
examples/          worked products: fixed inputs for an end-to-end run
roles/             the four working procedures
```

New platforms are added as sibling directories under `implementation/`, changing no design
document.

## Rules that hold for every role

**The repository is the source of truth.** Where anything you have been told conflicts with
a file here, the file wins. Cite the file.

**`design/` is platform-agnostic and stays that way.** Logical types, capabilities, and
invariants only: never a platform type, never SQL. `implementation/{platform}/` binds it.
Every capability named in a design document has a binding there, and every invariant has a
check.

**Never invent a container, database, or object name.** Placement comes from the
object-placement standard at build time and from the product's own registries at access
time. A name derived from a convention will either fail loudly or, worse, resolve to a
different object than you meant.

**Design order is not deployment order.** Design Domain first, because every other module
references its entities. Deploy Memory and Semantic first, because every other module needs
somewhere to register as it lands. See MASTER_DESIGN §10.

**Never assume filesystem access.** Agree with the user where your output goes - a file,
this conversation, their repo, or an MCP resource - based on what you can actually reach.

**The product is its own artifact store.** Once built, design decisions live in Memory
(documentation facet), structure in Semantic, and validation evidence in Observability. The
next role reads them from there. The one transient artifact is the pre-build design brief,
because Memory does not exist yet to hold it.
