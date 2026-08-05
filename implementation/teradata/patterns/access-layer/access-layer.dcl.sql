-- =============================================================================
-- ACCESS LAYER: {ProductName} Data Product (Teradata)
-- Binding of design/patterns/access-layer.md. File: 00-access/{ProductName}_access_layer.dcl
--
-- Phase 1.5a: apply as soon as the containers exist, at the end of Phase 1.
-- Phase 1.5b: apply after Memory + Semantic are deployed. REQUIRES DBA PRIVILEGE.
-- Phase 2.5:  apply after Domain + Observability are deployed; add further GRANT
--             blocks as additional modules deploy.
-- Standard {ProductName}_{Module} placement shown; for STRICT_SEPARATION substitute
-- the _V view containers (see object-placement).
-- =============================================================================

-- =============================================================================
-- Phase 1.5a: implied grants. NO DBA PRIVILEGE REQUIRED.
--
-- These are what lets a view in the access container compile against a base table
-- in a module container. They need only ownership of both containers, they do not
-- depend on the roles below, and omitting them fails later and elsewhere: the view
-- creation in a subsequent phase reports [5315] An owner referenced by user does
-- not have SELECT WITH GRANT OPTION access, which reads as a problem with the view.
--
-- Apply these before compiling any consumer view. Required only where
-- object-placement separates views from base tables; under co-located placement
-- the access container is the module container and there is nothing to grant.
-- =============================================================================
GRANT SELECT ON {ProductName}_Semantic      TO {ProductName}_Access WITH GRANT OPTION;
GRANT SELECT ON {ProductName}_Memory        TO {ProductName}_Access WITH GRANT OPTION;
GRANT SELECT ON {ProductName}_Domain        TO {ProductName}_Access WITH GRANT OPTION;
GRANT SELECT ON {ProductName}_Observability TO {ProductName}_Access WITH GRANT OPTION;
-- GRANT SELECT ON {ProductName}_Search      TO {ProductName}_Access WITH GRANT OPTION;
-- GRANT SELECT ON {ProductName}_Prediction  TO {ProductName}_Access WITH GRANT OPTION;

-- =============================================================================
-- Phase 1.5b onwards: roles and consumer grants. REQUIRES DBA PRIVILEGE.
--
-- CREATE ROLE is a DBA-level operation. Confirm the deploying account holds it
-- before generating this block:
--     SELECT * FROM DBC.AllRightsV WHERE UserName = USER AND AccessRight = 'CG';
--
-- Where it does not, emit everything from here down as a separate artefact for a
-- DBA to apply, and continue the deployment without it: the schema and data are
-- fully functional, and the outstanding step stays visible instead of being
-- silently skipped. Phase 1.5a above is unaffected and must still be applied.
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

-- Phase 1.5b: after Memory + Semantic -----------------------------------------
GRANT SELECT ON {ProductName}_Semantic TO {ProductName}_ROLE_READ;
GRANT SELECT ON {ProductName}_Semantic TO {ProductName}_ROLE_AGENT;
GRANT SELECT ON {ProductName}_Semantic TO {ProductName}_ROLE_ADMIN;

GRANT SELECT ON {ProductName}_Memory   TO {ProductName}_ROLE_READ;
GRANT SELECT ON {ProductName}_Memory   TO {ProductName}_ROLE_AGENT;
GRANT SELECT ON {ProductName}_Memory   TO {ProductName}_ROLE_ADMIN;

-- Agent write-back to Memory: interactions, learned strategies, design decisions
GRANT INSERT ON {ProductName}_Memory   TO {ProductName}_ROLE_AGENT;

-- Phase 2.5: after Domain + Observability -------------------------------------
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
