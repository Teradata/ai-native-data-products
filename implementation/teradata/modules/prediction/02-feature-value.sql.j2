-- Prediction module — tall-format feature-value table (Teradata).
-- Binding of design/modules/prediction.md §3. One feature per row; sparse/dynamic/mixed-type.
-- SCD2 with point-in-time. Replace {{ product }}.

CREATE TABLE {{ product }}_Prediction.feature_value (
    feature_value_id  INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    entity_id         BIGINT NOT NULL,
    entity_type       VARCHAR(50) NOT NULL,   -- PARTY, PRODUCT, ...
    feature_name      VARCHAR(128) NOT NULL,
    feature_group     VARCHAR(100),
    value_numeric     DECIMAL(18,4),          -- normalised 0-1 where appropriate
    value_text        VARCHAR(500),
    value_json        JSON,
    value_type        VARCHAR(20),            -- NUMERIC, TEXT, JSON, BOOLEAN
    observation_dts   TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_from_dts    TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_to_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL
                          DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
    is_current        BYTEINT NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    feature_version   VARCHAR(20),
    computation_dts   TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    source_system     VARCHAR(50),
    created_by         VARCHAR(100)
)
PRIMARY INDEX (entity_id);

COMMENT ON TABLE {{ product }}_Prediction.feature_value IS
'Feature values - tall format, one feature per row, flexible types for sparse or dynamic feature sets. ENGINEERED values; raw Domain values are joined, not duplicated.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.feature_value_id IS 'Surrogate key for the feature value.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.entity_id IS 'FK to the Domain entity - id only.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.entity_type IS 'Entity kind - PARTY, PRODUCT, ...';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.feature_name IS 'Feature name - e.g. recency_score.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.feature_group IS 'Feature group - e.g. behavioral, demographic.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.value_numeric IS 'Numeric value, normalised 0-1 where appropriate.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.value_text IS 'Categorical/text value.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.value_json IS 'Complex multi-dimensional value.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.value_type IS 'NUMERIC, TEXT, JSON, BOOLEAN - which value column holds data.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.observation_dts IS 'When observed/computed - point-in-time anchor (no leakage).';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.valid_from_dts IS 'When this version became valid.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.valid_to_dts IS 'When superseded - sentinel 9999-12-31 for current.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.is_current IS '1 = current, 0 = historical.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.feature_version IS 'Feature computation logic version.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.computation_dts IS 'When computed and stored.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.source_system IS 'Process that computed the feature.';
COMMENT ON COLUMN {{ product }}_Prediction.feature_value.created_by IS 'User/process that created the value.';
