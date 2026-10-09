"""Every SQL template renders, and what it renders is canonical.

The templates take their temporal columns from the pattern's macro library by Jinja
import (`00-temporal-macros.sql.j2`). That is what stops thirty tables from each
spelling the same columns their own way, and it is also a dependency nothing else in
the repository exercises: a template that no longer renders is a deploy that fails at
the customer, not a test that fails here.

Every `.sql.j2` under `implementation/teradata/` has a case here (Platform Implementation
Authoring Standard section 8, "every template is rendered by at least one test"); a test
fails when a template is added without one. So this asserts, per template:

  * it renders at all, under StrictUndefined, so a variable the template expects and
    the caller does not supply is an error rather than an empty string;
  * the rendered SQL contains no prohibited generic name (TLM-04), read from the
    pattern exactly as `design_lint` reads it;
  * a template that imports the temporal macros emitted the temporal columns, rather
    than silently producing an empty block.

Jinja is optional: the whole module skips where it is absent, so the stdlib-only
contract of the rest of `tooling/` still holds.

Run:
    python -m unittest discover -s tooling/validation/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from td_context import CONTEXT, TERADATA  # noqa: E402
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
    "modules/observability/05-graph-tables.sql.j2": dict(
        product="Demo", graph_key="LIN_DEMO"),
    "modules/prediction/01-feature-group.sql.j2": dict(
        db="Demo_Prediction", group=FEATURE_GROUP),
    "modules/prediction/02-feature-value.sql.j2": dict(product="Demo"),
    "modules/prediction/03-model-prediction.sql.j2": dict(product="Demo"),
    "modules/search/01-embedding.sql.j2": dict(
        database="Demo_Search", entity_kinds="PARTY, PRODUCT"),
    "modules/semantic/01-catalog-tables.sql.j2": dict(product="Demo"),
    "modules/semantic/02-discovery-tables.sql.j2": dict(product="Demo"),
    # Templates whose only inputs are the shared build context (td_context.CONTEXT).
    "modules/domain/validation.sql.j2": dict(product="Demo"),
    "modules/memory/02-runtime-views.sql.j2": dict(product="Demo"),
    "modules/memory/11-documentation-views.sql.j2": dict(product="Demo"),
    "modules/memory/12-capture-protocol.sql.j2": dict(
        registered_modules=[{
            "name": "DOMAIN", "container": "Demo_Domain", "purpose": "Business entities.",
            "scope": "Core entities", "entities": "Party", "upstream": "None",
            "downstream": "Search", "owner": "Data Office", "tech_contact": "Platform team",
            "version": "1.0.0", "status": "DEPLOYED"}],
        decisions=[{
            "id": "DD-DOMAIN-001", "title": "Keymap-sourced surrogate keys",
            "description": "Surrogates come from the keymap.", "context": "Stable ids.",
            "alternatives": "Identity columns.", "rationale": "Keys survive reloads.",
            "consequences": "Keymap load first.", "category": "DESIGN", "module": "DOMAIN",
            "version": "1.0.0", "tables": "Party_H", "author": "Design agent"}],
        superseded=["DD-DOMAIN-001"],
        changes=[{
            "id": "CL-DOMAIN-001", "title": "Initial release", "description": "First deploy.",
            "module": "DOMAIN", "tables": "Party_H", "deployer": "Release agent",
            "version": "1.0.0", "decision_id": "DD-DOMAIN-001"}],
        glossary_terms=[{
            "term": "Party", "category": "ENTITY", "definition": "A person or organisation.",
            "context": "Customer's customer", "module": "DOMAIN", "version": "1.0.0"}],
        recipes=[{
            "id": "QC-DOMAIN-001", "title": "Current parties", "description": "List parties.",
            "use_case": "Orientation", "target_module": "DOMAIN",
            "sql_template": "SELECT * FROM Demo_Domain.Party_Current WHERE party_key = <party_key>",
            "parameters": "party_key: the natural key", "performance": "Indexed read.",
            "complexity": "SIMPLE", "is_batch": False, "module": "DOMAIN",
            "version": "1.0.0"}]),
    "modules/memory/validation.sql.j2": dict(product="Demo"),
    "modules/observability/03-lineage-views.sql.j2": dict(product="Demo"),
    "modules/prediction/validation.sql.j2": dict(product="Demo"),
    "modules/search/validation.sql.j2": dict(product="Demo"),
    "modules/semantic/03-registry.sql.j2": {},
    "modules/semantic/04-path-discovery.sql.j2": dict(product="Demo"),
    "modules/semantic/05-column-catalogue.sql.j2": dict(product="Demo"),
    "modules/semantic/07-access-object.sql.j2": dict(product="Demo"),
    "modules/semantic/07-metric-tables.sql.j2": dict(product="Demo"),
    "modules/semantic/08-access-relationship-paths.sql.j2": dict(product="Demo"),
    "modules/semantic/09-orientation-manifest.sql.j2": dict(product="Demo"),
    "modules/semantic/validation.sql.j2": dict(product="Demo"),
    "patterns/temporal-lifecycle-metadata/00-temporal-macros.sql.j2": {},
    "patterns/temporal-lifecycle-metadata/02-dml-maintenance.sql.j2": {},
    "patterns/temporal-lifecycle-metadata/03-access-views.sql.j2": {},
    "patterns/temporal-lifecycle-metadata/04-statistics.sql.j2": {},
    "patterns/temporal-lifecycle-metadata/conformance-queries.sql.j2": {},
    "patterns/validation/01-validation-run.sql.j2": {},
    "patterns/validation/02-views.sql.j2": {},
    "patterns/validation/03-validation-area.sql.j2": {},
    "patterns/validation/04-trust-map-views.sql.j2": {},
    "patterns/validation/conformance-queries.sql.j2": {},
    "patterns/validation/consumer-queries.sql.j2": {},
    "patterns/catalogue-interface/01-container-interface-tables.sql.j2": {},
    "patterns/catalogue-interface/02-lifecycle-dml.sql.j2": {},
    "patterns/catalogue-interface/03-catalogue-views.sql.j2": {},
    "patterns/catalogue-interface/04-resolution-queries.sql.j2": {},
    "patterns/catalogue-interface/05-semantic-model-export.sql.j2": {},
    "patterns/catalogue-interface/conformance-queries.sql.j2": {},
    "patterns/access-layer/access-layer.dcl.sql.j2": {},
    "patterns/access-layer/dd-access-001.sql.j2": {},
    # Templates with their own structured inputs.
    "modules/domain/05-views.sql.j2": dict(
        database="Demo_Domain",
        entity={"name": "Party", "lower": "party",
                "columns": ["party_id", "party_key", "legal_name"],
                "enriched": {"columns": ["party_id", "legal_name"],
                             "joins": "FROM Demo_Domain.Party_Current e"}}),
    "modules/observability/06-graph-locking-views.sql.j2": dict(graph_key="LIN_DEMO"),
    "modules/observability/07-graph-acl-views.sql.j2": dict(graph_key="LIN_DEMO"),
    "modules/observability/08-catalogue-seed.sql.j2": dict(
        product="Demo", graph_key="LIN_DEMO", display_name="Demo Lineage",
        description="Demo lineage graph.", sort_order=10, column_lineage_enabled=True),
    "modules/observability/09-load-lineage.sql.j2": dict(
        product="Demo", graph_key="LIN_DEMO", column_lineage_enabled=True),
    "modules/observability/10-access.dcl.sql.j2": dict(graph_key="LIN_DEMO"),
    "modules/prediction/04-views.sql.j2": dict(
        pred_db="Demo_Prediction", domain_db="Demo_Domain",
        entity={"name": "Party", "lower": "party", "kind": "PARTY",
                "feature_table": "party_features", "features": ["reorder_propensity"],
                "domain_columns": ["legal_name"]}),
    "modules/search/02-searchable-view.sql.j2": dict(
        search_db="Demo_Search", domain_db="Demo_Domain",
        entity={"name": "Party", "lower": "party", "kind": "PARTY",
                "content_columns": ["legal_name"]}),
    "modules/search/03-similarity.sql.j2": dict(
        search_db="Demo_Search", domain_db="Demo_Domain", metric="cosine", top_k=10,
        rag_k=5,
        entity={"name": "Party", "lower": "party", "kind": "PARTY",
                "content_columns": ["legal_name"]}),
}

# Macro library: it defines macros and emits nothing by itself, so it is the one template
# whose own render is expected to be blank. Its output is exercised by every importer.
RENDERS_EMPTY = {"patterns/temporal-lifecycle-metadata/00-temporal-macros.sql.j2"}

# A template that imports the temporal macros and renders no temporal columns has
# silently lost its macro call, which no other assertion here would notice.
REQUIRED_IN_MACRO_IMPORTERS = ("created_dts", "updated_dts")
MACRO_IMPORT = "00-temporal-macros.sql.j2"

# Comment length is only decidable after rendering: the product name is substituted in,
# and a Jinja conditional contributes one branch rather than all of them. `design_lint`
# checks what it can statically; this is the exact check. The long name is deliberate,
# since the names are the part that varies between deployments.
LONG_PRODUCT = "GlobalRetailCustomerAnalytics"


def all_templates():
    return sorted(p.relative_to(TERADATA).as_posix() for p in TERADATA.rglob("*.j2"))


def context_for(case):
    """The shared build context overlaid with the case's own inputs."""
    merged = dict(CONTEXT)
    merged.update(case)
    return merged


def widened(context):
    """The same context with every container and product name made long."""
    out = dict(context)
    for key, value in context.items():
        if not isinstance(value, str):
            continue
        if key == "product":
            out[key] = LONG_PRODUCT
        elif key in ("db", "database") or key.endswith("_db"):
            suffix = value.split("_", 1)[-1]
            out[key] = f"{LONG_PRODUCT}_{suffix}"
    return out


@unittest.skipIf(Environment is None, "jinja2 not installed")
class TemplatesRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = Environment(loader=FileSystemLoader(str(TERADATA)),
                              keep_trailing_newline=True, undefined=StrictUndefined)
        cls.names = load_prohibited_names(PATTERN_DOC.read_text(encoding="utf-8"))

    def test_prohibited_names_load(self):
        self.assertIn("created_at", self.names)

    def test_every_template_has_a_render_case(self):
        """Standard section 8: every template is rendered by at least one test."""
        templates = all_templates()
        self.assertGreater(len(templates), 40)
        self.assertEqual(
            sorted(set(templates) - set(CASES)), [],
            "a Teradata template has no render case in CASES")
        self.assertEqual(
            sorted(set(CASES) - set(templates)), [],
            "CASES names a template that no longer exists")

    def test_every_template_renders_canonical_sql(self):
        for template, case in CASES.items():
            with self.subTest(template=template):
                out = self.env.get_template(template).render(**context_for(case))

                if template in RENDERS_EMPTY:
                    self.assertEqual(out.strip(), "", f"{template} emitted output")
                else:
                    self.assertTrue(out.strip(), f"{template} rendered nothing")

                findings = find_prohibited_name_violations(out, template, self.names)
                self.assertEqual(
                    findings, [],
                    "rendered SQL uses a prohibited temporal name:\n"
                    + "\n".join(str(f) for f in findings))

                source = self.env.loader.get_source(self.env, template)[0]
                if MACRO_IMPORT in source and template not in RENDERS_EMPTY:
                    for column in REQUIRED_IN_MACRO_IMPORTERS:
                        self.assertIn(column, mask_sql_noise(out),
                                      f"{template} rendered without {column}: the temporal "
                                      f"macro call is missing or emitted nothing")

                self.assertNotIn(
                    "TEMPORAL PROFILE ERROR", out,
                    f"{template} names a profile the macros do not define")

                for marker in ("{{", "{%", "{#"):
                    self.assertNotIn(
                        marker, out,
                        f"{template} left a Jinja expression unrendered: a macro "
                        f"argument quoted as a string does not interpolate")

    def test_no_comment_exceeds_the_limit_under_a_long_product_name(self):
        """Teradata [5550]: a comment over 255 characters is rejected.

        Checked at the widest realistic substitution, because the product name is what
        varies and a comment that fits for 'Demo' can fail for a real one.
        """
        for template, case in CASES.items():
            with self.subTest(template=template):
                out = self.env.get_template(template).render(
                    **widened(context_for(case)))
                findings = find_comment_length_violations(out, template)
                self.assertEqual(
                    findings, [],
                    f"comment over the {COMMENT_LIMIT}-character limit:\n"
                    + "\n".join(str(f) for f in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
