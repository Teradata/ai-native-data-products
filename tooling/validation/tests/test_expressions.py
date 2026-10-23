"""The expression vocabulary, binding declarations, and the build-context fields built on them.

Derivations, measures and conditions are written once in a specification and rendered in
each binding's dialect from the fragments the binding declares. These tests hold the
parser to the vocabulary, every binding's declarations to the authoring standard, and the
rendered SQL to what each platform can execute.

Run:
    python -m unittest discover -s tooling/validation/tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "evals"))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "build"))

import build_context  # noqa: E402
from binding import load_binding  # noqa: E402
from expressions import ExpressionError, Unrenderable, functions_used, parse, references, render  # noqa: E402
from spec_notation import load_standard  # noqa: E402

PLATFORMS = sorted(p.name for p in (REPO_ROOT / "implementation").iterdir() if p.is_dir())
EXAMPLE = REPO_ROOT / "examples" / "it-service-desk-data-product"
ITSD_SPEC = EXAMPLE / "design-output" / "design_specification.md"
TERADATA_PROFILE = EXAMPLE / "profiles" / "teradata.md"


def sql(text, platform, **kw):
    b, _ = load_binding(platform)
    return render(parse(text), b.functions,
                  lambda e, a: f"{e.lower()}.{a}" if a else e.lower(), b.literal, **kw)


class Parsing(unittest.TestCase):
    def test_every_vocabulary_shape_parses(self):
        for text in ["map(Ticket.priority, {P1: 1, P2: 2})",
                     "map(Category.category_code, {CAT-006: 1, 'Service Desk': 3})",
                     "count_related(Order, Order.ordered_dts, 90 days) / coalesce(count_related(Order, Order.ordered_dts, 365 days), 1)",
                     "is_null(Ticket.score) or Ticket.score >= 1 and Ticket.score <= 5",
                     "not Ticket.is_deleted", "-(Ticket.amount)", "ratio(metric('Order Value'), count_rows(Order))"]:
            with self.subTest(text=text):
                parse(text)

    def test_precedence_binds_and_before_or(self):
        node = parse("a.x = 1 or b.y = 2 and c.z = 3")
        self.assertEqual(node.value, "or")
        self.assertEqual(node.args[1].value, "and")

    def test_references_and_functions(self):
        node = parse("map(as_of(Agent.team, Ticket.opened_dts), {A: 1})")
        self.assertEqual(references(node), [("Agent", "team"), ("Ticket", "opened_dts")])
        self.assertEqual(functions_used(node), ["map", "as_of"])

    def test_malformed_expressions_rejected(self):
        for text in ["sum(Ticket.x", "Ticket.x = = 1", "{A: 1}("]:
            with self.subTest(text=text), self.assertRaises(ExpressionError):
                parse(text)


class Bindings(unittest.TestCase):
    def test_every_binding_declares_cleanly(self):
        """Discovered from implementation/, never listed: a new platform must declare too."""
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                b, findings = load_binding(platform)
                self.assertEqual([str(f) for f in findings], [])
                missing = {"Identifier", "Reference", "NaturalKey", "ShortText", "Text", "Integer",
                           "Timestamp", "Date", "Flag", "Enum", "Decimal"} - set(b.types)
                self.assertEqual(missing, set(), f"{platform} lacks core logical types")

    def test_physical_types_take_parameters(self):
        b, _ = load_binding("duckdb")
        self.assertEqual(b.physical_type("Vector[384]"), "FLOAT[384]")
        self.assertEqual(b.physical_type("Decimal(12,2)"), "DECIMAL(12,2)")
        self.assertEqual(b.physical_type("Enum{A|B}"), "VARCHAR")
        self.assertIsNone(b.physical_type("Telepathy"))

    def test_undeclared_function_or_type_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("design/core/IMPLEMENTATION_AUTHORING.md", "design/core/DESIGN_SPECIFICATION.md"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text((REPO_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
            target = root / "implementation" / "fake" / "binding.toml"
            target.parent.mkdir(parents=True)
            text = (REPO_ROOT / "implementation" / "duckdb" / "binding.toml").read_text(encoding="utf-8")
            target.write_text(text.replace("[types]\n", "[types]\nHologram = 'BLOB'\n")
                              .replace("[functions]\n", "[functions]\nteleport = 'X({0})'\n"), encoding="utf-8")
            _, findings = load_binding("fake", root)
            messages = " ".join(str(f) for f in findings)
            self.assertIn("Hologram", messages)
            self.assertIn("teleport", messages)


class Rendering(unittest.TestCase):
    def test_same_expression_three_dialects(self):
        text = "hour_of_day(Ticket.opened_dts)"
        rendered = {p: sql(text, p) for p in PLATFORMS}
        self.assertEqual(len(set(rendered.values())), len(PLATFORMS), rendered)

    def test_flag_condition_on_a_platform_without_booleans(self):
        is_flag = lambda e, a: a == "sla_breached"
        self.assertIn("= 1", sql("when(Ticket.sla_breached, 1, 0)", "teradata", is_flag=is_flag))
        self.assertNotIn("= 1", sql("when(Ticket.sla_breached, 1, 0)", "duckdb", is_flag=is_flag))

    def test_undeclared_function_is_unrenderable_not_guessed(self):
        with self.assertRaises(Unrenderable):
            sql("as_of(Customer.tier, Ticket.opened_dts)", "teradata")

    def test_map_renders_a_case(self):
        out = sql("map(Ticket.priority, {P1: 1, P2: 2})", "postgres")
        self.assertEqual(out, "CASE ticket.priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE NULL END")


class ContextFields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx, findings = build_context.resolve(ITSD_SPEC, TERADATA_PROFILE)
        assert not findings, findings

    def entity(self, name):
        return next(e for e in self.ctx["entities"] if e["name"] == name)

    def test_profile_columns_are_canonical(self):
        canonical = load_standard(REPO_ROOT / "design").canonical_attributes
        for names in list(build_context.PROFILE_COLUMNS.values()) + [build_context.AUDIT_COLUMNS,
                                                                     build_context.DELETION_COLUMNS]:
            self.assertLessEqual(set(names), canonical)

    def test_entities_carry_descriptions_and_physical_types(self):
        ticket = self.entity("Ticket")
        self.assertTrue(ticket["description"])
        priority = next(a for a in ticket["attributes"] if a["name"] == "priority")
        self.assertEqual(priority["members"], ["P1", "P2", "P3", "P4"])
        self.assertTrue(all(a["physical_type"] and a["description"] for a in ticket["attributes"]))

    def test_temporal_columns_follow_the_profile(self):
        names = [t["name"] for t in self.entity("Ticket")["temporal"]]
        self.assertIn("transaction_from_dts", names)       # bitemporal
        self.assertNotIn("is_current", names)               # declared on the entity already
        self.assertEqual([t["name"] for t in self.entity("TicketKeymap")["temporal"]],
                         ["created_dts", "updated_dts"])  # current state

    def test_relationships_come_from_references(self):
        rel = next(r for r in self.ctx["relationships"] if r["source_attribute"] == "customer_id"
                   and r["source"] == "Ticket")
        self.assertEqual((rel["target"], rel["target_columns"], rel["mandatory"]),
                         ("Customer", ["customer_id"], True))

    def test_standard_relations_are_defined_by_their_module(self):
        meta = next(x for x in self.ctx["relations"] if x["name"] == "EntityMetadata")
        self.assertTrue(meta["defined"])
        self.assertIn("logical_name", [a["name"] for a in meta["attributes"]])

    def test_unrenderable_expressions_are_reported(self):
        features = self.entity("TicketFeatureSet")
        tier = next(a for a in features["attributes"] if a["name"] == "f_customer_tier_int")
        self.assertIsNone(tier["derive"]["sql"])
        self.assertEqual(tier["derive"]["unsupported"], ["as_of"])

    def test_metric_references_are_inlined(self):
        ctx, _ = build_context.resolve(REPO_ROOT / "tooling" / "evals" / "reference" / "customer-orders.md",
                                       TERADATA_PROFILE)
        aov = next(m for m in ctx["metrics"] if m["name"] == "Average Order Value")
        self.assertIn("SUM(", aov["measure"]["sql"])

    def test_version_defaults_are_recorded(self):
        self.assertEqual(self.ctx["product"]["version"], build_context.DEFAULT_VERSION)
        self.assertIn("product.version", {d["field"] for d in self.ctx["defaults_applied"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
