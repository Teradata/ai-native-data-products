"""The Platform Layout Standard: platform layout blocks, and the product layout declaration.

Each rule of the checker is made to fire by one targeted break of a real platform profile, so
a check that cannot fail is caught. The product-side tests hold every binding to the columns
the Semantic module defines for the declaration, so a binding cannot drift from the design.

Run:
    python -m unittest discover -s tooling/validation/tests
"""
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "build"))

import platform_layout as pl  # noqa: E402
from build_context import resolve  # noqa: E402

TABLE = pl.load_standard()
EXAMPLE = REPO_ROOT / "examples" / "it-service-desk-data-product"
SEMANTIC = (REPO_ROOT / "design" / "modules" / "semantic.md").read_text(encoding="utf-8")


def profile_text(platform: str) -> str:
    return pl.profile_path(platform).read_text(encoding="utf-8")


def rules(text: str):
    return {f.rule for f in pl.check_text(text, "<profile>", TABLE)}


class EveryPlatformDeclaresALayout(unittest.TestCase):
    def test_platforms_are_discovered_not_listed(self):
        self.assertEqual(set(pl.platforms()), {"duckdb", "postgres", "teradata"})

    def test_each_profile_conforms(self):
        for platform in pl.platforms():
            with self.subTest(platform=platform):
                self.assertEqual([str(f) for f in pl.check_platform(platform, TABLE)], [])

    def test_the_standard_defines_the_block(self):
        self.assertEqual(
            {n for n, s in TABLE.items() if s.required},
            {"Container term", "Qualification", "Grant boundary", "Access layer", "Access rationale",
             "Consumer container", "Catalogue source", "Dialect", "Physical checks"})
        self.assertEqual(TABLE["Access layer"].values, ["required", "recommended", "optional", "not-applicable"])
        self.assertEqual(TABLE["Consumer container"].values, ["separate", "may-share"])

    def test_export_is_machine_readable(self):
        exported = pl.export_layout("teradata", TABLE)
        self.assertEqual(exported["platform"], "teradata")
        self.assertEqual(exported["Access layer"], "recommended")
        self.assertIn("DBC.TablesV", exported["Catalogue source"])
        json.dumps(exported)

    def test_a_platform_without_a_profile_fails(self):
        self.assertEqual([f.rule for f in pl.check_platform("no-such-platform", TABLE)], ["missing-profile"])


class EveryRuleCanFail(unittest.TestCase):
    def setUp(self):
        self.good = profile_text("postgres")

    def test_the_unbroken_profile_is_clean(self):
        self.assertEqual(rules(self.good), set())

    def test_missing_heading(self):
        self.assertIn("missing-heading", rules(self.good.replace("## 8. Layout", "## 8. Placement")))

    def test_missing_block(self):
        text = re.sub(r"```\nLayout: -.*?```", "```\n```", self.good, flags=re.S)
        self.assertIn("missing-block", rules(text))

    def test_missing_field(self):
        text = re.sub(r"  Dialect:.*\n", "", self.good)
        self.assertIn("missing-field", rules(text))

    def test_unknown_field(self):
        self.assertIn("unknown-field", rules(self.good.replace("  Dialect:", "  Flavour:     x\n  Dialect:")))

    def test_enum_value_outside_the_standard(self):
        self.assertIn("invalid-value", rules(self.good.replace("Access layer:       optional", "Access layer:       sometimes")))

    def test_block_named(self):
        self.assertIn("invalid-value", rules(self.good.replace("Layout: -", "Layout: postgres")))

    def test_duplicate_block(self):
        block = re.search(r"```\nLayout: -.*?```", self.good, flags=re.S).group(0)
        self.assertIn("duplicate-block", rules(self.good + "\n" + block + "\n"))

    def test_multi_line_value(self):
        self.assertIn("invalid-value", rules(self.good.replace("Dialect:            PostgreSQL SQL",
                                                               "Dialect:\n    PostgreSQL SQL")))


class TheProductDeclaresItsLayout(unittest.TestCase):
    """Every binding carries the columns the Semantic module defines (Platform Layout Standard, section 5)."""

    def test_the_design_defines_the_attributes(self):
        for attribute in ("platform_profile", "standard_version", "consumer_audience", "access_semantics"):
            self.assertIn(f"  {attribute}: ", SEMANTIC)

    def test_every_binding_carries_them(self):
        files = {
            "teradata": [REPO_ROOT / "implementation/teradata/modules/semantic/03-registry.sql",
                         REPO_ROOT / "implementation/teradata/modules/semantic/07-access-object.sql.j2"],
            "postgres": [REPO_ROOT / "implementation/postgres/modules/semantic/entities.json"],
            "duckdb": [REPO_ROOT / "implementation/duckdb/model.py"],
        }
        for platform, paths in files.items():
            text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
            for attribute in ("platform_profile", "standard_version", "consumer_audience", "access_semantics", "object_type"):
                with self.subTest(platform=platform, attribute=attribute):
                    self.assertIn(attribute, text)

    def test_the_build_context_records_platform_and_standard_version(self):
        master = (REPO_ROOT / "design" / "core" / "MASTER_DESIGN.md").read_text(encoding="utf-8")
        version = re.search(r"^version:\s*(\S+)", master, re.M).group(1)
        for profile in ("organisation-profile.md", "organisation-profile-type-grouped.md"):
            with self.subTest(profile=profile):
                context, findings = resolve(EXAMPLE / "design-output" / "design_specification.md", EXAMPLE / profile)
                self.assertEqual([str(f) for f in findings], [])
                self.assertEqual(context["standard_version"], version)
                self.assertEqual(context["platform"]["name"], "teradata")


if __name__ == "__main__":
    unittest.main()
