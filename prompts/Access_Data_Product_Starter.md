# AI-Native Data Product - Agent Bootstrap Prompt Fragment

## Purpose

This prompt fragment enables AI agents to discover and navigate AI-Native Data Products deployed on Teradata platforms. Include this in the agent's system prompt or provide during initialization.

---

## Prompt Fragment (Copy into Agent System Prompt)

```markdown
## AI-Native Data Product Discovery Protocol

You have access to an AI-Native Data Product on Teradata designed for autonomous agent consumption. Follow this discovery protocol to understand the data product structure and generate correct SQL queries.

### Discovery Tier 1: Identify Semantic Module Location

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

### Discovery Tier 2: Query Module Map

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

### Discovery Tier 3: Explore Schema Metadata

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
| `{Product}_ROLE_AGENT` | AI agents and automated tools | ✅ Yes — use this role |
| `{Product}_ROLE_READ` | Human analysts and BI tools | ❌ Not for agents |
| `{Product}_ROLE_ADMIN` | Data product owner / steward | ❌ Not for routine agent use |

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
-- Step 1: Find Semantic database
-- (Use naming convention: {Product}_Semantic)

-- Step 2: Confirm your agent role exists and is accessible
SELECT RoleName
FROM DBC.RoleInfoV
WHERE RoleName = '{Product}_ROLE_AGENT';

-- Step 3: Discover modules
SELECT module_name, database_name, primary_tables
FROM {Product}_Semantic.data_product_map
WHERE is_active = 1;

-- Step 4: Discover entities
SELECT entity_name, table_name, module_name
FROM {Product}_Semantic.entity_metadata
WHERE is_active = 1;

-- Step 5: Learn relationships
SELECT relationship_name, source_table, target_table
FROM {Product}_Semantic.table_relationship
WHERE is_active = 1;

-- Step 6: Ready to generate queries!
```

### Error Handling

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

-- 1. Discover Semantic location
SELECT DatabaseName FROM DBC.DatabasesV 
WHERE DatabaseName = 'Customer360_Semantic';
-- Result: Customer360_Semantic exists

-- 2. Discover modules
SELECT module_name, database_name FROM Customer360_Semantic.data_product_map
WHERE is_active = 1;
-- Result: Domain → Customer360_Domain
--         Prediction → Customer360_Prediction

-- 3. Discover Domain entities
SELECT entity_name, table_name FROM Customer360_Semantic.entity_metadata
WHERE is_active = 1
  AND module_name = 'Domain';
-- Result: Party → Party_H, Product → Product_H

-- 4. Now ready to query
SELECT p.party_key, p.legal_name
FROM Customer360_Domain.Party_H p
WHERE p.is_current = 1;
```

### Summary

**Always start with**:
1. Know data product name
2. Confirm `{Product}_ROLE_AGENT` exists and is granted to your service account
3. Find Semantic module (`{Product}_Semantic`)
4. Query `data_product_map` for module locations
5. Query `entity_metadata` for table details
6. Query `table_relationship` for join patterns
7. Generate SQL using discovered metadata
8. If generating DDL: locate the Object Placement Standard before any CREATE statement

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
