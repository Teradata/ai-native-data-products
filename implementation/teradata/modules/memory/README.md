---
title: Teradata Memory Module Implementation
anchor: memory
type: implementation
status: draft
version: 3.0
normative: true
implements: memory
platform: teradata
---

# Teradata: Memory

Binding of [Memory](../../../../design/modules/memory.md). The design remains the source of truth; the binding supplies reusable mechanisms, not a product schema.

## Templates

`01-tables.sql.j2` calls `module_tables('memory')` from the [shared macros](../../patterns/temporal-lifecycle-metadata/README.md). The relations are those the Memory standard defines and the resolver places: the documentation relations (module registry, design decisions, glossary, cookbook, implementation notes, change log), versioned with governed and consumer views, and the runtime relations the context includes, which have no consumer view. Text is `CHARACTER SET UNICODE`, so prose with typographic characters is stored as written.

`02-capture.sql.j2` writes the design-memory records the build context settles in `capture`, one insert per record, by logical attribute name through the `insert` macro:

- `capture.modules` into the module registry, with `product.version`;
- `capture.decisions` into design decisions, each with its settled `DD-{MODULE}-{NNN}` id, version 1 and status `ACCEPTED`;
- `capture.glossary`, `capture.notes` and `capture.change_log` into their relations;
- `capture.cookbook` into the cookbook, with each recipe's query rendered here in the Teradata dialect from its `kind`: a metric's measure and filter over its dataset's consumer view (`metrics`); a `CALL` of the similarity procedure with a `?` parameter, where the binding emits one (`embeddings`); a join of a relationship's source and target consumer views (`relationships`); a catalogue lookup of entity metadata for the named modules; otherwise the named relation's consumer view. A stored query never holds a `:name` parameter, which the MCP driver would try to bind (PLATFORM_PROFILE §7).

A record the context does not carry is not written. What capture could not settle is listed in `capture.gaps` and reported in the manifest.

`validation.sql.j2` is the `module memory` check. Every row it returns is a registered module below the capture floor: three design decisions, three glossary terms and one cookbook recipe.

## Access

The [access-layer template](../../patterns/access-layer/README.md) grants the agent tier `SELECT`, `INSERT` and `UPDATE` on each runtime relation. Teradata has no row-level security in SQL, so the binding declares `Runtime scope: unsupported`: runtime records are not restricted to the requesting identity's scope, and every build with runtime relations reports it as a gap.

## Capability bindings

| Capability | Binding |
|---|---|
| `DocumentationCapture` | Versioned documentation relations; `02-capture.sql.j2` writes the settled records; `validation.sql.j2` reports modules below the floor. |
| `AgentContinuity` | Runtime relations with required scope columns and no consumer view. Scope enforcement is a reported gap. |

Templates read only the build context: see [tooling/build](../../../../tooling/build/README.md) and the [Platform Implementation Authoring Standard](../../../../design/core/IMPLEMENTATION_AUTHORING.md) §3 and §6. Phases, checks, types and expression fragments are declared in [PLATFORM_PROFILE.md](../../PLATFORM_PROFILE.md#binding-declarations); coverage and gaps are in [CONFORMANCE.md](../../CONFORMANCE.md). Rendering uses StrictUndefined.

## Invariants and checks

| Invariant | Evidence or outstanding check |
|---|---|
| `INV-MEMORY-001,002,004` | Standard-owned structures separate process and design context; producer payload review remains necessary. |
| `INV-MEMORY-003` | Required scope columns. Enforcement at the access surface is not rendered (`Runtime scope: unsupported`), and reported. |
| `INV-MEMORY-005` | Shared versioned temporal macros and the `entity temporal` check. |
| `INV-MEMORY-006` | `module memory` check of the capture floor; the reference specifications meet it on the engine. |

Physical types come from the `Types:` block of the [binding declarations](../../PLATFORM_PROFILE.md#binding-declarations). Temporal and lifecycle columns come only from the shared pattern. Semantic registration and Memory capture are soft dependencies and render nothing when those modules are absent.
