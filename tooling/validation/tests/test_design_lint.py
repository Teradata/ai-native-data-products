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
    find_prohibited_name_violations,
    load_prohibited_names,
    mask_sql_noise,
)

# The shape of the prohibited-name table in the temporal pattern, section 4.2. The last
# two rows are the ones that must NOT contribute: a name permitted on some profile, and
# a name prohibited only in one of its two readings.
PROHIBITED_TABLE = """
| Prohibited | Canonical | Scope |
|------------|-----------|-------|
| `created_at`, `created_timestamp`, `created_dt`, `created_date` (as audit) | `created_dts` | All profiles |
| `valid_from`, `effective_from`, `start_timestamp` | `valid_from_dts` | All profiles |
| `deleted_flag`, `active_ind`, `*_yn`, single-character encodings | `is_deleted` / `is_active` (a `Flag`) | All profiles |
| `effective_date` | `valid_from_dts` | Prohibited except on `CURRENT_STATE` |
"""

CLEAN_ENTITY_DOC = """# Domain

Some prose that mentions a table, a view, a date, and the default metric: all fine.

```
Entity: Party                     [kind: History]
  party_id   : Identifier: surrogate, stable across versions
  party_key  : NaturalKey [required] [unique]: business identifier from source
  legal_name : ShortText [optional]: registered legal name
  tax_id     : ShortText [optional] [pii]: tax identifier

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


class ProhibitedTemporalNames(unittest.TestCase):
    """TLM-04, read from the pattern that declares it rather than hard-coded here."""

    def setUp(self):
        self.names = load_prohibited_names(PROHIBITED_TABLE)

    def test_all_profiles_rows_contribute_every_plain_name(self):
        for name in ("created_at", "created_timestamp", "created_dt",
                     "valid_from", "effective_from", "start_timestamp",
                     "deleted_flag", "active_ind"):
            with self.subTest(name=name):
                self.assertIn(name, self.names)

    def test_canonical_replacement_is_carried(self):
        self.assertEqual(self.names["created_at"], "created_dts")
        self.assertEqual(self.names["start_timestamp"], "valid_from_dts")

    def test_replacement_drops_parenthetical_annotation(self):
        # "(a `Flag`)" annotates the replacement; it is not one of the names.
        self.assertEqual(self.names["deleted_flag"], "is_deleted / is_active")

    def test_profile_scoped_row_does_not_contribute(self):
        # effective_date is permitted on CURRENT_STATE, and which profile an entity
        # declares is not knowable from the file being linted.
        self.assertNotIn("effective_date", self.names)

    def test_qualified_name_does_not_contribute(self):
        # created_date is prohibited *as audit* and legal as a day-grain event column.
        self.assertNotIn("created_date", self.names)

    def test_glob_and_prose_do_not_contribute(self):
        self.assertNotIn("*_yn", self.names)
        for key in self.names:
            self.assertNotIn(" ", key)

    def test_column_definition_flagged(self):
        ddl = "CREATE TABLE x (\n    created_at TIMESTAMP(6)\n);\n"
        findings = find_prohibited_name_violations(ddl, "x.sql", self.names)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "tlm-04")
        self.assertEqual(findings[0].line, 2)
        self.assertIn("created_dts", findings[0].message)

    def test_canonical_names_pass(self):
        ddl = ("CREATE TABLE x (\n"
               "    created_dts TIMESTAMP(6),\n"
               "    valid_from_dts TIMESTAMP(6)\n);\n")
        self.assertEqual(find_prohibited_name_violations(ddl, "x.sql", self.names), [])

    def test_prose_in_comments_not_flagged(self):
        # How a template explains which spelling it replaced, and how a keymap header
        # names the prohibited form. Neither is a column.
        art = ("-- created_at is a prohibited spelling of created_dts.\n"
               "{# valid_from and valid_to are prohibited everywhere. #}\n"
               "/* was: created_timestamp */\n"
               "CREATE TABLE x (created_dts TIMESTAMP(6));\n")
        self.assertEqual(find_prohibited_name_violations(art, "x.sql.j2", self.names), [])

    def test_string_literal_not_flagged(self):
        # The catalogue conformance query scans *for* these names.
        art = "SELECT c.ColumnName FROM DBC.ColumnsV\nWHERE c.ColumnName IN ('created_at','valid_from');\n"
        self.assertEqual(find_prohibited_name_violations(art, "q.sql", self.names), [])

    def test_masking_preserves_line_numbers(self):
        art = "-- comment\n\n'literal'\ncreated_at\n"
        masked = mask_sql_noise(art)
        self.assertEqual(len(masked.splitlines()), len(art.splitlines()))
        self.assertEqual(masked.splitlines()[3], "created_at")

    def test_empty_name_table_is_inert(self):
        # Linting a tree with no temporal pattern in it enforces nothing, rather than
        # falling back to a stale copy of the list.
        self.assertEqual(find_prohibited_name_violations("created_at\n", "x.sql", {}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
