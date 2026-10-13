"""Contract and engine tests for the Jinja bindings, driven by build contexts.

Every binding that declares its phases is rendered from the same design specifications and
the example organisation's profile for that platform, so one specification is shown to build
on every platform. The engine tests are written once, against the build context, and run on
every engine; what differs between engines is only how a test writes a value (a flag, an open
interval end, a vector) and how it reads history, never what it expects.

DuckDB tests need the duckdb driver. PostgreSQL tests need POSTGRES_TEST_DSN naming a
disposable database where the test role may create roles and schemas; every PostgreSQL test
runs in one transaction that is rolled back, so nothing is left behind and no existing object
is dropped. Teradata tests need teradatasql and TERADATA_TEST_DSN, the connection parameters
as JSON, for a user that may create databases and roles; they deploy each specification once
under containers and roles prefixed `anptest_`, reset its rows between tests, and drop
everything carrying that prefix, and nothing else, before and after. A skipped engine is a
gap, never a pass.

Run:
    python -m unittest discover -s tooling/bindings/tests -v
"""
import copy
import csv
import json
import os
import re
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
from render import RenderError, environment, persisted, render_context, render_product  # noqa: E402
from engines import engine, statements  # noqa: E402
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


def prefixed_containers(text, prefix):
    """A profile whose every created container, and every derivation example, carries a prefix:
    another organisation's naming, written as that organisation would write it."""
    text = text.replace("\r\n", "\n")
    adoption = re.search(r"Adoption: -\n((?:  .*\n)*)", text)
    adopted = set(re.findall(r"^    (\w+): ", adoption.group(1), re.M)) if adoption else set()
    block = re.search(r"Containers: -\n((?:  .*\n)+)", text).group(1)
    lines = []
    for line in block.splitlines():
        key, _, template = line.strip().partition(":")
        lines.append(line if key in adopted else f"  {key}: {prefix}{template.strip()}")
    text = text.replace(block, "\n".join(lines) + "\n")
    return re.sub(r"(-> )([^ .]+\.)", lambda m: m.group(1) + prefix + m.group(2), text)


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
            with self.subTest(platform=platform):
                b = load_binding(platform)[0]
                ours, theirs = context(ITSD, platform), context(CUSTORD, platform)
                itsd, other = render_context(ours)["deploy.sql"], render_context(theirs)["deploy.sql"]
                mine = {c["name"] for c in ours["containers"] if not c["adopted"]}
                for name in mine:
                    self.assertIn(b.ident(name), itsd)
                for name in mine - {c["name"] for c in theirs["containers"]}:
                    self.assertNotIn(b.ident(name), other)
                with tempfile.TemporaryDirectory() as tmp:
                    renamed = Path(tmp) / f"{platform}.md"
                    renamed.write_text(prefixed_containers(profile(platform).read_text(encoding="utf-8"), "dp_"),
                                       encoding="utf-8")
                    ctx, findings = build_context.resolve(ITSD, renamed)
                    self.assertEqual([str(f) for f in findings], [])
                    domain = named(ours, "Ticket")["objects"]["table"]["container"]
                    self.assertEqual(named(ctx, "Ticket")["objects"]["table"]["container"], "dp_" + domain)
                    self.assertIn(b.ident("dp_" + domain), render_context(ctx)["deploy.sql"])

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

    def test_every_binding_takes_the_path_bound_from_the_context(self):
        """Semantic §5 bounds path discovery; no binding fixes its own bound."""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                ctx = context(ITSD, platform)
                env = environment(load_binding(platform)[0], ctx)
                paths = named(ctx, "RelationshipPaths")
                self.assertEqual(paths["max_hops"], build_context.PATH_HOPS)
                template = env.get_template("modules/semantic/03-discovery.sql.j2")
                rendered = []
                for hops in (2, 5):
                    paths["max_hops"] = hops
                    rendered.append(template.render(**ctx))
                self.assertNotEqual(*rendered)

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
    """Behaviour every binding must show on its engine, from the same contexts. An engine
    class says how it writes a flag, an open interval end and a vector, whether its driver
    returns a generated key, and how it reads an entity as at an instant; nothing else."""
    platform = None
    returning = True  # the driver returns a generated key from an INSERT
    open_end = "infinity"

    def flag(self, value):
        return value

    def vector(self, values):
        return values

    def timestamp(self, sql_text):
        return f"CAST('{sql_text}' AS TIMESTAMPTZ)"

    def as_of(self, x, valid_at, known_at):
        """A relation of `x` as it was valid at one instant and known at another."""
        fn = x["objects"]["function"]
        return (f"{self.binding.qualified(fn['container'], fn['name'])}"
                f"({self.timestamp(valid_at)}, {self.timestamp(known_at)})")

    def uncomment(self, table, column):
        self.con.execute(f"COMMENT ON COLUMN {table}.{column} IS NULL")

    def undo(self, sql):
        """Reverse a test's change to the schema, where the engine keeps it after the test."""

    # ---- harness ---------------------------------------------------------------------
    def context(self, spec):
        return context(spec, self.platform)

    def deploy(self, spec=ITSD, ctx=None):
        self.ctx = ctx or self.context(spec)
        self.binding = load_binding(self.platform)[0]
        self.files = render_context(self.ctx)
        self.manifest = json.loads(self.files["manifest.json"])
        self.apply(self.files)
        return self.manifest

    def q(self, sql, params=None):
        return self.con.execute(sql, params or []).fetchall()

    @property
    def marker(self):
        return engine(self.platform).marker

    def first_key(self, name):
        """The lowest stable key with a current row: keys are allocated, never assumed."""
        x = named(self.ctx, name)
        return self.q(f"SELECT MIN({self.binding.ident(x['version_columns'][0])}) FROM {self.view(name)}")[0][0]

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
        if returning and self.returning:
            sql += " RETURNING " + self.binding.ident(cn[returning])
        cur = self.con.execute(sql, list(values.values()))
        if not returning:
            return None
        if self.returning:
            return cur.fetchone()[0]
        return self.q(f"SELECT MAX({self.binding.ident(cn[returning])}) FROM {self.table(name)}")[0][0]

    def allocate(self, keymap, natural):
        env = environment(self.binding, self.ctx)
        sql = env.get_template("modules/domain/02-key-allocation.sql.j2").render(
            **dict(self.ctx, keymap=named(self.ctx, keymap), natural_value=natural))
        *writes, read = statements(sql)
        for statement in writes:
            self.con.execute(statement)
        return self.con.execute(read).fetchone()[0]

    def temporal(self, x, valid_from):
        out = {}
        names = {c["name"] for c in x["columns"]}
        now = datetime.now(timezone.utc)
        for col, value in (("created_dts", now), ("updated_dts", now), ("valid_from_dts", valid_from),
                           ("valid_to_dts", self.open_end), ("transaction_from_dts", datetime(2026, 7, 1, tzinfo=timezone.utc)),
                           ("transaction_to_dts", self.open_end), ("is_current", self.flag(True)),
                           ("is_deleted", self.flag(False))):
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
                        value = _value(raw, col["type"].split("{")[0])
                        values[col["name"]] = self.flag(value) if col["type"] == "Flag" and value is not None else value
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
            if re.search(r"\$1|\?", re.sub(r"'(?:[^']|'')*'", "", sql)):
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
        searchable = {"function", "procedure"} & set(embedding["objects"])
        if not searchable:  # not rendered on this platform: then the build must say so
            self.assertIn(f"embeddings[{embedding['name']}]: the binding emits no similarity search object",
                          self.manifest["gaps"])
            return
        tickets = [r[0] for r in self.q(f"SELECT {self.binding.ident(named(self.ctx, 'Ticket')['key_columns'][0])} "
                                         f"FROM {self.view('Ticket')} ORDER BY 1")][:2]
        x = named(self.ctx, embedding["store"])
        for ticket, first in zip(tickets, (1.0, 0.0)):
            vector = [first] + [0.0] * (dims - 2) + [1.0 - first]
            self.insert(x["name"], dict(entity_id=ticket, entity_kind="TICKET", source_attribute=embedding["name"],
                                        embedding=self.vector(vector), embedding_dimensions=dims,
                                        embedding_model="test-encoder",
                                        generated_dts=datetime.now(timezone.utc),
                                        **self.temporal(x, datetime(2026, 1, 1, tzinfo=timezone.utc))))
        query = [1.0] + [0.0] * (dims - 1)
        rows = self.similar(embedding, self.vector(query), 5)
        self.assertEqual(rows[0][0], tickets[0])
        self.assertAlmostEqual(float(rows[0][1]), 1.0, places=5)
        self.assertEqual(len(rows), 1)  # the orthogonal vector is below the declared threshold

    def similar(self, embedding, query, limit):
        """(entity_id, similarity) rows from the embedding's similarity search object."""
        fn = embedding["objects"]["function"]
        return self.q(f"SELECT entity_id, similarity FROM {self.binding.qualified(fn['container'], fn['name'])}"
                      f"({self.marker}, {limit})", [query])

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
        stable = self.first_key("Ticket")
        ticket, before = self.current_row("Ticket", stable)
        cn, key = ticket["column_names"], self.binding.ident(ticket["version_columns"][0])
        row = dict(before)
        row.update({cn["priority"]: "P1", cn["valid_to_dts"]: "infinity",
                    cn["transaction_from_dts"]: "2026-08-01 00:00:00+00:00", cn["transaction_to_dts"]: "infinity",
                    cn["is_current"]: True, cn["is_deleted"]: False, cn["deleted_dts"]: None,
                    cn["updated_dts"]: "2026-08-01 00:00:00+00:00"})
        row = {k: (str(v) if isinstance(v, (datetime, date)) else v) for k, v in row.items()}
        env = environment(self.binding, self.ctx)
        sql = env.get_template("patterns/temporal-lifecycle-metadata/04-maintenance.sql.j2").render(
            **dict(self.ctx, entity=ticket, stable_key=stable, effective_at=None,
                   recorded_at="2026-08-01 00:00:00+00:00", replacement_rows=[row]))
        for statement in statements(sql):
            self.con.execute(statement)
        prio = self.binding.ident(cn["priority"])
        known_before = self.as_of(ticket, "2026-07-10 00:00:00+00:00", "2026-07-20 00:00:00+00:00")
        known_after = self.as_of(ticket, "2026-07-10 00:00:00+00:00", "2026-08-20 00:00:00+00:00")
        self.assertEqual(self.q(f"SELECT {prio} FROM {known_before} WHERE {key} = {stable}"),
                         [(before[cn["priority"]],)])
        self.assertEqual(self.q(f"SELECT {prio} FROM {known_after} WHERE {key} = {stable}"), [("P1",)])
        self.assertEqual(self.q(f"SELECT {prio} FROM {self.view('Ticket')} WHERE {key} = {stable}"), [("P1",)])
        self.assertEqual(self.check("temporal", "Ticket"), [])

    def test_relationship_paths_follow_the_standard_bound(self):
        """Semantic §5: every path in either direction up to the standard's bound, never
        revisiting a table, so every engine returns the same paths for the same relationships."""
        self.deploy()
        edges = []
        for r in self.ctx["relationships"]:
            if r["source_table"] and r["target_table"]:
                s, t = (f"{x['container']}.{x['name']}" for x in (r["source_table"], r["target_table"]))
                edges += [(s, t), (t, s)]
        expected, frontier = {}, [[e] for e in edges]
        for hops in range(1, named(self.ctx, "RelationshipPaths")["max_hops"] + 1):
            expected[hops] = len(frontier)
            frontier = [path + [e] for path in frontier for e in edges
                        if e[0] == path[-1][1] and e[1] not in [path[0][0]] + [p[1] for p in path]]
        rows = dict(self.q(f"SELECT hops, COUNT(*) FROM {self.view('RelationshipPaths')} GROUP BY hops"))
        self.assertEqual({int(k): int(v) for k, v in rows.items()}, {k: v for k, v in expected.items() if v})

    def test_key_allocation_is_permanent_and_idempotent(self):
        self.deploy()
        first = self.allocate("TicketKeymap", "SRC-1")
        self.assertEqual(self.allocate("TicketKeymap", "SRC-1"), first)
        self.assertNotEqual(self.allocate("TicketKeymap", "SRC-2"), first)

    def test_mutations_are_detected(self):
        self.deploy()
        self.load_itsd()
        ticket, before = self.current_row("Ticket", self.first_key("Ticket"))
        cn = ticket["column_names"]
        table, column = self.table("Ticket"), self.binding.ident(cn["subject"])
        self.assertEqual(self.check("metadata", "Ticket"), [])
        self.uncomment(table, column)
        described = next(c["description"] for c in ticket["columns"] if c["name"] == "subject")
        self.undo(f"COMMENT ON COLUMN {table}.{column} IS {self.binding.literal(described)}")
        self.assertTrue(self.check("metadata", "Ticket"))
        # A second open version of the same identity: an engine that can refuse it does; one
        # that cannot must have the temporal check find it. Either way it is not silent.
        overlap = dict(before, **{cn["valid_from_dts"]: datetime(2026, 7, 1, tzinfo=timezone.utc)})
        overlap.update(self.temporal(ticket, overlap[cn["valid_from_dts"]]))
        refused = False
        try:
            with engine(self.platform).isolate(self.con):
                self.insert("Ticket", {c["name"]: overlap[c["physical_name"]] for c in ticket["columns"]
                                       if c["physical_name"] in overlap})
        except Exception:
            refused = True
        if not refused:
            self.assertTrue(self.check("temporal", "Ticket"))
        refs = [c for c in self.manifest["checks"] if c["check"] == "reference" and c["scope_id"] == "Ticket"]
        self.assertTrue(all(self.q(c["sql"]) == [] for c in refs))
        deleted = named(self.ctx, "Customer")["column_names"]
        self.con.execute(f"UPDATE {self.table('Customer')} SET {self.binding.ident(deleted['is_deleted'])} = {self.marker}, "
                         f"{self.binding.ident(deleted['deleted_dts'])} = {self.marker}",
                         [self.flag(True), datetime.now(timezone.utc)])
        self.assertTrue(any(self.q(c["sql"]) for c in refs))

    def test_an_unregistered_table_is_detected(self):
        self.deploy()
        self.assertEqual(self.check("module", "semantic"), [])
        container = named(self.ctx, "Ticket")["objects"]["table"]["container"]
        stray = self.binding.qualified(container, "stray")
        self.con.execute(f"CREATE TABLE {stray} (x INTEGER)")
        self.undo(f"DROP TABLE {stray}")
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
                       category="STRUCTURAL", severity="ERROR", sql="SELECT 1 AS x"),
                  dict(test_id="T-2", check="x", scope_kind="MODULE", scope_id="search", module="search",
                       category="STRUCTURAL", severity="ERROR", sql="SELECT * FROM no_such_table"),
                  dict(test_id="T-3", check="x", scope_kind="MODULE", scope_id="memory", module="memory",
                       category="STRUCTURAL", severity="ERROR", sql="SELECT 1 AS x WHERE 1 = 0")]
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
                         f"{self.marker} WHERE {self.binding.ident(run['run_id'])} = 'first'", [now - timedelta(days=1)])
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

    def test_a_legacy_run_is_graded_by_its_counts_and_capped(self):
        """Validation §10: a run at a legacy wire version publishes no areas; it is read as one
        PRODUCT entry, graded by §4.3 on its counts and never above `partial`."""
        self.deploy()
        producer, code = self.ctx["product"]["trust_producer"], self.ctx["product"]["code"]
        now = datetime.now(timezone.utc)

        def legacy(run_id, completed, failures):
            counts = dict(passed_count=4 - failures, failed_count=failures, error_count=0,
                          critical_failure_count=0, error_failure_count=failures)
            self.insert("ValidationRun", dict(
                product_code=code, producer_id=producer, producer_version="1.0", profile_id="legacy",
                profile_version="1.0", source_format="NATIVE", payload_schema_version="2.0", run_id=run_id,
                started_dts=completed, completed_dts=completed, trust_status="UNTRUSTED" if failures else "TRUSTED",
                total_checks=4, **counts, repair_candidate_count=0, failed_checks_json="[]",
                evidence_expires_dts=completed + timedelta(days=1), created_dts=completed, updated_dts=completed))

        legacy("legacy-clean", now, 0)
        self.assertEqual(self.trust(code), [("pass", "partial")])
        legacy("legacy-failed", now + timedelta(seconds=1), 1)
        self.assertEqual(self.trust(code), [("fail", "weak")])

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


try:
    import teradatasql
except ImportError:  # pragma: no cover
    teradatasql = None
TERADATA_DSN = os.environ.get("TERADATA_TEST_DSN")
TEST_PREFIX = "anptest"


def isolated(text, prefix):
    """The example profile with every container it creates, and every principal, under a prefix
    the tests own. It uses the profile's own environment mechanism: phases share one system,
    and each container name carries the phase."""
    text = re.sub(r"Environments: -\n(?:  .*\n)+",
                  f"Environments: -\n  Phases:             {prefix}\n  Isolation:          container\n"
                  f"  Container template: {{environment}}_{{container}}\n", text.replace("\r\n", "\n"))
    return re.sub(r"(  ROLE_\w+:\s+)create (\S+)", rf"\1create {prefix}_\2", text)


@unittest.skipUnless(teradatasql and TERADATA_DSN and "teradata" in PLATFORMS,
                     "TERADATA_TEST_DSN or teradatasql missing: Teradata engine coverage is a gap")
class Teradata(EngineTests, unittest.TestCase):
    """Teradata commits each DDL statement and cannot roll a deployment back, so each
    specification is deployed once per run, under the tests' prefix, and every test starts
    from its freshly written rows. Schema a test changes, it reverses."""
    platform = "teradata"
    returning = False
    open_end = datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
    deployments = {}
    BATCHED = re.compile(r"(INSERT|UPDATE|DELETE|MERGE|COMMENT)\b", re.I)

    @classmethod
    def setUpClass(cls):
        cls.con = engine("teradata").connect(TERADATA_DSN)
        cls.profiles = tempfile.TemporaryDirectory()
        cls.drop_test_objects()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.drop_test_objects()
        finally:
            cls.con.close()
            cls.profiles.cleanup()

    @classmethod
    def drop_test_objects(cls):
        """Every role and database carrying the tests' prefix, children first; nothing else."""
        like = f"LIKE '{TEST_PREFIX}!_%' ESCAPE '!'"
        for (role,) in cls.con.execute(f"LOCKING ROW FOR ACCESS SELECT TRIM(RoleName) FROM DBC.RoleInfoV "
                                       f"WHERE RoleName {like}").fetchall():
            cls.con.execute(f'DROP ROLE "{role}"')
        while True:
            leaves = cls.con.execute(
                f"LOCKING ROW FOR ACCESS SELECT TRIM(d.DatabaseName) FROM DBC.DatabasesV d WHERE d.DatabaseName {like} "
                f"AND NOT EXISTS (SELECT 1 FROM DBC.DatabasesV c WHERE c.OwnerName = d.DatabaseName "
                f"AND c.DatabaseName <> d.DatabaseName)").fetchall()
            if not leaves:
                break
            for (name,) in leaves:
                cls.con.execute(f'DELETE DATABASE "{name}"')
                cls.con.execute(f'DROP DATABASE "{name}"')
        cls.deployments.clear()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    # ---- how Teradata writes and reads what the shared tests ask for -----------------
    def flag(self, value):
        return int(value)

    def vector(self, values):
        return json.dumps(values)

    def timestamp(self, sql_text):
        return f"CAST('{sql_text}' AS TIMESTAMP(6) WITH TIME ZONE)"

    def as_of(self, x, valid_at, known_at):
        """Teradata SQL has no table functions: history is read through the governed base view,
        with the temporal profile's predicates."""
        b, cn, v = self.binding, x["column_names"], x["objects"]["base_view"]
        at, known = self.timestamp(valid_at), self.timestamp(known_at)
        where = [f"{b.ident(cn['valid_from_dts'])} <= {at}", f"{at} < {b.ident(cn['valid_to_dts'])}"]
        if x["bitemporal"]:
            where += [f"{b.ident(cn['transaction_from_dts'])} <= {known}", f"{known} < {b.ident(cn['transaction_to_dts'])}"]
        if x["supports_deletion"]:
            where.append(f"{b.ident(cn['is_deleted'])} = 0")
        return f"(SELECT * FROM {b.qualified(v['container'], v['name'])} WHERE {' AND '.join(where)}) AS as_of"

    def uncomment(self, table, column):
        self.con.execute(f"COMMENT ON COLUMN {table}.{column} IS ''")

    def undo(self, sql):
        self.addCleanup(self.con.execute, sql)

    # ---- deployment ------------------------------------------------------------------
    def context(self, spec):
        path = Path(self.profiles.name) / "teradata.md"
        path.write_text(isolated(profile("teradata").read_text(encoding="utf-8"), TEST_PREFIX), encoding="utf-8")
        ctx, findings = build_context.resolve(Path(spec), path, TEST_PREFIX)
        assert not findings, [str(f) for f in findings]
        return ctx

    def deploy(self, spec=ITSD, ctx=None):
        key = str(spec)
        if ctx is None and key in self.deployments:
            context_json, self.files = self.deployments[key]
            self.ctx, self.binding = json.loads(context_json), load_binding(self.platform)[0]
            self.manifest = json.loads(self.files["manifest.json"])
            self.reset()
            return self.manifest
        manifest = super().deploy(spec, ctx)
        if ctx is None:
            self.deployments[key] = (json.dumps(self.ctx), self.files)
        return manifest

    def run_statements(self, sql):
        """Statements in order; consecutive row writes and comments share a request."""
        batch = []

        def flush():
            if batch:
                self.con.execute(";".join(batch))
                batch.clear()
        for statement in sql:
            if self.BATCHED.match(statement):
                batch.append(statement)
                if len(batch) == 40:
                    flush()
            else:
                flush()
                self.con.execute(statement)
        flush()

    def apply(self, files):
        for name in self.manifest["phases"]:
            self.run_statements(statements(files[name]))

    def reset(self):
        """Every row a test wrote goes, and the rows the build writes come back."""
        self.run_statements([f"DELETE FROM {self.binding.qualified(x['objects']['table']['container'], x['objects']['table']['name'])}"
                             for x in persisted(self.ctx)])
        for name in self.manifest["phases"]:
            self.run_statements([s for s in statements(self.files[name])
                                 if re.match(r"(INSERT|UPDATE|DELETE|MERGE)\b", s, re.I)])

    # ---- Teradata's own behaviour ----------------------------------------------------
    def test_the_read_tier_reaches_views_but_not_tables(self):
        """Granted rights, read from the dictionary: the read role reaches the consumer view
        and holds nothing on the database of the table beneath it."""
        self.deploy()
        role = self.ctx["principals"]["ROLE_READ"]["name"]
        rights = {(d, t) for d, t, r in self.q(
            "LOCKING ROW FOR ACCESS SELECT TRIM(DatabaseName), TRIM(TableName), TRIM(AccessRight) "
            "FROM DBC.AllRoleRightsV WHERE RoleName = ?", [role]) if r == "R"}
        ticket = named(self.ctx, "Ticket")["objects"]
        view, table = ticket["consumer_view"], ticket["table"]
        self.assertTrue({(view["container"], "All"), (view["container"], view["name"])} & rights, rights)
        self.assertFalse([d for d, _ in rights if d == table["container"]], rights)

    def test_a_vector_of_the_wrong_dimension_is_refused(self):
        self.deploy()
        embedding = self.ctx["embeddings"][0]
        x = named(self.ctx, embedding["store"])
        with self.assertRaises(teradatasql.Error):
            self.insert(x["name"], dict(entity_id=1, entity_kind="TICKET", source_attribute=embedding["name"],
                                        embedding=self.vector([1.0, 0.0]), embedding_dimensions=2,
                                        embedding_model="m", generated_dts=datetime.now(timezone.utc),
                                        **self.temporal(x, datetime(2026, 1, 1, tzinfo=timezone.utc))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
