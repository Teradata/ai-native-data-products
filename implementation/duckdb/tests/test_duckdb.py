"""Native persistent-file tests, including mutation and consumer behaviour."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
EXAMPLE = REPO / "examples/customer360-duckdb"
sys.path.insert(0, str(ROOT))
import duckdb
from checks import Check, profile
from model import ENTITIES
from render import render_all
from temporal import apply_change, allocate_key
from validate import validate, summarize, append


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEMO = load_file("customer360_agent", EXAMPLE / "agent_demo.py")
BUILD = load_file("customer360_build", EXAMPLE / "build.py")


class ProductCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "customer360.duckdb"
        self.con = duckdb.connect(str(self.path))
        self.addCleanup(self.con.close)
        self.con.execute((EXAMPLE / "build.sql").read_text(encoding="utf-8"))

    def rows(self, query, values=None):
        return self.con.execute(query, values or []).fetchall()

    def check(self, test_id):
        check = next(c for c in profile() if c.test_id==test_id)
        return self.rows(check.sql)

    def test_complete_profile_and_published_evidence(self):
        result = validate(self.con)
        self.assertGreater(len(result), 500)
        self.assertEqual([r for r in result if r["status"]!="PASSED"], [])
        areas = self.rows("SELECT scope_id,confidence FROM observability.trust_map")
        for module in ("domain","semantic","memory","prediction","search","observability"):
            self.assertIn((module,"strong"), areas)
        self.assertIn(("access-layer","unknown"), areas)
        self.assertEqual(self.check("C360-VAL-001"), [])
        self.assertEqual(self.check("C360-VAL-002"), [])

    def test_all_tables_and_modules(self):
        self.assertEqual(len(self.rows("SELECT * FROM semantic.entity_metadata")), len(ENTITIES))
        self.assertEqual(len(self.rows("SELECT * FROM semantic.data_product_map")), 6)
        self.assertEqual(self.rows("SELECT count(*) FROM semantic.column_catalogue WHERE table_name='customer' AND NOT documentation_covered"), [(0,)])

    def test_current_and_half_open_asof(self):
        self.assertEqual(self.rows("SELECT segment FROM domain.at_customer('2025-01-31 23:59:59.999999+00') WHERE customer_id=1"), [("standard",)])
        self.assertEqual(self.rows("SELECT segment FROM domain.at_customer('2025-02-01 00:00:00+00') WHERE customer_id=1"), [("premium",)])
        self.assertEqual(self.rows("SELECT customer_id FROM domain.v_customer ORDER BY customer_id"), [(1,), (2,)])
        cols = [r[0] for r in self.rows("DESCRIBE domain.v_customer")]
        self.assertNotIn("is_deleted", cols)
        self.assertNotIn("updated_dts", cols)

    def test_temporal_replay_late_change_delete_restore(self):
        attrs = dict(customer_key="C002", display_name="Sam Synthetic", segment="standard")
        self.assertFalse(apply_change(self.con,"domain.customer",2,"2025-03-01 00:00:00+00",attrs))
        changed = dict(attrs, segment="premium")
        self.assertTrue(apply_change(self.con,"domain.customer",2,"2025-03-01 00:00:00+00",changed))
        self.assertFalse(apply_change(self.con,"domain.customer",2,"2025-03-01 00:00:00+00",changed))
        late = dict(attrs, segment="student")
        self.assertTrue(apply_change(self.con,"domain.customer",2,"2025-02-01 00:00:00+00",late))
        self.assertEqual(self.rows("SELECT segment FROM domain.at_customer('2025-02-15 00:00:00+00') WHERE customer_id=2"), [("student",)])
        self.assertTrue(apply_change(self.con,"domain.customer",2,"2025-04-01 00:00:00+00",changed, deleted=True))
        self.assertEqual(self.rows("SELECT customer_id FROM domain.v_customer WHERE customer_id=2"), [])
        self.assertTrue(apply_change(self.con,"domain.customer",2,"2025-05-01 00:00:00+00",changed))
        self.assertEqual(self.rows("SELECT customer_id FROM domain.v_customer WHERE customer_id=2"), [(2,)])
        self.assertEqual(self.check("C360-TLM-OVERLAP-001"), [])
        self.assertEqual(self.rows("SELECT count(*) FROM observability.change_event WHERE changed_by='temporal-writer'"),[(4,)])

    def test_typed_timestamp_replay_and_invalid_instants(self):
        attrs = dict(transaction_key="T001",account_id=1,amount=10,posted_dts="2025-01-04 00:00:00+00")
        self.assertFalse(apply_change(self.con,"domain.transaction",1,"2025-04-01 00:00:00+00",attrs))
        with self.assertRaises(ValueError):
            apply_change(self.con,"domain.transaction",1,"infinity",attrs)

    def test_boundary_conflict_rolls_back_and_keys_are_stable(self):
        before = self.rows("SELECT * FROM domain.customer ORDER BY customer_id,valid_from_dts")
        with self.assertRaises(ValueError):
            apply_change(self.con,"domain.customer",1,"2025-02-01 00:00:00+00",dict(customer_key="C001",display_name="Wrong",segment="wrong"))
        self.assertEqual(before, self.rows("SELECT * FROM domain.customer ORDER BY customer_id,valid_from_dts"))
        self.assertEqual(allocate_key(self.con,"customer","C001"),1)
        self.assertEqual(allocate_key(self.con,"customer","C004"),4)
        self.assertEqual(allocate_key(self.con,"customer","C004"),4)
        with self.assertRaises(ValueError):
            apply_change(self.con,"domain.customer",4,"2025-05-01 00:00:00+00",dict(customer_key="OTHER",display_name="Wrong",segment="standard"))

    def test_overlap_mutation_is_detected(self):
        self.con.execute("UPDATE domain.customer SET valid_to_dts='2025-02-10 00:00:00+00' WHERE customer_id=1 AND NOT is_current")
        self.assertTrue(self.check("C360-TLM-OVERLAP-001"))

    def test_search_native_persistence_and_join_back(self):
        result = self.rows("SELECT entity_id,similarity FROM search.nearest(search.embed('savings'),2)")
        self.assertEqual(result[0][0],1)
        self.assertAlmostEqual(result[0][1],1.0,places=5)
        self.con.execute("UPDATE domain.product SET product_name='Changed upstream' WHERE product_id=1")
        self.assertEqual(self.rows("SELECT product_name FROM search.searchable WHERE entity_id=1"), [("Changed upstream",)])
        self.assertEqual(self.rows("SELECT count(*) FROM duckdb_extensions() WHERE extension_name='vss' AND loaded"), [(0,)])

    def test_prediction_cutoff_and_computation(self):
        self.assertEqual(self.rows("SELECT count(*) FROM prediction.training_at('2025-01-15 00:00:00+00')"), [(0,)])
        feb = self.rows("SELECT entity_id,value_numeric FROM prediction.training_at('2025-02-15 00:00:00+00') ORDER BY entity_id")
        self.assertAlmostEqual(float(feb[0][1]),.37)
        self.assertAlmostEqual(float(feb[1][1]),.18)
        self.assertEqual(self.check("C360-PRED-002"), [])
        self.con.execute("UPDATE prediction.model_prediction SET feature_observation_dts='2026-01-01 00:00:00+00' WHERE is_current")
        self.assertTrue(self.check("C360-PRED-002"))

    def test_metadata_mutations_fail(self):
        self.con.execute("DELETE FROM semantic.column_metadata WHERE table_name='customer' AND column_name='segment'")
        self.assertTrue(self.check("C360-META-001"))
        self.con.execute("DELETE FROM semantic.table_relationship WHERE source_entity='domain.account' AND target_entity='domain.customer'")
        self.assertTrue(self.check("C360-REL-004"))
        self.con.execute("UPDATE semantic.access_object SET object_identity='domain.missing' WHERE object_identity='domain.v_customer'")
        self.assertTrue(self.check("C360-SEM-007"))

    def test_content_duplication_mutation_fails(self):
        self.con.execute("ALTER TABLE search.entity_embedding ADD COLUMN copied_customer_name VARCHAR")
        self.assertTrue(next(self.rows(c.sql) for c in profile() if c.test_id.startswith("C360-BOUNDARY") and c.scope_id=="search"))

    def test_all_cookbook_and_agent_queries_execute(self):
        for (query,) in self.rows("SELECT query_template FROM memory.v_query_cookbook"):
            self.con.execute(query).fetchall()
        self.con.execute((EXAMPLE / "agent_demo.sql").read_text())
        result = DEMO.discover(self.con)
        self.assertEqual(result["path"]["hops"],2)
        self.assertTrue(result["result"][0][0]>0)
        self.assertEqual(result["confidence"][0]["confidence"],"unknown")
        self.assertNotIn("domain.customer ",result["sql"])

    def test_cli_conformance_and_all_asof_macros(self):
        sql = (ROOT / "patterns/validation/conformance.sql").read_text(encoding="utf-8")
        for statement in self.con.extract_statements(sql):
            self.assertEqual(self.con.execute(statement).fetchone()[1],0)
        for e in ENTITIES:
            if e.history:
                self.con.execute(f"SELECT * FROM {e.schema}.at_{e.name}('2025-03-01 00:00:00+00')").fetchall()

    def test_active_lineage_and_runtime_privacy_metadata(self):
        self.assertEqual(len(self.rows("SELECT * FROM semantic.lineage_graph")),6)
        self.con.execute("UPDATE observability.data_lineage SET is_active=false,retired_dts=current_timestamp WHERE lineage_id=1")
        self.assertEqual(len(self.rows("SELECT * FROM semantic.lineage_graph")),4)
        self.assertEqual(self.rows("SELECT count(*) FROM semantic.access_object WHERE represents_entity='memory.agent_session' AND is_agent_consumable"),[(0,)])
        with self.assertRaises(duckdb.ConstraintException):
            self.con.execute("UPDATE memory.agent_session SET scope_identifier=NULL")

    def test_append_failures_errors_and_warning_severity(self):
        results = validate(self.con, [Check("C360-TEST-FAIL","MODULE","domain","SELECT 1"),
                                    Check("C360-TEST-ERROR","MODULE","search","SELECT * FROM missing")])
        self.assertEqual([r["status"] for r in results],["FAILED","ERROR"])
        self.assertEqual(self.rows("SELECT trust_status,failed_count,error_count FROM observability.validation_run"),[("UNTRUSTED",1,1)])
        validate(self.con,[Check("C360-TEST-WARN","MODULE","domain","SELECT 1",severity="WARNING")])
        self.assertEqual(self.rows("SELECT confidence FROM observability.trust_map WHERE scope_id='domain'"),[("partial",)])
        self.assertEqual(self.rows("SELECT count(*) FROM observability.validation_run"),[(2,)])

    def test_latest_per_area_and_staleness(self):
        validate(self.con,[Check("C360-TEST-A","MODULE","domain","SELECT 1 WHERE false")],run_id="first")
        self.con.execute("UPDATE observability.validation_run SET evidence_expires_dts=current_timestamp-INTERVAL '1 day' WHERE run_id='first'")
        validate(self.con,[Check("C360-TEST-B","MODULE","search","SELECT 1 WHERE false")],run_id="second")
        self.assertEqual(self.rows("SELECT confidence FROM observability.trust_map WHERE scope_id='domain'"),[("unknown",)])
        self.assertEqual(self.rows("SELECT confidence FROM observability.trust_map WHERE scope_id='search'"),[("strong",)])

    def test_designated_producer_and_cautious_fallback(self):
        validate(self.con,[Check("C360-TEST-A","MODULE","domain","SELECT 1 WHERE false")],run_id="ours")
        validate(self.con,[Check("C360-TEST-B","MODULE","domain","SELECT 1")],run_id="other")
        self.con.execute("UPDATE observability.validation_area SET producer_id='other-producer' WHERE run_id='other'")
        self.con.execute("UPDATE observability.validation_run SET producer_id='other-producer' WHERE run_id='other'")
        self.assertEqual(self.rows("SELECT confidence FROM observability.trust_map WHERE scope_id='domain'"),[("strong",)])
        self.con.execute("UPDATE semantic.data_product_registry SET trust_authoritative_producer=''")
        self.assertEqual(self.rows("SELECT confidence FROM observability.trust_map WHERE scope_id='domain'"),[("weak",)])
        self.assertIn("cautious", self.rows("SELECT recommended_action FROM observability.trust_map WHERE scope_id='domain'")[0][0])

    def test_shared_trust_fixture_producer_and_sql_consumer(self):
        cases = json.loads((ROOT / "tests/trust_cases.json").read_text())
        now = datetime.now(timezone.utc)
        for i, case in enumerate(cases):
            results = [dict(status=s,severity=v) for s,v in case["outcomes"]]
            summary = summarize(case["expected"],results)
            self.assertEqual((summary["area_status"],summary["confidence"]),(case["area_status"],case["confidence"]))
            # Use actual writer to establish a run, then publish fixture coverage.
            run = "fixture-"+str(i)
            validate(self.con,[],run_id=run)
            append(self.con,"validation_area",dict(product_prefix="customer360",producer_id="duckdb-reference",run_id=run,
                   area_id=run+":MODULE:domain",payload_schema_version="2.1",scope_kind="MODULE",scope_id="domain",**summary,
                   open_gaps=None if summary["confidence"]=="strong" else "fixture gap",
                   recommended_action=None if summary["confidence"]=="strong" else "rerun",completed_dts=now+timedelta(seconds=i)),now)
            self.assertEqual(self.rows("SELECT area_status,confidence FROM observability.trust_map WHERE scope_id='domain'"),[(case["area_status"],case["confidence"])])

    def test_close_reopen_and_read_only(self):
        self.con.close()
        self.con = duckdb.connect(str(self.path),read_only=True)
        self.addCleanup(self.con.close)
        self.assertEqual(self.rows("SELECT count(*) FROM search.nearest(search.embed('credit'),2)"),[(2,)])
        with self.assertRaises(duckdb.InvalidInputException):
            self.con.execute("DELETE FROM domain.customer")

    def test_rebuild_protects_existing_file(self):
        self.con.close()
        with self.assertRaises(FileExistsError):
            BUILD.build(self.path)
        BUILD.build(self.path,replace=True)
        with duckdb.connect(str(self.path),read_only=True) as reopened:
            self.assertEqual(reopened.execute("SELECT count(*) FROM domain.customer").fetchone()[0],5)


class SourceCase(unittest.TestCase):
    def test_generated_sql_is_current(self):
        for path, expected in render_all().items():
            self.assertEqual(path.read_text(encoding="utf-8"),expected,str(path))

    def test_no_optional_index_requirement(self):
        sql = (EXAMPLE / "build.sql").read_text(encoding="utf-8").lower()
        self.assertNotIn("install vss",sql)
        self.assertNotIn("hnsw_enable_experimental_persistence",sql)


if __name__ == "__main__":
    unittest.main()
