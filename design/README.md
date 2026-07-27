# Design

Platform-neutral design hierarchy — **what** an AI-Native Data Product is and
**why**, independent of any target platform. Its counterpart is
[`implementation/`](../implementation), which holds the **how** for each
platform.

Everything here is written in the notation defined by
[`core/DESIGN_LANGUAGE.md`](core/DESIGN_LANGUAGE.md), and the
[design linter](../tooling/validation) enforces it — a design document that
leaks platform SQL fails the build.

---

## Structure

```
design/
├── core/       the notation, the vocabulary, the architecture, the decisions
├── modules/    one document per module — logical rules only
└── patterns/   the logical/physical bridge — each has a platform binding
```

**`core/`** describes the architecture as a whole rather than any one module or
pattern: the notation everything is written in, the shared vocabulary, the master
design, and the decision catalogue.

**`modules/`** holds one document per module, carrying logical rules — entities,
responsibilities, relationships — with no physical representation.

**`patterns/`** is the bridge layer between logical design and physical
implementation. The membership test is: **does this document have, or need, a
per-platform binding document?** If yes, it is a pattern, regardless of which
module references it. The validation pattern names Observability as its module
home but lives here, because the binding pairing is the structural signal and
module ownership is a content-level cross-reference.

## Catalogue

Generated from document frontmatter by
[`tooling/catalogue`](../tooling/catalogue) — do not edit by hand.

<!-- catalogue:start -->

### Core

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [Advocated Standards — Decision Catalogue](core/ADVOCATED_STANDARDS.md) | `advocated-standards` | draft | — | — | — |
| [Design Language](core/DESIGN_LANGUAGE.md) | `design-language` | standard | — | — | — |
| [Glossary](core/GLOSSARY.md) *(advisory)* | `glossary` | standard | — | — | — |
| [Master Design](core/MASTER_DESIGN.md) | `master-design` | standard | — | — | — |

### Patterns

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [Access Layer Pattern](patterns/access-layer.md) | `access-layer` | standard | `AccessView` | `DocumentationCapture` | — |
| [Object Placement Pattern](patterns/object-placement.md) | `object-placement` | standard | — | — | — |
| [Physical Storage Pattern](patterns/physical-storage.md) | `physical-storage` | standard | — | — | — |
| [Temporal Lifecycle Metadata Pattern](patterns/temporal-lifecycle-metadata.md) | `temporal-lifecycle-metadata` | standard | `CurrentStateFilter`, `PointInTimeReconstruction`, `SoftDelete` | `RichMetadata`, `SemanticRegistration` | — |
| [Validation Pattern](patterns/validation.md) | `validation` | standard | `QualityScore` | `RichMetadata` | — |

### Modules

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [Domain Module](modules/domain.md) | `domain` | standard | `AccessView`, `CurrentStateFilter`, `EntityJoinBack`, `NaturalKeyLookup`, `PointInTimeReconstruction`, `SoftDelete` | `DocumentationCapture`, `MetadataCoverageCheck`, `RichMetadata`, `SemanticRegistration`, `SurrogateKeyAllocation` | `DEC-TEMPORAL-PATTERN`, `DEC-COLUMN-STRATEGY`, `DEC-SURROGATE-ALLOCATION`, `DEC-DELETE-STRATEGY`, `DEC-TIMESTAMP-ZONE` |
| [Memory Module](modules/memory.md) | `memory` | standard | `AgentContinuity`, `DocumentationCapture` | `DocumentationCapture`, `EntityJoinBack`, `NearestNeighbors`, `QualityScore`, `RichMetadata`, `SemanticRegistration` | `DEC-TEMPORAL-PATTERN`, `DEC-DELETE-STRATEGY`, `DEC-TIMESTAMP-ZONE` |
| [Observability Module](modules/observability.md) | `observability` | standard | `ChangeEventCapture`, `LineageCapture`, `QualityScore` | `DocumentationCapture`, `EntityJoinBack`, `RichMetadata`, `SemanticRegistration` | `DEC-QUALITY-STORAGE`, `DEC-AUDIT-RETENTION`, `DEC-TIMESTAMP-ZONE` |
| [Prediction Module](modules/prediction.md) | `prediction` | standard | `AccessView`, `CurrentStateFilter`, `PointInTimeReconstruction` | `AccessView`, `CurrentStateFilter`, `DocumentationCapture`, `EntityJoinBack`, `PointInTimeReconstruction`, `RichMetadata`, `SemanticRegistration` | `DEC-TEMPORAL-PATTERN`, `DEC-DELETE-STRATEGY`, `DEC-TIMESTAMP-ZONE` |
| [Search Module](modules/search.md) | `search` | standard | `ApproxIndex`, `Embed`, `NearestNeighbors` | `AccessView`, `CurrentStateFilter`, `DocumentationCapture`, `EntityJoinBack`, `RichMetadata`, `SemanticRegistration` | `DEC-TEMPORAL-PATTERN`, `DEC-DELETE-STRATEGY`, `DEC-TIMESTAMP-ZONE` |
| [Semantic Module](modules/semantic.md) | `semantic` | standard | `SemanticRegistration` | `DocumentationCapture`, `EntityJoinBack`, `RichMetadata` | `DEC-TIMESTAMP-ZONE` |

<!-- catalogue:end -->

---

## The platform-neutrality test

Nothing under `design/` may contain a SQL keyword, a vendor data type, a
catalogue query, indexing syntax, or deployment-tool behaviour. That is the
enforceable test for whether a document belongs here or under
`implementation/{platform}/`.

---

## Anchor mapping

`design/` and `implementation/{platform}/` share **anchor names** — the
basename of a module or pattern. Given an anchor, either path is computable
without a lookup table:

| Design | Teradata implementation |
|--------|-------------------------|
| `design/modules/{anchor}.md` | `implementation/teradata/modules/{anchor}/` |
| `design/patterns/{anchor}.md` | `implementation/teradata/patterns/{anchor}/` |

The implementation side is a **directory** per anchor rather than a single file,
because one binding is often more than one artifact — a design document plus one
or more templates. See
[`implementation/teradata/README.md`](../implementation/teradata/README.md) for
what those directories contain.

`design/core/` has no implementation counterpart: it is architecture-level
material with nothing to bind.

---

## Normative versus advisory

Not everything under `design/` carries the same weight:

- **Normative** — required for conformance. A product that violates a normative
  rule is not conformant.
- **Advisory** — recommended practice. Useful, but not a conformance
  requirement.

Every document declares its own classification in frontmatter, as `normative:
true` or `normative: false`; the catalogue above marks advisory documents
explicitly. Directory placement is a navigation aid, not a substitute for that
declaration — read the frontmatter before treating a rule as binding.

**Advocated practice is not a third category.** Recommendations that were once
advisory prose are expressed as **decisions** (see the [Design Language](core/DESIGN_LANGUAGE.md)): each
names its options, marks one advocated, and states when the others are sound.
What is normative is that an applicable decision must be *declared*; which option
a product picks is its own. This is why there is no `guidance/` directory —
advisory material that sits outside the design workflow cannot be applied
consistently or checked at all, which is the problem the decision construct
solves.

---

## Document identity

Each document opens with a short frontmatter block declaring `title`, `anchor`,
`type`, `status` (`draft` / `standard` / `deprecated`), `version`, and
`normative` — identity only.

Everything else lives in the body: what a document provides and requires, and
the decisions it asks a designer to settle. Frontmatter is an index card, not an
abstract — a capability graph stated in both a header and a body table is two
things to maintain and two things to disagree. The catalogue above reads the
body tables, so the graph is machine-readable in one place without any document
restating it.

---

## Relationship to extensions and profiles

Issues #10 and #16 define a governance model of core standards, additive
extensions, and composable profiles. That model maps onto this structure as
follows:

- **Core standards** → `design/core/`, `design/modules/`, `design/patterns/`.
- **Platform extensions** → `implementation/{platform}/`. Extensions are
  additive: they may specialise a design document, but must not redefine its
  semantics or weaken its invariants.
- **Non-platform extensions** (deployment, interoperability, security, domain
  overlays) have no home in this scaffold yet. They are not platform bindings,
  so `implementation/` is the wrong place for them.
- **Profiles** — approved combinations of a core set plus selected extensions —
  likewise have no home yet.

Reconciling this hierarchy with the extension and profile taxonomy of #16 is
open work, tracked against #44 rather than settled here.

---

## Empty directories

A directory reserved before it has content is held in git by an empty `.gitkeep`
file. It marks the location and nothing more — no document is there, and the
absence of one carries no meaning. Nothing should read, render, or compile a
`.gitkeep`.
