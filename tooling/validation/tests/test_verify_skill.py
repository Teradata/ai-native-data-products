"""Unit tests for the skill-package verifier.

The standards are not compiled any more: the repository is the skill, so there is no
rewriting to check for loss or paraphrase. What is left is whether the package is well
formed and whether its routing resolves, and the second is the one that matters. The
compiled packages shipped a review skill that told its agent to run a linter absent from
the bundle; these tests exist so that cannot happen again.

Each test builds a minimal conforming package in a temp directory, then breaks it one way
at a time.

Run from anywhere:
    python -m unittest discover -s tooling/validation/tests
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "skill"))

from verify_skill import ROLES, SKILL_NAME, verify  # noqa: E402

DESCRIPTION = (
    "Design, build, review, or access an AI-Native Data Product. Load when modelling a "
    "product's modules and decisions, when generating deployable platform DDL, when "
    "assessing how far a built product can be trusted, or when discovering and querying "
    "one that already exists.")


class Package:
    """A minimal package that satisfies every check, then breaks on request."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "roles").mkdir()
        (self.root / "design" / "core").mkdir(parents=True)
        (self.root / "design" / "core" / "MASTER_DESIGN.md").write_text(
            "# Master\n\n## 10. Deployment Sequence\n\nbody\n", encoding="utf-8")
        self.write_skill()
        for role in ROLES:
            self.write_role(role)

    def write_skill(self, name=SKILL_NAME, description=DESCRIPTION, body=None):
        body = body or "# Skill\n\nRead `roles/design.md` for the designer role.\n"
        (self.root / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\n{body}",
            encoding="utf-8")

    def write_role(self, role, body=None):
        body = body or f"# Role: {role}\n\nRead `design/core/MASTER_DESIGN.md` first.\n"
        (self.root / "roles" / f"{role}.md").write_text(body, encoding="utf-8")

    def rules(self):
        return sorted(f.rule for f in verify(self.root))

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class VerifySkillTest(unittest.TestCase):

    def setUp(self):
        self.pkg = Package()
        self.addCleanup(self.pkg.cleanup)

    def test_minimal_package_conforms(self):
        self.assertEqual(verify(self.pkg.root), [])

    def test_wrong_name_is_reported(self):
        self.pkg.write_skill(name="ai-native-dp-design")
        self.assertIn("skill-frontmatter", self.pkg.rules())

    def test_missing_description_is_reported(self):
        self.pkg.write_skill(description="")
        self.assertIn("skill-frontmatter", self.pkg.rules())

    def test_description_omitting_a_role_is_reported(self):
        self.pkg.write_skill(
            description=DESCRIPTION.replace("or access ", "or query ")
                                   .replace("access", "reach"))
        self.assertIn("skill-description", self.pkg.rules())

    def test_wrapped_scalar_in_frontmatter_is_reported(self):
        """The defect that shipped: a description reflowed onto an unindented line.

        `design_lint.parse_frontmatter` is a lenient subset parser and accepts it, so the
        package verified clean and then failed to install against a real YAML loader.
        """
        (self.pkg.root / "SKILL.md").write_text(
            "---\nname: ai-native-data-product\n"
            f"description: {DESCRIPTION[:80]}\n{DESCRIPTION[80:]}\n"
            "---\n\n# Skill\n",
            encoding="utf-8")
        self.assertIn("skill-frontmatter", self.pkg.rules())

    def test_indented_continuation_is_also_reported(self):
        """Valid YAML, but `design_lint.parse_frontmatter` does not fold it.

        SKILL.md's frontmatter is flat - two keys, one line each - so the rule is simply
        that a value stays on its line. Allowing the indented form would pass here and
        still mangle the description everywhere the corpus tooling reads it.
        """
        (self.pkg.root / "SKILL.md").write_text(
            "---\nname: ai-native-data-product\n"
            f"description: {DESCRIPTION[:80]}\n  {DESCRIPTION[80:]}\n"
            "---\n\n# Skill\n",
            encoding="utf-8")
        self.assertIn("skill-frontmatter", self.pkg.rules())

    def test_absent_frontmatter_block_is_reported(self):
        (self.pkg.root / "SKILL.md").write_text("# Skill\n\nNo frontmatter.\n",
                                                encoding="utf-8")
        self.assertIn("skill-frontmatter", self.pkg.rules())

    def test_missing_role_file_is_reported(self):
        (self.pkg.root / "roles" / "build.md").unlink()
        self.assertIn("role-missing", self.pkg.rules())

    def test_dangling_route_is_reported(self):
        self.pkg.write_role("review", "# Review\n\nRun `tooling/validation/design_lint.py`.\n")
        self.assertIn("dangling-route", self.pkg.rules())

    def test_dangling_route_in_skill_md_is_reported(self):
        self.pkg.write_skill(body="# Skill\n\nRead `roles/nonexistent.md`.\n")
        self.assertIn("dangling-route", self.pkg.rules())

    def test_placeholder_route_resolves_when_one_expansion_exists(self):
        impl = self.pkg.root / "implementation" / "teradata" / "modules" / "domain"
        impl.mkdir(parents=True)
        (impl / "validation.sql.j2").write_text("SELECT 1;\n", encoding="utf-8")
        self.pkg.write_role(
            "build",
            "# Build\n\nRun `implementation/{platform}/modules/{module}/validation.sql.j2`.\n")
        self.assertNotIn("dangling-route", self.pkg.rules())

    def test_placeholder_route_with_no_expansion_is_reported(self):
        self.pkg.write_role(
            "build", "# Build\n\nRun `implementation/{platform}/modules/{module}/absent.sql`.\n")
        self.assertIn("dangling-route", self.pkg.rules())

    def test_dangling_section_is_reported(self):
        self.pkg.write_role(
            "design", "# Design\n\nRead `design/core/MASTER_DESIGN.md` §99 first.\n")
        self.assertIn("dangling-section", self.pkg.rules())

    def test_real_section_reference_passes(self):
        self.pkg.write_role(
            "design", "# Design\n\nRead `design/core/MASTER_DESIGN.md` §10 first.\n")
        self.assertNotIn("dangling-section", self.pkg.rules())

    def test_oversized_skill_md_is_reported(self):
        self.pkg.write_skill(body="# Skill\n\n" + "filler line\n" * 200)
        self.assertIn("too-long", self.pkg.rules())

    def test_oversized_role_file_is_reported(self):
        self.pkg.write_role("access", "# Access\n\n" + "filler line\n" * 200)
        self.assertIn("too-long", self.pkg.rules())


class RepositoryIsAConformingSkillTest(unittest.TestCase):
    """The repository itself must pass, so a corpus change cannot silently break routing."""

    def test_this_repository_conforms(self):
        findings = verify(REPO_ROOT)
        self.assertEqual(findings, [], "\n".join(str(f) for f in findings))


if __name__ == "__main__":
    unittest.main()
