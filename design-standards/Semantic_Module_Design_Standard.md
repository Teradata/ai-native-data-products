# Semantic Module Design Standard
## AI-Native Data Product Architecture - Version 2.11 (Tested & Validated)

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 2.11 |
| **Status** | STANDARD - Tested on Teradata |
| **Last Updated** | 2026-07-18 |
| **Owner** | Nathan Green, Worldwide Data Architecture Team, Teradata |
| **Scope** | Semantic Module (Knowledge & Meaning) |
| **Type** | Design Standard (Structural Requirements) |
| **Testing** | Validated on Teradata v20.0 |

---

## Table of Contents

1. [AI-Native Semantic Module Overview](#1-ai-native-semantic-module-overview)
2. [Module Scope and Boundaries](#2-module-scope-and-boundaries)
3. [Core Metadata Tables](#3-core-metadata-tables)
4. [Table-Level Relationship Metadata](#4-table-level-relationship-metadata)
5. [Multi-Hop Path Discovery](#5-multi-hop-path-discovery)
6. [Agent Discovery and Querying](#6-agent-discovery-and-querying)
7. [Integration with Other Modules](#7-integration-with-other-modules)
8. [Designer Responsibilities](#8-designer-responsibilities)

---

## 1. AI-Native Semantic Module Overview

### 1.1 Key Terminology

- **Entity** = Table (e.g., Party_H is an entity)
- **Attribute** = Column (e.g., party_id is an attribute)
- **Relationship** = How tables join (e.g., PartyAddress.party_id -> Party.party_id)

### 1.2 Primary Purpose: Enable Correct SQL Generation

Semantic module helps agents write correct SQL by answering:
1. What entities (tables) exist?
2. What attributes (columns) do entities have?
3. How do entities (tables) relate?
4. How do I join table A to table B? (including multi-hop)

---

## 2. Module Scope and Boundaries

**IN SCOPE**: Schema metadata (hundreds of rows)
**OUT OF SCOPE**: Instance data (millions of rows)

---

## 3. Core Metadata Tables

### 3.1 entity_metadata

```sql
CREATE TABLE Semantic.entity_metadata (
    entity_metadata_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    entity_name VARCHAR(128) NOT NULL,
    entity_description VARCHAR(1000) NOT NULL,
    module_name VARCHAR(50) NOT NULL,
    database_name VARCHAR(128),
    table_name VARCHAR(128) NOT NULL,
    view_name VARCHAR(128),
    surrogate_key_column VARCHAR(128),
    natural_key_column VARCHAR(128),
    temporal_pattern VARCHAR(50),
    current_flag_column VARCHAR(128),
    deleted_flag_column VARCHAR(128),
    industry_standard VARCHAR(50),
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (entity_metadata_id);

COMMENT ON TABLE Semantic.entity_metadata IS 
'Entity (table) catalog - describes all tables across all modules for agent discovery';

COMMENT ON COLUMN Semantic.entity_metadata.entity_metadata_id IS 
'Surrogate key for entity metadata record';

COMMENT ON COLUMN Semantic.entity_metadata.entity_name IS 
'Business name of entity - e.g., Party, Product, Customer';

COMMENT ON COLUMN Semantic.entity_metadata.entity_description IS 
'Business description of entity purpose and scope';

COMMENT ON COLUMN Semantic.entity_metadata.module_name IS 
'Module where entity resides - Domain, Prediction, Search, Memory, Observability';

COMMENT ON COLUMN Semantic.entity_metadata.database_name IS 
'Physical database name where table is located';

COMMENT ON COLUMN Semantic.entity_metadata.table_name IS 
'Physical table name - e.g., Party_H, Product_H';

COMMENT ON COLUMN Semantic.entity_metadata.view_name IS 
'Standard current view name for accessing current records - e.g., Party_Current';

COMMENT ON COLUMN Semantic.entity_metadata.surrogate_key_column IS 
'Name of surrogate key column - e.g., party_id, product_id';

COMMENT ON COLUMN Semantic.entity_metadata.natural_key_column IS 
'Name of natural business key column - e.g., party_key, product_key';

COMMENT ON COLUMN Semantic.entity_metadata.temporal_pattern IS 
'Temporal tracking pattern used - BI_TEMPORAL, TYPE_2_SCD, NONE';

COMMENT ON COLUMN Semantic.entity_metadata.current_flag_column IS 
'Name of current version flag column - typically is_current';

COMMENT ON COLUMN Semantic.entity_metadata.deleted_flag_column IS 
'Name of soft delete flag column - typically is_deleted';

COMMENT ON COLUMN Semantic.entity_metadata.industry_standard IS 
'Industry data model standard used - FIBO, HL7, CUSTOM, etc.';

COMMENT ON COLUMN Semantic.entity_metadata.is_active IS 
'Metadata active indicator - Y = entity is active, N = deprecated';

COMMENT ON COLUMN Semantic.entity_metadata.created_at IS 
'Timestamp when metadata record was created';

COMMENT ON COLUMN Semantic.entity_metadata.updated_at IS 
'Timestamp when metadata record was last updated';
```

### 3.2 column_metadata

```sql
CREATE TABLE Semantic.column_metadata (
    column_metadata_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    database_name VARCHAR(128) NOT NULL,
    table_name VARCHAR(128) NOT NULL,
    column_name VARCHAR(128) NOT NULL,
    business_description VARCHAR(1000),
    is_pii BYTEINT NOT NULL DEFAULT 0,
    is_sensitive BYTEINT NOT NULL DEFAULT 0,
    data_classification VARCHAR(50),
    is_required BYTEINT NOT NULL DEFAULT 1,
    data_type VARCHAR(100),
    allowed_values_json JSON,
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (column_metadata_id);

COMMENT ON TABLE Semantic.column_metadata IS 
'Column (attribute) metadata - describes column meanings, data classifications, and validation rules';

COMMENT ON COLUMN Semantic.column_metadata.column_metadata_id IS 
'Surrogate key for column metadata record';

COMMENT ON COLUMN Semantic.column_metadata.database_name IS 
'Physical database name where table is located';

COMMENT ON COLUMN Semantic.column_metadata.table_name IS 
'Physical table name containing this column';

COMMENT ON COLUMN Semantic.column_metadata.column_name IS 
'Physical column name';

COMMENT ON COLUMN Semantic.column_metadata.business_description IS 
'Business meaning and purpose of column - explains what the data represents';

COMMENT ON COLUMN Semantic.column_metadata.is_pii IS 
'Personally Identifiable Information flag - Y = contains PII, N = no PII - used for privacy compliance';

COMMENT ON COLUMN Semantic.column_metadata.is_sensitive IS 
'Sensitive data flag - Y = sensitive (SSN, credit card, etc.), N = not sensitive - used for security controls';

COMMENT ON COLUMN Semantic.column_metadata.data_classification IS 
'Data classification level - PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED - determines access controls';

COMMENT ON COLUMN Semantic.column_metadata.is_required IS 
'Required field indicator - Y = NOT NULL constraint, N = nullable - indicates mandatory data';

COMMENT ON COLUMN Semantic.column_metadata.data_type IS 
'Physical data type - VARCHAR, INTEGER, DECIMAL, DATE, TIMESTAMP, etc.';

COMMENT ON COLUMN Semantic.column_metadata.allowed_values_json IS 
'Allowed values constraint - JSON array of valid values for constrained columns';

COMMENT ON COLUMN Semantic.column_metadata.is_active IS 
'Metadata active indicator - Y = column is active, N = deprecated or removed';

COMMENT ON COLUMN Semantic.column_metadata.created_at IS 
'Timestamp when metadata record was created';

COMMENT ON COLUMN Semantic.column_metadata.updated_at IS 
'Timestamp when metadata record was last updated';
```

### 3.3 naming_standard

```sql
CREATE TABLE Semantic.naming_standard (
    naming_standard_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    standard_type VARCHAR(50) NOT NULL,
    standard_value VARCHAR(100) NOT NULL,
    meaning VARCHAR(500) NOT NULL,
    usage_guidance VARCHAR(1000),
    applies_to VARCHAR(50),
    examples VARCHAR(1000),
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (naming_standard_id);

COMMENT ON TABLE Semantic.naming_standard IS 
'Naming convention standards - documents naming patterns for agent interpretation';

COMMENT ON COLUMN Semantic.naming_standard.naming_standard_id IS 
'Surrogate key for naming standard record';

COMMENT ON COLUMN Semantic.naming_standard.standard_type IS 
'Type of naming convention - SUFFIX, PREFIX, PATTERN, ABBREVIATION';

COMMENT ON COLUMN Semantic.naming_standard.standard_value IS 
'The actual naming element - e.g., _H, _id, is_, dts';

COMMENT ON COLUMN Semantic.naming_standard.meaning IS 
'What this naming element means - e.g., _H means history table with temporal tracking';

COMMENT ON COLUMN Semantic.naming_standard.usage_guidance IS 
'How and when to apply this naming convention';

COMMENT ON COLUMN Semantic.naming_standard.applies_to IS 
'What this convention applies to - TABLE, COLUMN, VIEW, ALL';

COMMENT ON COLUMN Semantic.naming_standard.examples IS 
'Example usage of this naming convention';

COMMENT ON COLUMN Semantic.naming_standard.is_active IS 
'Standard active indicator - Y = currently used, N = deprecated';

COMMENT ON COLUMN Semantic.naming_standard.created_at IS 
'Timestamp when naming standard was documented';
```

### 3.4 data_product_registry (Product Discovery)

**Purpose**: Enable agents and MCP clients to discover the data product, its current metadata contract, and its approved data access entrypoint before navigating module metadata or querying data.

`data_product_registry` is the product-level storage anchor for the **Data Product Orientation Layer**. It complements `data_product_map`: agents and MCP clients discover the product and read its manifest first, then use the manifest to locate the product's contract, Semantic model, Memory guidance, Observability evidence, policy, quality, lineage, physical map, and approved data access surfaces. They then query `data_product_map` inside the Semantic module for deployed module locations.

The key principle is **product first, not tables first**. Clients must not start by guessing physical databases or listing tables.

```sql
CREATE MULTISET TABLE governance.data_product_registry
(
    product_id             VARCHAR(128) NOT NULL
   ,product_name           VARCHAR(256) NOT NULL
   ,product_version        VARCHAR(32) NOT NULL
   ,product_description    VARCHAR(1000)
   ,product_status         VARCHAR(32) NOT NULL
   ,owner_team             VARCHAR(256)
   ,semantic_database      VARCHAR(128)
   ,memory_database        VARCHAR(128)
   ,observability_database VARCHAR(128)
   ,manifest_json          CLOB
   ,contract_uri           VARCHAR(1000)
   ,semantic_uri           VARCHAR(1000)
   ,quality_uri            VARCHAR(1000)
   ,lineage_uri            VARCHAR(1000)
   ,policy_uri             VARCHAR(1000)
   ,glossary_uri           VARCHAR(1000)
   ,query_cookbook_uri     VARCHAR(1000)
   ,approved_entrypoint    VARCHAR(1000)
   ,approved_access_mode   VARCHAR(32)
   ,is_active              BYTEINT NOT NULL
   ,is_deleted             BYTEINT NOT NULL
   ,created_at             TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
   ,updated_at             TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_id);

COMMENT ON TABLE governance.data_product_registry IS
'Product-level registry - agents and MCP clients discover current data products, metadata contracts, and approved access entrypoints';

COMMENT ON COLUMN governance.data_product_registry.product_id IS
'Stable product identifier used by agents, MCP resources, manifests, lineage, policies, and contracts';

COMMENT ON COLUMN governance.data_product_registry.product_name IS
'Human-readable data product name';

COMMENT ON COLUMN governance.data_product_registry.product_version IS
'Current data product contract or release version';

COMMENT ON COLUMN governance.data_product_registry.product_description IS
'Business description of the product purpose, scope, and intended consumers';

COMMENT ON COLUMN governance.data_product_registry.product_status IS
'Lifecycle status - DRAFT, ACTIVE, DEPRECATED, or RETIRED';

COMMENT ON COLUMN governance.data_product_registry.owner_team IS
'Owning team or steward responsible for product contract, policy, and support';

COMMENT ON COLUMN governance.data_product_registry.semantic_database IS
'Semantic module database to query after registry discovery';

COMMENT ON COLUMN governance.data_product_registry.memory_database IS
'Memory module database containing Business_Glossary, Query_Cookbook, and design memory';

COMMENT ON COLUMN governance.data_product_registry.observability_database IS
'Observability module database containing lineage, quality, and usage telemetry where deployed';

COMMENT ON COLUMN governance.data_product_registry.manifest_json IS
'Machine-readable product orientation manifest for agents and MCP clients';

COMMENT ON COLUMN governance.data_product_registry.contract_uri IS
'URI for the product contract or external contract document';

COMMENT ON COLUMN governance.data_product_registry.semantic_uri IS
'URI for Semantic metadata, an MCP resource, or related documentation';

COMMENT ON COLUMN governance.data_product_registry.quality_uri IS
'URI for data quality rules, reports, or MCP resource';

COMMENT ON COLUMN governance.data_product_registry.lineage_uri IS
'URI for lineage metadata, graph, or MCP resource';

COMMENT ON COLUMN governance.data_product_registry.policy_uri IS
'URI for policy, usage, classification, or access-control guidance';

COMMENT ON COLUMN governance.data_product_registry.glossary_uri IS
'URI for business glossary metadata, typically backed by Memory.Business_Glossary';

COMMENT ON COLUMN governance.data_product_registry.query_cookbook_uri IS
'URI for validated query recipes, typically backed by Memory.Query_Cookbook';

COMMENT ON COLUMN governance.data_product_registry.approved_entrypoint IS
'Approved first data access surface, such as an access view, semantic view, or MCP tool resource';

COMMENT ON COLUMN governance.data_product_registry.approved_access_mode IS
'Approved access mode - VIEW, MCP_TOOL, SEMANTIC_QUERY, or site-defined equivalent';

COMMENT ON COLUMN governance.data_product_registry.is_active IS
'Registry row active indicator - 1 = current and discoverable, 0 = inactive';

COMMENT ON COLUMN governance.data_product_registry.is_deleted IS
'Soft delete indicator - 1 = logically deleted and hidden from discovery, 0 = discoverable when active';

COMMENT ON COLUMN governance.data_product_registry.created_at IS
'Timestamp when registry record was created';

COMMENT ON COLUMN governance.data_product_registry.updated_at IS
'Timestamp when registry record was last updated';
```

#### Data Product Orientation Layer

MCP servers should expose the orientation layer as resources first and tools second.

**Resources provide context**: product lists, manifests, contracts, schemas, policies, quality evidence, lineage, and physical maps.

**Tools perform actions**: searching products, describing a product, choosing an entrypoint, querying approved data, or explaining an access path.

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

/tools
  search_data_products
  describe_data_product
  get_recommended_entrypoint
  query_product_data
  explain_access_path
```

**Metadata-first handshake**:

1. Client asks what products are available.
2. Server returns products and manifest resources.
3. Client reads the selected product manifest.
4. Server recommends navigation: contract, semantic model, policy, quality, lineage, physical map, approved data access.
5. Client queries data only through the approved access path.

#### Discovery Manifest

The manifest is the first resource an MCP client should read after selecting a product. It can be stored in `manifest_json` and exposed as `/products/{product_id}/manifest`.

```yaml
data_product_id: call_centre.customer_experience
name: Customer Experience Data Product
version: 1.0.0

entrypoints:
  orientation: mcp://products/call_centre/customer_experience/manifest
  contract: mcp://products/call_centre/customer_experience/contract
  semantic_model: mcp://products/call_centre/customer_experience/semantic
  lineage: mcp://products/call_centre/customer_experience/lineage
  quality: mcp://products/call_centre/customer_experience/quality
  policy: mcp://products/call_centre/customer_experience/access-policy
  data_access: mcp://products/call_centre/customer_experience/data

recommended_navigation:
  - contract
  - semantic_model
  - policy
  - quality
  - lineage
  - data_access
```

The manifest should tell the agent what the product is, what it means, what it trusts, what the agent may access, and how to proceed.

**MCP Catalog Query**:
```sql
-- MCP client discovers all current, discoverable data products
SELECT product_id,
       product_name,
       product_version,
       product_description,
       product_status,
       owner_team,
       semantic_database,
       memory_database,
       observability_database,
       contract_uri,
       semantic_uri,
       quality_uri,
       lineage_uri,
       policy_uri,
       glossary_uri,
       query_cookbook_uri,
       approved_entrypoint,
       approved_access_mode
FROM governance.data_product_registry
WHERE is_active = 1
  AND is_deleted = 0;
```

**Expected MCP resource shape**:

```text
mcp://products
mcp://products/{product_id}/manifest
mcp://products/{product_id}/contract
mcp://products/{product_id}/semantic
mcp://products/{product_id}/lineage
mcp://products/{product_id}/quality
mcp://products/{product_id}/access-policy
mcp://products/{product_id}/physical-map
mcp://products/{product_id}/data
```

### 3.5 data_product_map (Module Discovery)

**Purpose**: Enable agents to discover which modules are deployed and where they are physically located

```sql
CREATE TABLE Semantic.data_product_map (
    module_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- Module identification
    module_name VARCHAR(50) NOT NULL,
    module_description VARCHAR(1000),
    module_purpose VARCHAR(500),
    
    -- Physical location (CRITICAL for agent discovery)
    database_name VARCHAR(128) NOT NULL,
    naming_pattern VARCHAR(20),  -- 'SEPARATE_DB' or 'SINGLE_DB_PREFIX'
    table_prefix VARCHAR(10),    -- If using prefix pattern
    
    -- Entry points
    -- DEPRECATED (v2.8): CSV entry-point columns are superseded by the
    -- data_product_map_primary_objects child relation (Section 3.6).
    -- Retained for backward compatibility only; do not populate for new
    -- products and do not parse in new integrations.
    primary_tables VARCHAR(500),  -- DEPRECATED - see Section 3.6
    primary_views VARCHAR(500),   -- DEPRECATED - see Section 3.6
    
    -- Module metadata
    module_version VARCHAR(20),
    deployment_status VARCHAR(20),  -- 'DEPLOYED', 'PLANNED', 'DEPRECATED'
    deployed_dts TIMESTAMP(6) WITH TIME ZONE,
    
    -- Status
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (module_id);

COMMENT ON TABLE Semantic.data_product_map IS 
'Module registry - agents discover deployed modules and their physical locations';

COMMENT ON COLUMN Semantic.data_product_map.module_id IS 
'Surrogate key for module registry record';

COMMENT ON COLUMN Semantic.data_product_map.module_name IS 
'Module name - Domain, Semantic, Prediction, Search, Memory, Observability';

COMMENT ON COLUMN Semantic.data_product_map.module_description IS 
'Business description of module purpose and scope';

COMMENT ON COLUMN Semantic.data_product_map.module_purpose IS 
'Concise statement of module purpose';

COMMENT ON COLUMN Semantic.data_product_map.database_name IS 
'Physical Teradata database name where module is deployed - critical for agent discovery';

COMMENT ON COLUMN Semantic.data_product_map.naming_pattern IS 
'Naming approach used - SEPARATE_DB (one database per module) or SINGLE_DB_PREFIX (all modules in one database with prefixes)';

COMMENT ON COLUMN Semantic.data_product_map.table_prefix IS 
'Table name prefix if using SINGLE_DB_PREFIX pattern - e.g., D_, P_, S_';

COMMENT ON COLUMN Semantic.data_product_map.primary_tables IS 
'DEPRECATED (v2.8) - superseded by data_product_map_primary_objects; retained for backward compatibility only';

COMMENT ON COLUMN Semantic.data_product_map.primary_views IS 
'DEPRECATED (v2.8) - superseded by data_product_map_primary_objects; retained for backward compatibility only';

COMMENT ON COLUMN Semantic.data_product_map.module_version IS 
'Version of module design standard used';

COMMENT ON COLUMN Semantic.data_product_map.deployment_status IS 
'Current deployment status - DEPLOYED, PLANNED, DEPRECATED';

COMMENT ON COLUMN Semantic.data_product_map.deployed_dts IS 
'Timestamp when module was deployed to production';

COMMENT ON COLUMN Semantic.data_product_map.is_active IS 
'Module active indicator - Y = module is active, N = deprecated';

COMMENT ON COLUMN Semantic.data_product_map.created_at IS 
'Timestamp when module registry record was created';

COMMENT ON COLUMN Semantic.data_product_map.updated_at IS 
'Timestamp when module registry record was last updated';


-- Example: Customer360 using separate databases per module
INSERT INTO Semantic.data_product_map VALUES
(DEFAULT, 'Domain', 'Core business entities and source of truth', 'Business entity storage',
 'Customer360_Domain', 'SEPARATE_DB', NULL, 'Party_H, Product_H, Transaction_H', 'Party_Current, Product_Current',
 '2.0', 'DEPLOYED', CURRENT_TIMESTAMP(6), 'Y', CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));

INSERT INTO Semantic.data_product_map VALUES
(DEFAULT, 'Semantic', 'Schema metadata and relationships', 'Schema knowledge layer',
 'Customer360_Semantic', 'SEPARATE_DB', NULL, 'entity_metadata, table_relationship, data_product_map', 'v_entity_catalog, v_relationship_paths',
 '2.0', 'DEPLOYED', CURRENT_TIMESTAMP(6), 'Y', CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));

INSERT INTO Semantic.data_product_map VALUES
(DEFAULT, 'Prediction', 'Feature store and ML predictions', 'ML feature storage',
 'Customer360_Prediction', 'SEPARATE_DB', NULL, 'customer_features, model_prediction', 'v_customer_features_current',
 '1.0', 'DEPLOYED', CURRENT_TIMESTAMP(6), 'Y', CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6));
```

**Agent Discovery Query**:
```sql
-- Agent discovers all deployed modules
SELECT module_name, database_name, deployment_status
FROM Semantic.data_product_map
WHERE is_active = 1
ORDER BY module_name;
```

Entry-point objects are discovered through the child relation in
Section 3.6 — never by parsing `primary_tables` / `primary_views`.

### 3.6 data_product_map_primary_objects (Primary Object Discovery)

**Purpose**: Give agents an authoritative, fully qualified identity for
every primary object of every module — one row per object, no CSV parsing,
no name derivation.

**Problem this solves** (issue #14): the deprecated `primary_tables` /
`primary_views` columns stored multi-valued CSV lists that cannot be
validated relationally, and a single module-level `database_name` cannot
identify objects deployed across different databases or security layers.
Agents were forced to parse strings and construct names from naming
conventions, which can select physical tables where governed views should
be used.

```sql
CREATE TABLE Semantic.data_product_map_primary_objects (
    primary_object_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,

    -- Logical parent reference to data_product_map.module_id.
    -- No physical FK constraint required; orphans are detected by
    -- deployment checks and trust validation.
    module_id INTEGER NOT NULL,

    -- Exact deployed identity. The canonical agent-facing name is
    -- database_name.object_name - used verbatim, never derived.
    database_name VARCHAR(128) CHARACTER SET UNICODE NOT NULL,
    object_name VARCHAR(128) CHARACTER SET UNICODE NOT NULL,

    -- Classification
    object_type VARCHAR(50) NOT NULL,   -- 'TABLE', 'VIEW', 'PROCEDURE', 'FUNCTION'
    object_role VARCHAR(50) NOT NULL,   -- controlled vocabulary (below)
    usage_guidance VARCHAR(500) CHARACTER SET UNICODE,
    table_kind CHAR(1),                 -- Teradata DBC.TablesV.TableKind code (optional)

    -- Lifecycle - canonical columns per the Temporal & Lifecycle
    -- Metadata Standard. is_active semantics:
    -- 1 = registration is live and discoverable; 0 = retired from
    -- discovery. Independent of whether the object physically exists
    -- (existence is a validation concern, not a lifecycle state).
    is_active BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (module_id);

COMMENT ON TABLE Semantic.data_product_map_primary_objects IS 
'Primary object registry - one row per agent-facing object per module; authoritative fully qualified identities (issue #14)';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.primary_object_id IS 
'Surrogate key for primary object registration record';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.module_id IS 
'Logical parent reference to data_product_map.module_id - validated by trust checks, no physical FK';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.database_name IS 
'Exact deployed database name - agents use database_name.object_name verbatim';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.object_name IS 
'Exact deployed object name - never derived from naming conventions';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.object_type IS 
'Portable classification - TABLE, VIEW, PROCEDURE, FUNCTION';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.object_role IS 
'Controlled recommendation for how agents should use the object - one role per row, never CSV';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.usage_guidance IS 
'Concise object-specific instructions or constraints for agents';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.table_kind IS 
'Native Teradata catalogue object-kind code (DBC.TablesV.TableKind) - enables catalogue-kind mismatch validation';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.is_active IS 
'Registration lifecycle - 1 = live and discoverable, 0 = retired from discovery; independent of physical existence';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.created_dts IS 
'Physical row creation time (UTC)';

COMMENT ON COLUMN Semantic.data_product_map_primary_objects.updated_dts IS 
'Physical row last-change time (UTC)';
```

**Object role vocabulary** (one role per row; if many-to-many assignment
becomes necessary, add an object-role child relation — never CSV):

| Role | Meaning |
|------|---------|
| `AGENT_ENTRYPOINT` | Recommended first object(s) when an agent explores the module |
| `ANALYTICAL_QUERY` | Governed object intended for analytical SELECT workloads |
| `REFERENCE_LOOKUP` | Code / reference data lookup object |
| `RELATIONSHIP_BRIDGE` | Association object used to traverse relationships |
| `LINEAGE_EVIDENCE` | Object holding lineage or provenance evidence |
| `OPERATIONAL_METRIC` | Operational or quality metric object |
| `WRITE_TARGET` | Object agents may write to, only under explicit policy |
| `INTERNAL_SUPPORT` | Internal object not intended for direct agent use |

**Security architecture support**: primary objects need not be physical
tables. A product may register physical tables where direct access is
permitted, views that enforce row/column/masking/tenancy/business-policy
controls, a mixture across modules, or other discoverable objects. Each
deployment implements its own security architecture while presenting agents
with one authoritative, portable discovery contract.

**Consumption contract**:

1. Query primary-object metadata through the product's governed metadata
   access layer.
2. Select objects by `object_role`.
3. Use the stored `database_name.object_name` verbatim — never derive
   names from naming conventions.
4. Honour `usage_guidance`.

```sql
-- Example seed rows (Customer360, matching the Section 3.5 example)
INSERT INTO Semantic.data_product_map_primary_objects
    (module_id, database_name, object_name, object_type, object_role, usage_guidance, table_kind)
VALUES
    (1, 'Customer360_Domain', 'Party_H', 'TABLE', 'INTERNAL_SUPPORT',
     'SCD2 history table - query via Party_Current unless history is required', 'T');

INSERT INTO Semantic.data_product_map_primary_objects
    (module_id, database_name, object_name, object_type, object_role, usage_guidance, table_kind)
VALUES
    (1, 'Customer360_Domain', 'Party_Current', 'VIEW', 'AGENT_ENTRYPOINT',
     'Current-state party view - default entry point for party questions', 'V');

INSERT INTO Semantic.data_product_map_primary_objects
    (module_id, database_name, object_name, object_type, object_role, usage_guidance, table_kind)
VALUES
    (2, 'Customer360_Semantic', 'v_relationship_paths', 'VIEW', 'RELATIONSHIP_BRIDGE',
     'Multi-hop join path discovery - filter hop_count to bound reads', 'V');
```

**Agent Discovery Query**:
```sql
-- Agent discovers the entry points of every deployed module
SELECT m.module_name,
       po.database_name || '.' || po.object_name AS qualified_name,
       po.object_type,
       po.object_role,
       po.usage_guidance
FROM Semantic.data_product_map AS m
JOIN Semantic.data_product_map_primary_objects AS po
    ON po.module_id = m.module_id
WHERE m.is_active = 1
  AND po.is_active = 1
  AND po.object_role = 'AGENT_ENTRYPOINT'
ORDER BY m.module_name, po.object_name;
```

**Validation** (Trust Engine / deployment checks):

```sql
-- Orphan module references
SELECT po.primary_object_id, po.module_id
FROM Semantic.data_product_map_primary_objects AS po
WHERE po.is_active = 1
  AND NOT EXISTS (
      SELECT 1 FROM Semantic.data_product_map AS m
      WHERE m.module_id = po.module_id AND m.is_active = 1
  );

-- Registered objects missing from the catalogue, or catalogue-kind mismatch
SELECT po.database_name, po.object_name, po.table_kind,
       t.TableKind AS actual_kind
FROM Semantic.data_product_map_primary_objects AS po
LEFT JOIN DBC.TablesV AS t
    ON  t.DatabaseName = po.database_name
    AND t.TableName = po.object_name
WHERE po.is_active = 1
  AND (t.TableName IS NULL
       OR (po.table_kind IS NOT NULL AND TRIM(t.TableKind) <> TRIM(po.table_kind)));

-- Invalid roles
SELECT po.primary_object_id, po.object_role
FROM Semantic.data_product_map_primary_objects AS po
WHERE po.object_role NOT IN
    ('AGENT_ENTRYPOINT', 'ANALYTICAL_QUERY', 'REFERENCE_LOOKUP'
   , 'RELATIONSHIP_BRIDGE', 'LINEAGE_EVIDENCE', 'OPERATIONAL_METRIC'
   , 'WRITE_TARGET', 'INTERNAL_SUPPORT');

-- Duplicate active registrations
SELECT po.module_id, po.database_name, po.object_name, COUNT(*) AS regs
FROM Semantic.data_product_map_primary_objects AS po
WHERE po.is_active = 1
GROUP BY po.module_id, po.database_name, po.object_name
HAVING COUNT(*) > 1;
```

**Migration from the CSV columns**:

1. Introduce `data_product_map_primary_objects` and expose it through the
   product's governed metadata access layer.
2. Backfill one row per value currently stored in `primary_tables` /
   `primary_views`, resolving each value to its exact deployed database
   and object type.
3. Update agents, generators, validators, and discovery APIs to consume
   the child relation.
4. Do not populate the CSV columns for new products.
5. Retain the legacy columns only where backward compatibility is
   required, with an agreed retirement date.

### 3.7 view_metadata (View Catalogue)

**Purpose**: Catalogue every view that exposes a base table — one row per
(base table, exposing view) — so consumers resolve an entity's full
exposure map, and which object is primary, from metadata rather than
naming conventions (resolves issue #36).

`entity_metadata.view_name` carries only the single standard current view;
deployments routinely expose one base table through several views. This
relation is the pragmatic interim on the path to issue #9's fuller
`access_object` registry: a `view_metadata` row migrates cleanly into an
`access_object` row with `access_role` derived from `view_type`.

```sql
CREATE TABLE Semantic.view_metadata (
    view_metadata_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    base_database VARCHAR(128) NOT NULL,
    base_table VARCHAR(128) NOT NULL,
    view_database VARCHAR(128) NOT NULL,
    view_name VARCHAR(128) NOT NULL,
    view_type VARCHAR(20) NOT NULL,     -- 'LOCKING','BUSINESS','CURRENT','ENRICHED','PIT','DERIVED'
    view_purpose VARCHAR(500),
    is_primary BYTEINT NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    is_active BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (base_table);

COMMENT ON TABLE Semantic.view_metadata IS 
'View catalogue - one row per (base table, exposing view); consumers resolve exposure from metadata, never naming conventions';

COMMENT ON COLUMN Semantic.view_metadata.view_metadata_id IS 
'Surrogate key for view catalogue record';

COMMENT ON COLUMN Semantic.view_metadata.base_database IS 
'Database of the base table this view exposes';

COMMENT ON COLUMN Semantic.view_metadata.base_table IS 
'Base table this view exposes';

COMMENT ON COLUMN Semantic.view_metadata.view_database IS 
'Database the exposing view is deployed in';

COMMENT ON COLUMN Semantic.view_metadata.view_name IS 
'Exposing view name - used verbatim by consumers';

COMMENT ON COLUMN Semantic.view_metadata.view_type IS 
'Exposure kind - LOCKING (1:1 full contract), BUSINESS, CURRENT (default current surface), ENRICHED (composite), PIT (point-in-time), DERIVED';

COMMENT ON COLUMN Semantic.view_metadata.view_purpose IS 
'Concise statement of what this exposure is for and any consumer constraints';

COMMENT ON COLUMN Semantic.view_metadata.is_primary IS 
'1 = the primary consumer exposure of the base table; at most one active primary per base table';

COMMENT ON COLUMN Semantic.view_metadata.is_active IS 
'Registration lifecycle - 1 = live catalogue entry, 0 = retired; independent of physical existence';

COMMENT ON COLUMN Semantic.view_metadata.created_dts IS 
'Physical row creation time (UTC)';

COMMENT ON COLUMN Semantic.view_metadata.updated_dts IS 
'Physical row last-change time (UTC)';
```

**Validation** (Trust Engine / deployment checks):

```sql
-- Governed base tables with no registered exposure
SELECT e.database_name, e.table_name
FROM Semantic.entity_metadata AS e
WHERE e.is_active = 1
  AND NOT EXISTS (
      SELECT 1 FROM Semantic.view_metadata AS vm
      WHERE vm.base_database = e.database_name
        AND vm.base_table = e.table_name
        AND vm.is_active = 1
  );

-- Registered views missing from the catalogue
SELECT vm.view_database, vm.view_name
FROM Semantic.view_metadata AS vm
LEFT JOIN DBC.TablesV AS t
    ON  t.DatabaseName = vm.view_database
    AND t.TableName = vm.view_name
    AND t.TableKind = 'V'
WHERE vm.is_active = 1
  AND t.TableName IS NULL;

-- More than one active primary exposure per base table
SELECT vm.base_database, vm.base_table, COUNT(*) AS primaries
FROM Semantic.view_metadata AS vm
WHERE vm.is_active = 1
  AND vm.is_primary = 1
GROUP BY vm.base_database, vm.base_table
HAVING COUNT(*) > 1;
```

### 3.8 view_column_type (View Column Type Overrides)

**Purpose**: Curated data types for view columns. The platform dictionary
cannot report data types for view columns, so the column catalogue (3.9)
needs a curated override supplying the friendly type string per view
column.

```sql
CREATE TABLE Semantic.view_column_type (
    view_column_type_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    database_name VARCHAR(128) NOT NULL,
    view_name VARCHAR(128) NOT NULL,
    column_name VARCHAR(128) NOT NULL,
    data_type VARCHAR(100) NOT NULL,    -- full friendly string, e.g. 'VARCHAR(50)', 'DECIMAL(7,2)'
    is_active BYTEINT NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (view_name);

COMMENT ON TABLE Semantic.view_column_type IS 
'Curated data types for view columns - supplies what the platform dictionary cannot report; consumed by column_catalogue';
```

Rows are generated at view-deployment time (the deployer knows each
projected column's type) rather than curated by hand.

### 3.9 column_catalogue (Live Hybrid Column Catalogue)

**Purpose**: The complete, consumer-facing column catalogue — live
structural facts joined to curated semantic facts, with the **provenance**
of every resolved value (addresses issue #22 for this module; the
RDBMS-neutral contract split follows the issue #16 restructure).

`column_metadata` (3.2) remains the curated store, but it can drift from
deployed structures and covers only the curated subset. The catalogue view
lists **every deployed column**, decodes types live from the dictionary
(with 3.8 overrides for view columns), resolves each description with
explicit precedence (curated → deployed comment → none), and flags
documentation coverage — so consumers see a complete schema without the
curated store ever copying dictionary facts.

```sql
REPLACE VIEW Semantic.column_catalogue
(
      catalogue_database         -- Database the column lives in
    , catalogue_table            -- Table or view the column belongs to
    , column_name                -- Physical column name
    , ordinal_position           -- Column order within the table
    , data_type                  -- Friendly type: view override when present, else live dictionary decode
    , data_type_source           -- 'override' | 'dictionary'
    , is_nullable                -- 1 if the column accepts NULL, else 0
    , is_required                -- 1 if the column is NOT NULL, else 0
    , business_description       -- Curated description, else deployed COMMENT, else NULL
    , description_source         -- 'curated' | 'comment' | 'none'
    , is_documented              -- 1 if a description exists from any source, else 0
    , is_pii                     -- Curated PII flag (1/0); 0 when not yet curated
    , is_sensitive               -- Curated sensitivity flag (1/0); 0 when not curated
    , data_classification        -- Curated classification label (NULL when not curated)
    , allowed_values_json        -- Curated allowed-value domain (NULL when not curated)
)
AS
SELECT
      dcol.DatabaseName                                        AS catalogue_database
    , dcol.TableName                                           AS catalogue_table
    , dcol.ColumnName                                          AS column_name
    , dcol.ColumnId                                            AS ordinal_position
    , COALESCE(
          vtype.data_type
        , CASE TRIM(dcol.ColumnType)
              WHEN 'I'  THEN 'INTEGER'
              WHEN 'I1' THEN 'BYTEINT'
              WHEN 'I2' THEN 'SMALLINT'
              WHEN 'I8' THEN 'BIGINT'
              WHEN 'F'  THEN 'FLOAT'
              WHEN 'D'  THEN 'DECIMAL(' || TRIM(dcol.DecimalTotalDigits)
                              || ',' || TRIM(dcol.DecimalFractionalDigits) || ')'
              WHEN 'DA' THEN 'DATE'
              WHEN 'AT' THEN 'TIME'
              WHEN 'TS' THEN 'TIMESTAMP'
              WHEN 'SZ' THEN 'TIMESTAMP WITH TIME ZONE'
              WHEN 'CF' THEN 'CHAR(' || TRIM(CAST(
                                  CASE WHEN dcol.CharType = 2
                                       THEN dcol.ColumnLength / 2
                                       ELSE dcol.ColumnLength END AS INTEGER)) || ')'
              WHEN 'CV' THEN 'VARCHAR(' || TRIM(CAST(
                                  CASE WHEN dcol.CharType = 2
                                       THEN dcol.ColumnLength / 2
                                       ELSE dcol.ColumnLength END AS INTEGER)) || ')'
              WHEN 'CO' THEN 'CLOB'
              WHEN 'JN' THEN 'JSON'
              WHEN 'BO' THEN 'BLOB'
              WHEN 'BV' THEN 'VARBYTE'
              WHEN 'BF' THEN 'BYTE'
              ELSE TRIM(dcol.ColumnType)
          END
      )                                                        AS data_type
    , CASE WHEN vtype.data_type IS NOT NULL THEN 'override'
           ELSE 'dictionary'
      END                                                      AS data_type_source
    , CASE WHEN dcol.Nullable = 'Y' THEN 1 ELSE 0 END          AS is_nullable
    , CASE WHEN dcol.Nullable = 'N' THEN 1 ELSE 0 END          AS is_required
    , COALESCE(meta.business_description
              , NULLIF(TRIM(dcol.CommentString), ''))          AS business_description
    , CASE WHEN meta.business_description IS NOT NULL              THEN 'curated'
           WHEN NULLIF(TRIM(dcol.CommentString), '') IS NOT NULL   THEN 'comment'
           ELSE 'none'
      END                                                      AS description_source
    , CASE WHEN COALESCE(meta.business_description
                       , NULLIF(TRIM(dcol.CommentString), '')) IS NOT NULL
           THEN 1 ELSE 0 END                                   AS is_documented
    , COALESCE(meta.is_pii, 0)                                 AS is_pii
    , COALESCE(meta.is_sensitive, 0)                           AS is_sensitive
    , meta.data_classification                                 AS data_classification
    , meta.allowed_values_json                                 AS allowed_values_json
FROM DBC.ColumnsV AS dcol
LEFT OUTER JOIN Semantic.column_metadata AS meta
    ON  meta.database_name = dcol.DatabaseName
    AND meta.table_name    = dcol.TableName
    AND meta.column_name   = dcol.ColumnName
    AND meta.is_active     = 1
LEFT OUTER JOIN Semantic.view_column_type AS vtype
    ON  vtype.database_name = dcol.DatabaseName
    AND vtype.view_name     = dcol.TableName
    AND vtype.column_name   = dcol.ColumnName
    AND vtype.is_active     = 1
WHERE dcol.DatabaseName IN (
    SELECT m.database_name FROM Semantic.data_product_map AS m
    WHERE m.is_active = 1
);
```

Rules:

1. Scope the dictionary read to the product's own databases (the template
   scopes via `data_product_map`; deployments may refine with layer
   predicates and staging/backup exclusions).
2. Source precedence is explicit and carried per row: `data_type_source`
   and `description_source` let consumers distinguish curated facts from
   dictionary facts and detect drift.
3. Consumers prefer `column_catalogue` for schema display; `column_metadata`
   remains the curation write-target.
4. A documentation gap report is `WHERE is_documented = 0`.

### 3.10 data_product_orientation (Agent Orientation Contract)

**Purpose**: Give an agent one authoritative, ordered starting point for
discovering and safely using the product — a queryable relation with one row
per product resource, its role, where it lives, whether it is required, and
the order to process it (resolves issue #20).

This formalises the Orientation Layer prose of §3.4 into a relation a
consumer can read and a validator can check. A consumer no longer needs to
know repository conventions or invent a discovery sequence: it reads this
relation, processes the required resources in `discovery_order`, evaluates
the trust gate before any analytical resource, and uses the stored fully
qualified names verbatim.

```sql
CREATE TABLE Semantic.data_product_orientation (
    orientation_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    product_id VARCHAR(128) NOT NULL,
    resource_role VARCHAR(40) NOT NULL,          -- controlled vocabulary (below)
    database_name VARCHAR(128),                  -- deployed location (object-backed resources)
    object_name VARCHAR(128),                    -- deployed object (object-backed resources)
    fully_qualified_object_name VARCHAR(257),    -- canonical database.object; used verbatim
    resource_uri VARCHAR(1000),                  -- URI for MCP/external resources (nullable)
    usage_guidance VARCHAR(500),                 -- how a consumer should use this resource
    is_required BYTEINT NOT NULL DEFAULT 0,      -- 1 = missing resource is a conformance failure
    discovery_order SMALLINT NOT NULL,           -- processing order; trust gate precedes analytics
    metadata_updated_dts TIMESTAMP(6) WITH TIME ZONE,
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (product_id);

COMMENT ON TABLE Semantic.data_product_orientation IS
'Agent orientation contract - one ordered row per product resource; the authoritative bootstrap sequence for consumers (issue #20)';
COMMENT ON COLUMN Semantic.data_product_orientation.product_id IS
'Product this resource belongs to - matches data_product_registry.product_id';
COMMENT ON COLUMN Semantic.data_product_orientation.resource_role IS
'Controlled role of the resource in the bootstrap sequence - one role per row, never CSV';
COMMENT ON COLUMN Semantic.data_product_orientation.fully_qualified_object_name IS
'Canonical database.object identity - consumers use it verbatim, never derived from conventions';
COMMENT ON COLUMN Semantic.data_product_orientation.resource_uri IS
'URI for a resource exposed as MCP or external documentation rather than a database object';
COMMENT ON COLUMN Semantic.data_product_orientation.is_required IS
'1 = a consumer must resolve this resource; its absence is a conformance failure';
COMMENT ON COLUMN Semantic.data_product_orientation.discovery_order IS
'Ascending processing order; the trust gate role precedes every analytical resource';
COMMENT ON COLUMN Semantic.data_product_orientation.metadata_updated_dts IS
'When this orientation row was last regenerated from authoritative metadata';
COMMENT ON COLUMN Semantic.data_product_orientation.is_active IS
'1 = live orientation row, 0 = retired; independent of whether the resource physically exists';
```

**Resource role vocabulary** (baseline; extensions may add roles). One role
per row — never a CSV. The baseline **required** roles a conformant product
publishes, in canonical discovery order:

| # | `resource_role` | Backed by | Required |
|---|-----------------|-----------|----------|
| 1 | `MANIFEST` | `data_product_manifest` (§3.11) | Yes |
| 2 | `TRUST_GATE` | the product's trust view (Validation Standard) | Yes |
| 3 | `MODULE_MAP` | `data_product_map` | Yes |
| 4 | `OBJECT_CATALOGUE` | `data_product_map_primary_objects` | Yes |
| 5 | `ENTITY_CATALOGUE` | `entity_metadata` | Yes |
| 6 | `COLUMN_CATALOGUE` | `column_catalogue` | Yes |
| 7 | `RELATIONSHIP_CATALOGUE` | `table_relationship` | Yes |
| 8 | `RELATIONSHIP_PATHS` | `v_relationship_paths` | No |
| 9 | `LINEAGE` | Observability definitional lineage | No |
| 10 | `QUERY_COOKBOOK` | `Query_Cookbook` | No |
| 11 | `GLOSSARY` | `Business_Glossary` | No |
| 12 | `DESIGN_DECISIONS` | `Design_Decision` | No |
| — | `POLICY`, `QUALITY` | site policy / quality evidence | Conditional |

**Consumption contract**:

1. Start at the `MANIFEST` resource (§3.11), or at this relation directly.
2. Process resources in ascending `discovery_order`.
3. Evaluate the `TRUST_GATE` resource **before** any analytical resource; a
   blocked gate stops autonomous use (Validation Standard §8).
4. Resolve every `is_required = 1` resource; a missing required resource is
   a conformance failure.
5. Use `fully_qualified_object_name` (or `resource_uri`) verbatim — never
   derive object names from conventions.

```sql
-- Example seed (CallCentre; fully qualified names elided to the pattern)
INSERT INTO Semantic.data_product_orientation
    (product_id, resource_role, database_name, object_name, fully_qualified_object_name, usage_guidance, is_required, discovery_order, metadata_updated_dts)
VALUES
    ('call_centre.customer_experience', 'MANIFEST', 'CallCentre_SEM_BUS_V', 'data_product_manifest', 'CallCentre_SEM_BUS_V.data_product_manifest', 'Read first - product identity and entrypoints', 1, 1, CURRENT_TIMESTAMP(6));
INSERT INTO Semantic.data_product_orientation
    (product_id, resource_role, database_name, object_name, fully_qualified_object_name, usage_guidance, is_required, discovery_order, metadata_updated_dts)
VALUES
    ('call_centre.customer_experience', 'TRUST_GATE', 'CallCentre_SEM_BUS_V', 'trust_engine_latest', 'CallCentre_SEM_BUS_V.trust_engine_latest', 'Evaluate before analytical use - stop if agent_use_allowed = 0', 1, 2, CURRENT_TIMESTAMP(6));
INSERT INTO Semantic.data_product_orientation
    (product_id, resource_role, database_name, object_name, fully_qualified_object_name, usage_guidance, is_required, discovery_order, metadata_updated_dts)
VALUES
    ('call_centre.customer_experience', 'OBJECT_CATALOGUE', 'CallCentre_SEM_BUS_V', 'data_product_map_primary_objects', 'CallCentre_SEM_BUS_V.data_product_map_primary_objects', 'Pick objects by role; use qualified names verbatim', 1, 4, CURRENT_TIMESTAMP(6));
```

**Agent orientation query**:
```sql
SELECT o.discovery_order,
       o.resource_role,
       o.fully_qualified_object_name,
       o.resource_uri,
       o.is_required,
       o.usage_guidance
FROM Semantic.data_product_orientation AS o
WHERE o.product_id = :product_id
  AND o.is_active = 1
ORDER BY o.discovery_order;
```

**Validation** (Trust Engine / deployment checks):

```sql
-- Missing required baseline role for the product
SELECT req.resource_role
FROM (SELECT 'MANIFEST' AS resource_role
      UNION SELECT 'TRUST_GATE' UNION SELECT 'MODULE_MAP'
      UNION SELECT 'OBJECT_CATALOGUE' UNION SELECT 'ENTITY_CATALOGUE'
      UNION SELECT 'COLUMN_CATALOGUE' UNION SELECT 'RELATIONSHIP_CATALOGUE') AS req
WHERE NOT EXISTS (
    SELECT 1 FROM Semantic.data_product_orientation AS o
    WHERE o.product_id = :product_id AND o.is_active = 1
      AND o.resource_role = req.resource_role
);

-- Duplicate active role for one product (each role is singular)
SELECT product_id, resource_role, COUNT(*) AS n
FROM Semantic.data_product_orientation
WHERE is_active = 1
GROUP BY product_id, resource_role
HAVING COUNT(*) > 1;

-- Duplicate discovery_order for one product
SELECT product_id, discovery_order, COUNT(*) AS n
FROM Semantic.data_product_orientation
WHERE is_active = 1
GROUP BY product_id, discovery_order
HAVING COUNT(*) > 1;

-- Unresolved object-backed resource (registered object not deployed)
SELECT o.product_id, o.resource_role, o.fully_qualified_object_name
FROM Semantic.data_product_orientation AS o
LEFT JOIN DBC.TablesV AS t
    ON  t.DatabaseName = o.database_name
    AND t.TableName = o.object_name
WHERE o.is_active = 1
  AND o.object_name IS NOT NULL
  AND t.TableName IS NULL;

-- Trust gate not ordered before analytical resources
SELECT o.product_id
FROM Semantic.data_product_orientation AS o
WHERE o.is_active = 1
  AND o.resource_role IN ('ENTITY_CATALOGUE', 'RELATIONSHIP_PATHS', 'QUERY_COOKBOOK')
  AND o.discovery_order < (
      SELECT MIN(g.discovery_order)
      FROM Semantic.data_product_orientation AS g
      WHERE g.product_id = o.product_id AND g.is_active = 1
        AND g.resource_role = 'TRUST_GATE'
  );
```

These checks are designed to be lifted into validation profiles; a missing
required resource or an unordered trust gate is a blocking conformance
failure (Validation Standard).

### 3.11 data_product_manifest (Machine-Readable Manifest)

**Purpose**: One machine-readable bootstrap record per product — identity,
ownership, conformance posture, approved access mode, and the key discovery
entrypoints — **generated from authoritative metadata** so it cannot drift
from the sources it summarises (issue #20).

The manifest is a **view**, not a stored table: it assembles product
identity from `data_product_registry` and the entrypoints from
`data_product_orientation`, pivoting the ordered resources into named
columns. Because it is derived, the manifest–orientation–source consistency
rule holds by construction. The registry's `manifest_json` remains the
serialised representation for MCP clients that want the whole document in
one read.

```sql
REPLACE VIEW Semantic.data_product_manifest
(
      product_id
    , product_name
    , product_version
    , product_status
    , owner_team
    , approved_access_mode
    , approved_entrypoint
    , manifest_entrypoint
    , trust_entrypoint
    , module_map_entrypoint
    , object_catalogue_entrypoint
    , entity_catalogue_entrypoint
    , column_catalogue_entrypoint
    , relationship_catalogue_entrypoint
    , manifest_json
)
AS
LOCKING ROW FOR ACCESS
SELECT
      r.product_id
    , r.product_name
    , r.product_version
    , r.product_status
    , r.owner_team
    , r.approved_access_mode
    , r.approved_entrypoint
    , MAX(CASE WHEN o.resource_role = 'MANIFEST'               THEN o.fully_qualified_object_name END)
    , MAX(CASE WHEN o.resource_role = 'TRUST_GATE'             THEN o.fully_qualified_object_name END)
    , MAX(CASE WHEN o.resource_role = 'MODULE_MAP'             THEN o.fully_qualified_object_name END)
    , MAX(CASE WHEN o.resource_role = 'OBJECT_CATALOGUE'       THEN o.fully_qualified_object_name END)
    , MAX(CASE WHEN o.resource_role = 'ENTITY_CATALOGUE'       THEN o.fully_qualified_object_name END)
    , MAX(CASE WHEN o.resource_role = 'COLUMN_CATALOGUE'       THEN o.fully_qualified_object_name END)
    , MAX(CASE WHEN o.resource_role = 'RELATIONSHIP_CATALOGUE' THEN o.fully_qualified_object_name END)
    , r.manifest_json
FROM governance.data_product_registry AS r
LEFT JOIN Semantic.data_product_orientation AS o
    ON  o.product_id = r.product_id
    AND o.is_active = 1
WHERE r.is_active = 1
  AND r.is_deleted = 0
GROUP BY
      r.product_id, r.product_name, r.product_version, r.product_status
    , r.owner_team, r.approved_access_mode, r.approved_entrypoint, r.manifest_json;
```

**Consumption contract**:

1. A consumer reads the manifest first (or resolves it as the `MANIFEST`
   orientation resource), then follows `data_product_orientation` in
   `discovery_order`.
2. The `trust_entrypoint` is evaluated before any analytical entrypoint.
3. Entrypoint columns carry fully qualified names used verbatim.
4. `manifest_json`, where present, is the serialised form of the same facts;
   it is regenerated from authoritative metadata, never hand-authored to
   diverge from the columns above.

**Consistency check** (manifest entrypoints resolve to orientation rows):

```sql
-- A manifest entrypoint with no backing active orientation row
SELECT m.product_id
FROM Semantic.data_product_manifest AS m
WHERE m.trust_entrypoint IS NULL
   OR m.manifest_entrypoint IS NULL
   OR m.entity_catalogue_entrypoint IS NULL;
```

### 3.12 access_object (Access Layer Metadata)

**Purpose**: Register the objects a consumer actually queries — one row per
consumable object — with the role it plays, the entity it represents, its
grain, and whether an agent should query it directly. This lets a consumer
resolve any queryable object to its logical meaning **once, from metadata**,
without parsing DDL or recomputing lineage at query time (resolves issue #9).

> This is **access-layer metadata**, distinct from the security **Access Layer
> Design Standard** (which governs roles and grants). It models *which objects
> represent what*, not *who may read them*.

The logical layer (`entity_metadata`, `table_relationship`) models entities and
their relationships; it does not model the *access layer*. A platform security
model may expose one entity through several objects (locking, business, current
views), and products publish composite ("enriched") objects that join several
entities into one unit. `access_object` captures those facts so consumers stop
reverse-engineering them from DDL or names.

**Logical schema** (normative; physical types bind per platform extension):

| Column | Meaning | Requirement |
|--------|---------|-------------|
| `access_object_id` | Surrogate key | Required |
| `database_name`, `object_name` | Physical location of the object | Required |
| `access_role` | Role in the access layer. **Open vocabulary**: baseline `BASE`, `PASSTHROUGH`, `COMPOSITE`; extensions add values | Required |
| `represents_entity` | Logical entity this object exposes (references `entity_metadata.entity_name`); null for composites that span entities | Conditional |
| `object_grain` | Plain-language grain, e.g. "one row per call" | Recommended |
| `is_agent_consumable` | Whether agents/humans should query this object directly | Required |
| `resolves_to_object` | For 1:1 passthroughs/projections, the object this maps straight through to (collapse the chain to the entity in one hop) | Conditional |
| `access_note` | Free-form guidance (locking, filtering, …) | Optional |
| lifecycle (`is_active`, `created_dts`, `updated_dts`) | Housekeeping per the Temporal & Lifecycle Metadata Standard | Required |

**Illustrative Teradata realisation** — physical types, the `access_role`
vocabulary beyond the baseline, placement, and locking bind in the platform
extension (#11); this DDL is not itself normative:

```sql
CREATE TABLE Semantic.access_object (
    access_object_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    database_name VARCHAR(128) NOT NULL,
    object_name VARCHAR(128) NOT NULL,
    access_role VARCHAR(40) NOT NULL,        -- BASE | PASSTHROUGH | COMPOSITE | extension value
    represents_entity VARCHAR(128),          -- entity_metadata.entity_name; null for cross-entity composites
    object_grain VARCHAR(200),
    is_agent_consumable BYTEINT NOT NULL DEFAULT 1,
    resolves_to_object VARCHAR(257),         -- database.object for 1:1 passthroughs
    access_note VARCHAR(500),
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (represents_entity);
```

**Consumption contract** (normative):

1. A consumer selecting data **resolves through `access_object`** — chooses
   `is_agent_consumable = 1` objects and reads `represents_entity` — rather
   than querying base tables directly.
2. A `COMPOSITE` object is presented as a **single unit**; its internal
   structure is read from `access_composition` (§3.13), never by parsing DDL
   or computing column lineage at consumption time.
3. Emitted join syntax targets consumable objects (access-resolved, §3.14),
   not base tables.
4. **Object names are not a contract.** No consumer infers an object's role,
   layer, entity, or purpose from its name. The registry is the single source
   of truth; classification is asserted in metadata, never derived from a name.

**Establishment & ownership** (normative): this metadata is **established once
at deployment** by a registration step, defined here by responsibility, not by
tool. The step classifies objects from **verifiable structure** — the
dependency graph and object definitions — not from names, and asserts the
result in the registry. Consumers read it; they never recompute it. The
*implementation* of the step is a platform concern (#11).

**Relationship to `view_metadata` (§3.7)**: `view_metadata` catalogues the
physical base-table → view exposure map; `access_object` is the consumption
contract layered on it — the semantic access role, entity resolution, grain,
and agent-consumability. `BASE`/`PASSTHROUGH` rows may be backfilled from
`view_metadata` + `entity_metadata`; `COMPOSITE` rows and `is_agent_consumable`
are access-object-only. `access_object` is authoritative for object
multiplicity per entity; `entity_metadata.view_name` is retained as the
denormalised "canonical consumable object" pointer.

**Agent discovery query** (object → entity resolution):

```sql
SELECT a.database_name || '.' || a.object_name AS consumable_object,
       a.access_role,
       a.represents_entity,
       a.object_grain,
       a.resolves_to_object
FROM Semantic.access_object AS a
WHERE a.is_active = 1
  AND a.is_agent_consumable = 1
ORDER BY a.represents_entity, a.access_role;
```

**Validation** (Trust Engine / deployment checks):

```sql
-- Invalid baseline role (extension roles are validated by the extension)
SELECT access_object_id, access_role
FROM Semantic.access_object
WHERE is_active = 1
  AND access_role NOT IN ('BASE', 'PASSTHROUGH', 'COMPOSITE');

-- Non-composite consumable object that resolves to no entity
SELECT access_object_id, database_name, object_name
FROM Semantic.access_object
WHERE is_active = 1
  AND access_role <> 'COMPOSITE'
  AND represents_entity IS NULL;

-- represents_entity that is not a catalogued entity
SELECT a.access_object_id, a.represents_entity
FROM Semantic.access_object AS a
WHERE a.is_active = 1
  AND a.represents_entity IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM Semantic.entity_metadata AS e
      WHERE e.is_active = 1 AND e.entity_name = a.represents_entity
  );

-- Registered access object not deployed
SELECT a.database_name, a.object_name
FROM Semantic.access_object AS a
LEFT JOIN DBC.TablesV AS t
    ON  t.DatabaseName = a.database_name AND t.TableName = a.object_name
WHERE a.is_active = 1 AND t.TableName IS NULL;
```

### 3.13 access_composition (Composite Object Structure)

**Purpose**: Record what a `COMPOSITE` access object encapsulates — one row per
component — so a consumer expands the composite from metadata, never from DDL.
Components are referenced as **entities**, not raw tables, to keep the record
intelligible and platform-neutral.

**Logical schema** (normative; physical types bind per platform extension):

| Column | Meaning | Requirement |
|--------|---------|-------------|
| `access_composition_id` | Surrogate key | Required |
| `composite_database`, `composite_object` | The composite being described | Required |
| `member_seq` | Ordering of the component within the composite | Required |
| `member_entity` | Entity the component represents (references `entity_metadata`) | Required |
| `member_role` | Join role: `ANCHOR`, `INNER`, `LEFT`, `RIGHT`, `FULL` | Required |
| `join_path` | Logical join condition, entity-level (same form as `v_relationship_paths.path_joins`) | Recommended |
| `is_grain_contributor` | Whether this component changes the composite's grain | Recommended |
| `member_note`, lifecycle | Guidance + housekeeping | Optional / Required |

**Illustrative Teradata realisation** (non-normative):

```sql
CREATE TABLE Semantic.access_composition (
    access_composition_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    composite_database VARCHAR(128) NOT NULL,
    composite_object VARCHAR(128) NOT NULL,
    member_seq SMALLINT NOT NULL,
    member_entity VARCHAR(128) NOT NULL,
    member_role VARCHAR(20) NOT NULL,        -- ANCHOR | INNER | LEFT | RIGHT | FULL
    join_path VARCHAR(1000),
    is_grain_contributor BYTEINT NOT NULL DEFAULT 0,
    member_note VARCHAR(500),
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (composite_object);
```

**Composite expansion query** (read a composite as a unit):

```sql
SELECT c.member_seq,
       c.member_entity,
       c.member_role,
       c.is_grain_contributor,
       c.join_path
FROM Semantic.access_composition AS c
WHERE c.is_active = 1
  AND c.composite_database = :composite_database
  AND c.composite_object = :composite_object
ORDER BY c.member_seq;
```

**Validation**: exactly one `ANCHOR` per composite; every `member_entity`
catalogued in `entity_metadata`; every described composite present in
`access_object` with `access_role = 'COMPOSITE'`.

```sql
-- Composite without exactly one ANCHOR
SELECT composite_database, composite_object,
       SUM(CASE WHEN member_role = 'ANCHOR' THEN 1 ELSE 0 END) AS anchors
FROM Semantic.access_composition
WHERE is_active = 1
GROUP BY composite_database, composite_object
HAVING SUM(CASE WHEN member_role = 'ANCHOR' THEN 1 ELSE 0 END) <> 1;
```

### 3.14 Access-Resolved Relationship Paths

`v_relationship_paths` (§5) stays as the logical, entity-level truth. Its
`path_joins` are emitted against base tables; where a platform exposes a
separate consumable layer, those joins point at objects an agent may not query,
at the wrong grain.

The **access-resolved** artifact rewrites path endpoints and join targets to
**consumable objects** — via `access_object.represents_entity` and
`resolves_to_object` — so agents receive joins written against objects they can
actually query. What it contains is normative; its persistence (a view, or a
table refreshed at deployment) is a platform/performance decision left to the
extension.

**Contract** (normative): for each logical path, resolve every endpoint entity
to its canonical consumable object (the `is_agent_consumable = 1` `access_object`
for that entity, collapsing `resolves_to_object` chains) and emit the join
against those objects. A path whose endpoint entity has no consumable object is
omitted, not emitted against a base table.

**Illustrative view** (non-normative — endpoint resolution; the full join
rewrite binds in the extension):

```sql
REPLACE VIEW Semantic.v_access_relationship_paths
(
      source_entity
    , source_object
    , target_entity
    , target_object
    , hop_count
    , path_description
)
AS
LOCKING ROW FOR ACCESS
SELECT
      p.source_table
    , sa.database_name || '.' || sa.object_name
    , p.target_table
    , ta.database_name || '.' || ta.object_name
    , p.hop_count
    , p.path_description
FROM Semantic.v_relationship_paths AS p
JOIN Semantic.access_object AS sa
    ON  sa.represents_entity = p.source_table
    AND sa.is_agent_consumable = 1 AND sa.is_active = 1
JOIN Semantic.access_object AS ta
    ON  ta.represents_entity = p.target_table
    AND ta.is_agent_consumable = 1 AND ta.is_active = 1;
```

---

## 4. Table-Level Relationship Metadata

```sql
CREATE TABLE Semantic.table_relationship (
    relationship_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    relationship_name VARCHAR(128) NOT NULL,
    relationship_description VARCHAR(1000),
    source_database VARCHAR(128),
    source_table VARCHAR(100) NOT NULL,
    source_column VARCHAR(128) NOT NULL,
    target_database VARCHAR(128),
    target_table VARCHAR(100) NOT NULL,
    target_column VARCHAR(128) NOT NULL,
    relationship_type VARCHAR(50) NOT NULL,
    cardinality VARCHAR(20),
    relationship_meaning VARCHAR(500),
    is_mandatory BYTEINT NOT NULL DEFAULT 0,
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (relationship_id);

COMMENT ON TABLE Semantic.table_relationship IS 
'Table-level relationship metadata - describes how tables join for correct SQL generation by agents';

COMMENT ON COLUMN Semantic.table_relationship.relationship_id IS 
'Surrogate key for relationship metadata record';

COMMENT ON COLUMN Semantic.table_relationship.relationship_name IS 
'Descriptive name for relationship - e.g., PartyAddress_To_Party, Party_Hierarchy';

COMMENT ON COLUMN Semantic.table_relationship.relationship_description IS 
'Business description of relationship purpose and meaning';

COMMENT ON COLUMN Semantic.table_relationship.source_database IS 
'Database containing source table (the table with foreign key column)';

COMMENT ON COLUMN Semantic.table_relationship.source_table IS 
'Source table name - the table containing the foreign key column';

COMMENT ON COLUMN Semantic.table_relationship.source_column IS 
'Source column name - the foreign key column that references target';

COMMENT ON COLUMN Semantic.table_relationship.target_database IS 
'Database containing target table (the referenced table)';

COMMENT ON COLUMN Semantic.table_relationship.target_table IS 
'Target table name - the table being referenced by the foreign key';

COMMENT ON COLUMN Semantic.table_relationship.target_column IS 
'Target column name - the primary/unique key column being referenced';

COMMENT ON COLUMN Semantic.table_relationship.relationship_type IS 
'Type of relationship - FOREIGN_KEY, HIERARCHY, ASSOCIATIVE';

COMMENT ON COLUMN Semantic.table_relationship.cardinality IS 
'Relationship cardinality - 1:1, 1:M, M:1, M:M - indicates one-to-one, one-to-many, etc.';

COMMENT ON COLUMN Semantic.table_relationship.relationship_meaning IS 
'Business meaning of relationship - explains what the association represents';

COMMENT ON COLUMN Semantic.table_relationship.is_mandatory IS 
'Mandatory relationship indicator - Y = foreign key is NOT NULL (required), N = nullable (optional)';

COMMENT ON COLUMN Semantic.table_relationship.is_active IS 
'Relationship active indicator - Y = currently valid, N = deprecated';

COMMENT ON COLUMN Semantic.table_relationship.created_at IS 
'Timestamp when relationship metadata was created';

COMMENT ON COLUMN Semantic.table_relationship.updated_at IS 
'Timestamp when relationship metadata was last updated';
```

---

## 5. Multi-Hop Path Discovery

### 5.1 v_relationship_paths View (TESTED ✅)

```sql
CREATE VIEW Semantic.v_relationship_paths
(
    -- View contract: agents see all returned columns without parsing the SELECT body
    source_table,
    target_table,
    path_tables,
    path_joins,
    hop_count,
    path_description
)
AS
WITH RECURSIVE relationship_paths (
    source_table,
    target_table,
    path_tables,
    path_joins,
    hop_count,
    path_description
) AS (
    -- Anchor: Forward (1-hop)
    SELECT 
        source_table,
        target_table,
        source_table || ' -> ' || target_table AS path_tables,
        'JOIN ' || target_table || ' ON ' || 
            target_table || '.' || target_column || ' = ' ||
            source_table || '.' || source_column AS path_joins,
        1 AS hop_count,
        relationship_description AS path_description
    FROM Semantic.table_relationship
    WHERE is_active = 1
    
    UNION ALL
    
    -- Anchor: Reversed (1-hop backward)
    SELECT 
        target_table AS source_table,
        source_table AS target_table,
        target_table || ' -> ' || source_table AS path_tables,
        'JOIN ' || source_table || ' ON ' || 
            source_table || '.' || source_column || ' = ' ||
            target_table || '.' || target_column AS path_joins,
        1 AS hop_count,
        'REVERSE: ' || relationship_description AS path_description
    FROM Semantic.table_relationship
    WHERE is_active = 1
    
    UNION ALL
    
    -- Recursive: Forward
    SELECT 
        rp.source_table,
        tr.target_table,
        rp.path_tables || ' -> ' || tr.target_table AS path_tables,
        rp.path_joins || ' | ' ||
        'JOIN ' || tr.target_table || ' ON ' ||
            tr.target_table || '.' || tr.target_column || ' = ' ||
            tr.source_table || '.' || tr.source_column AS path_joins,
        rp.hop_count + 1 AS hop_count,
        rp.path_description || ' -> ' || tr.relationship_description AS path_description
    FROM relationship_paths rp
    INNER JOIN Semantic.table_relationship tr 
        ON tr.source_table = rp.target_table
       AND tr.is_active = 1
    WHERE rp.hop_count < 5
      AND rp.path_tables NOT LIKE '%' || tr.target_table || '%'
      
    UNION ALL
    
    -- Recursive: Backward
    SELECT 
        rp.source_table,
        tr.source_table AS target_table,
        rp.path_tables || ' -> ' || tr.source_table AS path_tables,
        rp.path_joins || ' | ' ||
        'JOIN ' || tr.source_table || ' ON ' ||
            tr.source_table || '.' || tr.source_column || ' = ' ||
            tr.target_table || '.' || tr.target_column AS path_joins,
        rp.hop_count + 1 AS hop_count,
        rp.path_description || ' -> REVERSE: ' || tr.relationship_description AS path_description
    FROM relationship_paths rp
    INNER JOIN Semantic.table_relationship tr 
        ON tr.target_table = rp.target_table
       AND tr.is_active = 1
    WHERE rp.hop_count < 5
      AND rp.path_tables NOT LIKE '%' || tr.source_table || '%'
)
SELECT * FROM relationship_paths;

COMMENT ON VIEW Semantic.v_relationship_paths IS 
'Multi-hop relationship path discovery view - enables agents to find indirect join paths between any two tables up to 5 hops, with bidirectional traversal support and complete JOIN syntax generation';
```

### 5.2 Agent Example (TESTED ✅)

```sql
-- Find path from Party_H to Transaction_H
SELECT hop_count, path_tables, path_joins
FROM Semantic.v_relationship_paths
WHERE source_table = 'Party_H'
  AND target_table = 'Transaction_H'
ORDER BY hop_count
QUALIFY ROW_NUMBER() OVER (ORDER BY hop_count) = 1;

-- Result:
-- hop_count: 2
-- path_tables: Party_H -> PartyProduct_H -> Transaction_H
-- path_joins: JOIN PartyProduct_H ON PartyProduct_H.party_id = Party_H.party_id | 
--             JOIN Transaction_H ON Transaction_H.party_product_id = PartyProduct_H.party_product_id
```

---

## 6. Agent Discovery and Querying

### 6.1 Discovery Queries

```sql
-- Which data products are currently discoverable?
SELECT product_id, product_name, semantic_database, approved_entrypoint
FROM governance.data_product_registry
WHERE is_active = 1
  AND is_deleted = 0;

-- Which modules are deployed for the selected product?
SELECT module_name, database_name, deployment_status
FROM Semantic.data_product_map
WHERE is_active = 1
ORDER BY module_name;

-- Which objects should I use in each module? (never parse CSV columns)
SELECT m.module_name,
       po.database_name || '.' || po.object_name AS qualified_name,
       po.object_role, po.usage_guidance
FROM Semantic.data_product_map AS m
JOIN Semantic.data_product_map_primary_objects AS po
    ON po.module_id = m.module_id
WHERE m.is_active = 1
  AND po.is_active = 1
ORDER BY m.module_name, po.object_role, po.object_name;

-- What tables exist?
SELECT entity_name, module_name, table_name
FROM Semantic.entity_metadata
WHERE is_active = 1;

-- How do I join A to B?
SELECT hop_count, path_joins
FROM Semantic.v_relationship_paths
WHERE source_table = 'A' AND target_table = 'B'
ORDER BY hop_count;
```

---

## 7. Integration with Other Modules

Semantic describes all modules via entity_metadata and table_relationship.

**Definitional lineage exposure**: definitional `data_lineage` is owned by
the Observability module (Observability standard, definition/execution
split). The Semantic discovery surface exposes a `data_lineage` projection
of it, so catalogue consumers resolve a product's declared flows from the
same database they discover everything else in — without reaching into
module internals.

---

## 8. Designer Responsibilities

### 8.1 Required Tables

- data_product_registry (product-level registry in governance database)
- entity_metadata (~10-50 rows)
- column_metadata (~100-500 rows)
- table_relationship (~20-100 rows)
- naming_standard (~10-30 rows)
- data_product_map (one row per deployed module)
- data_product_map_primary_objects (one row per primary object)
- view_metadata (one row per base-table exposure)
- view_column_type (populated at view-deployment time)
- data_product_orientation (ordered resource bootstrap, 3.10)
- access_object (consumable object registry, 3.12)
- access_composition (composite structure, when composites exist, 3.13)

### 8.2 Required Views

- column_catalogue (live hybrid column catalogue, 3.9)
- data_product_manifest (generated machine-readable manifest, 3.11)
- v_access_relationship_paths (access-resolved paths, 3.14)
- v_entity_catalog
- v_entity_schema
- **v_relationship_paths** (CRITICAL)

### 8.3 Optional Tables

- ontology (taxonomies)
- business_rule (validation)
- data_contract_catalog (use open standards)

### 8.4 Documentation Capture Requirements

Every Semantic module must populate the Memory database documentation tables as part of its design workflow. The table definitions, workflows, and full protocol are defined in the **Memory Module Design Standard, Section 8**.

**Minimum requirements:**

| Record Type | Table | Minimum | Notes |
|-------------|-------|---------|-------|
| Module_Registry | `Memory.Module_Registry` | 1 | Register this module with data_product and version |
| Design_Decision | `Memory.Design_Decision` | 3 | Key architectural and schema choices |
| Change_Log | `Memory.Change_Log` | 1 | Initial release entry (version 1.0.0) |
| Business_Glossary | `Memory.Business_Glossary` | 3 | Metadata terms and relationship definitions introduced |
| Query_Cookbook | `Memory.Query_Cookbook` | 1 | Key query patterns (e.g., multi-hop path discovery, entity lookup) |

**Typical decision categories for Semantic modules:**

| Decision Category | Example |
|-------------------|---------|
| `INTEGRATION` | Relationship mapping strategy and join path decisions |
| `NAMING` | Metadata naming standards and column classification conventions |
| `ARCHITECTURE` | data_product_map scope and agent discovery strategy |
| `SCHEMA` | entity_metadata vs column_metadata boundary decisions |

**Decision ID prefix for this module:** `DD-SEMANTIC-{NNN}` (e.g., `DD-SEMANTIC-001`)

**Required product discovery decision:** When the Data Product Orientation Layer is deployed, generate the `DD-DISCOVERY-001` `Design_Decision` INSERT defined in the Memory Module Design Standard. This records why agents and MCP clients read the product manifest before metadata maps or data access.

**Output file placement:** Write documentation capture SQL as the last numbered file in the semantic deployment directory (e.g., `02-semantic/05-documentation.sql`).

**Full protocol, SQL templates, and ID conventions:** See Memory Module Design Standard, Section 8.3 (Workflow 2 — Capture).

**Design Checklist additions:**

- [ ] `Module_Registry` INSERT generated for this module (with `deployment_status = 'DEPLOYED'`)
- [ ] `DD-DISCOVERY-001` INSERT generated when the Data Product Orientation Layer is deployed
- [ ] Min. 3 `Design_Decision` INSERTs generated
- [ ] `Change_Log` initial release entry generated
- [ ] Min. 3 `Business_Glossary` terms captured
- [ ] Min. 1 `Query_Cookbook` recipe captured
- [ ] `table_relationship` completeness verified (see Section 8.5)
- [ ] `v_relationship_paths` validated for all expected agent traversal paths

---

### 8.5 table_relationship Completeness Requirement

`table_relationship` is the machine-readable entity-relationship model for this data product. Agents use it — via `v_relationship_paths` — to discover how to join any two tables without human guidance. An incomplete `table_relationship` is one of the most common causes of agent SQL errors, because the agent cannot traverse a path it has no record of.

**Completeness means registering every relationship an agent is expected to traverse**, not just the relationships that feel "important" or that have physical foreign keys. The following categories must all be covered:

| Category | Examples | Common omission |
|---|---|---|
| **Intra-module FKs** | `Loan_H → Loan_Keymap`, `LoanPerformance_H → Loan_Keymap` | Child-to-parent within the same entity cluster |
| **Reference table lookups** | `Loan_H → LoanPurpose_R`, `LoanPerformance_H → DelinquencyStatus_R` | Reference decodes, especially from append-only tables |
| **Cross-module joins** | `Domain.Loan_H → Prediction.loan_features`, `Domain.Customer_H → Search.entity_embedding` | Joins between modules are frequently omitted |
| **Semantic joins** | `Domain.LoanStatement_H → Domain.Payment_H → Domain.LoanPerformance_H` | Multi-hop chains used in lineage and audit queries |
| **Reverse directions** | If A→B is registered, register B→A if agents will traverse in both directions | Bidirectional traversal requirements are easy to miss |

**Validation step — required before deployment:**

Run the following query after populating `table_relationship`. For each entity pair that agents are expected to join, confirm a path exists and that the `path_joins` column contains syntactically valid SQL join conditions:

```sql
-- Verify a specific traversal path exists (run for each expected entity pair)
SELECT hop_count, path_tables, path_joins
FROM {ProductName}_Semantic.v_relationship_paths
WHERE source_table = '{TableA}'
  AND target_table = '{TableB}'
ORDER BY hop_count;

-- Verify no isolated tables (tables with no registered relationships)
SELECT em.table_name
FROM {ProductName}_Semantic.entity_metadata em
WHERE em.is_active = 1
  AND NOT EXISTS (
    SELECT 1 FROM {ProductName}_Semantic.table_relationship r
    WHERE r.is_active = 1
      AND (r.from_table = em.table_name OR r.to_table = em.table_name)
  );
```

A table that appears in `entity_metadata` but has no entries in `table_relationship` is either a deliberate standalone entity (document why in `Design_Decision`) or an omission that will cause agent navigation failures.

**The ERD recipe (`QC-SEMANTIC-002`) in the `Query_Cookbook` generates an entity-relationship listing directly from `table_relationship`.** Generating this output and reviewing it is a practical completeness check — if the ERD looks incomplete, the `table_relationship` data is incomplete.

---

## Appendix: Quick Reference

**Core Tables**: data_product_registry, entity_metadata, column_metadata, table_relationship, naming_standard, data_product_map, data_product_map_primary_objects
**Required Views**: v_relationship_paths (multi-hop path discovery)
**Key Principle**: Entity = Table, Attribute = Column
**Scale**: Hundreds of metadata rows (not millions)
**Agent Discovery**: Start with the Data Product Orientation Manifest, use data_product_registry as the backing catalogue, then query data_product_map to find deployed modules

---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 2.11 | 2026-07-18 | Added the access-object metadata layer (resolves issue #9, Semantic half): Section 3.12 `access_object` (registry of consumable objects - open `access_role` baseline BASE/PASSTHROUGH/COMPOSITE, `represents_entity`, `object_grain`, `is_agent_consumable`, `resolves_to_object`), with a normative consumption contract (resolve through the registry, not base tables; object names are not a contract), an establish-once-at-deployment ownership clause, and a note on its relationship to `view_metadata`; Section 3.13 `access_composition` (what a COMPOSITE encapsulates, referenced by entity); Section 3.14 access-resolved relationship paths (join targets rewritten to consumable objects). Logical schemas are normative; Teradata DDL is illustrative and binds per platform extension. Updated required tables/views (8.1, 8.2). Pairs with Master 2.1. | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 2.10 | 2026-07-18 | Added the agent orientation contract: Section 3.10 `data_product_orientation` (resolves issue #20) - one ordered row per product resource with a controlled `resource_role` vocabulary, `is_required` and `discovery_order`, formalising the Orientation Layer prose of Section 3.4 into a queryable, conformance-checkable relation with trust-before-analytical ordering and validation queries; Section 3.11 `data_product_manifest` (generated view over the registry and orientation, so the manifest cannot drift from source metadata). Updated required tables/views (8.1, 8.2). New objects use canonical lifecycle columns per the Temporal & Lifecycle Metadata Standard. | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 2.9 | 2026-07-15 | Added the catalogue exposure objects: Section 3.7 `view_metadata` view catalogue (resolves issue #36 — one row per base-table exposure, controlled `view_type` vocabulary, `is_primary` uniqueness, validation queries, interim on the issue #9 path); Section 3.8 `view_column_type` curated view-column types; Section 3.9 `column_catalogue` live hybrid column catalogue with value provenance (`data_type_source`, `description_source`, `is_documented` — addresses issue #22 for this module). Documented Semantic exposure of Observability's definitional `data_lineage` (Section 7). Updated required tables/views (8.1, 8.2). New tables use canonical lifecycle columns per the Temporal & Lifecycle Metadata Standard. | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 2.8 | 2026-07-15 | Added Section 3.6 `data_product_map_primary_objects` (resolves issue #14): one row per primary object with exact fully qualified identity, controlled `object_role` vocabulary, `usage_guidance`, optional `table_kind`, and validation queries (orphan modules, missing objects, invalid roles, catalogue-kind mismatches, duplicates). Deprecated the `primary_tables` / `primary_views` CSV columns (retained for backward compatibility only) and updated agent discovery queries to use the child relation. New table adopts canonical lifecycle columns (`created_dts` / `updated_dts`) per the Temporal & Lifecycle Metadata Standard. | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 2.7 | 2026-05-30 | Added `data_product_registry` and the Data Product Orientation Layer as the product-level discovery contract for agents and MCP clients. Clarified that clients should read the product manifest, contract, semantic model, policy, quality, and lineage before querying `data_product_map` for module locations or using approved data access. | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 2.6 | 2026-04-15 | Added Section 8.5 `table_relationship` Completeness Requirement: all inter-entity relationships must be registered — intra-module FKs, reference table lookups, cross-module joins, multi-hop semantic joins, and bidirectional traversals. Added path existence and isolation validation queries. Cross-referenced ERD recipe (QC-SEMANTIC-002) as a completeness check. Updated Section 8.4 design checklist with deployment_status requirement, table_relationship completeness check, and v_relationship_paths validation. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 2.5 | 2026-03-20 | Fixed boolean column definitions and filter values throughout: converted all CHAR(1) DEFAULT 'Y'/'N' columns (is_active, is_pii, is_sensitive, is_required, is_mandatory) to BYTEINT NOT NULL DEFAULT 1/0; converted all = 'Y' / = 'N' filter values to = 1 / = 0 to align with platform boolean standard. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 2.4 | 2026-03-20 | Revised Documentation Capture Requirements section — updated to reflect self-contained data product principle. Documentation tables now reside in the Memory database ({ProductName}_Memory), not a shared dp_documentation database. Removed data_product column from INSERT templates, removed bootstrap checklist item, updated prose references from dp_documentation to Memory database. |
| 2.3 | 2026-03-20 | Added Section 8.4 Documentation Capture Requirements — minimum dp_documentation records, typical decision categories, output file placement, design checklist additions, and reference to Memory Module Section 8 protocol. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 2.2 | 2026-03-18 | Applied surrogate key naming convention to internal management tables: renamed {table}_key → {table}_id for all GENERATED ALWAYS AS IDENTITY columns | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 2.1 | 2026-03-17 | Updated naming convention: {entity}_id = Surrogate Key, {entity}_key = Natural Business Key, aligned with Domain Module Design Standard v2.1 | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.0 | 2025-02-09 | Initial Semantic Module Design Standard | Nathan Green, Worldwide Data Architecture Team, Teradata |
