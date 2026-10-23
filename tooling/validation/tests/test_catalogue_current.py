"""Integration check: the generated catalogue matches the frontmatter it derives from.

Adding or changing a design document without regenerating the catalogue leaves the
hierarchy READMEs lying about what the corpus contains: exactly the staleness that
moving navigation into frontmatter is meant to prevent. Run:

    python -m unittest discover -s tooling/validation/tests
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "catalogue"))

from build_catalogue import INDEX_END, INDEX_LIMIT, INDEX_START, index, main as build_main  # noqa: E402

README = REPO_ROOT / "examples" / "README.md"  # any path inside the repository


class CatalogueIsCurrent(unittest.TestCase):
    def test_catalogue_matches_frontmatter(self):
        self.assertEqual(
            build_main(["--check"]), 0,
            "the generated catalogue is out of date: run:\n"
            "    python tooling/catalogue/build_catalogue.py",
        )


class ReadmeIndex(unittest.TestCase):
    """An agent may read only a file's first 100 lines, so a longer README opens with an index
    giving the line each section starts on."""

    def test_each_section_is_listed_on_the_line_it_starts(self):
        text = (f"# T\n\nIntro.\n\n{INDEX_START}\n{INDEX_END}\n\n## First\n\ntext\n\n### Part\n\n"
                f"## Second | more\n\ntext\n")
        updated, problems = index(README, text)
        self.assertEqual(problems, [])
        lines = updated.split("\n")
        rows = [r for r in lines if r.startswith("| ") and "](#" in r]
        self.assertEqual(len(rows), 2)
        for row, title in zip(rows, ("## First", "## Second | more")):
            self.assertEqual(lines[int(row.split("|")[1]) - 1], title)
        self.assertIn("| Part |", rows[0], "a new row starts from the section's ### headings")

    def test_a_hand_written_covers_cell_survives(self):
        text = f"{INDEX_START}\n| 9 | [First](#first) | Kept words |\n{INDEX_END}\n\n## First\n"
        self.assertIn("| Kept words |", index(README, text)[0])

    def test_a_long_readme_without_an_index_fails(self):
        _, problems = index(README, "# T\n" + "line\n" * INDEX_LIMIT)
        self.assertTrue(problems)

    def test_an_index_ending_past_the_limit_fails(self):
        text = "# T\n" + "line\n" * INDEX_LIMIT + f"{INDEX_START}\n{INDEX_END}\n## First\n"
        self.assertTrue(index(README, text)[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
