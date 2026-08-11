#!/usr/bin/env python3
"""verify_skill: check that this repository is a well-formed agent skill.

The standards are no longer compiled into skills: the repository *is* the skill, read
progressively through `SKILL.md` and the role files in `roles/`. Nothing is rewritten,
so there is nothing to check for paraphrase or loss. What remains checkable is whether
the package is well formed and whether its routing resolves.

That second one is the check that matters. The failure mode of a routed skill is a
dangling pointer: `SKILL.md` sends an agent to a file that is not there, and the agent
either guesses or gives up. The compiled packages shipped exactly this defect - the
review skill told its agent to run a linter that was not in the bundle - so it is worth
a build gate.

    python tooling/skill/verify_skill.py              # checks this repository
    python tooling/skill/verify_skill.py --root path  # or somewhere else

Exit code is 0 when the package conforms, 1 when it does not, 2 when there is no
SKILL.md to check, so a missing skill is not mistaken for a pass.

Stdlib only, like the tools it sits beside.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))

from design_lint import parse_frontmatter  # noqa: E402

SKILL_NAME = "ai-native-data-product"
ROLES = ("design", "build", "review", "access")
# SKILL.md is read on every invocation; the role files once per session. Both are the
# only context this package spends unconditionally, so both are budgeted.
MAX_SKILL_LINES = 120
MAX_ROLE_LINES = 150
MIN_DESCRIPTION_CHARS = 120

PLATFORMS = ("teradata",)
MODULES = ("domain", "search", "prediction", "observability", "semantic", "memory")
PATTERNS = ("access-layer", "object-placement", "physical-storage",
            "temporal-lifecycle-metadata", "validation")

# A routed path is a backticked token containing a slash: `design/core/MASTER_DESIGN.md`,
# `implementation/{platform}/modules/{module}/`. Prose mentions of a directory without
# backticks are not routing and are not checked.
PATH_RE = re.compile(r"`([A-Za-z_][\w./{}-]*/[\w./{}-]*)`")
# A section reference is a backticked path immediately followed by one or more §N.
SECTION_RE = re.compile(r"`([\w./{}-]+\.md)`[^`\n]{0,40}?§(\d+)")
HEADING_RE = re.compile(r"^##\s+(\d+)\.", re.M)
SKIP_PREFIXES = ("http://", "https://", "N/A")


class Finding(NamedTuple):
    rule: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: [{self.rule}] {self.message}"


def expand(path: str) -> List[str]:
    """Expand the corpus's placeholders into the concrete paths they stand for."""
    out = [path]
    for token, values in (("{platform}", PLATFORMS),
                          ("{module}", MODULES),
                          ("{pattern}", PATTERNS)):
        if any(token in p for p in out):
            out = [p.replace(token, v) for p in out for v in values]
    return out


def check_frontmatter(root: Path) -> List[Finding]:
    skill = root / "SKILL.md"
    fm, _ = parse_frontmatter(skill.read_text(encoding="utf-8"))
    fm = fm or {}
    found = []

    def scalar(key: str) -> str:
        """An absent or empty frontmatter scalar parses as `[]`, not `''`."""
        value = fm.get(key, "")
        return value.strip() if isinstance(value, str) else ""

    name = scalar("name")
    if name != SKILL_NAME:
        found.append(Finding(
            "skill-frontmatter", "SKILL.md",
            f"name is {name or '(absent)'!r}, expected {SKILL_NAME!r}. The name is the "
            f"handle users and docs cite; it must stay stable across versions."))
    description = scalar("description")
    if not description:
        found.append(Finding("skill-frontmatter", "SKILL.md",
                             "no description. It is what decides whether the skill loads."))
    elif len(description) < MIN_DESCRIPTION_CHARS:
        found.append(Finding(
            "skill-description", "SKILL.md",
            f"description is {len(description)} chars. It carries all four roles' "
            f"vocabularies, so an under-described role will under-trigger."))
    else:
        for role in ROLES:
            if role not in description.lower():
                found.append(Finding(
                    "skill-description", "SKILL.md",
                    f"description never says {role!r}; that role will under-trigger."))
    return found


def check_budgets(root: Path) -> List[Finding]:
    found = []
    for path, budget in [(root / "SKILL.md", MAX_SKILL_LINES)] + \
                        [(root / "roles" / f"{r}.md", MAX_ROLE_LINES) for r in ROLES]:
        if not path.exists():
            continue
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > budget:
            found.append(Finding(
                "too-long", path.name,
                f"{lines} lines, budget {budget}. Detail belongs in the corpus, which is "
                f"read on demand; this file is not."))
    return found


def check_roles_present(root: Path) -> List[Finding]:
    found = []
    for role in ROLES:
        path = root / "roles" / f"{role}.md"
        if not path.exists():
            found.append(Finding("role-missing", "roles/",
                                 f"no {role}.md, so SKILL.md cannot route that role."))
    return found


def routing_files(root: Path) -> List[Path]:
    files = [root / "SKILL.md"]
    files += sorted((root / "roles").glob("*.md")) if (root / "roles").is_dir() else []
    return [f for f in files if f.exists()]


def check_routes(root: Path) -> List[Finding]:
    """Every path the routing names must exist. This is the check that earns its keep."""
    found = []
    for path in routing_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for raw in sorted(set(PATH_RE.findall(text))):
            if raw.startswith(SKIP_PREFIXES):
                continue
            candidates = expand(raw)
            if not any((root / c.rstrip("/")).exists() for c in candidates):
                shown = raw if len(candidates) == 1 else f"{raw} (no expansion exists)"
                found.append(Finding("dangling-route", rel,
                                     f"routes to {shown}, which is not in the repository."))
    return found


def check_sections(root: Path) -> List[Finding]:
    """A `file.md` §N reference must land on a real `## N.` heading in that file."""
    found = []
    for path in routing_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for raw, number in sorted(set(SECTION_RE.findall(text))):
            for candidate in expand(raw):
                target = root / candidate
                if not target.exists():
                    continue  # already reported by check_routes
                headings = set(HEADING_RE.findall(target.read_text(encoding="utf-8")))
                if number not in headings:
                    found.append(Finding(
                        "dangling-section", rel,
                        f"cites {candidate} §{number}, which has no such section."))
    return found


def verify(root: Path) -> List[Finding]:
    found = []
    found += check_frontmatter(root)
    found += check_budgets(root)
    found += check_roles_present(root)
    found += check_routes(root)
    found += check_sections(root)
    return found


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Check this repository is a well-formed skill.")
    ap.add_argument("--root", type=Path, default=REPO_ROOT,
                    help="repository root to check (default: this repository)")
    args = ap.parse_args(argv)
    root = args.root.resolve()

    if not (root / "SKILL.md").exists():
        print(f"No SKILL.md in {root}. Nothing to verify.", file=sys.stderr)
        return 2

    found = verify(root)
    for finding in found:
        print(finding)
    if found:
        print(f"\n{len(found)} problem(s).", file=sys.stderr)
        return 1
    print("Skill package conforms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
