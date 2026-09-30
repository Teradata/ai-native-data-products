-- Dedicated database and fresh cluster-wide role names required.
-- Deployment login owns objects; provision login memberships separately.
CREATE ROLE customer360_role_read NOLOGIN;
CREATE ROLE customer360_role_agent NOLOGIN;
CREATE ROLE customer360_role_admin NOLOGIN;

DO $$
DECLARE ns text; obj record;
BEGIN
 FOREACH ns IN ARRAY ARRAY['memory','semantic','domain','observability','search','prediction'] LOOP
  EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC',ns);
  EXECUTE format('GRANT USAGE ON SCHEMA %I TO customer360_role_read,customer360_role_agent,customer360_role_admin',ns);
  EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM PUBLIC',ns);
  EXECUTE format('REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA %I FROM PUBLIC',ns);
  EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC',ns);
  EXECUTE format('GRANT ALL ON ALL TABLES IN SCHEMA %I TO customer360_role_admin',ns);
  EXECUTE format('GRANT ALL ON ALL SEQUENCES IN SCHEMA %I TO customer360_role_admin',ns);
  EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA %I TO customer360_role_admin',ns);
 END LOOP;
 FOR obj IN SELECT object_identity FROM semantic.access_object WHERE is_agent_consumable LOOP
  EXECUTE format('GRANT SELECT ON %s TO customer360_role_read,customer360_role_agent',obj.object_identity::regclass);
 END LOOP;
 FOREACH ns IN ARRAY ARRAY['agent_session','agent_interaction','learned_strategy','user_preference','discovered_pattern'] LOOP
  EXECUTE format('ALTER TABLE memory.%I ENABLE ROW LEVEL SECURITY',ns);
  EXECUTE format('CREATE POLICY runtime_owner ON memory.%I TO customer360_role_agent USING (scope_level=''USER'' AND scope_identifier=session_user) WITH CHECK (scope_level=''USER'' AND scope_identifier=session_user)',ns);
  EXECUTE format('CREATE POLICY runtime_admin ON memory.%I TO customer360_role_admin USING (true) WITH CHECK (true)',ns);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON memory.%I TO customer360_role_agent',ns);
 END LOOP;
END;
$$;
GRANT INSERT ON observability.agent_outcome TO customer360_role_agent;
GRANT EXECUTE ON FUNCTION search.embed(text),search.cosine(double precision[],double precision[]),search.nearest(double precision[],integer)
 TO customer360_role_read,customer360_role_agent;
