---
title: DuckDB Memory Implementation
anchor: memory
type: implementation
status: draft
version: 2.0
normative: true
implements: memory
platform: duckdb
---

# DuckDB: Memory

Binding of [Memory](../../../../design/modules/memory.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`01-tables.sql.j2` calls `module_tables('memory')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). The relations are those the Memory standard defines and the resolver places: the documentation relations (module registry, design decisions, glossary, cookbook, implementation notes, change log), versioned with consumer views and point-in-time table macros, and the runtime relations the context includes, which have no consumer view. Process context uses the DuckDB `JSON` type.

`02-capture.sql.j2` writes the design-memory records the build context settles in `capture`, one insert per record, by logical attribute name through the `insert` macro:

- `capture.modules` into the module registry, with `product.version`;
- `capture.decisions` into design decisions, each with its settled `DD-{MODULE}-{NNN}` id, version 1 and status `ACCEPTED`;
- `capture.glossary`, `capture.notes` and `capture.change_log` into their relations;
- `capture.cookbook` into the cookbook, with each recipe's query rendered here in the DuckDB dialect from its `kind`: a metric's measure and filter over its dataset's consumer view (`metrics`); a call to a similarity macro with `$1` and a limit of 10, joined to the entity's consumer view where the recipe asks (`embeddings`); a join of a relationship's source and target consumer views (`relationships`); a catalogue lookup of entity metadata for the named modules; otherwise the named relation's consumer view.

A record the context does not carry is not written. What capture could not settle is listed in `capture.gaps` and reported in the manifest.

`validation.sql.j2` is the `module memory` check. Every row it returns is a registered module below the capture floor: three design decisions, three glossary terms and one cookbook recipe.

## Access

DuckDB has no row-level security or principals. Runtime rows carry the required `scope_level` and `scope_identifier` columns, but nothing in the engine filters by caller, and read-only mode does not hide them. The organisation profile declares how each access tier is enforced outside the database. Privacy needs an authenticated serving application that derives scope from identity, or separate protected storage. Direct access to the database file exposes runtime data.

## Capability bindings

| Capability | Binding |
|---|---|
| `DocumentationCapture` | Versioned documentation relations; `02-capture.sql.j2` writes the settled records; `validation.sql.j2` reports modules below the floor. |
| `AgentContinuity` | Runtime relations with required scope columns and no consumer view. Scope enforcement is outside DuckDB. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-MEMORY-001,002,004` | Standard-owned structures separate process and design context; producer payload review remains necessary. |
| `INV-MEMORY-003` | Required scope columns and no consumer view. Runtime privacy enforcement is a declared gap. |
| `INV-MEMORY-005` | Shared versioned temporal macros and the `entity temporal` check. |
| `INV-MEMORY-006` | `module memory` check of the capture floor; the reference specifications meet it. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
