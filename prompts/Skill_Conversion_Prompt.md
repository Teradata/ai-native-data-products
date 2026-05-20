# AI-Native Data Product — Unified Skill Conversion Prompt
## Converting Design Standard Documents into a Single Agent Skill

---

## Purpose

This prompt converts the full set of AI-Native Data Product design standard
documents into a single unified agent skill with progressive disclosure.

The **design standard documents are the master source of truth**.
The skill is a compressed, agent-optimised rendering of those documents —
structured for efficient sub-agent consumption, not independent of them.

When design documents change, the skill must be updated to match.
When there is a conflict between skill content and design document content,
the design document wins.

---

## Skill Architecture

The unified skill uses a two-tier progressive disclosure structure:

```
ai-native-data-product.skill (zip)
├── SKILL.md                    ← always read by orchestrator and every sub-agent
│                                  core principles, architecture, naming conventions,
│                                  deployment order, documentation capture protocol,
│                                  sub-agent routing instructions
└── modules/
      ├── domain.md             ← read when designing Domain module
      ├── semantic.md           ← read when designing Semantic module
      ├── search.md             ← read when designing Search module
      ├── prediction.md         ← read when designing Prediction module
      ├── observability.md      ← read when designing Observability module
      ├── memory.md             ← read when designing Memory module
      │                            (includes Documentation Sub-Module)
      └── access-layer.md       ← read when generating the Access Layer DCL
                                   three-role model, two-phase deployment,
                                   DD-ACCESS-001 documentation record
```

**SKILL.md** is read by every agent — orchestrator and sub-agents alike.
It must be lean enough that it does not consume meaningful context on its own.

**Module files** are read on demand — each sub-agent reads SKILL.md plus
only the module file relevant to its current design task. Module files
assume SKILL.md has been read and do not repeat its content.

---

## How to Use This Prompt

**To generate the full unified skill from scratch:**
1. Start a new AI agent/chat conversation
2. Attach all design standard documents:
   - `AI_Native_Data_Product_Master_Design.md`
   - `Domain_Module_Design_Standard.md`
   - `Semantic_Module_Design_Standard.md`
   - `Search_Module_Design_Standard.md`
   - `Prediction_Module_Design_Standard.md`
   - `Observability_Module_Design_Standard.md`
   - `Memory_Module_Design_Standard.md`
   - `Access_Layer_Design_Standard.md`
3. Attach platform standard interface specifications:
   - `platform-standards/Object_Placement_Standard_Spec.md`
   - `platform-standards/Physical_Storage_Standard_Spec.md`
4. Attach `Advocated_Data_Management_Standards.md`
5. Paste this prompt

**To update the skill after design documents change:**
1. Attach the updated design document(s)
2. Attach the current `.skill` file
3. Paste this prompt with the instruction: "Update the skill to reflect
   changes in [document name]"

---

## Conversion Prompt

You are converting the AI-Native Data Product design standard documents
into a single unified agent skill. The skill creator tool is available
in your skills library — use it to package the final output.

The design standard documents are the **master source of truth**.
The skill is a compressed, structured rendering of that knowledge.
Every design decision and DDL pattern in the skill must be traceable
to a source document.

---

### Step 1 — Read and Analyse

Read all attached documents before writing anything.

From the Master Design Standard, extract:
- The six-module architecture and how modules relate
- Physical naming conventions (`{ProductName}_{Module}` pattern)
- Module deployment order (phases)
- The "design memory" concept — documentation tables in Memory database

From each module design standard, extract:
- **Module purpose** — one sentence
- **Core principle** — the never-violate rule
- **Tables to design** — each table with its purpose
- **Design decisions** — choices the designer must make (storage pattern,
  temporal strategy, indexing, etc.)
- **Integration points** — how this module connects to others
- **Standard views** — required vs optional
- **Agent discovery patterns** — how agents find and query this module
- **Documentation capture requirements** — minimum records for Memory
  documentation tables (Memory Module Design Standard, Section 8)

Then identify any **consistency issues** before writing a single line of output.

Check every boolean-style column across all design standards against:
- Boolean flags must use `BYTEINT NOT NULL DEFAULT 1/0` — never `CHAR(1)`
- Boolean columns must use the `is_` prefix
- Filter values must be `= 1` or `= 0` — never `= 'Y'` or `= 'N'`
- Temporal tables use non-unique `PRIMARY INDEX` — never `UNIQUE PRIMARY INDEX`

**Stop and report any inconsistencies before proceeding.**
List the table name, column name, current definition, and corrected definition.
Wait for confirmation before continuing.

---

### Step 2 — Write SKILL.md (Core)

SKILL.md is read by every agent. It must be lean, complete, and contain
no module-specific content. Target: 100–150 lines. Hard limit: 175 lines.

**SKILL.md must contain:**

1. **YAML frontmatter** — `name: ai-native-data-product` and a description
   covering the full scope: orchestrating multi-module data product design,
   directing sub-agents to module files, designing any individual module

2. **Architecture overview** — compact table showing all six modules,
   their purpose, and their database naming pattern

3. **Deployment order** — which modules to design in which phase,
   including the note that Memory module documentation tables are
   created as part of Memory DDL (no separate bootstrap step)

4. **Physical naming convention** — `{ProductName}_{Module}` pattern
   with a concrete example (e.g. Customer360_Domain, Customer360_Memory)

5. **Universal conventions** — applied in every module, stated once here:
   - Boolean columns: `BYTEINT NOT NULL DEFAULT 1/0`, `is_` prefix, filter `= 1/0`
   - Surrogate keys in **Domain module** `_H` tables (FK-target entities): `BIGINT NOT NULL` — best practice is to manage surrogate allocation separately from the history table so that the same surrogate is used consistently across all SCD versions. Apply the organisation's existing key allocation standard, or the Keymap pattern recommended in Advocated Data Management Standards Section 4. Reference/lookup tables and detail entities not FK-referenced may allocate surrogates directly (see Advocated Standards Section 4.4 for the decision rule).
   - Surrogate keys in **all other modules** (Semantic, Memory, Observability, Search, Prediction): `BIGINT GENERATED ALWAYS AS IDENTITY` or `INTEGER GENERATED ALWAYS AS IDENTITY` — these are internal management tables, not SCD history tables, so IDENTITY is correct.
   - Natural/business keys: `{entity}_key VARCHAR` or appropriate type
   - Timestamps: `TIMESTAMP(6) WITH TIME ZONE`
   - Temporal end date: `DATE '9999-12-31'` (open / no end)
   - Table suffixes: `_H` history, `_R` reference, `_Current` view, `_Enriched` view
   - `COMMENT ON TABLE` and `COMMENT ON COLUMN` required on all objects

6. **Documentation capture protocol** — cross-cutting, stated here once,
   not repeated in module files:
   - All documentation tables live in `{ProductName}_Memory`
   - Every module must generate: 1× Module_Registry INSERT, min. 3×
     Design_Decision INSERTs, 1× Change_Log INSERT, min. 3×
     Business_Glossary INSERTs, min. 1× Query_Cookbook INSERT
   - Decision ID format: `DD-{MODULE}-{NNN}` (e.g. DD-DOMAIN-001)
   - Output file placement: last numbered file in each module directory
     (e.g. `01-domain/05-documentation.sql`)
   - Temporal field defaults: `valid_from = CURRENT_DATE`,
     `valid_to = DATE '9999-12-31'`, `is_current = 1`, `is_active = 1`

7. **Sub-agent routing instructions** — explicit directive:
   "Read SKILL.md first. Then read `modules/{module}.md` for the module
   you are designing. Do not read other module files unless explicitly
   designing that module."

8. **Module file index** — one-line description of each module file
   and when to load it

**SKILL.md must NOT contain:**
- DDL templates
- Query syntax
- INSERT/UPDATE patterns
- Module-specific design decisions
- Checklists

---

### Step 3 — Write Module Files

Write one file per module under `modules/`. Each file is self-contained
for its module design task. Each file assumes SKILL.md has been read —
do not repeat naming conventions, boolean standards, or documentation
capture protocol.

**Target per module file: 300–400 lines. Hard limit: 500 lines.**

Each module file must contain, in this order:

1. **Module header** — purpose (one sentence), core principle (never-violate
   rule), and the physical database name pattern for this module

2. **Design decisions table** — the choices the designer must make before
   writing DDL. Format as a decision table:
   ```
   | Decision | Options | Choose when |
   ```
   Not prose. Compact. Covers every significant fork in the design.

3. **Design workflow** — numbered steps the sub-agent follows to complete
   the module design. References the decision table above.

4. **DDL templates** — parameterised CREATE TABLE and CREATE VIEW statements
   for every table and view defined in the design standard.
   - Use `{ProductName}` and `{entity}` placeholders
   - Include all COMMENT ON TABLE / COMMENT ON COLUMN statements
   - Preserve exact Teradata-specific syntax (validated patterns must not
     be paraphrased)
   - Do not include a separate example — the template is the example

5. **Integration patterns** — compact reference showing how this module
   connects to other modules. FK patterns, join-back patterns, cross-module
   views. Tables not prose.

6. **Agent discovery queries** — the SQL sequence an agent uses to find
   and explore this module. Include Semantic module registration INSERTs
   (entity_metadata, column_metadata, table_relationship, data_product_map)
   as ready-to-run templates.

7. **Documentation capture** — minimum INSERT templates for this module's
   documentation records, using `{ProductName}_Memory.` table references.
   Pre-filled with module-specific placeholders. One-line reminder that
   the protocol is defined in SKILL.md.

8. **Design checklist** — final verification items specific to this module.
   Does not repeat universal conventions from SKILL.md.
   Includes: functional validation queries; anti-pattern checks.

**Special instructions for `access-layer.md`:**

The access layer file is short (target 100–150 lines). It must contain:

1. **Header** — "Every AI-Native Data Product requires an Access Layer. Without it, all module
   databases are deployed but operationally invisible (Error 3523)."
2. **Three-role model** — ROLE_READ, ROLE_AGENT, ROLE_ADMIN with naming pattern and the rationale
   for keeping ROLE_AGENT separate from ROLE_READ
3. **Two-phase deployment** — Phase 1.5 (Semantic + Memory) and Phase 2.5 (Domain + Observability)
   with explicit note that Phase 1.5 is the minimum viable access grant
4. **DCL template** — the complete parameterised DCL from Section 6 of the Access Layer Design
   Standard: COMMENT ON ROLE statements, phase-separated GRANT blocks, commented-out Search and
   Prediction blocks, user assignment template comments
5. **Artefact location** — `{ProductName}/00-access/{ProductName}_access_layer.dcl`
6. **Documentation record** — complete `DD-ACCESS-001` Design_Decision INSERT template
7. **Checklist** — the 9-item checklist from Section 10 of the Access Layer Design Standard

**Object Placement Standard — SKILL.md protocol addition (universal convention):**

SKILL.md must include the following (this applies before every CREATE statement, not to one module):

> **Object Placement Protocol:** Before generating any CREATE TABLE, CREATE VIEW, CREATE PROCEDURE,
> or CREATE FUNCTION statement, locate the organisation's conforming implementation of the Object
> Placement Standard. Priority order: (1) explicit path in conversation, (2)
> `/mnt/skills/user/object-placement/SKILL.md`, (3) any file matching
> `Object_Placement_Standard*.md` in the project context. If none found: stop and ask
> *"Which database should this object type go in?"* before writing any DDL.

> **Physical Storage Protocol:** If object storage (S3, ADLS, GCS) is in use, also locate the
> Physical Storage Standard implementation before generating any OTF table DDL.

Both belong in SKILL.md, not in module files.

---

**Module-specific content that must be preserved exactly (do not paraphrase):**
- Recursive CTEs (Semantic `v_relationship_paths`)
- TD_VectorDistance function calls (Search)
- Any SQL marked as `TESTED ✅` in the source documents

**Content to add that source documents typically omit:**
- The expire-current → insert-new DML pattern for all temporal tables
- A staleness detection query (how to find records needing refresh)
- The agent discovery query sequence for this specific module

---

### Step 4 — Apply Compression Techniques

The goal is to leave the sub-agent maximum working memory for the design task.

**Replace prose with decision tables:**
```
Instead of: three paragraphs on wide vs tall feature format
Use:        | Condition | Pattern |
            | Features always accessed together | Wide |
            | Features accessed individually, sparse | Tall |
```

**Replace specific examples with parameterised templates:**
```
Instead of: Customer-specific DDL showing party_key
Use:        CREATE TABLE {ProductName}_Prediction.{entity}_features (
                {entity}_id BIGINT NOT NULL ...
```

**Consolidate repeated column sets:**
If multiple tables share the same temporal column pattern, define it once
at the top of the DDL section with a note: "apply to all temporal tables."

**Preserve exactly — do not compress:**
- Validated SQL (`TESTED ✅` in source documents)
- COMMENT ON TABLE/COLUMN text — agent-readable metadata
- Teradata-specific syntax with known failure modes

---

### Step 5 — Verify Before Packaging

**SKILL.md:**
- [ ] Under 175 lines
- [ ] No DDL or query syntax
- [ ] Documentation capture protocol complete and accurate
- [ ] Sub-agent routing instructions clear and unambiguous
- [ ] All six modules AND access-layer.md listed in module file index
- [ ] Object Placement Protocol present (locate standard before any CREATE statement)
- [ ] Physical Storage Protocol present (locate standard before any OTF table DDL)

**Each module file:**
- [ ] Under 500 lines
- [ ] Does not repeat SKILL.md content (naming conventions,
      boolean standards, documentation capture protocol)
- [ ] All tables from the design standard are present
- [ ] DDL uses `{ProductName}` and `{entity}` placeholders
- [ ] No `CHAR(1)` boolean columns
- [ ] No `= 'Y'` or `= 'N'` filter values
- [ ] Semantic registration INSERTs present
- [ ] Documentation capture INSERTs use `{ProductName}_Memory.` prefix
- [ ] Validated SQL preserved exactly

---

### Step 6 — Package and Validate

Use the skill creator packaging tool:

```bash
python -m scripts.package_skill /home/agent/ai-native-data-product /home/agent
```

The validator must return `✅ Skill is valid!` before proceeding.

Copy the packaged `.skill` file to `/mnt/user-data/outputs/` and present
it to the user for download.

---

### Step 7 — Report

After packaging, provide a summary covering:

1. **Skill structure** — file names and line counts for all files
2. **Context efficiency** — SKILL.md lines; typical sub-agent session
   (SKILL.md + 1 module file); comparison to previous 6-skill total
3. **Consistency corrections** — any boolean or naming fixes applied (old → new)
4. **Source document gaps filled** — operational patterns added
5. **Source document updates required** — exact changes to keep docs in sync

---

### Step 8 — Updating After Design Document Changes

When a design document is updated:

1. Identify which module file(s) are affected
2. List every change and its impact on the skill (confirm with user before editing)
3. If a universal convention changed (naming, booleans, documentation protocol),
   update SKILL.md and check all module files for knock-on impacts
4. If a module-specific change, update only the affected module file
5. Apply changes using `str_replace` — do not rewrite whole files
6. Re-run Step 5 verification and Step 6 packaging
7. Report what changed

The skill name must not change between versions: `ai-native-data-product`

---

## Reference: Size Targets

| File | Target | Hard limit |
|------|--------|-----------|
| `SKILL.md` | 100–150 lines | 175 lines |
| Any single module file | 300–400 lines | 500 lines |
| `access-layer.md` | 100–150 lines | 175 lines (compact standard) |
| Total (all files combined) | < 3,000 lines | 3,400 lines |
| Typical sub-agent context (SKILL.md + 1 module) | 400–550 lines | — |
| Access layer context (SKILL.md + access-layer.md) | 200–325 lines | — |

## Reference: Skill Directory Structure

```
ai-native-data-product/
├── SKILL.md
└── modules/
    ├── domain.md
    ├── semantic.md
    ├── search.md
    ├── prediction.md
    ├── observability.md
    ├── memory.md
    └── access-layer.md   ← always required; three roles, two-phase DCL, DD-ACCESS-001
```

## Reference: Module Deployment Order

| Phase | Module | Database pattern | Notes |
|-------|--------|-----------------|-------|
| 1 | Memory | `{Name}_Memory` | First — hosts documentation tables for all modules |
| 1 | Semantic | `{Name}_Semantic` | First — hosts discovery metadata for all modules |
| 2 | Domain | `{Name}_Domain` | Entity foundation |
| 2 | Observability | `{Name}_Observability` | Begins monitoring Domain immediately |
| 3 | Search | `{Name}_Search` | Requires Domain entities |
| 3 | Prediction | `{Name}_Prediction` | Requires Domain entities |

## Reference: Documentation Capture ID Prefixes

| Module | Decision ID | Change Log | Query Cookbook | Impl. Note |
|--------|------------|------------|----------------|------------|
| Domain | DD-DOMAIN- | CL-DOMAIN- | QC-DOMAIN- | IN-DOMAIN- |
| Semantic | DD-SEMANTIC- | CL-SEMANTIC- | QC-SEMANTIC- | IN-SEMANTIC- |
| Search | DD-SEARCH- | CL-SEARCH- | QC-SEARCH- | IN-SEARCH- |
| Prediction | DD-PREDICTION- | CL-PREDICTION- | QC-PREDICTION- | IN-PREDICTION- |
| Observability | DD-OBSERVABILITY- | CL-OBSERVABILITY- | QC-OBSERVABILITY- | IN-OBSERVABILITY- |
| Memory | DD-MEMORY- | CL-MEMORY- | QC-MEMORY- | IN-MEMORY- |
| Access Layer | DD-ACCESS- | CL-ACCESS- | QC-ACCESS- | IN-ACCESS- |

> Access Layer decisions live in the general `{ProductName}_Memory.Design_Decision` table.
> `DD-ACCESS-001` is the mandatory three-tier role model decision record (see Access Layer
> Design Standard Section 8).
