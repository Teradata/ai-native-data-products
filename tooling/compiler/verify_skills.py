#!/usr/bin/env python3
"""verify_skills: check a compiled skill package against the standards it came from.

The Skill Conversion Prompt asks an agent to compress `design/` and
`implementation/` into four role skills. That compression is judgement work, so it
is not deterministic: two runs produce different skills from identical input. What
*is* deterministic is whether the result kept everything it was required to keep.

This makes the prompt's "Verify before finishing" checklist executable. It does not
judge whether the compression was good, only whether it was lossless where the prompt
said it must be.

    python tooling/compiler/verify_skills.py                 # checks ./skills
    python tooling/compiler/verify_skills.py --skills path   # or somewhere else
    python tooling/compiler/verify_skills.py --platform teradata

Exit code is 0 when the package conforms, 1 when it does not, 2 when there is nothing
to check.

Everything expected is read from the repository: the module and pattern anchors, the
decisions, the invariants, the conformance rules, the platform artifacts. Add a module
to `design/` and the verifier expects it in the skills without being edited.

Stdlib only, like the tools it sits beside.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))

from design_lint import Finding, lint_text, parse_frontmatter  # noqa: E402

ROLES = ("design", "build", "review", "access")
SKILL_NAME_PREFIX = "ai-native-dp-"
MAX_SKILL_LINES = 150

DECISION_RE = re.compile(r"\b(DEC-[A-Z0-9-]+)\b")
INVARIANT_RE = re.compile(r"\b(INV-[A-Z]+-\d{3})\b")
CONFORMANCE_RE = re.compile(r"\b((?:TLM|VAL)-\d{2})\b")
# Object names in the templates are themselves templated (`{{ database }}.{{ entity }}_H`),
# so matching them verifies nothing. Verbatim preservation is checked instead by
# fingerprinting each artifact on its most distinctive un-templated lines.
JINJA_RE = re.compile(r"\{\{|\{%")
ANCHOR_MIN = 40
ANCHORS_PER_ARTIFACT = 2
# A repeated run of this many substantial lines means an on-demand file is echoing
# SKILL.md rather than adding to it.
DUPLICATE_RUN = 5
SUBSTANTIAL = 40


# --------------------------------------------------------------------------- #
# What the repository says the skills must carry
# --------------------------------------------------------------------------- #

class Expected:
    """Read from `design/` and `implementation/`, never hardcoded."""

    def __init__(self, repo: Path, platform: str):
        self.repo = repo
        self.platform = platform
        design = repo / "design"

        self.modules = sorted(p.stem for p in (design / "modules").glob("*.md"))
        self.patterns = sorted(p.stem for p in (design / "patterns").glob("*.md"))

        self.decisions: Set[str] = set()
        self.invariants: Set[str] = set()
        for anchor in self.modules:
            text = (design / "modules" / f"{anchor}.md").read_text(encoding="utf-8")
            self.decisions |= set(DECISION_RE.findall(_settle_table(text)))
            self.invariants |= _own_invariants(text)
        # Framework invariants are declared by the master design, not by any module.
        # Taken deliberately rather than picked up from whichever module happens to
        # cite one in its own Invariants section.
        master = design / "core" / "MASTER_DESIGN.md"
        if master.is_file():
            self.invariants |= set(INVARIANT_RE.findall(
                _named_section(master.read_text(encoding="utf-8"), "Framework Invariants")))

        self.conformance: Set[str] = set()
        for anchor in self.patterns:
            text = (design / "patterns" / f"{anchor}.md").read_text(encoding="utf-8")
            self.conformance |= set(CONFORMANCE_RE.findall(text))

        # `{artifact name: [distinctive lines]}`. If none of an artifact's anchors
        # survives into the build skill, its SQL was not preserved verbatim.
        self.artifact_anchors: Dict[str, List[str]] = {}
        impl = repo / "implementation" / platform
        if impl.exists():
            for artifact in sorted(impl.rglob("*")):
                if artifact.suffix in (".sql", ".j2") and artifact.is_file():
                    anchors = _anchor_lines(artifact.read_text(encoding="utf-8",
                                                              errors="replace"))
                    if anchors:
                        self.artifact_anchors[artifact.name] = anchors


def _own_invariants(text: str) -> Set[str]:
    """A module's own invariants, not the ones it cites.

    The prefix is derived: `observability` declares `INV-OBS-*`, and no rule maps one
    to the other. Whichever prefix dominates the section is the module's own.
    """
    found = INVARIANT_RE.findall(_named_section(text, "Invariants"))
    if not found:
        return set()
    prefixes = [i.split("-")[1] for i in found]
    own = max(set(prefixes), key=prefixes.count)
    return {i for i in found if i.split("-")[1] == own}


def _anchor_lines(body: str) -> List[str]:
    """The most distinctive un-templated lines of an artifact, for a verbatim check."""
    candidates = [l.strip() for l in body.splitlines()]
    candidates = [l for l in candidates
                  if len(l) >= ANCHOR_MIN and not JINJA_RE.search(l)
                  and not l.startswith("--")]
    return sorted(candidates, key=len, reverse=True)[:ANCHORS_PER_ARTIFACT]


def _named_section(text: str, heading: str) -> str:
    m = re.search(rf"^## \d+\.\s*{heading}\b.*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _settle_table(text: str) -> str:
    m = re.search(r"^#{3,4} [\d.]*\s*Decisions to settle\b.*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^#{2,4} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


# --------------------------------------------------------------------------- #
# Reading the compiled package
# --------------------------------------------------------------------------- #

def role_files(skills: Path, role: str) -> Dict[Path, str]:
    root = skills / role
    if not root.is_dir():
        return {}
    return {p: p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(root.rglob("*.md")) if p.is_file()}


def role_text(files: Dict[Path, str]) -> str:
    return "\n".join(files.values())


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #

def check_structure(skills: Path, expected: Expected) -> List[Finding]:
    """Every role exists, with an on-demand file per module and pattern in scope."""
    findings = []
    wanted = {
        "design": [f"modules/{m}.md" for m in expected.modules]
                  + [f"patterns/{p}.md" for p in expected.patterns],
        "build": [f"modules/{m}.md" for m in expected.modules]
                 + [f"patterns/{p}.md" for p in expected.patterns]
                 + ["platform-profile.md"],
        "review": [f"checks/{a}.md" for a in expected.modules + expected.patterns],
        "access": ["discovery.md"],
    }
    for role in ROLES:
        skill_md = skills / role / "SKILL.md"
        if not skill_md.is_file():
            findings.append(Finding(str(skills / role), 1, "missing-skill",
                                    f"no SKILL.md for the '{role}' role"))
            continue
        for rel in wanted[role]:
            if not (skills / role / rel).is_file():
                findings.append(Finding(str(skills / role / rel), 1, "missing-file",
                                        f"'{role}' is missing {rel}, which the corpus "
                                        f"says is in scope"))
    return findings


def check_skill_md(skills: Path) -> List[Finding]:
    """SKILL.md is lean and correctly identified: it is read on every invocation."""
    findings = []
    for role in ROLES:
        path = skills / role / "SKILL.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        p = str(path)

        lines = text.count("\n") + 1
        if lines > MAX_SKILL_LINES:
            findings.append(Finding(p, 1, "skill-too-long",
                                    f"{lines} lines, over the {MAX_SKILL_LINES} the prompt "
                                    f"allows; move detail into an on-demand file"))

        fm, _ = parse_frontmatter(text)
        if fm is None:
            findings.append(Finding(p, 1, "skill-frontmatter", "SKILL.md has no frontmatter"))
            continue
        name = fm.get("name")
        if name != f"{SKILL_NAME_PREFIX}{role}":
            findings.append(Finding(p, 1, "skill-frontmatter",
                                    f"name is '{name}', expected "
                                    f"'{SKILL_NAME_PREFIX}{role}'"))
        if not fm.get("description"):
            findings.append(Finding(p, 1, "skill-frontmatter",
                                    "no description, so nothing tells an agent when to "
                                    "load this skill"))
    return findings


def check_no_duplication(skills: Path) -> List[Finding]:
    """An on-demand file that repeats SKILL.md wastes the context it was meant to save."""
    findings = []
    for role in ROLES:
        skill_md = skills / role / "SKILL.md"
        if not skill_md.is_file():
            continue
        base = [l.strip() for l in skill_md.read_text(encoding="utf-8", errors="replace").split("\n")]
        base_runs = _runs(base)
        for path, text in role_files(skills, role).items():
            if path.name == "SKILL.md":
                continue
            shared = base_runs & _runs([l.strip() for l in text.split("\n")])
            if shared:
                findings.append(Finding(str(path), 1, "duplicates-skill",
                                        f"repeats {DUPLICATE_RUN}+ consecutive lines from "
                                        f"SKILL.md; the on-demand file should add, not echo"))
    return findings


def _runs(lines: List[str]) -> Set[str]:
    substantial = [l for l in lines if len(l) >= SUBSTANTIAL]
    return {"\n".join(substantial[i:i + DUPLICATE_RUN])
            for i in range(max(0, len(substantial) - DUPLICATE_RUN + 1))}


def check_design_is_platform_neutral(skills: Path) -> List[Finding]:
    """The design skill stays platform-agnostic, exactly as `design/` is."""
    findings = []
    for path, text in role_files(skills, "design").items():
        findings += lint_text(str(path), text)
    return findings


def check_design_carries_decisions(skills: Path, expected: Expected) -> List[Finding]:
    """A decision the corpus raises but the skill omits can never be put to a designer."""
    text = role_text(role_files(skills, "design"))
    if not text:
        return []
    present = set(DECISION_RE.findall(text))
    return [Finding(str(skills / "design"), 1, "missing-decision",
                    f"{d} is raised by a module but appears nowhere in the design skill")
            for d in sorted(expected.decisions - present)]


def check_review_carries_checks(skills: Path, expected: Expected) -> List[Finding]:
    """The reviewer cannot check what the skill did not carry."""
    text = role_text(role_files(skills, "review"))
    if not text:
        return []
    findings = []
    for inv in sorted(expected.invariants - set(INVARIANT_RE.findall(text))):
        findings.append(Finding(str(skills / "review"), 1, "missing-invariant",
                                f"{inv} is declared by a module but absent from the "
                                f"review skill"))
    for rule in sorted(expected.conformance - set(CONFORMANCE_RE.findall(text))):
        findings.append(Finding(str(skills / "review"), 1, "missing-conformance-rule",
                                f"{rule} is defined by a pattern but absent from the "
                                f"review skill"))
    return findings


def check_build_preserves_platform_sql(skills: Path, expected: Expected) -> List[Finding]:
    """Platform SQL is preserved verbatim, not paraphrased.

    Checked by fingerprint: if none of an artifact's most distinctive lines survives
    into the build skill, that SQL was rewritten rather than carried.
    """
    text = role_text(role_files(skills, "build"))
    if not text or not expected.artifact_anchors:
        return []
    return [Finding(str(skills / "build"), 1, "paraphrased-platform-sql",
                    f"no line of '{name}' survives verbatim in the build skill; the "
                    f"prompt requires platform SQL to be preserved, never compressed")
            for name, anchors in sorted(expected.artifact_anchors.items())
            if not any(a in text for a in anchors)]


def check_access_leads_with_discovery(skills: Path) -> List[Finding]:
    """The access skill's whole job is to orient before touching data."""
    path = skills / "access" / "SKILL.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    findings = []
    if "product-first" not in text and "product first" not in text:
        findings.append(Finding(str(path), 1, "access-discovery",
                                "does not lead with product-first discovery"))
    if "gate" not in text:
        findings.append(Finding(str(path), 1, "access-trust-gate",
                                "does not mention the pre-use trust gate"))
    return findings


# --------------------------------------------------------------------------- #

def verify(skills: Path, repo: Path = REPO_ROOT, platform: str = "teradata") -> List[Finding]:
    expected = Expected(repo, platform)
    findings = check_structure(skills, expected)
    findings += check_skill_md(skills)
    findings += check_no_duplication(skills)
    findings += check_design_is_platform_neutral(skills)
    findings += check_design_carries_decisions(skills, expected)
    findings += check_review_carries_checks(skills, expected)
    findings += check_build_preserves_platform_sql(skills, expected)
    findings += check_access_leads_with_discovery(skills)
    return sorted(findings, key=lambda f: (f.path, f.rule, f.message))


MANUAL = """
Not checkable here, and still on you:

  * Every claim traces to a repo source. A skill can be structurally complete and
    still say something the standards do not.
  * The compression is good. This verifies that nothing required was lost, not that
    what remains is well written or well routed.
  * The build skill's capability-to-binding and invariant-to-check mappings are
    correct, rather than merely present.
"""


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--skills", default=str(REPO_ROOT / "skills"),
                    help="the compiled skill package (default: ./skills)")
    ap.add_argument("--repo", default=str(REPO_ROOT),
                    help="the repository the skills were compiled from")
    ap.add_argument("--platform", default="teradata",
                    help="the platform whose implementation the build skill carries")
    ap.add_argument("--quiet", action="store_true", help="suppress the manual checklist")
    args = ap.parse_args(argv)

    skills = Path(args.skills)
    if not skills.is_dir():
        print(f"verify-skills: nothing to check, {skills} does not exist.\n"
              f"Compile the skills first, per prompts/Skill_Conversion_Prompt.md.",
              file=sys.stderr)
        return 2

    findings = verify(skills, Path(args.repo), args.platform)
    for f in findings:
        print(str(f))
    if findings:
        print(f"\nverify-skills: {len(findings)} problem(s)", file=sys.stderr)
    else:
        print(f"verify-skills: clean ({skills})")
    if not args.quiet:
        print(MANUAL)
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
