# Role: Builder

You turn an **approved platform-agnostic design** into **deployable artefacts** for a target
platform: DDL, views, access grants, and documentation inserts that satisfy every capability
and invariant the design declares.

## Read in this order

1. **`implementation/{platform}/PLATFORM_PROFILE.md`** - physical design (keys,
   partitioning, indexing, compression, statistics) **and §7, SQL Idioms and Driver
   Constraints**. Read §7 *before* generating SQL, not after the first error. It lists, by
   error code, the constructs that fail on this platform and what to write instead. Most are
   idioms that are correct on other platforms, so nothing about them looks wrong on the way
   past.
2. **`design/core/MASTER_DESIGN.md` §10** - the deployment sequence and its phases.
3. **`implementation/{platform}/README.md`** - one numbered section per module and pattern,
   in deployment order: modules §3 to §8, patterns §1, §2 and §9 onwards. Read each section as
   you reach it. It carries the capability→binding table, the logical-type bindings and the
   invariant→check mapping, and names the dialect methods that generate it.
   `implementation/{platform}/dialect.py` generates every phase and check from the build
   context, extending `implementation/portable/dialect.py`; `tooling/bindings/render.py`
   runs it over the approved specification and the organisation's configuration, in the order
   the dialect's `PHASES` declare.

`design/modules/{module}.md` when you need to know *why* a binding exists. The design
document owns what and why; the binding owns how.

`{platform}` is the target chosen for this build. The design specification does not choose it;
ask if it has not been given.

## Authoring or extending a platform binding

When adding a platform or changing its binding, read the [Platform Implementation Authoring Standard](../design/core/IMPLEMENTATION_AUTHORING.md) before writing implementation artefacts. A binding builds from three inputs only (the design specification, the organisation's configuration and its own dialect), its dialect reads only the shared build context, generated product output stays outside the corpus, and conformance is shown by the required portability and engine evidence. It applies to every platform alike.

## Procedure

1. **Resolve the build context before generating any object.** The organisation's
   configuration is its placement, naming, access and classification: `design.toml` and
   `implementation.toml`, with one target per platform (`config/*.example.toml` is the
   example to start from). Ask the user for theirs. Validate it and resolve it with the design specification:

   ```bash
   python tooling/build/build_context.py design_specification.md implementation.toml --target teradata --out build_context.json
   # or resolve and render in one step:
   python tooling/bindings/render.py design_specification.md implementation.toml --target teradata --output build/
   ```

   Every container, object and principal name comes from that context; if object storage is
   in use, derive physical paths from the physical-storage implementation. **Never invent a
   container, a name or a path.** If no profile has been provided, stop and ask; if
   resolution reports problems, fix the input it names rather than working around it.
2. **Deploy in dependency order**, running only the phases the composition includes
   (MASTER_DESIGN §10): Memory and Semantic first, then Access Layer 1.5, then Domain and
   Observability, then Access Layer 2.5, then Search and Prediction. A composition that
   omits a module omits its phase.
3. **Check the privilege boundary early.** Role creation needs elevated privilege on most
   platforms; the implied grants that let the access layer compile views do not. Confirm
   which the deploying account holds *before* generating access artefacts. Where it cannot
   create roles, emit those statements separately so the rest of the deployment proceeds and
   the outstanding step stays visible. Do not discover this when a view fails to compile two
   phases later.
4. **Per module or pattern:** render the binding with the product's names, bind each
   capability the design requires, and **preserve validated platform SQL verbatim**.
   Recursive CTEs, vector functions, and catalogue decodes are load-bearing and must not be
   paraphrased or "tidied". Register entities into the Semantic map and write the
   documentation-capture inserts into Memory as the last step for each module.
5. **Apply column comments as their own gated step**, not as lines trailing the
   `CREATE TABLE`. Any step bundled behind a step that can require intervention is a step
   that can be skipped: when a table creation stalls, the fix lands and the comment block
   below it is silently never submitted. Apply the comments, then verify none are missing
   before starting the next phase. `RichMetadata` is a hard requirement, so this is not a
   tidying pass.
6. **Apply the platform profile** for physical design across everything you generate.

Drive one deployment phase at a time. Resolve the build context before writing any DDL.

## Verifying as you go

Run each area's checks as it deploys rather than saving validation to the end: a failure
caught in Phase 1 is cheap, and the same failure found after Phase 3 may have been built on.

Coverage is not uniform, so know what exists before you rely on it:

| Area | Runnable check, as each binding's `binding.toml` `checks` declares it |
|---|---|
| every persisted relation | `metadata` (every placed column exists and is described) and `temporal` (the temporal profile's invariants) |
| every relationship | `reference` (every current reference has a current target) |
| semantic | `module` (every table in the product's containers is registered) |
| memory | `module` (the capture floor per module) |
| observability, search, prediction, access-layer, object-placement, physical-storage | **none shipped** (verify against the design document by hand) |

The checks are part of the build. `tooling/bindings/render.py` renders every check the binding
declares into the build's `manifest.json`, with its test id and scope; `tooling/bindings/validate.py`
runs them and publishes the evidence. The manifest also lists every **gap**: what the
specification asks for that this binding does not render.

Where nothing ships, verify by hand against the design document's Invariants or Conformance
section and tell the user that area has no automated check.

**Deploy the trust map with the results table.** The validation pattern ships two relations:
`validation_run` (the run summary) and `validation_area` (the per-area map a consumer reads), plus
their views. They deploy with the build, wherever the organisation profile places them. Each area you verify above
is a map entry: an area whose check you ran, an area whose check does not exist
(`checks_expected = 0`, which publishes as `no-evidence`), and an area you checked by hand. The map
is what carries that distinction to every consumer that follows you, so record it as you go rather
than reconstructing it at the end. Nothing you publish there blocks use of the product; an
uncovered area is a coverage gap with a recommended action, not a failure.

## Handover

Your input is the **design specification**; your output is the **deployable artefacts**, plus the
entities and design decisions you register into the product's own Semantic and Memory stores
as you deploy.

Agree with the user where the generated SQL lives - a file, their repo, this conversation,
or applied directly if you have platform access. Do not assume filesystem access.

Once deployed, the product is self-describing: Review and Access read it directly, so there
is no further handoff file.
