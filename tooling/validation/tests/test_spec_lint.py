"""Unit tests for the design specification validator, plus the reference-product regression.

Every rule gets two tests: one asserting it fires on a broken specification, one asserting the
reference specification stays clean. The second matters more than it looks. A validator that
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

from spec_lint import (  # noqa: E402
    Corpus,
    check_composition,
    check_decisions,
    check_entities,
    check_frontmatter,
    check_invariants,
    check_notation,
    declared_types,
    lint_spec,
    read_entities,
)
from design_lint import parse_frontmatter  # noqa: E402

REFERENCE = REPO_ROOT / "tooling" / "evals" / "reference" / "customer-orders.md"
DESIGN = REPO_ROOT / "design"


def spec_text():
    return REFERENCE.read_text(encoding="utf-8")


def rules_for(text):
    """Rules a modified specification would raise, without touching the file on disk."""
    corpus = Corpus(DESIGN)
    fm, _ = parse_frontmatter(text)
    findings = check_frontmatter(fm, "specification.md")
    if fm is not None:
        findings += check_composition(fm, corpus, "specification.md")
        findings += check_decisions(fm, corpus, "specification.md")
        findings += check_entities(text, "specification.md")
        findings += check_invariants(fm, text, corpus, "specification.md")
        findings += check_notation(fm, text, corpus, "specification.md")
    return [f.rule for f in findings]


def broken(old, new):
    """The reference specification with one targeted change, which must apply."""
    text = spec_text()
    assert old in text, f"fixture no longer contains {old!r}"
    return text.replace(old, new, 1)


class ReferenceSpecificationIsClean(unittest.TestCase):
    """The regression gate: the reference product still conforms to the standards."""

    def test_reference_specification_validates(self):
        findings = lint_spec(REFERENCE)
        self.assertEqual(
            findings, [],
            "the reference design specification no longer conforms:\n"
            + "\n".join(str(f) for f in findings))

    def test_reference_specification_exercises_every_entity_kind(self):
        kinds = {k for _, k, _, _ in read_entities(spec_text())}
        self.assertTrue({"History", "Reference", "Relationship", "Keymap"} <= kinds,
                        f"fixture should cover all four Domain entity kinds, has {kinds}")

    def test_reference_specification_takes_one_non_advocated_decision(self):
        """The `because` path stays exercised, or it rots untested."""
        corpus = Corpus(DESIGN)
        fm, _ = parse_frontmatter(spec_text())
        departures = [d for d in fm["decisions"]
                      if not corpus.decisions.get(d["id"], {}).get(d.get("choice"), True)]
        self.assertTrue(departures, "fixture should depart from one advocated option")
        self.assertTrue(all(d.get("because") for d in departures))


class CompositionRules(unittest.TestCase):
    def test_dropping_a_hard_dependency_is_invalid(self):
        text = spec_text().replace("  - domain\n", "", 1)
        self.assertIn("invalid-composition", rules_for(text))

    def test_unknown_module_flagged(self):
        text = spec_text().replace("  - semantic\n", "  - telepathy\n", 1)
        self.assertIn("unknown-module", rules_for(text))


class DecisionRules(unittest.TestCase):
    def test_unsettled_decision_flagged(self):
        text = spec_text().replace(
            "  - id: DEC-SURROGATE-ALLOCATION\n    choice: keymap\n", "", 1)
        self.assertIn("unsettled-decision", rules_for(text))

    def test_invalid_option_flagged(self):
        text = spec_text().replace("choice: bi-temporal", "choice: tri-temporal", 1)
        self.assertIn("invalid-choice", rules_for(text))

    def test_departing_without_a_reason_flagged(self):
        """Strip whatever reason the fixture carries, not one particular wording."""
        text = re.sub(r"^\s+because:[^\n]*\n", "", spec_text(), count=1, flags=re.M)
        self.assertNotEqual(text, spec_text(), "fixture should carry a 'because' to strip")
        self.assertIn("unjustified-choice", rules_for(text))


class EntityRules(unittest.TestCase):
    def test_history_entity_without_a_natural_key_flagged(self):
        text = re.sub(r"  customer_key\s*: NaturalKey[^\n]*\n", "", spec_text(), count=1)
        self.assertIn("identity-shape", rules_for(text))

    def test_history_entity_without_an_identifier_flagged(self):
        text = re.sub(r"  customer_id\s*: Identifier[^\n]*\n", "", spec_text(), count=1)
        self.assertIn("identity-shape", rules_for(text))

    def test_capability_name_is_not_mistaken_for_a_type(self):
        """`NaturalKeyLookup` contains `NaturalKey`; only declarations count."""
        attrs = ["  party_id : Identifier   // surrogate",
                 "  Requires capabilities:", "    - NaturalKeyLookup"]
        self.assertEqual(declared_types(attrs), ["Identifier"])

    def test_a_specification_with_no_entities_flagged(self):
        text = re.sub(r"```\nEntity:.*?```", "", spec_text(), flags=re.S)
        self.assertIn("no-entities", rules_for(text))


class InvariantRules(unittest.TestCase):
    def test_unacknowledged_invariant_flagged(self):
        text = spec_text().replace("`INV-OBS-004`,", "", 1)
        self.assertIn("unacknowledged-invariant", rules_for(text))

    def test_module_invariant_prefixes_are_derived_not_guessed(self):
        """`observability` declares `INV-OBS-*`; no rule maps the anchor to it."""
        corpus = Corpus(DESIGN)
        self.assertTrue(corpus.modules["observability"]["invariants"],
                        "observability's invariants should be found despite the prefix")
        self.assertTrue(all(i.startswith("INV-OBS-")
                            for i in corpus.modules["observability"]["invariants"]))


class NotationFrontmatter(unittest.TestCase):
    def test_missing_product_code_flagged(self):
        self.assertIn("spec-frontmatter", rules_for(broken("product_code: CUSTORD\n", "")))

    def test_product_code_must_be_identifier_safe(self):
        text = broken("product_code: CUSTORD", "product_code: Customer Orders")
        self.assertIn("spec-frontmatter", rules_for(text))

    def test_a_platform_key_is_flagged(self):
        text = broken("product_code: CUSTORD\n", "product_code: CUSTORD\nplatform: snowflake\n")
        self.assertIn("platform-reference", rules_for(text))

    def test_a_platform_named_in_the_body_is_flagged(self):
        text = broken("Similarity over product descriptions.",
                      "Similarity over product descriptions, using Snowflake Cortex.")
        self.assertIn("platform-reference", rules_for(text))


class NotationEntities(unittest.TestCase):
    STATUS = "Entity: OrderStatus               [kind: Reference] [profile: SCD2_HISTORY]"

    def test_missing_profile_flagged(self):
        text = broken(self.STATUS, "Entity: OrderStatus               [kind: Reference]")
        self.assertIn("missing-profile", rules_for(text))

    def test_unknown_profile_flagged(self):
        text = broken(self.STATUS, self.STATUS.replace("SCD2_HISTORY", "SCD3"))
        self.assertIn("invalid-value", rules_for(text))

    def test_profile_departure_needs_a_decision(self):
        text = broken(self.STATUS, self.STATUS.replace("SCD2_HISTORY", "CURRENT_STATE"))
        self.assertIn("unrecorded-departure", rules_for(text))

    def test_a_recorded_departure_is_accepted(self):
        text = broken(self.STATUS, self.STATUS.replace("SCD2_HISTORY", "CURRENT_STATE"))
        text = text.replace("Decision: DD-SEARCH-001", "Decision: DD-DOMAIN-001\n"
                            "  Title: Order statuses hold present values only\n"
                            "  Category: SCHEMA\n  Module: domain\n  Applies to: OrderStatus\n"
                            "  Context: Reference entities default to SCD2_HISTORY.\n"
                            "  Rationale: Status labels are never reworded.\n```\n\n```\n"
                            "Decision: DD-SEARCH-001", 1)
        self.assertNotIn("unrecorded-departure", rules_for(text))

    def test_allocation_departure_needs_a_decision(self):
        text = broken("[kind: History] [profile: SCD2_BITEMPORAL]",
                      "[kind: History] [profile: SCD2_BITEMPORAL] [allocation: inline]")
        self.assertIn("unrecorded-departure", rules_for(text))

    def test_unresolved_reference_flagged(self):
        text = broken("[required] [-> Customer]  // the ordering customer",
                      "[required] [-> Client]  // the ordering customer")
        self.assertIn("unresolved-reference", rules_for(text))

    def test_multi_target_reference_needs_a_discriminator(self):
        text = broken("[required] [-> Customer]  // the ordering customer",
                      "[required] [-> Customer | Product]  // the ordering customer")
        self.assertIn("missing-discriminator", rules_for(text))

    def test_unknown_function_in_a_derivation_flagged(self):
        text = broken("[derive: count_related(", "[derive: rolling_count(")
        self.assertIn("invalid-expression", rules_for(text))

    def test_aggregate_in_a_row_derivation_flagged(self):
        text = broken("[derive: count_related(Order, Order.ordered_dts, 90 days) /",
                      "[derive: sum(Order.order_total) /")
        self.assertIn("invalid-expression", rules_for(text))

    def test_unresolved_attribute_in_a_derivation_flagged(self):
        text = broken("Order, Order.ordered_dts, 90 days)", "Order, Order.placed_dts, 90 days)")
        self.assertIn("invalid-expression", rules_for(text))

    def test_timestamp_not_named_dts_flagged(self):
        text = broken("  ordered_dts      : Timestamp", "  ordered_at       : Timestamp")
        self.assertIn("timestamp-name", rules_for(text))

    def test_prohibited_name_flagged(self):
        text = broken("  ordered_dts      : Timestamp [required]",
                      "  ordered_dts      : Timestamp [required]\n  valid_from : Date [optional]")
        self.assertIn("prohibited-name", rules_for(text))

    def test_effective_date_outside_current_state_flagged(self):
        text = broken("  ordered_dts      : Timestamp [required]",
                      "  ordered_dts      : Timestamp [required]\n  effective_date : Date [optional]")
        self.assertIn("prohibited-name", rules_for(text))

    def test_missing_volume_flagged(self):
        text = broken("    natural:   order_status_code\n\n  Volume:\n    initial: 8\n"
                      "    growth:  0 per year\n    horizon: 3 years\n",
                      "    natural:   order_status_code\n")
        self.assertIn("missing-section", rules_for(text))

    def test_malformed_growth_flagged(self):
        self.assertIn("invalid-value", rules_for(broken("growth:  2000 per month", "growth:  lots")))

    def test_feature_group_without_derived_features_flagged(self):
        text = re.sub(r" \[derive: [^\n]*?\]  //", "  //", spec_text(), count=1)
        self.assertNotEqual(text, spec_text(), "fixture should carry a derivation to strip")
        self.assertIn("missing-field", rules_for(text))


class NotationBlocks(unittest.TestCase):
    def test_module_without_its_required_block_flagged(self):
        text = re.sub(r"```\nOrientation: -\n.*?```", "", spec_text(), flags=re.S)
        self.assertIn("missing-block", rules_for(text))

    def test_required_field_missing_flagged(self):
        self.assertIn("missing-field", rules_for(broken("  Similarity: cosine\n", "")))

    def test_unknown_field_flagged(self):
        text = broken("  Similarity: cosine\n", "  Similarity: cosine\n  Colour: blue\n")
        self.assertIn("unknown-field", rules_for(text))

    def test_value_outside_enumeration_flagged(self):
        self.assertIn("invalid-value", rules_for(broken("Similarity: cosine", "Similarity: manhattan")))

    def test_measure_must_be_an_aggregate(self):
        text = broken("Measure:     sum(Order.order_total)", "Measure:     Order.order_total")
        self.assertIn("invalid-value", rules_for(text))

    def test_metric_reference_must_resolve(self):
        text = broken("ratio(metric('Order Value')", "ratio(metric('Order Worth')")
        self.assertIn("invalid-value", rules_for(text))

    def test_thresholds_must_fit_the_check(self):
        text = broken("- freshness(Order): warn after 24 hours, fail after 48 hours",
                      "- freshness(Order): pass >= 0.9, warn >= 0.8")
        self.assertIn("invalid-value", rules_for(text))

    def test_weights_must_sum_to_100(self):
        self.assertIn("invalid-value", rules_for(broken("completeness: 40%", "completeness: 45%")))

    def test_flow_target_must_resolve(self):
        text = broken("-> load_orders -> Order", "-> load_orders -> Orders")
        self.assertIn("invalid-value", rules_for(text))

    def test_retention_must_be_a_duration(self):
        self.assertIn("invalid-value", rules_for(broken("AgentInteraction: 1 years",
                                                        "AgentInteraction: a while")))

    def test_retention_names_an_entity(self):
        self.assertIn("invalid-value", rules_for(broken("AgentInteraction: 1 years",
                                                        "AgentChat: 1 years")))

    def test_decision_id_shape_enforced(self):
        self.assertIn("invalid-value", rules_for(broken("Decision: DD-SEARCH-001",
                                                        "Decision: SEARCH-1")))

    def test_embedding_dimensions_match_a_vector(self):
        self.assertIn("invalid-value", rules_for(broken("Dimensions: 768", "Dimensions: 512")))

    def test_unnamed_block_takes_no_name(self):
        self.assertIn("invalid-value", rules_for(broken("Orientation: -", "Orientation: main")))

    def test_duplicate_block_flagged(self):
        block = re.search(r"```\nRuntime: -\n.*?```", spec_text(), flags=re.S).group(0)
        self.assertIn("duplicate-block", rules_for(broken(block, block + "\n\n" + block)))


class PlatformNeutrality(unittest.TestCase):
    def test_platform_sql_in_a_specification_flagged(self):
        text = spec_text().replace("order_total      : Decimal(12,2)",
                                    "order_total      : DECIMAL(12,2) NOT NULL")
        rules = [f.rule for f in lint_spec(REFERENCE)]  # baseline is clean
        self.assertEqual(rules, [])
        from design_lint import lint_text
        self.assertTrue(any(f.rule == "vendor-token" for f in lint_text("b.md", text)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
