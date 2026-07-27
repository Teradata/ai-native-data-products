# Teradata Implementation

Teradata's conforming implementation of the patterns and modules defined under
[`design/`](../../design). Mirrors the design hierarchy by anchor name.

Physical-design conventions that apply across every binding here — primary
index selection, partitioning, compression, statistics — live in
[`PLATFORM_PROFILE.md`](PLATFORM_PROFILE.md).

---

## Structure

```
implementation/teradata/
├── patterns/   one directory per design/patterns/ anchor
└── modules/    one directory per design/modules/ anchor
```

Each pattern or module gets **its own directory** (e.g. `modules/domain/`)
rather than a single top-level file, because an implementation is usually more
than one artifact — a binding document plus one or more templates.

Adding a platform means creating a same-shaped sibling of this directory
(`implementation/postgres/`, say), not inventing a new layout.

## Catalogue

Generated from document frontmatter by
[`tooling/catalogue`](../../tooling/catalogue) — do not edit by hand.

<!-- catalogue:start -->

### Platform profile

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [Teradata Platform Profile](PLATFORM_PROFILE.md) *(advisory)* | `teradata` | standard | — | — | — |

### Bindings

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [Teradata — Access Layer Pattern Implementation](patterns/access-layer/README.md) | `access-layer` | standard | — | — | — |
| [Teradata — Domain Module Implementation](modules/domain/README.md) | `domain` | standard | — | — | — |
| [Teradata — Memory Module Implementation](modules/memory/README.md) | `memory` | standard | — | — | — |
| [Teradata — Object Placement Pattern Implementation](patterns/object-placement/README.md) | `object-placement` | standard | — | — | — |
| [Teradata — Observability Module Implementation](modules/observability/README.md) | `observability` | standard | — | — | — |
| [Teradata — Physical Storage Pattern Implementation](patterns/physical-storage/README.md) | `physical-storage` | standard | — | — | — |
| [Teradata — Prediction Module Implementation](modules/prediction/README.md) | `prediction` | standard | — | — | — |
| [Teradata — Search Module Implementation](modules/search/README.md) | `search` | standard | — | — | — |
| [Teradata — Semantic Module Implementation](modules/semantic/README.md) | `semantic` | standard | — | — | — |
| [Teradata — Temporal Lifecycle Metadata Pattern Implementation](patterns/temporal-lifecycle-metadata/README.md) | `temporal-lifecycle-metadata` | standard | — | — | — |
| [Teradata — Validation Pattern Implementation](patterns/validation/README.md) | `validation` | standard | — | — | — |

<!-- catalogue:end -->

---

## What goes in a directory

Two kinds of artifact, distinguished by extension:

| Artifact | Extension | Contents |
|----------|-----------|----------|
| **Binding document** | `.md` | Prose: how this platform satisfies the design contract — physical model, type bindings, failure modes, deviations. Human-readable, never executed. |
| **Template** | `.sql.j2` | Jinja-templated DDL/DCL rendered at build time. Mostly-static SQL with placeholders for the part that varies per product. |

Most anchors need a binding document. Only some need a template. An anchor whose
platform behaviour is fully described in prose does not need a `.sql.j2` file,
and one should not be created speculatively.

## Naming

- The **binding document** is named for its anchor, matching the design-side
  basename: `patterns/validation/validation.md` binds
  `design/patterns/validation.md`.
- **Templates** are named for what they emit, not for the directory they sit in.
  A module directory may hold several — `domain/tables.sql.j2`,
  `domain/views.sql.j2` — and a name that merely repeats the anchor
  (`domain/domain.sql.j2`) says nothing about what rendering it produces.
- Anchor names always match `design/` exactly. That symmetry is what lets an
  agent holding a module name compute the implementation path directly.

---

## Placeholders

Directories reserved but not yet populated are held in git by an empty
`.gitkeep` file. There are deliberately **no placeholder templates**: an empty
or comment-only `.sql.j2` is indistinguishable from a real one to a renderer,
and would silently produce empty SQL. A `.sql.j2` file exists only once it has
an implementation.
