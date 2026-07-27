"""Unit tests for the frontmatter, corpus, and decision rules (Design Language S3.1, S3.2, S8).

Frontmatter carries identity only; a document's substance — capabilities and the decisions
it asks a designer to settle — is read from the body. These tests hold that line.

Run from anywhere:
    python -m unittest discover -s tooling/validation/tests
    python tooling/validation/tests/test_design_frontmatter.py
"""
import re
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
    read_document_capabilities,
    read_document_decisions,
)

MODULE_DOC = """---
title: Search Module
anchor: search
type: module
status: standard
version: 2.0
normative: true
---

# Search

**Provides:**

| Capability | Made available to |
|---|---|
| `NearestNeighbors` | Similarity retrieval over current embeddings. |

**Requires:**

| Capability | Strength | Provider | Why |
|---|---|---|---|
| `EntityJoinBack` | `[hard]` | `module:Domain` | Content lives in Domain. |

### 11.1 Decisions to settle

| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-TEMPORAL-PATTERN` | `scd2` | **because** embeddings are regenerated, not corrected. |
| `DEC-DELETE-STRATEGY` | `soft-delete` | Does anything analyse withdrawn embeddings? |
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
| `SoftDelete` | Mark deleted without destroying. | flag predicate. |

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

```
Decision: DEC-DELETE-STRATEGY
  Question:   What happens on delete?

  Option: soft-delete                    [advocated]
    Summary: mark it

  Option: hard-delete
    Summary: destroy it
```
"""


def fm_of(text):
    return parse_frontmatter(text)[0]


class FrontmatterParsing(unittest.TestCase):
    def test_parses_identity_keys(self):
        fm = fm_of(MODULE_DOC)
        self.assertEqual(fm["title"], "Search Module")
        self.assertEqual(fm["anchor"], "search")
        self.assertEqual(fm["type"], "module")

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
    def violations(self, text, path="design/modules/search.md"):
        return find_frontmatter_violations(Path(path), text)

    def test_identity_only_frontmatter_passes(self):
        self.assertEqual(self.violations(MODULE_DOC), [])

    def test_missing_frontmatter_flagged(self):
        self.assertEqual([f.rule for f in self.violations("# Search\n")], ["frontmatter-missing"])

    def test_missing_required_key_flagged(self):
        text = MODULE_DOC.replace("status: standard\n", "")
        self.assertIn("frontmatter-key", [f.rule for f in self.violations(text)])

    def test_substance_keys_are_rejected(self):
        """The S3.2 boundary: substance must not drift back into the header."""
        text = MODULE_DOC.replace("normative: true", "normative: true\nprovides:\n  - Whatever")
        self.assertTrue(any("provides" in f.message for f in self.violations(text)))

    def test_bad_enum_flagged(self):
        text = MODULE_DOC.replace("type: module", "type: nonsense")
        self.assertIn("frontmatter-enum", [f.rule for f in self.violations(text)])

    def test_anchor_must_match_location(self):
        rules = [f.rule for f in self.violations(MODULE_DOC, "design/modules/prediction.md")]
        self.assertIn("anchor-mismatch", rules)

    def test_implementation_requires_implements_and_platform(self):
        text = MODULE_DOC.replace("type: module", "type: implementation")
        messages = [f.message for f in self.violations(text)]
        self.assertTrue(any("implements" in m for m in messages))
        self.assertTrue(any("platform" in m for m in messages))


class BodyReaders(unittest.TestCase):
    def test_capabilities_read_from_provides_and_requires_tables(self):
        caps = read_document_capabilities(MODULE_DOC)
        self.assertEqual(caps["provides"], ["NearestNeighbors"])
        self.assertEqual(caps["requires"], ["EntityJoinBack"])

    def test_a_row_naming_several_capabilities_yields_all_of_them(self):
        """One line of prose often covers several capabilities at once."""
        text = MODULE_DOC.replace(
            "| `NearestNeighbors` | Similarity retrieval over current embeddings. |",
            "| `NearestNeighbors`, `Embed`, `SoftDelete` | Retrieval and lifecycle. |")
        self.assertEqual(read_document_capabilities(text)["provides"],
                         ["NearestNeighbors", "Embed", "SoftDelete"])

    def test_a_heading_closes_the_table(self):
        """A Decisions table further down must not be read as more capabilities."""
        self.assertNotIn("DEC", read_document_capabilities(MODULE_DOC)["requires"])

    def test_decisions_read_from_the_settle_table(self):
        self.assertEqual([(d, r) for d, r, _ in read_document_decisions(MODULE_DOC)],
                         [("DEC-TEMPORAL-PATTERN", "scd2"),
                          ("DEC-DELETE-STRATEGY", "soft-delete")])

    def test_capability_catalogue_reads_only_its_section(self):
        self.assertEqual(load_capability_catalogue(CAPABILITY_DOC),
                         {"EntityJoinBack", "NearestNeighbors", "SoftDelete"})

    def test_decision_catalogue_records_the_advocated_option(self):
        self.assertEqual(load_decision_catalogue(DECISION_DOC)["DEC-TEMPORAL-PATTERN"],
                         {"bi-temporal": True, "scd2": False})


class CorpusRules(unittest.TestCase):
    def corpus(self, doc_text, path="design/modules/search.md"):
        docs = {
            Path("design/core/DESIGN_LANGUAGE.md"): (fm_of(CAPABILITY_DOC), CAPABILITY_DOC, 0),
            Path("design/core/ADVOCATED_STANDARDS.md"): (fm_of(DECISION_DOC), DECISION_DOC, 0),
            Path(path): (fm_of(doc_text), doc_text, 0),
        }
        # The fixtures are minimal documents, so the spine rule fires on all of them.
        # Spine is covered by ModuleSpine below; these tests are about corpus rules.
        return [f for f in find_corpus_violations(docs) if f.rule != "module-spine"]

    def test_valid_document_passes(self):
        self.assertEqual(self.corpus(MODULE_DOC), [])

    def test_unknown_capability_flagged(self):
        text = MODULE_DOC.replace("`NearestNeighbors`", "`Teleportation`")
        self.assertIn("unknown-capability", [f.rule for f in self.corpus(text)])

    def test_unresolvable_implements_anchor_flagged(self):
        text = MODULE_DOC.replace("normative: true", "normative: true\nimplements: nowhere")
        self.assertIn("unknown-anchor", [f.rule for f in self.corpus(text)])

    def test_unknown_decision_flagged(self):
        text = MODULE_DOC.replace("`DEC-TEMPORAL-PATTERN`", "`DEC-INVENTED`")
        self.assertIn("unknown-decision", [f.rule for f in self.corpus(text)])

    def test_invalid_recommended_option_flagged(self):
        text = MODULE_DOC.replace("| `scd2` |", "| `tri-temporal` |")
        self.assertIn("invalid-choice", [f.rule for f in self.corpus(text)])

    def test_recommending_against_the_advocated_option_needs_a_reason(self):
        text = MODULE_DOC.replace(
            "**because** embeddings are regenerated, not corrected.", "No reason given.")
        self.assertIn("unjustified-choice", [f.rule for f in self.corpus(text)])

    def test_advocated_recommendation_needs_no_reason(self):
        text = MODULE_DOC.replace("| `scd2` |", "| `bi-temporal` |").replace(
            "**because** embeddings are regenerated, not corrected.", "An ordinary question?")
        self.assertEqual(self.corpus(text), [])

    def test_history_module_must_ask_about_versioning_and_deletion(self):
        text = re.sub(r"\| `DEC-DELETE-STRATEGY`.*\n", "", MODULE_DOC)
        text = text.replace("# Search", "# Search\n\n```\nEntity: Doc [kind: History]\n```")
        self.assertIn("undeclared-decision", [f.rule for f in self.corpus(text)])


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
        self.assertEqual([f.rule for f in find_glossary_violations(text, "GLOSSARY.md")],
                         ["glossary-order"])

    def test_wrapped_cross_reference_flagged(self):
        text = GLOSSARY_CLEAN.replace(
            "so that a **facet** may be taken", "so that a\n**facet** may be taken")
        self.assertEqual([f.rule for f in find_glossary_violations(text, "GLOSSARY.md")],
                         ["glossary-entry"])

    def test_end_marker_is_not_an_entry(self):
        self.assertFalse(any("End of" in f.message
                             for f in find_glossary_violations(GLOSSARY_CLEAN, "GLOSSARY.md")))


if __name__ == "__main__":
    unittest.main(verbosity=2)


SPINE_DOC = "\n".join(
    ["---", "title: X", "anchor: x", "type: module", "status: standard",
     "version: 1.0", "normative: true", "---", ""]
    + [f"## {i}. {name}\n\nprose\n"
       for i, name in enumerate([
           "Purpose", "Scope and Boundaries", "Entity Model — Runtime Facet",
           "Something Module-Specific", "Applied Patterns",
           "Capabilities and Composition", "Integration with Other Modules",
           "Invariants", "Designer Responsibilities", "Implementation"], start=1)]
)


class ModuleSpine(unittest.TestCase):
    def test_complete_spine_passes(self):
        from design_lint import find_spine_violations
        self.assertEqual(find_spine_violations(SPINE_DOC, "m.md"), [])

    def test_missing_spine_section_flagged(self):
        from design_lint import find_spine_violations
        text = SPINE_DOC.replace("## 7. Integration with Other Modules", "## 7. Talking To Others")
        findings = find_spine_violations(text, "m.md")
        self.assertEqual([f.rule for f in findings], ["module-spine"])
        self.assertIn("Integration with Other Modules", findings[0].message)

    def test_subtitle_after_em_dash_still_matches(self):
        """`Entity Model — Runtime Facet` satisfies the `Entity Model` requirement."""
        from design_lint import find_spine_violations
        self.assertFalse(any("Entity Model" in f.message
                             for f in find_spine_violations(SPINE_DOC, "m.md")))

    def test_module_specific_sections_are_allowed(self):
        from design_lint import find_spine_violations
        self.assertEqual(find_spine_violations(SPINE_DOC, "m.md"), [],
                         "a module may add its own sections anywhere in the spine")
