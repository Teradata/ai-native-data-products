# AI-Native Data Product — Platform Standards Application Guide
## Reference Fragment for Object Placement and Physical Storage Standards

---

## Purpose

This prompt fragment guides agents and designers in applying two platform-agnostic
interface specifications that govern **where objects are placed** and **how they are
physically stored** before any DDL is generated.

Include this fragment when:
- Starting a new data product design
- Adding new objects to an existing product
- Generating DDL for any CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, or CREATE FUNCTION statement
- Working with Open Table Format (OTF) tables backed by object storage (S3, ADLS, GCS)

---

## The Two Standards

### Object Placement Standard (logical layer)

The Object Placement Standard governs the **logical layer** — which database (container)
each object type belongs in, how databases are named, and what access principals can reach them.

**It is an interface specification, not a naming convention.** Your organisation provides a
conforming implementation that answers the eight required questions. Claude reads your
implementation; it does not invent placement rules.

Before generating any DDL, Claude will:
1. Locate your implementation (see priority order below)
2. Read all eight required sections
3. Call the Derivation Function to determine the target database for each object
4. Apply the Object Naming Rule (type-discriminated by container in strict-separation environments)
5. Provision implied grants required by the separation architecture
6. Run the Validation Procedure after generation

### Physical Storage Standard (physical layer)

The Physical Storage Standard governs the **physical layer** — object store paths, file formats,
partition strategies, and physical access controls — for platforms using object storage.

**It extends the Object Placement Standard.** Both must be present when object storage is in use.
Claude reads the Object Placement Standard first to derive the logical container name, then reads
the Physical Storage Standard to derive the physical path.

---

## Prompt Fragment (Include in Agent System Prompt or Design Session)

```markdown
## Platform Standards Protocol

### Before ANY DDL generation

**Step 1 — Locate the Object Placement Standard implementation**

Priority order:
1. An explicit file path provided in this conversation or project instructions
2. `/mnt/skills/user/object-placement/SKILL.md`
3. A file matching `Object_Placement_Standard*.md` in the project context
4. **If none of the above exist: STOP.**

   Do not write any CREATE statement. Ask:

   > "Before I generate any objects, I need your Object Placement Standard. Specifically:
   > - Are tables and views in separate databases (strict separation) or in the same database
   >   (co-located)?
   > - What is the naming convention for those databases?
   > - Are there any object types with special placement rules?"

**Step 2 — Read all eight required sections of the implementation**

The eight sections are: Platform Declaration, Container Model, Naming Pattern,
Object Placement Rules, Separation Policy, Derivation Function, Access Model,
Validation Procedure.

If any section is missing, the implementation is non-conforming. Report the gap
and ask for clarification before proceeding.

**Step 3 — Call the Derivation Function before every CREATE statement**

```
derive_container(
  object_type,         // TABLE, VIEW, PROCEDURE, FUNCTION, MACRO
  environment_inputs,  // from the Naming Pattern (environment, programme, etc.)
  classification       // if the implementation uses security classification
) → target_database_name
```

Place the object in the database returned by this function only. Never default
to a previously-used database or assume co-location.

**Step 4 — Apply the correct Object Naming Rule**

- If the implementation declares `STRICT_SEPARATION`: object names must be
  **identical** across container types for the same logical object.
  Type prefixes (`v_`, `t_`) and suffixes (`_vw`, `_tbl`) are **prohibited**
  on object names — the container is the type discriminator.
- If the implementation declares `CO_LOCATED` or `TYPE_GROUPED`: apply the
  disambiguation rule exactly as declared. Never invent a convention.

**Step 5 — Provision implied grants**

If the Object Placement Standard's Access Model declares implied grants
(typically cross-database view grants required for strict-separation architectures),
provision them as part of the standard creation sequence — not as an afterthought.
These grants fail silently at object creation but produce access errors at query time.

**Step 6 — Run the Validation Procedure**

After generating objects, run the platform-specific procedure from Section 8 of
the implementation. If validation fails: halt, report, and await instruction.
Never auto-correct silently.

---

### If Object Storage Is in Use

**Step 1 — Locate the Physical Storage Standard implementation**

Priority order:
1. An explicit file path provided in this conversation or project instructions
2. `/mnt/skills/user/physical-storage/SKILL.md`
3. A file matching `Physical_Storage_Standard*.md` in the project context
4. **If none of the above exist and the Object Placement Standard indicates object
   storage is in use: STOP.**

   Do not generate any OTF table DDL with a LOCATION clause. Ask:

   > "The Object Placement Standard indicates object storage is in use, but I cannot
   > find a Physical Storage Standard. Before I generate any table DDL with a storage
   > location, I need: the physical path convention, the Open Table Format in use,
   > the file format, and the partition strategy."

**Step 2 — Derive the physical path alongside the logical container**

Call both derivation functions in sequence:
```
logical_container = derive_container(object_type, environment_inputs)
physical_path     = derive_path(logical_container, object_name, bucket)
```

Both are required in the CREATE TABLE statement when OTF is in use:
- `logical_container` → the database in the CREATE TABLE statement
- `physical_path` → the LOCATION clause in the CREATE TABLE statement

**Step 3 — Apply the declared file format and partition strategy**

Use the defaults from Section 4 (file format) and Section 5 (partition strategy).
Do not choose formats or partitioning based on general knowledge of the platform —
only apply what the implementation declares.

**Step 4 — Run both validation procedures**

After generation, run:
1. Object Placement Standard Section 8 — validates logical placement
2. Physical Storage Standard Section 8 — validates physical placement and access

Both must pass. A table at the correct logical location but the wrong physical path
is a governance defect that will not surface until lifecycle management or backup fails.
```

---

## What to Declare in the Design Session

If you are starting a new design session, provide the following information upfront
to avoid interruptions during DDL generation:

```
Object Placement Standard location: [file path or "NONE — please ask me questions"]
Physical Storage Standard location: [file path or "NOT APPLICABLE — block storage only"]
Environment inputs for Derivation Function:
  [whatever parameters your implementation requires, e.g.:]
  - Programme code: [e.g. D01]
  - Function code: [e.g. MP]
  - Lifecycle phase: [e.g. DEV / TEST / PRD]
  - Security classification: [if applicable]
```

---

## Common Errors This Protocol Prevents

| Error | Root cause | Prevented by |
|-------|-----------|-------------|
| `Error 3523` access denied on a view that references another database | Missing implied cross-database grant | Step 5 (provision implied grants) |
| Objects in wrong database discovered during audit | Container derivation not called before CREATE | Step 3 (Derivation Function) |
| Type-prefixed names in a strict-separation environment | Naming rule not read | Step 4 (Object Naming Rule) |
| Table at wrong S3 path, lifecycle policy missed | Physical path not derived | Physical Storage Step 2 |
| File format inconsistency across related tables | Format not read from implementation | Physical Storage Step 3 |
| Validation discovers misplaced objects after data has accumulated | Validation skipped | Step 6 / Physical Storage Step 4 |

---

## Notes for Prompt Engineers

**When to include this fragment:**
- Any design session that produces DDL
- Any agent that generates objects on behalf of a designer
- Any migration or refactoring that moves objects between databases

**When NOT to include:**
- Read-only query sessions (no DDL being generated)
- Sessions where the designer has already confirmed object placement verbally and
  the Object Placement Standard has been read in a prior turn

**Integration with Design_Data_Product_Starter.md:**
This fragment is referenced by the Platform Standards Pre-flight in the Design Starter.
When using the Design Starter, the pre-flight handles the location questions — this
fragment provides the operational protocol that Claude applies during DDL generation.

**Integration with Access Layer:**
The Object Placement Standard's Access Model section (Section 7) and the Access Layer
Design Standard both govern access. They are complementary:
- The Object Placement Standard defines the container-level access model (which principals
  can reach which containers, and which cannot)
- The Access Layer Design Standard defines the product-level role model (ROLE_READ,
  ROLE_AGENT, ROLE_ADMIN) and the DCL artefact that implements it

Both must be applied. The Object Placement Standard's implied grants are provisioned
as part of DDL generation (they are infrastructure grants). The Access Layer roles are
provisioned as a separate DCL artefact at Phase 1.5 and Phase 2.5.
