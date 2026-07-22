-- Prediction module — model prediction outputs (Teradata).
-- Binding of design/modules/prediction.md §3. SCD2 with reproducibility linkage. Replace {{ product }}.

CREATE TABLE {{ product }}_Prediction.model_prediction (
    prediction_id     INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    entity_id         BIGINT NOT NULL,
    entity_type       VARCHAR(50) NOT NULL,
    model_key         VARCHAR(100) NOT NULL,
    model_version     VARCHAR(20) NOT NULL,
    prediction_value  DECIMAL(10,6),          -- score / probability / continuous output
    prediction_class  VARCHAR(100),           -- classification label
    prediction_json   JSON,                   -- multi-class / structured output
    confidence_score  DECIMAL(5,4),           -- 0-1
    prediction_dts    TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    feature_observation_dts TIMESTAMP(6) WITH TIME ZONE,  -- links to the feature timestamp used
    valid_from_dts    TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_to_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL
                          DEFAULT TIMESTAMP '9999-12-31 23:59:59.999999+00:00',
    is_current        BYTEINT NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    created_by         VARCHAR(100),
    created_at         TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (entity_id);

COMMENT ON TABLE {{ product }}_Prediction.model_prediction IS
'Model prediction outputs with temporal tracking and confidence - ML inference results.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.prediction_id IS 'Surrogate key for the prediction.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.entity_id IS 'FK to the Domain entity this prediction is about - id only.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.entity_type IS 'Entity kind - PARTY, PRODUCT, ...';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.model_key IS 'Model identifier.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.model_version IS 'Model version used.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.prediction_value IS 'Numeric output - probability, risk, or continuous value.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.prediction_class IS 'Predicted class or category.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.prediction_json IS 'Multi-class probabilities or structured output.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.confidence_score IS 'Model confidence, 0-1.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.prediction_dts IS 'When the prediction was generated.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.feature_observation_dts IS 'When the input features were observed - reproducibility linkage.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.valid_from_dts IS 'When this prediction version became valid.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.valid_to_dts IS 'When superseded - sentinel 9999-12-31 for current.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.is_current IS '1 = latest prediction, 0 = historical.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.created_by IS 'Serving API / batch scoring job.';
COMMENT ON COLUMN {{ product }}_Prediction.model_prediction.created_at IS 'When inserted.';
