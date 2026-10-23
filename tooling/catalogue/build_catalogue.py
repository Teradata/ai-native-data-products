#!/usr/bin/env python3
"""build_catalogue: derive corpus navigation from frontmatter.

Every design document declares its own identity in frontmatter (see the Design
Language). This script reads those declarations and writes the navigation
tables into the hierarchy READMEs, between marker comments:

    <!-- catalogue:start -->
    ... generated ...
    <!-- catalogue:end -->

Nothing between the markers is hand-maintained. Adding a module or a pattern means
adding a document; the catalogue follows.

It also keeps an index near the top of every README longer than 100 lines, between

    <!-- index:start -->
    <!-- index:end -->

An agent may read only a file's first 100 lines before deciding whether to read on, so the
index names every `##` section with the line it starts on. The rows and line numbers are
generated; each row's "Covers" cell is written by hand and kept across regenerations (a new
row starts with the section's `###` headings). A long README without an index, or one whose
index ends past line 100, fails. Run:

    python tooling/catalogue/build_catalogue.py          # rewrite in place
    python tooling/catalogue/build_catalogue.py --check  # fail if out of date

`--check` is the CI form: it reports drift without touching the tree, so a document
added without regenerating the catalogue fails the build.

Stdlib only, like the linter it sits beside.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validation"))

from design_lint import (  # noqa: E402
    is_design_document,
    parse_frontmatter,
    read_document_capabilities,
    read_document_decisions,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
START = "<!-- catalogue:start -->"
END = "<!-- catalogue:end -->"
INDEX_START = "<!-- index:start -->"
INDEX_END = "<!-- index:end -->"
INDEX_LIMIT = 100  # the lines an agent reads before deciding where to look
SKIP_DIRS = {".git", "build", "__pycache__", "node_modules"}

TYPE_HEADINGS = [
    ("core", "Core"),
    ("pattern", "Patterns"),
    ("module", "Modules"),
    ("platform-profile", "Platform profile"),
    ("implementation", "Bindings"),
]


def collect(roots: List[Path]) -> List[Tuple[Path, dict]]:
    """Every design document under `roots`, with its identity and its capability graph.

    Identity comes from frontmatter; the graph is read from the body tables, which are
    where it is stated (Design Language: What frontmatter is not for). Collecting it here is the point of
    the catalogue: an agent gets the whole graph in one file instead of opening fifteen.
    """
    found = []
    for root in roots:
        if not root.exists():
            continue
        for md in sorted(root.rglob("*.md")):
            if not is_design_document(md):
                continue
            text = md.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(text)
            if not fm:
                continue
            caps = read_document_capabilities(text)
            entry = dict(fm)
            entry["provides"] = sorted(set(caps["provides"]))
            entry["requires"] = sorted(set(caps["requires"]))
            # The design language shows an illustrative decisions table to define the
            # notation; it settles nothing, so it is not read as a declaration.
            entry["decisions"] = ([] if fm.get("anchor") == "design-language"
                                  else [d for d, _, _ in read_document_decisions(text)])
            found.append((md, entry))
    return found


def _cell(fm: dict, key: str) -> str:
    value = fm.get(key)
    if not value:
        return "-"
    if isinstance(value, list):
        names = []
        for item in value:
            names.append(item.get("capability", "?") if isinstance(item, dict) else str(item))
        return ", ".join(f"`{n}`" for n in names) if names else "-"
    return str(value)


def render(docs: List[Tuple[Path, dict]], relative_to: Path) -> str:
    """A section per document type, listing anchor, status, and capability flow."""
    by_type: Dict[str, List[Tuple[Path, dict]]] = {}
    for path, fm in docs:
        by_type.setdefault(fm.get("type", "unknown"), []).append((path, fm))

    blocks = []
    for type_key, heading in TYPE_HEADINGS:
        entries = by_type.get(type_key)
        if not entries:
            continue
        lines = [f"### {heading}", "",
                 "| Document | Anchor | Status | Provides | Requires | Decisions |",
                 "|---|---|---|---|---|---|"]
        for path, fm in sorted(entries, key=lambda e: e[1].get("anchor", "")):
            try:
                href = path.relative_to(relative_to).as_posix()
            except ValueError:
                href = ("../" * len(relative_to.relative_to(REPO_ROOT).parts)
                        + path.relative_to(REPO_ROOT).as_posix())
            title = fm.get("title", path.stem)
            normative = "" if str(fm.get("normative", "")).lower() == "true" else " *(advisory)*"
            lines.append(
                f"| [{title}]({href}){normative} | `{fm.get('anchor', '?')}` | "
                f"{fm.get('status', '?')} | {_cell(fm, 'provides')} | {_cell(fm, 'requires')} | "
                f"{_cell(fm, 'decisions')} |"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def inject(readme: Path, text: str, body: str) -> str:
    """The text with its catalogue region replaced."""
    if START not in text or END not in text:
        print(f"warning: no catalogue markers in {readme}", file=sys.stderr)
        return text
    head, _, rest = text.partition(START)
    _, _, tail = rest.partition(END)
    return f"{head}{START}\n\n{body}\n\n{END}{tail}"


def _slug(heading: str) -> str:
    """The anchor GitHub gives a heading."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def _sections(lines: List[str]) -> List[Tuple[int, str, List[str]]]:
    """Each `##` heading outside code fences: its 0-based line, its text and its `###` headings."""
    found, fenced = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            found.append((i, line[3:].strip(), []))
        elif not fenced and line.startswith("### ") and found:
            found[-1][2].append(line[4:].strip())
    return found


def index(readme: Path, text: str) -> Tuple[str, List[str]]:
    """The text with its index regenerated, and what is wrong that regeneration cannot fix.
    The index lists the `##` sections after it, each with the line it starts on."""
    where = readme.relative_to(REPO_ROOT).as_posix()
    if INDEX_START not in text or INDEX_END not in text:
        if len(text.splitlines()) > INDEX_LIMIT:
            return text, [f"{where} is longer than {INDEX_LIMIT} lines and has no index; add "
                          f"{INDEX_START} and {INDEX_END} after its introduction"]
        return text, []
    head, _, rest = text.partition(INDEX_START)
    old, _, tail = rest.partition(INDEX_END)
    covers = dict(re.findall(r"^\| \d+ \| \[.*\]\(#([^)]+)\) \| (.*) \|$", old, re.M))
    sections = _sections(tail.split("\n"))

    def block(numbers):
        rows = ["| Line | Section | Covers |", "|---:|---|---|"]
        for n, (_, title, subs) in zip(numbers, sections):
            label = title.replace("|", "\\|")
            rows.append(f"| {n} | [{label}](#{_slug(title)}) | {covers.get(_slug(title), ' · '.join(subs))} |")
        return f"{head}{INDEX_START}\n" + "\n".join(rows) + f"\n{INDEX_END}"

    # The rows' count fixes where everything after the index lands, so one draft gives the lines.
    first = block([0] * len(sections)).count("\n")
    updated = block([first + i + 1 for i, _, _ in sections]) + tail
    problems = []
    end = updated.split(INDEX_END)[0].count("\n") + 1
    if end > INDEX_LIMIT:
        problems.append(f"{where}: its index ends on line {end}, past line {INDEX_LIMIT}")
    return updated, problems


def main(argv: List[str]) -> int:
    check = "--check" in argv
    design, implementation = REPO_ROOT / "design", REPO_ROOT / "implementation"
    targets = [
        (design / "README.md", collect([design]), design),
    ]
    targets.extend((platform / "README.md", collect([platform]), platform)
                   for platform in sorted(implementation.iterdir()) if platform.is_dir())

    catalogues = {readme: (docs, base) for readme, docs, base in targets if readme.exists()}
    readmes = sorted(p for p in REPO_ROOT.rglob("README.md")
                     if not any(part in SKIP_DIRS or part.startswith(".") for part in p.relative_to(REPO_ROOT).parts))

    stale, problems = [], []
    for readme in readmes:
        text = readme.read_text(encoding="utf-8")
        updated = text
        if readme in catalogues:
            updated = inject(readme, updated, render(*catalogues[readme]))
        updated, found = index(readme, updated)  # last: it numbers the lines the catalogue leaves
        problems += found
        if updated != text:
            stale.append(readme.relative_to(REPO_ROOT).as_posix())
            if not check:
                readme.write_text(updated, encoding="utf-8", newline="")

    for problem in problems:
        print(f"index: {problem}", file=sys.stderr)
    if check and stale:
        print("catalogue out of date: " + ", ".join(stale), file=sys.stderr)
        print("run: python tooling/catalogue/build_catalogue.py", file=sys.stderr)
    if problems or (check and stale):
        return 1
    print("catalogue: " + ("up to date" if not stale else "rewrote " + ", ".join(stale)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
