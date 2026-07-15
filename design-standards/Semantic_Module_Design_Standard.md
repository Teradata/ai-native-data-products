# Semantic Module Design Standard
## AI-Native Data Product Architecture - Version 2.8 (Tested & Validated)

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 2.8 |
| **Status** | STANDARD - Tested on Teradata |
| **Last Updated** | 2026-07-15 |
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
    -- Metadata Standard (design-standards/core/). is_active semantics:
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

---

## 8. Designer Responsibilities

### 8.1 Required Tables

- data_product_registry (product-level registry in governance database)
- entity_metadata (~10-50 rows)
- column_metadata (~100-500 rows)
- table_relationship (~20-100 rows)
- naming_standard (~10-30 rows)
- data_product_map (one row per deployed module)

### 8.2 Required Views

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
| 2.8 | 2026-07-15 | Added Section 3.6 `data_product_map_primary_objects` (resolves issue #14): one row per primary object with exact fully qualified identity, controlled `object_role` vocabulary, `usage_guidance`, optional `table_kind`, and validation queries (orphan modules, missing objects, invalid roles, catalogue-kind mismatches, duplicates). Deprecated the `primary_tables` / `primary_views` CSV columns (retained for backward compatibility only) and updated agent discovery queries to use the child relation. New table adopts canonical lifecycle columns (`created_dts` / `updated_dts`) per the Temporal & Lifecycle Metadata Standard. | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 2.7 | 2026-05-30 | Added `data_product_registry` and the Data Product Orientation Layer as the product-level discovery contract for agents and MCP clients. Clarified that clients should read the product manifest, contract, semantic model, policy, quality, and lineage before querying `data_product_map` for module locations or using approved data access. | Paul Dancer, Worldwide Data Architecture Team, Teradata |
| 2.6 | 2026-04-15 | Added Section 8.5 `table_relationship` Completeness Requirement: all inter-entity relationships must be registered — intra-module FKs, reference table lookups, cross-module joins, multi-hop semantic joins, and bidirectional traversals. Added path existence and isolation validation queries. Cross-referenced ERD recipe (QC-SEMANTIC-002) as a completeness check. Updated Section 8.4 design checklist with deployment_status requirement, table_relationship completeness check, and v_relationship_paths validation. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 2.5 | 2026-03-20 | Fixed boolean column definitions and filter values throughout: converted all CHAR(1) DEFAULT 'Y'/'N' columns (is_active, is_pii, is_sensitive, is_required, is_mandatory) to BYTEINT NOT NULL DEFAULT 1/0; converted all = 'Y' / = 'N' filter values to = 1 / = 0 to align with platform boolean standard. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 2.4 | 2026-03-20 | Revised Documentation Capture Requirements section — updated to reflect self-contained data product principle. Documentation tables now reside in the Memory database ({ProductName}_Memory), not a shared dp_documentation database. Removed data_product column from INSERT templates, removed bootstrap checklist item, updated prose references from dp_documentation to Memory database. |
| 2.3 | 2026-03-20 | Added Section 8.4 Documentation Capture Requirements — minimum dp_documentation records, typical decision categories, output file placement, design checklist additions, and reference to Memory Module Section 8 protocol. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 2.2 | 2026-03-18 | Applied surrogate key naming convention to internal management tables: renamed {table}_key → {table}_id for all GENERATED ALWAYS AS IDENTITY columns | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 2.1 | 2026-03-17 | Updated naming convention: {entity}_id = Surrogate Key, {entity}_key = Natural Business Key, aligned with Domain Module Design Standard v2.1 | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.0 | 2025-02-09 | Initial Semantic Module Design Standard | Nathan Green, Worldwide Data Architecture Team, Teradata |
