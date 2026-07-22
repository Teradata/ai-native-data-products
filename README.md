# AI-Native Data Product Design Standards

A modular library of data design patterns for building **AI-Native Data Products** — self-describing
data assets optimised for autonomous agent discovery and operation. The library is a set of
independent, composable modules; assembling a chosen subset produces a particular kind of data asset.

---

## The design / implementation split

The framework is split along one boundary:

- **[`design/`](design/)** — **platform-agnostic** standards. Written in logical types, capabilities,
  and invariants; no platform SQL. This is the single source of truth for *what* and *why*.
- **[`implementation/{platform}/`](implementation/)** — **platform-specific** bindings (the concrete
  DDL, queries, and grants) that satisfy the design. Teradata is the current reference; new platforms
  are added as sibling directories, changing no design document.

The boundary is enforced automatically by the linter in [`tooling/validation/`](tooling/validation/):
a design document that leaks platform SQL fails the build.

```
ai-native-data-products/
├── design/                     ← platform-agnostic standards (source of truth)
│   ├── core/                   MASTER_DESIGN · DESIGN_LANGUAGE · GLOSSARY
│   ├── modules/                domain · search · prediction · observability · semantic · memory
│   └── patterns/               temporal-lifecycle-metadata · object-placement ·
│                               physical-storage · validation · access-layer
├── implementation/
│   └── teradata/               PLATFORM_PROFILE + modules/ and patterns/ bindings
├── tooling/
│   └── validation/             the design linter (+ tests)
├── prompts/                    how to use the standards
└── skills/                     generated agent skills (gitignored)
```

**Start here:** [`design/core/MASTER_DESIGN.md`](design/core/MASTER_DESIGN.md) (the blueprint) and
[`design/core/DESIGN_LANGUAGE.md`](design/core/DESIGN_LANGUAGE.md) (the notation everything is written in).

---

## Compositions — one library, many patterns

There is no single fixed architecture. Modules declare what they **provide** and **require** (each
requirement `[hard]` or `[soft]`); a composition is valid when every hard requirement is met within
it, and unmet soft requirements simply disable a feature. An **AI-Native Data Product is the fullest
composition**, not the only one.

| Composition | Modules | 
|-------------|---------|
| **Data Asset** | Domain + Memory (documentation) + Access Layer |
| **Traditional Data Product** | Domain + Semantic + Observability (+ optional Memory) |
| **AI-Native Data Product** | all six modules + Access Layer |
| **Search / Prediction extension** | added onto an existing Domain |

See [`design/core/MASTER_DESIGN.md#4-compositions`](design/core/MASTER_DESIGN.md).

---

## The six modules

| Module | Purpose | Composition role |
|--------|---------|------------------|
| **[Domain](design/modules/domain.md)** | Authoritative business entities — the source of truth | Root; stands alone |
| **[Semantic](design/modules/semantic.md)** | The discovery map — entity/column/relationship catalogue + orientation | Cross-cutting (soft) |
| **[Search](design/modules/search.md)** | Vector embeddings and similarity search | Hard-depends on Domain |
| **[Prediction](design/modules/prediction.md)** | Feature store and model outputs | Hard-depends on Domain |
| **[Observability](design/modules/observability.md)** | Events, quality, lineage; home of validation results | Cross-cutting (soft) |
| **[Memory](design/modules/memory.md)** | Agent runtime state **and** design memory (two facets) | Cross-cutting (soft) |

---

## The five patterns

Cross-cutting concerns that modules *apply* (referenced, never restated):

| Pattern | Concern |
|---------|---------|
| **[temporal-lifecycle-metadata](design/patterns/temporal-lifecycle-metadata.md)** | Canonical temporal/lifecycle contract; half-open SCD2; point-in-time |
| **[object-placement](design/patterns/object-placement.md)** | Where objects live and who may reach them (interface spec) |
| **[physical-storage](design/patterns/physical-storage.md)** | Object-storage layout beneath logical containers (interface spec) |
| **[validation](design/patterns/validation.md)** | The validation-result contract and the agent stop/go gate |
| **[access-layer](design/patterns/access-layer.md)** | The three roles and phased grants that make a product reachable |

---

## Deployment order

Modules deploy in dependency order — only those the composition includes:

| Phase | Deploy (if present) |
|-------|---------------------|
| 1 — Infrastructure | Memory, then Semantic |
| 1.5 — Access (initial) | Create roles; grant read on Semantic + Memory |
| 2 — Foundation | Domain, then Observability |
| 2.5 — Access (extend) | Extend grants to Domain + Observability |
| 3 — Enhancement | Search, Prediction |

---

## Tooling

`tooling/validation/design_lint.py` enforces the platform-agnostic boundary on `design/`:

```bash
python tooling/validation/design_lint.py design
python -m unittest discover -s tooling/validation/tests
```

---

## Key principles

1. **Platform-neutral by construction** — enforced by the design/implementation split and the linter.
2. **Modular and composable** — modules function independently and in any valid combination.
3. **Zero data duplication** — modules reference Domain by identifier and join back; never copy.
4. **Self-describing** — queryable metadata, standard patterns, and multi-hop discovery enable autonomy.
5. **Self-contained products** — discovery and documentation stores live within the product.
6. **Design memory** — every module records its decisions into Memory during design.

---

## License

Copyright © 2025-2026 Teradata Corporation. Licensed under Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0). See
[LICENSE.md](LICENSE.md) for full terms.

Developed by Teradata's Worldwide Data Architecture Team, Field Technology Organization.
