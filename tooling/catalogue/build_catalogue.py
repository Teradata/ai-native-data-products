#!/usr/bin/env python3
"""build_catalogue — derive corpus navigation from frontmatter.

Every design document declares its own identity in frontmatter (Design Language
Section 3.1). This script reads those declarations and writes the navigation
tables into the hierarchy READMEs, between marker comments:

    <!-- catalogue:start -->
    ... generated ...
    <!-- catalogue:end -->

Nothing between the markers is hand-maintained. Adding a module or a pattern means
adding a document; the catalogue follows. Run:

    python tooling/catalogue/build_catalogue.py          # rewrite in place
    python tooling/catalogue/build_catalogue.py --check  # fail if out of date

`--check` is the CI form: it reports drift without touching the tree, so a document
added without regenerating the catalogue fails the build.

Stdlib only, like the linter it sits beside.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validation"))

from design_lint import is_design_document, parse_frontmatter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
START = "<!-- catalogue:start -->"
END = "<!-- catalogue:end -->"

TYPE_HEADINGS = [
    ("core", "Core"),
    ("pattern", "Patterns"),
    ("module", "Modules"),
    ("platform-profile", "Platform profile"),
    ("implementation", "Bindings"),
]


def collect(roots: List[Path]) -> List[Tuple[Path, dict]]:
    """Every design document under `roots`, with its frontmatter."""
    found = []
    for root in roots:
        if not root.exists():
            continue
        for md in sorted(root.rglob("*.md")):
            if not is_design_document(md):
                continue
            fm, _ = parse_frontmatter(md.read_text(encoding="utf-8"))
            if fm:
                found.append((md, fm))
    return found


def _cell(fm: dict, key: str) -> str:
    value = fm.get(key)
    if not value:
        return "—"
    if isinstance(value, list):
        names = []
        for item in value:
            names.append(item.get("capability", "?") if isinstance(item, dict) else str(item))
        return ", ".join(f"`{n}`" for n in names) if names else "—"
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
        lines = [f"### {heading}", "", "| Document | Anchor | Status | Provides | Requires |",
                 "|---|---|---|---|---|"]
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
                f"{fm.get('status', '?')} | {_cell(fm, 'provides')} | {_cell(fm, 'requires')} |"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def inject(readme: Path, body: str, check: bool) -> bool:
    """Replace the marked region. Returns True when the file is (or would be) changed."""
    text = readme.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print(f"warning: no catalogue markers in {readme}", file=sys.stderr)
        return False
    head, _, rest = text.partition(START)
    _, _, tail = rest.partition(END)
    updated = f"{head}{START}\n\n{body}\n\n{END}{tail}"
    if updated == text:
        return False
    if not check:
        readme.write_text(updated, encoding="utf-8", newline="")
    return True


def main(argv: List[str]) -> int:
    check = "--check" in argv
    design, implementation = REPO_ROOT / "design", REPO_ROOT / "implementation"
    targets = [
        (design / "README.md", collect([design]), design),
        (implementation / "teradata" / "README.md",
         collect([implementation / "teradata"]), implementation / "teradata"),
    ]

    stale = []
    for readme, docs, base in targets:
        if not readme.exists():
            continue
        if inject(readme, render(docs, base), check):
            stale.append(readme.relative_to(REPO_ROOT).as_posix())

    if check and stale:
        print("catalogue out of date: " + ", ".join(stale), file=sys.stderr)
        print("run: python tooling/catalogue/build_catalogue.py", file=sys.stderr)
        return 1
    print("catalogue: " + ("up to date" if not stale else "rewrote " + ", ".join(stale)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
