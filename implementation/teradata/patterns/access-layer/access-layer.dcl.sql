-- =============================================================================
-- ACCESS LAYER — {ProductName} Data Product (Teradata)
-- Binding of design/patterns/access-layer.md. File: 00-access/{ProductName}_access_layer.dcl
--
-- Phase 1.5: apply after Memory + Semantic are deployed.
-- Phase 2.5: apply after Domain + Observability are deployed; add further GRANT
--            blocks as additional modules deploy.
-- Standard {ProductName}_{Module} placement shown; for STRICT_SEPARATION substitute
-- the _V view containers (see object-placement).
-- =============================================================================

-- Create roles -----------------------------------------------------------------
CREATE ROLE {ProductName}_ROLE_READ;
COMMENT ON ROLE {ProductName}_ROLE_READ IS
    '{ProductName} data product - read-only access for analysts and BI tools.';

CREATE ROLE {ProductName}_ROLE_AGENT;
COMMENT ON ROLE {ProductName}_ROLE_AGENT IS
    '{ProductName} data product - AI agent and automated tool access. Read on module
     access containers plus write-back to Memory and Observability. Kept separate
     from ROLE_READ for independent lifecycle and the write-back boundary.';

CREATE ROLE {ProductName}_ROLE_ADMIN;
COMMENT ON ROLE {ProductName}_ROLE_ADMIN IS
    '{ProductName} data product - owner and data steward access. Read on all containers.';

-- Phase 1.5 — after Memory + Semantic ------------------------------------------
GRANT SELECT ON {ProductName}_Semantic TO {ProductName}_ROLE_READ;
GRANT SELECT ON {ProductName}_Semantic TO {ProductName}_ROLE_AGENT;
GRANT SELECT ON {ProductName}_Semantic TO {ProductName}_ROLE_ADMIN;

GRANT SELECT ON {ProductName}_Memory   TO {ProductName}_ROLE_READ;
GRANT SELECT ON {ProductName}_Memory   TO {ProductName}_ROLE_AGENT;
GRANT SELECT ON {ProductName}_Memory   TO {ProductName}_ROLE_ADMIN;

-- Agent write-back to Memory: interactions, learned strategies, design decisions
GRANT INSERT ON {ProductName}_Memory   TO {ProductName}_ROLE_AGENT;

-- Phase 2.5 — after Domain + Observability -------------------------------------
GRANT SELECT ON {ProductName}_Domain        TO {ProductName}_ROLE_READ;
GRANT SELECT ON {ProductName}_Domain        TO {ProductName}_ROLE_AGENT;
GRANT SELECT ON {ProductName}_Domain        TO {ProductName}_ROLE_ADMIN;

GRANT SELECT ON {ProductName}_Observability TO {ProductName}_ROLE_READ;
GRANT SELECT ON {ProductName}_Observability TO {ProductName}_ROLE_AGENT;
GRANT SELECT ON {ProductName}_Observability TO {ProductName}_ROLE_ADMIN;

-- Agent write-back to Observability: usage events and quality feedback
GRANT INSERT ON {ProductName}_Observability TO {ProductName}_ROLE_AGENT;

-- When Search is deployed ------------------------------------------------------
-- GRANT SELECT ON {ProductName}_Search     TO {ProductName}_ROLE_READ;
-- GRANT SELECT ON {ProductName}_Search     TO {ProductName}_ROLE_AGENT;
-- GRANT SELECT ON {ProductName}_Search     TO {ProductName}_ROLE_ADMIN;

-- When Prediction is deployed --------------------------------------------------
-- GRANT SELECT ON {ProductName}_Prediction TO {ProductName}_ROLE_READ;
-- GRANT SELECT ON {ProductName}_Prediction TO {ProductName}_ROLE_AGENT;
-- GRANT SELECT ON {ProductName}_Prediction TO {ProductName}_ROLE_ADMIN;

-- Assign roles to users/service accounts (operational event; replace placeholders):
-- GRANT {ProductName}_ROLE_AGENT TO {agent_service_account};
-- GRANT {ProductName}_ROLE_READ  TO {analyst_user_or_group_role};
-- GRANT {ProductName}_ROLE_ADMIN TO {product_owner_user};
