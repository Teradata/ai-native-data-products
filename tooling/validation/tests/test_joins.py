"""How an entity's `[-> Target]` attributes combine into joins (tooling/evals/joins.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals"))
from joins import join_groups  # noqa: E402


class JoinGroups(unittest.TestCase):
    def test_a_bare_reference_is_a_whole_join_on_its_own(self):
        groups = join_groups([("customer_id", "Customer", None), ("note", None, None)])
        self.assertEqual(groups, [{"name": "customer_id", "target": "Customer", "targets": ["Customer"],
                                   "attributes": ["customer_id"], "target_attributes": None, "kind": "bare"}])

    def test_named_attributes_of_one_target_form_one_ordered_join(self):
        groups = join_groups([("product_code", "Run.product_code", None), ("x", None, None),
                              ("producer_id", "Run.producer_id", None), ("run_id", "Run.run_id", None)])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["attributes"], ["product_code", "producer_id", "run_id"])
        self.assertEqual(groups[0]["target_attributes"], ["product_code", "producer_id", "run_id"])
        self.assertEqual((groups[0]["name"], groups[0]["kind"]), ("product_code", "named"))

    def test_a_join_name_keeps_two_joins_to_one_target_apart(self):
        groups = join_groups([("a_id", "T.id", "first"), ("b_id", "T.id", "second"), ("c_id", "T.k", "first")])
        self.assertEqual([(g["name"], g["attributes"], g["target_attributes"]) for g in groups],
                         [("first", ["a_id", "c_id"], ["id", "k"]), ("second", ["b_id"], ["id"])])

    def test_a_join_without_a_name_groups_by_target(self):
        groups = join_groups([("a_id", "T.id", None), ("b_id", "U.id", None), ("c_id", "T.k", None)])
        self.assertEqual([(g["target"], g["attributes"]) for g in groups], [("T", ["a_id", "c_id"]), ("U", ["b_id"])])

    def test_a_bare_and_a_named_join_to_one_target_stay_separate(self):
        groups = join_groups([("a_id", "T", None), ("b_id", "T.id", None)])
        self.assertEqual([g["kind"] for g in groups], ["bare", "named"])

    def test_a_multi_target_reference_is_one_attribute(self):
        groups = join_groups([("subject", "A | B", None)])
        self.assertEqual((groups[0]["kind"], groups[0]["targets"], groups[0]["target"]), ("multi", ["A", "B"], None))


if __name__ == "__main__":
    unittest.main()
