"""Every SQL template renders, and what it renders is canonical.

The templates take their temporal columns from the pattern's macro library by Jinja
import (`00-temporal-macros.sql.j2`). That is what stops thirty tables from each
spelling the same columns their own way, and it is also a dependency nothing else in
the repository exercises: a template that no longer renders is a deploy that fails at
the customer, not a test that fails here.

So this asserts three things per template:

  * it renders at all, under StrictUndefined, so a variable the template expects and
    the caller does not supply is an error rather than an empty string;
  * the rendered SQL contains no prohibited generic name (TLM-04), read from the
    pattern exactly as `design_lint` reads it;
  * the macro emitted something, rather than silently producing an empty block.

Jinja is optional: the whole module skips where it is absent, so the stdlib-only
contract of the rest of `tooling/` still holds.

Run:
    python -m unittest discover -s tooling/validation/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design_lint import (  # noqa: E402
    COMMENT_LIMIT,
    find_comment_length_violations,
    find_prohibited_name_violations,
    load_prohibited_names,
    mask_sql_noise,
)

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:  # pragma: no cover - environment without Jinja
    Environment = None

REPO_ROOT = Path(__file__).resolve().parents[3]
TERADATA = REPO_ROOT / "implementation" / "teradata"
PATTERN_DOC = REPO_ROOT / "design" / "patterns" / "temporal-lifecycle-metadata.md"

ENTITY = {
    "name": "Party", "lower": "party", "natural_key_len": 100,
    "table_comment": "Party history.",
    "attributes": [{"name": "legal_name", "type": "VARCHAR(200)",
                    "nullable": True, "comment": "Registered name."}],
}
RELATIONSHIP = {
    "name": "PartyProduct", "lower": "party_product",
    "entity1": {"name": "Party", "lower": "party"},
    "entity2": {"name": "Product", "lower": "product"},
    "attributes": [{"name": "role_code", "type": "VARCHAR(20)",
                    "nullable": True, "comment": "Role in the relationship."}],
}
FEATURE_GROUP = {
    "name": "customer_features", "label": "customer", "entity_kinds": "PARTY",
    "features": [{"name": "reorder_propensity", "comment": "Reorder propensity."}],
}

# template -> the context a caller supplies
CASES = {
    "patterns/temporal-lifecycle-metadata/01-ddl-template.sql.j2": dict(
        db="Demo_Domain", entity="agreement", natural_key="agreement_bk",
        surrogate_key="agreement_sk", supports_deletion=True,
        attributes=[{"name": "status_code", "type": "VARCHAR(20)",
                     "comment": "Agreement status."}]),
    "modules/domain/01-keymap.sql.j2": dict(database="Demo_Domain", entity=ENTITY),
    "modules/domain/02-entity.sql.j2": dict(database="Demo_Domain", entity=ENTITY),
    "modules/domain/03-reference.sql.j2": dict(
        database="Demo_Domain",
        reference={"name": "CountryCode", "lower": "country_code",
                   "versioned": True, "hierarchical": False}),
    "modules/domain/04-relationship.sql.j2": dict(
        database="Demo_Domain", rel=RELATIONSHIP),
    "modules/memory/01-runtime-tables.sql.j2": dict(product="Demo"),
    "modules/memory/10-documentation-tables.sql.j2": dict(product="Demo"),
    "modules/observability/01-event-tables.sql.j2": dict(product="Demo"),
    "modules/observability/02-lineage-tables.sql.j2": dict(product="Demo"),
    "modules/prediction/01-feature-group.sql.j2": dict(
        db="Demo_Prediction", group=FEATURE_GROUP),
    "modules/prediction/02-feature-value.sql.j2": dict(product="Demo"),
    "modules/prediction/03-model-prediction.sql.j2": dict(product="Demo"),
    "modules/search/01-embedding.sql.j2": dict(
        database="Demo_Search", entity_kinds="PARTY, PRODUCT"),
    "modules/semantic/01-catalog-tables.sql.j2": dict(product="Demo"),
    "modules/semantic/02-discovery-tables.sql.j2": dict(product="Demo"),
}

# A template that renders but produces no temporal columns has silently lost its
# macro call, which no other assertion here would notice.
REQUIRED_IN_EVERY_RENDER = ("created_dts", "updated_dts")

# Comment length is only decidable after rendering: the product name is substituted in,
# and a Jinja conditional contributes one branch rather than all of them. `design_lint`
# checks what it can statically; this is the exact check. The long name is deliberate,
# since the product name is the part that varies between deployments.
LONG_PRODUCT = "GlobalRetailCustomerAnalytics"


@unittest.skipIf(Environment is None, "jinja2 not installed")
class TemplatesRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = Environment(loader=FileSystemLoader(str(TERADATA)),
                              keep_trailing_newline=True, undefined=StrictUndefined)
        cls.names = load_prohibited_names(PATTERN_DOC.read_text(encoding="utf-8"))

    def test_prohibited_names_load(self):
        self.assertIn("created_at", self.names)

    def test_every_template_renders_canonical_sql(self):
        for template, context in CASES.items():
            with self.subTest(template=template):
                out = self.env.get_template(template).render(**context)

                findings = find_prohibited_name_violations(out, template, self.names)
                self.assertEqual(
                    findings, [],
                    "rendered SQL uses a prohibited temporal name:\n"
                    + "\n".join(str(f) for f in findings))

                for column in REQUIRED_IN_EVERY_RENDER:
                    self.assertIn(column, mask_sql_noise(out),
                                  f"{template} rendered without {column}: the temporal "
                                  f"macro call is missing or emitted nothing")

                self.assertNotIn(
                    "TEMPORAL PROFILE ERROR", out,
                    f"{template} names a profile the macros do not define")

                self.assertNotIn(
                    "{{", out,
                    f"{template} left a Jinja placeholder unrendered: a macro argument "
                    f"quoted as a string does not interpolate")

    def test_no_comment_exceeds_the_limit_under_a_long_product_name(self):
        """Teradata [5550]: a comment over 255 characters is rejected.

        Checked at the widest realistic substitution, because the product name is what
        varies and a comment that fits for 'Demo' can fail for a real one.
        """
        for template, context in CASES.items():
            with self.subTest(template=template):
                widened = dict(context)
                for key in ("product",):
                    if key in widened:
                        widened[key] = LONG_PRODUCT
                for key in ("db", "database"):
                    if isinstance(widened.get(key), str):
                        suffix = widened[key].split("_", 1)[-1]
                        widened[key] = f"{LONG_PRODUCT}_{suffix}"

                out = self.env.get_template(template).render(**widened)
                findings = find_comment_length_violations(out, template)
                self.assertEqual(
                    findings, [],
                    f"comment over the {COMMENT_LIMIT}-character limit:\n"
                    + "\n".join(str(f) for f in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
