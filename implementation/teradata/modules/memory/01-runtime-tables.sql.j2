-- Memory module — runtime facet tables (Teradata).
-- Binding of design/modules/memory.md §4. Every runtime record carries a privacy
-- scope (INV-MEMORY-003); references are table-level only (INV-MEMORY-001).
-- Replace {{ product }} with the data product name.

-- ---------------------------------------------------------------------------
-- Agent session
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.agent_session (
    session_id           INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    session_key          VARCHAR(100) NOT NULL,
    agent_key            VARCHAR(100) NOT NULL,
    user_key             VARCHAR(100),
    session_start_dts    TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    session_end_dts      TIMESTAMP(6) WITH TIME ZONE,
    session_status       VARCHAR(20),          -- ACTIVE, COMPLETED, ABANDONED
    session_goal         VARCHAR(500),
    session_context_json JSON,
    scope_level          VARCHAR(20) NOT NULL, -- USER, TEAM, ORGANIZATION, AGENT
    scope_identifier     VARCHAR(100) NOT NULL,
    created_at           TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (session_id);

COMMENT ON TABLE {{ product }}_Memory.agent_session IS
'Agent session state - tracks active and historical agent sessions for continuity across interactions.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.session_id IS 'Surrogate key for session record.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.session_key IS 'Business session identifier - unique across systems.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.agent_key IS 'Agent identifier - which agent instance handles this session.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.user_key IS 'User identifier - which user is interacting. Key only; no name/email (join to Domain).';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.session_start_dts IS 'When the session began.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.session_end_dts IS 'When the session ended - NULL while active.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.session_status IS 'ACTIVE (ongoing), COMPLETED, ABANDONED.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.session_goal IS 'What the user is trying to accomplish this session.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.session_context_json IS 'Flexible session context - retrieved and processed by the consumer.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.scope_level IS 'Privacy scope - USER, TEAM, ORGANIZATION, AGENT.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.scope_identifier IS 'Scope identifier matching scope_level - enforces privacy boundaries.';
COMMENT ON COLUMN {{ product }}_Memory.agent_session.created_at IS 'When this session record was created.';

-- ---------------------------------------------------------------------------
-- Agent interaction (table-level references only; counts, not result data)
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.agent_interaction (
    interaction_id       INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    session_id           INTEGER NOT NULL,     -- FK to agent_session
    interaction_seq      INTEGER NOT NULL,
    interaction_type     VARCHAR(50),          -- QUERY, ACTION, DECISION, EXPLANATION
    interaction_dts      TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    user_input           VARCHAR(4000),
    agent_response       VARCHAR(4000),
    action_taken         VARCHAR(500),
    referenced_tables    VARCHAR(1000),        -- 'Domain.Party_H, Prediction.customer_features' (TABLE LEVEL)
    sql_executed         VARCHAR(4000),        -- the query text, not its results
    query_result_count   INTEGER,              -- aggregate count only, never the ids
    execution_time_ms    INTEGER,
    outcome_status       VARCHAR(20),          -- SUCCESS, PARTIAL, FAILED
    user_feedback        VARCHAR(20),          -- POSITIVE, NEUTRAL, NEGATIVE, NULL
    scope_level          VARCHAR(20) NOT NULL,
    scope_identifier     VARCHAR(100) NOT NULL,
    created_at           TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (interaction_id);

COMMENT ON TABLE {{ product }}_Memory.agent_interaction IS
'Agent interaction log - what the agent did, which tables were involved, and the outcome. TABLE-LEVEL references only; never individual result keys.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.interaction_id IS 'Surrogate key for interaction record.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.session_id IS 'FK to agent_session - parent session.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.interaction_seq IS 'Order within the session.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.interaction_type IS 'QUERY, ACTION, DECISION, EXPLANATION.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.interaction_dts IS 'When this interaction occurred.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.user_input IS 'What the user asked.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.agent_response IS 'Brief summary of what the agent provided.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.action_taken IS 'What the agent actually did.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.referenced_tables IS 'Comma-separated qualified table names - TABLE LEVEL, not instance keys.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.sql_executed IS 'Query text run by the agent, if applicable - not its results.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.query_result_count IS 'Aggregate count of records returned - NOT individual keys.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.execution_time_ms IS 'Execution time in milliseconds.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.outcome_status IS 'SUCCESS, PARTIAL, FAILED.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.user_feedback IS 'POSITIVE, NEUTRAL, NEGATIVE, NULL - used for learning.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.scope_level IS 'Privacy scope - USER, TEAM, ORGANIZATION, AGENT.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.scope_identifier IS 'Scope identifier matching scope_level.';
COMMENT ON COLUMN {{ product }}_Memory.agent_interaction.created_at IS 'When this interaction record was created.';

-- ---------------------------------------------------------------------------
-- Learned strategy
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.learned_strategy (
    strategy_id            INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    strategy_name          VARCHAR(128) NOT NULL,
    strategy_description    VARCHAR(1000),
    strategy_category      VARCHAR(50),        -- QUERY_OPTIMIZATION, FEATURE_SELECTION, ERROR_HANDLING
    applies_to_scenario    VARCHAR(500),
    strategy_pattern       VARCHAR(4000),
    strategy_metadata_json JSON,
    discovered_dts         TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    discovered_by_agent    VARCHAR(100),
    times_used             INTEGER DEFAULT 0,
    success_rate           DECIMAL(5,4),       -- 0.0-1.0
    scope_level            VARCHAR(20) NOT NULL,
    scope_identifier       VARCHAR(100) NOT NULL,
    is_active              BYTEINT NOT NULL DEFAULT 1,
    is_validated           BYTEINT NOT NULL DEFAULT 0,
    created_at             TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at             TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (strategy_id);

COMMENT ON TABLE {{ product }}_Memory.learned_strategy IS
'Strategies learned by agents - successful patterns discovered through experience.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.strategy_id IS 'Surrogate key for learned strategy.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.strategy_name IS 'Descriptive identifier for this approach.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.strategy_description IS 'What the strategy does and when to apply it.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.strategy_category IS 'QUERY_OPTIMIZATION, FEATURE_SELECTION, ERROR_HANDLING, etc.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.applies_to_scenario IS 'Conditions where this strategy is effective.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.strategy_pattern IS 'The pattern, logic, or approach - described, not result data.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.strategy_metadata_json IS 'Complex strategy details - processed by the consumer.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.discovered_dts IS 'When the strategy was discovered.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.discovered_by_agent IS 'Agent that learned this pattern.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.times_used IS 'How many times applied.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.success_rate IS '0.0-1.0 - share of successful outcomes.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.scope_level IS 'Privacy scope - USER, TEAM, ORGANIZATION, AGENT.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.scope_identifier IS 'Scope identifier matching scope_level.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.is_active IS '1 = active, 0 = deprecated.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.is_validated IS '1 = validated by human or testing, 0 = not yet.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.created_at IS 'When this strategy record was created.';
COMMENT ON COLUMN {{ product }}_Memory.learned_strategy.updated_at IS 'When this strategy was last refined.';

-- ---------------------------------------------------------------------------
-- User preference
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.user_preference (
    preference_id          INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    user_key               VARCHAR(100) NOT NULL,
    user_group             VARCHAR(100),
    preference_category    VARCHAR(50),        -- REPORT_FORMAT, DATA_FILTER, AGGREGATION_LEVEL, VISUALIZATION_TYPE
    preference_name        VARCHAR(128) NOT NULL,
    preference_value       VARCHAR(1000),
    preference_value_json  JSON,
    applies_to_entity      VARCHAR(100),
    confidence             DECIMAL(5,4),       -- 0.0-1.0
    last_used_dts          TIMESTAMP(6) WITH TIME ZONE,
    scope_level            VARCHAR(20) NOT NULL DEFAULT 'USER',
    scope_identifier       VARCHAR(100) NOT NULL,
    is_active              BYTEINT NOT NULL DEFAULT 1,
    created_at             TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6),
    updated_at             TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (preference_id);

COMMENT ON TABLE {{ product }}_Memory.user_preference IS
'User and stakeholder preferences learned from interactions - enables personalised agent behaviour.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.preference_id IS 'Surrogate key for preference record.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.user_key IS 'User this preference belongs to. Key only; no PII.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.user_group IS 'User group or team for group-level preferences.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.preference_category IS 'REPORT_FORMAT, DATA_FILTER, AGGREGATION_LEVEL, VISUALIZATION_TYPE, etc.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.preference_name IS 'Specific preference identifier within category.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.preference_value IS 'Simple text value.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.preference_value_json IS 'Structured preference - processed by the consumer.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.applies_to_entity IS 'Table or entity type this preference applies to.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.confidence IS '0.0-1.0 - evidence strength for this preference.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.last_used_dts IS 'When the preference was last applied.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.scope_level IS 'Privacy scope - USER (default), TEAM, ORGANIZATION.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.scope_identifier IS 'Scope identifier matching scope_level.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.is_active IS '1 = active, 0 = deprecated.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.created_at IS 'When first learned.';
COMMENT ON COLUMN {{ product }}_Memory.user_preference.updated_at IS 'When last reinforced.';

-- ---------------------------------------------------------------------------
-- Discovered pattern (summary statistics; TABLE-LEVEL references)
-- ---------------------------------------------------------------------------
CREATE TABLE {{ product }}_Memory.discovered_pattern (
    pattern_id              INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY,
    pattern_name            VARCHAR(128) NOT NULL,
    pattern_description     VARCHAR(1000),
    pattern_type            VARCHAR(50),       -- CORRELATION, TEMPORAL, TABLE_RELATIONSHIP, ANOMALY
    pattern_definition_json JSON,
    sample_size             INTEGER,           -- how many records analysed (summary, not the records)
    occurrences             INTEGER,
    confidence_score        DECIMAL(5,4),
    statistical_significance DECIMAL(5,4),
    discovered_dts          TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    discovered_by_agent     VARCHAR(100),
    involved_tables         VARCHAR(1000),     -- 'Domain.Party_H, Prediction.customer_features' (TABLE LEVEL)
    is_validated            BYTEINT NOT NULL DEFAULT 0,
    scope_level             VARCHAR(20) NOT NULL,
    scope_identifier        VARCHAR(100) NOT NULL,
    is_active               BYTEINT NOT NULL DEFAULT 1,
    created_at              TIMESTAMP(6) WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP(6)
)
PRIMARY INDEX (pattern_id);

COMMENT ON TABLE {{ product }}_Memory.discovered_pattern IS
'Patterns discovered by agents - pattern metadata and statistical support, NOT individual record details.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.pattern_id IS 'Surrogate key for pattern record.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.pattern_name IS 'Descriptive identifier for the insight.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.pattern_description IS 'The pattern and its business implication.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.pattern_type IS 'CORRELATION, TEMPORAL, TABLE_RELATIONSHIP, ANOMALY.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.pattern_definition_json IS 'Pattern conditions/formulas - processed by the consumer.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.sample_size IS 'How many records were analysed - evidence strength, not the records.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.occurrences IS 'How many times the pattern was observed.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.confidence_score IS '0.0-1.0 statistical confidence.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.statistical_significance IS 'Significance score for validity testing.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.discovered_dts IS 'When the pattern was discovered.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.discovered_by_agent IS 'Agent that performed the analysis.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.involved_tables IS 'Comma-separated qualified table names - TABLE LEVEL, not instance keys.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.is_validated IS '1 = validated, 0 = not yet.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.scope_level IS 'Privacy scope - USER, TEAM, ORGANIZATION, AGENT.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.scope_identifier IS 'Scope identifier matching scope_level.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.is_active IS '1 = active, 0 = invalidated.';
COMMENT ON COLUMN {{ product }}_Memory.discovered_pattern.created_at IS 'When this pattern record was created.';
