# AI-Native Data Product Design Standards

A modular library of data design patterns for building **AI-Native Data Products**: self-describing data assets optimised for autonomous agent discovery and operation. The library is a set of independent, composable modules; assembling a chosen subset produces a particular kind of data asset.

---

## The design / implementation split

The framework is split along one boundary:

- **[`design/`](design/)**: **platform-agnostic** standards. Written in logical types, capabilities, and invariants; no platform SQL. This is the single source of truth for *what* and *why*.
- **[`implementation/{platform}/`](implementation/)**: **platform-specific** bindings (the concrete DDL, queries, and grants) that satisfy the design. Teradata is the current reference; new platforms are added as sibling directories, changing no design document.

The boundary is enforced automatically by the linter in [`tooling/validation/`](tooling/validation/): a design document that leaks platform SQL fails the build.

```
ai-native-data-products/
├── SKILL.md                    ← agent entry point: role routing (see "As an agent skill")
├── roles/                      designer · builder · reviewer · consumer procedures
├── design/                     ← platform-agnostic standards (source of truth)
│   ├── core/                   MASTER_DESIGN · DESIGN_LANGUAGE · ADVOCATED_STANDARDS · GLOSSARY
│   ├── modules/                domain · search · prediction · observability · semantic · memory
│   └── patterns/               temporal-lifecycle-metadata · object-placement ·
│                               physical-storage · validation · access-layer
├── implementation/
│   └── teradata/               PLATFORM_PROFILE + modules/ and patterns/ bindings
├── tooling/
│   ├── validation/             the design linter (+ tests)
│   ├── catalogue/              generates corpus navigation from frontmatter
│   ├── evals/                  validates a product design against the standards
│   └── skill/                  verifies the skill package and its routing
├── examples/                   worked products: fixed inputs for an end-to-end run
└── prompts/                    intake templates for starting a conversation
```

**Start here:** [`design/core/MASTER_DESIGN.md`](design/core/MASTER_DESIGN.md) (the blueprint), [`design/core/DESIGN_LANGUAGE.md`](design/core/DESIGN_LANGUAGE.md) (the notation everything is written in), and [`design/core/ADVOCATED_STANDARDS.md`](design/core/ADVOCATED_STANDARDS.md) (the decisions a design must settle, and the recommended answer for each).

---

## As an agent skill

This repository **is** the skill. There is no build step and nothing to generate: an agent
reads [`SKILL.md`](SKILL.md), routes itself to one of the four files in [`roles/`](roles/),
and opens corpus files from there as the task needs them. Progressive disclosure means the
rest costs nothing until it is read, so the whole standard can ship without loading it.

Install it by placing the repository in your agent's skills directory:

```bash
git clone https://github.com/Teradata/ai-native-data-products.git ~/.claude/skills/ai-native-data-product
```

Downloading the ZIP works too, with one wrinkle: GitHub nests the archive under
`ai-native-data-products-<branch>/`, so rename the extracted directory rather than leaving
the branch name in place.

| Role | Reads | Starter |
|------|-------|---------|
| Designer | `design/` only | [Design starter](prompts/Design_Data_Product_Starter.md) |
| Builder | `implementation/{platform}/` + the design's capability tables | [Build starter](prompts/Build_Data_Product_Starter.md) |
| Reviewer | invariants, conformance rules, and the runnable checks | [Review starter](prompts/Review_Data_Product_Starter.md) |
| Consumer | the deployed product itself, plus the validation contract | [Access starter](prompts/Access_Data_Product_Starter.md) |

The starters are intake templates for a human to fill in and paste. The procedure each agent
follows lives in `roles/`, so it is stated once.

Verify the package before relying on it, particularly after moving or renaming a document:

```bash
python tooling/skill/verify_skill.py
```

Because the corpus is read directly rather than compiled, a skill cannot drift from the
standard: there is only one copy of every rule, and it is the one in `design/`.

---

## Compositions: one library, many patterns

There is no single fixed architecture. Modules declare what they **provide** and **require** (each requirement `[hard]` or `[soft]`); a composition is valid when every hard requirement is met within it, and unmet soft requirements simply disable a feature. An **AI-Native Data Product is the fullest composition**, not the only one.

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
| **[Domain](design/modules/domain.md)** | Authoritative business entities: the source of truth | Root; stands alone |
| **[Semantic](design/modules/semantic.md)** | The discovery map: entity/column/relationship catalogue + orientation | Cross-cutting (soft) |
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

Modules deploy in dependency order: only those the composition includes:

| Phase | Deploy (if present) |
|-------|---------------------|
| 1. Infrastructure | Memory, then Semantic |
| 1.5. Access (initial) | Create roles; grant read on Semantic + Memory |
| 2. Foundation | Domain, then Observability |
| 2.5. Access (extend) | Extend grants to Domain + Observability |
| 3. Enhancement | Search, Prediction |

---

## Tooling

`tooling/validation/design_lint.py` enforces the platform-agnostic boundary on `design/`, the frontmatter schema on every design document, and the decision rules across both hierarchies:

```bash
python tooling/validation/design_lint.py design implementation
```

`tooling/evals/brief_lint.py` is the other half, and the one a **designer** uses: `design_lint` checks that the standards are well formed, `brief_lint` checks that a product design written against them is complete and conformant. Run it on a design brief before handing it to review:

```bash
python tooling/evals/brief_lint.py path/to/design_brief.md
```

`tooling/catalogue/build_catalogue.py` regenerates the navigation tables in the hierarchy READMEs from document frontmatter: run it after adding or renaming a document:

```bash
python tooling/catalogue/build_catalogue.py
```

`tooling/skill/verify_skill.py` checks that the repository is a well-formed agent skill: frontmatter, the `SKILL.md` and role-file line budgets, and that every path the routing names actually exists.

```bash
python tooling/skill/verify_skill.py
```

The whole suite:

```bash
python -m unittest discover -s tooling/validation/tests
```

---

## Key principles

1. **Platform-neutral by construction**: enforced by the design/implementation split and the linter.
2. **Modular and composable**: modules function independently and in any valid combination.
3. **Zero data duplication**: modules reference Domain by identifier and join back; never copy.
4. **Self-describing**: queryable metadata, standard patterns, and multi-hop discovery enable autonomy.
5. **Self-contained products**: discovery and documentation stores live within the product.
6. **Design memory**: every module records its decisions into Memory during design.

---

## Learn More

**Blogs:**
- [Grounding your agents in your world](https://medium.com/teradata-labs/grounding-agents-in-your-world-cbf6e5ed22db)
- [More than a map](https://medium.com/teradata-labs/more-than-a-map-9b30c33e2192)
- [Governed by design](https://medium.com/teradata-labs/governed-by-design-2cf2338417ec)
- [Design time memory](https://medium.com/teradata-labs/design-time-memory-storing-decisions-inside-data-products-da23e7e715df)
- [You don't have to start over](https://medium.com/teradata-labs/you-dont-have-to-start-over-068685c30063)

**Videos:**
- Hands on loyalty data product build: [YouTube](https://www.youtube.com/watch?v=rjsxXmGrso0&t=1s)


---
## License

Copyright © 2025-2026 Teradata Corporation. Licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0). See [LICENSE.md](LICENSE.md) for full terms.

Developed by Teradata's Worldwide Data Architecture Team, Field Technology Organization.
