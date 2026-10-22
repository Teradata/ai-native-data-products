"""`conformance.py --trust-committed`: when it may stand a committed live run in for engine
tests that cannot run, and what it never lets through.

It lives in the validation suite rather than the binding suite: the binding suite is what
the conformance reports record, so a test there would change every binding's report.
"""
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tooling" / "bindings"))

from conformance import ENGINE_LINE, committed_engine, trust  # noqa: E402

REPORT = f"""{ENGINE_LINE} Teradata 20.00 through teradatasql 20.0.

## Evidence

### Engine behaviour

| Test | Outcome |
|---|---|
| ITSD deploys and every check passes | pass |
| Mutations are detected | pass |

### Package

| Test | Outcome |
|---|---|
| Every template is declared or caller rendered | fail |
"""


class Result:
    """The parts of a recorded test run that trust() reads and writes."""

    def __init__(self, outcomes):
        self.outcomes, self.labels, self.versions = defaultdict(dict), {}, {}
        for (cls, method, label), slot in outcomes.items():
            self.outcomes[(cls, method)] = slot
            self.labels[(cls, method)] = label


class CommittedEngine(unittest.TestCase):
    def test_a_clean_live_run_is_read_with_its_engine_tests(self):
        version, rows = committed_engine(REPORT)
        self.assertEqual(version, "Teradata 20.00 through teradatasql 20.0")
        self.assertEqual(rows, {"ITSD deploys and every check passes": "pass", "Mutations are detected": "pass"})

    def test_a_report_with_no_engine_run_is_not_trusted(self):
        text = REPORT.replace("Teradata 20.00 through teradatasql 20.0.", "none: the engine tests did not run.")
        self.assertIsNone(committed_engine(text))

    def test_a_live_run_with_an_engine_test_not_passing_is_not_trusted(self):
        for status in ("skip", "fail"):
            with self.subTest(status=status):
                self.assertIsNone(committed_engine(REPORT.replace("detected | pass", f"detected | {status}")))


class Trust(unittest.TestCase):
    def test_only_skipped_engine_tests_the_committed_run_carries_become_passes(self):
        result = Result({
            ("Teradata", "test_itsd", "ITSD deploys and every check passes"): {"teradata": ("skip", "no DSN")},
            ("Teradata", "test_new", "A new engine test"): {"teradata": ("skip", "no DSN")},
            ("Teradata", "test_mut", "Mutations are detected"): {"teradata": ("fail", "broke")},
        })
        self.assertEqual(trust(result, "teradata", committed_engine(REPORT)), 1)
        self.assertEqual(result.outcomes[("Teradata", "test_itsd")]["teradata"], ("pass", None))
        self.assertEqual(result.outcomes[("Teradata", "test_new")]["teradata"][0], "skip",
                         "an engine test the committed run does not carry needs a new live run")
        self.assertEqual(result.outcomes[("Teradata", "test_mut")]["teradata"][0], "fail",
                         "a test that ran here keeps its own outcome")
        self.assertEqual(result.versions["teradata"], "Teradata 20.00 through teradatasql 20.0")


if __name__ == "__main__":
    unittest.main()
