"""Unit tests for the compiled-skill verifier.

The verifier exists because skill compilation is not deterministic: an agent does the
compression, so the only reliable guarantee is that nothing required was dropped. These
tests build a minimal conforming package in a temp directory, then break it one way at
a time.

Run from anywhere:
    python -m unittest discover -s tooling/validation/tests
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "compiler"))

from verify_skills import Expected, verify  # noqa: E402


def skill_md(role, body=""):
    return (f"---\nname: ai-native-dp-{role}\n"
            f"description: the {role} role, load it when {role}ing.\n---\n\n"
            f"# {role}\n\nRouting: read the on-demand files.\n{body}\n")


class SkillPackage:
    """A minimal package that satisfies every check, then breaks on request."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp())
        self.skills = self.root / "skills"
        self.expected = Expected(REPO_ROOT, "teradata")
        self._build()

    def _build(self):
        e = self.expected
        for role in ("design", "build", "review", "access"):
            (self.skills / role).mkdir(parents=True, exist_ok=True)
        (self.skills / "design" / "SKILL.md").write_text(skill_md("design"), encoding="utf-8")
        (self.skills / "build" / "SKILL.md").write_text(skill_md("build"), encoding="utf-8")
        (self.skills / "review" / "SKILL.md").write_text(skill_md("review"), encoding="utf-8")
        (self.skills / "access" / "SKILL.md").write_text(
            skill_md("access", "Product-first discovery, then the pre-use trust gate."),
            encoding="utf-8")

        for role in ("design", "build"):
            for kind, anchors in (("modules", e.modules), ("patterns", e.patterns)):
                (self.skills / role / kind).mkdir(parents=True, exist_ok=True)
                for a in anchors:
                    (self.skills / role / kind / f"{a}.md").write_text(
                        f"# {a}\n", encoding="utf-8")
        (self.skills / "build" / "platform-profile.md").write_text("# profile\n", encoding="utf-8")

        (self.skills / "review" / "checks").mkdir(parents=True, exist_ok=True)
        for a in e.modules + e.patterns:
            (self.skills / "review" / "checks" / f"{a}.md").write_text(
                f"# {a}\n", encoding="utf-8")
        (self.skills / "access" / "discovery.md").write_text("# discovery\n", encoding="utf-8")

        # the content each role is required to carry
        (self.skills / "design" / "decisions.md").write_text(
            "# decisions\n\n" + "\n".join(f"- {d}" for d in sorted(e.decisions)),
            encoding="utf-8")
        (self.skills / "review" / "checks" / "all.md").write_text(
            "# checks\n\n" + "\n".join(sorted(e.invariants | e.conformance)),
            encoding="utf-8")
        (self.skills / "build" / "sql.md").write_text(
            "# sql\n\n" + "\n".join(v[0] for v in e.artifact_anchors.values()),
            encoding="utf-8")

    def rules(self):
        return [f.rule for f in verify(self.skills, REPO_ROOT, "teradata")]

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class VerifierAcceptsAConformingPackage(unittest.TestCase):
    def setUp(self):
        self.pkg = SkillPackage()

    def tearDown(self):
        self.pkg.cleanup()

    def test_conforming_package_passes(self):
        findings = verify(self.pkg.skills, REPO_ROOT, "teradata")
        self.assertEqual(findings, [],
                         "the synthetic package should satisfy every check:\n"
                         + "\n".join(str(f) for f in findings))


class VerifierCatchesLoss(unittest.TestCase):
    def setUp(self):
        self.pkg = SkillPackage()

    def tearDown(self):
        self.pkg.cleanup()

    def test_missing_role_flagged(self):
        (self.pkg.skills / "review" / "SKILL.md").unlink()
        self.assertIn("missing-skill", self.pkg.rules())

    def test_missing_module_file_flagged(self):
        anchor = self.pkg.expected.modules[0]
        (self.pkg.skills / "design" / "modules" / f"{anchor}.md").unlink()
        self.assertIn("missing-file", self.pkg.rules())

    def test_overlong_skill_md_flagged(self):
        path = self.pkg.skills / "design" / "SKILL.md"
        path.write_text(skill_md("design", "\n".join(f"line {i}" for i in range(200))),
                        encoding="utf-8")
        self.assertIn("skill-too-long", self.pkg.rules())

    def test_wrong_skill_name_flagged(self):
        path = self.pkg.skills / "design" / "SKILL.md"
        path.write_text(skill_md("design").replace("ai-native-dp-design", "designer"),
                        encoding="utf-8")
        self.assertIn("skill-frontmatter", self.pkg.rules())

    def test_dropped_decision_flagged(self):
        decisions = self.pkg.skills / "design" / "decisions.md"
        kept = sorted(self.pkg.expected.decisions)[1:]
        decisions.write_text("# decisions\n" + "\n".join(kept), encoding="utf-8")
        self.assertIn("missing-decision", self.pkg.rules())

    def test_dropped_invariant_flagged(self):
        checks = self.pkg.skills / "review" / "checks" / "all.md"
        both = sorted(self.pkg.expected.invariants | self.pkg.expected.conformance)
        checks.write_text("# checks\n" + "\n".join(
            x for x in both if not x.startswith("INV-OBS-004")), encoding="utf-8")
        self.assertIn("missing-invariant", self.pkg.rules())

    def test_dropped_conformance_rule_flagged(self):
        checks = self.pkg.skills / "review" / "checks" / "all.md"
        both = sorted(self.pkg.expected.invariants | self.pkg.expected.conformance)
        checks.write_text("# checks\n" + "\n".join(x for x in both if x != "TLM-01"),
                          encoding="utf-8")
        self.assertIn("missing-conformance-rule", self.pkg.rules())

    def _state(self, ident, statement):
        """Restate a rule in the review skill, declaration-shaped."""
        e = self.pkg.expected
        (self.pkg.skills / "review" / "checks" / "all.md").write_text(
            "# checks\n\n" + "\n".join(sorted(e.invariants | e.conformance))
            + f"\n\n| Rule | Statement | Check |\n|---|---|---|\n"
            + f"| `{ident}` | {statement} | some runnable check |\n",
            encoding="utf-8")

    def test_paraphrased_statement_flagged(self):
        """Carrying the id is not carrying the rule: a summary reads as authoritative."""
        ident = sorted(self.pkg.expected.statements)[0]
        self._state(ident, "a shorter way of putting roughly the same thing.")
        self.assertIn("paraphrased-statement", self.pkg.rules())

    def test_verbatim_statement_accepted(self):
        ident, statement = sorted(self.pkg.expected.statements.items())[0]
        self._state(ident, statement)
        self.assertNotIn("paraphrased-statement", self.pkg.rules())

    def test_rewrapped_statement_accepted(self):
        """Reflowing to fit a table is presentation, not compression."""
        ident, statement = sorted(self.pkg.expected.statements.items())[0]
        self._state(ident, statement.replace(" ", "\n  ", 1))
        self.assertNotIn("paraphrased-statement", self.pkg.rules())

    def test_cited_statement_not_required(self):
        """An id mid-sentence points at wording carried elsewhere; it is not a restatement."""
        e = self.pkg.expected
        ident = sorted(e.statements)[0]
        (self.pkg.skills / "review" / "checks" / "all.md").write_text(
            "# checks\n\n" + "\n".join(sorted(e.invariants | e.conformance))
            + f"\n\nWhere `{ident}` fails, the areas depending on it inherit the doubt.\n",
            encoding="utf-8")
        self.assertNotIn("paraphrased-statement", self.pkg.rules())

    def test_paraphrased_platform_sql_flagged(self):
        """The point of the fingerprint: rewritten SQL is not preserved SQL."""
        (self.pkg.skills / "build" / "sql.md").write_text(
            "# sql\n\nThe templates create the usual tables and views.\n", encoding="utf-8")
        self.assertIn("paraphrased-platform-sql", self.pkg.rules())

    def test_platform_sql_in_the_design_skill_flagged(self):
        (self.pkg.skills / "design" / "modules" / "domain.md").write_text(
            "# domain\n\n```\nCREATE TABLE Party_H (party_id BIGINT NOT NULL);\n```\n",
            encoding="utf-8")
        rules = self.pkg.rules()
        self.assertTrue({"vendor-token", "sql-statement"} & set(rules),
                        f"platform SQL should not survive into the design skill: {rules}")

    def test_on_demand_file_echoing_skill_md_flagged(self):
        shared = "\n".join(f"This is a substantial line of guidance number {i}." for i in range(8))
        (self.pkg.skills / "design" / "SKILL.md").write_text(
            skill_md("design", shared), encoding="utf-8")
        (self.pkg.skills / "design" / "decisions.md").write_text(
            "# decisions\n" + shared + "\n"
            + "\n".join(sorted(self.pkg.expected.decisions)), encoding="utf-8")
        self.assertIn("duplicates-skill", self.pkg.rules())

    def test_access_skill_without_discovery_flagged(self):
        (self.pkg.skills / "access" / "SKILL.md").write_text(skill_md("access"),
                                                             encoding="utf-8")
        rules = self.pkg.rules()
        self.assertIn("access-discovery", rules)
        self.assertIn("access-trust-gate", rules)


class ExpectationsComeFromTheCorpus(unittest.TestCase):
    def test_nothing_about_the_standards_is_hardcoded(self):
        e = Expected(REPO_ROOT, "teradata")
        self.assertEqual(e.modules, sorted(
            p.stem for p in (REPO_ROOT / "design" / "modules").glob("*.md")))
        self.assertTrue(e.decisions and e.invariants and e.conformance)

    def test_framework_invariants_are_taken_deliberately(self):
        """Not picked up incidentally from whichever module happens to cite one."""
        e = Expected(REPO_ROOT, "teradata")
        self.assertTrue({i for i in e.invariants if i.startswith("INV-MASTER-")},
                        "framework invariants belong in the review skill too")

    def test_every_declared_rule_has_its_wording(self):
        """The wording check is only as good as its reading of the corpus."""
        e = Expected(REPO_ROOT, "teradata")
        self.assertEqual(set(e.statements), e.invariants | e.conformance,
                         "every declared invariant and conformance rule should have been "
                         "read with its statement, or the wording check silently skips it")
        self.assertTrue(all(v.strip() for v in e.statements.values()))

    def test_missing_platform_tree_is_not_an_error(self):
        e = Expected(REPO_ROOT, "no-such-platform")
        self.assertEqual(e.artifact_anchors, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
