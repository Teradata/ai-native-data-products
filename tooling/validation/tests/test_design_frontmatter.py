"""Unit tests for the frontmatter, anchor, and decision rules (Design Language S3.1, S8).

Run from anywhere:
    python -m unittest discover -s tooling/validation/tests
    python tooling/validation/tests/test_design_frontmatter.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design_lint import (  # noqa: E402
    parse_frontmatter,
    expected_anchor,
    find_frontmatter_violations,
    find_corpus_violations,
    find_glossary_violations,
    load_capability_catalogue,
    load_decision_catalogue,
)

VALID_FM = """---
title: Search Module
anchor: search
type: module
status: standard
version: 2.0
normative: true
provides:
  - NearestNeighbors
requires:
  - capability: EntityJoinBack
    strength: hard
    provider: module:domain
patterns:
  - temporal-lifecycle-metadata
decisions:
  - id: DEC-TEMPORAL-PATTERN
    choice: scd2
    because: embeddings are regenerated rather than corrected
---

# Search
"""

CAPABILITY_DOC = """---
title: Design Language
anchor: design-language
type: core
status: standard
version: 2.0
normative: true
---

### 6.1 Standard capability catalogue

| Capability | Contract | Bindings |
|---|---|---|
| `EntityJoinBack` | Obtain the referenced entity. | join. |
| `NearestNeighbors(query, k)` | Rank candidates. | distance function. |

### 6.2 Something else

| `NotACapability` | should not be picked up | — |
"""

DECISION_DOC = """---
title: Advocated Standards
anchor: advocated-standards
type: core
status: draft
version: 2.0
normative: true
---

```
Decision: DEC-TEMPORAL-PATTERN
  Question:   How is history represented?

  Option: bi-temporal                    [advocated]
    Summary: two dimensions

  Option: scd2
    Summary: one dimension
```
"""


def fm_of(text):
    return parse_frontmatter(text)[0]


class FrontmatterParsing(unittest.TestCase):
    def test_parses_scalars_lists_and_mappings(self):
        fm = fm_of(VALID_FM)
        self.assertEqual(fm["title"], "Search Module")
        self.assertEqual(fm["provides"], ["NearestNeighbors"])
        self.assertEqual(fm["requires"][0]["capability"], "EntityJoinBack")
        self.assertEqual(fm["requires"][0]["strength"], "hard")
        self.assertEqual(fm["decisions"][0]["id"], "DEC-TEMPORAL-PATTERN")

    def test_document_without_frontmatter_returns_none(self):
        self.assertIsNone(fm_of("# Just a heading\n"))

    def test_trailing_comments_are_stripped(self):
        fm = fm_of("---\ntype: module # the kind of document\n---\n\n# X\n")
        self.assertEqual(fm["type"], "module")


class ExpectedAnchor(unittest.TestCase):
    def test_filename_is_normalised_to_kebab_case(self):
        self.assertEqual(expected_anchor(Path("design/core/MASTER_DESIGN.md")), "master-design")

    def test_binding_readme_anchors_on_its_directory(self):
        self.assertEqual(
            expected_anchor(Path("implementation/teradata/modules/domain/README.md")), "domain")

    def test_platform_profile_anchors_on_its_platform(self):
        self.assertEqual(
            expected_anchor(Path("implementation/teradata/PLATFORM_PROFILE.md")), "teradata")


class FrontmatterRules(unittest.TestCase):
    def test_valid_frontmatter_passes(self):
        self.assertEqual(
            find_frontmatter_violations(Path("design/modules/search.md"), VALID_FM), [])

    def test_missing_frontmatter_flagged(self):
        findings = find_frontmatter_violations(Path("design/modules/search.md"), "# Search\n")
        self.assertEqual([f.rule for f in findings], ["frontmatter-missing"])

    def test_missing_required_key_flagged(self):
        text = VALID_FM.replace("status: standard\n", "")
        rules = [f.rule for f in find_frontmatter_violations(Path("design/modules/search.md"), text)]
        self.assertIn("frontmatter-key", rules)

    def test_unknown_key_flagged(self):
        text = VALID_FM.replace("normative: true", "normative: true\nnonsense: yes")
        findings = find_frontmatter_violations(Path("design/modules/search.md"), text)
        self.assertTrue(any("nonsense" in f.message for f in findings))

    def test_bad_enum_flagged(self):
        text = VALID_FM.replace("type: module", "type: nonsense")
        rules = [f.rule for f in find_frontmatter_violations(Path("design/modules/search.md"), text)]
        self.assertIn("frontmatter-enum", rules)

    def test_anchor_must_match_location(self):
        rules = [f.rule for f in
                 find_frontmatter_violations(Path("design/modules/prediction.md"), VALID_FM)]
        self.assertIn("anchor-mismatch", rules)

    def test_bad_require_strength_flagged(self):
        text = VALID_FM.replace("strength: hard", "strength: medium")
        rules = [f.rule for f in find_frontmatter_violations(Path("design/modules/search.md"), text)]
        self.assertIn("frontmatter-enum", rules)

    def test_implementation_requires_implements_and_platform(self):
        text = VALID_FM.replace("type: module", "type: implementation")
        messages = [f.message for f in
                    find_frontmatter_violations(Path("design/modules/search.md"), text)]
        self.assertTrue(any("implements" in m for m in messages))
        self.assertTrue(any("platform" in m for m in messages))


class Catalogues(unittest.TestCase):
    def test_capability_catalogue_reads_only_its_section(self):
        caps = load_capability_catalogue(CAPABILITY_DOC)
        self.assertEqual(caps, {"EntityJoinBack", "NearestNeighbors"})

    def test_decision_catalogue_records_the_advocated_option(self):
        decisions = load_decision_catalogue(DECISION_DOC)
        self.assertEqual(decisions["DEC-TEMPORAL-PATTERN"],
                         {"bi-temporal": True, "scd2": False})


class CorpusRules(unittest.TestCase):
    def corpus(self, doc_text, path="design/modules/search.md"):
        docs = {
            Path("design/core/DESIGN_LANGUAGE.md"): (fm_of(CAPABILITY_DOC), CAPABILITY_DOC, 0),
            Path("design/core/ADVOCATED_STANDARDS.md"): (fm_of(DECISION_DOC), DECISION_DOC, 0),
            Path("design/patterns/temporal-lifecycle-metadata.md"): (
                {"anchor": "temporal-lifecycle-metadata", "type": "pattern"}, "", 0),
            Path(path): (fm_of(doc_text), doc_text, 0),
        }
        return find_corpus_violations(docs)

    def test_valid_document_passes(self):
        self.assertEqual(self.corpus(VALID_FM), [])

    def test_unknown_capability_flagged(self):
        text = VALID_FM.replace("- NearestNeighbors", "- Teleportation")
        self.assertIn("unknown-capability", [f.rule for f in self.corpus(text)])

    def test_unresolvable_pattern_anchor_flagged(self):
        text = VALID_FM.replace("- temporal-lifecycle-metadata", "- imaginary-pattern")
        self.assertIn("unknown-anchor", [f.rule for f in self.corpus(text)])

    def test_unknown_decision_flagged(self):
        text = VALID_FM.replace("DEC-TEMPORAL-PATTERN", "DEC-INVENTED")
        self.assertIn("unknown-decision", [f.rule for f in self.corpus(text)])

    def test_invalid_choice_flagged(self):
        text = VALID_FM.replace("choice: scd2", "choice: tri-temporal")
        self.assertIn("invalid-choice", [f.rule for f in self.corpus(text)])

    def test_departing_from_the_advocated_option_needs_a_reason(self):
        text = VALID_FM.replace(
            "    because: embeddings are regenerated rather than corrected\n", "")
        self.assertIn("unjustified-choice", [f.rule for f in self.corpus(text)])

    def test_advocated_option_needs_no_reason(self):
        text = VALID_FM.replace("choice: scd2", "choice: bi-temporal").replace(
            "    because: embeddings are regenerated rather than corrected\n", "")
        self.assertEqual(self.corpus(text), [])

    def test_history_module_must_declare_its_versioning_decisions(self):
        text = VALID_FM.replace("decisions:\n", "x_unused:\n").replace(
            "  - id: DEC-TEMPORAL-PATTERN\n", "").replace(
            "    choice: scd2\n", "").replace(
            "    because: embeddings are regenerated rather than corrected\n", "")
        text = text.replace("# Search", "# Search\n\n```\nEntity: Doc [kind: History]\n```")
        rules = [f.rule for f in self.corpus(text)]
        self.assertIn("undeclared-decision", rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)


GLOSSARY_CLEAN = """---
title: Glossary
anchor: glossary
type: core
status: standard
version: 1.2
normative: false
---

# Glossary

**Anchor** — The short name identifying a module across the corpus.

**Composition** — A chosen set of modules assembled into a data design pattern,
so that a **facet** may be taken without the whole module.

**Decision** — A named choice a design must settle explicitly.

---

**End of Glossary**
"""


class GlossaryRules(unittest.TestCase):
    def test_clean_glossary_passes(self):
        self.assertEqual(find_glossary_violations(GLOSSARY_CLEAN, "GLOSSARY.md"), [])

    def test_out_of_order_entry_flagged(self):
        text = GLOSSARY_CLEAN.replace("**Anchor** —", "**Zebra** —")
        findings = find_glossary_violations(text, "GLOSSARY.md")
        self.assertEqual([f.rule for f in findings], ["glossary-order"])

    def test_wrapped_cross_reference_flagged(self):
        text = GLOSSARY_CLEAN.replace(
            "so that a **facet** may be taken", "so that a\n**facet** may be taken")
        findings = find_glossary_violations(text, "GLOSSARY.md")
        self.assertEqual([f.rule for f in findings], ["glossary-entry"])

    def test_end_marker_is_not_an_entry(self):
        self.assertFalse(any("End of" in f.message
                             for f in find_glossary_violations(GLOSSARY_CLEAN, "GLOSSARY.md")))
