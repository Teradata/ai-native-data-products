"""Tests for the release bundle generator and the committed bundle.

The committed bundle must match what the sources generate, and the current version must
have its authored documents. The release bundle must also never become a module.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from tooling.bindings.render import ORDER  # noqa: E402
from tooling.release import build_release as release  # noqa: E402


class CommittedBundle(unittest.TestCase):
    def test_committed_bundle_is_current(self):
        self.assertEqual(release.stale_files(), [], "run: python tooling/release/build_release.py")

    def test_current_version_has_authored_documents(self):
        self.assertEqual(release.authored_problems(), [])

    def test_generation_is_deterministic(self):
        self.assertEqual(release.render_bundle(), release.render_bundle())

    def test_bundle_is_not_a_module(self):
        self.assertNotIn("release", ORDER)
        self.assertFalse((REPO / "design/modules/release.md").exists())
        for platform in (REPO / "implementation").iterdir():
            self.assertFalse((platform / "modules/release").exists(), platform.name)
        contract = release.build_contract()
        self.assertEqual(contract["modules"], list(ORDER))
        self.assertNotIn("release", contract["metadata_entities"])


class ContractContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = release.build_contract()

    def test_declares_its_own_version(self):
        self.assertEqual(self.contract["standard_version"], release.read_version())

    def test_declaration_surface_is_published(self):
        entities = {e["name"]: e for e in self.contract["metadata_entities"]["semantic"]}
        self.assertIn("standard_declaration", entities)
        self.assertEqual([c["name"] for c in entities["standard_declaration"]["columns"]][:3],
                         ["declaration_id", "product_id", "component_kind"])
        surface = {v["name"]: v["columns"] for v in self.contract["access_surface"]}
        self.assertIn("v_standard_declaration", surface)
        self.assertEqual(surface["data_product_manifest"][-1], "standard_version")

    def test_identity_grammar_examples_match_their_patterns(self):
        import re
        for rule in self.contract["identity_grammar"]:
            with self.subTest(kind=rule["kind"]):
                self.assertRegex(rule["example"], rule["pattern"])
                others = [r for r in self.contract["identity_grammar"] if r is not rule]
                self.assertFalse(any(re.fullmatch(o["pattern"], rule["example"]) for o in others))

    def test_ordered_group_surfaces_are_published(self):
        entities = {e["name"]: [c["name"] for c in e["columns"]] for e in self.contract["metadata_entities"]["semantic"]}
        self.assertEqual(entities["key_column"], ["key_column_id", "key_id", "ordinal", "column_name"])
        self.assertEqual(entities["relationship_column"], ["relationship_column_id", "relationship_id", "ordinal", "source_column", "target_column"])
        self.assertIn("source_entity", entities["access_column"])
        for gone in ("source_column", "target_column"):
            self.assertNotIn(gone, entities["table_relationship"])
        for gone in ("surrogate_key_column", "natural_key_column"):
            self.assertNotIn(gone, entities["entity_metadata"])
        self.assertNotIn("join_path", entities["access_composition"])
        surface = {v["name"]: v["columns"] for v in self.contract["access_surface"]}
        self.assertEqual(surface["relationship_paths"], [
            "path_id", "origin_entity", "destination_entity", "hop_count", "hop", "key_ordinal",
            "from_entity", "from_column", "to_entity", "to_column", "relationship_id", "direction"])
        self.assertEqual(surface["relationship_edges"], [
            "relationship_id", "key_ordinal", "direction", "from_entity", "from_column", "to_entity", "to_column"])

    def test_every_published_access_object_lists_columns(self):
        for view in self.contract["access_surface"]:
            with self.subTest(view=view["name"]):
                self.assertTrue(view["columns"])

    def test_every_published_column_has_a_comment(self):
        for entities in self.contract["metadata_entities"].values():
            for entity in entities:
                for column in entity["columns"]:
                    with self.subTest(entity=entity["name"], column=column["name"]):
                        self.assertTrue(column["comment"].strip())

    def test_discovery_starts_at_the_trust_map(self):
        roles = self.contract["discovery_roles"]
        self.assertEqual(roles[0]["role"], "TRUST_MAP")
        self.assertEqual([r["discovery_order"] for r in roles], sorted(r["discovery_order"] for r in roles))

    def test_bindings_report_declaration_support(self):
        support = {b["platform"]: b["declares_standard_version"] for b in release.build_bindings()["bindings"]}
        self.assertTrue(support["postgres"])
        self.assertFalse(support["teradata"])

    def test_checks_include_comment_coverage(self):
        rendered = release.build_checks()["rendered_checks"]["postgres"]
        self.assertIn({"scope_kind": "PRODUCT", "check": "comment-coverage"}, rendered)


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
