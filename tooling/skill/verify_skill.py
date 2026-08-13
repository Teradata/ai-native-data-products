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
from typing import Dict, List, NamedTuple, Set

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

# The frontmatter is flat by design: exactly these two keys, one line each.
FRONTMATTER_KEYS = ("name", "description")

# A routed path is a backticked token containing a slash: `design/core/MASTER_DESIGN.md`,
# `implementation/{platform}/modules/{module}/`. Prose mentions of a directory without
# backticks are not routing and are not checked.
PATH_RE = re.compile(r"`([A-Za-z_][\w./{}-]*/[\w./{}-]*)`")
# A section reference is a backticked path immediately followed by one or more §N.
SECTION_RE = re.compile(r"`([\w./{}-]+\.md)`[^`\n]{0,40}?§(\d+)")
HEADING_RE = re.compile(r"^##\s+(\d+)\.", re.M)
SKIP_PREFIXES = ("http://", "https://", "N/A")
FRONTMATTER_BLOCK_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
# A top-level frontmatter line is a `key:` at column 0, and the key must be one the flat
# frontmatter declares. Anything else is a plain scalar that wrapped onto a new line without
# indentation, which silently truncates the value it belongs to - even when that wrapped
# fragment happens to open `word:` and so looks like a key. `design_lint.parse_frontmatter`
# is a lenient subset parser and accepts the wrap; a real YAML loader - the one the skill
# installer uses - does not.
YAML_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:")


class Finding(NamedTuple):
    rule: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: [{self.rule}] {self.message}"


def discover_placeholders(root: Path) -> Dict[str, List[str]]:
    """Derive placeholder values from the checkout, never a hardcoded list.

    A new platform, module or pattern added to the corpus must be picked up without
    editing this file: a route that resolves only under the new value would otherwise be
    reported as a false `dangling-route`, failing the build on a legitimate change. Values
    are read from both the design tree (the source of truth) and the implementation tree,
    because a route may name an area one carries and the other does not.
    """
    impl = root / "implementation"

    def impl_children(kind: str) -> Set[str]:
        return {d.name for d in impl.glob(f"*/{kind}/*") if d.is_dir()}

    platforms = sorted(p.name for p in impl.glob("*") if p.is_dir())
    modules = sorted({p.stem for p in (root / "design" / "modules").glob("*.md")}
                     | impl_children("modules"))
    patterns = sorted({p.stem for p in (root / "design" / "patterns").glob("*.md")}
                      | impl_children("patterns"))
    return {"{platform}": platforms, "{module}": modules, "{pattern}": patterns}


def expand(path: str, tokens: Dict[str, List[str]]) -> List[str]:
    """Expand the corpus's placeholders into the concrete paths they stand for."""
    out = [path]
    for token, values in tokens.items():
        if any(token in p for p in out):
            out = [p.replace(token, v) for p in out for v in values]
    return out


def check_frontmatter_yaml(root: Path) -> List[Finding]:
    """Reject frontmatter a real YAML loader would refuse.

    The installer parses this with a proper loader, so leniency here buys a package that
    verifies clean and then fails to install. The wrapped-scalar case is the one that bites:
    a long `description:` reflowed onto an unindented second line parses as a new key.
    """
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    m = FRONTMATTER_BLOCK_RE.match(text)
    if not m:
        return [Finding("skill-frontmatter", "SKILL.md",
                        "no YAML frontmatter block. It must open the file.")]
    found = []
    for offset, line in enumerate(m.group(1).splitlines(), start=2):
        if not line.strip():
            continue
        key = YAML_KEY_RE.match(line)
        # A wrapped continuation can itself begin `word:` and so parse as a key. Because the
        # frontmatter is flat, only the known keys are legitimate at column 0; anything else
        # is a stray line, whether it opens with a colon-word or not.
        if key and key.group(1) in FRONTMATTER_KEYS:
            continue
        found.append(Finding(
            "skill-frontmatter", f"SKILL.md:{offset}",
            f"{line.strip()[:48]!r}... is not a `name:` or `description:` line at column 0. "
            f"This frontmatter is flat - `name` and `description`, one line each. A value "
            f"reflowed onto a second line breaks it: unindented it ends the scalar, and "
            f"indented it is folded by real YAML but not by the corpus tooling. Keep "
            f"each value on one line however long it gets."))
    return found


def check_frontmatter(root: Path) -> List[Finding]:
    skill = root / "SKILL.md"
    fm, _ = parse_frontmatter(skill.read_text(encoding="utf-8"))
    if not isinstance(fm, dict):
        return []  # an absent or unparseable block is already reported by check_frontmatter_yaml
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


def check_routes(root: Path, tokens: Dict[str, List[str]]) -> List[Finding]:
    """Every path the routing names must exist. This is the check that earns its keep."""
    found = []
    for path in routing_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for raw in sorted(set(PATH_RE.findall(text))):
            if raw.startswith(SKIP_PREFIXES):
                continue
            candidates = expand(raw, tokens)
            if not any((root / c.rstrip("/")).exists() for c in candidates):
                shown = raw if len(candidates) == 1 else f"{raw} (no expansion exists)"
                found.append(Finding("dangling-route", rel,
                                     f"routes to {shown}, which is not in the repository."))
    return found


def check_sections(root: Path, tokens: Dict[str, List[str]]) -> List[Finding]:
    """A `file.md` §N reference must land on a real `## N.` heading in that file."""
    found = []
    for path in routing_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for raw, number in sorted(set(SECTION_RE.findall(text))):
            for candidate in expand(raw, tokens):
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
    # The frontmatter checks read SKILL.md unconditionally; guard here so verify() is safe
    # to call as a library, not only via main() (which returns exit 2 for the same case).
    if not (root / "SKILL.md").exists():
        return [Finding("skill-missing", "SKILL.md",
                        "no SKILL.md at the root; there is nothing to route from.")]
    tokens = discover_placeholders(root)
    found = []
    found += check_frontmatter_yaml(root)
    found += check_frontmatter(root)
    found += check_budgets(root)
    found += check_roles_present(root)
    found += check_routes(root, tokens)
    found += check_sections(root, tokens)
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
