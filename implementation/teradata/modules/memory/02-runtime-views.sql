-- Memory module — runtime facet standard views (Teradata). AccessView binding.
-- Explicit column contracts so agents read the header, not the SELECT body.
-- Replace {{ product }} with the data product name.

REPLACE VIEW {{ product }}_Memory.v_interactions_summary
(
    session_id, interaction_seq, interaction_type, user_input, action_taken,
    sql_executed, query_result_count, execution_time_ms, outcome_status,
    user_feedback, referenced_tables, scope_level, scope_identifier, interaction_dts
)
AS
SELECT
    ai.session_id, ai.interaction_seq, ai.interaction_type, ai.user_input, ai.action_taken,
    ai.sql_executed, ai.query_result_count, ai.execution_time_ms, ai.outcome_status,
    ai.user_feedback, ai.referenced_tables, ai.scope_level, ai.scope_identifier, ai.interaction_dts
FROM {{ product }}_Memory.agent_interaction ai;

COMMENT ON VIEW {{ product }}_Memory.v_interactions_summary IS
'Agent interaction summary - table references for filtering without JSON parsing.';

REPLACE VIEW {{ product }}_Memory.v_active_sessions
(
    session_id, session_key, agent_key, user_key, session_start_dts,
    session_goal, scope_level, scope_identifier
)
AS
SELECT
    session_id, session_key, agent_key, user_key, session_start_dts,
    session_goal, scope_level, scope_identifier
FROM {{ product }}_Memory.agent_session
WHERE session_status = 'ACTIVE';

COMMENT ON VIEW {{ product }}_Memory.v_active_sessions IS
'Currently active agent sessions.';

REPLACE VIEW {{ product }}_Memory.v_learned_strategies_org
(
    strategy_id, strategy_name, strategy_category, strategy_pattern, success_rate, times_used
)
AS
SELECT
    strategy_id, strategy_name, strategy_category, strategy_pattern, success_rate, times_used
FROM {{ product }}_Memory.learned_strategy
WHERE scope_level = 'ORGANIZATION'
  AND is_active = 1
  AND is_validated = 1;

COMMENT ON VIEW {{ product }}_Memory.v_learned_strategies_org IS
'Organization-wide validated strategies.';
