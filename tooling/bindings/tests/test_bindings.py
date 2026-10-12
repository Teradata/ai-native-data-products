"""Contract and engine tests for the Jinja bindings, driven by build contexts.

Every binding that declares its phases is rendered from the same design specifications and
the example organisation's profile for that platform, so one specification is shown to build
on every platform. DuckDB tests need the duckdb driver. PostgreSQL tests need
POSTGRES_TEST_DSN naming a disposable database where the test role may create roles and
schemas; every PostgreSQL test runs in one transaction that is rolled back, so nothing is left
behind and no existing object is dropped. A skipped engine is a gap, never a pass.

Run:
    python -m unittest discover -s tooling/bindings/tests -v
"""
import copy
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tooling" / "bindings"))
sys.path.insert(0, str(REPO / "tooling" / "build"))

import build_context  # noqa: E402
from binding import load_binding  # noqa: E402
from jinja2 import UndefinedError  # noqa: E402
from render import RenderError, environment, render_context, render_product  # noqa: E402
from validate import publish, run_checks, summarize, validate  # noqa: E402

PLATFORMS = tuple(p.name for p in sorted((REPO / "implementation").iterdir())
                  if (p / "PLATFORM_PROFILE.md").exists() and load_binding(p.name)[0].phases)
EXAMPLE = REPO / "examples" / "it-service-desk-data-product"
ITSD = EXAMPLE / "design-output" / "design_specification.md"
CUSTORD = REPO / "tooling" / "evals" / "reference" / "customer-orders.md"
TRUST_CASES = json.loads((Path(__file__).parent / "trust_cases.json").read_text(encoding="utf-8"))


def profile(platform):
    return EXAMPLE / "profiles" / f"{platform}.md"


@lru_cache(maxsize=None)
def _resolved(spec, platform):
    ctx, findings = build_context.resolve(Path(spec), profile(platform))
    assert not findings, [str(f) for f in findings]
    return json.dumps(ctx)


def context(spec, platform):
    """A fresh copy of the resolved build context, safe to modify."""
    return json.loads(_resolved(str(spec), platform))


def named(ctx, name):
    return next(x for x in ctx["entities"] + ctx["relations"] if x["name"] == name)


class Rendering(unittest.TestCase):
    def test_every_binding_renders_every_reference_specification(self):
        for platform in PLATFORMS:
            for spec in (ITSD, CUSTORD):
                with self.subTest(platform=platform, spec=spec.name):
                    files = render_context(context(spec, platform))
                    manifest = json.loads(files["manifest.json"])
                    self.assertIn("deploy.sql", files)
                    self.assertTrue(manifest["checks"])
                    self.assertTrue(all(c["test_id"].startswith(manifest["product"]["code"] + "-")
                                        for c in manifest["checks"]))

    def test_names_come_from_the_specification_and_profile(self):
        """Another product, or another organisation's naming, changes every name and no template."""
        for platform in PLATFORMS:
            itsd = render_context(context(ITSD, platform))["deploy.sql"]
            other = render_context(context(CUSTORD, platform))["deploy.sql"]
            self.assertIn('"itsd_domain"', itsd)
            self.assertIn('"custord_domain"', other)
            self.assertNotIn('"itsd_', other)
            with tempfile.TemporaryDirectory() as tmp:
                renamed = Path(tmp) / f"{platform}.md"
                renamed.write_text(profile(platform).read_text(encoding="utf-8")
                                   .replace("{product_code|lower}_{module}", "dp_{product_code|lower}_{module}")
                                   .replace("-> itsd_domain.", "-> dp_itsd_domain.")
                                   .replace("-> itsd_semantic.", "-> dp_itsd_semantic."), encoding="utf-8")
                ctx, findings = build_context.resolve(ITSD, renamed)
                self.assertEqual([str(f) for f in findings], [])
                self.assertIn('"dp_itsd_domain"', render_context(ctx)["deploy.sql"])

    def test_a_platform_without_principals_refuses_to_create_them(self):
        unsupported = [p for p in PLATFORMS if load_binding(p)[0].principals == "unsupported"]
        for platform in unsupported:
            with tempfile.TemporaryDirectory() as tmp:
                bad = Path(tmp) / f"{platform}.md"
                bad.write_text(profile(platform).read_text(encoding="utf-8").replace(
                    "ROLE_READ:   outside read-only file access to the database",
                    "ROLE_READ:   create {product_code|lower}_reader"), encoding="utf-8")
                _, findings = build_context.resolve(ITSD, bad)
                self.assertIn("unsupported-principal", {f.rule for f in findings})

    def test_templates_are_strict(self):
        for platform in PLATFORMS:
            ctx = context(ITSD, platform)
            env = environment(load_binding(platform)[0], ctx)
            with self.assertRaises(UndefinedError):
                env.from_string("{{ product.no_such_field }}").render(**ctx)

    def test_caller_templates_quote_their_values(self):
        for platform in PLATFORMS:
            ctx = context(ITSD, platform)
            env = environment(load_binding(platform)[0], ctx)
            sql = env.get_template("modules/domain/02-key-allocation.sql.j2").render(
                **dict(ctx, keymap=named(ctx, "TicketKeymap"), natural_value="T-1'; DROP"))
            self.assertIn("'T-1''; DROP'", sql)
            ticket = named(ctx, "Ticket")
            row = {c["physical_name"]: None for c in ticket["columns"]}
            sql = env.get_template("patterns/temporal-lifecycle-metadata/04-maintenance.sql.j2").render(
                **dict(ctx, entity=ticket, stable_key=1, effective_at="2026-01-01", recorded_at="2026-02-01",
                       replacement_rows=[row]))
            self.assertIn("INSERT INTO", sql)

    def test_gaps_are_reported_not_hidden(self):
        for platform in PLATFORMS:
            gaps = json.loads(render_context(context(ITSD, platform))["manifest.json"])["gaps"]
            self.assertTrue(any("as_of" in g for g in gaps), gaps)
            self.assertTrue(any("TicketDetail" in g for g in gaps), gaps)

    def test_cli_refuses_reserved_and_existing_output(self):
        cmd = [sys.executable, str(REPO / "tooling" / "bindings" / "render.py"), str(ITSD), str(profile(PLATFORMS[0]))]
        reserved = subprocess.run(cmd + ["--output", str(REPO / "implementation" / "x")], capture_output=True)
        self.assertNotEqual(reserved.returncode, 0)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "keep.txt").write_text("existing")
            existing = subprocess.run(cmd + ["--output", tmp], capture_output=True)
            self.assertNotEqual(existing.returncode, 0)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["keep.txt"])

    def test_an_invalid_specification_renders_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.md"
            bad.write_text(ITSD.read_text(encoding="utf-8").replace("  Module:     memory\n", "  Module:     access-layer\n", 1),
                           encoding="utf-8")
            with self.assertRaises(RenderError):
                render_product(bad, profile(PLATFORMS[0]))

    def test_shared_trust_cases(self):
        for case in TRUST_CASES:
            summary = summarize(case["expected"], [dict(status=s, severity=v) for s, v in case["outcomes"]])
            self.assertEqual((summary["area_status"], summary["confidence"]),
                             (case["area_status"], case["confidence"]), case["name"])


class _Statement:
    """No savepoint: DuckDB statements fail atomically on their own."""
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _value(raw, logical):
    if raw in (None, ""):
        return None
    if logical == "Flag":
        return raw.lower() == "true"
    if logical == "Integer":
        return int(raw)
    if logical == "Timestamp":
        return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    if logical == "Date":
        return date.fromisoformat(raw)
    return raw


class EngineTests:
    """Behaviour every binding must show on its engine, from the same contexts."""
    platform = None

    # ---- harness ---------------------------------------------------------------------
    def deploy(self, spec=ITSD, ctx=None):
        self.ctx = ctx or context(spec, self.platform)
        self.binding = load_binding(self.platform)[0]
        self.files = render_context(self.ctx)
        self.manifest = json.loads(self.files["manifest.json"])
        self.apply(self.files)
        return self.manifest

    def q(self, sql, params=None):
        return self.con.execute(sql, params or []).fetchall()

    @property
    def marker(self):
        return "%s" if self.platform == "postgres" else "?"

    def table(self, name):
        t = named(self.ctx, name)["objects"]["table"]
        return self.binding.qualified(t["container"], t["name"])

    def view(self, name):
        v = named(self.ctx, name)["objects"]["consumer_view"]
        return self.binding.qualified(v["container"], v["name"])

    def insert(self, name, values, returning=None):
        x = named(self.ctx, name)
        cn = x["column_names"]
        cols = ", ".join(self.binding.ident(cn[k]) for k in values)
        sql = f"INSERT INTO {self.table(name)} ({cols}) VALUES ({', '.join(self.marker for _ in values)})"
        if returning:
            sql += " RETURNING " + self.binding.ident(cn[returning])
        cur = self.con.execute(sql, list(values.values()))
        return cur.fetchone()[0] if returning else None

    def allocate(self, keymap, natural):
        env = environment(self.binding, self.ctx)
        sql = env.get_template("modules/domain/02-key-allocation.sql.j2").render(
            **dict(self.ctx, keymap=named(self.ctx, keymap), natural_value=natural))
        return self.con.execute(sql).fetchone()[0]

    def temporal(self, x, valid_from):
        out = {}
        names = {c["name"] for c in x["columns"]}
        now = datetime.now(timezone.utc)
        for col, value in (("created_dts", now), ("updated_dts", now), ("valid_from_dts", valid_from),
                           ("valid_to_dts", "infinity"), ("transaction_from_dts", datetime(2026, 7, 1, tzinfo=timezone.utc)),
                           ("transaction_to_dts", "infinity"), ("is_current", True), ("is_deleted", False)):
            if col in names:
                out[col] = value
        return out

    def load_itsd(self):
        """Test-only loading of the four ITSD source files, through the binding's own key
        allocation. Not a product loader."""
        def rows(file):
            with (EXAMPLE / "data" / f"{file}.csv").open(encoding="utf-8", newline="") as f:
                return list(csv.DictReader(f))
        keys = {"category": {}, "agent": {}, "customer": {}}
        renames = {"Ticket": {"opened_dts": "created_at", "first_response_dts": "first_response_at",
                              "resolved_dts": "resolved_at", "closed_dts": "closed_at"}}
        refs = {"customer_id": "customer", "assigned_agent_id": "agent", "category_id": "category",
                "parent_category_id": "category"}
        for entity, file, keymap in (("Category", "categories", None), ("Agent", "agents", "AgentKeymap"),
                                     ("Customer", "customers", "CustomerKeymap"), ("Ticket", "tickets", "TicketKeymap")):
            x = named(self.ctx, entity)
            source_key = f"{entity.lower()}_id"
            for row in rows(file):
                values = {}
                for col in x["columns"]:
                    if col["origin"] != "attribute" or col["name"] in x["surrogate_columns"]:
                        continue
                    if col["name"] == "category_code":
                        values[col["name"]] = row["category_id"]
                        continue
                    raw = row.get(renames.get(entity, {}).get(col["name"], col["name"]))
                    if col["name"] in refs and col["name"] != x["surrogate_columns"][0]:
                        values[col["name"]] = keys[refs[col["name"]]].get(raw) if raw else None
                    elif raw is not None:
                        values[col["name"]] = _value(raw, col["type"].split("{")[0])
                values.update(self.temporal(x, values.get("opened_dts") or datetime(2020, 1, 1, tzinfo=timezone.utc)))
                if keymap:
                    key = self.allocate(keymap, row[source_key])
                    values[x["surrogate_columns"][0]] = key
                    self.insert(entity, values)
                else:
                    key = self.insert(entity, values, returning=x["surrogate_columns"][0])
                if entity != "Ticket":
                    keys[entity.lower()][row[source_key]] = key

    def check(self, check, scope_id):
        c = next(c for c in self.manifest["checks"] if c["check"] == check and c["scope_id"] == scope_id)
        return self.q(c["sql"])

    def area(self, run_id, producer, scope, summary, completed, gap=None):
        """Test-only: publish one area record the way a producer would."""
        self.insert("ValidationArea", dict(
            product_code=self.ctx["product"]["code"], producer_id=producer, run_id=run_id, scope_kind="MODULE",
            scope_id=scope, **summary, open_gaps=gap, recommended_action=None if gap is None else "rerun",
            completed_dts=completed, created_dts=completed, updated_dts=completed))

    def trust(self, scope):
        return self.q(f"SELECT area_status, confidence FROM {self.view('TrustMap')} WHERE scope_id = {self.marker}", [scope])

    # ---- behaviour -------------------------------------------------------------------
    def test_itsd_deploys_and_every_check_passes(self):
        self.deploy()
        failing = [r for r in run_checks(self.con, self.manifest) if r["status"] != "PASSED"]
        self.assertEqual(failing, [])

    def test_an_unrelated_product_deploys_and_every_check_passes(self):
        self.deploy(CUSTORD)
        failing = [r for r in run_checks(self.con, self.manifest) if r["status"] != "PASSED"]
        self.assertEqual(failing, [])

    def test_itsd_source_rows_load_and_stay_conformant(self):
        self.deploy()
        self.load_itsd()
        for entity, count in (("Ticket", 150), ("Agent", 12), ("Customer", 20), ("Category", 15)):
            self.assertEqual(self.q(f"SELECT count(*) FROM {self.view(entity)}")[0][0], count)
        failing = [r for r in run_checks(self.con, self.manifest) if r["status"] != "PASSED"]
        self.assertEqual(failing, [])

    def test_metrics_and_cookbook_recipes_execute(self):
        self.deploy()
        self.load_itsd()
        recipe = named(self.ctx, "QueryCookbook")
        cn = recipe["column_names"]
        recipes = self.q(f"SELECT {self.binding.ident(cn['recipe_id'])}, {self.binding.ident(cn['query_template'])} "
                         f"FROM {self.view('QueryCookbook')}")
        self.assertTrue(recipes)
        for recipe_id, sql in recipes:
            if "$1" in sql:
                continue  # a parameterised recipe; the similarity test runs one
            with self.subTest(recipe=recipe_id):
                self.q(sql)
        opened = self.q(next(sql for rid, sql in recipes if rid == "QC-DOMAIN-001"))[0][0]
        self.assertEqual(opened, 150)

    def test_similarity_ranks_current_vectors_of_its_embedding(self):
        self.deploy()
        self.load_itsd()
        embedding = self.ctx["embeddings"][0]
        dims = int(embedding["dimensions"])
        tickets = [r[0] for r in self.q(f"SELECT {self.binding.ident(named(self.ctx, 'Ticket')['key_columns'][0])} "
                                         f"FROM {self.view('Ticket')} ORDER BY 1 LIMIT 2")]
        x = named(self.ctx, embedding["store"])
        for ticket, first in zip(tickets, (1.0, 0.0)):
            vector = [first] + [0.0] * (dims - 2) + [1.0 - first]
            self.insert(x["name"], dict(entity_id=ticket, entity_kind="TICKET", source_attribute=embedding["name"],
                                        embedding=vector, embedding_dimensions=dims, embedding_model="test-encoder",
                                        generated_dts=datetime.now(timezone.utc),
                                        **self.temporal(x, datetime(2026, 1, 1, tzinfo=timezone.utc))))
        fn = embedding["objects"]["function"]
        query = [1.0] + [0.0] * (dims - 1)
        rows = self.q(f"SELECT entity_id, similarity FROM {self.binding.qualified(fn['container'], fn['name'])}"
                      f"({self.marker}, 5)", [query])
        self.assertEqual(rows[0][0], tickets[0])
        self.assertAlmostEqual(float(rows[0][1]), 1.0, places=5)
        self.assertEqual(len(rows), 1)  # the orthogonal vector is below the declared threshold

    def current_row(self, name, key_value):
        """The current version of one identity, by physical column name, finite columns only."""
        x = named(self.ctx, name)
        cols = [c["physical_name"] for c in x["columns"]
                if c["origin"] == "attribute" or c["name"] in ("valid_from_dts", "created_dts")]
        key = self.binding.ident(x["version_columns"][0])
        row = self.q(f"SELECT {', '.join(self.binding.ident(c) for c in cols)} FROM {self.view(name)} "
                     f"WHERE {key} = {self.marker}", [key_value])[0]
        return x, dict(zip(cols, row))

    def test_bitemporal_maintenance_keeps_known_history(self):
        self.deploy()
        self.load_itsd()
        ticket, before = self.current_row("Ticket", 1)
        cn, key = ticket["column_names"], self.binding.ident(ticket["version_columns"][0])
        row = dict(before)
        row.update({cn["priority"]: "P1", cn["valid_to_dts"]: "infinity",
                    cn["transaction_from_dts"]: "2026-08-01T00:00:00+00:00", cn["transaction_to_dts"]: "infinity",
                    cn["is_current"]: True, cn["is_deleted"]: False, cn["deleted_dts"]: None,
                    cn["updated_dts"]: "2026-08-01T00:00:00+00:00"})
        row = {k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in row.items()}
        env = environment(self.binding, self.ctx)
        sql = env.get_template("patterns/temporal-lifecycle-metadata/04-maintenance.sql.j2").render(
            **dict(self.ctx, entity=ticket, stable_key=1, effective_at=None,
                   recorded_at="2026-08-01T00:00:00+00:00", replacement_rows=[row]))
        for statement in [s for s in sql.split(";") if s.strip()]:
            self.con.execute(statement)
        fn = ticket["objects"]["function"]
        at = self.binding.qualified(fn["container"], fn["name"])
        prio = self.binding.ident(cn["priority"])
        self.assertEqual(self.q(f"SELECT {prio} FROM {at}('2026-07-10'::TIMESTAMPTZ, '2026-07-20'::TIMESTAMPTZ) "
                                f"WHERE {key} = 1"), [(before[cn["priority"]],)])
        self.assertEqual(self.q(f"SELECT {prio} FROM {at}('2026-07-10'::TIMESTAMPTZ, '2026-08-20'::TIMESTAMPTZ) "
                                f"WHERE {key} = 1"), [("P1",)])
        self.assertEqual(self.q(f"SELECT {prio} FROM {self.view('Ticket')} WHERE {key} = 1"), [("P1",)])
        self.assertEqual(self.check("temporal", "Ticket"), [])

    def test_key_allocation_is_permanent_and_idempotent(self):
        self.deploy()
        first = self.allocate("TicketKeymap", "SRC-1")
        self.assertEqual(self.allocate("TicketKeymap", "SRC-1"), first)
        self.assertNotEqual(self.allocate("TicketKeymap", "SRC-2"), first)

    def savepoint(self):
        return self.con.transaction() if self.platform == "postgres" else _Statement()

    def test_mutations_are_detected(self):
        self.deploy()
        self.load_itsd()
        ticket, before = self.current_row("Ticket", 1)
        cn = ticket["column_names"]
        t = ticket["objects"]["table"]
        self.assertEqual(self.check("metadata", "Ticket"), [])
        self.con.execute(f"COMMENT ON COLUMN {self.binding.qualified(t['container'], t['name'])}."
                         f"{self.binding.ident(cn['subject'])} IS NULL")
        self.assertTrue(self.check("metadata", "Ticket"))
        # A second open version of the same identity: an engine that can refuse it does; one
        # that cannot must have the temporal check find it. Either way it is not silent.
        overlap = dict(before, **{cn["valid_from_dts"]: datetime(2026, 7, 1, tzinfo=timezone.utc)})
        overlap.update(self.temporal(ticket, overlap[cn["valid_from_dts"]]))
        refused = False
        try:
            with self.savepoint():
                self.insert("Ticket", {c["name"]: overlap[c["physical_name"]] for c in ticket["columns"]
                                       if c["physical_name"] in overlap})
        except Exception:
            refused = True
        if not refused:
            self.assertTrue(self.check("temporal", "Ticket"))
        refs = [c for c in self.manifest["checks"] if c["check"] == "reference" and c["scope_id"] == "Ticket"]
        self.assertTrue(all(self.q(c["sql"]) == [] for c in refs))
        deleted = named(self.ctx, "Customer")["column_names"]
        self.con.execute(f"UPDATE {self.table('Customer')} SET {self.binding.ident(deleted['is_deleted'])} = TRUE, "
                         f"{self.binding.ident(deleted['deleted_dts'])} = current_timestamp")
        self.assertTrue(any(self.q(c["sql"]) for c in refs))

    def test_an_unregistered_table_is_detected(self):
        self.deploy()
        self.assertEqual(self.check("module", "semantic"), [])
        container = named(self.ctx, "Ticket")["objects"]["table"]["container"]
        self.con.execute(f"CREATE TABLE {self.binding.qualified(container, 'stray')} (x INTEGER)")
        self.assertTrue(self.check("module", "semantic"))

    def test_evidence_publishes_and_the_trust_map_reads_it(self):
        self.deploy()
        results = validate(self.con, self.manifest)
        self.assertTrue(all(r["status"] == "PASSED" for r in results))
        self.assertEqual(self.trust("domain"), [("pass", "strong")])
        product = self.trust(self.ctx["product"]["code"])
        self.assertEqual(product, [("partial", "partial")])  # the reported gaps cap it

    def test_errors_and_failures_are_never_successes(self):
        self.deploy()
        checks = [dict(test_id="T-1", check="x", scope_kind="MODULE", scope_id="domain", module="domain",
                       category="STRUCTURAL", severity="ERROR", sql="SELECT 1"),
                  dict(test_id="T-2", check="x", scope_kind="MODULE", scope_id="search", module="search",
                       category="STRUCTURAL", severity="ERROR", sql="SELECT * FROM no_such_table"),
                  dict(test_id="T-3", check="x", scope_kind="MODULE", scope_id="memory", module="memory",
                       category="STRUCTURAL", severity="ERROR", sql="SELECT 1 WHERE 1 = 0")]
        results = validate(self.con, dict(self.manifest, checks=checks))
        self.assertEqual([r["status"] for r in results], ["FAILED", "ERROR", "PASSED"])
        run = named(self.ctx, "ValidationRun")["column_names"]
        self.assertEqual(self.q(f"SELECT {self.binding.ident(run['trust_status'])} FROM {self.table('ValidationRun')}"),
                         [("UNTRUSTED",)])
        self.assertEqual(self.trust("search"), [("fail", "weak")])

    def test_latest_evidence_per_area_and_staleness(self):
        self.deploy()
        producer = self.ctx["product"]["trust_producer"]
        strong = summarize(1, [dict(status="PASSED", severity="ERROR")])
        now = datetime.now(timezone.utc)
        for run_id in ("first", "second"):
            publish(self.con, self.manifest, [], now, producer, run_id)
        self.area("first", producer, "fixture-a", strong, now)
        self.area("second", producer, "fixture-b", strong, now + timedelta(seconds=1))
        self.assertEqual(self.trust("fixture-a") + self.trust("fixture-b"), [("pass", "strong")] * 2)
        run = named(self.ctx, "ValidationRun")["column_names"]
        self.con.execute(f"UPDATE {self.table('ValidationRun')} SET {self.binding.ident(run['evidence_expires_dts'])} = "
                         f"current_timestamp - INTERVAL '1 day' WHERE {self.binding.ident(run['run_id'])} = 'first'")
        self.assertEqual(self.trust("fixture-a"), [("pass", "unknown")])
        self.assertEqual(self.trust("fixture-b"), [("pass", "strong")])

    def test_designated_producer_then_cautious_fallback(self):
        self.deploy()
        producer = self.ctx["product"]["trust_producer"]
        now = datetime.now(timezone.utc)
        good = summarize(1, [dict(status="PASSED", severity="ERROR")])
        bad = summarize(1, [dict(status="FAILED", severity="ERROR")])
        publish(self.con, self.manifest, [], now, producer, "ours")
        publish(self.con, self.manifest, [], now, "other-producer", "other")
        self.area("ours", producer, "fixture-p", good, now)
        self.area("other", "other-producer", "fixture-p", bad, now + timedelta(seconds=1), "other gap")
        self.assertEqual(self.trust("fixture-p"), [("pass", "strong")])
        reg = named(self.ctx, "DataProductRegistry")["column_names"]
        self.con.execute(f"UPDATE {self.table('DataProductRegistry')} SET "
                         f"{self.binding.ident(reg['trust_authoritative_producer'])} = ''")
        self.assertEqual(self.trust("fixture-p"), [("fail", "weak")])

    def test_no_evidence_is_unknown_not_sound(self):
        self.deploy()
        self.assertEqual(self.trust(self.ctx["product"]["code"]), [("no-evidence", "unknown")])


try:
    import duckdb
except ImportError:  # pragma: no cover - reported as a skip, which is a gap
    duckdb = None


@unittest.skipUnless(duckdb and "duckdb" in PLATFORMS, "DuckDB driver not installed: engine coverage is a gap")
class DuckDB(EngineTests, unittest.TestCase):
    platform = "duckdb"

    def setUp(self):
        self.con = duckdb.connect()

    def tearDown(self):
        self.con.close()

    def apply(self, files):
        self.con.execute(files["deploy.sql"])

    def test_a_product_file_reopens_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "itsd.duckdb")
            self.con.close()
            self.con = duckdb.connect(path)
            self.deploy()
            self.con.close()
            self.con = duckdb.connect(path, read_only=True)
            self.assertEqual(self.trust(self.ctx["product"]["code"]), [("no-evidence", "unknown")])
            with self.assertRaises(duckdb.Error):
                self.con.execute(f"DELETE FROM {self.table('DataProductRegistry')}")

    def test_a_fixed_size_vector_rejects_the_wrong_dimension(self):
        self.deploy()
        embedding = self.ctx["embeddings"][0]
        x = named(self.ctx, embedding["store"])
        with self.assertRaises(duckdb.Error):
            self.insert(x["name"], dict(entity_id=1, entity_kind="TICKET", source_attribute=embedding["name"],
                                        embedding=[1.0, 0.0], embedding_dimensions=2, embedding_model="m",
                                        generated_dts=datetime.now(timezone.utc),
                                        **self.temporal(x, datetime(2026, 1, 1, tzinfo=timezone.utc))))


try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None
DSN = os.environ.get("POSTGRES_TEST_DSN")


@unittest.skipUnless(psycopg and DSN and "postgres" in PLATFORMS,
                     "POSTGRES_TEST_DSN or psycopg missing: PostgreSQL engine coverage is a gap")
class PostgreSQL(EngineTests, unittest.TestCase):
    platform = "postgres"

    def setUp(self):
        self.con = psycopg.connect(DSN)
        self.con.execute("SET TimeZone = 'UTC'")

    def tearDown(self):
        self.con.rollback()
        self.con.close()

    def apply(self, files):
        """Every phase in the test's own transaction, so the rollback removes roles too."""
        for name in self.manifest["phases"]:
            self.con.execute(files[name])

    def role(self, tier):
        return self.binding.ident(self.ctx["principals"][tier]["name"])

    def test_the_read_tier_reaches_views_but_not_tables(self):
        self.deploy()
        self.con.execute(f"SET ROLE {self.role('ROLE_READ')}")
        self.q(f"SELECT count(*) FROM {self.view('Ticket')}")
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.con.transaction():
                self.q(f"SELECT count(*) FROM {self.table('Ticket')}")
        fn = named(self.ctx, "Ticket")["objects"]["function"]
        self.q(f"SELECT count(*) FROM {self.binding.qualified(fn['container'], fn['name'])}"
               f"(current_timestamp, current_timestamp)")
        self.con.execute("RESET ROLE")

    def test_runtime_memory_is_scoped_to_the_session_user(self):
        self.deploy()
        session = named(self.ctx, "AgentSession")
        user = self.q("SELECT session_user")[0][0]
        self.con.execute(f"SET ROLE {self.role('ROLE_AGENT')}")
        row = dict(session_key="S-1", agent_key="agent", session_start_dts=datetime.now(timezone.utc),
                   scope_level="USER", scope_identifier=user,
                   **self.temporal(session, datetime.now(timezone.utc)))
        self.insert(session["name"], row)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.con.transaction():
                self.insert(session["name"], dict(row, session_key="S-2", scope_identifier="someone-else"))
        self.con.execute("RESET ROLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
