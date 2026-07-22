# Physical Storage — Pattern

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
| **Implementations** | [`implementation/teradata/patterns/physical-storage/`](../../implementation/teradata/patterns/physical-storage/) |

This pattern is an **interface specification**: it defines what a conforming physical-storage
implementation must **declare** when object storage (S3, ADLS, GCS, …) is the physical layer
beneath the logical containers of the [object-placement](object-placement.md) pattern. The physical
path is derived deterministically from the logical names — the two patterns are explicitly coupled,
and neither is complete without the other when object storage is in use.

If an organisation uses only proprietary block storage, this pattern does not apply and
object-placement alone suffices.

---

## 1. Purpose

Object-placement governs the **logical layer** (container and object naming, access principals).
This pattern governs the **physical layer** — object-store paths, file formats, partition
strategies, physical access controls, and data lifecycle — so physical placement is deterministic
and governed rather than ad hoc.

---

## 2. Terminology

| Term | Meaning |
|------|---------|
| **Object store** | A flat, key-value storage service; keys are paths, values are binary objects. S3, ADLS Gen2, GCS, MinIO. |
| **Bucket** | Top-level named container; bucket-level policies govern coarse access. |
| **Path / Path prefix** | The full key addressing an object, or a prefix identifying a logical grouping (directory). |
| **Open Table Format (OTF)** | A table format over object-store files providing ACID, schema evolution, time travel, hidden partitioning. Iceberg, Delta, Hudi. |
| **File format** | Binary encoding of data files. Parquet, ORC, Avro. |
| **Partition** | A logical subdivision for query pruning — Hive-style (in the path) or hidden (in OTF metadata). |
| **Snapshot** | An OTF point-in-time table state enabling time travel; retained for a period before expiry. |
| **Path derivation function** | The deterministic algorithm computing the object-store path for a logical object. |
| **Bucket policy** | An access policy on a bucket governing which principals may act on which prefixes. |

---

## 3. Agent Consumption

When generating any physically-stored object:

1. **Locate** a conforming implementation of both this pattern and object-placement — both must be present.
2. **Derive the logical container name** using object-placement's derivation function.
3. **Derive the physical path** using this pattern's path derivation function.
4. **Generate the DDL** with both the logical container name and the physical path.
5. **Apply** the declared file format and partition strategy.
6. **Provision physical access** — bucket policies or equivalent — in addition to the logical access model.
7. **Run both validation procedures** — the logical (object-placement) and physical (this pattern).
8. **Never invent a path** not produced by the declared derivation function — ad-hoc paths are a storage-governance defect.

**If object storage is declared in object-placement but no physical-storage implementation exists:**
STOP. Do not generate OTF table DDL. Ask the user for the physical path convention, file format, and
partition strategy.

---

## 4. Required Sections

Every conforming implementation MUST include all eight, using these exact headings.

**Section 1 — Storage Platform Declaration.** The object-store service and region constraints; the
OTF in use (or a statement that raw files are used); OTF version where relevant; the companion
object-placement implementation named; whether this governs all physically-stored objects or a
declared subset; any objects excluded from object storage.

**Section 2 — Path Model.** How logical container-name segments map to physical path segments and in
what order; the bucket strategy (one bucket, per-tier, per-classification, …) with rationale; the
root prefix; whether segments use raw or annotated (`key=value`) values; whether views have physical
paths (usually not); how production vs development paths are separated.

**Section 3 — Path Derivation Pattern.** The complete path as an ordered `{{Segment}}` sequence;
per segment its logical source, format, and mandatory/conditional status; the separator; the
trailing-slash convention; ≥3 worked examples across lifecycle phases. Minimum signature:

```
derive_path(
  logical_container_name,  // output of object-placement derive_container()
  object_name,             // the logical object name
  bucket                   // the target bucket
) -> fully_qualified_object_store_path
```

**Section 4 — File Format and Encoding.** Default format for persistent tables; permitted
alternatives and conditions; default compression; schema encoding rules; the schema-evolution
policy (what is permitted vs requires drop/recreate); explicit prohibitions (e.g. no CSV for
persistent tables).

**Section 5 — Partition Strategy.** The partitioning model (Hive-style, hidden, none, or a
combination); the partition spec (columns and transforms) or how `key=value` pairs appear in the
path; the rule for selecting partition keys; the maximum number and rationale; how partition
evolution is handled.

**Section 6 — Retention and Lifecycle.** Default retention per logical layer; OTF snapshot
retention; orphan-file cleanup policy; object-store lifecycle/tiering rules; the workstream
retirement procedure at the physical layer; who executes lifecycle actions.

**Section 7 — Access Model.** The physical access model (bucket policies, IAM roles, ACLs) and its
relationship to the logical access model; the mapping between logical and physical principals; the
governing principle that **physical access must never exceed logical access**; the bucket-policy
structure; bucket-level controls; cross-service access governance.

**Section 8 — Validation Procedure.** An agent-executable check confirming: the path exists and
matches the derivation function; the file format matches the default; the partition spec matches;
no data files exist at non-conforming paths; physical principals are correctly scoped. States
passing/failing output and requires halt-and-report on failure — never silent auto-correct.

---

## 5. Optional Sections

Implementations MAY include: external catalogue integration, cross-platform access, disaster
recovery, cost allocation, migration procedure (block → object storage). Agents read them if present.

---

## 6. Conformance Checklist

- [ ] Section 1 names the object store and OTF, and the companion object-placement implementation.
- [ ] Section 2 declares the bucket strategy and logical-to-physical mapping.
- [ ] Section 3 produces a unique path for any valid logical name and object name.
- [ ] Section 4 declares default format, compression, and schema-evolution policy.
- [ ] Section 5 declares the partitioning model and key-selection rules.
- [ ] Section 6 declares retention per layer and the retirement procedure.
- [ ] Section 7 maps logical to physical principals and states the non-bypass principle.
- [ ] Section 8 is agent-executable and covers all five minimum checks.
- [ ] All section headings match exactly.

---

## 7. Non-Goals

This pattern does not prescribe object-placement's concerns, which object store or OTF to use,
compute-engine choice, data-modelling methodology, how data arrives, or query optimisation beyond
partition strategy.

---

**End of Physical Storage Pattern**
