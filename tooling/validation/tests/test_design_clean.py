"""Integration check: the whole design/ tree must pass the linter.

This is the gate for every worked module: converting a module means its design
document lints clean here. Run:

    python -m unittest discover -s tooling/validation/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design_lint import lint_paths  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DESIGN_DIR = REPO_ROOT / "design"
IMPLEMENTATION_DIR = REPO_ROOT / "implementation"


class DesignTreeIsClean(unittest.TestCase):
    def test_design_tree_has_no_platform_sql(self):
        findings = lint_paths([str(DESIGN_DIR)])
        self.assertEqual(
            findings, [],
            "design/ must be free of platform SQL:\n"
            + "\n".join(str(f) for f in findings),
        )

    def test_implementation_tree_uses_canonical_temporal_names(self):
        """TLM-04 over the whole corpus.

        Both trees are linted together on purpose: the prohibited names are read from
        the temporal pattern in `design/`, so linting `implementation/` alone would
        enforce nothing and pass for the wrong reason.
        """
        findings = [f for f in lint_paths([str(DESIGN_DIR), str(IMPLEMENTATION_DIR)])
                    if f.rule == "tlm-04"]
        self.assertEqual(
            findings, [],
            "implementation/ must use the canonical temporal column names:\n"
            + "\n".join(str(f) for f in findings),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
