"""Organisation profiles and the build-context resolver.

The profile checks are tested the way the specification linter is: each rule is made to
fire by one targeted break of a real profile, so a check that cannot fail is caught. The
resolver is tested on the worked inputs (two specifications, two deliberately different
profiles) for the properties the Platform Implementation Authoring Standard requires of
it: every context matches the one schema, the same specification yields products that
differ only where the profiles do, and every rule the resolver enforces can be tripped.

Run:
    python -m unittest discover -s tooling/validation/tests
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "build"))

from build_context import resolve  # noqa: E402
from org_profile import (  # noqa: E402
    check_profile,
    load_profile_standard,
    parse_profile,
)

EXAMPLE = REPO_ROOT / "examples" / "it-service-desk-data-product"
ITSD_SPEC = EXAMPLE / "design-output" / "design_specification.md"
ORDERS_SPEC = REPO_ROOT / "tooling" / "evals" / "reference" / "customer-orders.md"
PROFILE_A = EXAMPLE / "organisation-profile.md"
PROFILE_B = EXAMPLE / "organisation-profile-type-grouped.md"
SCHEMA = json.loads((REPO_ROOT / "tooling" / "build" / "build_context.schema.json")
                    .read_text(encoding="utf-8"))
PSTD = load_profile_standard(REPO_ROOT / "design")


# --------------------------------------------------------------------------- #
# A validator for the JSON Schema subset the build-context schema uses
# --------------------------------------------------------------------------- #

TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None),
         "integer": int, "number": (int, float)}


def schema_errors(value, schema, root=SCHEMA, at="$"):
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return schema_errors(value, node, root, at)
    if "oneOf" in schema:
        matches = [s for s in schema["oneOf"] if not schema_errors(value, s, root, at)]
        return [] if len(matches) == 1 else [f"{at}: matches {len(matches)} of oneOf"]
    errors = []
    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(isinstance(value, TYPES[t]) and not (t in ("integer", "number")
                   and isinstance(value, bool)) for t in allowed):
            return [f"{at}: {type(value).__name__} is not {allowed}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{at}: {value!r} is not {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{at}: {value!r} is not one of {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        errors.append(f"{at}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{at}: missing '{key}'")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                errors += schema_errors(item, props[key], root, f"{at}.{key}")
            elif extra is False:
                errors.append(f"{at}: unexpected '{key}'")
            elif isinstance(extra, dict):
                errors += schema_errors(item, extra, root, f"{at}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors += schema_errors(item, schema["items"], root, f"{at}[{i}]")
    return errors


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def profile_rules(text):
    return [f.rule for f in check_profile(parse_profile(text, PSTD, "p.md"), PSTD)]


def broken(path, old, new, *more):
    """A worked input with targeted changes, each of which must apply."""
    text = path.read_text(encoding="utf-8")
    pairs = [(old, new)] + list(zip(more[::2], more[1::2]))
    for o, n in pairs:
        assert o in text, f"{path.name} no longer contains {o!r}"
        text = text.replace(o, n, 1)
    return text


class Resolved:
    """Resolve, optionally with modified inputs written to a temporary directory."""

    def __init__(self, spec=ITSD_SPEC, profile=PROFILE_A, spec_text=None, profile_text=None,
                 environment=None):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        if spec_text is not None:
            spec = root / "spec.md"
            spec.write_text(spec_text, encoding="utf-8")
        if profile_text is not None:
            profile = root / "profile.md"
            profile.write_text(profile_text, encoding="utf-8")
        self.context, self.findings = resolve(spec, profile, environment)
        self.rules = [f.rule for f in self.findings]
        self.tmp.cleanup()


def names(context):
    """Every physical container, qualified object and principal name in a context."""
    out = {c["name"] for c in context["containers"]}
    for item in context["entities"] + context["relations"]:
        for obj in item["objects"].values():
            out.add(f"{obj['container']}.{obj['name']}")
    out |= {p["name"] for p in context["principals"].values()}
    return out


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #

class WorkedProfilesAreClean(unittest.TestCase):
    def test_both_example_profiles_validate(self):
        for path in (PROFILE_A, PROFILE_B):
            with self.subTest(profile=path.name):
                self.assertEqual(profile_rules(path.read_text(encoding="utf-8")), [])


class ProfileRules(unittest.TestCase):
    def test_unknown_platform_flagged(self):
        self.assertIn("profile-frontmatter", profile_rules(
            broken(PROFILE_A, "platform: teradata", "platform: mainframe")))

    def test_missing_required_heading_flagged(self):
        self.assertIn("missing-heading", profile_rules(
            broken(PROFILE_A, "## Section 5. Separation Policy", "## Separation")))

    def test_missing_block_flagged(self):
        text = re.sub(r"```\nEnvironments: -\n.*?```", "", PROFILE_A.read_text(encoding="utf-8"),
                      flags=re.S)
        self.assertIn("missing-block", profile_rules(text))

    def test_unknown_field_flagged(self):
        self.assertIn("unknown-field", profile_rules(
            broken(PROFILE_A, "  Namespace:       flat\n", "  Namespace:       flat\n  Colour: blue\n")))

    def test_value_outside_enumeration_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_A, "Namespace:       flat", "Namespace:       nested")))

    def test_unknown_template_variable_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_A, "{product_code}_MEM", "{product_name}_MEM")))

    def test_unknown_template_filter_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_A, "{product_code}_MEM", "{product_code|kebab}_MEM")))

    def test_unknown_object_role_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_A, "    consumer_view: {entity}\n",
                   "    consumer_view: {entity}\n    trigger: {entity}_trg\n")))

    def test_required_role_without_a_template_flagged(self):
        self.assertIn("missing-field", profile_rules(
            broken(PROFILE_A, "    base_view: {entity}_Current\n", "")))

    def test_rule_to_an_unknown_container_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_A, "    function: domain", "    function: library")))

    def test_standard_names_must_be_one_to_one(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_A, "    ValidationArea: validation_area", "    ValidationArea: validation_run")))

    def test_unknown_standard_name_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_A, "    ValidationArea: validation_area", "    TrustThing: trust_thing")))

    def test_classification_default_outside_scheme_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_A, "Default: Internal", "Default: Secret")))

    def test_unmapped_sensitivity_marker_flagged(self):
        self.assertIn("missing-field", profile_rules(
            broken(PROFILE_A, "    pii-incidental: Confidential\n", "")))

    def test_invalid_protection_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_B, "Sensitive: mask for ROLE_READ, ROLE_AGENT", "Sensitive: mask for EVERYONE")))

    def test_container_isolation_needs_a_template(self):
        self.assertIn("missing-field", profile_rules(
            broken(PROFILE_B, "  Container template: {container}_{environment}\n", "")))

    def test_adoption_of_an_unknown_container_flagged(self):
        self.assertIn("invalid-value", profile_rules(
            broken(PROFILE_B, "    governance: enterprise_catalogue\n  Entities:",
                   "    archive: old_archive\n  Entities:")))

    def test_derivation_example_must_agree(self):
        self.assertIn("derivation-mismatch", profile_rules(
            broken(PROFILE_A, "-> ITSD_DOM.Ticket_History", "-> ITSD_DOM.Ticket")))

    def test_three_derivation_examples_required(self):
        text = re.sub(r"(    - table domain Ticket History[^\n]*\n).*?(```)", r"\1\2",
                      PROFILE_A.read_text(encoding="utf-8"), count=1, flags=re.S)
        self.assertIn("missing-field", profile_rules(text))


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

class ContextsResolve(unittest.TestCase):
    def test_every_worked_combination_resolves_to_the_schema(self):
        for spec in (ITSD_SPEC, ORDERS_SPEC):
            for profile in (PROFILE_A, PROFILE_B):
                with self.subTest(spec=spec.name, profile=profile.name):
                    r = Resolved(spec, profile)
                    self.assertEqual(r.findings, [], "\n".join(map(str, r.findings)))
                    self.assertEqual(schema_errors(r.context, SCHEMA), [])

    def test_matches_the_examples_placement(self):
        ctx = Resolved().context
        ticket = next(e for e in ctx["entities"] if e["name"] == "Ticket")
        self.assertEqual(ticket["objects"]["table"], {"container": "ITSD_DOM", "name": "Ticket_History"})
        self.assertEqual(ticket["objects"]["consumer_view"], {"container": "ITSD_ACC", "name": "Ticket"})
        registry = next(x for x in ctx["relations"] if x["name"] == "DataProductRegistry")
        self.assertEqual(registry["objects"]["table"]["container"], "governance")
        self.assertEqual(ctx["principals"]["ROLE_AGENT"], {"name": "ITSD_ROLE_AGENT", "create": True})

    def test_defaults_are_recorded(self):
        fields = {d["field"] for d in Resolved().context["defaults_applied"]}
        self.assertIn("entities.Ticket.allocation", fields)
        self.assertIn("entities.Ticket.module", fields)


class Portability(unittest.TestCase):
    def test_profiles_share_no_physical_names(self):
        a, b = names(Resolved(profile=PROFILE_A).context), names(Resolved(profile=PROFILE_B).context)
        self.assertEqual(a & b, set(), "the two profiles should yield disjoint physical names")

    def test_products_differ_only_where_the_profiles_do(self):
        """Strip what a profile controls; what is left is the product, and must match."""
        def logical(ctx):
            return [(e["name"], e["module"], e["profile"], e["allocation"],
                     [(a["name"], a["type"], a["required"], a["derive"]) for a in e["attributes"]])
                    for e in ctx["entities"]]
        a, b = Resolved(profile=PROFILE_A).context, Resolved(profile=PROFILE_B).context
        self.assertEqual(logical(a), logical(b))
        for key in ("metrics", "embeddings", "models", "quality", "lineage", "retention",
                    "decisions", "product_decisions"):
            self.assertEqual(a[key], b[key], key)

    def test_one_profile_serves_another_product(self):
        ctx = Resolved(spec=ORDERS_SPEC).context
        self.assertFalse([n for n in names(ctx) if "ITSD" in n.upper()])
        self.assertTrue(all(c["name"].startswith("CUSTORD_") or c["adopted"]
                            for c in ctx["containers"]))

    def test_standard_names_are_mapped(self):
        ctx = Resolved(spec=ORDERS_SPEC, profile=PROFILE_B).context
        keymap = next(e for e in ctx["entities"] if e["name"] == "CustomerKeymap")
        created = next(a for a in keymap["attributes"] if a["name"] == "created_dts")
        self.assertEqual(created["physical_name"], "row_created_ts")

    def test_classification_and_protection_follow_the_profile(self):
        def contact(profile):
            ctx = Resolved(profile=profile).context
            customer = next(e for e in ctx["entities"] if e["name"] == "Customer")
            a = next(a for a in customer["attributes"] if a["name"] == "contact_email")
            return a["classification"], a["protection"]
        self.assertEqual(contact(PROFILE_A), ("Restricted", "none"))
        self.assertEqual(contact(PROFILE_B), ("Sensitive", "mask for ROLE_READ, ROLE_AGENT"))


class ResolutionRules(unittest.TestCase):
    def test_adopted_entity_and_principal(self):
        ctx = Resolved(profile=PROFILE_B).context
        customer = next(e for e in ctx["entities"] if e["name"] == "Customer")
        self.assertTrue(customer["adopted"])
        self.assertEqual(customer["objects"]["table"], {"container": "crm", "name": "customer_master"})
        self.assertEqual(ctx["principals"]["ROLE_ADMIN"], {"name": "dba_data_stewards", "create": False})

    def test_container_isolation_renames_containers_not_objects(self):
        dev = Resolved(profile=PROFILE_B, environment="dev").context
        prod = Resolved(profile=PROFILE_B, environment="prod").context
        ticket = lambda c: next(e for e in c["entities"] if e["name"] == "Ticket")["objects"]["table"]
        self.assertEqual(ticket(dev)["container"], "dp_itsd_data_dev")
        self.assertEqual(ticket(dev)["name"], ticket(prod)["name"])
        self.assertIn({"name": "enterprise_catalogue", "adopted": True}, dev["containers"])

    def test_unknown_environment_flagged(self):
        self.assertIn("unknown-environment", Resolved(environment="staging").rules)

    def test_retention_outside_the_organisations_bounds_flagged(self):
        r = Resolved(profile=PROFILE_B,
                     spec_text=broken(ITSD_SPEC, "ChangeEvent:       3 years", "ChangeEvent:       10 years"))
        self.assertIn("retention-bound", r.rules)

    def test_session_retention_is_not_an_audit_record(self):
        self.assertNotIn("retention-bound", Resolved(profile=PROFILE_B).rules)

    def test_name_too_long_flagged(self):
        r = Resolved(profile_text=broken(PROFILE_A, "Max name length: 30", "Max name length: 8"))
        self.assertIn("name-too-long", r.rules)

    def test_reserved_name_flagged(self):
        r = Resolved(profile_text=broken(PROFILE_A, "Reserved words:  DBC,", "Reserved words:  ITSD_ACC, DBC,"))
        self.assertIn("reserved-name", r.rules)

    def test_name_collision_flagged(self):
        r = Resolved(profile_text=broken(
            PROFILE_A, "    consumer_view: access", "    consumer_view: module",
            "    consumer_view: {entity}\n", "    consumer_view: {entity}_Current\n",
            "    - consumer_view domain Ticket History -> ITSD_ACC.Ticket\n", ""))
        self.assertIn("name-collision", r.rules)

    def test_unplaceable_module_flagged(self):
        r = Resolved(profile_text=broken(
            PROFILE_A, "  search:        {product_code}_SCH\n", "",
            "    - table search EntityEmbedding History -> ITSD_SCH.EntityEmbedding\n", ""))
        self.assertIn("unplaceable", r.rules)

    def test_invalid_specification_stops_resolution(self):
        r = Resolved(spec_text=broken(ITSD_SPEC, "product_code: ITSD\n", ""))
        self.assertEqual(r.context, {})
        self.assertIn("spec-frontmatter", r.rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
