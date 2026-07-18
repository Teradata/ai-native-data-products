# AI-Native Data Product - Master Design Standard

**Version:** 2.1  
**Date:** 2026-05-07  
**Document Type:** Design Standard / Reusable Template  
**Purpose:** Define the architectural blueprint and design standards for modular, AI-native data products optimized for agentic consumption

---

## Executive Summary

This document defines **design standards** for AI-native data products - a reusable template for building multiple data products with consistency, repeatability, and alignment to best practices. This is NOT a specific data product implementation, but rather the **standard patterns, principles, and structures** that all data products should follow.

The architecture enables progressive enhancement - starting with traditional data models and adding AI-native capabilities incrementally. All modules co-locate on the deployment platform, enabling efficient joins to source data without duplication.

### How to Use This Standard

**For Design Teams:**
1. Use this Master Design Standard as the foundation for ALL data product designs
2. Reference Module Design Standards (Domain, Search, Prediction, etc.) for detailed patterns
3. Apply these standards when designing specific data products (Customer 360, Fraud Detection, etc.)
4. Customize only where business requirements demand deviation from standards

**Documentation Hierarchy:**
```
LAYER 1: DESIGN STANDARDS (This Document + Module Standards)
├── Master Design Standard ← You are here
├── Access Layer Design Standard (roles, grants, deployment timing)
└── Module Design Standards (6 documents - created separately)
    ├── Domain/Subject Data Design Standard
    ├── Search Module Design Standard
    ├── Prediction Module Design Standard
    ├── Observability Module Design Standard
    ├── Semantic Module Design Standard
    └── Memory Module Design Standard
        └── Section 8: Documentation Sub-Module
            Covers: Module_Registry, Design_Decision, Business_Glossary,
            Query_Cookbook, Implementation_Note, Change_Log
            (co-located in {ProductName}_Memory database)

NOTE: Documentation is not a standalone module. The documentation tables
(design memory) are defined in the Memory Module Design Standard (Section 8)
and deployed as part of the Memory module for each data product.

LAYER 2: ACTUAL DATA PRODUCT DESIGNS (Apply Standards)
├── Customer 360 Data Product (uses standards above)
├── Fraud Detection Data Product (uses standards above)
└── [Any other data product...]
```

This standards-based approach ensures **repeatability** (build products faster), **consistency** (all products work the same way), **quality** (best practices baked in), and **interoperability** (products integrate easily).

---

## Understanding Design Standards vs. Implementations

### What This Document IS
✅ **Reusable Template** - Standard patterns applicable to any data product  
✅ **Best Practice Guide** - Proven approaches for AI-native design  
✅ **Consistency Framework** - Ensures all data products follow same principles  
✅ **Integration Blueprint** - How modules connect regardless of use case  
✅ **Quality Baseline** - Incorporates industry standards and Teradata optimizations

### What This Document IS NOT
❌ **Specific Implementation** - Not the schema for Customer 360 or any particular product  
❌ **Complete Specification** - Requires Module Design Standards for full detail  
❌ **Prescriptive Requirements** - Allows customization for business needs  
❌ **Final DDL** - Provides patterns, not production-ready code

### Standard Components vs. Product-Specific Elements

| Standard (Reusable) | Product-Specific (Varies) |
|---------------------|---------------------------|
| 6 module architecture | Which modules to implement |
| Integration patterns | Actual entity names |
| Table naming conventions | Database names |
| PI selection principles | Specific PI choices |
| Temporal patterns (Type 2 SCD) | Which entities need history |
| Standard audit columns | Business-specific attributes |
| Industry reference models (FIBO, BIAN) | How to apply them |

### Benefits of Standards-Based Design

**Repeatability**: Design new products 3-5x faster using proven templates  
**Consistency**: All products "look and feel" the same - easier integration  
**Quality**: Industry best practices and Teradata optimizations built-in  
**Governance**: Standard patterns simplify compliance and audit  
**Interoperability**: Products built on same foundation integrate easily  
**Knowledge Transfer**: Teams learn standards once, apply everywhere  
**Evolution**: Update standards, benefit all products simultaneously

---

## Design Vision & Principles

### Core Vision
Create data products that agents can **discover, understand, and consume autonomously** - moving from human-mediated data access to agent-native data platforms.

### Guiding Principles

1. **Modularity First**: Each module is independently deployable and composable
2. **Progressive Enhancement**: Start with traditional models, add AI capabilities incrementally
3. **Zero Data Duplication**: Leverage platform co-location — join to source data instead of copying
4. **Self-Describing**: Data products expose their own semantics, contracts, and relationships
5. **Agent-Native Design**: Optimize for machine interpretation, not just human readability
6. **Standards-Driven**: Use Knowledge Stores to ensure consistency and compliance
7. **Platform-Neutral Design**: The structural standards defined here are platform-agnostic. DDL examples throughout the module design standards use Teradata syntax as the reference implementation. Teams deploying on other platforms should adapt the DDL syntax while preserving the structural intent. Platform-specific implementation guidance is captured in Platform Profiles (see Platform Profiles section).

---

## Architecture Overview

### The Six Core Modules

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI-Native Data Product                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Domain/    │  │    Search    │  │  Prediction  │          │
│  │   Subject    │  │   (Vector    │  │   (Feature   │          │
│  │     Data     │  │  Embeddings) │  │    Store)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │Observability │  │   Semantic   │  │    Memory    │          │
│  │  (Feedback & │  │  (Knowledge  │  │ (Agent State,│          │
│  │    Events)   │  │   & Meaning) │  │Learning & Doc│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
    ┌────┴────┐          ┌────┴────┐         ┌────┴────┐
    │ Agent A │          │ Agent B │         │ Agent C │
    └─────────┘          └─────────┘         └─────────┘
```

---

## Module Definitions

### 1. Domain/Subject Data
**Purpose:** Core business entities, relationships, and foundational data structures

**Scope:**
- Traditional data models (3NF, dimensional, Data Vault, etc.)
- Core business entities and their relationships
- Master data and reference data (canonical examples, "golden records")
- Temporal structures: Type 2 SCD, point-in-time snapshots, state transitions
- Event logs and state change history

**Key Characteristics:**
- Source of truth for business entities
- Optimized for both transactional and analytical patterns
- Maintains full history for temporal reasoning
- Provides "base layer" that other modules enhance

**Integration Points:**
- All other modules join back to Domain entities
- Search module embeds Domain entities
- Feature Store derives features from Domain data
- Semantic module describes Domain schema, relationships and meaning

---

### 2. Search (Vector Embeddings & Similarity Search)
**Purpose:** Enable semantic search and similarity-based retrieval for both structured and unstructured data

**Scope:**
- Vector embeddings for text, documents, images, structured records
- Similarity search indexes (vector databases, HNSW indexes)
- Pre-computed embeddings for frequently accessed entities
- Multi-modal embedding strategies

**Key Characteristics:**
- Enables "find things like this" queries
- Supports RAG (Retrieval Augmented Generation) patterns
- Handles both exact and fuzzy matching
- Optimized for high-dimensional vector operations

**Integration Points:**
- Embeds entities from Domain/Subject Data
- Provides context for Prediction module
- Feeds Memory module with relevant historical context
- Leverages Semantic module for embedding strategy

---

### 3. Prediction (Feature Store)
**Purpose:** Engineered features, ML model inputs/outputs, and training data for predictive analytics

**Scope:**
- Pre-computed features for ML models
- Feature metadata: lineage, versioning, freshness, dependencies
- Training datasets and validation sets
- Model predictions and confidence scores
- Few-shot learning examples with labeled outcomes
- Historical feature values for point-in-time consistency

**Key Characteristics:**
- Time-travel capable (historical feature reconstruction)
- Self-documenting features with semantic meaning
- Optimized for both training and inference
- Supports online and batch feature serving

**Integration Points:**
- Derives features from Domain/Subject Data
- Uses Search for feature discovery
- Logs performance in Observability module
- Described in Semantic module (feature semantics)

---

### 4. Observability (Feedback & Events)
**Purpose:** Monitor data product health, track agent interactions, and capture outcomes for continuous improvement

**Scope:**
- Data quality metrics and monitoring
- Agent interaction logs (queries, actions, decisions)
- Feedback and corrections (human-in-the-loop)
- Outcome tracking (did predictions work? did searches help?)
- Performance metrics (latency, accuracy, resource usage)
- Event streams (what happened, when, why)
- Anomaly detection and alerting

**Key Characteristics:**
- Real-time and historical monitoring
- Enables closed-loop learning
- Provides audit trail for agent decisions
- Supports A/B testing and experimentation

**Integration Points:**
- Monitors all other modules
- Feeds Memory module (what worked/didn't work)
- Informs Feature Store (feature drift, importance)
- Can update Semantic metadata based on observed patterns

---

### 5. Semantic (Knowledge & Meaning)
**Purpose:** Capture the meaning of data, relationships between entities, and rules that govern the domain

**Scope:**
- **Table-Level Relationship Metadata**: Foreign key definitions, join patterns, cardinality
- **Entity Schema Metadata**: What tables exist, where they are located, how to query them
- **Column Metadata**: Column meanings, data classifications (PII, sensitive), validation rules
- **Naming Conventions**: Documented standards for agent interpretation (suffixes, prefixes, abbreviations)
- **Ontologies & Taxonomies**: Concept hierarchies and controlled vocabularies
- **Business Rules** (Optional): Validation rules, derivation formulas, constraints
- **Data Contracts** (Optional): Interfaces between data products (use open standards: ODCS, datacontract.com)
- **Multi-Hop Path Discovery**: Enables agents to discover indirect join paths between tables

**Key Characteristics:**
- Machine-readable semantics stored as queryable SQL tables (not just documentation)
- Multi-format support (SQL tables, JSON for flexible data)
- Versioned and evolving
- Enables autonomous agent reasoning and SQL generation
- Bidirectional relationship traversal (multi-hop path discovery)

**Integration Points:**
- Describes all other modules
- Enables Search to understand context
- Defines Feature Store semantics
- Provides rules for Memory module reasoning
- Core enabler for agent autonomy

---

### 6. Memory (Agent State, Learning & Documentation)
**Purpose:** Enable agents to learn, remember, and collaborate across sessions and users. Also serves as the host for the Documentation Sub-Module — a shared knowledge repository capturing design decisions, business glossary terms, query patterns, and change history across all data products.

**Scope:**
- Conversation history and decision logs
- Agent preferences and learned strategies
- User/stakeholder preferences and context
- Session state and environment metadata
- Cross-agent shared learnings (patterns discovered, strategies tested)
- Situational context (market conditions, operational state)
- Long-term patterns and insights
- **Documentation Sub-Module** (design memory, co-located in `{ProductName}_Memory`):
  - `Module_Registry` — version registry for all modules in this data product
  - `Design_Decision` — Architecture Decision Records with version chain
  - `Business_Glossary` — domain term definitions for this data product
  - `Query_Cookbook` — proven, reusable query patterns
  - `Implementation_Note` — operational knowledge and known issues
  - `Change_Log` — versioned change history per module

**Key Characteristics:**
- Persistent across sessions
- Shared across agent instances
- Privacy-aware and scoped appropriately
- Enables meta-learning (learning how to learn)
- Documentation tables are co-located in the Memory database — the data product is fully self-contained

**Integration Points:**
- Learns from Observability module outcomes
- Uses Search to find relevant historical context
- Applies Semantic rules to reason about past decisions
- Informs Feature Store (what features were useful)
- References Domain data for entity continuity
- Receives documentation captures from every other module (Domain, Semantic, Search, Prediction, Observability) during their design workflow

---

## Knowledge Stores for Design Guidance

### Concept
**Knowledge Stores** contain design-time knowledge that guides HOW to build the data product - separate from the runtime knowledge ABOUT the data product (which lives in the Semantic module).

### Two Layers of Knowledge

| Layer | Purpose | Consumers | Examples |
|-------|---------|-----------|----------|
| **Design-Time Knowledge** | Guide data product construction | Data architects, designers, LLMs building schemas | Modeling standards, naming conventions, industry models |
| **Runtime Knowledge** | Describe the data product itself | Agents consuming the data | Data contracts, entity relationships, business rules |

### Types of Knowledge Stores

**1. Data Modeling Standards**
- Normalization approaches (3NF, dimensional, Data Vault, anchor modeling)
- Naming conventions (table prefixes, column suffixes, abbreviations)
- Teradata-specific patterns (PI selection, indexing strategies, join optimization)
- Documentation standards and metadata requirements

**2. Industry Reference Models**
- Financial Services: FIBO (Financial Industry Business Ontology), BIAN
- Healthcare: HL7 FHIR, OMOP Common Data Model
- Retail: NRF, GS1 standards
- Manufacturing: ISA-95, OPCUA information models
- Government: NIEM (National Information Exchange Model)
- And Teradata's library of Industry LDM's

**3. Organizational Context**
- Enterprise data architecture principles and patterns
- Corporate taxonomy, glossaries, and controlled vocabularies
- Integration patterns already in use
- Existing data product catalog and reusable components
- Security and privacy classification schemes

**4. Regulatory & Compliance**
- GDPR, CCPA data handling requirements
- Industry regulations (BASEL III, HIPAA, SOX)
- Data retention and archival policies
- Audit and lineage requirements

### Implementation Options
- **Vector Stores + RAG**: Embed standards documents for semantic retrieval
- **Structured Knowledge Bases**: Tables with rules, patterns, examples
- **Document Repositories**: PDF/Markdown files with /rag capability
- **LLM Skills/Prompts**: Pre-loaded context for specific domains
- **Hybrid Approaches**: Combine multiple methods based on knowledge type

### Usage in Design Process
Each module design document will include **💡 Knowledge Store Opportunities** callouts identifying where design standards should be consulted. Examples:
- "Consult naming convention store when defining column names"
- "Reference industry model for entity definitions"
- "Apply organization's PI selection rules"

---

## Cross-Module Integration Patterns

### Data Flow Patterns

**1. Join-Back Pattern**
- All modules JOIN to Domain/Subject Data (no duplication)
- Uses Teradata co-location for efficient joins
- Maintains single source of truth

**2. Enhancement Pattern**
- Modules progressively enhance Domain entities
- Search adds embeddings, Prediction adds features, Semantic adds relationship metadata
- Can be deployed incrementally

**3. Feedback Loop Pattern**
- Observability → Memory → Feature Store → Prediction
- Closed-loop learning from agent outcomes
- Continuous improvement cycle

---

## Agent Discovery via Semantic Map

### The Discovery Challenge

AI agents must autonomously discover and navigate the data product without human guidance. The Semantic module serves as the **comprehensive map** that enables this discovery.

### Three-Tier Discovery Hierarchy

**Tier 1: Module Discovery**
- Agent discovers which modules are deployed
- Agent learns physical location of each module (database names)
- Uses `Semantic.data_product_map` table

**Tier 2: Entity Discovery**
- Agent discovers what entities (tables) exist in each module
- Agent learns table structures and key columns
- Uses `Semantic.entity_metadata` and `Semantic.column_metadata` tables

**Tier 3: Relationship Discovery**
- Agent discovers how entities relate (join patterns)
- Agent finds multi-hop paths between tables
- Uses `Semantic.table_relationship` and `Semantic.v_relationship_paths` view

### Discovery Workflow

```
Agent Initialization
    ↓
1. Locate Semantic Module
   Convention: {DataProductName}_Semantic database
   Query: data_product_map table
    ↓
2. Discover Module Locations
   Result: Domain → Customer360_Domain
           Prediction → Customer360_Prediction
           Search → Customer360_Search
           [etc.]
    ↓
3. Explore Module Contents
   Query: entity_metadata (what tables exist?)
   Query: column_metadata (what do columns mean?)
    ↓
4. Learn Relationships
   Query: table_relationship (how to join?)
   Query: v_relationship_paths (multi-hop paths?)
    ↓
5. Generate SQL
   Agent can now autonomously query any module
```

### Example: Agent Discovers Customer360

```sql
-- Step 1: Agent knows product name, constructs Semantic database name
-- Convention: Customer360_Semantic

-- Step 2: Discover modules
SELECT module_name, database_name, primary_tables
FROM Customer360_Semantic.data_product_map
WHERE is_active = 1;

-- Result: 
-- Domain → Customer360_Domain (Party_H, Product_H, Transaction_H)
-- Prediction → Customer360_Prediction (customer_features)
-- [etc.]

-- Step 3: Discover Domain entities
SELECT entity_name, table_name, view_name, natural_key_column
FROM Customer360_Semantic.entity_metadata
WHERE module_name = 'Domain' AND is_active = 1;

-- Result:
-- Party → Party_H (view: Party_Current, key: party_key)
-- Product → Product_H (view: Product_Current, key: product_key)

-- Step 4: Learn how to join Party to customer features
SELECT hop_count, path_tables, path_joins
FROM Customer360_Semantic.v_relationship_paths
WHERE source_table = 'Party_H' AND target_table = 'customer_features'
ORDER BY hop_count;

-- Result: Direct join via party_id

-- Step 5: Generate query
SELECT p.party_key, p.legal_name, cf.credit_score_normalized
FROM Customer360_Domain.Party_H p
INNER JOIN Customer360_Prediction.customer_features cf
    ON cf.party_id = p.party_id
WHERE p.is_current = 1 AND cf.is_current = 1;
```

### Why Semantic as the Map

**Semantic module provides**:
1. **Module Registry** (`data_product_map`) - Where are modules?
2. **Entity Catalog** (`entity_metadata`) - What tables exist?
3. **Column Dictionary** (`column_metadata`) - What do columns mean?
4. **Relationship Graph** (`table_relationship`) - How do tables join?
5. **Path Finder** (`v_relationship_paths`) - Multi-hop join discovery
6. **Naming Standards** (`naming_standard`) - How to interpret names

**Result**: Agents can discover structure, generate SQL, and navigate independently

### Bootstrap Convention

**Standard convention for agent initialization**:
1. Agent receives data product name (e.g., "Customer360")
2. Agent constructs Semantic database name: `{Product}_Semantic`
3. Agent queries `data_product_map` for module locations
4. Agent explores using other Semantic tables
5. Agent is now autonomous

**For detailed discovery protocol and SQL examples**, see:
- **Semantic Module Design Standard** - Complete data_product_map specification
- **Agent Bootstrap Prompt Fragment** - Reusable agent initialization protocol

---

### Access Layer (Consumable Object Metadata)

The logical map above answers *what entities exist and how they relate*. It
does not, on its own, answer *which objects a consumer should actually query*.
A platform's security model may expose one entity through several objects
(locking views, business views, current views), and products publish composite
("enriched") objects that join several entities into one consumable unit. Which
object to query, what it represents, and what a composite encapsulates are
**access-layer** facts.

The Semantic module therefore carries an **access-object metadata layer** — a
registry of consumable objects (`access_object`), the composition of composite
objects (`access_composition`), and access-resolved join paths — so any
consumer resolves a queryable object to its logical meaning **once, from
metadata**, without parsing DDL or recomputing lineage at query time. See the
Semantic Module Design Standard for the schemas, consumption contract, and
discovery queries.

Two principles govern it:

- **Object names are not a contract.** No consumer infers an object's role,
  layer, entity, or purpose from its name. Naming schemes vary across estates;
  the registry is the single source of truth, and classification is asserted in
  metadata, never derived from a name. (This is distinct from the security
  **Access Layer Design Standard**, which governs roles and grants.)
- **Established once, at deployment.** A registration step classifies objects
  from verifiable structure — the dependency graph and object definitions — and
  asserts the result in the registry; consumers read it and never recompute it.
  The concrete role vocabulary beyond the small open baseline, physical types,
  and the population step are platform concerns, defined through the relevant
  **Platform Profile**.

---

### Physical Naming Conventions

**Critical Consideration**: Multiple AI-Native Data Products can be deployed on a single Teradata platform. Database names must be unique across the platform.

#### Documentation Tables: Self-Contained in Memory Database

Documentation tables (Module_Registry, Design_Decision, Business_Glossary, Query_Cookbook, Implementation_Note, Change_Log) live inside the data product's own Memory database — `{ProductName}_Memory`. There is no shared cross-product documentation database. This keeps each data product fully self-contained and independently deployable.

See Memory Module Design Standard, Section 8 for the complete Documentation Sub-Module design.

#### Approach 1: Separate Databases per Module (RECOMMENDED)

**Pattern**: `{DataProductName}_{ModuleName}`

**Example - Customer 360 Data Product**:
```
Databases:
├── Customer360_Domain          (Domain module)
├── Customer360_Semantic        (Semantic module)
├── Customer360_Prediction      (Prediction/Feature Store)
├── Customer360_Search          (Search/Vector embeddings)
├── Customer360_Memory          (Memory/Agent state)
└── Customer360_Observability   (Observability/Events)

Tables within each database:
- Customer360_Domain: Party_H, Product_H, Transaction_H
- Customer360_Semantic: entity_metadata, table_relationship
- Customer360_Prediction: customer_features, model_prediction
- Customer360_Search: entity_embedding
- Customer360_Memory: agent_session, agent_interaction
- Customer360_Observability: change_event, data_quality_metric
```

**Benefits**:
- ✅ Clear module boundaries
- ✅ Independent access control per module (GRANT DATABASE) — see Access Layer Design Standard
- ✅ Modules can be deployed incrementally
- ✅ Separate space management per module
- ✅ Aligns with modular architecture concept
- ✅ Easier to understand and navigate

**Use When**:
- Enterprise deployments
- Multiple teams/roles need different module access
- Modules deployed at different times
- Clear separation of concerns required

#### Approach 2: Single Database with Module Prefixes

**Pattern**: `{DataProductName}` database with `{Module}_{ObjectName}` tables

**Example - Customer 360 Data Product**:
```
Database:
└── Customer360

Tables with module prefixes:
- D_Party_H, D_Product_H, D_Transaction_H              (Domain)
- S_entity_metadata, S_table_relationship              (Semantic)
- P_customer_features, P_model_prediction              (Prediction)
- E_entity_embedding                                   (Search/Embeddings)
- M_agent_session, M_agent_interaction                 (Memory)
- O_change_event, O_data_quality_metric                (Observability)
```

**Module Prefix Codes**:
- `D_` = Domain
- `S_` = Semantic  
- `P_` = Prediction
- `E_` = Embeddings/Search (E to avoid conflict with Semantic)
- `M_` = Memory
- `O_` = Observability

**Benefits**:
- ✅ Fewer databases to manage
- ✅ All data in one place
- ✅ Simpler for small deployments
- ✅ No cross-database joins

**Use When**:
- Small deployments (single team)
- Unified access control acceptable
- All modules deployed together
- Simpler management preferred

#### Decision Criteria

| Factor | Separate Databases | Single Database |
|--------|-------------------|-----------------|
| **Team Size** | Multiple teams | Single team |
| **Access Control** | Module-level control needed | Unified access OK |
| **Deployment** | Incremental by module | All modules together |
| **Scale** | Enterprise (100+ tables) | Small (< 50 tables) |
| **Management** | Prefer clear separation | Prefer simplicity |

**Default Recommendation**: Use separate databases per module unless deployment is small and simple.

#### Cross-Module References

**Both approaches use same foreign key pattern**:

```sql
-- From Prediction module to Domain module (Approach 1 - Separate DBs)
CREATE TABLE Customer360_Prediction.customer_features (
    party_is BIGINT NOT NULL  -- FK to Customer360_Domain.Party_H
    ...
);

-- From Prediction module to Domain module (Approach 2 - Single DB)  
CREATE TABLE Customer360.P_customer_features (
    party_id BIGINT NOT NULL  -- FK to Customer360.D_Party_H
    ...
);
```

#### Module Design Standards - Naming Placeholder

**All module design standards use generic placeholders**:
- `Domain.Party_H` (generic database reference)
- `Semantic.entity_metadata` (generic database reference)
- `Prediction.customer_features` (generic database reference)

**Implementation teams replace with**:
- **Approach 1**: `Customer360_Domain.Party_H`
- **Approach 2**: `Customer360.D_Party_H`

---

**Foreign Key Relationships**
- All module tables include `<entity>_id` to join back to Domain
- Temporal tables include `valid_from`, `valid_to` for point-in-time joins
- Join indexes on common patterns for performance

**Schema Organization**
- Option 1: Single database with module-prefixed tables
- Option 2: Separate databases per module (e.g., CUSTOMER360_DOMAIN, CUSTOMER360_SEARCH)
- Recommendation: Start with Option 1, migrate to Option 2 as modules mature

---

## Platform Profiles

### Concept

A **Platform Profile** is a companion document to these design standards that captures platform-specific implementation guidance for a particular deployment target. The design standards define *what* to build — the structural requirements, module patterns, naming conventions, and integration contracts. A Platform Profile defines *how* to build it on a specific platform.

Platform Profiles are separate from the core design standards deliberately: they can be updated as platform capabilities evolve without changing the structural standards, and new profiles can be added for new platforms without modifying existing ones.

### What a Platform Profile Contains

| Section | Content |
|---------|---------|
| **Physical design guidance** | Primary key strategy, partitioning, indexing, co-location patterns |
| **DDL syntax adaptations** | Data types, default value syntax, view/index DDL for the target platform |
| **Performance optimisation** | Statistics collection, query optimisation, compression |
| **Deployment tooling** | Load patterns, ETL tooling recommendations, scheduling |
| **Platform-specific constraints** | Known limitations, workarounds, version dependencies |

### Current Platform Profiles

| Platform | Document | Status |
|----------|----------|--------|
| Teradata | `Advocated_Data_Management_Standards.md` — Section 10 | Current reference implementation |

As the framework is adopted on additional platforms, new Platform Profiles should be created following the same structure as the Teradata reference. Teams implementing on platforms not yet covered should document their implementation choices in a new Platform Profile rather than modifying the core design standards.

---

## Design Constraints & Considerations

### Platform Implementation Notes

Physical design decisions — indexing strategy, partitioning, compression, statistics collection, and query optimisation — are platform-specific and are documented in Platform Profiles rather than in these core standards. See the relevant Platform Profile for your deployment target.

The following considerations apply regardless of platform:

### Performance Considerations
- **Vector Search**: Requires platform-native vector index support or a specialist vector store; consult the relevant Platform Profile
- **Feature Store**: Pre-compute expensive aggregations
- **Observability**: Partition by time for efficient retention management
- **Memory**: Consider archival strategy for old sessions

### Scalability Patterns
- **Horizontal**: Partition large tables by time or entity type
- **Vertical**: Separate hot/cold data (recent vs. historical)
- **Compute**: Use Teradata's workload management for module-specific resource allocation

---

## Module Dependencies & Development Sequence

### Recommended Implementation Order

**Phase 1: Infrastructure (Memory & Semantic)**
1. Memory — creates `{ProductName}_Memory` database including all documentation tables. Every subsequent module writes documentation INSERTs here as its final deployment step.
2. Semantic — creates `{ProductName}_Semantic` database. Every subsequent module writes entity, column, and relationship registration INSERTs here as part of its deployment.

Both must exist before any other module deploys.

**Phase 1.5: Access Layer — initial grant**
3. Create the three product roles (`{ProductName}_ROLE_READ`, `{ProductName}_ROLE_AGENT`, `{ProductName}_ROLE_ADMIN`) and grant SELECT on the Semantic and Memory databases. This is the minimum grant required for agents and operational tools to discover and read the data product. See _Access Layer Design Standard_.

**Phase 2: Foundation (Domain & Observability)**
4. Domain — core business entities; documentation and Semantic registration written on deploy
5. Observability — begins monitoring Domain immediately; coverage expands as later modules deploy

**Phase 2.5: Access Layer — extend grants**
6. Extend role grants to Domain and Observability databases. Apply further grants as Search and Prediction are deployed in Phase 3.

**Phase 3: Enhancement (Search & Prediction)**
7. Search — requires Domain entities to embed
8. Prediction — requires Domain entities to featurise

### Module Dependencies
```
Memory ────────────────→ (hosts documentation tables for all modules)
Semantic ───────────────→ (hosts discovery metadata for all modules)
    │
    Both must exist first
    │
Access Layer (1.5) ─────→ ROLE_READ, ROLE_AGENT, ROLE_ADMIN created
                          SELECT granted on Semantic + Memory
    │
Domain ────────┬────────→ Search
               ├────────→ Prediction
               └────────→ (entity foundation for all modules)

Observability ──────────→ Memory (closed-loop learning feedback)

Access Layer (2.5) ─────→ SELECT extended to Domain + Observability
                          (and Search, Prediction as deployed)
```

---

## Access Layer

Every AI-Native Data Product must deploy an Access Layer alongside its module DDL. The Access Layer creates standard database roles and grants them SELECT access to each module's databases, making the data product discoverable and queryable by agents and consumers as each module is deployed.

### Why it is mandatory

Without an Access Layer, a correctly deployed data product is operationally invisible: every consumer — agents, dashboards, reporting tools, and analysts — will be denied access regardless of how completely the module databases have been deployed.

### Three standard roles

Three roles are created per product, named `{ProductName}_ROLE_{TIER}`:

| Role | Consumers | Purpose |
|------|-----------|---------|
| `{ProductName}_ROLE_READ` | Analysts, BI tools, ad-hoc SQL users | SELECT on module databases |
| `{ProductName}_ROLE_AGENT` | AI agents, MCP servers, automated tools | SELECT on module databases; kept separate to allow independent lifecycle management |
| `{ProductName}_ROLE_ADMIN` | Data product owner, data steward | SELECT on all databases |

The roles themselves are data product artefacts — created once and owned by the data product team. Assigning specific users or service accounts to those roles is an operational event, not a design standard concern.

### Relationship to Physical Naming Approaches

In the recommended Approach 1 (separate databases per module), each module database receives its own grant — for example: `GRANT SELECT ON {ProductName}_Semantic TO {ProductName}_ROLE_READ`. In Approach 2 (single database), a single grant covers all modules: `GRANT SELECT ON {ProductName} TO {ProductName}_ROLE_READ`.

In deployments that separate base tables and views into distinct databases, consumers should be granted access to the view-layer database only — not the base table database.

**Full specification**: see `Access_Layer_Design_Standard.md`.

---

## Glossary

**Access Layer**: The mandatory access control artefact of an AI-Native Data Product. Creates standard database roles (`ROLE_READ`, `ROLE_AGENT`, `ROLE_ADMIN`) and grants them SELECT access to module databases, making the data product discoverable and queryable by all consumers. Deployed in two phases interleaved with the module deployment sequence. See _Access Layer Design Standard_.

**Agent**: An autonomous software entity that can perceive, reason, and act - consuming data products to achieve goals.

**Architecture Decision Record (ADR)**: A structured record capturing a significant design decision, including context, alternatives considered, rationale, and consequences. Stored in `Memory.Design_Decision` as part of the Documentation Sub-Module.

**Attribute**: A column within an entity (table). For example, party_key is an attribute of the Party entity.

**Co-location**: Teradata's ability to store related data on the same AMPs for efficient joins without data movement.

**Data Product**: A self-contained, well-defined data asset with clear ownership, interfaces, and SLAs - treated as a product rather than a byproduct.

**Documentation Sub-Module**: A sub-module of the Memory Module providing design memory for a data product. Tables (Module_Registry, Design_Decision, Business_Glossary, Query_Cookbook, Implementation_Note, Change_Log) are co-located in the data product's Memory database, keeping the data product fully self-contained. Captures architectural decisions, business glossary terms, proven query patterns, and change history during the design process. Defined in Memory Module Design Standard, Section 8.

**Embedding**: A dense vector representation of data (text, images, entities) in a high-dimensional space where semantic similarity maps to geometric proximity.

**Entity**: A table within the data product. For example, Party_H is an entity, not a row in the table.

**Feature Store**: A centralized repository for storing, managing, and serving ML features - ensuring consistency between training and inference.

**Instance**: An actual row of data within a table. For example, Customer Key CUST-123 is an instance.

**Module**: A self-contained, independently deployable component of an AI-Native Data Product, responsible for a distinct capability (e.g., Domain, Semantic, Search). Each module has its own database, data model, table structures, and design standard. Modules are composable — a data product can implement any combination — and integrate through standard join-back and cross-module reference patterns. The six standard modules are: Domain, Semantic, Search, Prediction, Observability, and Memory (which includes the Documentation Sub-Module).

**Knowledge Graph**: A network of entities and their relationships, enabling semantic reasoning and inference.

**Knowledge Store**: Design-time knowledge that guides HOW to build the data product (standards, patterns, industry models).

**Point-in-Time (PIT)**: Reconstructing features or data as they existed at a specific historical moment - critical for ML training without data leakage.

**RAG (Retrieval Augmented Generation)**: Pattern where LLMs retrieve relevant context before generating responses - requires Search module.

**Relationship**: An association or connection between entities, which may be expressed through foreign keys, hierarchies, or semantic associations.

**Semantic Module**: Runtime knowledge ABOUT the data product - describes meaning, relationships, and contracts.

**Temporal Data**: Data that tracks changes over time - includes valid time (when true in reality) and transaction time (when recorded in system).

**Vector Store**: A specialized database optimized for storing and searching high-dimensional vectors using similarity metrics.

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.1 | 2026-07-18 | Paul Dancer, Worldwide Data Architecture Team, Teradata | Added the Access Layer (Consumable Object Metadata) concept to Agent Discovery (resolves issue #9, core half). Describes the access-object metadata layer - which objects a consumer queries, what each represents, and what composites encapsulate - and the two governing principles (object names are not a contract; the registry is established once at deployment from verifiable structure). Points to the Semantic Module Design Standard for the schemas and consumption contract, and to Platform Profiles for the concrete role vocabulary, physical types, and population step. Distinct from the security Access Layer Design Standard (roles and grants). |
| 2.0 | 2026-05-07 | Paul Dancer, Worldwide Data Architecture Team, Teradata | Added mandatory Access Layer. New section defining three standard roles (ROLE_READ, ROLE_AGENT, ROLE_ADMIN), two-phase grant timing (Phase 1.5 after Memory+Semantic, Phase 2.5 after Domain+Observability), and guidance for both naming approaches. Updated Documentation Hierarchy tree, Recommended Implementation Order, Module Dependencies diagram, Approach 1 benefits, and Glossary. Full specification in Access_Layer_Design_Standard.md. |
| 1.9 | 2026-04-15 | Nathan Green, Worldwide Data Architecture Team, Teradata | Established platform neutrality throughout. Updated Executive Summary and Zero Data Duplication principle to remove Teradata-specific language. Added Platform-Neutral Design as Guiding Principle 7. Added Platform Profiles section defining the concept, structure, and current implementations. Refactored Design Constraints section: removed Teradata-Specific Optimizations subsection, added Platform Implementation Notes framing directing implementors to Platform Profiles. Updated Performance Considerations to be platform-neutral. |
| 1.8 | 2026-03-20 | Nathan Green, Worldwide Data Architecture Team, Teradata | Corrected module deployment order. Memory and Semantic are now Phase 1 (both must exist before any other module deploys — Memory hosts documentation tables, Semantic hosts discovery metadata). Domain and Observability are Phase 2. Search and Prediction are Phase 3. Updated Implementation Order section and Module Dependencies diagram. |
| 1.7 | 2026-03-20 | Nathan Green, Worldwide Data Architecture Team, Teradata | Fixed = 'Y' filter values in agent discovery example queries to = 1 to align with platform boolean standard. |
| 1.6 | 2026-03-20 | Nathan Green, Worldwide Data Architecture Team, Teradata | Revised to align with data product self-containment principle. Removed shared dp_documentation database pattern. Documentation tables now co-located in {ProductName}_Memory database as design memory alongside runtime memory. Removed Pre-Phase bootstrap from implementation order. Updated Memory module definition, Physical Naming Conventions, and Glossary (revised Documentation Sub-Module entry, removed dp_documentation entry). |
| 1.5 | 2026-03-20 | Nathan Green, Worldwide Data Architecture Team, Teradata | Added Glossary entry for Module. |
| 1.4 | 2026-03-20 | Nathan Green, Worldwide Data Architecture Team, Teradata | Merged Documentation as sub-module of Memory. Updated Documentation Hierarchy tree, Architecture Overview ASCII, Memory module definition (Scope and Integration Points), Implementation Order (added Pre-Phase dp_documentation bootstrap), Physical Naming Conventions (added dp_documentation shared database), Glossary (added Architecture Decision Record, Documentation Sub-Module, dp_documentation). |
| 1.3 | 2026-03-18 | Kimiko Yabu, Worldwide Data Architecture Team, Teradata | Updated to remain consistent with module design docs, the key/id swap |
| 1.2 | 2026-02-16 | Nathan Green, Worldwide Data Architecture Team, Teradata | Updated to remain consistent with module design docs, added agent discovery section |
| 1.1 | 2026-02-05 | Nathan Green, Worldwide Data Architecture Team, Teradata | Updated to clarify scope of modules |
| 1.0 | 2025-11-07 | Nathan Green, Worldwide Data Architecture Team, Teradata | Initial master design standard with standards-based approach |
---

*This is a living standard. Module Design Standards will extend these principles, and actual data product implementations will apply them. Standards evolve based on experience and feedback.*
