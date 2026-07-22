# AI-Native Data Product — Skill Conversion Prompt

## Converting the standards into four role skills

---

## Purpose

This prompt converts the AI-Native Data Product standards into **four role-scoped agent skills** —
one per stage of the designer → builder → reviewer pipeline, plus a consumer skill:

| Skill | Role | Question it answers |
|-------|------|---------------------|
| `design` | Designer | *How do I design a data product (platform-agnostic)?* |
| `build` | Builder | *How do I deploy that design on a specific platform?* |
| `review` | Reviewer | *How far can this design/build be trusted, and where are the gaps?* |
| `access` | Consumer | *How do I discover and query a deployed product?* |

Each role receives **purpose-built context** — a designer never loads platform DDL; a consumer never
loads build templates. This is the whole point of the split.

**The repository is the source of truth.** `design/` is platform-agnostic; `implementation/{platform}/`
binds it; `tooling/validation/` enforces the boundary. Skills are a compressed, agent-optimised
*rendering* of these — never independent of them. When the repo changes, regenerate the skills. On
any conflict, the repo wins.

Skills are generated artefacts and are **gitignored** (`/skills/`). Do not commit them.

---

## Source → skill mapping

Read the repository before writing anything. Each skill draws from a specific slice:

| Skill | Reads from |
|-------|-----------|
| `design` | `design/core/` (all), `design/modules/*.md`, `design/patterns/*.md` |
| `build` | `implementation/{platform}/` (all), plus each design doc's §"Implementation" and capability tables for the design→binding mapping |
| `review` | Every `INV-*` invariant and every conformance-rule table (`TLM-*`, `VAL-*`, object-placement/physical-storage conformance checklists), `design/patterns/validation.md`, `tooling/validation/design_lint.py`, and each implementation's `validation.sql` |
| `access` | `design/modules/semantic.md` (§4 orientation, §5–6 discovery), `design/patterns/validation.md` (§8 the stop/go gate), `implementation/{platform}/modules/semantic/06-orientation.md` and `04-path-discovery.sql` |

`{platform}` defaults to `teradata` (the current reference). To target another platform, point `build`
and `access` at that platform's `implementation/` tree once it exists.

---

## Output structure

Write four skill directories under `skills/` (gitignored). Each is a progressive-disclosure package:
a lean `SKILL.md` read on every invocation, plus on-demand files.

```
skills/
├── design/
│   ├── SKILL.md               ← framework, design language, composition method, routing
│   ├── modules/{module}.md    ← per-module logical model, capabilities, invariants (6 files)
│   └── patterns/{pattern}.md  ← per-pattern contract (5 files)
├── build/
│   ├── SKILL.md               ← the design/implementation split, deployment order, object-placement protocol
│   ├── platform-profile.md    ← physical-design guidance for the target platform
│   ├── modules/{module}.md    ← per-module DDL templates + capability bindings (6 files)
│   └── patterns/{pattern}.md  ← per-pattern concrete binding (5 files)
├── review/
│   ├── SKILL.md               ← how to build the product's trust map; the invariant/conformance catalogue index; the linter
│   └── checks/{module|pattern}.md ← the INV-*/conformance rules and validation queries per area, with severities
└── access/
    ├── SKILL.md               ← product-first discovery order; the pre-use trust gate
    └── discovery.md           ← orientation manifest, module/entity/relationship discovery, multi-hop paths
```

Every `SKILL.md` carries YAML frontmatter: `name` (`ai-native-dp-{role}`) and a `description` that
states the role and when to load it. Keep each `SKILL.md` lean (target ≤ 150 lines) — it is read on
every invocation.

---

## Per-skill instructions

### 1. `design` — the designer skill

`SKILL.md` (from `design/core/`): the composition method (modules provide/require capabilities;
`[hard]`/`[soft]`; a composition is valid iff every hard requirement is met — Design Language §6.2);
the named compositions (Master §4); the logical-type vocabulary and entity notation (Design Language
§4–5); the capability catalogue (§6.1); the invariant convention (§7); and the deployment order
(Master §10). Routing: "read `SKILL.md`, then `modules/{module}.md` for the module you are designing
and `patterns/{pattern}.md` for each pattern it applies."

`modules/{module}.md` (from `design/modules/`): the logical entity model in the entity notation, the
Provides/Requires capabilities with strengths, applied patterns, the invariants to satisfy, and
designer responsibilities. **Platform-agnostic — no platform types, no DDL.** This is the design
document, compressed.

`patterns/{pattern}.md` (from `design/patterns/`): the contract the pattern imposes and the capabilities
it underpins.

**Output of a designer using this skill:** a platform-agnostic design — chosen composition, entities in
logical types, capabilities required, invariants to satisfy — ready to hand to a builder.

### 2. `build` — the builder skill

`SKILL.md`: the design/implementation split; that a design is realised by binding each capability and
generating the concrete artefacts; the deployment order for the chosen composition (Master §10); and
the **object-placement protocol** — *before generating any object, locate the conforming
object-placement implementation and derive the container; if object storage is in use, also locate the
physical-storage implementation; never invent a container or path.*

`platform-profile.md` (from `implementation/{platform}/PLATFORM_PROFILE.md`): physical-design guidance
(keys, partitioning, indexing, compression, statistics).

`modules/{module}.md` (from `implementation/{platform}/modules/`): the concrete DDL/query templates, the
capability→binding table (so the builder knows which design capability each artefact satisfies), and
the invariant→check mapping. **Preserve validated platform SQL exactly** — recursive CTEs, vector
functions, catalogue decodes must not be paraphrased.

`patterns/{pattern}.md` (from `implementation/{platform}/patterns/`): the concrete pattern binding
(temporal DDL/DML, access-layer DCL, validation results table, etc.).

**Output of a builder using this skill:** deployable, ordered artefacts for the target platform that
satisfy the design's capabilities and invariants.

### 3. `review` — the reviewer skill

The reviewer's job is to build a **trust map** of the data product — not to open or close a gate. The
map gives the agent visibility over *how much of the product is validated, how strongly, and where the
gaps are*, so the agent can carry it as knowledge, inform the user, and identify where extra data,
analysis, or discovery is needed.

`SKILL.md`: how to build the trust map. For each module and pattern present, gather the evidence — walk
its invariants and conformance rules, run the design linter against `design/`, and read any published
validation results — then record, **per area** (module / entity / pattern), its **coverage** (which
checks exist and ran), **status** (pass / fail / not-yet-validated / no-evidence), **confidence**
(strong / partial / weak / unknown), and **open gaps**. Index the `checks/` files.

`checks/{module|pattern}.md`: the full `INV-*` list for that area (from the design doc's Invariants
section) and its conformance-rule table where one exists (`TLM-*` for temporal, `VAL-*` for validation,
the object-placement/physical-storage conformance checklists), each paired with its runnable check (the
implementation's `validation.sql`, or the `design_lint.py` rule) and its **severity** — so a failure
lowers that area's confidence on the map rather than flipping a single global switch.

**Output of a reviewer using this skill:** a **trust map** — per module / entity / pattern: what is
validated, how strongly, what is uncovered, and what is stale or missing — plus concrete
recommendations on where to focus further data, analysis, or discovery. Severe failures are surfaced
prominently and their impact explained, but the map *informs* the agent and the user; it does not
silently block use. Where the validation pattern publishes a formal result it is **one input** to the
map, not the whole story. (The gate-to-map relationship is still evolving — further changes to the
validation pattern are planned to support the map view; reflect the map framing here regardless.)

### 4. `access` — the consumer skill

`SKILL.md`: **product-first discovery** — orient to the product before touching modules or data
(Semantic §4); the discovery order (product → module → entity → relationship); and the **pre-use trust
gate** — read the gate-authoritative validation result before analytical use; stop on `UNTRUSTED`, stale,
or missing evidence (validation §8, §10).

`discovery.md`: the orientation manifest and MCP resource/tool shapes; the module/entity/relationship
discovery sequence; multi-hop path discovery; primary-object entrypoints (use the stored
`container.object` verbatim, never derive names).

**Output of a consumer using this skill:** correct, gated queries against a deployed product, discovered
autonomously.

---

## Compression guidance

Leave each agent maximum working memory:

- **Replace prose with decision tables** (e.g. wide-vs-tall storage → a two-row table).
- **Keep the parameterised template, drop the worked example** — the template is the example. Use the
  repo's placeholders (`{ProductName}`, `{entity}`, `{{ product }}`).
- **State cross-cutting conventions once** in `SKILL.md`; do not repeat them in every file.
- **Preserve exactly, never compress:** validated platform SQL, `COMMENT ON` metadata text, invariant
  wording and ids, conformance-rule ids and their blocking markers.

Do **not** let platform SQL leak into the `design` skill — it must stay platform-agnostic, exactly as
`design/` is. (You can sanity-check by running `tooling/validation/design_lint.py` against any design
material you lift.)

---

## Verify before finishing

For every skill:

- [ ] `SKILL.md` ≤ 150 lines, correct frontmatter, clear routing, no content that belongs in an on-demand file.
- [ ] On-demand files present for every module/pattern in scope; none repeats `SKILL.md`.
- [ ] `design` skill contains no platform types or DDL (lint-clean).
- [ ] `build` skill preserves validated platform SQL verbatim and carries the capability→binding and invariant→check mappings.
- [ ] `review` skill builds a **trust map**: every `INV-*` and conformance rule with its runnable check and severity, rolled up per area into coverage / status / confidence / gaps, plus recommendations — not a binary stop/go gate.
- [ ] `access` skill leads with product-first discovery and the pre-use trust gate.
- [ ] Every claim traces to a repo source; on conflict, the repo wins.

Optionally package each `skills/{role}/` as a distributable `.skill` archive; the directories under
`skills/` remain the working output and stay gitignored.

---

## Report

Summarise: the four skills and their file/line counts; the typical context load per role (SKILL.md + the
files that role opens for one module); any repo inconsistencies found (report, don't silently fix — the
repo is the source of truth); and any repo updates needed to keep the skills faithful.

---

## Updating after the repo changes

1. Identify which skill(s) and file(s) an edit affects (a `design/` change usually touches `design` +
   `review`; an `implementation/` change touches `build`; a new invariant touches `review`).
2. Update only the affected files with targeted edits; do not rewrite whole skills.
3. Re-run the verification checklist. Skill names must stay stable across versions.
