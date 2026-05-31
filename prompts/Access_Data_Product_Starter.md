# AI-Native Data Product - Agent Bootstrap Prompt Fragment

## Purpose

This prompt fragment enables AI agents to discover and navigate AI-Native Data Products deployed on Teradata platforms. Include this in the agent's system prompt or provide during initialization.

---

## Prompt Fragment (Copy into Agent System Prompt)

```markdown
## AI-Native Data Product Discovery Protocol

You have access to an AI-Native Data Product on Teradata designed for autonomous agent consumption. Follow this discovery protocol to understand the data product structure and generate correct SQL queries.

### Discovery Tier 1: Read the Data Product Orientation Manifest

**Best starting point**: If your environment exposes MCP resources, list products and read the product manifest before deriving database names or querying metadata tables. The manifest tells you where the contract, Semantic model, policy, quality, lineage, physical map, and approved data access surfaces are.

```text
/resources
  /products
  /products/{product_id}/manifest
  /products/{product_id}/contract
  /products/{product_id}/semantic
  /products/{product_id}/lineage
  /products/{product_id}/quality
  /products/{product_id}/policy
  /products/{product_id}/physical-map
```

Read the manifest first. Follow its `recommended_navigation` order:

1. contract
2. semantic_model
3. policy
4. quality
5. lineage
6. data_access

Do not expose or query tables first. Discover the product first, then the contract and meaning, then the approved data path.

**Registry fallback**: If MCP resources are not available, use the known Semantic module table database from deployment configuration or standard naming convention, then query the product registry before navigating module metadata or data. The registry backs the orientation manifest and lives in the Semantic module.

```sql
-- Discover current data product contract and approved entrypoint
SELECT product_id,
       product_name,
       product_version,
       semantic_database,
       memory_database,
       observability_database,
       approved_entrypoint,
       approved_access_mode
FROM {SemanticDatabase}.data_product_registry
WHERE is_active = 1
  AND is_deleted = 0
  AND product_name = '{DataProductName}';
```

**Expected result**: Product metadata and the Semantic database name to use for metadata navigation.

### Discovery Tier 2: Identify Semantic Module Location

**Given**: Data product name (e.g., "Customer360", "FraudDetection")

**Standard Convention**: Semantic module database follows pattern `{DataProductName}_Semantic`

**Your first query**:
```sql
-- Discover if Semantic module exists
SELECT DatabaseName 
FROM DBC.DatabasesV 
WHERE DatabaseName LIKE '{DataProductName}_Semantic';
```

**Expected result**: Database name for Semantic module (e.g., "Customer360_Semantic")

### Discovery Tier 3: Query Module Map

**Once you know Semantic database location, query the module map**:

```sql
-- Discover all deployed modules
SELECT 
    module_name,
    module_description,
    database_name,
    naming_pattern,
    primary_tables,
    primary_views,
FROM {SemanticDatabase}.data_product_map
WHERE is_active = 1
ORDER BY module_name;
```

**Note**: All `is_*` flags in AI-Native Data Products are `BYTEINT` (1 = true, 0 = false), not `CHAR`. Filtering with `'Y'` / `'N'` will fail with Error 3535 (character to numeric conversion). Always filter with integer `1` / `0`.

**This tells you**:
- Which modules are deployed (Domain, Prediction, Search, Memory, Observability)
- Where each module lives (database names)
- Key tables in each module (entry points)
- Naming pattern used (separate databases vs single database with prefixes)

### Discovery Tier 4: Explore Schema Metadata

**Now you can query Semantic module tables for detailed schema knowledge**:

```sql
-- What entities (tables) exist?
SELECT entity_name, module_name, table_name, view_name
FROM {SemanticDatabase}.entity_metadata
WHERE is_active = 1;

-- What columns does Party_H have?
SELECT column_name, business_description, is_pii
FROM {SemanticDatabase}.column_metadata
WHERE table_name = 'Party_H';

-- How do tables relate (for joins)?
SELECT relationship_name, source_table, target_table, 
       source_column, target_column, cardinality
FROM {SemanticDatabase}.table_relationship
WHERE is_active = 1;

-- How do I join Party_H to Transaction_H (multi-hop)?
SELECT hop_count, path_tables, path_joins
FROM {SemanticDatabase}.v_relationship_paths
WHERE source_table = 'Party_H' 
  AND target_table = 'Transaction_H'
ORDER BY hop_count;
```

### Key Principles for AI-Native Data Products

**1. Entity = Table** (not row instance)
- "Party" entity = Party_H table
- "Product" entity = Product_H table

**2. Modules Store Minimal Data**
- Domain: Business data (customers, products, transactions)
- Other modules: Keys/references only (join to Domain for full content)
- Prediction: Engineered features (not raw domain values)
- Search: Vector embeddings + entity keys (join to Domain for content)
- Memory: Agent state + table references (not instance keys)
- Observability: Events/metrics + aggregate counts (not instance data)

**3. Use Views to Join Modules**
- Don't expect duplicated data across modules
- Query views like `v_customer_features_enriched` for complete context
- Views join Domain + module data efficiently

**4. Temporal Queries**
- Most tables use temporal tracking (valid_from_dts, valid_to_dts, is_current)
- For current state: `WHERE is_current = 1 AND is_deleted = 0`
- For historical: Use temporal range queries
- All `is_*` flags are `BYTEINT`; always compare with `1` / `0`, never `'Y'` / `'N'`

**5. Table References in Metadata**
- Memory and Observability use VARCHAR comma-separated table lists
- Format: 'Domain.Party_H, Prediction.customer_features'
- Query with LIKE: `WHERE referenced_tables LIKE '%Party_H%'`

### Access Roles

Every AI-Native Data Product creates three standard roles:

| Role | Purpose | Your connecting user should hold |
|------|---------|----------------------------------|
| `{Product}_ROLE_AGENT` | AI agents and automated tools. SELECT on module access databases, plus controlled INSERT write-back to Memory and Observability. | ✅ Yes — use this role |
| `{Product}_ROLE_READ` | Human analysts and BI tools. SELECT-only access. | ❌ Not for agents |
| `{Product}_ROLE_ADMIN` | Data product owner / steward. Administrative access. | ❌ Not for routine agent use |

`{Product}_ROLE_AGENT` must not write to Domain or Semantic. Domain is governed by source-system
ingestion and ETL pipelines; Semantic metadata is governed by the data product design process. Agent
write-back is limited to Memory (conversation history, learned strategies, design insights) and
Observability (usage events, quality feedback).

**If you receive `Error 3523` (no SELECT access):** The Access Layer may not have been deployed
yet, or your service account has not been granted `{Product}_ROLE_AGENT`. Do not attempt to work
around this by requesting direct grants to individual databases. Ask the data product owner to run
Phase 1.5 and Phase 2.5 of the Access Layer DCL (`00-access/{Product}_access_layer.dcl`).

**If you need to generate DDL (not just query):** Before writing any CREATE statement, locate the
organisation's Object Placement Standard implementation. It specifies which database each object
type belongs in. Never assume co-location or invent database names.

---

### Standard Discovery Queries (Execute These First)

When starting work on a new data product:

```sql
-- Step 1: Discover product contract and approved entrypoint if registry exists
SELECT product_id, semantic_database, approved_entrypoint, approved_access_mode
FROM {SemanticDatabase}.data_product_registry
WHERE is_active = 1
  AND is_deleted = 0
  AND product_name = '{Product}';

-- Step 2: Confirm your agent role exists and is accessible
SELECT RoleName
FROM DBC.RoleInfoV
WHERE RoleName = '{Product}_ROLE_AGENT';

-- Step 3: If no registry row is available, find Semantic database by convention
-- (Use naming convention: {Product}_Semantic)

-- Step 4: Discover modules
SELECT module_name, database_name, primary_tables
FROM {Product}_Semantic.data_product_map
WHERE is_active = 1;

-- Step 5: Discover entities
SELECT entity_name, table_name, module_name
FROM {Product}_Semantic.entity_metadata
WHERE is_active = 1;

-- Step 6: Learn relationships
SELECT relationship_name, source_table, target_table
FROM {Product}_Semantic.table_relationship
WHERE is_active = 1;

-- Step 7: Ready to generate queries through approved_entrypoint!
```

### Error Handling

**If data_product_registry doesn't exist or has no row for the product**:
- Fall back to Semantic database discovery by convention
- Continue with `data_product_map`
- Prefer the registry when it is later deployed

**If data_product_map doesn't exist**:
- Data product may not follow AI-Native standards
- Fall back to standard database discovery (DBC.TablesV)
- May need human guidance

**If Semantic database doesn't exist**:
- Query DBC.DatabasesV for databases matching pattern
- May be using single-database approach with prefixes
- Look for tables like S_entity_metadata, S_table_relationship

### Example Complete Discovery Session

```sql
-- Given: Work with "Customer360" data product

-- 1. Discover product registry row if available
SELECT product_id, semantic_database, approved_entrypoint
FROM {SemanticDatabase}.data_product_registry
WHERE is_active = 1
  AND is_deleted = 0
  AND product_name = 'Customer360';
-- Result: semantic_database = Customer360_Semantic

-- 2. Discover Semantic location if registry is not available
SELECT DatabaseName FROM DBC.DatabasesV 
WHERE DatabaseName = 'Customer360_Semantic';
-- Result: Customer360_Semantic exists

-- 3. Discover modules
SELECT module_name, database_name FROM Customer360_Semantic.data_product_map
WHERE is_active = 1;
-- Result: Domain → Customer360_Domain
--         Prediction → Customer360_Prediction

-- 4. Discover Domain entities
SELECT entity_name, table_name FROM Customer360_Semantic.entity_metadata
WHERE is_active = 1
  AND module_name = 'Domain';
-- Result: Party → Party_H, Product → Product_H

-- 5. Now ready to query via approved entrypoint
SELECT p.party_key, p.legal_name
FROM Customer360_Domain.Party_H p
WHERE p.is_current = 1;
```

### Summary

**Always start with**:
1. Know data product name
2. Confirm `{Product}_ROLE_AGENT` exists and is granted to your service account
3. Read the MCP product manifest when available
4. Follow manifest navigation: contract → semantic model → policy → quality → lineage → data access
5. Query `{SemanticDatabase}.data_product_registry` if MCP resources are not available
6. Find Semantic module (`{Product}_Semantic`) if no registry row is available
7. Query `data_product_map` for module locations
8. Query `entity_metadata` and `table_relationship` for table details and join patterns
9. Generate SQL using discovered metadata and the approved entrypoint
10. If generating DDL: locate the Object Placement Standard before any CREATE statement

This protocol enables fully autonomous navigation of any AI-Native Data Product on Teradata.
```

---

## Notes for Prompt Engineers

**When to include this fragment**:
- Agent will work with Teradata AI-Native Data Products
- Agent needs to discover structure autonomously
- Agent will generate SQL queries

**Customization points**:
- Replace `{DataProductName}` with actual product name
- Or leave as template for agent to substitute

**Integration with existing prompts**:
- Include in agent system prompt
- Or provide as initialization context
- Can be combined with tool definitions (Teradata MCP server, etc.)

---

**This prompt fragment is reusable across any AI-Native Data Product deployment.**
