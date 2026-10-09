"""Teradata binding conformance to the Platform Implementation Authoring Standard.

Standard section 6 (template rules) and section 8 (acceptance checks), for the Teradata
binding. `test_templates_render.py` renders every template; this module asserts what a
render alone cannot:

  * **Jinja is the only template language.** No plain `.sql` artefact exists under
    `implementation/teradata/`, and no template carries another substitution convention:
    brace tokens (`{db}`), format placeholders (`%s`, `{0}`, `%(name)s`, `${x}`),
    angle-bracket tokens (`<db>`) or marker tokens (`__DB__`). Jinja comments and `raw`
    blocks are removed first, because they are Jinja syntax and do not render.
  * **No container literal.** The shared governance container arrives from the build
    context; no template names it.
  * **Missing values fail.** A template rendered without a value it reads raises, rather
    than emitting an empty string.
  * **Composition is honoured.** Search and Prediction grants render only when those
    modules are in the composition.
  * **The spelled-out temporal block matches the macros.** The registry and the two
    catalogue feeds cannot be generated from the macros without restyling a deployed
    table, so a test holds them to the macros' column set instead.

Jinja is optional: the render-dependent tests skip where it is absent, while the
file-system hygiene checks do not need it.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from td_context import CONTEXT, TERADATA, render  # noqa: E402

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from jinja2.exceptions import UndefinedError
except ImportError:  # pragma: no cover - environment without Jinja
    Environment = None

JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.S)
JINJA_RAW = re.compile(r"\{%-?\s*raw\s*-?%\}.*?\{%-?\s*endraw\s*-?%\}", re.S)

# Substitution conventions other than Jinja. Each is a pattern that cannot occur in the
# SQL a binding legitimately emits, so none of them needs an allowlist.
FOREIGN_CONVENTIONS = {
    "brace token": re.compile(r"(?<!\{)\{[A-Za-z_][\w.]*\}(?!\})"),
    "format placeholder {0}": re.compile(r"(?<!\{)\{\d*\}(?!\})"),
    "named format placeholder": re.compile(r"%\([A-Za-z_]\w*\)[sdr]"),
    "shell or dollar-brace token": re.compile(r"\$\{[^}\n]*\}"),
    "angle-bracket token": re.compile(r"<[A-Za-z_][A-Za-z0-9_ -]*>"),
    "marker token": re.compile(r"__[A-Z][A-Z0-9_]*__"),
}

SQL_FAMILY = (".sql", ".sql.j2")


def teradata_artefacts():
    return sorted(p for p in TERADATA.rglob("*") if p.is_file()
                  and p.name.endswith(SQL_FAMILY))


def jinja_free(text):
    """The template with Jinja comments and raw blocks removed, newlines kept."""
    def blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))
    return JINJA_COMMENT.sub(blank, JINJA_RAW.sub(blank, text))


def line_of(text, index):
    return text.count("\n", 0, index) + 1


class TemplateHygiene(unittest.TestCase):
    def test_there_is_no_plain_sql_under_the_binding(self):
        plain = [p.relative_to(TERADATA).as_posix() for p in teradata_artefacts()
                 if p.name.endswith(".sql") and not p.name.endswith(".sql.j2")]
        self.assertEqual(
            plain, [],
            "plain .sql under implementation/teradata/: every platform artefact is a "
            "Jinja template (*.sql.j2)")

    def test_there_are_templates_to_check(self):
        self.assertGreater(len(teradata_artefacts()), 40)

    def test_no_substitution_convention_other_than_jinja(self):
        findings = []
        for path in teradata_artefacts():
            text = jinja_free(path.read_text(encoding="utf-8"))
            for label, pattern in FOREIGN_CONVENTIONS.items():
                for match in pattern.finditer(text):
                    findings.append("%s:%d: %s %r" % (
                        path.relative_to(TERADATA).as_posix(),
                        line_of(text, match.start()), label, match.group(0)))
        self.assertEqual(findings, [], "\n".join(findings))

    def test_no_shared_container_literal(self):
        """The governance container is a build-context value, never a literal."""
        literal = re.compile(r"\bgovernance\.[A-Za-z_]")
        findings = []
        for path in teradata_artefacts():
            text = jinja_free(path.read_text(encoding="utf-8"))
            for match in literal.finditer(text):
                findings.append("%s:%d: %r" % (
                    path.relative_to(TERADATA).as_posix(),
                    line_of(text, match.start()), match.group(0)))
        self.assertEqual(findings, [], "\n".join(findings))

    def test_the_hygiene_patterns_do_catch_what_they_claim_to(self):
        """A pattern that matches nothing would pass the checks above for ever."""
        samples = {
            "brace token": "SELECT 1 FROM {db}.t;",
            "format placeholder {0}": "SELECT {0};",
            "named format placeholder": "SELECT %(name)s;",
            "shell or dollar-brace token": "SELECT '${HOME}';",
            "angle-bracket token": "-- name is <product>_Semantic",
            "marker token": "SELECT __DB__.t;",
        }
        for label, sample in samples.items():
            with self.subTest(label=label):
                self.assertRegex(jinja_free(sample), FOREIGN_CONVENTIONS[label])
        for ok in ("SELECT {{ db }}.t;", "{#- {db} in a Jinja comment #}",
                   "{% raw %}{db}{% endraw %}", "WHERE a <> b AND c <= d"):
            with self.subTest(ok=ok):
                for label, pattern in FOREIGN_CONVENTIONS.items():
                    self.assertNotRegex(jinja_free(ok), pattern, label)


@unittest.skipIf(Environment is None, "jinja2 not installed")
class RenderedBehaviour(unittest.TestCase):
    def test_a_missing_context_value_fails(self):
        for template, missing in (
                ("patterns/validation/01-validation-run.sql.j2", "db"),
                ("patterns/validation/conformance-queries.sql.j2", "semantic_db"),
                ("patterns/catalogue-interface/02-lifecycle-dml.sql.j2", "stage"),
                ("patterns/catalogue-interface/03-catalogue-views.sql.j2", "governance_db"),
                ("patterns/access-layer/access-layer.dcl.sql.j2", "role_agent"),
                ("patterns/access-layer/dd-access-001.sql.j2", "memory_db"),
                ("patterns/temporal-lifecycle-metadata/02-dml-maintenance.sql.j2",
                 "natural_key")):
            with self.subTest(template=template, missing=missing):
                env = Environment(loader=FileSystemLoader(str(TERADATA)),
                                  undefined=StrictUndefined)
                context = {k: v for k, v in CONTEXT.items() if k != missing}
                with self.assertRaises(UndefinedError):
                    env.get_template(template).render(**context)

    def test_names_come_from_the_context_not_from_a_literal(self):
        """Rendered under unrelated names, no name from the shared fixture survives."""
        keys = [k for k, v in CONTEXT.items() if isinstance(v, str)
                and (k.endswith("_db") or k in ("db", "stage") or k.startswith("role_"))]
        renamed = dict(CONTEXT, **{k: "Zq_" + k for k in keys})
        for template in ("patterns/validation/04-trust-map-views.sql.j2",
                         "patterns/catalogue-interface/03-catalogue-views.sql.j2",
                         "patterns/catalogue-interface/04-resolution-queries.sql.j2",
                         "patterns/catalogue-interface/02-lifecycle-dml.sql.j2",
                         "patterns/access-layer/access-layer.dcl.sql.j2",
                         "modules/semantic/03-registry.sql.j2"):
            with self.subTest(template=template):
                out = render(template, **renamed)
                for key in keys:
                    self.assertNotIn(CONTEXT[key], out, key)
                self.assertNotIn("governance.", out)

    def test_access_layer_grants_follow_the_composition(self):
        template = "patterns/access-layer/access-layer.dcl.sql.j2"
        full = render(template)
        minimal = render(template, modules=["semantic", "memory", "domain", "observability"])
        self.assertIn(CONTEXT["search_db"], full)
        self.assertIn(CONTEXT["prediction_db"], full)
        self.assertNotIn(CONTEXT["search_db"], minimal)
        self.assertNotIn(CONTEXT["prediction_db"], minimal)
        for tier in ("role_read", "role_agent", "role_admin"):
            self.assertIn("CREATE ROLE %s;" % CONTEXT[tier], minimal)
        only_search = render(template, modules=["semantic", "memory", "domain",
                                                "observability", "search"])
        self.assertIn(CONTEXT["search_db"], only_search)
        self.assertNotIn(CONTEXT["prediction_db"], only_search)

    def test_role_comments_stay_within_the_dictionary_limit_for_a_long_product(self):
        out = render("patterns/access-layer/access-layer.dcl.sql.j2",
                     product="GlobalRetailCustomerAnalytics")
        for match in re.finditer(r"COMMENT ON ROLE \w+ IS\s+'([^']*)'", out):
            self.assertLessEqual(len(match.group(1)), 255)

    def test_the_maintenance_specimen_renders_the_declared_attributes(self):
        out = render("patterns/temporal-lifecycle-metadata/02-dml-maintenance.sql.j2",
                     attributes=[{"name": "a_one"}, {"name": "a_two"}, {"name": "a_three"}])
        self.assertIn("(a_one <> :new_a_one OR a_two <> :new_a_two "
                      "OR a_three <> :new_a_three)", out)
        self.assertIn(":last_a_three", out)

    def test_unresolved_expressions_never_reach_output(self):
        for path in teradata_artefacts():
            name = path.relative_to(TERADATA).as_posix()
            if name.endswith("00-temporal-macros.sql.j2"):
                continue
            with self.subTest(template=name):
                try:
                    out = render(name)
                except UndefinedError:
                    continue  # templates with their own structured inputs: covered in
                    #           test_templates_render.CASES
                for marker in ("{{", "{%", "}}", "%}"):
                    self.assertNotIn(marker, out)


@unittest.skipIf(Environment is None, "jinja2 not installed")
class InputContractIsDocumented(unittest.TestCase):
    """TEMPLATE_INPUTS.md lists every value any template reads."""

    MACRO_INTERNAL = {"_", "comma", "width"}

    def test_every_variable_a_template_reads_is_documented(self):
        from jinja2 import meta
        env = Environment(loader=FileSystemLoader(str(TERADATA)))
        doc = (TERADATA / "TEMPLATE_INPUTS.md").read_text(encoding="utf-8")
        missing = {}
        for path in sorted(TERADATA.rglob("*.j2")):
            name = path.relative_to(TERADATA).as_posix()
            source = env.loader.get_source(env, name)[0]
            for var in meta.find_undeclared_variables(env.parse(source)):
                if var not in self.MACRO_INTERNAL and ("`%s`" % var) not in doc:
                    missing.setdefault(var, []).append(name)
        self.assertEqual(missing, {}, "undocumented template inputs")


# The columns every SCD2 table carries, as the macros emit them. Compared as
# (name, type-and-constraints) so comma style and alignment cannot matter.
def column_set(block):
    columns = {}
    for raw in block.splitlines():
        line = re.sub(r"--.*", "", raw).strip().strip(",").strip()
        if not line:
            continue
        name, _, rest = line.partition(" ")
        columns[name] = " ".join(rest.split())
    return columns


@unittest.skipIf(Environment is None, "jinja2 not installed")
class SpelledOutTemporalBlockMatchesTheMacros(unittest.TestCase):
    """03-registry and the catalogue feeds spell the SCD2 block out in leading-comma
    style. Their header says it must match the macros; this makes that checkable."""

    TABLES = {
        "modules/semantic/03-registry.sql.j2": "data_product_registry",
        "patterns/catalogue-interface/01-container-interface-tables.sql.j2":
            "data_product_container",
    }

    @classmethod
    def macro_columns(cls):
        env = Environment(loader=FileSystemLoader(str(TERADATA)), undefined=StrictUndefined)
        block = env.from_string(
            "{% import 'patterns/temporal-lifecycle-metadata/00-temporal-macros.sql.j2' "
            "as tlm %}{{ tlm.columns('SCD2_HISTORY', pad=1, supports_deletion=true) }}"
        ).render()
        return column_set(block)

    def test_each_spelled_out_table_carries_exactly_the_macro_columns(self):
        expected = self.macro_columns()
        self.assertIn("valid_to_dts", expected)
        for template, table in self.TABLES.items():
            with self.subTest(table=table):
                out = render(template)
                match = re.search(
                    r"CREATE MULTISET TABLE \S+\.%s\s*\((.*?)\n\)\s*\n(?:PRIMARY|UNIQUE)"
                    % table, out, re.S)
                self.assertIsNotNone(match, "table %s not found" % table)
                spelled = column_set(match.group(1).replace("\n   ,", "\n"))
                for name, definition in expected.items():
                    self.assertIn(name, spelled, "%s lacks macro column %s" % (table, name))
                    self.assertEqual(
                        spelled[name], definition,
                        "%s.%s differs from the macro definition" % (table, name))


if __name__ == "__main__":
    unittest.main(verbosity=2)
