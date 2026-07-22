"""Unit tests for design_lint.

Run from anywhere:
    python -m unittest discover -s tooling/validation/tests
    python tooling/validation/tests/test_design_lint.py
"""
import sys
import unittest
from pathlib import Path

# Make design_lint importable regardless of the current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design_lint import (  # noqa: E402
    lint_text,
    find_sql_violations,
    find_invariant_violations,
)

CLEAN_ENTITY_DOC = """# Domain

Some prose that mentions a table, a view, a date, and the default metric — all fine.

```
Entity: Party                     [kind: History]
  party_id   : Identifier                     — surrogate, stable across versions
  party_key  : NaturalKey [required] [unique] — business identifier from source
  legal_name : ShortText [optional]           — registered legal name
  tax_id     : ShortText [optional] [pii]     — tax identifier

  Keys:
    surrogate: party_id
    natural:   party_key

  Applies patterns:
    - temporal-lifecycle-metadata

  Requires capabilities:
    - CurrentStateFilter
    - NaturalKeyLookup

  Invariants:
    - INV-DOMAIN-001: every attribute carries descriptive metadata.
```
"""


class NoPlatformSqlRule(unittest.TestCase):
    def test_clean_document_passes(self):
        self.assertEqual(lint_text("clean.md", CLEAN_ENTITY_DOC), [])

    def test_sql_fenced_block_flagged(self):
        doc = "# X\n\n```sql\nSELECT 1;\n```\n"
        rules = {f.rule for f in lint_text("x.md", doc)}
        self.assertIn("sql-fence", rules)
        self.assertIn("sql-statement", rules)

    def test_sql_statement_in_generic_fence_flagged(self):
        doc = "# X\n\n```\nCREATE TABLE Party_H (\n  party_id BIGINT\n);\n```\n"
        findings = find_sql_violations(doc, "x.md")
        rules = {f.rule for f in findings}
        self.assertIn("sql-statement", rules)   # CREATE
        self.assertIn("vendor-token", rules)    # BIGINT

    def test_vendor_tokens_flagged(self):
        for token in [
            "party_key VARCHAR(50)",
            "is_current BYTEINT",
            "PRIMARY INDEX (party_id)",
            "generated_dts TIMESTAMP(6) WITH TIME ZONE",
            "COMMENT ON COLUMN Party_H.party_id IS 'x'",
            "call TD_VectorDistance(...)",
            "amount DECIMAL(10,2)",
            "embedding ::VECTOR",
            "is_current BYTEINT NOT NULL DEFAULT 1",
        ]:
            with self.subTest(token=token):
                doc = f"prose line\n{token}\n"
                self.assertTrue(
                    any(f.rule == "vendor-token" for f in find_sql_violations(doc, "x.md")),
                    f"expected vendor-token finding for: {token}",
                )

    def test_prose_words_not_flagged(self):
        # These English words overlap SQL keywords but must not trip the linter.
        doc = (
            "The table below lists each view. Use the default metric. "
            "The valid date range and the index of terms are described here.\n"
        )
        self.assertEqual(find_sql_violations(doc, "x.md"), [])

    def test_ignore_file_directive_suppresses_everything(self):
        doc = (
            "<!-- design-lint: ignore-file (meta doc) -->\n"
            "# Meta\n\n```sql\nSELECT VARCHAR FROM Party_H;\n```\n"
        )
        self.assertEqual(lint_text("meta.md", doc), [])


class InvariantIdRule(unittest.TestCase):
    def test_wellformed_invariant_passes(self):
        self.assertEqual(find_invariant_violations("- INV-SEARCH-001: keys only.\n"), [])

    def test_malformed_invariant_flagged(self):
        for bad in ["INV-search-001", "INV-SEARCH-1", "INV-SEARCH-01"]:
            with self.subTest(bad=bad):
                findings = find_invariant_violations(f"- {bad}: x\n")
                self.assertTrue(any(f.rule == "invariant-id" for f in findings))

    def test_template_placeholder_not_flagged(self):
        # The literal template with angle brackets must not be treated as a real id.
        self.assertEqual(find_invariant_violations("ids follow INV-<MODULE>-<NNN> form\n"), [])


class EntityNotationRule(unittest.TestCase):
    def test_unknown_logical_type_flagged(self):
        doc = "```\nEntity: Party [kind: History]\n  party_id : Ident\n```\n"
        findings = find_sql_violations(doc, "x.md")
        self.assertTrue(any(f.rule == "unknown-type" for f in findings))

    def test_known_logical_types_pass(self):
        doc = (
            "```\nEntity: E [kind: History]\n"
            "  a : Vector[384]\n"
            "  b : Decimal(10,2) [optional]\n"
            "  c : Enum{X|Y}\n"
            "  d : Reference [-> Party]\n```\n"
        )
        findings = [f for f in find_sql_violations(doc, "x.md") if f.rule == "unknown-type"]
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
