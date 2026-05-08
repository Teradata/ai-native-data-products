# Advocated Data Management Standards

## AI-Native Data Product Architecture - Teradata Recommendations

---

## Document Control

| Attribute | Value |
| --- | --- |
| **Version** | 1.6 |
| **Status** | GUIDANCE |
| **Last Updated** | 2026-05-08 |
| **Owner** | Data Architecture |
| **Scope** | Cross-Module Data Management Guidance |
| **Type** | Recommended Practices |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Bi-Temporal Data Management](#2-bi-temporal-data-management)
3. [Column Optimization Strategy](#3-column-optimization-strategy)
4. [Surrogate Key Strategy](#4-surrogate-key-strategy)
5. [Soft Delete Pattern](#5-soft-delete-pattern)
6. [Access Layer](#6-access-layer)
7. [Observability Offload Pattern](#7-observability-offload-pattern)
8. [Timezone Handling](#8-timezone-handling)
9. [Data Quality Management](#9-data-quality-management)
10. [Audit Trail Strategy](#10-audit-trail-strategy)
11. [Platform Implementation Guidance: Teradata](#11-platform-implementation-guidance-teradata)
12. [Implementation Decision Trees](#12-implementation-decision-trees)

---

## 1. Introduction

### 1.1 Purpose of This Document

This document provides **Teradata's recommended practices** for data management in AI-Native Data Products. These are **advocated approaches** based on 30+ years of enterprise data management experience, not mandatory requirements.

**Key Principle**: The Domain Module Design Standard defines STRUCTURE; this document advocates IMPLEMENTATION CHOICES.

### 1.2 How to Use This Guidance

| Your Situation | How to Apply |
| --- | --- |
| **Starting fresh** | Adopt these practices as defaults |
| **Existing patterns** | Evaluate selective adoption |
| **Specific constraints** | Adapt patterns to your context |
| **Different philosophy** | Document your alternative approach |


### 1.3 Advocacy vs Mandate

| This Document ADVOCATES | Design Standard MANDATES |
| --- | --- |
| Bi-temporal tracking | Module structure |
| Surrogate keys | Naming conventions |
| Soft deletes | Cross-module integration patterns |
| Observability offload | Agent discoverability |
| TIMESTAMP WITH TIME ZONE | View standards |
| Column optimization | - |


**Remember**: You can build AI-Native data products using different temporal patterns, different key strategies, or different column approaches—as long as you follow the structural patterns in the Design Standard.

---

## 2. Bi-Temporal Data Management

### 2.1 Why We Advocate Bi-Temporal

**Traditional Approach**: Type 2 SCD (single time dimension) **Advocated Approach**: Bi-temporal (two independent time dimensions)

#### Key Benefits for AI-Native Data Products

| Requirement | Type 2 SCD | Bi-Temporal |
| --- | --- | --- |
| **Point-in-time correctness** | ⚠️ Approximate | ✅ Exact |
| **Late-arriving facts** | ❌ Corrupts history | ✅ Preserves history |
| **Corrections tracking** | ❌ Lost | ✅ Traceable |
| **ML feature accuracy** | ⚠️ May be wrong | ✅ Guaranteed correct |
| **Audit trail** | ⚠️ Partial | ✅ Complete |
| **Explainability** | ⚠️ Limited | ✅ Full reconstruction |


### 2.2 The Two Time Dimensions

    Example: Customer changes name from "Jane Doe" to "Jane Smith"

    Real World Event:
    - Marriage happens on 2024-06-15 (Valid Time)

    Database Recording:
    - We learn about it on 2024-07-01 (Transaction Time)

    Bi-Temporal Record:
    - valid_from_dts = 2024-06-15 (when it became true in reality)
    - transaction_from_dts = 2024-07-01 (when we recorded it)

**Valid Time**: When the fact was TRUE in the real world **Transaction Time**: When the fact was RECORDED in the database

### 2.3 Advocated Bi-Temporal Column Set

    -- ADVOCATED: Bi-temporal columns
    valid_from_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL
        COMMENT 'When this version became true in real world',

    valid_to_dts        TIMESTAMP(6) WITH TIME ZONE NOT NULL
        DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
        COMMENT 'When this version stopped being true in real world',

    transaction_from_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL
        DEFAULT CURRENT_TIMESTAMP(6)
        COMMENT 'When this version was inserted into database',

    transaction_to_dts   TIMESTAMP(6) WITH TIME ZONE NOT NULL
        DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
        COMMENT 'When this version was superseded in database',

    is_current  BYTEINT NOT NULL DEFAULT 1
        COMMENT '1 = Current version, 0 = Historical version',

**IMPORTANT: PRIMARY INDEX for Temporal Tables**

Temporal tables (bi-temporal, Type 2 SCD, versioned) should use **PRIMARY INDEX** (NUPI), not UNIQUE PRIMARY INDEX, because:

- Multiple versions exist for the same entity_id
- Historical records create natural duplicates
- UNIQUE PRIMARY INDEX would prevent version updates


    -- CORRECT for temporal tables
    CREATE TABLE Party_H (
        party_id BIGINT NOT NULL,
        -- ... bi-temporal columns ...
    )
    PRIMARY INDEX (party_id);  -- NUPI allows multiple versions

    -- INCORRECT for temporal tables
    CREATE TABLE Party_H (
        party_id BIGINT NOT NULL,
        -- ... bi-temporal columns ...
    )
    UNIQUE PRIMARY INDEX (party_id);  -- Would fail on version 2

**Use UNIQUE PRIMARY INDEX only for:**

- Non-temporal tables (no versioning)
- Reference data with unique codes
- Tables where each key appears exactly once


### 2.4 Bi-Temporal Operations

#### Insert New Entity (Version 1)

    INSERT INTO Party_H (
        party_id, party_key, legal_name,
        valid_from_dts, valid_to_dts,
        transaction_from_dts, transaction_to_dts,
        is_current, is_deleted
    ) VALUES (
        1001, 'CUST-12345', 'Jane Doe',
        TIMESTAMP '2024-01-01 00:00:00+00:00',
        TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
        CURRENT_TIMESTAMP(6),
        TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
        1, 0
    );

#### Update Entity (Create Version 2)

    -- Step 1: Close out current version
    UPDATE Party_H
    SET valid_to_dts = TIMESTAMP '2024-06-15 00:00:00+00:00',
        transaction_to_dts = CURRENT_TIMESTAMP(6),
        is_current = 0
    WHERE party_id = 1001 AND is_current = 1;

    -- Step 2: Insert new version
    INSERT INTO Party_H (
        party_id, party_key, legal_name,
        valid_from_dts, valid_to_dts,
        transaction_from_dts, transaction_to_dts,
        is_current, is_deleted
    ) VALUES (
        1001, 'CUST-12345', 'Jane Smith',  -- NAME CHANGED
        TIMESTAMP '2024-06-15 00:00:00+00:00',  -- When change occurred
        TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
        CURRENT_TIMESTAMP(6),  -- When we recorded it
        TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
        1, 0
    );

#### Correct Historical Data (Late-Arriving Fact)

    -- Scenario: Discovered marriage actually happened on 2024-06-10, not 2024-06-15
    -- We need to correct valid_from_dts but preserve transaction history

    -- Step 1: Close incorrect version in transaction time
    UPDATE Party_H
    SET transaction_to_dts = CURRENT_TIMESTAMP(6),
        is_current = 0
    WHERE party_id = 1001
      AND valid_from_dts = TIMESTAMP '2024-06-15 00:00:00+00:00'
      AND is_current = 1;

    -- Step 2: Insert corrected version with new transaction time
    INSERT INTO Party_H (
        party_id, party_key, legal_name,
        valid_from_dts, valid_to_dts,
        transaction_from_dts, transaction_to_dts,
        is_current, is_deleted
    ) VALUES (
        1001, 'CUST-12345', 'Jane Smith',
        TIMESTAMP '2024-06-10 00:00:00+00:00',  -- CORRECTED valid time
        TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
        CURRENT_TIMESTAMP(6),  -- NEW transaction time
        TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
        1, 0
    );

    -- Result: Complete history preserved
    -- - What we thought (2024-06-15) - closed in transaction time
    -- - What actually happened (2024-06-10) - current

### 2.5 Advocated Query Patterns

#### Get Current State

    SELECT party_id, party_key, legal_name
    FROM Party_H
    WHERE party_key = 'CUST-12345'
      AND is_current = 1
      AND is_deleted = 0;

#### Point-in-Time Query (for ML Features)

    -- "What was the customer's name on 2024-05-01?"
    -- Critical for computing features with temporal correctness
    SELECT party_id, party_key, legal_name
    FROM Party_H
    WHERE party_key = 'CUST-12345'
      AND TIMESTAMP '2024-05-01 00:00:00+00:00' >= valid_from_dts
      AND TIMESTAMP '2024-05-01 00:00:00+00:00' < valid_to_dts
      AND is_deleted = 0
      AND transaction_from_dts = (
          SELECT MAX(transaction_from_dts)
          FROM Party_H p2
          WHERE p2.party_id = Party_H.party_id
            AND p2.transaction_from_dts <= TIMESTAMP '2024-05-01 23:59:59.999999+00:00'
      );

#### As-Of Query (Transaction Time)

    -- "What did our database show on 2024-07-15 (before correction)?"
    SELECT party_id, party_key, legal_name
    FROM Party_H
    WHERE party_key = 'CUST-12345'
      AND transaction_from_dts <= TIMESTAMP '2024-07-15 23:59:59.999999+00:00'
      AND transaction_to_dts > TIMESTAMP '2024-07-15 23:59:59.999999+00:00';

### 2.6 Alternative: Type 2 SCD (When Acceptable)

**Use Type 2 SCD instead of bi-temporal when:**

- Late-arriving facts are extremely rare
- Corrections are not needed
- ML features don't require point-in-time correctness
- Simpler is better for your use case


    -- Type 2 SCD (simpler temporal)
    CREATE TABLE Party_H (
        party_id BIGINT NOT NULL,
        party_key VARCHAR(50) NOT NULL,
        effective_date DATE NOT NULL,
        expiration_date DATE NOT NULL DEFAULT DATE '9999-12-31',
        is_current BYTEINT NOT NULL DEFAULT 1,
        -- ... other columns ...
    );

**Trade-off**: Simpler implementation, but loses ability to handle corrections and lacks transaction-time dimension.

---

## 3. Column Optimization Strategy

### 3.1 The Column Overhead Challenge

**Traditional Standards**: 20+ standard columns per table **Problem**: Significant overhead on high-volume tables **Advocated Solution**: Three-tier approach

### 3.2 Three-Tier Column Strategy

#### Tier 1: Core Columns (Always Include)

**Minimum viable set for AI-Native domain tables:**

    {entity}_id        BIGINT NOT NULL             -- Surrogate key
    {entity}_key       VARCHAR(50) NOT NULL        -- Natural key
    valid_from_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL
    valid_to_dts        TIMESTAMP(6) WITH TIME ZONE NOT NULL
    transaction_from_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL
    transaction_to_dts   TIMESTAMP(6) WITH TIME ZONE NOT NULL
    is_current  BYTEINT NOT NULL DEFAULT 1
    is_deleted          BYTEINT NOT NULL DEFAULT 0

**Total: 8 columns**

#### Tier 2: Extended Columns (Add When Justified)

    -- Version tracking (if humans need it)
    version_number      INTEGER

    -- ID type (if multiple identifier types exist)
    {entity}_id_type    VARCHAR(20)

    -- Direct references to Observability (for performance)
    change_event_id    BIGINT  -- FK to Observability.ChangeEvent_H
    lineage_id         BIGINT  -- FK to Observability.DataLineage_H
    quality_id        BIGINT  -- FK to Observability.DataQuality_H

    -- Change detection (if needed in ETL)
    record_hash         VARCHAR(64)

**Add selectively based on need**

#### Tier 3: Offload to Observability (Recommended)

    -- Instead of in Domain table:
    created_by, updated_by, deleted_by, deleted_reason
    source_system, source_record_id, batch_id
    data_quality_score, quality_rule_failures

    -- Store in Observability module:
    Observability.ChangeEvent_H    -- Who, when, why
    Observability.DataLineage_H    -- Source tracking
    Observability.DataQuality_H    -- Quality time-series

### 3.3 Column Overhead Comparison

| Approach | Columns | Storage Impact | Join Needed |
| --- | --- | --- | --- |
| **Core Only** | 8 | Minimal | Yes (via views) |
| **Core + FK Refs** | 11 | Low | Yes (but fast) |
| **Core + Extended** | 15-20 | Medium | Sometimes |
| **Traditional (all in Domain)** | 20-25 | High | No |


### 3.4 Advocated Approach by Table Volume

| Table Volume | Advocated Approach | Rationale |
| --- | --- | --- |
| **< 10M rows** | Core + Extended OK | Storage overhead acceptable |
| **10M - 100M rows** | Core + FK Refs | Balance performance and storage |
| **> 100M rows** | Core Only + Views | Minimize overhead |
| **Reference tables** | Core + Extended OK | Small, low-volume |

---

## 4. Surrogate Key Strategy

### 4.1 Why We Advocate Surrogate Keys

**Advocated**: System-generated BIGINT surrogate keys **Alternative**: Natural keys as primary identifier

#### Benefits of Surrogate Keys

| Benefit | Description |
| --- | --- |
| **Stability** | Never changes, even if natural key changes |
| **Performance** | BIGINT joins faster than VARCHAR |
| **Simplicity** | Single column vs composite natural keys |
| **Universality** | Works for all entity types |
| **Cross-module** | Consistent FK pattern |


### 4.2 Surrogate Key Stability in History Tables

In SCD Type 2 history tables, multiple rows exist for the same real-world entity —
one row per version. It is therefore best practice to **allocate surrogate keys
separately from the history table itself**, so that the same surrogate value is
consistently used across all versions of an entity.

This matters because other tables — transaction history, product holdings, prediction
outputs, cross-module joins — hold FK references to the entity's surrogate. If the
surrogate changes between versions, those FK references become ambiguous: which
version's value should be stored?

    Illustrative example: Customer 'CUST-12345' with 3 SCD versions
      Version 1 → party_id = 1
      Version 2 → party_id = 1   ← same surrogate (correct — separate allocation)
      Version 3 → party_id = 1   ← same surrogate (correct — separate allocation)

      A transaction table holding party_id = 1 unambiguously identifies the customer
      regardless of which version is current.

When surrogate allocation is managed separately, cross-module FK joins are stable
and unambiguous regardless of how many SCD versions exist for an entity.

### 4.3 Recommended Approach: The Keymap Pattern

The Keymap pattern is the approach recommended in this document. If your organisation
already has an established surrogate key allocation strategy — such as a central
sequence service, a UUID generator, or an enterprise key management framework — that
existing standard should be used in preference to the Keymap pattern described here.
The requirement from the Domain Module Design Standard is simply that surrogate keys
are **stable across SCD versions**; the mechanism for achieving that stability is a
designer choice.

If adopting the Keymap pattern, the following templates apply.

#### Keymap Table DDL

    -- One row per unique real-world entity.
    -- IDENTITY fires here once per natural key — never on the _H table.
    CREATE TABLE {ProductName}_Domain.{Entity}_Keymap (
        {entity}_id   BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
        {entity}_key  VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC NOT NULL,
        source_system VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
        created_dts   TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
    )
    UNIQUE PRIMARY INDEX ({entity}_key);  -- UNIQUE PI: one row per natural key

    COMMENT ON TABLE {ProductName}_Domain.{Entity}_Keymap IS
    'Keymap: one row per unique {entity}. Surrogate key (IDENTITY) generated here
    and referenced by {Entity}_H and all cross-domain FK columns. Natural key is
    {entity}_key from the source system.';
    COMMENT ON COLUMN {ProductName}_Domain.{Entity}_Keymap.{entity}_id IS
    'Surrogate key - generated exactly once per real-world entity. Stable across
    all SCD versions in {Entity}_H and across all modules that reference this entity.';
    COMMENT ON COLUMN {ProductName}_Domain.{Entity}_Keymap.{entity}_key IS
    'Natural business key from the source system - used to look up the stable surrogate.';

#### History Table DDL

    -- {entity}_id is BIGINT NOT NULL — populated from the keymap (or equivalent
    -- allocation mechanism) via JOIN. Never generated directly on this table.
    -- Multiple rows with the same {entity}_id will exist (one per SCD version).
    -- PRIMARY INDEX (non-unique) co-locates all versions on the same AMP,
    -- making expire-and-insert SCD operations efficient.
    CREATE TABLE {ProductName}_Domain.{Entity}_H (
        {entity}_id   BIGINT NOT NULL,         -- from Keymap — stable across versions
        {entity}_key  VARCHAR(50) NOT NULL,    -- natural key repeated for convenience
        -- ... temporal and business columns ...
        PRIMARY INDEX ({entity}_id)            -- NUPI: multiple versions allowed
    );

    COMMENT ON COLUMN {ProductName}_Domain.{Entity}_H.{entity}_id IS
    'Surrogate key - allocated via surrogate key allocation strategy (see Advocated
    Data Management Standards Section 4). Stable across all SCD versions for the
    same real-world entity. Never generated directly on this table.';

#### Two-Step Load Pattern (Keymap approach)

    -- Step 1: Register any new natural keys (idempotent — WHERE NOT EXISTS)
    INSERT INTO {ProductName}_Domain.{Entity}_Keymap ({entity}_key, source_system)
    SELECT DISTINCT TRIM(s.NATURAL_KEY_COLUMN), 'SOURCE_SYSTEM_NAME'
    FROM {source_table} s
    WHERE NOT EXISTS (
        SELECT 1 FROM {ProductName}_Domain.{Entity}_Keymap k
        WHERE k.{entity}_key = TRIM(s.NATURAL_KEY_COLUMN)
    );

    -- Step 2: Populate history table using keymap JOIN
    INSERT INTO {ProductName}_Domain.{Entity}_H (
        {entity}_id, {entity}_key, /* business columns */,
        valid_from_dts, valid_to_dts, is_current, is_deleted
    )
    SELECT
        k.{entity}_id,               -- stable surrogate from keymap
        TRIM(s.NATURAL_KEY_COLUMN),
        /* business columns */,
        CURRENT_TIMESTAMP(6), TIMESTAMP '9999-12-31 23:59:59.999999+00:00', 1, 0
    FROM {source_table}                              s
    JOIN {ProductName}_Domain.{Entity}_Keymap        k
        ON k.{entity}_key = TRIM(s.NATURAL_KEY_COLUMN);

#### Cross-Entity Foreign Keys

Regardless of the surrogate key allocation mechanism chosen, all FK references
between domain entities should point to the **stable surrogate**, not to a specific
row in the `_H` table, to ensure FK joins are unambiguous across SCD versions.

    -- FK columns in other entities reference the stable surrogate
    CREATE TABLE {ProductName}_Domain.Order_H (
        order_id    BIGINT NOT NULL,
        party_id    BIGINT,     -- FK to Party stable surrogate (e.g. via Party_Keymap)
        product_id  BIGINT,     -- FK to Product stable surrogate
        -- ...
    );

### 4.4 Reference and Lookup Table Exemption

The surrogate key stability requirement applies to entities whose surrogate is **referenced as a foreign key by other tables**. Reference and lookup tables, as
well as detail/child entities that are never themselves FK-referenced, do not need a
separate allocation mechanism — a simple IDENTITY column directly on the `_H` table
is sufficient, since no external table holds a reference to their surrogate across
SCD versions.

    Stable allocation required           Simple IDENTITY on _H acceptable
    ----------------------------------   ------------------------------------------
    Party   (FK target of Order)         Reference tables  (e.g. LoanPurpose_R)
    Order   (FK target of LineItem)      Lookup tables     (e.g. StatusCode_R)
    Product (FK target of Order)         Detail/child entities with no FK dependants
                                         (e.g. CustomerContact, PropertyRisk)

**Rule**: Does any other table hold a FK column pointing to this entity's surrogate?

- YES → A surrogate allocation strategy is recommended to ensure FK stability across SCD versions
- NO → Simple IDENTITY on `_H` is sufficient


### 4.5 Surrogate Key Allocation Decision Tree

    START: Is this entity's surrogate referenced as a FK by any other table?
    |
    +-- YES --> Surrogate allocation strategy required
    |           Options (choose one):
    |           a) Keymap pattern (recommended in this document)
    |           b) Organisation's existing central key allocation standard
    |           c) Database sequence with natural key constraint on _H
    |           Key principle: the surrogate must be stable across SCD versions
    |
    +-- NO  --> Reference/lookup table or detail entity: IDENTITY on _H is acceptable
                - {entity}_id = BIGINT GENERATED ALWAYS AS IDENTITY on _H
                - Single-step INSERT; no prior allocation step needed
                - Document explicitly that this entity is not a FK target

### 4.6 When Natural Keys Are Acceptable as the Surrogate

**Use natural key as surrogate when:**

- Natural key is truly immutable
- Natural key is single column
- Natural key is numeric (not VARCHAR)
- Business strongly prefers it


**Example**: Product SKU that never changes

    CREATE TABLE Product_H (
        product_id BIGINT NOT NULL,  -- Still use surrogate internally
        sku        VARCHAR(20) NOT NULL,
        -- ...
        PRIMARY INDEX (product_id)
    );

---

## 5. Soft Delete Pattern

### 5.1 Why We Advocate Soft Deletes

**Hard Delete**: `DELETE FROM Party_H WHERE party_id = 1001` **Soft Delete**: `UPDATE Party_H SET is_deleted = 1 WHERE party_id = 1001`

#### Benefits for AI-Native Data Products

| Benefit | Description |
| --- | --- |
| **Audit trail** | Complete history preserved |
| **Explainability** | "Why did model predict X?" requires historical state |
| **Regulatory compliance** | GDPR, CCPA require audit trails |
| **Reversibility** | Accidental deletes recoverable |
| **Analytics** | Churn analysis, deletion patterns |
| **ML features** | "Was customer deleted" is a feature |


### 5.2 Advocated Soft Delete Implementation

    -- Core column
    is_deleted BYTEINT NOT NULL DEFAULT 0
        COMMENT '0 = Active, 1 = Soft deleted'

    -- Optional: Store deletion details in Domain table
    deleted_by VARCHAR(100)
        COMMENT 'User/system that soft deleted this record'
    deleted_dts TIMESTAMP(6) WITH TIME ZONE
        COMMENT 'When this record was soft deleted'
    deleted_reason VARCHAR(500)
        COMMENT 'Reason for soft delete (GDPR, data quality, etc.)'

    -- Better: Store deletion details in Observability
    -- (see Section 7)

### 5.3 Soft Delete Operation

    -- Step 1: Close out current version
    UPDATE Party_H
    SET valid_to_dts = CURRENT_TIMESTAMP(6),
        transaction_to_dts = CURRENT_TIMESTAMP(6),
        is_current = 0
    WHERE party_id = 1001
      AND is_current = 1;

    -- Step 2: Insert soft-deleted version
    INSERT INTO Party_H (
        party_id, party_key, legal_name,
        valid_from_dts, valid_to_dts,
        transaction_from_dts, transaction_to_dts,
        is_current, is_deleted
    ) VALUES (
        1001, 'CUST-12345', 'Jane Smith',
        CURRENT_TIMESTAMP(6),  -- Deleted as of now
        TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
        CURRENT_TIMESTAMP(6),
        TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
        1,  -- is_current = 1 (this IS the current state: deleted)
        1   -- is_deleted = 1
    );

    -- Track deletion details in Observability
    INSERT INTO Observability.ChangeEvent_H (
        entity_type, entity_id, change_type,
        changed_by, changed_dts, change_reason
    ) VALUES (
        'PARTY', 1001, 'DELETE',
        'DELETE_PROCESS', CURRENT_TIMESTAMP(6), 'GDPR Right to be Forgotten'
    );

### 5.4 Querying with Soft Deletes

    -- Current active records only (most common)
    SELECT * FROM Party_H
    WHERE is_current = 1
      AND is_deleted = 0;

    -- Include deleted records
    SELECT * FROM Party_H
    WHERE is_current = 1;

    -- Only deleted records
    SELECT * FROM Party_H
    WHERE is_current = 1
      AND is_deleted = 1;

### 5.5 When Hard Deletes Are Acceptable

**Use hard deletes when:**

- No regulatory audit requirement
- No ML feature dependency
- No analytics on deletion patterns
- Storage constraints are critical
- Data truly has no future value


**Example**: Temporary staging data, test data

---

## 6. Access Layer

### 6.1 Why We Advocate Reading Through Views

**Traditional Approach**: Consumers — analysts, applications, BI
tools, agents — read tables directly, managing lock posture and
column projection in every query.

**Advocated Approach**: Tables are not the consumer surface.
Every table that is read by anything other than its load process
and DBAs is fronted by a view. Consumers read the view; the table
is private.

#### Key Benefits for AI-Native Data Products

| Concern                        | Direct table reads          | Read through views      |
| ------------------------------ | --------------------------- | ----------------------- |
| **Concurrent loads**           | ⚠️ Read can block load      | ✅ Read is non-blocking |
| **Lock posture consistency**   | ⚠️ Per-query, easy to omit  | ✅ Centralised in view  |
| **Agent discoverability**      | ⚠️ Physical schema exposed  | ✅ Stable contract      |
| **Permission management**      | ⚠️ Coupled to physical      | ✅ Decoupled            |
| **Refactoring physical layer** | ❌ Breaks every consumer    | ✅ View absorbs change  |
| **Schema documentation**       | ⚠️ Scattered                | ✅ Co-located in view   |

The view layer is the **stable contract** between physical data
and every consumer. As long as the contract holds, the underlying
table can be re-partitioned, re-indexed, re-located, or
re-modelled without breaking a single consumer. For AI-Native
Data Products specifically, this stability is what allows an
agent to learn a data product once and continue to operate
correctly as its physical implementation evolves.

### 6.2 Defer to the Object Placement Standard

This document is deliberately silent on **where** tables and
views are placed, **how** containers are named, and **how**
access is granted across them. Those decisions are governed by a
separate, layered standards system:

| Document                                                | Role                                                                                                       |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Object Placement Standard — Interface Specification** | Platform-agnostic contract. Defines the eight required sections any conforming placement standard must declare. |
| **Object Placement Standard — Platform Implementation** | A conforming implementation for a specific platform (e.g. Teradata). Declares concrete naming, separation, view-tier architecture, access model, and validation procedure. |

This document **advocates** access through views. The Object
Placement Standard **prescribes** how that access is structured
on a given platform. The split is intentional:

- **Different organisations have different conventions.** Some
  separate tables and views into distinct containers; some
  co-locate them; some apply a layered zone model. All can be
  conformant.
- **The agent contract must be portable.** An AI-Native Data
  Product agent reads a conforming Object Placement Standard
  before generating any DDL. It does not assume — it reads, it
  derives, it validates. The contract is the same shape on every
  platform; the implementation differs.
- **This document advocates patterns; the Object Placement
  Standard prescribes structure.** Conflating the two would force
  every reader to either adopt a single naming convention or
  rewrite parts of this document — neither of which is
  appropriate for an advocacy document.

#### Agent and Builder Behaviour

A data product builder, or an agent generating DDL within a data
product, **must locate a conforming Object Placement Standard
implementation before generating any object**. The Interface
Specification defines the priority order for locating it:

1. An explicit file path provided in conversation or project
   instructions
2. A skill file at a well-known path (e.g.
   `/mnt/skills/user/object-placement/SKILL.md`)
3. A file matching `Object_Placement_Standard*.md` in project
   context
4. **If none are present:** halt and ask the user

A builder must never default to a placement convention,
substitute its own assumption, or fall back to "the most common
pattern". If the standard is absent, the correct response is to
ask, not to guess.

### 6.3 What This Document Continues to Cover

The Object Placement Standard governs container structure,
naming, separation, and access. This document continues to
advocate **logical patterns** that are independent of placement:

- Bi-temporal columns and their semantics (Section 2)
- Column tiering and offload to Observability (Section 3)
- Surrogate key strategy and the Keymap pattern (Section 4)
- Soft-delete semantics (Section 5)
- Observability offload pattern (Section 7)
- Timezone handling (Section 8)
- Data quality scoring (Section 9)
- Audit trail strategy (Section 10)

These patterns are **expressed in DDL** that the Object Placement
Standard then places into the appropriate containers. The two
standards compose: this document advocates *what* a `Customer_H`
table contains; the Object Placement Standard determines *which
container* `Customer_H` and its fronting view are placed in, what
they are named, and how they are accessed.

#### Worked Example of the Composition

A `Customer_H` table designed under this document has bi-temporal
columns (Section 2), a stable surrogate from a Keymap (Section
4), and a soft-delete flag (Section 5). The Object Placement
Standard then determines:

- The container the table is placed in (e.g. a strict-separation
  Teradata implementation places it in a `_T` container)
- The container the fronting locking view is placed in (e.g. the
  matching `_V` container under strict separation, or the same
  container under co-location)
- The exact name of each container, derived from the standard's
  `derive_container()` function
- The access grants and any implied grants required by the
  separation architecture
- The validation procedure that confirms placement after
  deployment

Neither document is complete on its own. Together they describe a
fully-specified data product.

### 6.4 Why This Is Agent-Friendly

The split between *what to design* (this document) and *where to
place it* (the Object Placement Standard) is what makes the
combined system robust under agent operation. Three properties
follow:

**Portability across customers.** An agent that builds data
products for multiple customers does not carry hard-coded
placement assumptions. It carries a contract — read the
Placement Standard, call its derivation function, run its
validation procedure — and renders correctly into whatever
convention the customer has chosen.

**Stability under physical change.** A customer reorganising
their container hierarchy revises one document — their Object
Placement Standard. Every data product designed under this
document continues to apply unchanged.

**Independent evolution.** This document evolves as data
management practices evolve (new bi-temporal patterns, new
quality scoring approaches). Placement standards evolve as
platform capabilities evolve (new container types, new access
mechanisms). Neither blocks the other.

### 6.5 Reference

| Document                                                | Location                                                                                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Object Placement Standard — Interface Specification** | [`platform-standards/Object_Placement_Standard_Spec.md`](../platform-standards/Object_Placement_Standard_Spec.md) — platform-agnostic; the contract |
| **Teradata reference implementation**                   | `Object_Placement_Standard_Teradata.md` — conforming implementation for Teradata; distributed separately |

Implementations for other platforms (Snowflake, BigQuery,
Databricks, etc.) follow the same Interface Specification with
platform-appropriate constructs. Any organisation may author its
own conforming implementation that reflects local conventions.

---

## 7. Observability Offload Pattern

### 7.1 The Normalization Principle

**Problem**: Storing audit/lineage/quality data in Domain tables duplicates data across millions of rows

**Advocated Solution**: Store once in Observability module, join when needed

### 7.2 Observability Module Tables

#### ChangeEvent_H (Audit Trail)

    CREATE TABLE Observability.ChangeEvent_H (
        change_event_id     BIGINT NOT NULL,
        entity_type         VARCHAR(50) NOT NULL,  -- 'PARTY', 'PRODUCT', etc.
        entity_id          BIGINT NOT NULL,
        change_type         VARCHAR(20) NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE'
        changed_by          VARCHAR(100) NOT NULL,
        changed_dts         TIMESTAMP(6) WITH TIME ZONE NOT NULL,
        change_reason       VARCHAR(500),
        changed_columns     VARCHAR(2000),  -- JSON array of changed columns
        old_values_json     JSON,
        new_values_json     JSON,
        PRIMARY INDEX (entity_id, changed_dts)
    )
    PARTITION BY RANGE_N(
        changed_dts BETWEEN DATE '2020-01-01' AND DATE '2030-12-31'
        EACH INTERVAL '1' MONTH
    );

#### DataLineage_H (Source Tracking)

    CREATE TABLE Observability.DataLineage_H (
        lineage_id         BIGINT NOT NULL,
        entity_type         VARCHAR(50) NOT NULL,
        entity_id          BIGINT NOT NULL,
        source_system       VARCHAR(50) NOT NULL,
        source_record_id    VARCHAR(100),
        batch_id            VARCHAR(50),
        loaded_dts          TIMESTAMP(6) WITH TIME ZONE NOT NULL,
        extraction_dts      TIMESTAMP(6) WITH TIME ZONE,
        transformation_name VARCHAR(128),
        lineage_metadata_json JSON,
        PRIMARY INDEX (entity_id)
    );

#### DataQuality_H (Quality Time-Series)

    CREATE TABLE Observability.DataQuality_H (
        quality_id         BIGINT NOT NULL,
        entity_type         VARCHAR(50) NOT NULL,
        entity_id          BIGINT NOT NULL,
        evaluated_dts       TIMESTAMP(6) WITH TIME ZONE NOT NULL,
        quality_score       DECIMAL(3,2) NOT NULL,
        rule_results_json   JSON,  -- Array of {rule_id, passed, message}
        PRIMARY INDEX (entity_id, evaluated_dts)
    )
    PARTITION BY RANGE_N(
        evaluated_dts BETWEEN DATE '2024-01-01' AND DATE '2030-12-31'
        EACH INTERVAL '1' MONTH
    );

### 7.3 Two Join Approaches

#### Approach 1: Surrogate Key References (Fastest)

**Domain table includes FK to Observability:**

    CREATE TABLE Party_H (
        party_id BIGINT NOT NULL,
        -- ... core columns ...
  
        -- Optional: Direct references for performance
        change_event_id BIGINT,  -- FK to most recent ChangeEvent
        lineage_id BIGINT,       -- FK to current DataLineage
        quality_id BIGINT,       -- FK to latest DataQuality
  
        FOREIGN KEY (change_event_id)
            REFERENCES Observability.ChangeEvent_H(change_event_id),
        FOREIGN KEY (lineage_id)
            REFERENCES Observability.DataLineage_H(lineage_id),
        FOREIGN KEY (quality_id)
            REFERENCES Observability.DataQuality_H(quality_id)
    );

    -- Query: Fast direct join
    SELECT p.*, ce.changed_by, dl.source_system, dq.quality_score
    FROM Party_H p
    LEFT JOIN Observability.ChangeEvent_H ce
        ON ce.change_event_id = p.change_event_id
    LEFT JOIN Observability.DataLineage_H dl
        ON dl.lineage_id = p.lineage_id
    LEFT JOIN Observability.DataQuality_H dq
        ON dq.quality_id = p.quality_id
    WHERE p.is_current = 1;

**Overhead**: 3 BIGINT columns (24 bytes) vs 15+ columns (500+ bytes)

#### Approach 2: Join by entity_id (No FK Required)

**Domain table has NO FK, join on entity_id + entity_type:**

    CREATE TABLE Party_H (
        party_id BIGINT NOT NULL,
        -- ... core columns only (8 columns) ...
    );

    -- Query: Join by entity reference
    SELECT p.*, ce.changed_by, dl.source_system, dq.quality_score
    FROM Party_H p
    LEFT JOIN (
        SELECT entity_id, changed_by, changed_dts,
               ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY changed_dts DESC) AS rn
        FROM Observability.ChangeEvent_H
        WHERE entity_type = 'PARTY'
    ) ce ON ce.entity_id = p.party_id AND ce.rn = 1
    LEFT JOIN Observability.DataLineage_H dl
        ON dl.entity_type = 'PARTY' AND dl.entity_id = p.party_id
    LEFT JOIN (
        SELECT entity_id, quality_score, evaluated_dts,
               ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY evaluated_dts DESC) AS rn
        FROM Observability.DataQuality_H
        WHERE entity_type = 'PARTY'
    ) dq ON dq.entity_id = p.party_id AND dq.rn = 1
    WHERE p.is_current = 1;

**Overhead**: 0 additional columns, join on indexed columns

### 7.4 Pre-Joined Views for Agent Access

    -- Create view to simplify agent queries
    CREATE VIEW Party_Complete AS
    SELECT
        p.party_id, p.party_key, p.legal_name,
        p.valid_from_dts, p.valid_to_dts,
        ce.changed_by AS last_changed_by,
        ce.changed_dts AS last_changed_dts,
        ce.change_reason,
        dl.source_system,
        dl.batch_id,
        dq.quality_score,
        dq.evaluated_dts AS quality_evaluated_dts
    FROM Party_H p
    LEFT JOIN Observability.ChangeEvent_H ce
        ON ce.change_event_id = p.change_event_id  -- If using FK approach
    LEFT JOIN Observability.DataLineage_H dl
        ON dl.lineage_id = p.lineage_id
    LEFT JOIN Observability.DataQuality_H dq
        ON dq.quality_id = p.quality_id
    WHERE p.is_current = 1;

    -- Agent query (simple)
    SELECT * FROM Party_Complete WHERE party_key = 'CUST-12345';

### 7.5 Advocated Approach by Scenario

| Scenario | Recommended Approach |
| --- | --- |
| **High-volume tables (>100M rows)** | No FK, join by entity_id, use views |
| **Medium-volume (10M-100M)** | FK references for performance |
| **Low-volume (<10M)** | Either approach acceptable |
| **Agent-heavy workload** | Pre-joined views essential |
| **Storage-constrained** | No FK, offload everything |


### 7.6 Benefits Quantification

**Example: 50M row Party table**

| Approach | Domain Table Size | Join Performance | Complexity |
| --- | --- | --- | --- |
| **Traditional (all in Domain)** | ~10 GB | N/A (no join) | Low |
| **Core + FK refs** | ~6 GB | Fast (direct FK) | Medium |
| **Core only + views** | ~4 GB | Fast (indexed) | Medium |


**Storage savings**: 40-60% while maintaining query performance

---

## 8. Timezone Handling

### 8.1 Why We Advocate TIMESTAMP WITH TIME ZONE

**Problem**: Global enterprises operate across multiple timezones **Impact**: Temporal accuracy, regulatory compliance, cross-region analysis

### 8.2 Advocated Standard

**Always use `TIMESTAMP(6) WITH TIME ZONE` for all temporal columns**

    -- ADVOCATED
    valid_from_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL
    valid_to_dts        TIMESTAMP(6) WITH TIME ZONE NOT NULL
    transaction_from_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL
    transaction_to_dts   TIMESTAMP(6) WITH TIME ZONE NOT NULL

    -- NOT RECOMMENDED
    valid_from_dts      TIMESTAMP(6) NOT NULL  -- Missing timezone

### 8.3 Default Values with Timezone

    -- Always include timezone in defaults
    DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00'  -- UTC

    -- NOT
    DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999'  -- Ambiguous

### 8.4 Timezone Best Practices

| Practice | Recommendation |
| --- | --- |
| **Storage** | Always store in UTC (+00:00) |
| **Display** | Convert to user's local timezone in application |
| **Defaults** | Use UTC for all default timestamps |
| **Queries** | Include explicit timezone in literals |
| **Comparison** | Database handles timezone conversion automatically |


### 8.5 Query Examples with Timezone

    -- Correct: Explicit timezone
    SELECT * FROM Party_H
    WHERE valid_from_dts >= TIMESTAMP '2024-01-01 00:00:00+00:00'
      AND valid_from_dts < TIMESTAMP '2024-02-01 00:00:00+00:00';

    -- Also correct: Database will convert to UTC
    SELECT * FROM Party_H
    WHERE valid_from_dts >= TIMESTAMP '2024-01-01 00:00:00-05:00'  -- EST
      AND valid_from_dts < TIMESTAMP '2024-02-01 00:00:00-05:00';

    -- Convert to different timezone for display
    SELECT party_key,
           valid_from_dts AT TIME ZONE 'America/New_York' AS valid_from_est,
           valid_from_dts AT TIME ZONE 'Europe/London' AS valid_from_gmt
    FROM Party_H;

### 8.6 When TIMESTAMP (without timezone) Is Acceptable

**Use TIMESTAMP without timezone only when:**

- Data is purely local (single timezone, will never expand)
- Regulatory requirement for specific timezone
- Legacy system compatibility required


**Document the timezone assumption explicitly**

---

## 9. Data Quality Management

### 9.1 Advocated Quality Scoring Approach

**Principle**: Agents need to assess data reliability before using it

### 9.2 Quality Score Calculation

**Advocated**: 0.00-1.00 score based on validation rules

    -- Example: Party quality score
    quality_score = (
        CASE WHEN legal_name IS NOT NULL THEN 0.20 ELSE 0 END +
        CASE WHEN tax_identifier IS NOT NULL THEN 0.20 ELSE 0 END +
        CASE WHEN email_address IS NOT NULL AND email_validated = 1 THEN 0.20 ELSE 0 END +
        CASE WHEN phone_number IS NOT NULL AND phone_validated = 1 THEN 0.20 ELSE 0 END +
        CASE WHEN address_complete = 1 THEN 0.20 ELSE 0 END
    )

### 9.3 Two Storage Approaches

#### Approach 1: Store Latest Score in Domain (Extended Column)

    CREATE TABLE Party_H (
        -- ... core columns ...
        data_quality_score DECIMAL(3,2)
            COMMENT 'Quality score 0.00-1.00 based on validation rules',
        -- ...
    );

    -- Agent query
    SELECT party_key, legal_name, data_quality_score
    FROM Party_H
    WHERE is_current = 1
      AND data_quality_score >= 0.75;  -- High quality only

**Pros**: Simple, fast single-table queries **Cons**: Only latest score, no history, adds column overhead

#### Approach 2: Store in Observability (Advocated)

    -- Store quality time-series in Observability
    INSERT INTO Observability.DataQuality_H (
        entity_type, entity_id, evaluated_dts, quality_score,
        rule_results_json
    ) VALUES (
        'PARTY', 1001, CURRENT_TIMESTAMP(6), 0.80,
        JSON '{"rules": [
            {"rule_id": "R01", "rule_name": "has_legal_name", "passed": true},
            {"rule_id": "R02", "rule_name": "has_tax_id", "passed": true},
            {"rule_id": "R03", "rule_name": "has_email", "passed": true},
            {"rule_id": "R04", "rule_name": "has_phone", "passed": false}
        ]}'
    );

    -- Agent query with quality filter
    SELECT p.party_key, p.legal_name, dq.quality_score
    FROM Party_H p
    INNER JOIN (
        SELECT entity_id, quality_score,
               ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY evaluated_dts DESC) AS rn
        FROM Observability.DataQuality_H
        WHERE entity_type = 'PARTY'
    ) dq ON dq.entity_id = p.party_id AND dq.rn = 1
    WHERE p.is_current = 1
      AND dq.quality_score >= 0.75;

**Pros**: No Domain overhead, quality history, detailed rule results **Cons**: Requires join (mitigated by views)

### 9.4 Advocated: Use Views for Agent Access

    CREATE VIEW Party_HighQuality AS
    SELECT p.party_id, p.party_key, p.legal_name,
           dq.quality_score, dq.evaluated_dts,
           dq.rule_results_json
    FROM Party_H p
    INNER JOIN (
        SELECT entity_id, quality_score, evaluated_dts, rule_results_json,
               ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY evaluated_dts DESC) AS rn
        FROM Observability.DataQuality_H
        WHERE entity_type = 'PARTY'
    ) dq ON dq.entity_id = p.party_id AND dq.rn = 1
    WHERE p.is_current = 1
      AND p.is_deleted = 0
      AND dq.quality_score >= 0.75;

    -- Agent query (simple)
    SELECT * FROM Party_HighQuality WHERE party_key = 'CUST-12345';

### 9.5 Quality Rule Framework

**Advocated**: Standard rule categories

| Rule Category | Examples | Weight |
| --- | --- | --- |
| **Completeness** | Required fields populated | 30% |
| **Validity** | Format validation, range checks | 25% |
| **Consistency** | Cross-field validation | 20% |
| **Accuracy** | Third-party verification | 15% |
| **Timeliness** | Data freshness | 10% |

---

## 10. Audit Trail Strategy

### 10.1 Why Comprehensive Audit Trails

**Regulatory**: GDPR, CCPA, SOX, HIPAA require audit trails **Explainability**: "Why did the model predict X?" requires historical context **Security**: Detect unauthorized changes **Debugging**: Trace data lineage and transformations

### 10.2 Advocated Audit Approach

**Store detailed audit in Observability.ChangeEvent_H**

    CREATE TABLE Observability.ChangeEvent_H (
        change_event_id    BIGINT NOT NULL,
        entity_type         VARCHAR(50) NOT NULL,
        entity_id          BIGINT NOT NULL,
        change_type         VARCHAR(20) NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE'
  
        -- Who and when
        changed_by          VARCHAR(100) NOT NULL,
        changed_dts         TIMESTAMP(6) WITH TIME ZONE NOT NULL,
  
        -- What and why
        change_reason       VARCHAR(500),
        changed_columns     VARCHAR(2000),  -- JSON array: ["legal_name", "email"]
  
        -- Before and after
        old_values_json     JSON,  -- {legal_name: "Jane Doe", email: "old@..."}
        new_values_json     JSON,  -- {legal_name: "Jane Smith", email: "new@..."}
  
        -- Context
        session_id          VARCHAR(100),
        application_name VARCHAR(128),
        ip_address          VARCHAR(50),
  
        PRIMARY INDEX (entity_id, changed_dts)
    )
    PARTITION BY RANGE_N(
        changed_dts BETWEEN DATE '2020-01-01' AND DATE '2030-12-31'
        EACH INTERVAL '1' MONTH
    );

### 10.3 Capturing Change Events

    -- Example: Capture UPDATE event
    INSERT INTO Observability.ChangeEvent_H (
        change_event_id, entity_type, entity_id, change_type,
        changed_by, changed_dts, change_reason,
        changed_columns, old_values_json, new_values_json
    )
    SELECT
        change_event_seq.NEXTVAL,
        'PARTY',
        1001,
        'UPDATE',
        'data_steward@company.com',
        CURRENT_TIMESTAMP(6),
        'Customer name change due to marriage',
        JSON '["legal_name"]',
        JSON '{"legal_name": "Jane Doe"}',
        JSON '{"legal_name": "Jane Smith"}';

### 10.4 Audit Trail Queries

    -- Complete audit history for an entity
    SELECT
        changed_dts,
        changed_by,
        change_type,
        change_reason,
        changed_columns,
        old_values_json,
        new_values_json
    FROM Observability.ChangeEvent_H
    WHERE entity_type = 'PARTY'
      AND entity_id = 1001
    ORDER BY changed_dts;

    -- Who deleted this record and why?
    SELECT changed_by, changed_dts, change_reason
    FROM Observability.ChangeEvent_H
    WHERE entity_type = 'PARTY'
      AND entity_id = 1001
      AND change_type = 'DELETE'
    ORDER BY changed_dts DESC
    LIMIT 1;

    -- All changes by a specific user
    SELECT entity_type, entity_id, change_type, changed_dts
    FROM Observability.ChangeEvent_H
    WHERE changed_by = 'data_steward@company.com'
      AND changed_dts >= CURRENT_DATE - 30
    ORDER BY changed_dts DESC;

### 10.5 Retention Policy

**Advocated retention periods:**

| Audit Data Type | Retention | Rationale |
| --- | --- | --- |
| **Recent changes** | 2 years online | Active investigations |
| **Historical changes** | 7 years archived | Regulatory compliance |
| **Deletion records** | 10 years archived | GDPR accountability |
| **High-risk entities** | Indefinite | Fraud, AML compliance |

---

## 11. Platform Implementation Guidance: Teradata

> **Platform Profile — Teradata** This section is the reference Platform Profile for Teradata implementations of the AI-Native Data Product standard. The structural requirements in the module design standards are platform-agnostic; the guidance below is Teradata-specific. Teams implementing on other platforms should produce an equivalent Platform Profile for their target, covering the same topics: physical key strategy, partitioning, indexing, statistics collection, compression, and query optimisation.

### 11.1 Why Physical Design Matters for AI Workloads

AI-Native workloads have different access patterns than traditional BI:

- Point-in-time feature computation (temporal queries)
- High-volume batch processing (ML training)
- Low-latency single-row lookups (agent queries)
- Cross-module joins (enriched context)


**Advocated approach**: Design physical structures for these specific patterns.

### 11.2 Primary Index Selection

**Primary Index (PI) is the most critical physical design decision in Teradata.**

#### Advocated PI Selection by Entity Type

| Entity Type | Advocated PI | Rationale |
| --- | --- | --- |
| **Core entities** | Surrogate key (UPI) | Even distribution, simple joins |
| **High-volume entities** | Consider natural key (NUPI) | If frequently queried by business ID |
| **Reference data** | Code (UPI) | Code lookups most common |
| **Relationship tables** | Composite FK (NUPI) | Co-locate with parent entity |
| **Time-series entities** | Composite: entity + time (NUPI) | Partition elimination benefits |


#### PI Selection Decision Tree

    START: What is primary access pattern?
    ├─ Single-row lookup by surrogate key?
    │  └─ Use surrogate key UPI ✅
    ├─ Single-row lookup by natural key?
    │  └─ Use natural key UPI ✅
    ├─ Range queries on time + entity?
    │  └─ Use composite (entity_id, time_column) NUPI ✅
    ├─ Frequent joins to parent entity?
    │  └─ Use parent FK for co-location NUPI ✅
    └─ Mixed patterns?
       └─ Use surrogate key UPI + secondary indexes ✅

#### PI Examples

    -- Pattern 1: Surrogate key UPI (most common)
    CREATE TABLE Party_H (
        party_id BIGINT NOT NULL,
        -- ... columns ...
        PRIMARY INDEX (party_id)
    )
    UNIQUE PRIMARY INDEX (party_id, valid_from_dts, transaction_from_dts);

    -- Pattern 2: Natural key UPI (frequent business ID queries)
    CREATE TABLE Product_H (
        product_id BIGINT NOT NULL,
        product_key VARCHAR(50) NOT NULL,
        -- ... columns ...
        PRIMARY INDEX (product_key)  -- If most queries filter on product_key
    )
    UNIQUE PRIMARY INDEX (product_id, valid_from_dts, transaction_from_dts);

    -- Pattern 3: Composite NUPI (relationship table, co-located)
    CREATE TABLE PartyProduct_H (
        party_product_id BIGINT NOT NULL,
        party_id BIGINT NOT NULL,
        product_id BIGINT NOT NULL,
        -- ... columns ...
        PRIMARY INDEX (party_id, product_id)  -- Co-locate with Party
    )
    UNIQUE PRIMARY INDEX (party_product_id, valid_from_dts, transaction_from_dts);

    -- Pattern 4: Time-based composite (time-series data)
    CREATE TABLE Transaction_H (
        transaction_id BIGINT NOT NULL,
        party_id BIGINT NOT NULL,
        transaction_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
        -- ... columns ...
        PRIMARY INDEX (party_id, transaction_dts)  -- Time-series queries
    )
    UNIQUE PRIMARY INDEX (transaction_id, valid_from_dts, transaction_from_dts)
    PARTITION BY RANGE_N(
        transaction_dts BETWEEN DATE '2020-01-01' AND DATE '2030-12-31'
        EACH INTERVAL '1' MONTH
    );

### 11.3 Partitioning Strategy

**Advocate partitioning for:**

- Tables > 100M rows
- Time-series access patterns
- Need for partition elimination


#### Advocated Partitioning Approaches

| Partitioning Dimension | When to Use | Example |
| --- | --- | --- |
| **Transaction time** | Most common - queries filter on load/update date | `transaction_from_dts` |
| **Valid time** | Business queries filter on effective date | `valid_from_dts` |
| **Date attribute** | Event data with natural dates | `transaction_date`, `order_date` |
| **Multi-level** | Combine time + status/type | Time + is_deleted |


#### Partitioning Examples

    -- Pattern 1: Monthly partitioning (most common)
    PARTITION BY RANGE_N(
        transaction_from_dts BETWEEN DATE '2020-01-01'
                               AND DATE '2030-12-31'
                               EACH INTERVAL '1' MONTH
    );

    -- Pattern 2: Quarterly partitioning (moderate volume)
    PARTITION BY RANGE_N(
        transaction_from_dts BETWEEN DATE '2020-01-01'
                               AND DATE '2030-12-31'
                               EACH INTERVAL '3' MONTH
    );

    -- Pattern 3: Daily partitioning (very high volume)
    PARTITION BY RANGE_N(
        transaction_dts BETWEEN DATE '2024-01-01'
                          AND DATE '2025-12-31'
                          EACH INTERVAL '1' DAY
    );

    -- Pattern 4: Multi-level (time + status)
    PARTITION BY (
        RANGE_N(
            valid_from_dts BETWEEN DATE '2020-01-01'
                            AND DATE '2030-12-31'
                            EACH INTERVAL '1' YEAR
        ),
        CASE_N(
            is_deleted = 0,   -- Partition 1: Active
            is_deleted = 1,   -- Partition 2: Deleted
            UNKNOWN           -- Partition 3: NULL
        )
    );

#### Partitioning Decision Tree

    START: Table size?
    ├─ < 100M rows → No partitioning needed ⚠️
    └─ > 100M rows → What's primary query pattern?
       ├─ Time range queries common?
       │  └─ Partition by time column ✅
       ├─ Status/type filtering common?
       │  └─ Consider multi-level partitioning ✅
       └─ Full table scans anyway?
          └─ Partitioning won't help ⚠️

### 11.4 Secondary Index Strategy

**Advocate selective use of secondary indexes.**

#### When to Create Secondary Indexes

| Create SI When: | Avoid SI When: |
| --- | --- |
| ✅ Critical query doesn't use PI | ❌ Query is rare/ad-hoc |
| ✅ Query performance unacceptable | ❌ PI already covers query |
| ✅ Insert volume is moderate | ❌ High insert/update volume |
| ✅ Query is frequent | ❌ Query is already fast |


#### Advocated Secondary Index Patterns

    -- Pattern 1: Natural key index (when PI is surrogate key)
    CREATE UNIQUE INDEX idx_party_natural_key
    ON Party_H (party_key)
    WHERE is_current = 1 AND is_deleted = 0;

    -- Pattern 2: Foreign key index (for join optimization)
    CREATE INDEX idx_partyproduct_product
    ON PartyProduct_H (product_id)
    WHERE is_current = 1 AND is_deleted = 0;

    -- Pattern 3: Composite index (multi-column filters)
    CREATE INDEX idx_product_category_type
    ON Product_H (product_category, product_type_code)
    WHERE is_current = 1 AND is_deleted = 0;

    -- Pattern 4: Covering index (include frequently selected columns)
    CREATE INDEX idx_party_lookup (party_key, legal_name, status_code)
    ON Party_H (party_key)
    WHERE is_current = 1 AND is_deleted = 0;

### 11.5 Join Index Strategy

**Advocate join indexes for:**

- Expensive joins used frequently
- Pre-computed aggregations
- Materialized views


#### Join Index Patterns

    -- Pattern 1: Current version materialized view
    CREATE JOIN INDEX jidx_party_current AS
    SELECT
        party_id,
        party_key,
        legal_name,
        party_type_code,
        status_code
    FROM Party_H
    WHERE is_current = 1
      AND is_deleted = 0
      AND transaction_to_dts = TIMESTAMP '9999-12-31 23:59:59.999999+00:00'
    PRIMARY INDEX (party_id);

    -- Pattern 2: Denormalized join (frequent join pattern)
    CREATE JOIN INDEX jidx_party_product_denorm AS
    SELECT
        p.party_id,
        p.party_key,
        p.legal_name,
        pp.product_id,
        pr.product_key,
        pr.product_name
    FROM Party_H p
    INNER JOIN PartyProduct_H pp
        ON p.party_id = pp.party_id
    INNER JOIN Product_H pr
        ON pp.product_id = pr.product_id
    WHERE p.is_current = 1 AND p.is_deleted = 0
      AND pp.is_current = 1 AND pp.is_deleted = 0
      AND pr.is_current = 1 AND pr.is_deleted = 0
    PRIMARY INDEX (party_id);

    -- Pattern 3: Pre-computed aggregation
    CREATE JOIN INDEX jidx_party_metrics AS
    SELECT
        party_id,
        COUNT(*) AS product_cnt,
        SUM(balance_amt) AS total_balance_amt,
        MAX(last_transaction_dts) AS last_activity_dts
    FROM Party_H p
    INNER JOIN PartyProduct_H pp ON p.party_id = pp.party_id
    WHERE p.is_current = 1 AND p.is_deleted = 0
      AND pp.is_current = 1 AND pp.is_deleted = 0
    GROUP BY party_id
    PRIMARY INDEX (party_id);

### 11.6 Compression Strategy

**Advocate compression for large text columns.**

#### Compression Candidates

| Column Type | Compress? | Method |
| --- | --- | --- |
| **Large text (>500 chars)** | ✅ Yes | AUTO COMPRESS |
| **JSON columns** | ✅ Yes | AUTO COMPRESS or ZLIB |
| **Sparse columns** | ✅ Yes | AUTO COMPRESS |
| **Small strings (<50 chars)** | ❌ No | Overhead exceeds benefit |
| **Numeric columns** | ❌ No | Minimal benefit |
| **Frequently updated** | ⚠️ Caution | Recompression cost |


#### Compression Examples

    -- Pattern 1: AUTO COMPRESS (recommended)
    CREATE TABLE Party_H (
        party_id BIGINT NOT NULL,
        -- ... other columns ...
        notes_txt VARCHAR(5000),
        address_text VARCHAR(500)
    )
    WITH COLUMN_PARTITION = (
        AUTO COMPRESS (notes_txt, address_text)
    );

    -- Pattern 2: Specific algorithm for very large text
    CREATE TABLE Document_H (
        document_id BIGINT NOT NULL,
        document_content CLOB
    )
    WITH COLUMN_PARTITION = (
        COLUMN (document_content) COMPRESS USING ZLIBHIGH
    );

### 11.7 Statistics Collection

**Advocate automated statistics collection.**

#### Statistics Strategy

    -- Collect stats on critical columns
    COLLECT STATISTICS
    COLUMN (party_id),
    COLUMN (party_key),
    COLUMN (party_type_code),
    COLUMN (is_current),
    COLUMN (is_deleted),
    COLUMN (valid_from_dts),
    COLUMN (transaction_from_dts)
    ON Party_H;

    -- Collect stats on composite filters
    COLLECT STATISTICS
    COLUMN (party_type_code, is_current, is_deleted)
    ON Party_H;

    -- For large tables, use sampling
    COLLECT STATISTICS ON Party_H USING SAMPLE 10 PERCENT;

#### Advocated Collection Schedule

| Table Size | Frequency | Method |
| --- | --- | --- |
| **< 1M rows** | After major loads | Full scan |
| **1M - 100M rows** | Daily | 10% sample |
| **> 100M rows** | Weekly | 5% sample |
| **Reference tables** | After changes only | Full scan |


### 11.8 Physical Design Checklist

**Before implementation:**

- [ ] Primary Index chosen and justified
- [ ] Partitioning strategy defined (if applicable)
- [ ] Secondary indexes planned with rationale
- [ ] Join indexes considered for expensive patterns
- [ ] Compression strategy defined for large columns
- [ ] Statistics collection automated
- [ ] Query patterns tested against physical design
- [ ] Storage estimates calculated
- [ ] Performance benchmarks established

---

## 12. Implementation Decision Trees

### 12.1 Temporal Pattern Decision

    START: Do you need point-in-time correctness for ML features?
    ├─ YES → Are late-arriving facts common?
    │  ├─ YES → Use BI-TEMPORAL ✅ (Advocated)
    │  └─ NO → Are corrections needed?
    │     ├─ YES → Use BI-TEMPORAL ✅
    │     └─ NO → Type 2 SCD acceptable ⚠️
    └─ NO → Is complete audit trail required?
       ├─ YES → Use BI-TEMPORAL ✅
       └─ NO → Type 2 SCD acceptable ⚠️

### 12.2 Column Strategy Decision

    START: What is table volume?
    ├─ < 10M rows → Core + Extended OK ⚠️
    ├─ 10M - 100M rows → Core + FK Refs ✅ (Advocated)
    └─ > 100M rows → Core Only + Views ✅ (Advocated)
        │
        ├─ Need fast audit access?
        │  ├─ YES → Add change_event_id FK
        │  └─ NO → Join by entity_id (no FK)
        │
        ├─ Need fast lineage access?
        │  ├─ YES → Add lineage_id FK
        │  └─ NO → Join by entity_id (no FK)
        │
        └─ Need fast quality access?
           ├─ YES → Add quality_id FK
           └─ NO → Join by entity_id (no FK)

### 12.3 Delete Strategy Decision

    START: Is regulatory audit trail required?
    ├─ YES → SOFT DELETE ✅ (Advocated)
    └─ NO → Do ML features depend on deletion status?
       ├─ YES → SOFT DELETE ✅
       └─ NO → Need analytics on deletion patterns?
          ├─ YES → SOFT DELETE ✅
          └─ NO → Is storage extremely constrained?
             ├─ YES → Hard delete acceptable ⚠️
             └─ NO → SOFT DELETE ✅ (safest default)

### 12.4 Quality Storage Decision

    START: What is table volume?
    ├─ < 10M rows → Either approach OK
    │  ├─ Simple implementation priority? → Store in Domain ⚠️
    │  └─ Quality history needed? → Store in Observability ✅
    └─ > 10M rows → Store in Observability ✅ (Advocated)
        │
        └─ Create views for agent access? → YES ✅ (Always)

---

## Document Change Log

| Version | Date | Changes | Author |
| --- | --- | --- | --- |
| 1.6 | 2026-05-08 | Added Section 6 (Access Layer). Defers placement, naming, separation, and access to the Object Placement Standard (interface specification + platform implementations). Establishes the principle of reading through views without prescribing where tables and views are placed. Lists builder/agent behaviour: locate a conforming Object Placement Standard before generating any object; halt and ask if absent. Sections 6–11 renumbered to 7–12. Subsection numbers within the renumbered Implementation Decision Trees corrected from 11.1–11.4 to 12.1–12.4. | Paul Dancer, Worldwide Field Tech, Teradata |
| 1.5 | 2026-04-15 | Established platform neutrality. Renamed Section 10 from "Physical Design for Teradata" to "Platform Implementation Guidance: Teradata" and added a Platform Profile preamble making explicit that this section is Teradata-specific and that other platforms should produce equivalent profiles. Section 10 content unchanged. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.4 | 2026-04-10 | Section 4 (Surrogate Key Strategy) rewritten to address surrogate key instability in SCD Type 2 tables (issue #7). Added Section 4.2 explaining why IDENTITY on _H tables fails; Section 4.3 documenting the recommended Keymap pattern (with flexibility note that organisations should use their own standard if one exists); Section 4.4 (Reference and Lookup Table Exemption) clarifying that reference/lookup tables and detail entities not FK-referenced may use IDENTITY directly; Section 4.5 providing a decision tree with three allocation options; Section 4.6 (natural keys, renamed from old 4.4). Removed old Sections 4.2-4.3 which incorrectly advocated IDENTITY on _H tables. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.3 | 2026-03-20 | Completed swap of id and key to be consistent throughout design standards | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.2 | 2026-03-18 | Renamed is_current_version → is_current throughout, aligned with Domain Module Design Standard naming convention | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.1 | 2026-03-17 | Updated naming convention throughout: {entity}_id = Surrogate Key (BIGINT), {entity}_key = Natural Business Key (VARCHAR), aligned with Domain Module Design Standard v2.1 | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.0 | 2025-02-09 | Initial Advocated Data Management Standards | Data Architecture |

---

**End of Advocated Data Management Standards**

*These are RECOMMENDED practices based on Teradata's 30+ years of enterprise data management experience. Adapt to your context and constraints. Document deviations and rationale.*
