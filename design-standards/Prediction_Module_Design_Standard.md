# Prediction Module Design Standard
## AI-Native Data Product Architecture - Version 1.6

---

## Document Control

| Attribute | Value |
|-----------|-------|
| **Version** | 1.6 |
| **Status** | STANDARD |
| **Last Updated** | 2026-03-20 |
| **Owner** | Nathan Green, Worldwide Data Architecture Team, Teradata |
| **Scope** | Prediction Module (Feature Store) |
| **Type** | Design Standard (Structural Requirements) |
| **Companion** | Advocated Data Management Standards (Implementation Guidance) |

---

## Table of Contents

1. [AI-Native Prediction Module Overview](#1-ai-native-prediction-module-overview)
2. [Module Scope and Boundaries](#2-module-scope-and-boundaries)
3. [Feature Store Structure](#3-feature-store-structure)
4. [Point-in-Time Correctness](#4-point-in-time-correctness)
5. [Integration with Other Modules](#5-integration-with-other-modules)
6. [Agent Discovery and Querying](#6-agent-discovery-and-querying)
7. [Designer Responsibilities](#7-designer-responsibilities)

---

## 1. AI-Native Prediction Module Overview

### 1.1 What Makes Prediction Module AI-Native?

The Prediction Module (Feature Store) stores **engineered features** for ML model training and serving with **point-in-time correctness** and **feature discoverability**.

**Key Principle**: Feature stores contain **ENGINEERED features** (transformed, normalized, aggregated), not raw domain data. If a feature is just a copy of a domain column with no transformation, it should NOT be duplicated in the feature store—use views to join instead.

| AI-Native Characteristic | Purpose |
|-------------------------|---------|
| **Feature Engineering** | Features are transformed, normalized, aggregated (not raw copies) |
| **Normalized Scaling** | Features scaled to common range (typically 0-1) for equal weighting |
| **Point-in-Time Correctness** | Features reconstructed exactly as they existed historically |
| **Feature Discoverability** | Agents can discover available features without human instruction |
| **Temporal Alignment** | Features aligned with Domain entity temporal tracking |
| **Training/Serving Consistency** | Same features used for training and inference |

### 1.2 Feature Engineering Requirement

**What belongs in Feature Store:**
- ✅ **Engineered features**: Normalized, transformed, aggregated values
  - Example: `income_normalized` = (income - min) / (max - min) → 0-1 range
  - Example: `recency_score` = days_since_last_purchase normalized to 0-1
  - Example: `transaction_velocity` = count of transactions in 30 days / max observed
  - Example: `product_affinity_score` = collaborative filtering score 0-1

**What does NOT belong in Feature Store:**
- ❌ **Raw domain values**: Direct copies of domain columns
  - Example: Don't duplicate `legal_name` from Party_H
  - Example: Don't duplicate `credit_limit_amt` as-is
  - Example: Don't duplicate `birth_date` 

**Exception**: Selective duplication acceptable for **low-latency scoring** when:
- Real-time inference requires sub-second response
- Complex joins to Domain would exceed latency budget
- Document rationale for each duplicated value

### 1.3 Normalization and Scaling

**Standard Practice**: Features normalized to common scale (typically 0-1) so all features are weighted equally during model training.

**Why this matters**:
- Features with different scales (e.g., age: 18-90, income: $0-$1M) would dominate model training
- Normalization ensures equal consideration of all features
- Common scales: [0,1], [-1,1], z-score standardization

**Example**:
```sql
-- Raw domain value: credit_limit_amt ranges from $0 to $1,000,000
-- Engineered feature: credit_limit_normalized = credit_limit_amt / 1000000
-- Result: Values between 0.0 and 1.0
```

### 1.4 Open Standards Alignment

**Designers should align with established feature store patterns:**

- **Feast** (Open-source feature store): https://feast.dev/
  - Feature definitions, feature services, materialization patterns
- **Tecton** (Commercial feature store patterns): Feature engineering best practices
- **MLOps Feature Store Patterns**: Versioning, lineage, monitoring

**Key concepts to adopt**:
- Feature definitions separate from feature values
- Point-in-time correctness
- Online vs offline feature stores
- Feature serving APIs
- Feature monitoring and drift detection

---

## 2. Module Scope and Boundaries

### 2.1 What Belongs in Prediction Module

**IN SCOPE:**

1. **Feature Values**
   - Actual computed feature values for entities
   - Historical feature values (for point-in-time training)
   - Feature timestamps (when computed/observed)

2. **Feature Groups**
   - Collections of related features
   - Feature group metadata

3. **Model Predictions**
   - Model outputs (scores, classifications, predictions)
   - Prediction timestamps and versions
   - Confidence scores

4. **Training Datasets** (Optional)
   - Labeled examples
   - Training/validation/test splits
   - Point-in-time feature snapshots

**OUT OF SCOPE (goes to other modules):**

- ❌ **Feature definitions** → Semantic Module (feature metadata, computation logic)
- ❌ **Source entity data** → Domain Module (customers, products, transactions)
- ❌ **Model monitoring** → Observability Module (drift detection, performance metrics)
- ❌ **Vector embeddings** → Search Module (semantic representations)

### 2.2 Critical Principle: Point-in-Time Correctness

**Requirement**: Features must be reconstructable as they existed at any historical moment.

**Why this matters**:
- **Training**: Use features as they existed at training time (no data leakage)
- **Backtesting**: Evaluate model performance with historical features
- **Explainability**: "Why did model predict X?" requires historical feature state
- **Reproducibility**: Same inputs produce same outputs

**Implementation**: Features have temporal tracking aligned with Domain module patterns.

---

## 3. Feature Store Structure

### 3.1 Feature Value Storage Pattern

**Two main patterns for feature storage:**

#### Pattern A: Wide Format (Feature Group Table)

**Use when**: Features frequently accessed together as a group

```sql
CREATE TABLE Prediction.customer_behavioral_features (
    feature_group_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- Entity reference (references Domain)
    entity_id BIGINT NOT NULL,
    entity_type VARCHAR(50) NOT NULL,  -- 'PARTY'
    
    -- ENGINEERED feature values (normalized to 0-1 range)
    recency_score DECIMAL(5,4),              -- Days since last transaction, normalized
    frequency_score DECIMAL(5,4),            -- Transaction count, normalized
    monetary_score DECIMAL(5,4),             -- Total spend, normalized
    avg_transaction_value_norm DECIMAL(5,4), -- Average transaction size, normalized
    channel_diversity_score DECIMAL(5,4),    -- Number of channels used, normalized
    product_category_breadth DECIMAL(5,4),   -- Category diversity, normalized
    
    -- NOT INCLUDED: Raw domain values (use views to join)
    -- Don't duplicate: legal_name, birth_date, email, phone, etc. from Domain.Party_H
    -- Don't duplicate: raw transaction_count, raw total_spend (unless needed for low-latency)
    
    -- Temporal tracking (point-in-time)
    observation_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_from_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_to_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL 
        DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
    is_current BYTEINT NOT NULL DEFAULT 1,
    
    -- Feature metadata
    feature_group_name VARCHAR(128) NOT NULL DEFAULT 'customer_behavioral',
    feature_group_version VARCHAR(20),
    computation_dts TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    
    -- Lineage
    source_system VARCHAR(50),
    created_by VARCHAR(100)
)
PRIMARY INDEX (feature_group_id);

COMMENT ON TABLE Prediction.customer_behavioral_features IS 
'Customer behavioral features - ENGINEERED and normalized to 0-1 range for model training';

COMMENT ON COLUMN Prediction.customer_behavioral_features.feature_group_id IS 
'Surrogate key for feature group record - unique identifier for this feature snapshot';

COMMENT ON COLUMN Prediction.customer_behavioral_features.entity_id IS 
'Foreign key to Domain entity (party_id) - links features to customer entity';

COMMENT ON COLUMN Prediction.customer_behavioral_features.entity_type IS 
'Entity type indicator - always PARTY for customer features - enables polymorphic references';

COMMENT ON COLUMN Prediction.customer_behavioral_features.recency_score IS 
'ENGINEERED: Days since last transaction normalized to 0-1 range - recent activity = higher score, formula: 1.0 - (days/365)';

COMMENT ON COLUMN Prediction.customer_behavioral_features.frequency_score IS 
'ENGINEERED: Transaction count normalized to 0-1 range - formula: count / max_count across all customers';

COMMENT ON COLUMN Prediction.customer_behavioral_features.monetary_score IS 
'ENGINEERED: Total spend normalized to 0-1 range - formula: total_spend / max_spend across all customers';

COMMENT ON COLUMN Prediction.customer_behavioral_features.avg_transaction_value_norm IS 
'ENGINEERED: Average transaction size normalized to 0-1 range - measures typical purchase value';

COMMENT ON COLUMN Prediction.customer_behavioral_features.channel_diversity_score IS 
'ENGINEERED: Number of channels used normalized to 0-1 range - measures omnichannel engagement';

COMMENT ON COLUMN Prediction.customer_behavioral_features.product_category_breadth IS 
'ENGINEERED: Product category diversity normalized to 0-1 range - measures cross-category purchasing';

COMMENT ON COLUMN Prediction.customer_behavioral_features.observation_dts IS 
'When features were observed/computed - critical for point-in-time correctness in ML training';

COMMENT ON COLUMN Prediction.customer_behavioral_features.valid_from_dts IS 
'When this feature version became valid - supports temporal feature tracking';

COMMENT ON COLUMN Prediction.customer_behavioral_features.valid_to_dts IS 
'When this feature version was superseded - default 9999-12-31 for current version';

COMMENT ON COLUMN Prediction.customer_behavioral_features.is_current IS 
'Current version indicator - 1 = current feature values, 0 = historical feature values';

COMMENT ON COLUMN Prediction.customer_behavioral_features.feature_group_name IS 
'Feature group identifier - groups related features together for management';

COMMENT ON COLUMN Prediction.customer_behavioral_features.feature_group_version IS 
'Version of feature engineering logic used - enables feature versioning and A/B testing';

COMMENT ON COLUMN Prediction.customer_behavioral_features.computation_dts IS 
'Timestamp when features were computed and inserted';

COMMENT ON COLUMN Prediction.customer_behavioral_features.source_system IS 
'System or process that computed features - ETL job, ML pipeline, etc.';

COMMENT ON COLUMN Prediction.customer_behavioral_features.created_by IS 
'User or process that created this feature record';
```

**Engineering Examples**:
```sql
-- Recency: Normalized days since last transaction
recency_score = 1.0 - (days_since_last_transaction / 365.0)  -- Recent = higher score

-- Frequency: Normalized transaction count
frequency_score = transaction_count_30d / MAX(transaction_count_30d across all customers)

-- Monetary: Normalized total spend  
monetary_score = total_spend_30d / MAX(total_spend_30d across all customers)
```

#### Pattern B: Tall Format (Feature-Value Table)

**Use when**: Features accessed individually, sparse features, or highly dynamic feature sets

```sql
CREATE TABLE Prediction.feature_value (
    feature_value_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- Entity reference
    entity_id BIGINT NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    
    -- Feature identification
    feature_name VARCHAR(128) NOT NULL,
    feature_group VARCHAR(100),
    
    -- Feature value (flexible storage)
    value_numeric DECIMAL(18,4),
    value_text VARCHAR(500),
    value_json JSON,
    value_type VARCHAR(20),  -- 'NUMERIC', 'TEXT', 'JSON', 'BOOLEAN'
    
    -- Temporal tracking
    observation_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_from_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_to_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL 
        DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
    is_current BYTEINT NOT NULL DEFAULT 1,
    
    -- Metadata
    feature_version VARCHAR(20),
    computation_dts TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    source_system VARCHAR(50),
    created_by VARCHAR(100)
)
PRIMARY INDEX (feature_value_id);

COMMENT ON TABLE Prediction.feature_value IS 
'Feature values - tall format with one feature per row, flexible data types for sparse or dynamic feature sets';

COMMENT ON COLUMN Prediction.feature_value.feature_value_id IS 
'Surrogate key for feature value record';

COMMENT ON COLUMN Prediction.feature_value.entity_id IS 
'Foreign key to Domain entity - links feature to specific entity instance';

COMMENT ON COLUMN Prediction.feature_value.entity_type IS 
'Entity type indicator - PARTY, PRODUCT, etc. - enables polymorphic entity references';

COMMENT ON COLUMN Prediction.feature_value.feature_name IS 
'Name of the feature - e.g., credit_score_normalized, recency_score';

COMMENT ON COLUMN Prediction.feature_value.feature_group IS 
'Feature group name for organizing related features - e.g., behavioral, demographic';

COMMENT ON COLUMN Prediction.feature_value.value_numeric IS 
'Numeric feature value - used for numeric features, normalized to 0-1 range when appropriate';

COMMENT ON COLUMN Prediction.feature_value.value_text IS 
'Text feature value - used for categorical or text-based features';

COMMENT ON COLUMN Prediction.feature_value.value_json IS 
'JSON feature value - used for complex multi-dimensional features';

COMMENT ON COLUMN Prediction.feature_value.value_type IS 
'Data type indicator - NUMERIC, TEXT, JSON, BOOLEAN - identifies which value column contains data';

COMMENT ON COLUMN Prediction.feature_value.observation_dts IS 
'When feature was observed/computed - critical for point-in-time ML training without data leakage';

COMMENT ON COLUMN Prediction.feature_value.valid_from_dts IS 
'When this feature version became valid';

COMMENT ON COLUMN Prediction.feature_value.valid_to_dts IS 
'When this feature version was superseded - default 9999-12-31 for current';

COMMENT ON COLUMN Prediction.feature_value.is_current IS 
'Current version indicator - 1 = current, 0 = historical';

COMMENT ON COLUMN Prediction.feature_value.feature_version IS 
'Version of feature computation logic - tracks feature engineering changes';

COMMENT ON COLUMN Prediction.feature_value.computation_dts IS 
'Timestamp when feature was computed and stored';

COMMENT ON COLUMN Prediction.feature_value.source_system IS 
'System that computed the feature - ML pipeline, ETL process, etc.';

COMMENT ON COLUMN Prediction.feature_value.created_by IS 
'User or process that created this feature value';
```

### 3.2 Pattern Selection Guidance

| Use Wide Format When: | Use Tall Format When: |
|----------------------|----------------------|
| Features always accessed together | Features accessed individually |
| Fixed set of features | Dynamic/evolving feature set |
| All features same data type | Mixed data types |
| Dense features (few NULLs) | Sparse features (many NULLs) |
| Performance critical (fewer joins) | Flexibility critical |

**Flexibility**: Designer chooses pattern based on use case. Can mix both patterns in same data product.

### 3.3 Model Prediction Storage

```sql
CREATE TABLE Prediction.model_prediction (
    prediction_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- Entity reference
    entity_id BIGINT NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    
    -- Model identification
    model_key VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    
    -- Prediction output
    prediction_value DECIMAL(10,6),  -- Score, probability, or numeric prediction
    prediction_class VARCHAR(100),    -- Classification result
    prediction_json JSON,             -- Complex predictions
    confidence_score DECIMAL(5,4),    -- Model confidence (0.0-1.0)
    
    -- Temporal tracking
    prediction_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    feature_observation_dts TIMESTAMP(6) WITH TIME ZONE,  -- When features were observed
    valid_from_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_to_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL 
        DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
    is_current BYTEINT NOT NULL DEFAULT 1,
    
    -- Metadata
    created_by VARCHAR(100),
    created_at TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (prediction_id);

COMMENT ON TABLE Prediction.model_prediction IS 
'Model prediction outputs with temporal tracking and confidence scores - stores ML model inference results';

COMMENT ON COLUMN Prediction.model_prediction.prediction_id IS 
'Surrogate key for prediction record';

COMMENT ON COLUMN Prediction.model_prediction.entity_id IS 
'Foreign key to Domain entity - identifies which entity this prediction is about';

COMMENT ON COLUMN Prediction.model_prediction.entity_type IS 
'Entity type - PARTY, PRODUCT, TRANSACTION, etc. - enables polymorphic entity references';

COMMENT ON COLUMN Prediction.model_prediction.model_key IS 
'Model identifier name - unique name for the ML model that generated this prediction';

COMMENT ON COLUMN Prediction.model_prediction.model_version IS 
'Model version - tracks which version of model was used for this prediction';

COMMENT ON COLUMN Prediction.model_prediction.prediction_value IS 
'Numeric prediction output - probability score, risk score, or continuous value prediction';

COMMENT ON COLUMN Prediction.model_prediction.prediction_class IS 
'Classification prediction output - predicted class or category label';

COMMENT ON COLUMN Prediction.model_prediction.prediction_json IS 
'Complex prediction output - JSON for multi-class probabilities or structured predictions';

COMMENT ON COLUMN Prediction.model_prediction.confidence_score IS 
'Model confidence in prediction - 0.0 to 1.0 range, higher = more confident';

COMMENT ON COLUMN Prediction.model_prediction.prediction_dts IS 
'Timestamp when prediction was generated';

COMMENT ON COLUMN Prediction.model_prediction.feature_observation_dts IS 
'When input features were observed - links prediction to feature timestamp for reproducibility';

COMMENT ON COLUMN Prediction.model_prediction.valid_from_dts IS 
'When this prediction version became valid';

COMMENT ON COLUMN Prediction.model_prediction.valid_to_dts IS 
'When this prediction was superseded by newer prediction - default 9999-12-31 for current';

COMMENT ON COLUMN Prediction.model_prediction.is_current IS 
'Current prediction indicator - 1 = latest prediction, 0 = historical prediction';

COMMENT ON COLUMN Prediction.model_prediction.created_by IS 
'Process or system that generated prediction - model serving API, batch scoring job, etc.';

COMMENT ON COLUMN Prediction.model_prediction.created_at IS 
'Timestamp when prediction record was inserted into database';
```

---

## 4. Point-in-Time Correctness

### 4.1 Why Point-in-Time Matters

**Problem**: Using current features for historical training causes data leakage

**Example**:
```
Training model to predict churn in March 2024
❌ WRONG: Use customer's current income (as of Feb 2025) 
✅ CORRECT: Use customer's income as it was in March 2024
```

### 4.2 Temporal Alignment with Domain

**Requirement**: Feature `observation_dts` must align with Domain entity temporal tracking

```sql
-- Get features as they existed on a specific date (point-in-time)
SELECT 
    f.entity_id,
    f.feature_name,
    f.value_numeric,
    f.observation_dts
FROM Prediction.feature_value f
WHERE f.entity_id = 1001
  AND f.entity_type = 'PARTY'
  AND f.observation_dts <= TIMESTAMP '2024-03-01 00:00:00+00:00'
  AND f.valid_from_dts <= TIMESTAMP '2024-03-01 00:00:00+00:00'
  AND f.valid_to_dts > TIMESTAMP '2024-03-01 00:00:00+00:00';

-- Join with Domain entity state at same point in time
SELECT 
    p.party_id,
    p.legal_name,
    f.feature_name,
    f.value_numeric
FROM Domain.Party_H p
INNER JOIN Prediction.feature_value f
    ON f.entity_id = p.party_id
   AND f.entity_type = 'PARTY'
WHERE p.party_key = 'CUST-123'
  AND TIMESTAMP '2024-03-01 00:00:00+00:00' >= p.valid_from_dts
  AND TIMESTAMP '2024-03-01 00:00:00+00:00' < p.valid_to_dts
  AND f.observation_dts <= TIMESTAMP '2024-03-01 00:00:00+00:00'
  AND f.valid_from_dts <= TIMESTAMP '2024-03-01 00:00:00+00:00'
  AND f.valid_to_dts > TIMESTAMP '2024-03-01 00:00:00+00:00';
```

### 4.3 Standard Temporal Columns for Features

**Required temporal columns:**

```sql
observation_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL
    COMMENT 'When feature was observed/computed'

valid_from_dts       TIMESTAMP(6) WITH TIME ZONE NOT NULL
    COMMENT 'When this feature version became valid'

valid_to_dts         TIMESTAMP(6) WITH TIME ZONE NOT NULL
    COMMENT 'When this feature version was superseded'

is_current           BYTEINT NOT NULL DEFAULT 1
    COMMENT 'Current version flag for query optimization'
```

**Pattern**: Similar to Domain module temporal tracking for consistency

---

## 5. Integration with Other Modules

### 5.1 Integration with Domain (Source Data)

**Pattern**: Features reference Domain entities using standard FK pattern

```sql
-- Feature references Domain entity
CREATE TABLE Prediction.customer_features (
    feature_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    
    -- Reference to Domain entity (standard pattern)
    entity_id BIGINT NOT NULL,      -- FK to Domain.Party_H.party_id
    entity_type VARCHAR(50) NOT NULL, -- 'PARTY'
    
    -- Or specific FK (type-safe)
    party_id BIGINT NOT NULL,  -- FK to Domain.Party_H.party_id
    
    -- Feature values...
    -- Temporal columns...
)
PRIMARY INDEX (feature_id);

-- Query: Get customer with features
SELECT 
    p.party_id,
    p.legal_name,
    cf.age_years,
    cf.income_amt,
    cf.credit_score
FROM Domain.Party_H p
INNER JOIN Prediction.customer_features cf
    ON cf.party_id = p.party_id
   AND cf.is_current = 1
WHERE p.is_current = 1
  AND p.is_deleted = 0
  AND p.party_key = 'CUST-123';
```

### 5.2 Integration with Semantic (Feature Definitions)

**Pattern**: Feature metadata stored in Semantic, feature values in Prediction

**Semantic Module stores**:
```sql
-- Feature definition metadata (in Semantic)
INSERT INTO Semantic.column_metadata (
    table_name, column_name, business_description,
    data_type, is_required
) VALUES (
    'customer_features', 'age_years',
    'Customer age in years calculated from date of birth',
    'INTEGER', 'Y'
);
```

**Prediction Module stores**:
```sql
-- Actual feature values (in Prediction)
INSERT INTO Prediction.customer_features (
    party_id, age_years, observation_dts, valid_from_dts
) VALUES (
    1001, 45, CURRENT_TIMESTAMP(6), CURRENT_TIMESTAMP(6)
);
```

**Agent workflow**:
1. Query Semantic → Learn what features exist and their meanings
2. Query Prediction → Get actual feature values for entities

### 5.3 Integration with Observability (Feature Monitoring)

**Pattern**: Observability tracks feature quality, not feature values

```sql
-- Feature drift/quality tracked in Observability (not Prediction)
CREATE TABLE Observability.feature_quality (
    quality_id INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    feature_name VARCHAR(128) NOT NULL,
    feature_group VARCHAR(100),
    evaluated_dts TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    null_percentage DECIMAL(5,4),
    distribution_shift_score DECIMAL(5,4),
    quality_score DECIMAL(3,2),
    is_active BYTEINT NOT NULL DEFAULT 1
)
PRIMARY INDEX (quality_id);

-- Observability stores metadata about features, not the features themselves
```

---

## 6. Agent Discovery and Querying

### 6.1 Discovery Patterns

#### What features exist?

```sql
-- Agent queries Semantic for feature catalog
SELECT table_name, column_name, business_description
FROM Semantic.column_metadata
WHERE table_name IN (
    SELECT table_name 
    FROM Semantic.entity_metadata 
    WHERE module_name = 'Prediction'
)
AND is_active = 1;
```

#### Get current feature values for an entity

```sql
-- Wide format
SELECT age_years, income_amt, credit_score
FROM Prediction.customer_features
WHERE party_id = 1001
  AND is_current = 1;

-- Tall format
SELECT feature_name, value_numeric
FROM Prediction.feature_value
WHERE entity_id = 1001
  AND entity_type = 'PARTY'
  AND is_current = 1;
```

#### Get historical feature values (point-in-time)

```sql
-- Features as they existed on specific date
SELECT feature_name, value_numeric, observation_dts
FROM Prediction.feature_value
WHERE entity_id = 1001
  AND entity_type = 'PARTY'
  AND observation_dts <= TIMESTAMP '2024-03-01 00:00:00+00:00'
  AND valid_from_dts <= TIMESTAMP '2024-03-01 00:00:00+00:00'
  AND valid_to_dts > TIMESTAMP '2024-03-01 00:00:00+00:00';
```

### 6.2 Standard Views for Agent Access

```sql
-- View 1: Current features only (engineered features from Prediction)
CREATE VIEW Prediction.v_customer_features_current
(
    -- View contract: agents see all returned columns without parsing the SELECT body
    party_id,
    age_normalized,
    income_normalized,
    credit_score_normalized,
    recency_score,
    transaction_velocity,
    observation_dts
)
AS
SELECT 
    cf.party_id,
    cf.age_normalized,        -- Engineered: normalized to 0-1
    cf.income_normalized,     -- Engineered: normalized to 0-1
    cf.credit_score_normalized, -- Engineered: normalized to 0-1
    cf.recency_score,         -- Engineered: days since last transaction, normalized
    cf.transaction_velocity,  -- Engineered: transaction count normalized
    cf.observation_dts
FROM Prediction.customer_features cf
WHERE cf.is_current = 1;

COMMENT ON VIEW Prediction.v_customer_features_current IS 
'Current customer features - filters to current engineered feature values for active feature serving and real-time scoring';

-- View 2: Features with Domain context (JOIN without duplication)
-- This pattern avoids duplicating domain attributes in Prediction module
CREATE VIEW Prediction.v_customer_features_enriched
(
    -- View contract: agents see all returned columns without parsing the SELECT body
    party_key,
    legal_name,
    party_type_code,
    birth_date,
    annual_income_amt,
    credit_limit_amt,
    age_normalized,
    income_normalized,
    credit_score_normalized,
    recency_score,
    transaction_velocity,
    observation_dts
)
AS
SELECT 
    -- Domain attributes (NOT duplicated in Prediction)
    p.party_key,
    p.legal_name,
    p.party_type_code,
    p.birth_date,           -- Raw value stays in Domain
    p.annual_income_amt,    -- Raw value stays in Domain
    p.credit_limit_amt,     -- Raw value stays in Domain
    
    -- Engineered features (stored in Prediction)
    cf.age_normalized,
    cf.income_normalized,
    cf.credit_score_normalized,
    cf.recency_score,
    cf.transaction_velocity,
    cf.observation_dts
FROM Prediction.v_customer_features_current cf
INNER JOIN Domain.Party_H p
    ON p.party_id = cf.party_id
   AND p.is_current = 1
   AND p.is_deleted = 0;

COMMENT ON VIEW Prediction.v_customer_features_enriched IS 
'Customer features enriched with Domain context - joins engineered features with raw domain attributes without duplication, provides complete customer context';

-- View 3: Point-in-Time Feature Reconstruction
-- For training with historical features
CREATE VIEW Prediction.v_customer_features_pit
(
    -- View contract: agents see all returned columns without parsing the SELECT body
    party_key,
    legal_name,
    age_normalized,
    income_normalized,
    observation_dts,
    valid_from_dts,
    valid_to_dts
)
AS
SELECT 
    p.party_key,
    p.legal_name,
    cf.age_normalized,
    cf.income_normalized,
    cf.observation_dts,
    cf.valid_from_dts,
    cf.valid_to_dts
FROM Prediction.customer_features cf
INNER JOIN Domain.Party_H p
    ON p.party_id = cf.party_id
   AND p.is_current = 1;  -- Join current party record to historical features

COMMENT ON VIEW Prediction.v_customer_features_pit IS 
'Point-in-time feature reconstruction - provides historical feature snapshots for ML training without data leakage, critical for model reproducibility';
```

**Key Pattern**: 
- Domain stores raw values (birth_date, annual_income_amt)
- Prediction stores engineered values (age_normalized, income_normalized)
- Views join them together efficiently (no data duplication)
- Agent queries view to get complete context

---

## 7. Designer Responsibilities

### 7.1 What Designers Must Supply

| Element | Designer Supplies | Example |
|---------|-------------------|---------|
| **Feature list** | What features to compute | age_years, income_amt, credit_score |
| **Storage pattern** | Wide or tall format | Wide for demographic features |
| **Feature groups** | Logical feature groupings | Demographics, Behavior, Risk |
| **Computation logic** | How features are calculated | age = CURRENT_DATE - birth_date |
| **Dependencies** | Source data for features | Demographics from Domain.Party_H |
| **Refresh frequency** | How often to update | Daily, real-time, on-demand |
| **Retention policy** | How long to keep history | 2 years for training |

### 7.2 Feature Definition in Semantic Module

**Designer must document features in Semantic**:

```sql
-- Feature metadata goes in Semantic
INSERT INTO Semantic.column_metadata (
    database_name, table_name, column_name,
    business_description, data_type, is_required
) VALUES (
    'PredictionDB', 'customer_features', 'age_years',
    'Customer age in years calculated from date of birth',
    'INTEGER', 'Y'
);
```

### 7.3 Design Checklist

**Before implementation:**

- [ ] Feature list defined
- [ ] Storage pattern chosen (wide vs tall)
- [ ] Feature definitions added to Semantic module
- [ ] Temporal strategy defined (observation_dts, valid_from_dts)
- [ ] Entity references follow standard FK pattern
- [ ] Point-in-time query patterns tested
- [ ] Current feature views created
- [ ] Integration with Domain tested
- [ ] Feature refresh process designed
- [ ] Retention policy documented
- [ ] Module_Registry INSERT generated for this module
- [ ] Min. 3 Design_Decision INSERTs generated
- [ ] Change_Log initial release entry generated
- [ ] Min. 3 Business_Glossary terms captured
- [ ] Min. 1 Query_Cookbook recipe captured

### 7.4 Documentation Capture Requirements

Every Prediction module must populate the Memory database documentation tables as part of its design workflow. The table definitions, workflows, and full protocol are defined in the **Memory Module Design Standard, Section 8**.

**Minimum requirements:**

| Record Type | Table | Minimum | Notes |
|-------------|-------|---------|-------|
| Module_Registry | `Memory.Module_Registry` | 1 | Register this module with data_product and version |
| Design_Decision | `Memory.Design_Decision` | 3 | Key architectural and schema choices |
| Change_Log | `Memory.Change_Log` | 1 | Initial release entry (version 1.0.0) |
| Business_Glossary | `Memory.Business_Glossary` | 3 | Feature store terms and ML concepts introduced |
| Query_Cookbook | `Memory.Query_Cookbook` | 1 | Key query patterns (e.g., current features lookup, point-in-time training dataset) |

**Typical decision categories for Prediction modules:**

| Decision Category | Example |
|-------------------|---------|
| `ARCHITECTURE` | Feature store pattern chosen — wide format vs tall format |
| `SCHEMA` | Feature engineering approach — normalization method, aggregation window |
| `PERFORMANCE` | Primary index on entity_id vs feature_date for access pattern alignment |
| `OPERATIONAL` | Feature refresh strategy and retention policy for training data |
| `INTEGRATION` | Feature metadata placement in Semantic vs Prediction boundary decisions |

**Decision ID prefix for this module:** `DD-PREDICTION-{NNN}` (e.g., `DD-PREDICTION-001`)

**Output file placement:** Write documentation capture SQL as the last numbered file in the prediction deployment directory (e.g., `03-prediction/05-documentation.sql`).

**Full protocol, SQL templates, and ID conventions:** See Memory Module Design Standard, Section 8.3 (Workflow 2 — Capture).

---

## Appendix A: Quick Reference

### Core Principles

```
✅ Feature Engineering Required → Store ENGINEERED features (normalized, transformed, aggregated)
✅ Not Raw Data Duplication → Don't copy domain columns as-is (use views to join)
✅ Normalized Scaling → Features scaled to common range (0-1) for equal weighting
✅ Feature Metadata → Semantic Module (definitions, computation logic)
✅ Feature Values → Prediction Module (actual engineered values)
✅ Point-in-Time Correctness → Critical for training without data leakage
✅ Selective Duplication OK → Only when justified for low-latency scoring (document rationale)
```

### Open Standards Alignment

Reference established feature store patterns:
- **Feast** (Open-source): https://feast.dev/ - Feature definitions, materialization
- **Tecton**: Feature engineering best practices
- **MLOps Feature Store Patterns**: Versioning, lineage, monitoring

### Storage Patterns

```
Wide Format:  Multiple features per row (feature groups accessed together)
Tall Format:  One feature per row (flexible, sparse, dynamic features)
Choice:       Designer decides based on access patterns and sparsity
```

### Standard Views (Required)

```
✅ v_{entity}_features_current    -- Current engineered feature values
✅ v_{entity}_features_enriched   -- Features + Domain context (JOIN, no duplication)
✅ v_{entity}_features_pit        -- Point-in-time feature reconstruction
```

### Temporal Columns (Required)

```
observation_dts      -- When feature was observed/computed
valid_from_dts       -- When this version became valid
valid_to_dts         -- When this version was superseded
is_current           -- Current version flag
```

### Feature Engineering Examples

```
Normalization:     (value - min) / (max - min) → 0-1
Standardization:   (value - mean) / std_dev → z-score
Aggregation:       COUNT(*) / time_window → velocity metrics
Derivation:        balance / credit_limit → utilization ratio
Encoding:          One-hot, target encoding for categoricals
```

### Integration Patterns

```
Prediction → Domain:       Join on entity_key for context (use views, avoid duplication)
Prediction → Semantic:     Feature definitions, computation logic
Prediction → Observability: Feature drift, quality monitoring
```

### When to Duplicate Domain Values

```
✅ Acceptable:
- Low-latency scoring (< 100ms requirement)
- Value changes infrequently  
- Complex join would exceed latency budget
- MUST document rationale

❌ Not Acceptable:
- "Convenience" (use views instead)
- Values change frequently (sync overhead)
- No performance requirement
```

---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.6 | 2026-03-20 | Fixed boolean column definition in model_prediction table: is_active CHAR(1) DEFAULT 'Y' → BYTEINT NOT NULL DEFAULT 1; fixed = 'Y' filter value to = 1. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.5 | 2026-03-20 | Revised Documentation Capture Requirements section — updated to reflect self-contained data product principle. Documentation tables now reside in the Memory database ({ProductName}_Memory), not a shared dp_documentation database. Removed data_product column from INSERT templates, removed bootstrap checklist item, updated prose references from dp_documentation to Memory database. |
| 1.4 | 2026-03-20 | Added Section 7.4 Documentation Capture Requirements — minimum dp_documentation records, typical decision categories, output file placement, and reference to Memory Module Section 8 protocol. Updated Section 7.3 checklist to include documentation capture steps. | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.3 | 2026-03-18 | Applied surrogate key naming convention to internal management tables: renamed {table}_key → {table}_id for all GENERATED ALWAYS AS IDENTITY columns | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.2 | 2026-03-17 | Updated naming convention: {entity}_id = Surrogate Key, {entity}_key = Natural Business Key, aligned with Domain Module Design Standard v2.1 | Kimiko Yabu, Worldwide Data Architecture Team, Teradata |
| 1.1 | 2025-02-27 | Changed is_current to be consistent with Domain module | Nathan Green, Worldwide Data Architecture Team, Teradata |
| 1.0 | 2025-02-09 | Initial Prediction Module Design Standard | Nathan Green, Worldwide Data Architecture Team, Teradata |

---

**End of Prediction Module Design Standard**
