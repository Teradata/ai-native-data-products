---
title: Physical Storage Pattern
anchor: physical-storage
type: pattern
status: standard
version: 2.0
normative: true
---

# Physical Storage: Pattern

## AI-Native Data Product Architecture

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Status** | STANDARD |
| **Type** | Pattern (cross-cutting, platform-agnostic interface spec) |
| **Scope** | Any platform using object storage beneath a logical data-container model |
| **Extends** | [Master Design](../core/MASTER_DESIGN.md) |
| **Companion** | [object-placement](object-placement.md) |
| **Notation** | [Design Language](../core/DESIGN_LANGUAGE.md) |
| **Implementations** | Organisation profiles supplied for a build ([Organisation Profile Standard](../core/ORGANISATION_PROFILE.md)), carrying this pattern's sections alongside their object-placement sections. `implementation/{platform}/patterns/physical-storage/` documents how a binding consumes resolved paths; it is not an organisation's implementation. |

This pattern is an **interface specification**: it defines what a conforming physical-storage implementation must **declare** when object storage is the physical layer beneath the logical containers of the [object-placement](object-placement.md) pattern. The physical path is derived deterministically from the logical names: the two patterns are explicitly coupled, and neither is complete without the other when object storage is in use.

If an organisation keeps no product data in object storage, this pattern does not apply and object-placement alone suffices.

---

## 1. Purpose

Object-placement governs the **logical layer** (container and object naming, access principals). This pattern governs the **physical layer**: object-store paths, file formats, partition strategies, physical access controls, and data lifecycle. Physical placement is then deterministic and governed rather than ad hoc.

**This pattern provides no capability.** Like object placement, it imposes a contract on physical paths, formats, and lifecycle rather than offering an operation a design can require.

---

## 2. Terminology

| Term | Meaning |
|------|---------|
| **Object store** | A flat, key-value storage service; keys are paths, values are binary objects. |
| **Bucket** | Top-level named container; bucket-level policies govern coarse access. |
| **Path / Path prefix** | The full key addressing an object, or a prefix identifying a logical grouping (directory). |
| **Open Table Format (OTF)** | A table format over object-store files providing ACID, schema evolution, time travel, hidden partitioning. |
| **File format** | Binary encoding of data files. |
| **Partition** | A logical subdivision for query pruning. Hive-style (in the path) or hidden (in OTF metadata). |
| **Snapshot** | An OTF point-in-time table state enabling time travel; retained for a period before expiry. |
| **Path derivation function** | The deterministic algorithm computing the object-store path for a logical object. |
| **Bucket policy** | An access policy on a bucket governing which principals may act on which prefixes. |

**Illustrative products (non-normative).**

| Term | Examples |
|------|----------|
| Object store | S3, ADLS Gen2, GCS, MinIO |
| Open Table Format | Iceberg, Delta, Hudi |
| File format | Parquet, ORC, Avro |

---

## 3. Agent Consumption

When generating any physically-stored object:

1. **Locate** a conforming implementation of both this pattern and object-placement: both must be present. In an organisation profile they are the same document.
2. **Read the logical container and object name from the build context**, where they are resolved under object-placement.
3. **Read the physical path from the build context.** Paths are resolved once, for every table the profile places in object storage, from the profile's `Path` template; an agent does not call the path derivation function at generation time.
4. **Generate the deployment artefact** with both the logical container name and the physical path.
5. **Apply** the declared file format and partition strategy.
6. **Provision physical access**, bucket policies or equivalent, in addition to the logical access model.
7. **Run both validation procedures**: the logical (object-placement) and physical (this pattern).
8. **Never invent a path.** An agent reads every path from the build context; a path not produced by the declared derivation is a storage-governance defect.

**If the organisation keeps product data in object storage but no physical-storage implementation exists:** STOP. Do not generate OTF table definitions. Ask the user for the physical path convention, file format, and partition strategy. Object storage is declared by the implementation having this pattern's sections; an organisation profile without them declares that no product data is held in object storage.

---

## 4. Required Sections

Every conforming implementation MUST include all eight, using these exact headings.

The preferred conforming implementation is an [organisation profile](../core/ORGANISATION_PROFILE.md). It carries these eight sections as headings prefixed `Storage ` (`Storage Section 1. Storage Platform Declaration` through `Storage Section 8. Validation Procedure`), so they sit beside the object-placement sections in one document without colliding; the prefix is part of the exact heading a profile uses, and satisfies this rule. Their rules are stated in the profile's `Storage:`, `Paths:`, `Files:`, `Partitioning:`, `Lifecycle:` and `StorageAccess:` blocks, which the build-context resolver executes. The eight sections are present together or not at all.

**Section 1. Storage Platform Declaration.** The object-store service and region constraints; the OTF in use (or a statement that raw files are used); OTF version where relevant; the companion object-placement implementation named; whether this governs all physically-stored objects or a declared subset; any objects excluded from object storage. In an organisation profile, the `Storage:` block, whose companion is the profile's own object-placement sections.

**Section 2. Path Model.** How logical container-name segments map to physical path segments and in what order; the bucket strategy (one bucket, per-tier, per-classification, …) with rationale; the root prefix; whether segments use raw or annotated (`key=value`) values; whether views have physical paths (usually not); how production vs development paths are separated. In an organisation profile, the `Paths:` block's buckets and bucket rules, a rule narrowed by classification routing that class to its own bucket.

**Section 3. Path Derivation Pattern.** The complete path as an ordered sequence of segments; per segment its logical source, format, and mandatory/conditional status; the separator; the trailing-slash convention; ≥3 worked examples across lifecycle phases. Minimum signature:

```
derive_path(
  logical_container_name,  // the resolved container, from object-placement
  object_name,             // the resolved object name
  bucket                   // the target bucket
) -> fully_qualified_object_store_path
```

In an organisation profile, this section is stated by the `Paths:` block: its `Path` template, using `{bucket}`, `{container}`, `{object}`, `{environment}` and the product variables, is the derivation, and its examples are executable, re-derived by the resolver on every build. The derivation runs once, when the build context is resolved.

**Section 4. File Format and Encoding.** Default format for persistent tables; permitted alternatives and conditions; default compression; schema encoding rules; the schema-evolution policy (what is permitted vs requires drop/recreate); explicit prohibitions (e.g. no CSV for persistent tables). In an organisation profile, the `Files:` block.

**Section 5. Partition Strategy.** The partitioning model (Hive-style, hidden, none, or a combination); the partition spec (columns and transforms) or how `key=value` pairs appear in the path; the rule for selecting partition keys; the maximum number and rationale; how partition evolution is handled. In an organisation profile, the `Partitioning:` block.

**Section 6. Retention and Lifecycle.** Default retention per logical layer; OTF snapshot retention; orphan-file cleanup policy; object-store lifecycle/tiering rules; the workstream retirement procedure at the physical layer; who executes lifecycle actions. In an organisation profile, the `Lifecycle:` block. Physical lifecycle never shortens a retention the product's design specification decides.

**Section 7. Access Model.** The physical access model (bucket policies, IAM roles, ACLs) and its relationship to the logical access model; the mapping between logical and physical principals; the governing principle that **physical access must never exceed logical access**; the bucket-policy structure; bucket-level controls; cross-service access governance. In an organisation profile, the `StorageAccess:` block, mapping each access tier to its physical principal.

**Section 8. Validation Procedure.** An agent-executable check confirming: the path exists and matches the derivation function; the file format matches the default; the partition spec matches; no data files exist at non-conforming paths; physical principals are correctly scoped. States passing/failing output and requires halt-and-report on failure: never silent auto-correct. In an organisation profile, this section states that the procedure is generated by the platform binding from the profile, as for placement; it needs no block.

---

## 5. Optional Sections

Implementations MAY include: external catalogue integration, cross-platform access, disaster recovery, cost allocation, migration procedure (block → object storage). Agents read them if present.

---

## 6. Conformance Checklist

- [ ] Section 1 names the object store and OTF, and the companion object-placement implementation.
- [ ] Section 2 declares the bucket strategy and logical-to-physical mapping.
- [ ] Section 3 produces a unique path for any valid logical name and object name, and its worked examples execute.
- [ ] Section 4 declares default format, compression, and schema-evolution policy.
- [ ] Section 5 declares the partitioning model and key-selection rules.
- [ ] Section 6 declares retention per layer and the retirement procedure.
- [ ] Section 7 maps logical to physical principals and states the non-bypass principle.
- [ ] Section 8 is agent-executable and covers all five minimum checks, or is generated by the binding.
- [ ] All section headings match exactly, with the `Storage ` prefix where the implementation is an organisation profile.

---

## 7. Non-Goals

This pattern does not prescribe object-placement's concerns, which object store or OTF to use, compute-engine choice, data-modelling methodology, how data arrives, or query optimisation beyond partition strategy.

---

**End of Physical Storage Pattern**
