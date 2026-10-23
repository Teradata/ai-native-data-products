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
    python tooling/skill/verify_skill.py --package    # and what an install receives

An install is a clone or a GitHub ZIP of a commit, which is what `git archive` produces:
tracked files only. `--package` builds that archive from HEAD and checks the routing
against it rather than the working tree, so a route to an untracked or ignored file fails
here instead of in an agent's session, and lists what the package contains.

Exit code is 0 when the package conforms, 1 when it does not, 2 when there is no
SKILL.md to check, so a missing skill is not mistaken for a pass.

Stdlib only, like the tools it sits beside.
"""
from __future__ import annotations

import argparse
import fnmatch
import io
import re
import subprocess
import sys
import tarfile
from collections import Counter
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional, Set

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
FRONTMATTER_BLOCK_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
# A top-level frontmatter line is a `key:` or a `- ` list item. Anything else at column 0 is
# a plain scalar that wrapped onto a new line without indentation, which silently truncates
# the value it belongs to. `design_lint.parse_frontmatter` is a lenient subset parser and
# accepts it; a real YAML loader - the one the skill installer uses - does not.
YAML_KEY_RE = re.compile(r"^(?:[A-Za-z_][\w-]*\s*:|-\s)")


class Finding(NamedTuple):
    rule: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: [{self.rule}] {self.message}"


def platforms(root: Path) -> List[str]:
    """Every binding the corpus holds: a directory under implementation/ with a platform
    profile. Discovered, never listed, so no platform is the one routes are checked on."""
    impl = root / "implementation"
    return sorted(p.name for p in impl.iterdir() if (p / "binding.toml").exists()) if impl.is_dir() else []


def expand(path: str, root: Path = REPO_ROOT) -> List[List[str]]:
    """Expand the corpus's placeholders into the concrete paths they stand for, one group
    per platform: a `{platform}` route must resolve on every binding, while `{module}` and
    `{pattern}` need only one expansion that exists, since a route may cover an area not
    every module implements."""
    bindings = platforms(root)
    groups = ([[path.replace("{platform}", p)] for p in bindings] if "{platform}" in path and bindings
              else [[path]])
    for token, values in (("{module}", MODULES), ("{pattern}", PATTERNS)):
        groups = [[c.replace(token, v) for c in g for v in values] if any(token in c for c in g) else g
                  for g in groups]
    return groups


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
        if not YAML_KEY_RE.match(line):
            found.append(Finding(
                "skill-frontmatter", f"SKILL.md:{offset}",
                f"{line.strip()[:48]!r}... is not a `key: value` at column 0. This "
                f"frontmatter is flat - `name` and `description`, one line each. A value "
                f"reflowed onto a second line breaks it: unindented it ends the scalar, and "
                f"indented it is folded by real YAML but not by the corpus tooling. Keep "
                f"each value on one line however long it gets."))
    return found


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


def check_routes(root: Path, exists: Optional[Callable[[str], bool]] = None,
                 rule: str = "dangling-route", where: str = "the repository") -> List[Finding]:
    """Every path the routing names must exist. This is the check that earns its keep."""
    exists = exists or (lambda rel: (root / rel).exists())
    found = []
    for path in routing_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for raw in sorted(set(PATH_RE.findall(text))):
            if raw.startswith(SKIP_PREFIXES):
                continue
            for group in expand(raw, root):
                if not any(exists(c.rstrip("/")) for c in group):
                    shown = group[0] if len(group) == 1 else f"{raw} (no expansion of {group[0]} exists)"
                    found.append(Finding(rule, rel, f"routes to {shown}, which is not in {where}."))
    return found


def check_sections(root: Path) -> List[Finding]:
    """A `file.md` §N reference must land on a real `## N.` heading in that file."""
    found = []
    for path in routing_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for raw, number in sorted(set(SECTION_RE.findall(text))):
            for candidate in (c for g in expand(raw, root) for c in g):
                target = root / candidate
                if not target.exists():
                    continue  # already reported by check_routes
                headings = set(HEADING_RE.findall(target.read_text(encoding="utf-8")))
                if number not in headings:
                    found.append(Finding(
                        "dangling-section", rel,
                        f"cites {candidate} §{number}, which has no such section."))
    return found


def package_files(root: Path) -> Optional[Set[str]]:
    """The files an install receives: `git archive` of HEAD. None outside a git checkout."""
    run = subprocess.run(["git", "-C", str(root), "archive", "--format=tar", "HEAD"], capture_output=True)
    if run.returncode != 0:
        return None
    with tarfile.open(fileobj=io.BytesIO(run.stdout)) as tar:
        return {m.name for m in tar.getmembers() if m.isfile()}


def _ignored(root: Path, names: Set[str]) -> List[str]:
    """Shipped files the repository's own .gitignore says should not be tracked."""
    ignore = root / ".gitignore"
    if not ignore.exists():
        return []
    patterns = [line.strip() for line in ignore.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith(("#", "!"))]
    out = []
    for name in sorted(names):
        parts = name.split("/")
        for pattern in patterns:
            anchored, pat = pattern.startswith("/"), pattern.strip("/")
            prefixes = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
            segments = prefixes if (anchored or "/" in pat) else parts
            if any(fnmatch.fnmatch(s, pat) for s in segments):
                out.append(name)
                break
    return out


def check_package(root: Path) -> List[Finding]:
    """What a clone or ZIP of HEAD delivers: the entry point and roles, every route, and
    nothing the repository itself says is local or generated."""
    names = package_files(root)
    if names is None:
        return [Finding("package", str(root), "not a git checkout with a commit, so no package can be built.")]
    found = [Finding("package", "SKILL.md", f"{required} is not in the package.")
             for required in ["SKILL.md"] + [f"roles/{r}.md" for r in ROLES] if required not in names]
    directories = {"/".join(n.split("/")[:i]) for n in names for i in range(1, n.count("/") + 1)}
    found += check_routes(root, lambda rel: rel in names or rel in directories,
                          "package-route", "the package (commit it, or stop routing to it)")
    found += [Finding("package-ignored", name, "is shipped although .gitignore excludes it; "
                      "untrack it or narrow the ignore rule.") for name in _ignored(root, names)]
    return found


def package_summary(root: Path) -> str:
    names = package_files(root) or set()
    tops = Counter(n.split("/")[0] if "/" in n else "(root)" for n in names)
    return "Package (git archive HEAD): " + ", ".join(f"{k} {v}" for k, v in sorted(tops.items())) \
        + f"; {len(names)} files."


def verify(root: Path) -> List[Finding]:
    found = []
    found += check_frontmatter_yaml(root)
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
    ap.add_argument("--package", action="store_true",
                    help="also build the package an install receives (git archive HEAD) and check it")
    args = ap.parse_args(argv)
    root = args.root.resolve()

    if not (root / "SKILL.md").exists():
        print(f"No SKILL.md in {root}. Nothing to verify.", file=sys.stderr)
        return 2

    found = verify(root)
    if args.package:
        found += check_package(root)
        print(package_summary(root))
    for finding in found:
        print(finding)
    if found:
        print(f"\n{len(found)} problem(s).", file=sys.stderr)
        return 1
    print("Skill package conforms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
