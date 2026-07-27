# Teradata Implementation

Teradata's conforming implementation of the patterns and modules defined under
[`design/`](../../design). Mirrors the design hierarchy by anchor name.

This directory is currently **scaffolding only**. Content migrates from
`platform-standards/` — and from the DDL currently living inside the generated
skill package — in a follow-up PR; see issue #44.

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
