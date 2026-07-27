# Design

Platform-neutral design hierarchy — **what** an AI-Native Data Product is and
**why**, independent of any target platform. Its counterpart is
[`implementation/`](../implementation), which holds the **how** for each
platform.

This directory is currently **scaffolding only**. Content migrates from
`design-standards/` and `platform-standards/` in a follow-up PR; see issue #44
for the phasing and the old-path → new-path mapping.

---

## Structure

```
design/
├── core/       philosophy, vocabulary, and cross-cutting guidance
├── modules/    one document per module — logical rules only
└── patterns/   the logical/physical bridge — each has a platform binding
```

### `core/`

The master design and the vocabulary it depends on. Documents here describe the
architecture as a whole rather than any one module or pattern.

### `modules/`

One document per module, named for the module: `domain.md`, `semantic.md`,
`search.md`, `prediction.md`, `observability.md`, `memory.md`. These carry the
logical rules — entities, responsibilities, relationships — with no physical
representation.

### `patterns/`

The bridge layer between logical design and physical implementation. The
membership test is: **does this document have, or need, a per-platform binding
document?** If yes, it is a pattern, regardless of which module references it.
`validation.md` names Observability as its module home but lives here, because
the binding pairing is the structural signal and module ownership is a
content-level cross-reference.

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

Every document declares its own classification in its Document Control table
(see the `Type` and `Status` rows). Directory placement is a navigation aid, not
a substitute for that declaration — read the header before treating a rule as
binding.

Where advocated (advisory) guidance ultimately lives is an open question:
issue #16 proposes a separate `guidance/` directory to keep advisory material
out of `core/`, so that placement alone does not imply conformance. That is
resolved as part of the content migration, not here.

---

## Document control

Each document carries a Document Control table recording version, status
(`DRAFT` / `APPROVED` / `DEPRECATED`), last-updated date, owner, scope, type,
and — for patterns — its platform bindings. When a contract changes, the
compatibility and deprecation rules are recorded in that table.

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

## Placeholders

Directories in this scaffold that hold no content yet are kept in git by an
empty `.gitkeep` file. A `.gitkeep` marks a **reserved, unpopulated** location:
there is no document there, and the absence of one carries no meaning. Nothing
should read, render, or compile a `.gitkeep`.
