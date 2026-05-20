# Search Module Design Standard
## AI-Native Data Product Architecture - Version 1.5

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.5 |
| **Status** | STANDARD |
| **Last Updated** | 2026-03-20 |
| **Owner** | Nathan Green, Worldwide Data Architecture Team, Teradata |
| **Scope** | Search Module (Vector Embeddings & Similarity) |
| **Type** | Design Standard (Structural Requirements) |
| **Companion** | Advocated Data Management Standards (Implementation Guidance) |

---

## Table of Contents

1. [AI-Native Search Module Overview](#1-ai-native-search-module-overview)
2. [Module Scope and Boundaries](#2-module-scope-and-boundaries)
3. [Vector Storage Structure](#3-vector-storage-structure)
4. [Similarity Search Patterns](#4-similarity-search-patterns)
5. [Integration with Other Modules](#5-integration-with-other-modules)
6. [Agent Discovery and Querying](#6-agent-discovery-and-querying)
7. [Designer Responsibilities](#7-designer-responsibilities)

---

## 1. AI-Native Search Module Overview

### 1.1 What Makes Search Module AI-Native?

The Search Module enables **semantic search and similarity-based retrieval** using vector embeddings, allowing agents to find relevant content by meaning rather than exact keyword matching.

| AI-Native Characteristic | Purpose |
|-------------------------|---------|
| **Semantic Search** | Find by meaning, not keywords ("find things like this") |
| **Native Vector Storage** | Teradata's VECTOR datatype for efficient embedding storage |
| **Similarity Functions** | In-database TD_VectorDistance for parallel similarity computation |
| **Efficient Storage** | Store vectors + ids only, join to Domain for content |
| **RAG Support** | Retrieval-augmented generation patterns |

### 1.2 Primary Purpose: Enable Similarity Search

**Search module enables:**

1. **Semantic Search** - Find similar documents, products, customers by meaning
2. **RAG (Retrieval Augmented Generation)** - Retrieve relevant context for LLMs
3. **Similarity Analysis** - Find similar entities across the data product
4. **Content Discovery** - Agents discover relevant data autonomously
5. **Multi-Modal Search** - Text, images, structured data embeddings

### 1.3 Critical Principle: Store IDs Only, Not Content

**EFFICIENT PATTERN** (advocated):
```
Vector Store:                         Domain Module:
┌──────────────────────┐            ┌──────────────────────┐
│ entity_id: 1001     │            │ party_id: 1001       │
│ embedding: [0.23,... │   points   │ party_key: CUST-123  │
│            ...,0.89] │   ────────>│ legal_name: "John"   │
│ (384 dimensions)     │            │ description: "..."    │
└──────────────────────┘            │ ... all attributes    │
   Vector + Id only                 └──────────────────────┘
   (minimal storage)                    Actual content
```

**INEFFICIENT PATTERN** (avoid):
```
Vector Store with duplicated content:
┌──────────────────────────────────────┐
│ entity_id: 1001                     │
│ embedding: [0.23, ..., 0.89]         │
│ legal_name: "John Doe" ❌ DUPLICATE  │
│ description: "..." ❌ DUPLICATE       │
│ email: "..." ❌ DUPLICATE             │
└──────────────────────────────────────┘
   Wastes storage, out of sync risk
```

**Benefits of key-only storage**:
- ✅ Minimal storage (vectors + ids only)
- ✅ No data duplication (single source of truth in Domain)
- ✅ Always current (join to Domain for latest content)
- ✅ Efficient updates (update embedding, not content)
- ✅ Co-located joins (fast on Teradata)

---

## 2. Module Scope and Boundaries

### 2.1 What Belongs in Search Module

**IN SCOPE:**

1. **Vector Embeddings**
   - Semantic representations of entities (text, images, structured data)
   - Multiple embedding models/versions supported
   - Embedding dimensions (384, 768, 1536, etc.)

2. **Entity References** 
   - Ids pointing back to Domain entities
   - Entity type classification
   - **NOT the actual content** (join to Domain for content)

3. **Embedding Metadata**
   - Which embedding model generated the vector
   - When embedding was generated
   - Embedding version

4. **Similarity Indexes** (Optional)
   - KMEANS clustering for approximate nearest neighbor
   - HNSW indexes for fast similarity search

**OUT OF SCOPE:**

- ❌ **Source content** → Domain Module (join to get actual text, descriptions)
- ❌ **Entity attributes** → Domain Module (names, descriptions, metadata)
- ❌ **Structured features** → Prediction Module (engineered ML features)
- ❌ **Embedding model definitions** → Semantic Module (metadata about models)

### 2.2 Teradata Native Vector Support

**Standard**: Use Teradata's native **VECTOR datatype** (available in Vantage 20.00.26.XX+)

**Format**: `VECTOR` using `FLOAT32(n)` notation where n = embedding dimensions

**Supported Features**:
- Native VECTOR UDT (User Defined Type)
- TD_VectorDistance function (cosine, Euclidean, Manhattan)
- KMEANS clustering (approximate nearest neighbor)
- HNSW indexing (graph-based ANN)
- ONNXEmbeddings (in-database embedding generation)
- Integration with LangChain, Enterprise Vector Store API

**Reference**: Teradata Enterprise Vector Store, ClearScape Analytics

---

## 3. Vector Storage Structure

### 3.1 Standard Embedding Table (Key-Only Pattern)

```sql
CREATE TABLE Search.entity_embedding (
    embedding_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- Entity reference (KEY ONLY - no content duplication)
    entity_id BIGINT NOT NULL,       -- FK to Domain entity
    entity_type VARCHAR(50) NOT NULL, -- 'PARTY', 'PRODUCT', 'DOCUMENT', etc.
    
    -- Source identification (what was embedded)
    source_module VARCHAR(50),        -- 'Domain', 'Prediction', etc.
    source_table VARCHAR(100),        -- 'Party_H', 'Product_H', etc.
    source_column VARCHAR(128),       -- Which column was embedded (e.g., 'description')
    
    -- Vector embedding (Teradata native VECTOR datatype)
    embedding_vector VECTOR,          -- FLOAT32(n) format
    embedding_dimensions INTEGER NOT NULL, -- 384, 768, 1536, etc.
    
    -- Embedding metadata
    embedding_model VARCHAR(100) NOT NULL, -- 'bge-small-en-v1.5', 'text-embedding-ada-002'
    embedding_model_version VARCHAR(20),
    
    -- Temporal tracking
    generated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_from_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_to_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL 
        DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
    is_current BYTEINT NOT NULL DEFAULT 1,
    
    -- Generation metadata
    generated_by VARCHAR(100),
    computation_method VARCHAR(50)  -- 'ONNX', 'OPENAI_API', 'NVIDIA_NIM', etc.
)
PRIMARY INDEX (embedding_id);

COMMENT ON TABLE Search.entity_embedding IS 
'Vector embeddings for entities - stores vectors and entity ids only, join to Domain for actual content to avoid duplication';

COMMENT ON COLUMN Search.entity_embedding.embedding_id IS 
'Surrogate key for embedding record';

COMMENT ON COLUMN Search.entity_embedding.entity_id IS 
'Foreign key to Domain entity - references specific entity instance (party_id, product_id, etc.) - NO content duplicated';

COMMENT ON COLUMN Search.entity_embedding.entity_type IS 
'Entity type indicator - PARTY, PRODUCT, DOCUMENT, etc. - identifies which Domain table this entity belongs to';

COMMENT ON COLUMN Search.entity_embedding.source_module IS 
'Module where source entity resides - Domain, Prediction, etc.';

COMMENT ON COLUMN Search.entity_embedding.source_table IS 
'Source table containing the entity - Party_H, Product_H, Document_H, etc.';

COMMENT ON COLUMN Search.entity_embedding.source_column IS 
'Source column that was embedded - description, notes, combined_text, etc. - identifies what text generated this embedding';

COMMENT ON COLUMN Search.entity_embedding.embedding_vector IS 
'Vector embedding - Teradata native VECTOR datatype storing FLOAT32(n) representation for semantic similarity search';

COMMENT ON COLUMN Search.entity_embedding.embedding_dimensions IS 
'Number of dimensions in embedding vector - 384, 768, 1536, etc. - depends on embedding model used';

COMMENT ON COLUMN Search.entity_embedding.embedding_model IS 
'Embedding model name - bge-small-en-v1.5, text-embedding-ada-002, etc. - identifies which model generated embedding';

COMMENT ON COLUMN Search.entity_embedding.embedding_model_version IS 
'Model version - tracks embedding model versions for reproducibility';

COMMENT ON COLUMN Search.entity_embedding.generated_dts IS 
'Timestamp when embedding was generated - tracks freshness of semantic representation';

COMMENT ON COLUMN Search.entity_embedding.valid_from_dts IS 
'When this embedding version became valid - supports embedding versioning';

COMMENT ON COLUMN Search.entity_embedding.valid_to_dts IS 
'When this embedding was superseded - default 9999-12-31 for current embedding';

COMMENT ON COLUMN Search.entity_embedding.is_current IS 
'Current embedding indicator - 1 = current embedding, 0 = historical embedding (from previous model or content version)';

COMMENT ON COLUMN Search.entity_embedding.generated_by IS 
'User or process that generated embedding - ML pipeline, batch job, API call, etc.';

COMMENT ON COLUMN Search.entity_embedding.computation_method IS 
'Method used to generate embedding - ONNX (in-database), OPENAI_API, NVIDIA_NIM, HUGGINGFACE_API, etc.';
```

**CRITICAL**: No content columns (description, text, name, etc.). Store keys only, join to Domain.

### 3.2 Alternative: Columnar Storage (Legacy/Analytics)

**For older Teradata versions (17.20+) or analytics workflows:**

```sql
CREATE TABLE Search.entity_embedding_columnar (
    embedding_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    entity_id BIGINT NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    
    -- Embedding dimensions as separate columns (for TD_VectorDistance)
    emb_0 FLOAT,
    emb_1 FLOAT,
    emb_2 FLOAT,
    -- ... continue to emb_383 for 384-dim embeddings
    
    embedding_model VARCHAR(100),
    generated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    is_current BYTEINT NOT NULL DEFAULT 1
)
PRIMARY INDEX (embedding_id);

-- TD_VectorDistance supports range notation
-- Can reference as '[emb_0:emb_383]' in queries
```

**Use native VECTOR format (3.1) unless**:
- Database version < 20.00.26.XX
- Need direct analytics on individual dimensions
- Legacy compatibility required

### 3.3 NO Content Duplication Examples

**❌ AVOID (data duplication)**:
```sql
CREATE TABLE Search.product_embedding_BAD (
    embedding_id INTEGER,
    product_id BIGINT,
    embedding_vector VECTOR,
    -- DON'T DUPLICATE THESE:
    product_name VARCHAR(200),      -- ❌ Already in Domain.Product_H
    product_description VARCHAR(2000), -- ❌ Already in Domain.Product_H
    category VARCHAR(100),          -- ❌ Already in Domain.Product_H
    price DECIMAL(10,2)             -- ❌ Already in Domain.Product_H
);
-- This wastes storage and creates sync issues
```

**✅ CORRECT (keys only)**:
```sql
CREATE TABLE Search.product_embedding_GOOD (
    embedding_id INTEGER,
    product_id BIGINT,              -- ID only
    entity_type VARCHAR(50),         -- 'PRODUCT'
    source_column VARCHAR(128),      -- 'product_description'
    embedding_vector VECTOR,
    embedding_dimensions INTEGER,
    embedding_model VARCHAR(100),
    generated_dts TIMESTAMP(6) WITH TIME ZONE,
    is_current BYTEINT NOT NULL DEFAULT 1
);

-- Join to Domain for actual content
SELECT 
    e.embedding_id,
    e.product_id,
    e.embedding_vector,
    p.product_name,        -- From Domain (not duplicated)
    p.product_description, -- From Domain (not duplicated)
    p.category,            -- From Domain (not duplicated)
    p.price                -- From Domain (not duplicated)
FROM Search.product_embedding_GOOD e
INNER JOIN Domain.Product_H p 
    ON p.product_id = e.product_id
   AND p.is_current = 1
WHERE e.is_current = 1;
```

---

## 4. Similarity Search Patterns

### 4.1 TD_VectorDistance Function

**Teradata's native similarity search function (parallel execution across AMPs)**

**Supported distance metrics**:
- **Cosine** (default, most common for text embeddings)
- **Euclidean** (L2 distance, spatial data)
- **Manhattan** (L1 distance)

**Basic similarity search**:
```sql
-- Find top 10 most similar products to query product
SELECT 
    ref.entity_id AS similar_product_id,
    ref.embedding_id,
    dt.distance AS similarity_distance
FROM TD_VECTORDISTANCE (
    ON (SELECT * FROM Search.entity_embedding WHERE entity_id = 5001) 
        AS TargetTable PARTITION BY ANY
    ON (SELECT * FROM Search.entity_embedding WHERE entity_type = 'PRODUCT' AND is_current = 1) 
        AS ReferenceTable DIMENSION
    USING
        TargetIDColumn('entity_id')
        TargetFeatureColumns('embedding_vector')
        RefIDColumn('entity_id')
        RefFeatureColumns('embedding_vector')
        DistanceMeasure('cosine')
        TopK(10)
) AS dt
INNER JOIN Search.entity_embedding ref 
    ON ref.entity_id = dt.reference_id
ORDER BY dt.distance;
```

**For columnar storage (FLOAT columns)**:
```sql
-- Using range notation for column-based embeddings
USING
    TargetFeatureColumns('[emb_0:emb_383]')
    RefFeatureColumns('[emb_0:emb_383]')
    DistanceMeasure('cosine')
    TopK(10)
```

### 4.2 Similarity Search with Content (JOIN to Domain)

**Pattern**: Search finds similar entities, join to Domain for actual content

```sql
-- Find similar products with full product details
SELECT 
    p.product_key,
    p.product_name,
    p.product_description,
    p.price,
    dt.distance AS similarity_score
FROM TD_VECTORDISTANCE (
    ON query_embedding AS TargetTable PARTITION BY ANY
    ON Search.entity_embedding AS ReferenceTable DIMENSION
    WHERE ReferenceTable.entity_type = 'PRODUCT' 
      AND ReferenceTable.is_current = 1
    USING
        TargetIDColumn('entity_id')
        TargetFeatureColumns('embedding_vector')
        RefIDColumn('entity_id')
        RefFeatureColumns('embedding_vector')
        DistanceMeasure('cosine')
        TopK(10)
) AS dt
-- Join to Domain for product details (NOT stored in Search)
INNER JOIN Domain.Product_H p
    ON p.product_id = dt.reference_id
   AND p.is_current = 1
   AND p.is_deleted = 0
ORDER BY dt.distance;
```

**Key pattern**: Search provides similarity ranking, Domain provides content

### 4.3 Approximate Nearest Neighbor (ANN) Indexing

**For large vector datasets, use indexing for performance:**

#### KMEANS Clustering (IVF-style)

**Pattern**: Partition vectors into clusters, search only closest clusters

**Configuration**:
```python
# Via Enterprise Vector Store API
vs.create(
    search_algorithm='KMEANS',
    train_numcluster=4,      # Number of clusters
    max_iternum=50,          # Convergence iterations
    stop_threshold=0.0395,   # Convergence precision
    metric='COSINE'
)
```

**Use when**:
- Large datasets (100K+ vectors)
- Batch/offline search acceptable
- Can rebuild index periodically

#### HNSW Indexing (Graph-based)

**Pattern**: Hierarchical navigable small world graph

**Configuration**:
```python
# Via Enterprise Vector Store API
vs.create(
    search_algorithm='hnsw',
    ef_search=50  # Accuracy-speed tradeoff
)
```

**Use when**:
- Interactive/real-time search required
- Frequent updates to vector store
- Higher accuracy requirements

#### Exact Search (Brute Force)

**Use TD_VectorDistance without indexing when**:
- Small datasets (< 50K vectors)
- Absolute accuracy required
- SQL pre-filtering already reduced candidate set

### 4.4 Distance Metrics Selection

| Metric | Use When | Formula |
|--------|----------|---------|
| **Cosine** | Text embeddings, semantic similarity | 1 - (A·B)/(‖A‖‖B‖) |
| **Euclidean** | Spatial data, geographic similarity | √Σ(Aᵢ-Bᵢ)² |
| **Manhattan** | Grid-like data, high-dimensional sparse | Σ‖Aᵢ-Bᵢ‖ |

**Default**: Cosine similarity for most text/semantic use cases

---

## 5. Integration with Other Modules

### 5.1 Integration with Domain (Entity References)

**Pattern**: Search stores embeddings for Domain entities using standard FK pattern

```sql
CREATE TABLE Search.party_embedding (
    embedding_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- Reference to Domain entity (ID ONLY)
    party_id BIGINT NOT NULL,  -- FK to Domain.Party_H
    
    -- What was embedded (metadata, not content)
    embedded_column VARCHAR(128),  -- 'description', 'notes', 'combined_text'
    
    -- Vector
    embedding_vector VECTOR,
    embedding_dimensions INTEGER DEFAULT 384,
    embedding_model VARCHAR(100),
    
    -- Temporal
    generated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    is_current BYTEINT NOT NULL DEFAULT 1
)
PRIMARY INDEX (embedding_id);

-- Query with Domain content (JOIN, no duplication)
SELECT 
    p.party_key,
    p.legal_name,
    p.description,      -- From Domain, NOT duplicated in Search
    e.embedding_model,
    e.generated_dts
FROM Search.party_embedding e
INNER JOIN Domain.Party_H p
    ON p.party_id = e.party_id
   AND p.is_current = 1
   AND p.is_deleted = 0
WHERE e.is_current = 1
  AND e.embedding_model = 'bge-small-en-v1.5';
```

### 5.2 Integration with Semantic (Embedding Definitions)

**Pattern**: Semantic describes embedding strategies, Search stores actual vectors

```sql
-- Semantic module documents embedding strategy (metadata)
INSERT INTO Semantic.column_metadata (
    table_name, column_name, business_description
) VALUES (
    'party_embedding', 'embedding_vector',
    'BGE-small-en-v1.5 embedding (384-dim) of Party description text for semantic search'
);

-- Search module stores actual embeddings (instance data)
INSERT INTO Search.party_embedding (
    party_id, embedded_column, embedding_vector, 
    embedding_dimensions, embedding_model
) VALUES (
    1001, 'description', [0.234, 0.567, ..., 0.891]::VECTOR,
    384, 'bge-small-en-v1.5'
);
```

### 5.3 Standard View Pattern (Search + Domain Content)

```sql
-- View combines embeddings with actual content (efficient join)
CREATE VIEW Search.v_party_searchable
(
    -- View contract: agents see all returned columns without parsing the SELECT body
    party_id,
    party_key,
    legal_name,
    description,
    notes,
    embedding_vector,
    embedding_model,
    embedding_dimensions,
    generated_dts
)
AS
SELECT 
    -- Entity identification
    p.party_id,
    p.party_key,
    
    -- Content from Domain (NOT duplicated in Search)
    p.legal_name,
    p.description,
    p.notes,
    
    -- Embedding from Search
    e.embedding_vector,
    e.embedding_model,
    e.embedding_dimensions,
    e.generated_dts
FROM Domain.Party_H p
INNER JOIN Search.party_embedding e
    ON e.party_id = p.party_id
   AND e.is_current = 1
WHERE p.is_current = 1
  AND p.is_deleted = 0;

COMMENT ON VIEW Search.v_party_searchable IS 
'Party records with embeddings - joins Domain content with Search vectors without duplication, provides complete context for semantic search and RAG';

-- Agent queries view for complete context
SELECT * FROM Search.v_party_searchable
WHERE party_key = 'CUST-123';
```

---

## 6. Agent Discovery and Querying

### 6.1 Discovery Patterns

#### What entities have embeddings?

```sql
SELECT DISTINCT entity_type, source_table, COUNT(*) AS embedding_cnt
FROM Search.entity_embedding
WHERE is_current = 1
GROUP BY entity_type, source_table;
```

#### What embedding models are in use?

```sql
SELECT DISTINCT 
    embedding_model, 
    embedding_dimensions,
    COUNT(*) AS vector_cnt
FROM Search.entity_embedding
WHERE is_current = 1
GROUP BY embedding_model, embedding_dimensions;
```

#### Find similar entities (with content via JOIN)

```sql
-- Semantic search: "Find customers similar to CUST-123"
WITH query_vector AS (
    SELECT embedding_vector
    FROM Search.entity_embedding
    WHERE entity_id = (
        SELECT party_id FROM Domain.Party_H WHERE party_key = 'CUST-123'
    )
    AND entity_type = 'PARTY'
    AND is_current = 1
)
SELECT 
    p.party_key,
    p.legal_name,
    p.description,          -- From Domain
    dt.distance AS similarity_score
FROM TD_VECTORDISTANCE (
    ON query_vector AS TargetTable PARTITION BY ANY
    ON (SELECT * FROM Search.entity_embedding WHERE entity_type = 'PARTY' AND is_current = 1) 
        AS ReferenceTable DIMENSION
    USING
        TargetFeatureColumns('embedding_vector')
        RefIDColumn('entity_id')
        RefFeatureColumns('embedding_vector')
        DistanceMeasure('cosine')
        TopK(10)
) AS dt
INNER JOIN Domain.Party_H p
    ON p.party_id = dt.reference_id
   AND p.is_current = 1
ORDER BY dt.distance;
```

### 6.2 RAG Pattern (Retrieval Augmented Generation)

```sql
-- Retrieve relevant documents for LLM context
-- Query: "What are our refund policies?"

WITH query_embedding AS (
    -- Generate embedding for query (via ONNXEmbeddings or API)
    SELECT embedding_vector FROM ... 
)
SELECT 
    d.document_id,
    d.document_title,
    d.content_text,        -- From Domain, NOT duplicated
    d.document_type,       -- From Domain
    dt.distance AS relevance_score
FROM TD_VECTORDISTANCE (
    ON query_embedding AS TargetTable PARTITION BY ANY
    ON (SELECT * FROM Search.document_embedding WHERE is_current = 1) 
        AS ReferenceTable DIMENSION
    USING
        RefIDColumn('entity_id')
        RefFeatureColumns('embedding_vector')
        DistanceMeasure('cosine')
        TopK(5)  -- Top 5 most relevant documents
) AS dt
INNER JOIN Domain.Document_H d
    ON d.document_id = dt.reference_id
   AND d.is_current = 1
ORDER BY dt.distance
QUALIFY ROW_NUMBER() OVER (ORDER BY dt.distance) <= 5;
```

---

## 7. Designer Responsibilities

### 7.1 What Designers Must Supply

| Element | Designer Supplies | Example |
|---------|-------------------|---------|
| **Entities to embed** | Which entities need embeddings | Party, Product, Document |
| **Content to embed** | Which columns to embed | description, notes, combined_text |
| **Embedding model** | Which model to use | bge-small-en-v1.5, text-embedding-ada-002 |
| **Embedding dimensions** | Model output dimensions | 384, 768, 1536 |
| **Update strategy** | When to regenerate embeddings | On insert, daily batch, on-demand |
| **Search patterns** | Expected query patterns | Find similar products, semantic document search |
| **Indexing strategy** | KMEANS, HNSW, or exact | HNSW for real-time, KMEANS for batch |

### 7.2 Embedding Model Selection

**Designer should align with established embedding models:**

**Text Embeddings**:
- BGE models (bge-small-en-v1.5, bge-base-en-v1.5) - 384/768 dims
- Sentence Transformers (all-MiniLM-L6-v2) - 384 dims
- OpenAI (text-embedding-ada-002) - 1536 dims
- NVIDIA NIM (nv-embedqa-mistral-7b-v2)

**Multi-Modal**:
- CLIP (images + text)
- Vision embeddings

**Teradata Native**:
- Available via ONNXEmbeddings in ClearScape Analytics
- Models from Teradata's Hugging Face repository

### 7.3 Design Checklist

**Before implementation:**

- [ ] Entities to embed identified
- [ ] Content columns identified (what to embed)
- [ ] Embedding model selected
- [ ] Vector dimensions determined
- [ ] Storage pattern chosen (VECTOR vs columnar)
- [ ] **NO content duplication** (IDs only verified)
- [ ] Standard views created (v_{entity}_searchable)
- [ ] Similarity search tested with TD_VectorDistance
- [ ] Integration with Domain tested (joins for content)
- [ ] Indexing strategy chosen (KMEANS, HNSW, exact)
- [ ] Update/refresh strategy defined
- [ ] Teradata version verified (20.00.26.XX+ for VECTOR)
- [ ] Module_Registry INSERT generated for this module
- [ ] Min. 3 Design_Decision INSERTs generated
- [ ] Change_Log initial release entry generated
- [ ] Min. 3 Business_Glossary terms captured
- [ ] Min. 1 Query_Cookbook recipe captured

### 7.4 Quality Criteria

**A good Search Module should:**

- ✅ Store vectors + IDs only (no content duplication)
- ✅ Use Teradata native VECTOR datatype
- ✅ Join to Domain for actual content
- ✅ Use TD_VectorDistance for similarity search
- ✅ Document embedding model and dimensions
- ✅ Support point-in-time embedding history
- ✅ Enable efficient similarity queries
- ✅ Integrate with RAG patterns
- ✅ Register itself in Memory.Module_Registry
- ✅ Capture design decisions (min. 3) into Memory.Design_Decision
- ✅ Populate Business_Glossary with embedding and search terms it introduces

### 7.5 Documentation Capture Requirements

Every Search module must populate the Memory database documentation tables as part of its design workflow. The table definitions, workflows, and full protocol are defined in the **Memory Module Design Standard, Section 8**.

**Minimum requirements:**

| Record Type | Table | Minimum | Notes |
|-------------|-------|---------|-------|
| Module_Registry | `Memory.Module_Registry` | 1 | Register this module with data_product and version |
| Design_Decision | `Memory.Design_Decision` | 3 | Key architectural and schema choices |
| Change_Log | `Memory.Change_Log` | 1 | Initial release entry (version 1.0.0) |
| Business_Glossary | `Memory.Business_Glossary` | 3 | Embedding, vector, and search terms introduced |
| Query_Cookbook | `Memory.Query_Cookbook` | 1 | Key query patterns (e.g., similarity search, RAG retrieval) |

**Typical decision categories for Search modules:**

| Decision Category | Example |
|-------------------|---------|
| `ARCHITECTURE` | Vector storage strategy (VECTOR datatype vs columnar legacy) |
| `PERFORMANCE` | ANN index choice — KMEANS vs HNSW vs exact brute-force |
| `SCHEMA` | Embedding dimensions and model selection |
| `INTEGRATION` | RAG pattern design and content join strategy |
| `OPERATIONAL` | Embedding refresh strategy (on-insert, daily batch, on-demand) |

**Decision ID prefix for this module:** `DD-SEARCH-{NNN}` (e.g., `DD-SEARCH-001`)

**Output file placement:** Write documentation capture SQL as the last numbered file in the search deployment directory (e.g., `04-search/05-documentation.sql`).

**Full protocol, SQL templates, and ID conventions:** See Memory Module Design Standard, Section 8.3 (Workflow 2 — Capture).

---

## Appendix A: Quick Reference

### Core Principles

```
✅ Store vectors + IDs only (NO content duplication)
✅ Use Teradata native VECTOR datatype
✅ Join to Domain for entity attributes/content
✅ Use TD_VectorDistance for similarity search
✅ Use KMEANS or HNSW for large datasets (100K+)
✅ Temporal tracking for embedding versioning
✅ PRIMARY INDEX only (temporal tables)
```

### Standard Table Structure

```sql
CREATE TABLE Search.entity_embedding (
    embedding_id INTEGER GENERATED ALWAYS AS IDENTITY,
    entity_id BIGINT NOT NULL,           -- ID to Domain entity
    entity_type VARCHAR(50) NOT NULL,
    embedding_vector VECTOR,              -- Native Teradata VECTOR
    embedding_dimensions INTEGER,
    embedding_model VARCHAR(100),
    generated_dts TIMESTAMP(6) WITH TIME ZONE,
    is_current BYTEINT NOT NULL DEFAULT 1
)
PRIMARY INDEX (embedding_id);
```

### Standard Views

```
✅ v_{entity}_searchable  -- Embeddings + Domain content (JOIN, no duplication)
✅ v_{entity}_current     -- Current embeddings only
```

### Similarity Search Pattern

```sql
-- Find similar + get content
SELECT domain_columns, dt.distance
FROM TD_VECTORDISTANCE(...) AS dt
JOIN Domain.Entity_H ON key  -- Get content here
```

### Teradata Vector Capabilities

```
VECTOR Datatype:     FLOAT32(n) format, n = dimensions
Distance Metrics:    Cosine, Euclidean, Manhattan
Indexing:            KMEANS (IVF-style), HNSW (graph-based)
Functions:           TD_VectorDistance, ONNXEmbeddings
Min Version:         20.00.26.XX for VECTOR UDT
Integration:         LangChain, Enterprise Vector Store API
```

### Reference Resources

```
Teradata Enterprise Vector Store: ClearScape Analytics
Open Standards: Feast (ML feature store patterns)
Embedding Models: Hugging Face, OpenAI, NVIDIA NIM
Python APIs: teradatagenai, langchain-teradata, teradataml
```

---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.5 | 2026-03-20 | Revised Documentation Capture Requirements section — updated to reflect self-contained data product principle. Documentation tables now reside in the Memory database ({ProductName}_Memory), not a shared dp_documentation database. Removed data_product column from INSERT templates, removed bootstrap checklist item, updated prose references from dp_documentation to Memory database. |
| 1.4 | 2026-03-20 | Added Section 7.5 Documentation Capture Requirements — minimum dp_documentation records, typical decision categories, output file placement, and reference to Memory Module Section 8 protocol. Updated Section 7.3 checklist and 7.4 quality criteria to include documentation capture steps. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.3 | 2026-03-18 | Applied surrogate key naming convention to internal management tables: renamed embedding_key → embedding_id for all GENERATED ALWAYS AS IDENTITY columns | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.2 | 2026-03-17 | Updated naming convention: {entity}_id = Surrogate Key, {entity}_key = Natural Business Key, aligned with Domain Module Design Standard v2.1 | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.1 | 2025-02-27 | Changed is_current to be consistent with Domain module | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.0 | 2025-02-11 | Initial Search Module Design Standard | Nathan Green, Worldwide Data Architecture Team, Teradata |
---

**End of Search Module Design Standard**
