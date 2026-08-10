"""Unit tests for the design brief validator, plus the reference-product regression.

Every rule gets two tests: one asserting it fires on a broken brief, one asserting the
reference brief stays clean. The second matters more than it looks. A validator that
cannot be made to fail is indistinguishable from one that does nothing, and the
identity-shape check shipped in exactly that state until a deliberate break caught it.

Run from anywhere:
    python -m unittest discover -s tooling/validation/tests
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "evals"))

from brief_lint import (  # noqa: E402
    Corpus,
    check_composition,
    check_decisions,
    check_entities,
    check_frontmatter,
    check_invariants,
    declared_types,
    lint_brief,
    read_entities,
)
from design_lint import parse_frontmatter  # noqa: E402

REFERENCE = REPO_ROOT / "tooling" / "evals" / "reference" / "customer-orders.md"
DESIGN = REPO_ROOT / "design"


def brief_text():
    return REFERENCE.read_text(encoding="utf-8")


def rules_for(text):
    """Rules a modified brief would raise, without touching the file on disk."""
    corpus = Corpus(DESIGN)
    fm, _ = parse_frontmatter(text)
    findings = check_frontmatter(fm, "brief.md")
    if fm is not None:
        findings += check_composition(fm, corpus, "brief.md")
        findings += check_decisions(fm, corpus, "brief.md")
        findings += check_entities(text, "brief.md")
        findings += check_invariants(fm, text, corpus, "brief.md")
    return [f.rule for f in findings]


class ReferenceBriefIsClean(unittest.TestCase):
    """The regression gate: the reference product still conforms to the standards."""

    def test_reference_brief_validates(self):
        findings = lint_brief(REFERENCE)
        self.assertEqual(
            findings, [],
            "the reference design brief no longer conforms:\n"
            + "\n".join(str(f) for f in findings))

    def test_reference_brief_exercises_every_entity_kind(self):
        kinds = {k for _, k, _, _ in read_entities(brief_text())}
        self.assertTrue({"History", "Reference", "Relationship", "Keymap"} <= kinds,
                        f"fixture should cover all four Domain entity kinds, has {kinds}")

    def test_reference_brief_takes_one_non_advocated_decision(self):
        """The `because` path stays exercised, or it rots untested."""
        corpus = Corpus(DESIGN)
        fm, _ = parse_frontmatter(brief_text())
        departures = [d for d in fm["decisions"]
                      if not corpus.decisions.get(d["id"], {}).get(d.get("choice"), True)]
        self.assertTrue(departures, "fixture should depart from one advocated option")
        self.assertTrue(all(d.get("because") for d in departures))


class CompositionRules(unittest.TestCase):
    def test_dropping_a_hard_dependency_is_invalid(self):
        text = brief_text().replace("  - domain\n", "", 1)
        self.assertIn("invalid-composition", rules_for(text))

    def test_unknown_module_flagged(self):
        text = brief_text().replace("  - semantic\n", "  - telepathy\n", 1)
        self.assertIn("unknown-module", rules_for(text))


class DecisionRules(unittest.TestCase):
    def test_unsettled_decision_flagged(self):
        text = brief_text().replace(
            "  - id: DEC-SURROGATE-ALLOCATION\n    choice: keymap\n", "", 1)
        self.assertIn("unsettled-decision", rules_for(text))

    def test_invalid_option_flagged(self):
        text = brief_text().replace("choice: bi-temporal", "choice: tri-temporal", 1)
        self.assertIn("invalid-choice", rules_for(text))

    def test_departing_without_a_reason_flagged(self):
        """Strip whatever reason the fixture carries, not one particular wording."""
        text = re.sub(r"^\s+because:[^\n]*\n", "", brief_text(), count=1, flags=re.M)
        self.assertNotEqual(text, brief_text(), "fixture should carry a 'because' to strip")
        self.assertIn("unjustified-choice", rules_for(text))


class EntityRules(unittest.TestCase):
    def test_history_entity_without_a_natural_key_flagged(self):
        text = re.sub(r"  customer_key\s*: NaturalKey[^\n]*\n", "", brief_text(), count=1)
        self.assertIn("identity-shape", rules_for(text))

    def test_history_entity_without_an_identifier_flagged(self):
        text = re.sub(r"  customer_id\s*: Identifier[^\n]*\n", "", brief_text(), count=1)
        self.assertIn("identity-shape", rules_for(text))

    def test_capability_name_is_not_mistaken_for_a_type(self):
        """`NaturalKeyLookup` contains `NaturalKey`; only declarations count."""
        attrs = ["  party_id : Identifier   // surrogate",
                 "  Requires capabilities:", "    - NaturalKeyLookup"]
        self.assertEqual(declared_types(attrs), ["Identifier"])

    def test_a_brief_with_no_entities_flagged(self):
        text = re.sub(r"```\nEntity:.*?```", "", brief_text(), flags=re.S)
        self.assertIn("no-entities", rules_for(text))


class InvariantRules(unittest.TestCase):
    def test_unacknowledged_invariant_flagged(self):
        text = brief_text().replace("`INV-OBS-004`,", "", 1)
        self.assertIn("unacknowledged-invariant", rules_for(text))

    def test_module_invariant_prefixes_are_derived_not_guessed(self):
        """`observability` declares `INV-OBS-*`; no rule maps the anchor to it."""
        corpus = Corpus(DESIGN)
        self.assertTrue(corpus.modules["observability"]["invariants"],
                        "observability's invariants should be found despite the prefix")
        self.assertTrue(all(i.startswith("INV-OBS-")
                            for i in corpus.modules["observability"]["invariants"]))


class PlatformNeutrality(unittest.TestCase):
    def test_platform_sql_in_a_brief_flagged(self):
        text = brief_text().replace("order_total      : Decimal(12,2)",
                                    "order_total      : DECIMAL(12,2) NOT NULL")
        rules = [f.rule for f in lint_brief(REFERENCE)]  # baseline is clean
        self.assertEqual(rules, [])
        from design_lint import lint_text
        self.assertTrue(any(f.rule == "vendor-token" for f in lint_text("b.md", text)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
