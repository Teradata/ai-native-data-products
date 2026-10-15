# Release contract for deployed products: design

Status: approved in conversation 2026-10-14; implementation proceeds from this document.

## Purpose

An agent reading a deployed AI-Native Data Product needs to know which version of the standard
the deployment implements and what it can rely on across releases. Today the repository has one
tag (`v1.0.0`), no compatibility or migration notes, and no deployed object that declares the
standard version. `product_version` in the registry is the product's own published contract
version, not the standard's.

This design adds a versioned release bundle and a deployed version declaration. It is
sub-project **A** of two. Sub-project **B** (a separate cycle) closes the four metadata gaps the
bundle will list as known limitations: composite-key grouping, ordered join paths, access-column
mappings, and stable-identity rules. B also replaces the concatenated `join_path` strings with
component rows. It is the first release that exercises the migration notes written here.

Consumers are agents and applications reading a deployed product. Authors of platform bindings
are served by existing documents and are not a goal of A.

## Decisions

| Decision | Choice |
|---|---|
| Sequence | A first (this document), then B as its own spec and plan |
| Version declaration | A table in the Semantic module's registry, one row per implemented component |
| Versioning | One semantic version for the whole standard; a breaking change to any consumer-facing surface bumps the major version |
| Bundle | Generated tree committed in the repository, checked for staleness by a test; attached to the GitHub release |
| Placement | Not a module. Top-level `release/`, generator in `tooling/release/` |

## Boundaries

- The module list stays at six. The bundle has no design document under `design/modules/`, no
  directory under `implementation/{platform}/modules/`, no entry in the renderer's module order, no
  container, placement or grants. No product deploys it.
- The deployed declaration is a table owned by Semantic, alongside `data_product_registry`. Semantic
  gains a table, not a sibling.
- The renderer refuses to write output into reserved directories; `release` joins that list.
- Documents call it "the release bundle", never a module or layer.

## The release bundle

Generated into `release/vX.Y.Z/` from the repository sources:

| File | Content |
|---|---|
| `contract.json` | Standard version; the six module names; every metadata table and column declared in each module's `entities.json` (name, type, nullability, comment); the access-schema objects and their columns; the discovery roles an agent starts from |
| `bindings.json` | Per platform: modules and patterns present, conformance documents, and whether the binding supports the version declaration |
| `examples.json` | Each example, the platforms it covers, its README |
| `checks.json` | The conformance checks a conforming deployment runs. Postgres check ids come from rendering the reference composition; other platforms list their check files |

Authored, at `release/`:

| File | Content |
|---|---|
| `COMPATIBILITY.md` | Versioning policy, which surfaces are stable, what counts as breaking, one row per release, binding adoption status |
| `migrations/vX.Y.Z.md` | One note per release: what changed, breaking or additive, what a deployment must do |

The version comes from a `VERSION` file at the repository root. The tag must equal `v` plus
that value.

### Staleness and completeness test

`tooling/release/tests` regenerates the four JSON files and fails if the committed copies differ.
It also fails if `VERSION` has no `release/vX.Y.Z/` directory, no `migrations/vX.Y.Z.md`, or no
row in `COMPATIBILITY.md`.

## The declaration table

`semantic.standard_declaration`, profile `CURRENT_STATE`, one row per implemented component:

| Column | Meaning |
|---|---|
| `declaration_id` | Key: `product_id:component_kind:component_name` |
| `product_id` | Product making the declaration |
| `component_kind` | `STANDARD`, `MODULE` or `PATTERN` |
| `component_name` | `standard`, a module name, or a pattern name |
| `platform` | Binding implementing the component |
| `standard_version` | Release the component conforms to |

Declaring is an assertion, not evidence. Evidence is the trust map.

The renderer reads `VERSION`, and registration writes one `STANDARD` row, one `MODULE` row per
deployed module, and one `PATTERN` row per pattern the binding applies. Because the table is a
declared entity, the generator creates its table, comments, metadata registration and the
`v_standard_declaration` access view without a hand-written view.

`data_product_manifest` gains a `standard_version` column read from the `STANDARD` row, so the
bootstrap read answers which contract the deployment implements. Both changes are additive: this
is release `1.1.0`.

## Scope of adoption

Only the Postgres binding implements the declaration in this release. Teradata and DuckDB are
recorded as not yet supporting it in `bindings.json`, `COMPATIBILITY.md` and the migration note.
The Teradata and DuckDB bindings cannot be executed here, and the DuckDB binding lives on another
branch.

## Out of scope

- The four metadata gaps (sub-project B).
- Tagging or publishing `v1.1.0`. The tree is prepared; the tag is a separate decision.
- Teradata and DuckDB declaration tables.
- Machine verification that a declaration is true.

## Testing

- Generator: unit tests over a temporary repository layout plus the real repository.
- Staleness and completeness: described above.
- Renderer: the declaration rows appear for the reference and minimal compositions, `VERSION` flows
  into the rows and the manifest column, and the new reserved directory is refused.
- Postgres execution tests are added but need `POSTGRES_TEST_DSN`; they were not run here.

## Implementation steps

1. `VERSION` file at `1.1.0`.
2. `standard_declaration` entity in the Postgres semantic `entities.json`.
3. Renderer: read `VERSION`, apply the pattern list, reserve `release`.
4. Registration inserts declaration rows; manifest view gains `standard_version`.
5. Generator `tooling/release/build_release.py` and tests.
6. Generate `release/v1.1.0/`; write `COMPATIBILITY.md` and `migrations/v1.1.0.md`.
7. Update Postgres semantic README and the design catalogue where the design names the Semantic
   entities.
