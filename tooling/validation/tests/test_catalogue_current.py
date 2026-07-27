"""Integration check: the generated catalogue matches the frontmatter it derives from.

Adding or changing a design document without regenerating the catalogue leaves the
hierarchy READMEs lying about what the corpus contains — exactly the staleness that
moving navigation into frontmatter is meant to prevent. Run:

    python -m unittest discover -s tooling/validation/tests
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "catalogue"))

from build_catalogue import main as build_main  # noqa: E402


class CatalogueIsCurrent(unittest.TestCase):
    def test_catalogue_matches_frontmatter(self):
        self.assertEqual(
            build_main(["--check"]), 0,
            "the generated catalogue is out of date — run:\n"
            "    python tooling/catalogue/build_catalogue.py",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
