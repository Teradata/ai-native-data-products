"""Teradata's dialect rules, checked on everything the Teradata binding renders.

Each rule is a row of implementation/teradata/PLATFORM_PROFILE.md §7: a construct that has
failed a real deployment, usually with a bare error number several statements after the
cause. The rules run over both reference specifications under both Teradata example
profiles, and over a product whose name is long enough to push a comment past the
dictionary's limit: every phase, the deploy script, every check, and the caller-rendered key
allocation and maintenance templates. Each rule is also shown to catch the construct it
names, so a rule that silently matches nothing cannot pass.

Run:
    python -m unittest discover -s tooling/bindings/tests -v
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tooling" / "bindings"))
sys.path.insert(0, str(REPO / "tooling" / "build"))

import build_context  # noqa: E402
from binding import load_binding  # noqa: E402
from engines import statements  # noqa: E402
from render import environment, render_context  # noqa: E402

EXAMPLE = REPO / "examples" / "it-service-desk-data-product"
ITSD = EXAMPLE / "design-output" / "design_specification.md"
CUSTORD = REPO / "tooling" / "evals" / "reference" / "customer-orders.md"
PROFILES = sorted((EXAMPLE / "profiles").glob("teradata*.md"))
COMMENT_LIMIT = 255


def literals(statement):
    return [m.group(1).replace("''", "'") for m in re.finditer(r"'((?:[^']|'')*)'", statement)]


def unquoted(statement):
    """The statement with string literals emptied and quoted identifiers kept."""
    return re.sub(r"'(?:[^']|'')*'", "''", statement)


def _depths(text):
    depth, out = 0, []
    for ch in text:
        if ch == ")":
            depth -= 1
        out.append(depth)
        if ch == "(":
            depth += 1
    return out


def fromless_selects(statement):
    """Each SELECT that reaches the end of its own query (a closing parenthesis, a set
    operator or the end of the statement) without a FROM at its own depth."""
    text = unquoted(statement)
    depth = _depths(text)
    words = [(m.start(), m.group(0).upper()) for m in
             re.finditer(r"\b(SELECT|FROM|UNION|INTERSECT|MINUS|EXCEPT)\b|\)", text, re.I)]
    out = []
    for n, (pos, word) in enumerate(words):
        if word != "SELECT":
            continue
        for later, other in words[n + 1:]:
            if other == ")" and depth[later] < depth[pos]:
                out.append(pos)
                break
            if depth[later] != depth[pos]:
                continue
            if other == "FROM":
                break
            if other in ("SELECT", "UNION", "INTERSECT", "MINUS", "EXCEPT"):
                out.append(pos)
                break
        else:
            out.append(pos)
    return out


def without_window_orders(statement):
    """The statement with every OVER (...) clause removed, so an ORDER BY left is a query's."""
    text = unquoted(statement)
    while True:
        m = re.search(r"\bOVER\s*\(", text, re.I)
        if not m:
            return text
        depth, i = 1, m.end()
        while depth and i < len(text):
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        text = text[:m.start()] + text[i:]


# ---- the rules: each returns its violations in one statement -------------------------------
def comment_too_long(s):
    if re.match(r"COMMENT\s+ON\b", s, re.I):
        return [x for x in literals(s) if len(x) > COMMENT_LIMIT]
    return []


def order_by_in_view(s):
    if re.match(r"(CREATE|REPLACE)\s+VIEW\b", s, re.I) and re.search(r"\bORDER\s+BY\b", without_window_orders(s), re.I):
        return ["ORDER BY in a view body"]
    return []


def zoned_literal_default(s):
    return re.findall(r"\bDEFAULT\s+TIMESTAMP\s*'[^']*[+-]\d\d:\d\d'", s, re.I)


def fromless_select_in_union(s):
    if re.search(r"\b(UNION|INTERSECT|MINUS|EXCEPT)\b", unquoted(s), re.I):
        return [s[p:p + 60] for p in fromless_selects(s)]
    return []


def untyped_null_in_union(s):
    text = unquoted(s)
    if re.search(r"\b(UNION|INTERSECT|MINUS|EXCEPT)\b", text, re.I):
        return re.findall(r"(?:\bSELECT|,)\s*NULL\s*(?=,|\bFROM\b|\)|$)", text, re.I)
    return []


def colon_name_in_string(s):
    return [x for x in literals(s) if re.search(r"(?<![:\w]):[A-Za-z_]\w*", x)]


def unrendered_jinja(s):
    return re.findall(r"\{\{|\{%|\{#", s)


def text_without_character_set(s):
    if not re.match(r"CREATE\s+(MULTISET\s+|SET\s+)?TABLE\b", s, re.I):
        return []
    return re.findall(r"\b(?:VARCHAR\(\d+\)|CLOB|JSON)(?!\s+CHARACTER\s+SET)", unquoted(s), re.I)


def index_in_another_dialect(s):
    bad = re.findall(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+\S+\s+ON\b", s, re.I)
    if re.match(r"CREATE\s+(UNIQUE\s+)?INDEX\b", s, re.I) and re.search(r"\bWHERE\b", unquoted(s), re.I):
        bad.append("filtered index")
    return bad


def wrong_dictionary_view(s):
    text = unquoted(s)
    bad = re.findall(r"\bDBC\.DatabasePrivilegesV\b", text, re.I)
    if re.search(r"\bDBC\.AllRightsV\b", text, re.I):
        bad += re.findall(r"\bGrantee\b", text, re.I)
    return bad


RULES = {
    "a COMMENT over 255 characters [5550]": comment_too_long,
    "ORDER BY inside a view [3706]": order_by_in_view,
    "a zone-qualified TIMESTAMP literal in a DEFAULT (the driver hangs)": zoned_literal_default,
    "a FROM-less SELECT in a set operation [3888]": fromless_select_in_union,
    "an untyped NULL in a set operation [3654]": untyped_null_in_union,
    "a :name inside a stored string (the driver binds it)": colon_name_in_string,
    "unrendered Jinja": unrendered_jinja,
    "a text column without its character set [6706]": text_without_character_set,
    "another dialect's CREATE INDEX [3706]": index_in_another_dialect,
    "a dictionary view or column that does not exist [3807, 5628]": wrong_dictionary_view,
}

# One statement each rule must catch, so no rule passes by matching nothing.
CAUGHT = {
    "a COMMENT over 255 characters [5550]": "COMMENT ON TABLE d.t IS '" + "x" * 256 + "'",
    "ORDER BY inside a view [3706]": "REPLACE VIEW d.v AS SELECT a FROM d.t ORDER BY a",
    "a zone-qualified TIMESTAMP literal in a DEFAULT (the driver hangs)":
        "CREATE MULTISET TABLE d.t (a TIMESTAMP(6) WITH TIME ZONE DEFAULT TIMESTAMP '9999-12-31 23:59:59+00:00')",
    "a FROM-less SELECT in a set operation [3888]": "SELECT a FROM d.t UNION ALL SELECT 'x'",
    "an untyped NULL in a set operation [3654]": "SELECT a, b FROM d.t UNION ALL SELECT a, NULL FROM d.u",
    "a :name inside a stored string (the driver binds it)": "INSERT INTO d.t VALUES ('WHERE id = :ticket_id')",
    "unrendered Jinja": "SELECT {{ x }} FROM d.t",
    "a text column without its character set [6706]": "CREATE MULTISET TABLE d.t (a VARCHAR(10))",
    "another dialect's CREATE INDEX [3706]": "CREATE INDEX i ON d.t (a)",
    "a dictionary view or column that does not exist [3807, 5628]": "SELECT Grantee FROM DBC.AllRightsV",
}
# And the shapes each must let through.
ALLOWED = [
    "REPLACE VIEW d.v AS SELECT a FROM d.t QUALIFY ROW_NUMBER() OVER (PARTITION BY a ORDER BY b DESC) = 1",
    "SELECT a FROM d.t UNION ALL SELECT b FROM (SELECT b FROM d.u) x",
    "SELECT a, b FROM d.t UNION ALL SELECT a, CAST(NULL AS VARCHAR(10)) FROM d.u WHERE b IS NULL",
    "INSERT INTO d.t VALUES ('2026-01-01 00:00:00+00:00', 'a: b')",
    "CREATE MULTISET TABLE d.t (a VARCHAR(10) CHARACTER SET UNICODE, v VARCHAR(100) CHARACTER SET LATIN)",
    "CREATE INDEX i (a) ON d.t",
]


def long_named(spec, tmp):
    """The specification under a product name long enough to overflow any comment it reaches."""
    text = spec.read_text(encoding="utf-8")
    name = re.search(r"^product: (.+)$", text, re.M).group(1)
    out = Path(tmp) / spec.name
    out.write_text(text.replace(f"product: {name}", "product: " + (name + " ") * 30, 1), encoding="utf-8")
    return out


class TeradataDialect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rendered, cls.long = {}, set()
        with tempfile.TemporaryDirectory() as tmp:
            for name, spec in (("ITSD", ITSD), ("Customer Orders", CUSTORD), ("long-named ITSD", long_named(ITSD, tmp))):
                for profile in PROFILES:
                    ctx, findings = build_context.resolve(spec, profile)
                    assert not findings, [str(f) for f in findings]
                    label = f"{name} on {profile.name}"
                    cls.rendered[label] = cls.everything(ctx)
                    if name.startswith("long"):
                        cls.long.add(label)

    @staticmethod
    def everything(ctx):
        files = render_context(ctx)
        sql = [text for name, text in files.items() if name.endswith(".sql")]
        sql += [c["sql"] for c in json.loads(files["manifest.json"])["checks"]]
        binding, _ = load_binding("teradata")
        env = environment(binding, ctx)
        named = {x["name"]: x for x in ctx["entities"] + ctx["relations"]}
        for keymap in (x for x in ctx["entities"] if x["kind"] == "Keymap"):
            sql.append(env.get_template("modules/domain/02-key-allocation.sql.j2").render(
                **dict(ctx, keymap=keymap, natural_value="SRC-1")))
        for x in (x for x in named.values() if x.get("history") and "table" in x.get("objects", {})):
            row = {c["physical_name"]: "infinity" if c["name"] in ("valid_to_dts", "transaction_to_dts") else None
                   for c in x["columns"]}
            sql.append(env.get_template("patterns/temporal-lifecycle-metadata/04-maintenance.sql.j2").render(
                **dict(ctx, entity=x, stable_key=1, effective_at="2026-01-01T00:00:00+00:00",
                       recorded_at="2026-01-01T00:00:00+00:00", replacement_rows=[row])))
        return [s for text in sql for s in statements(text)]

    def test_every_rendered_statement_keeps_the_dialect_rules(self):
        self.assertEqual(len(self.rendered), 3 * len(PROFILES))
        for label, stmts in self.rendered.items():
            self.assertGreater(len(stmts), 100, label)
            for rule, check in RULES.items():
                with self.subTest(build=label, rule=rule):
                    found = [(s[:120], v) for s in stmts for v in check(s)]
                    self.assertEqual(found, [])

    def test_a_long_product_name_still_fits_every_comment(self):
        self.assertEqual(len(self.long), len(PROFILES))
        for label in self.long:
            comments = [x for s in self.rendered[label] if re.match(r"COMMENT\s+ON", s, re.I) for x in literals(s)]
            self.assertTrue(any(len(x) == COMMENT_LIMIT for x in comments), label)

    def test_each_rule_catches_what_it_names(self):
        self.assertEqual(set(CAUGHT), set(RULES))
        for rule, bad in CAUGHT.items():
            with self.subTest(rule=rule):
                self.assertTrue(RULES[rule](bad))

    def test_the_rules_let_the_teradata_forms_through(self):
        for good in ALLOWED:
            for rule, check in RULES.items():
                with self.subTest(statement=good, rule=rule):
                    self.assertEqual(check(good), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
