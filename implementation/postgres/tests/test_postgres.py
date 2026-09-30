"""Native PostgreSQL tests. POSTGRES_TEST_DSN must name a fresh disposable database.

The suite creates the product once. Each mutation test rolls back. It never drops
an existing database or schema; an occupied target fails the build transaction.
"""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from checks import Check, profile
from render import render_all
from temporal import allocate_key, apply_change
from validate import validate


class GeneratedSQL(unittest.TestCase):
    def test_generated_files_current(self):
        for path, content in render_all().items():
            self.assertEqual(path.read_text(encoding='utf-8'),content,str(path))


@unittest.skipUnless(os.environ.get('POSTGRES_TEST_DSN'), 'Set POSTGRES_TEST_DSN to a fresh disposable PostgreSQL database')
class PostgreSQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.con = psycopg.connect(os.environ['POSTGRES_TEST_DSN'],autocommit=True)
        spec = importlib.util.spec_from_file_location('postgres_build',ROOT.parents[1]/'examples/customer360-postgres/build.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # A rejected validation must leave neither schemas nor cluster roles.
        with patch.object(mod,'validate',return_value=[{'status':'FAILED'}]):
            try:
                mod.build(cls.con)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Invalid build unexpectedly published')
        if cls.con.execute("SELECT to_regnamespace('domain') IS NOT NULL OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname='customer360_role_read')").fetchone()[0]:
            raise AssertionError('Failed build did not roll back schema and role creation')
        cls.results = mod.build(cls.con)
        cls.builder = staticmethod(mod.build)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def setUp(self):
        self.tx = self.con.transaction(force_rollback=True)
        self.tx.__enter__()

    def tearDown(self):
        self.tx.__exit__(None,None,None)

    def rows(self,sql,params=None):
        return self.con.execute(sql,params).fetchall()

    def rejects(self,sql):
        import psycopg
        with self.assertRaises(psycopg.Error):
            with self.con.transaction():
                self.con.execute(sql)

    def test_complete_profile_and_append(self):
        self.assertGreater(len(self.results),500)
        self.assertFalse([r for r in self.results if r['status']!='PASSED'])
        results = validate(self.con)
        self.assertFalse([r for r in results if r['status']!='PASSED'])
        self.assertEqual(self.rows('SELECT count(*) FROM observability.validation_run'),[(2,)])
        self.assertIn(('Embed','unknown'),self.rows('SELECT scope_id,confidence FROM observability.trust_map'))

    def test_half_open_current_and_deleted(self):
        self.assertEqual(self.rows("SELECT segment FROM domain.at_customer('2025-02-01Z') WHERE customer_id=1"),[('premium',)])
        self.assertEqual(self.rows("SELECT segment FROM domain.at_customer('2025-01-31Z') WHERE customer_id=1"),[('standard',)])
        self.assertEqual(self.rows('SELECT customer_id FROM domain.v_customer ORDER BY customer_id'),[(1,),(2,)])

    def test_overlap_and_natural_key_constraints(self):
        import psycopg
        with self.assertRaises(psycopg.errors.ExclusionViolation):
            with self.con.transaction():
                self.con.execute("INSERT INTO domain.customer SELECT customer_id,customer_key,display_name,segment,'2025-01-15Z',valid_to_dts,is_current,is_deleted,deleted_dts,created_dts,updated_dts FROM domain.customer WHERE customer_id=1 AND NOT is_current")
        self.rejects("UPDATE domain.customer SET customer_key='OTHER' WHERE customer_id=1")

    def test_occupied_target_preserved(self):
        import psycopg
        with self.assertRaises(psycopg.errors.DuplicateSchema):
            self.builder(self.con)
        self.assertEqual(self.rows('SELECT count(*) FROM domain.customer'),[(5,)])

    def test_no_evidence_and_latest_per_area(self):
        self.con.execute('DELETE FROM observability.validation_check')
        self.con.execute('DELETE FROM observability.validation_area')
        self.con.execute('DELETE FROM observability.validation_run')
        self.assertEqual(self.rows('SELECT area_status,confidence FROM observability.trust_map'),[('no-evidence','unknown')])
        validate(self.con,[Check('DOMAIN','MODULE','domain','SELECT 1 WHERE false')])
        validate(self.con,[Check('SEMANTIC','MODULE','semantic','SELECT 1 WHERE false')])
        areas = self.rows("SELECT scope_id,confidence FROM observability.trust_map WHERE scope_kind='MODULE' ORDER BY scope_id")
        self.assertEqual(areas,[('domain','strong'),('semantic','strong')])

    def test_temporal_writer_replay_late_change_and_rollback(self):
        key = allocate_key(self.con,'customer','NEW')
        self.assertEqual(key,allocate_key(self.con,'customer','NEW'))
        attrs = dict(customer_key='NEW',display_name='New Customer',segment='standard')
        self.assertTrue(apply_change(self.con,'domain.customer',key,'2025-01-01Z',attrs))
        self.assertFalse(apply_change(self.con,'domain.customer',key,'2025-01-01Z',attrs))
        self.assertTrue(apply_change(self.con,'domain.customer',key,'2025-03-01Z',dict(attrs,segment='premium')))
        self.assertTrue(apply_change(self.con,'domain.customer',key,'2025-02-01Z',dict(attrs,segment='intermediate')))
        self.assertEqual(self.rows("SELECT segment FROM domain.at_customer('2025-02-15Z') WHERE customer_id=%s",[key]),[('intermediate',)])
        with self.assertRaises(ValueError):
            apply_change(self.con,'domain.customer',key,'2025-02-01Z',dict(attrs,segment='conflict'))
        self.assertEqual(self.rows('SELECT count(*) FROM domain.customer WHERE customer_id=%s',[key]),[(3,)])
        self.assertTrue(apply_change(self.con,'domain.customer',key,'2025-04-01Z',dict(attrs,segment='premium'),deleted=True))
        self.assertEqual(self.rows('SELECT * FROM domain.v_customer WHERE customer_id=%s',[key]),[])

    def test_search_and_content_joinback(self):
        self.assertEqual(self.rows("SELECT entity_id FROM search.nearest(search.embed('savings'),1)"),[(1,)])
        self.con.execute("UPDATE domain.product SET description='Authoritative change' WHERE product_id=1")
        self.assertEqual(self.rows('SELECT description FROM search.searchable WHERE entity_id=1'),[('Authoritative change',)])
        self.rejects('UPDATE search.entity_embedding SET embedding=ARRAY[1.0,2.0]')
        self.assertEqual(self.rows('SELECT * FROM search.nearest(ARRAY[0.0,0.0,0.0]::float8[],3)'),[])

    def test_prediction_cutoff(self):
        self.assertEqual(self.rows("SELECT count(*) FROM prediction.training_at('2025-01-15Z')"),[(0,)])
        self.assertEqual(self.rows("SELECT count(*) FROM prediction.training_at('2025-02-01Z')"),[(2,)])
        attrs = dict(entity_id=1,entity_kind='CUSTOMER',feature_name='spend_intensity',feature_version='1',
                     value_numeric=self.rows("SELECT value_numeric FROM prediction.feature_value WHERE feature_value_id=1 AND is_current")[0][0],
                     observation_dts='2025-03-01Z')
        self.assertFalse(apply_change(self.con,'prediction.feature_value',1,'2025-03-01Z',attrs))
        with self.assertRaises(ValueError):
            apply_change(self.con,'prediction.feature_value',1,'2025-02-15Z',dict(attrs,observation_dts='2025-02-15Z'))

    def test_validation_error_savepoint_and_expiry(self):
        checks = [Check('ERROR','MODULE','domain','SELECT * FROM no_such_schema.no_such_table'),
                  Check('PASS','MODULE','semantic','SELECT 1 WHERE false')]
        results = validate(self.con,checks)
        self.assertEqual([r['status'] for r in results],['ERROR','PASSED'])
        self.assertEqual(self.rows("SELECT confidence FROM observability.trust_map WHERE scope_id='domain'"),[('weak',)])
        self.con.execute("UPDATE observability.validation_run SET evidence_expires_dts=current_timestamp-interval '1 day'")
        self.assertEqual(self.rows("SELECT DISTINCT confidence FROM observability.trust_map"),[('unknown',)])

    def test_reader_views_and_base_table_denial(self):
        self.con.execute('SET LOCAL ROLE customer360_role_read')
        self.assertEqual(self.rows('SELECT count(*) FROM semantic.data_product_manifest'),[(1,)])
        self.assertEqual(self.rows('SELECT count(*) FROM domain.v_customer'),[(2,)])
        self.assertEqual(len(self.rows("SELECT * FROM search.nearest(search.embed('savings'),1)")),1)
        self.rejects('SELECT * FROM domain.customer')
        self.rejects('SELECT * FROM memory.agent_session')
        self.rejects("SELECT * FROM domain.at_customer('2025-01-01Z')")
        self.rejects("INSERT INTO observability.agent_outcome SELECT * FROM observability.agent_outcome")

    def test_runtime_authenticated_scope_and_spoof_denial(self):
        self.con.execute('CREATE ROLE c360_test_alice LOGIN')
        self.con.execute('GRANT customer360_role_agent TO c360_test_alice')
        self.con.execute("UPDATE memory.agent_session SET scope_identifier='c360_test_alice'")
        self.con.execute('SET SESSION AUTHORIZATION c360_test_alice')
        try:
            self.assertEqual(self.rows('SELECT count(*) FROM memory.agent_session'),[(1,)])
            self.assertEqual(self.rows('SELECT count(*) FROM memory.agent_interaction'),[(0,)])
            self.rejects("UPDATE memory.agent_session SET scope_identifier='someone_else'")
            self.rejects("UPDATE memory.agent_session SET scope_level='TEAM'")
            self.rejects('DELETE FROM memory.agent_session')
            self.rejects('UPDATE observability.agent_outcome SET records_processed=999')
        finally:
            self.con.execute('RESET SESSION AUTHORIZATION')

    def test_cookbook_and_demo(self):
        for (sql,) in self.rows('SELECT query_template FROM memory.v_query_cookbook'):
            self.con.execute(sql).fetchall()
        self.con.execute((ROOT.parents[1]/'examples/customer360-postgres/agent_demo.sql').read_text())


if __name__ == '__main__':
    unittest.main()
