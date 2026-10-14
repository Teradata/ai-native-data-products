"""Tests for the release bundle generator and the committed bundle.

The committed bundle must match what the sources generate, and the current version must
have its authored documents. The release bundle must also never become a module.
"""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tooling" / "release"))
import build_release as release  # noqa: E402

MODULES = ("memory", "semantic", "domain", "observability", "search", "prediction")


class CommittedBundle(unittest.TestCase):
    def test_committed_bundle_is_current(self):
        self.assertEqual(release.stale_files(), [], "run: python tooling/release/build_release.py")

    def test_current_version_has_authored_documents(self):
        self.assertEqual(release.authored_problems(), [])

    def test_generation_is_deterministic(self):
        self.assertEqual(release.render_bundle(), release.render_bundle())

    def test_bundle_is_not_a_module(self):
        self.assertFalse((REPO / "design/modules/release.md").exists())
        for platform in (REPO / "implementation").iterdir():
            self.assertFalse((platform / "modules/release").exists(), platform.name)
        contract = release.build_contract()
        self.assertEqual(contract["modules"], list(MODULES))
        self.assertNotIn("release", contract["metadata_entities"])


class ContractContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = release.build_contract()
        cls.entities = {e["name"]: e for items in cls.contract["metadata_entities"].values() for e in items}
        cls.surface = {s["relation"]: s for s in cls.contract["access_surface"]}

    def test_declares_its_own_version(self):
        self.assertEqual(self.contract["standard_version"], release.read_version())

    def test_declaration_surface_is_published(self):
        self.assertIn("StandardDeclaration", self.entities)
        self.assertEqual(self.entities["StandardDeclaration"]["identity"], "semantic.standard_declaration")
        self.assertEqual(self.surface["DataProductManifest"]["columns"][-1], "standard_version")

    def test_identity_grammar_examples_match_their_patterns(self):
        for rule in self.contract["identity_grammar"]:
            with self.subTest(kind=rule["kind"]):
                self.assertRegex(rule["example"], rule["pattern"])
                others = [r for r in self.contract["identity_grammar"] if r is not rule]
                self.assertFalse(any(re.fullmatch(o["pattern"], rule["example"]) for o in others))

    def test_every_published_identity_follows_the_grammar(self):
        patterns = [re.compile(r["pattern"]) for r in self.contract["identity_grammar"]]
        for identity in [e["identity"] for e in self.entities.values()] + [s["identity"] for s in self.surface.values()]:
            with self.subTest(identity=identity):
                self.assertTrue(any(p.fullmatch(identity) for p in patterns))

    def test_ordered_group_surfaces_are_published(self):
        columns = {name: [c["name"] for c in e["columns"]] for name, e in self.entities.items()}
        self.assertEqual(columns["KeyColumn"][:4], ["key_column_id", "key_definition_id", "ordinal", "column_name"])
        self.assertEqual(columns["RelationshipColumn"][:5],
                         ["relationship_column_id", "relationship_id", "ordinal", "source_column", "target_column"])
        self.assertIn("source_entity", columns["AccessColumn"])
        for gone in ("source_column", "target_column", "source_table", "target_table"):
            self.assertNotIn(gone, columns["TableRelationship"])
        for gone in ("surrogate_key_column", "natural_key_column"):
            self.assertNotIn(gone, columns["EntityMetadata"])
        self.assertNotIn("join_path", columns["AccessComposition"])
        self.assertEqual(self.surface["RelationshipPaths"]["columns"], [
            "path_id", "origin_entity", "destination_entity", "hop_count", "hop", "key_ordinal",
            "from_entity", "from_column", "to_entity", "to_column", "relationship_id", "direction"])

    def test_every_entity_publishes_its_keys_in_order(self):
        embedding = next(e for items in self.contract["metadata_entities"].values() for e in items
                         if e["name"] == "ValidationArea")
        natural = next(k for k in embedding["keys"] if k["role"] == "NATURAL")
        self.assertGreater(len(natural["columns"]), 1)

    def test_every_published_access_object_lists_columns(self):
        for view in self.contract["access_surface"]:
            with self.subTest(view=view["relation"]):
                self.assertTrue(view["columns"])

    def test_discovery_starts_at_the_trust_map(self):
        roles = self.contract["discovery_roles"]
        self.assertEqual(roles[0]["role"], "MANIFEST")
        orders = [r["discovery_order"] for r in roles]
        self.assertEqual(orders, sorted(orders))
        self.assertIn("TRUST_MAP", [r["role"] for r in roles[:2]])

    def test_bindings_report_declaration_support(self):
        support = {b["platform"]: b["declares_standard_version"] for b in release.build_bindings()["bindings"]}
        self.assertTrue(all(support.values()), support)

    def test_checks_include_the_contract_and_comment_coverage(self):
        rendered = release.build_checks()["rendered_checks"]
        for platform, checks in rendered.items():
            names = {c["check"] for c in checks}
            with self.subTest(platform=platform):
                for expected in ("contract-identity", "contract-keys", "contract-relationships",
                                 "contract-access-columns", "contract-composition", "comment-coverage"):
                    self.assertIn(expected, names)


class Generator(unittest.TestCase):
    def test_version_must_be_semantic(self):
        for bad in ("1.1", "v1.1.0", "1.1.0-rc1", ""):
            with self.subTest(version=bad), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "VERSION").write_text(bad + "\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    release.read_version(Path(tmp))

    def test_missing_authored_documents_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("2.0.0\n", encoding="utf-8")
            self.assertEqual(len(release.authored_problems(root)), 2)
            (root / "release/migrations").mkdir(parents=True)
            (root / "release/migrations/v2.0.0.md").write_text("note\n", encoding="utf-8")
            (root / "release/COMPATIBILITY.md").write_text("| 1.9.0 | x |\n", encoding="utf-8")
            self.assertEqual(len(release.authored_problems(root)), 1)
            (root / "release/COMPATIBILITY.md").write_text("| 2.0.0 | x |\n", encoding="utf-8")
            self.assertEqual(release.authored_problems(root), [])

    def test_stale_file_is_detected(self):
        bundle = release.render_bundle()
        path = REPO / next(iter(bundle))
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original + "\n", encoding="utf-8", newline="\n")
            self.assertEqual(release.stale_files(), [str(path.relative_to(REPO)).replace("\\", "/")])
        finally:
            path.write_text(original, encoding="utf-8", newline="\n")
        self.assertEqual(release.stale_files(), [])

    def test_bundle_files_are_valid_json(self):
        for relative, text in release.render_bundle().items():
            with self.subTest(file=relative):
                json.loads(text)


if __name__ == "__main__":
    unittest.main()
