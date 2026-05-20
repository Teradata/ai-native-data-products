# Memory Module Design Standard
## AI-Native Data Product Architecture - Version 1.7

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.7 |
| **Status** | STANDARD |
| **Last Updated** | 2026-03-20 |
| **Owner** | Nathan Green, Worldwide Data Architecture Team, Teradata |
| **Scope** | Memory Module (Agent State, Learning & Documentation Sub-Module) |
| **Type** | Design Standard (Structural Requirements) |
| **Companion** | Advocated Data Management Standards (Implementation Guidance) |

---

## Table of Contents

1. [AI-Native Memory Module Overview](#1-ai-native-memory-module-overview)
2. [Module Scope and Boundaries](#2-module-scope-and-boundaries)
3. [Agent State Structure](#3-agent-state-structure)
4. [Learning and Preference Patterns](#4-learning-and-preference-patterns)
5. [Privacy and Scoping](#5-privacy-and-scoping)
6. [Integration with Other Modules](#6-integration-with-other-modules)
7. [Designer Responsibilities](#7-designer-responsibilities)
8. [Documentation Sub-Module](#8-documentation-sub-module)

---

## 1. AI-Native Memory Module Overview

### 1.1 What Makes Memory Module AI-Native?

The Memory Module enables **agent learning, continuity, and collaboration** across sessions, users, and agent instances.

| AI-Native Characteristic | Purpose |
|-------------------------|---------|
| **Session Continuity** | Agents remember context across interactions |
| **Cross-Agent Learning** | Agents share successful strategies |
| **Preference Learning** | Agents adapt to user and business preferences |
| **Meta-Learning** | Agents learn what works and improve over time |
| **Privacy-Aware** | Scoped appropriately (user, team, organization) |
| **Knowledge Repository** | Captures design decisions, rationale, and operational knowledge via the Documentation Sub-Module |

### 1.2 Primary Purpose: Enable Agent Evolution

**Memory module enables:**

1. **Conversation History** - Track agent interactions and decisions
2. **Learned Strategies** - Store what approaches worked/failed
3. **User Preferences** - Remember stakeholder context and preferences
4. **Session State** - Maintain context across interactions
5. **Pattern Recognition** - Learn from outcomes over time
6. **Collaborative Learning** - Share insights across agent instances
7. **Design Knowledge** - Capture architectural decisions, business glossary, query patterns, and change history via the Documentation Sub-Module

### 1.3 Critical Principles

**Principle 1: Entity = Table (Not Instance)**

Memory references **entities** (tables), not **instances** (rows):
- ✅ Store: database_name, table_name (which entities were involved)
- ❌ Don't store: entity_id, instance IDs (individual records)

**Principle 2: Big Questions, Small Answers**

Agents process millions of records to answer questions. Memory stores the **metadata** about those processes:
- ✅ Store: SQL executed, patterns used, outcomes, decisions
- ✅ Store: "Analyzed 5M Party records using this query pattern"
- ❌ Don't store: Individual keys/IDs from those 5M records
- ❌ Don't store: Results of the query (that's in Domain)

**Why this matters**:
```
Agent Query: "Find high-value customers" (processes 50M Party records)

Memory stores:
✅ SQL: "SELECT ... FROM Party_H WHERE credit_score > 0.8"
✅ Tables involved: {database: "Domain", table: "Party_H"}
✅ Result count: 125,000 customers found
✅ Execution time: 2.3 seconds
✅ Outcome: "Generated actionable list, user satisfied"

Memory does NOT store:
❌ 125,000 individual party_id values
❌ Customer names, details, attributes
❌ Query result data (that lives in Domain or temp tables)
```

**Scale check**: Memory should have thousands to tens of thousands of rows (sessions, interactions, learnings), not millions.

---

## 2. Module Scope and Boundaries

### 2.1 What Belongs in Memory Module

**IN SCOPE:**

1. **Agent Interaction Metadata**
   - What questions agent answered
   - What SQL/queries were executed
   - Which entities (tables) were involved
   - What decisions were made
   - **NOT individual record keys/IDs from results**

2. **Agent Learning Metadata**
   - Successful strategies and patterns
   - Query optimization insights
   - Which approaches worked/failed
   - **NOT the actual data that was analyzed**

3. **Preferences**
   - User preferences
   - Agent configuration
   - Business context
   - **NOT user PII or detailed profiles**

4. **Session State**
   - Current session context
   - Active workflows
   - **NOT detailed result sets**

5. **Design Knowledge** (via Documentation Sub-Module)
   - Architectural decisions and rationale (Architecture Decision Records)
   - Business glossary terms introduced by each module
   - Proven query patterns (query cookbook)
   - Module version registry and change history
   - Operational notes and known issues
   - **NOT business domain data — keep in Domain Module**

**OUT OF SCOPE:**

- ❌ **Business domain data** → Domain Module
- ❌ **Query results** → Domain Module or temporary tables
- ❌ **Individual record keys/IDs** → Don't track millions of keys/IDs
- ❌ **Detailed customer/product data** → Domain Module

**Key Distinction**:
- Memory = Agent metadata (what agent did, which tables, what happened)
- Domain = Business data (the actual 50M customer records)

### 2.2 "Big Questions, Small Answers" Principle

**Agents ask big questions of the data platform**:
- Query involving 50 million Party records
- Analysis across 2 billion transactions
- Search through 10 million products

**Modules other than Domain provide small answers (metadata)**:
- Memory: "Here's the SQL pattern that worked"
- Semantic: "Here's how to join these tables"
- Prediction: "Here's the feature importance scores"
- Search: "Here are the 10 most similar items"

**Memory should NOT try to store**:
- ❌ Individual keys/IDs from 50M query results
- ❌ Details of 2B transactions processed
- ❌ All 10M products that were searched

**Memory SHOULD store**:
- ✅ SQL that queried 50M records
- ✅ Tables involved in analysis (Domain.Party_H, Domain.Transaction_H)
- ✅ Outcome: "Found 125K high-value customers, user satisfied"
- ✅ Pattern: "Queries filtering on is_current first perform 3x faster"

### 2.2 Privacy and Scoping Levels

**Memory must be scoped appropriately:**

| Scope Level | Visible To | Use Case | Example |
|-------------|-----------|----------|---------|
| **User** | Single user only | Personal preferences | User's preferred report format |
| **Team** | Team members | Shared workflows | Team's approved analysis templates |
| **Organization** | All users | Enterprise patterns | Successful query strategies |
| **Agent Instance** | Specific agent | Agent-specific learning | This agent's optimization history |

**Requirement**: Every Memory record MUST have a scope indicator.

---

## 3. Agent State Structure

### 3.1 Session State

```sql
CREATE TABLE Memory.agent_session (
    session_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    session_key VARCHAR(100) NOT NULL,
    agent_key VARCHAR(100) NOT NULL,
    user_key VARCHAR(100),
    
    -- Session context
    session_start_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    session_end_dts TIMESTAMP(6) WITH TIME ZONE,
    session_status VARCHAR(20),  -- 'ACTIVE', 'COMPLETED', 'ABANDONED'
    
    -- Session metadata
    session_goal VARCHAR(500),
    session_context_json JSON,  -- Flexible context storage
    
    -- Privacy scope
    scope_level VARCHAR(20) NOT NULL,  -- 'USER', 'TEAM', 'ORGANIZATION', 'AGENT'
    scope_identifier VARCHAR(100),     -- user_key, team_key, org_key, agent_key
    
    -- Metadata
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (session_id);

COMMENT ON TABLE Memory.agent_session IS 
'Agent session state - tracks active and historical agent sessions for continuity across interactions';

COMMENT ON COLUMN Memory.agent_session.session_id IS 
'Surrogate key for session record';

COMMENT ON COLUMN Memory.agent_session.session_key IS 
'Business session identifier - unique ID for tracking session across systems';

COMMENT ON COLUMN Memory.agent_session.agent_key IS 
'Agent identifier - which agent instance is handling this session';

COMMENT ON COLUMN Memory.agent_session.user_key IS 
'User identifier - which user is interacting with agent';

COMMENT ON COLUMN Memory.agent_session.session_start_dts IS 
'Session start timestamp - when agent session began';

COMMENT ON COLUMN Memory.agent_session.session_end_dts IS 
'Session end timestamp - when agent session completed or was abandoned - NULL for active sessions';

COMMENT ON COLUMN Memory.agent_session.session_status IS 
'Session status - ACTIVE (ongoing), COMPLETED (successfully finished), ABANDONED (user left)';

COMMENT ON COLUMN Memory.agent_session.session_goal IS 
'Session goal or objective - what user is trying to accomplish in this session';

COMMENT ON COLUMN Memory.agent_session.session_context_json IS 
'Flexible session context - JSON document with session-specific metadata, agent retrieves and processes externally';

COMMENT ON COLUMN Memory.agent_session.scope_level IS 
'Privacy scope level - USER (private), TEAM (team-shared), ORGANIZATION (company-wide), AGENT (agent-specific)';

COMMENT ON COLUMN Memory.agent_session.scope_identifier IS 
'Scope identifier - user_key for USER scope, team_key for TEAM scope, etc. - enforces privacy boundaries';

COMMENT ON COLUMN Memory.agent_session.created_at IS 
'Timestamp when session record was created';
```

### 3.2 Agent Interaction Log

```sql
CREATE TABLE Memory.agent_interaction (
    interaction_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    session_id INTEGER NOT NULL,  -- FK to agent_session
    
    -- Interaction details
    interaction_seq INTEGER NOT NULL,
    interaction_type VARCHAR(50),  -- 'QUERY', 'ACTION', 'DECISION', 'EXPLANATION'
    interaction_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    
    -- What happened
    user_input VARCHAR(4000),
    agent_response VARCHAR(4000),
    action_taken VARCHAR(500),
    
    -- Entity references (TABLE LEVEL - comma-separated list)
    referenced_tables VARCHAR(1000),  -- 'Domain.Party_H, Prediction.customer_features'
    
    -- Query executed (if applicable)
    sql_executed VARCHAR(4000),
    query_result_count INTEGER,
    execution_time_ms INTEGER,
    
    -- Outcome
    outcome_status VARCHAR(20),  -- 'SUCCESS', 'PARTIAL', 'FAILED'
    user_feedback VARCHAR(20),   -- 'POSITIVE', 'NEUTRAL', 'NEGATIVE', NULL
    
    -- Privacy scope
    scope_level VARCHAR(20) NOT NULL,
    scope_identifier VARCHAR(100),
    
    -- Metadata
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (interaction_id);

COMMENT ON TABLE Memory.agent_interaction IS 
'Agent interaction log - records what agent did, which tables were involved, and outcomes for learning and audit';

COMMENT ON COLUMN Memory.agent_interaction.interaction_id IS 
'Surrogate key for interaction record';

COMMENT ON COLUMN Memory.agent_interaction.session_id IS 
'Foreign key to agent_session - links interaction to parent session';

COMMENT ON COLUMN Memory.agent_interaction.interaction_seq IS 
'Sequence number within session - orders interactions chronologically within a session';

COMMENT ON COLUMN Memory.agent_interaction.interaction_type IS 
'Type of interaction - QUERY (data retrieval), ACTION (data modification), DECISION (business decision), EXPLANATION (reasoning provided)';

COMMENT ON COLUMN Memory.agent_interaction.interaction_dts IS 
'Timestamp of interaction - when this interaction occurred';

COMMENT ON COLUMN Memory.agent_interaction.user_input IS 
'User question or request - what the user asked the agent to do';

COMMENT ON COLUMN Memory.agent_interaction.agent_response IS 
'Agent response summary - brief description of what agent provided or did';

COMMENT ON COLUMN Memory.agent_interaction.action_taken IS 
'Specific action executed - describes what the agent actually did';

COMMENT ON COLUMN Memory.agent_interaction.referenced_tables IS 
'Tables involved in interaction - comma-separated list of database.table names, TABLE LEVEL not instance keys, format: Domain.Party_H, Prediction.customer_features';

COMMENT ON COLUMN Memory.agent_interaction.sql_executed IS 
'SQL query executed - actual SQL statement run by agent if applicable';

COMMENT ON COLUMN Memory.agent_interaction.query_result_count IS 
'Number of records returned - aggregate count, NOT individual record keys';

COMMENT ON COLUMN Memory.agent_interaction.execution_time_ms IS 
'Query execution time in milliseconds - performance metric';

COMMENT ON COLUMN Memory.agent_interaction.outcome_status IS 
'Outcome of interaction - SUCCESS (worked as expected), PARTIAL (incomplete), FAILED (error occurred)';

COMMENT ON COLUMN Memory.agent_interaction.user_feedback IS 
'User feedback on interaction - POSITIVE, NEUTRAL, NEGATIVE, NULL (no feedback) - used for agent learning';

COMMENT ON COLUMN Memory.agent_interaction.scope_level IS 
'Privacy scope - USER, TEAM, ORGANIZATION, AGENT - determines who can access this interaction';

COMMENT ON COLUMN Memory.agent_interaction.scope_identifier IS 
'Scope identifier - user_key, team_key, org_key, or agent_key matching scope_level';

COMMENT ON COLUMN Memory.agent_interaction.created_at IS 
'Timestamp when interaction record was created';
```

**Referenced tables format (VARCHAR comma-separated)**:
```
'Domain.Party_H, Prediction.customer_features'
'Domain.Party_H'
'Domain.Product_H, Search.product_embedding, Prediction.product_affinity'
```

**Example query pattern**:
```sql
-- Find all decisions related to Party table (TESTED ✅)
SELECT 
    ai.interaction_seq,
    ai.user_input,
    ai.action_taken,
    ai.outcome_status,
    ai.sql_executed,
    ai.query_result_count,
    ai.referenced_tables
FROM Memory.agent_interaction ai
WHERE ai.referenced_tables LIKE '%Domain.Party_H%'
  AND ai.interaction_type = 'DECISION'
ORDER BY ai.interaction_dts DESC;

-- Find interactions involving customer_features table
SELECT 
    interaction_seq,
    user_input,
    referenced_tables,
    query_result_count
FROM Memory.agent_interaction
WHERE referenced_tables LIKE '%customer_features%';

-- Find interactions involving Domain database
SELECT 
    interaction_seq,
    interaction_type,
    referenced_tables,
    outcome_status
FROM Memory.agent_interaction
WHERE referenced_tables LIKE '%Domain.%';

-- Find interactions involving multiple specific tables
SELECT * FROM Memory.agent_interaction
WHERE referenced_tables LIKE '%Party_H%'
  AND referenced_tables LIKE '%Transaction_H%';
```

**Format**: Comma-separated list of qualified table names: `database.table_name, database.table_name`

**What Memory stores**:
- ✅ "Agent analyzed Party_H table" (table name in referenced_tables)
- ✅ "Query returned 125,000 results" (count only)
- ✅ "SQL: SELECT ... FROM Party_H WHERE credit_score > 0.8" (SQL text)

**What Memory does NOT store**:
- ❌ 125,000 individual party_id values
- ❌ Customer names from those 125K records
- ❌ Detailed query results (that data lives in Domain)

### 3.3 JSON Column Usage Guidelines

**Use VARCHAR for**: Lists of simple values (table names, entity references)
- `referenced_tables VARCHAR(1000)` - Comma-separated table names
- `involved_tables VARCHAR(1000)` - Comma-separated table names

**Use JSON for**: Complex, flexible, or nested structures (agent retrieves and processes externally)
- `session_context_json` - Varying session context structures
- `strategy_metadata_json` - Complex strategy definitions
- `preference_value_json` - Structured preference data
- `pattern_definition_json` - Complex pattern specifications

**Rationale**: Agents can retrieve JSON documents and decode/search them in application layer (Python, etc.) where JSON parsing is more flexible and powerful.

---

## 4. Learning and Preference Patterns

### 4.1 Learned Strategies

```sql
CREATE TABLE Memory.learned_strategy (
    strategy_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    strategy_name VARCHAR(128) NOT NULL,
    strategy_description VARCHAR(1000),
    
    -- Strategy context
    strategy_category VARCHAR(50),  -- 'QUERY_OPTIMIZATION', 'FEATURE_SELECTION', 'ERROR_HANDLING'
    applies_to_scenario VARCHAR(500),
    
    -- Strategy definition
    strategy_pattern VARCHAR(4000),  -- SQL pattern, logic, approach
    strategy_metadata_json JSON,
    
    -- Learning metadata
    discovered_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    discovered_by_agent VARCHAR(100),
    times_used INTEGER DEFAULT 0,
    success_rate DECIMAL(5,4),  -- 0.0-1.0
    
    -- Privacy scope
    scope_level VARCHAR(20) NOT NULL,
    scope_identifier VARCHAR(100),
    
    -- Status
    is_active BYTEINT NOT NULL DEFAULT 1,
    is_validated BYTEINT NOT NULL DEFAULT 0,
    validation_dts TIMESTAMP(6) WITH TIME ZONE,
    
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (strategy_id);

COMMENT ON TABLE Memory.learned_strategy IS 
'Strategies learned by agents - successful patterns and approaches discovered through experience';

COMMENT ON COLUMN Memory.learned_strategy.strategy_id IS 
'Surrogate key for learned strategy record';

COMMENT ON COLUMN Memory.learned_strategy.strategy_name IS 
'Strategy name - descriptive identifier for this learned approach';

COMMENT ON COLUMN Memory.learned_strategy.strategy_description IS 
'Strategy description - explains what this strategy does and when to apply it';

COMMENT ON COLUMN Memory.learned_strategy.strategy_category IS 
'Strategy category - QUERY_OPTIMIZATION, FEATURE_SELECTION, ERROR_HANDLING, etc. - classifies strategy type';

COMMENT ON COLUMN Memory.learned_strategy.applies_to_scenario IS 
'Scenario where strategy applies - describes conditions or context where this strategy is effective';

COMMENT ON COLUMN Memory.learned_strategy.strategy_pattern IS 
'Strategy implementation - SQL pattern, logic description, or approach details';

COMMENT ON COLUMN Memory.learned_strategy.strategy_metadata_json IS 
'Additional strategy metadata - JSON document with complex strategy details, agent processes externally';

COMMENT ON COLUMN Memory.learned_strategy.discovered_dts IS 
'When strategy was discovered - timestamp of learning event';

COMMENT ON COLUMN Memory.learned_strategy.discovered_by_agent IS 
'Agent that discovered this strategy - agent_key that learned this pattern';

COMMENT ON COLUMN Memory.learned_strategy.times_used IS 
'Usage count - how many times this strategy has been applied';

COMMENT ON COLUMN Memory.learned_strategy.success_rate IS 
'Success rate - 0.0 to 1.0, percentage of times strategy led to successful outcome';

COMMENT ON COLUMN Memory.learned_strategy.scope_level IS 
'Privacy scope - USER, TEAM, ORGANIZATION, AGENT - determines who can use this strategy';

COMMENT ON COLUMN Memory.learned_strategy.scope_identifier IS 
'Scope identifier - user_key, team_key, org_key, or agent_key for access control';

COMMENT ON COLUMN Memory.learned_strategy.is_active IS 
'Active indicator - 1 = strategy is active and should be used, 0 = deprecated';

COMMENT ON COLUMN Memory.learned_strategy.is_validated IS 
'Validation status - 1 = strategy validated by human or testing, 0 = discovered but not yet validated';

COMMENT ON COLUMN Memory.learned_strategy.validation_dts IS 
'When strategy was validated - timestamp of validation event';

COMMENT ON COLUMN Memory.learned_strategy.created_at IS 
'Timestamp when strategy record was created';

COMMENT ON COLUMN Memory.learned_strategy.updated_at IS 
'Timestamp when strategy record was last updated - tracks strategy refinement';
```

**Example learned strategy**:
```sql
INSERT INTO Memory.learned_strategy (
    strategy_name, strategy_description, strategy_category,
    applies_to_scenario, strategy_pattern,
    discovered_by_agent, success_rate, scope_level
) VALUES (
    'CustomerChurnAnalysis_Optimize',
    'For churn analysis queries, filter on is_current first, then join to features',
    'QUERY_OPTIMIZATION',
    'Queries involving Party + customer_features with is_current filter',
    'SELECT ... FROM Party_H WHERE is_current=1 JOIN customer_features ...',
    'agent_analytics_001',
    0.92,
    'ORGANIZATION'
);
```

### 4.2 User Preferences

```sql
CREATE TABLE Memory.user_preference (
    preference_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- User identification
    user_key VARCHAR(100) NOT NULL,
    user_group VARCHAR(100),
    
    -- Preference definition
    preference_category VARCHAR(50),  -- 'REPORT_FORMAT', 'DATA_FILTER', 'AGGREGATION_LEVEL'
    preference_name VARCHAR(128) NOT NULL,
    preference_value VARCHAR(1000),
    preference_value_json JSON,
    
    -- Context
    applies_to_entity VARCHAR(100),  -- Which entities this preference applies to
    applies_to_scenario VARCHAR(500),
    
    -- Learning
    learned_from_interactions INTEGER,  -- How many interactions contributed
    confidence DECIMAL(5,4),  -- 0.0-1.0 confidence in preference
    last_used_dts TIMESTAMP(6) WITH TIME ZONE,
    
    -- Privacy
    scope_level VARCHAR(20) DEFAULT 'USER',
    
    -- Status
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (preference_id);

COMMENT ON TABLE Memory.user_preference IS 
'User and stakeholder preferences learned from interactions - enables personalized agent behavior';

COMMENT ON COLUMN Memory.user_preference.preference_id IS 
'Surrogate key for preference record';

COMMENT ON COLUMN Memory.user_preference.user_key IS 
'User identifier name - which user this preference belongs to';

COMMENT ON COLUMN Memory.user_preference.user_group IS 
'User group or team - for group-level preferences';

COMMENT ON COLUMN Memory.user_preference.preference_category IS 
'Preference category - REPORT_FORMAT, DATA_FILTER, AGGREGATION_LEVEL, VISUALIZATION_TYPE, etc.';

COMMENT ON COLUMN Memory.user_preference.preference_name IS 
'Preference name - specific preference identifier within category';

COMMENT ON COLUMN Memory.user_preference.preference_value IS 
'Preference value - simple text value for basic preferences';

COMMENT ON COLUMN Memory.user_preference.preference_value_json IS 
'Complex preference value - JSON document for structured preferences, agent processes externally';

COMMENT ON COLUMN Memory.user_preference.applies_to_entity IS 
'Entity this preference applies to - table name or entity type';

COMMENT ON COLUMN Memory.user_preference.applies_to_scenario IS 
'Scenario where preference applies - context or use case for this preference';

COMMENT ON COLUMN Memory.user_preference.learned_from_interactions IS 
'Number of interactions that contributed to learning this preference - confidence indicator';

COMMENT ON COLUMN Memory.user_preference.confidence IS 
'Confidence in preference - 0.0 to 1.0, higher values indicate stronger evidence for this preference';

COMMENT ON COLUMN Memory.user_preference.last_used_dts IS 
'Last time preference was applied - tracks preference usage recency';

COMMENT ON COLUMN Memory.user_preference.scope_level IS 
'Privacy scope - USER (default, personal), TEAM, ORGANIZATION - determines visibility';

COMMENT ON COLUMN Memory.user_preference.is_active IS 
'Active indicator - 1 = preference active, 0 = deprecated or superseded';

COMMENT ON COLUMN Memory.user_preference.created_at IS 
'Timestamp when preference was first learned';

COMMENT ON COLUMN Memory.user_preference.updated_at IS 
'Timestamp when preference was last updated or reinforced';
```

### 4.3 Pattern Discovery

```sql
CREATE TABLE Memory.discovered_pattern (
    pattern_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    pattern_name VARCHAR(128) NOT NULL,
    pattern_description VARCHAR(1000),
    
    -- Pattern definition
    pattern_type VARCHAR(50),  -- 'CORRELATION', 'TEMPORAL', 'TABLE_RELATIONSHIP', 'ANOMALY'
    pattern_definition_json JSON,
    
    -- Statistical support (summary statistics, NOT individual records)
    sample_size INTEGER,           -- How many records analyzed
    occurrences INTEGER,            -- How many times pattern observed
    confidence_score DECIMAL(5,4),
    statistical_significance DECIMAL(5,4),
    
    -- Discovery metadata
    discovered_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    discovered_by_agent VARCHAR(100),
    is_validated BYTEINT NOT NULL DEFAULT 0,
    
    -- Entity references (TABLE LEVEL - comma-separated list)
    involved_tables VARCHAR(1000),  -- 'Domain.Party_H, Prediction.customer_features'
    
    -- Privacy scope
    scope_level VARCHAR(20) NOT NULL,
    scope_identifier VARCHAR(100),
    
    -- Status
    is_active BYTEINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (pattern_id);

COMMENT ON TABLE Memory.discovered_pattern IS 
'Patterns discovered by agents through data analysis - stores pattern metadata and statistical support, NOT individual record details';

COMMENT ON COLUMN Memory.discovered_pattern.pattern_id IS 
'Surrogate key for discovered pattern record';

COMMENT ON COLUMN Memory.discovered_pattern.pattern_name IS 
'Pattern name - descriptive identifier for discovered insight';

COMMENT ON COLUMN Memory.discovered_pattern.pattern_description IS 
'Pattern description - explains the discovered pattern and its business implications';

COMMENT ON COLUMN Memory.discovered_pattern.pattern_type IS 
'Pattern type - CORRELATION, TEMPORAL, TABLE_RELATIONSHIP, ANOMALY - classifies discovery type';

COMMENT ON COLUMN Memory.discovered_pattern.pattern_definition_json IS 
'Pattern definition - JSON document with pattern details, conditions, and formulas, agent processes externally';

COMMENT ON COLUMN Memory.discovered_pattern.sample_size IS 
'Sample size - how many records were analyzed to discover pattern - indicates evidence strength';

COMMENT ON COLUMN Memory.discovered_pattern.occurrences IS 
'Occurrences - how many times pattern was observed in data - frequency indicator';

COMMENT ON COLUMN Memory.discovered_pattern.confidence_score IS 
'Confidence score - 0.0 to 1.0, statistical confidence in pattern validity';

COMMENT ON COLUMN Memory.discovered_pattern.statistical_significance IS 
'Statistical significance - p-value or significance score for pattern validity testing';

COMMENT ON COLUMN Memory.discovered_pattern.discovered_dts IS 
'When pattern was discovered - timestamp of discovery event';

COMMENT ON COLUMN Memory.discovered_pattern.discovered_by_agent IS 
'Agent that discovered pattern - agent_key that performed analysis';

COMMENT ON COLUMN Memory.discovered_pattern.is_validated IS 
'Validation status - 1 = pattern validated by human expert or testing, 0 = discovered but not yet validated';

COMMENT ON COLUMN Memory.discovered_pattern.involved_tables IS 
'Tables involved in pattern - comma-separated list of database.table names, TABLE LEVEL not instance keys';

COMMENT ON COLUMN Memory.discovered_pattern.scope_level IS 
'Privacy scope - USER, TEAM, ORGANIZATION, AGENT - determines who can access this pattern';

COMMENT ON COLUMN Memory.discovered_pattern.scope_identifier IS 
'Scope identifier - user_key, team_key, org_key, or agent_key for access control';

COMMENT ON COLUMN Memory.discovered_pattern.is_active IS 
'Active indicator - 1 = pattern active, 0 = deprecated or invalidated';

COMMENT ON COLUMN Memory.discovered_pattern.created_at IS 
'Timestamp when pattern record was created';
```

**Example pattern (table-level references)**:
```json
{
  "pattern": "Customers with age_normalized > 0.8 and recency_score > 0.9 have 3x higher conversion",
  "statistical_support": {
    "sample_size": 15000,
    "occurrences": 450,
    "p_value": 0.002
  }
}
```

**Involved tables stored as VARCHAR**: `'Domain.Party_H, Prediction.customer_features'`

**What is stored**: Pattern definition (JSON), which tables (VARCHAR), sample size
**What is NOT stored**: The 15,000 individual party_id values

**Query patterns involving specific tables**:
```sql
-- Find patterns discovered about Party table (TESTED ✅)
SELECT 
    dp.pattern_name,
    dp.pattern_description,
    dp.sample_size,
    dp.confidence_score,
    dp.involved_tables
FROM Memory.discovered_pattern dp
WHERE dp.involved_tables LIKE '%Party_H%'
  AND dp.is_validated = 1
ORDER BY dp.confidence_score DESC;

-- Find patterns involving specific database
SELECT 
    pattern_name,
    pattern_description,
    sample_size,
    involved_tables
FROM Memory.discovered_pattern
WHERE involved_tables LIKE '%Domain.%'
ORDER BY confidence_score DESC;

-- Find patterns involving multiple specific tables
SELECT 
    pattern_name,
    involved_tables,
    confidence_score
FROM Memory.discovered_pattern
WHERE involved_tables LIKE '%Party_H%'
  AND involved_tables LIKE '%customer_features%';
```

---

## 5. Privacy and Scoping

### 5.1 Scope Levels (REQUIRED)

**Every Memory record MUST include scope:**

```sql
-- Standard scope columns (required in all Memory tables)
scope_level VARCHAR(20) NOT NULL,      -- 'USER', 'TEAM', 'ORGANIZATION', 'AGENT'
scope_identifier VARCHAR(100) NOT NULL -- user_key, team_key, org_key, agent_key
```

### 5.2 Privacy Patterns

```sql
-- Query user-specific memory only
SELECT * FROM Memory.user_preference
WHERE user_key = 'john.doe@company.com'
  AND scope_level = 'USER';

-- Query team-shared memory
SELECT * FROM Memory.learned_strategy
WHERE scope_level = 'TEAM'
  AND scope_identifier = 'analytics_team';

-- Query organization-wide patterns
SELECT * FROM Memory.discovered_pattern
WHERE scope_level = 'ORGANIZATION'
  AND is_validated = 1;
```

### 5.3 Data Minimization

**Store minimal PII in Memory**:
- ✅ Store user_key (identifier)
- ❌ Don't store user names, emails, demographics (join to Domain if needed)
- ✅ Store entity IDs (references)
- ❌ Don't store entity content (join to Domain/other modules)

---

## 6. Integration with Other Modules

### 6.1 Integration with Observability (Learning from Outcomes)

**Pattern**: Memory learns from Observability outcomes

```sql
-- Example: Agent learns which query patterns perform well
INSERT INTO Memory.learned_strategy (
    strategy_name, strategy_category, strategy_pattern,
    success_rate, discovered_by_agent, scope_level
)
SELECT 
    'OptimizedPartyQuery_' || CURRENT_DATE,
    'QUERY_OPTIMIZATION',
    sql_text,
    success_count * 1.0 / total_count AS success_rate,
    'agent_optimizer',
    'ORGANIZATION'
FROM (
    SELECT 
        sql_text,
        COUNT(*) AS total_count,
        SUM(CASE WHEN execution_time_ms < 1000 THEN 1 ELSE 0 END) AS success_count
    FROM Observability.query_log
    WHERE query_date >= CURRENT_DATE - 7
      AND table_accessed LIKE '%Party_H%'
    GROUP BY sql_text
    HAVING COUNT(*) >= 10
) patterns
WHERE success_count * 1.0 / total_count > 0.8;
```

### 6.2 Integration with Domain (Table-Level References)

**Pattern**: Memory references which tables (entities) were involved, not individual records

```sql
-- View: Agent interactions summary (no JSON parsing needed!)
CREATE VIEW Memory.v_interactions_summary
(
    -- View contract: agents see all returned columns without parsing the SELECT body
    session_id,
    interaction_seq,
    interaction_type,
    user_input,
    action_taken,
    sql_executed,
    query_result_count,
    execution_time_ms,
    outcome_status,
    user_feedback,
    referenced_tables,
    scope_level,
    scope_identifier,
    interaction_dts
)
AS
SELECT 
    ai.session_id,
    ai.interaction_seq,
    ai.interaction_type,
    ai.user_input,
    ai.action_taken,
    ai.sql_executed,
    ai.query_result_count,
    ai.execution_time_ms,
    ai.outcome_status,
    ai.user_feedback,
    ai.referenced_tables,  -- Simple VARCHAR column
    ai.scope_level,
    ai.scope_identifier,
    ai.interaction_dts
FROM Memory.agent_interaction ai;

COMMENT ON VIEW Memory.v_interactions_summary IS 
'Agent interaction summary - simplified view of agent interactions with table references for easy filtering and analysis';

-- Agent discovers all decisions about Party table (TESTED ✅)
SELECT 
    interaction_seq,
    user_input,
    action_taken,
    outcome_status,
    sql_executed,
    query_result_count,
    referenced_tables
FROM Memory.v_interactions_summary
WHERE referenced_tables LIKE '%Domain.Party_H%'
  AND interaction_type = 'DECISION'
ORDER BY interaction_dts DESC;

-- Agent discovers which tables are queried most frequently
-- Parse referenced_tables in application for aggregation
SELECT 
    referenced_tables,
    COUNT(*) AS query_count,
    AVG(query_result_count) AS avg_results,
    AVG(execution_time_ms) AS avg_execution_ms
FROM Memory.v_interactions_summary
WHERE interaction_type = 'QUERY'
GROUP BY referenced_tables
ORDER BY query_count DESC;
```

**Key Pattern**:
- Memory stores: Which tables were queried ('Domain.Party_H, Prediction.customer_features')
- Memory stores: How many results returned (125,000 records)
- Memory does NOT store: The 125,000 individual party_id values
- Simple VARCHAR LIKE queries (no JSON parsing needed)
- For detailed table-by-table analysis, parse comma-separated list in application

### 6.3 Integration with Search (Finding Relevant History)

```sql
-- Example: Find similar past sessions using embeddings
-- Embed current session context, find similar historical sessions

WITH current_session_embedding AS (
    SELECT session_key, session_context_json,
           embedding_vector  -- Generated from session description
    FROM Memory.agent_session
    WHERE session_key = 'S-CURRENT'
)
SELECT 
    past.session_key,
    past.session_goal,
    past.session_status,
    dt.distance AS similarity_score
FROM TD_VECTORDISTANCE (
    ON current_session_embedding AS TargetTable PARTITION BY ANY
    ON Search.entity_embedding AS ReferenceTable DIMENSION
    WHERE ReferenceTable.entity_type = 'SESSION'
      AND ReferenceTable.is_current = 1
    USING
        TargetFeatureColumns('embedding_vector')
        RefIDColumn('entity_id')
        RefFeatureColumns('embedding_vector')
        DistanceMeasure('cosine')
        TopK(5)
) AS dt
INNER JOIN Memory.agent_session past
    ON past.session_id = dt.reference_id
ORDER BY dt.distance;
```

### 6.4 Integration with Semantic (Applying Rules)

```sql
-- Agent applies learned business rules from Memory
SELECT 
    ls.strategy_name,
    ls.strategy_pattern,
    ls.success_rate
FROM Memory.learned_strategy ls
INNER JOIN Semantic.business_rule br
    ON br.rule_name = ls.applies_to_scenario
WHERE ls.strategy_category = 'QUERY_OPTIMIZATION'
  AND ls.is_active = 1
  AND ls.success_rate > 0.85
ORDER BY ls.success_rate DESC;
```

### 6.5 Integration with Documentation Sub-Module (Recording Decisions)

**Pattern**: Every module generates INSERT statements into the Memory database documentation tables during its design workflow. Documentation tables are co-located in the same `{ProductName}_Memory` database as the runtime memory tables.

```sql
-- When any module makes a significant design decision, it generates an INSERT:
INSERT INTO Memory.Design_Decision
(decision_id, decision_version, decision_title, decision_description,
 context, alternatives_considered, rationale, consequences,
 decision_status, decision_category,
 source_module, module_version, affects_table,
 decided_by, decided_date, valid_from, valid_to, is_current)
VALUES
('DD-MEMORY-001', 1,
 'Use BYTEINT for all boolean flags in Memory tables',
 'All is_active, is_validated, is_current columns use BYTEINT NOT NULL DEFAULT value',
 'Consistency with platform standard', 'Could use CHAR(1) Y/N or INTEGER',
 'BYTEINT is smallest integer type, native boolean equivalent on Teradata',
 'Consistent storage, clear intent, SQL filtering without type conversion',
 'ACCEPTED', 'NAMING',
 'MEMORY', '1.5.0', 'agent_session, agent_interaction, learned_strategy',
 'Worldwide Data Architecture Team', CURRENT_DATE, CURRENT_DATE, DATE '9999-12-31', 1);
```

See **Section 8** for the complete Documentation Sub-Module design, table definitions, workflows, and cross-module capture protocol.

---

## 7. Designer Responsibilities

### 7.1 What Designers Must Supply

| Element | Designer Supplies | Example |
|---------|-------------------|---------|
| **Agent types** | What agents will use this | analytics_agent, customer_service_agent |
| **Session patterns** | Expected session workflows | query_session, analysis_session |
| **Learning categories** | What to learn | query_patterns, feature_importance, user_preferences |
| **Privacy scoping** | Scope levels in use | USER, TEAM, ORGANIZATION |
| **Retention policies** | How long to keep memory | 90 days for sessions, 2 years for learnings |
| **Sharing policies** | What can be shared across agents | Organization-level strategies only |
| **Design decisions** | Key architectural/schema choices | Min. 3 decisions per module (see Section 8.3) |
| **Glossary terms** | Domain terms introduced by this module | Min. 3 terms for Business_Glossary |
| **Query cookbook entries** | Key query patterns for this module | Min. 1 recipe per module; min. 1 cross-module recipe per deployed module pair |

### 7.2 Minimum Seed Data Requirements

The following `Module_Registry` and `Design_Decision` entries are **required** at data product deployment, not optional.

#### Module_Registry — all considered modules

A `Module_Registry` row must exist for **every module that was considered during design**, not only those that were deployed. This gives agents and team members the full scope picture without needing to consult external documents.

| deployment_status | When to use |
|---|---|
| `DEPLOYED` | Module is active and queryable — a corresponding `data_product_map` entry exists in Semantic |
| `PLANNED` | Module is in scope but not yet built — record expected timeline or dependency in `module_scope` |
| `DEPRECATED` | Module was previously deployed and has been retired |

For any module with `deployment_status` of `PLANNED` or `DEPRECATED`, a corresponding `Design_Decision` entry is **required** explaining the rationale (e.g. why deferred, what triggered retirement, what the plan is).

**Minimum: one `Module_Registry` row per module considered, with `deployment_status` set correctly.**

#### Design_Decision — scope decisions

At a minimum, the following design decisions must be documented at first deployment:

| Decision ID pattern | Covers |
|---|---|
| `DD-SCOPE-001` | Database layout choice (separate databases per module vs. single database) |
| `DD-SCOPE-002` | Which modules are in scope and which are deferred or excluded, with rationale |
| `DD-{MODULE}-001` | Each module's primary index strategy and temporal pattern choice |

Any deviation from the AI-Native Data Product design standards must also be captured as a `Design_Decision` with `decision_category = 'ARCHITECTURE'`. See Section 7.3 for the deviation convention.

#### Query_Cookbook — minimum entries

| Recipe ID pattern | Required content |
|---|---|
| `QC-SEMANTIC-001` | Agent bootstrap: query `data_product_map` then `entity_metadata` |
| `QC-SEMANTIC-002` | ERD generation: query `table_relationship` to produce entity-relationship output |
| `QC-{MODULE}-001` | At least one representative query per deployed module |
| `QC-XMODULE-{NNN}` | At least one cross-module join example per deployed module pair |

The ERD recipe (`QC-SEMANTIC-002`) is particularly important: it allows any agent or team member to generate a current entity-relationship diagram from the living `table_relationship` data rather than relying on a static diagram that may have drifted. A standard template for this recipe is provided in the `Query_Cookbook` table definition in Section 8.4.

### 7.3 Deviation Documentation Convention

When a data product deviates from any AI-Native Data Product design standard — whether intentionally or due to constraints — the deviation must be captured in `Design_Decision` before the product is considered complete.

```sql
INSERT INTO Memory.Design_Decision (
    decision_id, decision_version, decision_title,
    decision_description, context, alternatives_considered,
    rationale, consequences,
    decision_status, decision_category,
    source_module, module_version,
    decided_by, decided_date,
    valid_from, valid_to, is_current
) VALUES (
    'DD-{MODULE}-NNN', 1,
    'Deviation from {standard name}: {brief description}',
    'Description of what was done differently',
    'Why the standard could not be followed as written',
    'Standard approach and other options considered',
    'Why this deviation was chosen over the standard approach',
    'Impact on agents, maintainability, and future modules',
    'ACCEPTED', 'ARCHITECTURE',
    '{MODULE}', '{version}',
    '{author}', CURRENT_DATE,
    CURRENT_DATE, DATE '9999-12-31', 1
);
```

This is not a compliance step — it is how the data product communicates design intent to the agents and team members who will work with it in the future.

### 7.4 Design Checklist

**Before implementation:**

- [ ] Agent types identified
- [ ] Session state structure defined
- [ ] Interaction logging pattern established
- [ ] Learning strategy tables defined
- [ ] User preference structure defined
- [ ] Privacy scope levels defined
- [ ] **NO content duplication** (ids only verified)
- [ ] Integration with Observability (learning from outcomes)
- [ ] Integration with Domain (entity references by id)
- [ ] Integration with Search (finding similar sessions/patterns)
- [ ] Retention policies documented
- [ ] Privacy policies documented
- [ ] `Module_Registry` INSERT generated for **every module considered** (DEPLOYED, PLANNED, or DEPRECATED)
- [ ] `Design_Decision` entries generated for all deferred/excluded modules
- [ ] Min. 3 `Design_Decision` INSERTs generated per deployed module
- [ ] All deviations from design standards captured in `Design_Decision`
- [ ] `Change_Log` initial release entry generated
- [ ] Min. 3 `Business_Glossary` terms captured
- [ ] Min. 1 `Query_Cookbook` recipe per deployed module
- [ ] ERD generation recipe (`QC-SEMANTIC-002`) captured
- [ ] Min. 1 cross-module `Query_Cookbook` recipe per deployed module pair

### 7.5 Quality Criteria

**A good Memory Module should:**

- ✅ Store agent state and learnings (not business data)
- ✅ Reference entities by id only (no content duplication)
- ✅ Enforce privacy scoping (USER, TEAM, ORG, AGENT)
- ✅ Enable session continuity
- ✅ Support cross-agent learning
- ✅ Learn from Observability outcomes
- ✅ Use JSON for flexible context storage
- ✅ Implement retention policies
- ✅ Have a `Module_Registry` row for every module considered during design
- ✅ Capture design decisions (min. 3 per deployed module) in `Design_Decision`
- ✅ Document all deviations from standards in `Design_Decision`
- ✅ Populate `Business_Glossary` with terms it introduces
- ✅ Include ERD generation recipe in `Query_Cookbook`

---

## 8. Documentation Sub-Module

### 8.1 Core Principle (Never Violate)

**Store design memory — never duplicate Semantic metadata.**

The Documentation Sub-Module is the **design memory** of this data product. Just as runtime memory (Sections 3–4) captures what agents experienced and learned during *operation*, documentation captures what architects decided and why during *design*. Both are forms of memory — temporal, append-oriented, and structured around capturing history.

| Store in Documentation | Keep in Semantic (not here) |
|--------------------------|-------------------------------|
| "We chose bi-temporal because of regulatory replay requirements" | Table/column names, PII flags, join paths |
| "Use LEFT JOIN for Customer → Orders because not all customers have orders" | `table_relationship` rows |
| "`income_bin` is computed as NTILE(5) OVER (ORDER BY income)" | `column_metadata` classification |

**Separation**: Semantic stores *what exists and how it connects*. Documentation stores *why it exists, how to use it, and what changed*.

### 8.2 Architecture: Per-Data-Product, Inside Memory Database

Documentation tables live in the **same database as the other Memory tables** (`{ProductName}_Memory`). This keeps the data product fully self-contained and independently deployable — there is no shared cross-product documentation database and no external bootstrap prerequisite.

```
{ProductName}_Memory  (one database per data product)
  ├── Runtime Memory tables
  │     agent_session, agent_interaction,
  │     learned_strategy, user_preference, discovered_pattern
  │
  └── Design Memory tables  (Documentation Sub-Module)
        Module_Registry, Design_Decision, Business_Glossary,
        Query_Cookbook, Implementation_Note, Change_Log
```

Documentation tables are created as part of the Memory module DDL deployment — no separate step required. The data product is complete and portable with no dependencies outside its own set of databases.

**Which documentation tables to include:**

| Table | Include When |
|-------|-------------|
| `Module_Registry` | Always — version backbone for point-in-time documentation |
| `Design_Decision` | Always — architectural rationale is always valuable |
| `Change_Log` | Always — version history drives documentation generation |
| `Business_Glossary` | Always — term definitions reduce ambiguity for agents |
| `Query_Cookbook` | Complex data products with multiple query patterns |
| `Implementation_Note` | Complex deployments with operational gotchas |

### 8.3 Two Workflows

#### Workflow 1 — Capture (Record Decisions During Module Design)

When any module is designed for this data product, it generates INSERT statements into the Memory database documentation tables. Output is written **inline with each module** as the last numbered script in that module's directory (e.g., `01-domain/05-documentation.sql`).

**Module registration protocol:**
```sql
INSERT INTO Memory.Module_Registry
(module_name, database_name, module_version, module_purpose,
 key_entities, dependencies, dependents, data_owner, technical_owner,
 version_date, is_current, valid_from, valid_to)
VALUES
('{MODULE_NAME}', '{ProductName}_{Module}', '1.0.0',
 '{purpose}', '{entity_list}',
 '{upstream_modules}', '{downstream_modules}',
 '{owner}', '{tech_contact}',
 CURRENT_DATE, 1, CURRENT_DATE, DATE '9999-12-31');
```

**Decision capture protocol:**
```sql
INSERT INTO Memory.Design_Decision
(decision_id, decision_version, decision_title, decision_description,
 context, alternatives_considered, rationale, consequences,
 decision_status, decision_category,
 source_module, module_version, affects_table,
 decided_by, decided_date, valid_from, valid_to, is_current)
VALUES
('DD-{MODULE}-{NNN}', 1, '{title}', '{description}',
 '{context}', '{alternatives}', '{rationale}', '{consequences}',
 'ACCEPTED', '{category}',
 '{MODULE_NAME}', '{VERSION}', '{table_list}',
 '{agent_or_team}', CURRENT_DATE, CURRENT_DATE, DATE '9999-12-31', 1);
```

**Decision ID convention:** `DD-{MODULE}-{NNN}` where MODULE is the short module name (DOMAIN, SEMANTIC, SEARCH, OBSERVABILITY, MEMORY, PREDICTION) and NNN is a zero-padded sequence within that module.

**Version chain — updating a decision:**
```sql
-- Step 1: Close the current version
UPDATE Memory.Design_Decision
SET valid_to = CURRENT_DATE,
    is_current = 0,
    updated_timestamp = CURRENT_TIMESTAMP(6)
WHERE decision_id = 'DD-MEMORY-001'
  AND is_current = 1;

-- Step 2: Insert new version
INSERT INTO Memory.Design_Decision
(decision_id, decision_version, decision_title, ...)
VALUES
('DD-MEMORY-001', 2, '{updated_title}', ...);
```

**Change log entry protocol:**
```sql
INSERT INTO Memory.Change_Log
(change_id, version_number, change_title, change_description,
 change_type, change_category, source_module,
 affects_table, migration_steps, rollback_steps,
 related_decision_id, deployed_date, deployed_by, deployment_status)
VALUES
('CL-{MODULE}-{NNN}', '{VERSION}', '{title}', '{description}',
 '{type}', '{category}', '{MODULE_NAME}',
 '{table_list}', '{migration_sql}', '{rollback_sql}',
 'DD-{MODULE}-{NNN}', CURRENT_DATE, '{deployer}', 'DEPLOYED');
```

#### Workflow 2 — Generate (Produce Markdown Documentation)

Generates human-readable Markdown documentation for one or all modules of this data product, at a specific version or date.

**Trigger phrases:**
- "Generate documentation for the Memory module at v1.5.0"
- "Generate documentation for all modules as of 2026-03-01"
- "Generate current documentation for all modules"

**Steps:**
1. Determine module scope: single module or all modules
2. Determine version anchor:
   - **By version**: look up `version_date` from `Module_Registry` WHERE `module_version = :version`
   - **By date**: use the date directly as `as_of_date`
   - **Current**: use `CURRENT_DATE` or `is_current = 1`
3. Query all documentation records valid at that point
4. Render Markdown
5. Write to `documentation/` directory at project root

**File naming convention:**

| Request Type | File Name |
|-------------|-----------|
| Single module by version | `documentation/{module}_v{version}_{YYYYMMDD}.md` |
| Single module by date | `documentation/{module}_asof_{YYYYMMDD}.md` |
| All modules current | `documentation/all_modules_current.md` |

**During design phase (pre-deployment):** Read INSERT statements from the SQL output files to extract decision records, then render them as Markdown. The SQL files are the source of truth during design.

### 8.4 Table Definitions

#### Module_Registry

Tracks all modules in this data product and their version history.

```sql
CREATE TABLE Memory.Module_Registry (
    module_registry_key  BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    module_name          VARCHAR(50) NOT NULL,
    database_name        VARCHAR(128) NOT NULL,
    deployment_status    VARCHAR(20) NOT NULL DEFAULT 'DEPLOYED',
    module_version       VARCHAR(20) NOT NULL,
    module_purpose       CLOB NOT NULL,
    module_scope         CLOB,
    key_entities         VARCHAR(500),
    dependencies         VARCHAR(500),
    dependents           VARCHAR(500),
    data_owner           VARCHAR(100),
    technical_owner      VARCHAR(100),
    refresh_frequency    VARCHAR(50),
    version_date         DATE NOT NULL,
    is_current           BYTEINT NOT NULL DEFAULT 1,
    valid_from           DATE NOT NULL,
    valid_to             DATE DEFAULT DATE '9999-12-31',
    created_timestamp    TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp    TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (module_registry_key);

COMMENT ON TABLE Memory.Module_Registry IS
'Version registry for all modules considered during data product design — includes deployed, planned, and deprecated modules. Backbone for point-in-time documentation generation and full scope visibility.';
COMMENT ON COLUMN Memory.Module_Registry.module_name IS
'Module name — DOMAIN, SEMANTIC, SEARCH, OBSERVABILITY, MEMORY, PREDICTION';
COMMENT ON COLUMN Memory.Module_Registry.deployment_status IS
'Lifecycle status of this module: DEPLOYED = active and queryable; PLANNED = in scope but not yet built; DEPRECATED = previously deployed, now retired. Agents should filter data_product_map (Semantic) for active modules; this column captures the full design-time picture.';
COMMENT ON COLUMN Memory.Module_Registry.module_version IS
'Semantic version string (1.0.0)';
COMMENT ON COLUMN Memory.Module_Registry.is_current IS
'1 = current version, 0 = historical — use to find latest version without date filter';
COMMENT ON COLUMN Memory.Module_Registry.valid_from IS
'Temporal validity start — when this version became active';
COMMENT ON COLUMN Memory.Module_Registry.valid_to IS
'Temporal validity end — 9999-12-31 for current version';
```

#### Design_Decision

Architecture Decision Records with version chain. Same `decision_id` can have multiple rows with incrementing `decision_version`.

```sql
CREATE TABLE Memory.Design_Decision (
    decision_key              BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    decision_id               VARCHAR(50) NOT NULL,
    decision_version          INTEGER NOT NULL DEFAULT 1,
    decision_title            VARCHAR(200) NOT NULL,
    decision_description      CLOB,
    context                   CLOB,
    alternatives_considered   CLOB,
    rationale                 CLOB,
    consequences              CLOB,
    decision_status           VARCHAR(20) NOT NULL,
    decision_category         VARCHAR(50) NOT NULL,
    source_module             VARCHAR(50) NOT NULL,
    module_version            VARCHAR(20),
    affects_table             VARCHAR(200),
    decided_by                VARCHAR(100),
    decided_date              DATE,
    superseded_by             VARCHAR(50),
    valid_from                DATE NOT NULL,
    valid_to                  DATE DEFAULT DATE '9999-12-31',
    is_current                BYTEINT NOT NULL DEFAULT 1,
    created_timestamp         TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp         TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (decision_key);

COMMENT ON TABLE Memory.Design_Decision IS
'Architecture Decision Records — captures why design choices were made, with version chain for tracking superseded decisions';
COMMENT ON COLUMN Memory.Design_Decision.decision_id IS
'Human-readable decision ID — format DD-{MODULE}-{NNN} (e.g., DD-MEMORY-001)';
COMMENT ON COLUMN Memory.Design_Decision.decision_status IS
'Decision lifecycle — PROPOSED, ACCEPTED, SUPERSEDED, DEPRECATED';
COMMENT ON COLUMN Memory.Design_Decision.decision_category IS
'Decision type — ARCHITECTURE, SCHEMA, NAMING, PERFORMANCE, SECURITY, INTEGRATION, OPERATIONAL';
COMMENT ON COLUMN Memory.Design_Decision.superseded_by IS
'decision_id of the replacement decision when status = SUPERSEDED';
COMMENT ON COLUMN Memory.Design_Decision.is_current IS
'1 = current version of this decision, 0 = historical — query with is_current = 1 for latest';
```

#### Business_Glossary

Domain term definitions linked to source module, versioned temporally.

```sql
CREATE TABLE Memory.Business_Glossary (
    glossary_key        BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    term                VARCHAR(200) NOT NULL,
    term_category       VARCHAR(50) NOT NULL,
    definition          CLOB NOT NULL,
    business_context    CLOB,
    synonyms            VARCHAR(500),
    related_terms       VARCHAR(500),
    related_table       VARCHAR(200),
    related_column      VARCHAR(200),
    source_module       VARCHAR(50) NOT NULL,
    module_version      VARCHAR(20),
    is_active           BYTEINT NOT NULL DEFAULT 1,
    valid_from          DATE NOT NULL,
    valid_to            DATE DEFAULT DATE '9999-12-31',
    created_timestamp   TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp   TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (glossary_key);

COMMENT ON TABLE Memory.Business_Glossary IS
'Domain term definitions — reduces ambiguity for agents and new team members, versioned per module';
COMMENT ON COLUMN Memory.Business_Glossary.term_category IS
'Term type — ENTITY, ATTRIBUTE, METRIC, BUSINESS_RULE, CLASSIFICATION, REFERENCE_CODE';
COMMENT ON COLUMN Memory.Business_Glossary.is_active IS
'1 = active term, 0 = retired or superseded';
```

#### Query_Cookbook

Tested, reusable query patterns.

```sql
CREATE TABLE Memory.Query_Cookbook (
    recipe_key              BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    recipe_id               VARCHAR(50) NOT NULL,
    recipe_title            VARCHAR(200) NOT NULL,
    recipe_description      CLOB NOT NULL,
    use_case                VARCHAR(200) NOT NULL,
    target_module           VARCHAR(50) NOT NULL,
    sql_template            CLOB NOT NULL,
    parameter_descriptions  CLOB,
    performance_notes       CLOB,
    complexity              VARCHAR(20) NOT NULL,
    source_module           VARCHAR(50) NOT NULL,
    module_version          VARCHAR(20),
    is_active               BYTEINT NOT NULL DEFAULT 1,
    valid_from              DATE NOT NULL,
    valid_to                DATE DEFAULT DATE '9999-12-31',
    created_timestamp       TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp       TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (recipe_key);

COMMENT ON TABLE Memory.Query_Cookbook IS
'Proven query patterns — agents use these as starting points rather than generating SQL from scratch';
COMMENT ON COLUMN Memory.Query_Cookbook.recipe_id IS
'Human-readable recipe ID — format QC-{MODULE}-{NNN} (e.g., QC-MEMORY-001)';
COMMENT ON COLUMN Memory.Query_Cookbook.target_module IS
'Module this recipe queries — DOMAIN, SEMANTIC, SEARCH, MEMORY, PREDICTION, OBSERVABILITY, CROSS';
COMMENT ON COLUMN Memory.Query_Cookbook.complexity IS
'Query complexity — SIMPLE, MODERATE, COMPLEX, ADVANCED';
COMMENT ON COLUMN Memory.Query_Cookbook.sql_template IS
'SQL with :parameter placeholders — agents substitute values at runtime';
```

**Standard ERD Recipe (`QC-SEMANTIC-002`)**

Every data product must include the following recipe. It allows any agent or team member to generate a current entity-relationship diagram from the `table_relationship` data in the Semantic module, replacing any static diagram that may have drifted out of sync.

```sql
INSERT INTO Memory.Query_Cookbook (
    recipe_id, recipe_title, recipe_description, use_case,
    target_module, sql_template, parameter_descriptions,
    performance_notes, complexity,
    source_module, module_version,
    is_active, valid_from, valid_to
) VALUES (
    'QC-SEMANTIC-002',
    'Generate entity-relationship diagram from table_relationship',
    'Queries the Semantic table_relationship table to produce a complete entity-relationship listing for this data product. Output can be formatted as Mermaid erDiagram syntax or as a plain relationship listing. Use to verify the current data model without relying on a static diagram.',
    'Data model documentation, onboarding, design review',
    'SEMANTIC',
    '-- Full ER listing: all active relationships across all modules
SELECT
    r.from_database,
    r.from_table,
    r.from_column,
    r.relationship_type,
    r.cardinality,
    r.to_database,
    r.to_table,
    r.to_column,
    r.join_type,
    r.is_mandatory,
    r.relationship_desc
FROM {ProductName}_Semantic.table_relationship r
WHERE r.is_active = 1
ORDER BY r.from_table, r.to_table;

-- Mermaid erDiagram format (agent renders as diagram):
-- For each row above, emit:
--   {from_table} {cardinality_symbol} {to_table} : "{relationship_desc}"
-- Cardinality symbols: ONE_TO_ONE = ||--||, ONE_TO_MANY = ||--o{,
--   MANY_TO_ONE = }o--||, MANY_TO_MANY = }o--o{',
    'Replace {ProductName} with the actual product name before executing.',
    'Lightweight query on a small metadata table — no performance concerns.',
    'SIMPLE',
    'SEMANTIC', :module_version,
    1, CURRENT_DATE, DATE '9999-12-31'
);
```

Operational knowledge, workarounds, known issues.

```sql
CREATE TABLE Memory.Implementation_Note (
    note_key            BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    note_id             VARCHAR(50) NOT NULL,
    note_title          VARCHAR(200) NOT NULL,
    note_content        CLOB NOT NULL,
    note_category       VARCHAR(50) NOT NULL,
    severity            VARCHAR(20),
    affects_table       VARCHAR(200),
    resolution_status   VARCHAR(20),
    resolution_notes    CLOB,
    source_module       VARCHAR(50) NOT NULL,
    module_version      VARCHAR(20),
    is_active           BYTEINT NOT NULL DEFAULT 1,
    valid_from          DATE NOT NULL,
    valid_to            DATE DEFAULT DATE '9999-12-31',
    created_timestamp   TIMESTAMP(6) WITH TIME ZONE,
    updated_timestamp   TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (note_key);

COMMENT ON TABLE Memory.Implementation_Note IS
'Operational knowledge — workarounds, known issues, deployment tips, and gotchas discovered during implementation';
COMMENT ON COLUMN Memory.Implementation_Note.note_id IS
'Human-readable note ID — format IN-{MODULE}-{NNN} (e.g., IN-MEMORY-001)';
COMMENT ON COLUMN Memory.Implementation_Note.note_category IS
'Note type — DEPLOYMENT, WORKAROUND, KNOWN_ISSUE, PERFORMANCE_TIP, OPERATIONAL, SECURITY';
COMMENT ON COLUMN Memory.Implementation_Note.severity IS
'Issue severity — LOW, MEDIUM, HIGH, CRITICAL (NULL for non-issue notes)';
COMMENT ON COLUMN Memory.Implementation_Note.resolution_status IS
'Resolution state — OPEN, IN_PROGRESS, RESOLVED, WONT_FIX';
```

#### Change_Log

Versioned history of changes per module. Each row is a point-in-time event.

```sql
CREATE TABLE Memory.Change_Log (
    change_key          BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    change_id           VARCHAR(50) NOT NULL,
    version_number      VARCHAR(20) NOT NULL,
    change_title        VARCHAR(200) NOT NULL,
    change_description  CLOB NOT NULL,
    change_type         VARCHAR(30) NOT NULL,
    change_category     VARCHAR(50) NOT NULL,
    source_module       VARCHAR(50) NOT NULL,
    affects_table       VARCHAR(200),
    migration_steps     CLOB,
    rollback_steps      CLOB,
    related_decision_id VARCHAR(50),
    deployed_date       DATE,
    deployed_by         VARCHAR(100),
    deployment_status   VARCHAR(20) NOT NULL,
    created_timestamp   TIMESTAMP(6) WITH TIME ZONE
)
PRIMARY INDEX (change_key);

COMMENT ON TABLE Memory.Change_Log IS
'Versioned change history — each row is a point-in-time event; ordered by version_number to reconstruct deployment history';
COMMENT ON COLUMN Memory.Change_Log.change_id IS
'Human-readable change ID — format CL-{MODULE}-{NNN} (e.g., CL-MEMORY-001)';
COMMENT ON COLUMN Memory.Change_Log.change_type IS
'Change type — INITIAL_RELEASE, SCHEMA_CHANGE, FEATURE_ADDITION, BUG_FIX, PERFORMANCE, DEPRECATION';
COMMENT ON COLUMN Memory.Change_Log.change_category IS
'Impact category — BREAKING, NON_BREAKING, ADDITIVE, DEPRECATION';
COMMENT ON COLUMN Memory.Change_Log.related_decision_id IS
'Links to Design_Decision.decision_id — traceability from change to rationale';
COMMENT ON COLUMN Memory.Change_Log.deployment_status IS
'Deployment state — PLANNED, DEPLOYED, ROLLED_BACK';
```

### 8.5 Temporal Query Patterns

```sql
-- Current decisions for a module
SELECT * FROM Memory.Design_Decision
WHERE source_module = :module_name
  AND is_current = 1;

-- All decisions for a module as of a specific date
SELECT * FROM Memory.Design_Decision
WHERE source_module = :module_name
  AND valid_from <= :as_of_date
  AND valid_to > :as_of_date;

-- All decisions for a module as of a specific version
SELECT dd.*
FROM Memory.Design_Decision dd
WHERE dd.source_module = :module_name
  AND dd.valid_from <= (
      SELECT mr.version_date
      FROM Memory.Module_Registry mr
      WHERE mr.module_name = :module_name
        AND mr.module_version = :version
  )
  AND dd.valid_to > (
      SELECT mr.version_date
      FROM Memory.Module_Registry mr
      WHERE mr.module_name = :module_name
        AND mr.module_version = :version
  );

-- Change log up to a version for a module
SELECT * FROM Memory.Change_Log
WHERE source_module = :module_name
  AND version_number <= :version
ORDER BY version_number, created_timestamp;
```

Same temporal pattern applies to `Business_Glossary`, `Query_Cookbook`, and `Implementation_Note`.

### 8.6 Standard Views

| View | Purpose |
|------|---------|
| `v_Current_Decisions` | All current (is_current=1) non-superseded decisions |
| `v_Module_Registry_Current` | Current version of each module |
| `v_Glossary_Active` | Active glossary terms (is_active=1) |
| `v_Cookbook_Active` | Active recipes with complexity ranking |
| `v_Issues_Open` | Open issues ordered by severity |
| `v_Change_History` | Full change log ordered by version desc |
| `v_Documentation_Search` | Unified text search across all documentation tables |

### 8.7 Cross-Module Capture Protocol

When any module is designed for this data product, it generates INSERT statements into `Memory` documentation tables.

**Each module is responsible for:**

1. Registering itself in `Module_Registry`
2. Generating `Design_Decision` INSERTs for every significant design choice (min. 3)
3. Generating a `Change_Log` entry for the initial release (version 1.0.0)
4. Generating `Business_Glossary` entries for domain terms it introduces (min. 3)
5. Generating `Query_Cookbook` entries for key query patterns it supports (min. 1)

**Decision categories by module type:**

| Module | Typical Decision Categories |
|--------|-----------------------------|
| Domain | ARCHITECTURE (source mapping), SCHEMA (entity structure) |
| Semantic | INTEGRATION (relationship mapping), NAMING (metadata standards) |
| Search | ARCHITECTURE (vector strategy), PERFORMANCE (index choice) |
| Observability | OPERATIONAL (monitoring thresholds), INTEGRATION (lineage scope) |
| Memory | ARCHITECTURE (session strategy), SECURITY (privacy scoping) |
| Prediction | ARCHITECTURE (feature store strategy), SCHEMA (feature table design) |

**ID conventions:**

| Record Type | Format | Example |
|-------------|--------|---------|
| Design Decision | `DD-{MODULE}-{NNN}` | `DD-MEMORY-001` |
| Change Log | `CL-{MODULE}-{NNN}` | `CL-MEMORY-001` |
| Query Cookbook | `QC-{MODULE}-{NNN}` | `QC-MEMORY-001` |
| Implementation Note | `IN-{MODULE}-{NNN}` | `IN-MEMORY-001` |

**Temporal field standards** for all INSERTs:
- `valid_from = CURRENT_DATE`
- `valid_to = DATE '9999-12-31'`
- `is_current = 1` (for Design_Decision, Module_Registry)
- `is_active = 1` (for Business_Glossary, Query_Cookbook)
- `decision_status = 'ACCEPTED'` (for new decisions)

---


### Core Principles

```
✅ Store agent metadata (NOT business data)
✅ Reference entities at TABLE level (VARCHAR: 'database.table, database.table')
✅ Don't store instance keys/Ids from millions of query results
✅ "Big Questions, Small Answers" - Store SQL/patterns/outcomes, not result data
✅ Simple LIKE queries on referenced_tables VARCHAR column
✅ Use JSON for complex/flexible structures (agent processes externally)
✅ Enforce privacy scoping (USER, TEAM, ORG, AGENT)
✅ Temporal tracking with TIMESTAMP WITH TIME ZONE
```

### Entity Reference Pattern (TABLE LEVEL - TESTED ✅)

```
// Store in referenced_tables VARCHAR column (comma-separated)
'Domain.Party_H, Prediction.customer_features'
'Domain.Party_H'
'Domain.Product_H, Search.product_embedding'

// Query for interactions involving Party table (TESTED ✅):
SELECT * FROM Memory.agent_interaction
WHERE referenced_tables LIKE '%Domain.Party_H%'
  AND interaction_type = 'DECISION';

// Query for interactions involving any Domain table:
SELECT * FROM Memory.agent_interaction
WHERE referenced_tables LIKE '%Domain.%';

// Query for specific table (any database):
SELECT * FROM Memory.agent_interaction
WHERE referenced_tables LIKE '%Party_H%';

// Query for multiple tables:
SELECT * FROM Memory.agent_interaction
WHERE referenced_tables LIKE '%Party_H%'
  AND referenced_tables LIKE '%customer_features%';
```

**Format**: `database_name.table_name, database_name.table_name, ...`
**Benefits**: Simple LIKE queries, no JSON parsing, works with variable number of tables

### JSON vs VARCHAR Column Usage

**Use VARCHAR (comma-separated) for**:
- ✅ Table/entity references (`referenced_tables`, `involved_tables`)
- ✅ Simple lists that need SQL filtering
- ✅ When LIKE search is sufficient

**Use JSON for**:
- ✅ Complex nested structures (`session_context_json`, `pattern_definition_json`)
- ✅ Flexible/varying schema (`strategy_metadata_json`, `preference_value_json`)
- ✅ Documents agent retrieves and processes externally

**Querying**:
- VARCHAR: Direct LIKE in SQL (`WHERE referenced_tables LIKE '%Party_H%'`)
- JSON: Retrieve document, parse in application (Python, Java, etc.)

### "Big Questions, Small Answers" Examples

```
Agent Query: "Find high-value customers" (scans 50M Party records)

Memory Stores (SMALL):
✅ SQL: "SELECT ... FROM Party_H WHERE credit_score > 0.8"
✅ Tables: Domain.Party_H, Prediction.customer_features
✅ Result count: 125,000 customers found
✅ Execution time: 2.3 seconds
✅ Outcome: SUCCESS
Total: One interaction row (~2KB)

Memory Does NOT Store (WOULD BE BIG):
❌ 125,000 individual party_id values
❌ Customer names, details, attributes
❌ Query result dataset
Would be: 125,000+ rows (unnecessary)
```

### Privacy Scoping (Required)

```
Every Memory record must include:
- scope_level: 'USER' | 'TEAM' | 'ORGANIZATION' | 'AGENT'
- scope_identifier: user_key | team_key | org_key | agent_key

Query patterns:
- User memory: WHERE scope_level = 'USER' AND scope_identifier = {user_key}
- Team memory: WHERE scope_level = 'TEAM' AND scope_identifier = {team_key}
- Org memory:  WHERE scope_level = 'ORGANIZATION'
```

### Standard Views

```
✅ v_interactions_by_entity  -- Interactions grouped by table referenced
✅ v_active_sessions         -- Currently active agent sessions
✅ v_learned_strategies_org  -- Organization-wide validated strategies
```

### Integration Patterns

```
Memory → Observability:  Learn from outcomes (what worked)
Memory + Search:         Find similar sessions/patterns
Memory + Semantic:       Apply business rules learned
Memory + Prediction:     Inform feature selection
Memory references Domain: By table name only (not instance keys/IDs)
```

### What Memory Stores vs Doesn't Store

```
STORES (Metadata):
✅ Agent executed this SQL query
✅ Queried these tables: Party_H, Transaction_H
✅ Returned 5M results
✅ Execution time: 15 seconds
✅ User was satisfied with outcome
✅ Pattern learned: "Filter on is_current first improves performance 3x"

DOES NOT STORE (Instance Data):
❌ 5M individual record keys/IDs
❌ Customer names from those 5M records
❌ Transaction details
❌ Query result dataset
❌ Individual row-level information
```

### Retention Patterns

```
Session State:          90 days (purge completed sessions)
Interaction Logs:       1 year (audit trail)
Learned Strategies:     2 years (validated patterns longer)
User Preferences:       Active user lifecycle
Discovered Patterns:    Indefinite if validated
```

---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.7 | 2026-04-15 | Added `deployment_status VARCHAR(20) NOT NULL DEFAULT 'DEPLOYED'` to `Module_Registry` DDL, enabling DEPLOYED/PLANNED/DEPRECATED lifecycle tracking for all modules considered during design. Expanded Section 7 with Minimum Seed Data Requirements (7.2), Deviation Documentation Convention (7.3), updated Design Checklist (7.4), and Quality Criteria (7.5). Key additions: Module_Registry row required for every module considered; Design_Decision entries required for deferred/excluded modules and all standards deviations; ERD generation recipe (QC-SEMANTIC-002) mandatory; cross-module cookbook recipes required per deployed module pair. Added standard ERD recipe INSERT template to Section 8.4. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.6 | 2026-03-20 | Fixed = 'Y' filter value in Search integration example (Section 6.3) to = 1. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.5 | 2026-03-20 | Revised Documentation Sub-Module (Section 8) to align with data product self-containment principle. Removed shared dp_documentation cross-product database pattern. Documentation tables now reside in the same {ProductName}_Memory database as runtime memory tables, framed as "design memory" alongside "runtime memory". Removed data_product column from all 6 table DDL definitions. Removed cross-product (data_product = 'ALL') pattern. Simplified temporal queries. Collapsed 3 workflows to 2 (Bootstrap removed — documentation tables created as part of Memory DDL). Updated Section 6.5 example INSERT to use Memory.Design_Decision. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.4 | 2026-03-20 | Added Documentation Sub-Module (Section 8) — merged standalone documentation skill into Memory standard. Covers shared dp_documentation database, 6 table definitions (Module_Registry, Design_Decision, Business_Glossary, Query_Cookbook, Implementation_Note, Change_Log), 3 workflows (Bootstrap, Capture, Generate), temporal query patterns, standard views, and cross-module capture protocol. Updated Sections 1.1, 1.2, 2.1, 6, 7 to reference documentation capabilities. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.3 | 2026-03-18 | Applied surrogate key naming convention to internal management tables: renamed {table}_key → {table}_id for GENERATED ALWAYS AS IDENTITY columns; swapped session_key (INTEGER surrogate) ↔ session_id (VARCHAR natural key) in agent_session | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.2 | 2026-03-17 | Updated naming convention: {entity}_id = Surrogate Key, {entity}_key = Natural Business Key; updated all party_key/entity_key references in "do not store" examples to party_id, aligned with Domain Module Design Standard v2.1 | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.1 | 2025-02-27 | Changed is_active & is_validated to be consistent and align with boolean standards from Domain | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.0 | 2025-02-09 | Initial Memory Module Design Standard | Nathan Green, Worldwide Data Architecture Team, Teradata |

---

**End of Memory Module Design Standard**
