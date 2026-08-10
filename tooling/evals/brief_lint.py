#!/usr/bin/env python3
"""brief_lint: validate a product design brief against the standards corpus.

`design_lint` checks that the *standards* are well formed. This checks that a
*product design* written against them is complete and conformant, which is the
other half of the question and the one a designer actually faces.

Everything it expects is read from `design/`: the capability graph from the module
Provides/Requires tables, the decisions from the Decisions-to-settle tables and the
catalogue, the invariants from each module's Invariants section. Nothing about any
particular product, and nothing about the standards, is hardcoded here. Add a module
or a decision to the corpus and the validator expects it without being edited.

    python tooling/evals/brief_lint.py tooling/evals/reference/customer-orders.md

Exit code is 0 when the brief conforms, 1 when it does not.

Stdlib only, like the linter it sits beside.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))

from design_lint import (  # noqa: E402
    Finding,
    load_capability_catalogue,
    load_decision_catalogue,
    parse_frontmatter,
    lint_text,
)

REQUIRED_BRIEF_KEYS = {"product", "composition", "modules"}
OPTIONAL_BRIEF_KEYS = {"facets", "platform", "decisions"}

# A Requires row is `| `Capability` | `[hard]` | `provider` | why |`.
REQUIRES_ROW_RE = re.compile(
    r"^\|\s*`([A-Za-z][A-Za-z0-9]*)[`({][^|]*\|\s*`?\[(hard|soft)\]`?\s*\|\s*([^|]+)\|")
PROVIDES_ROW_RE = re.compile(r"`([A-Za-z][A-Za-z0-9]*)[`({]")
DECISION_ROW_RE = re.compile(r"^\|\s*`(DEC-[A-Z0-9-]+)`\s*\|\s*`([a-z0-9-]+)`\s*\|")
INVARIANT_RE = re.compile(r"`(INV-[A-Z]+-\d{3})`")
ENTITY_RE = re.compile(r"^\s*Entity:\s*(\S+)\s*\[kind:\s*([A-Za-z]+)\]")
# An attribute declaration is `  name : Type [qualifiers]`, indented inside the block.
ATTRIBUTE_TYPE_RE = re.compile(r"^\s{2,}[a-z_][A-Za-z0-9_]*\s*:\s*([A-Z][A-Za-z0-9]*)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

# A provider that is not another module is always satisfiable within the design.
SELF_PROVIDERS = ("self", "platform", "external")


# --------------------------------------------------------------------------- #
# Reading the corpus
# --------------------------------------------------------------------------- #

class Corpus:
    """What the standards say, read fresh from `design/` on every run."""

    def __init__(self, design_root: Path):
        self.root = design_root
        self.capabilities = set()
        self.decisions: Dict[str, Dict[str, bool]] = {}
        self.modules: Dict[str, dict] = {}
        self._load()

    def _load(self):
        for p in sorted((self.root / "core").glob("*.md")):
            text = p.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(text)
            if not fm:
                continue
            if fm.get("anchor") == "design-language":
                self.capabilities = load_capability_catalogue(text)
            if fm.get("anchor") == "advocated-standards":
                self.decisions = load_decision_catalogue(text)

        for p in sorted((self.root / "modules").glob("*.md")):
            text = p.read_text(encoding="utf-8")
            self.modules[p.stem] = {
                "provides": _read_provides(text),
                "requires": _read_requires(text),
                "decisions": [d for d, _ in _read_decision_rows(text)],
                "invariants": _read_own_invariants(text, p.stem),
            }


def _section(text: str, heading_word: str) -> str:
    """The body of the first `## N. <heading_word>` section, up to the next `## `."""
    m = re.search(rf"^## \d+\.\s*{heading_word}.*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _read_provides(text: str) -> List[str]:
    out, section = [], False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("**Provides"):
            section = True
            continue
        if not section:
            continue
        if stripped.startswith("|"):
            cell = stripped.strip("|").split("|")[0]
            out.extend(PROVIDES_ROW_RE.findall(cell))
        elif stripped:
            section = False
    return out


def _read_requires(text: str) -> List[Tuple[str, str, str]]:
    """`(capability, strength, provider)` from the Requires table."""
    out, section = [], False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("**Requires"):
            section = True
            continue
        if not section:
            continue
        if stripped.startswith("|"):
            m = REQUIRES_ROW_RE.match(stripped)
            if m:
                out.append((m.group(1), m.group(2), m.group(3).strip()))
        elif stripped:
            section = False
    return out


def _read_decision_rows(text: str) -> List[Tuple[str, str]]:
    return [(m.group(1), m.group(2))
            for line in text.split("\n")
            if (m := DECISION_ROW_RE.match(line.strip()))]


def _read_own_invariants(text: str, anchor: str) -> List[str]:
    """Invariants a module declares, not the ones it cites from elsewhere.

    The prefix is derived rather than guessed from the anchor: `observability`
    declares `INV-OBS-*`, and no rule maps one to the other. Whichever prefix
    dominates a module's own Invariants section is the module's own.
    """
    found = INVARIANT_RE.findall(_section(text, "Invariants"))
    if not found:
        return []
    prefixes = [inv.split("-")[1] for inv in found]
    own = max(set(prefixes), key=prefixes.count)
    return sorted({inv for inv in found if inv.split("-")[1] == own})


# --------------------------------------------------------------------------- #
# Reading the brief
# --------------------------------------------------------------------------- #

def read_entities(text: str) -> List[Tuple[str, str, List[str], int]]:
    """`(name, kind, attribute lines, line number)` for each entity block."""
    entities, lines, i, n = [], text.split("\n"), 0, len(text.split("\n"))
    infence = False
    while i < n:
        line = lines[i]
        if FENCE_RE.match(line):
            infence = not infence
            i += 1
            continue
        m = ENTITY_RE.match(line)
        if infence and m:
            attrs, j = [], i + 1
            while j < n and not FENCE_RE.match(lines[j]) and not ENTITY_RE.match(lines[j]):
                attrs.append(lines[j])
                j += 1
            entities.append((m.group(1), m.group(2), attrs, i + 1))
            i = j
            continue
        i += 1
    return entities


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #

def check_frontmatter(fm, path) -> List[Finding]:
    findings = []
    if fm is None:
        return [Finding(path, 1, "brief-frontmatter", "design brief has no frontmatter block")]
    for missing in sorted(REQUIRED_BRIEF_KEYS - set(fm)):
        findings.append(Finding(path, 1, "brief-frontmatter",
                                f"missing required key '{missing}'"))
    for unknown in sorted(set(fm) - REQUIRED_BRIEF_KEYS - OPTIONAL_BRIEF_KEYS):
        findings.append(Finding(path, 1, "brief-frontmatter",
                                f"unknown key '{unknown}'"))
    return findings


def check_composition(fm, corpus: Corpus, path) -> List[Finding]:
    """Every `[hard]` requirement is met by a `Provides` inside the composition."""
    findings = []
    chosen = [m for m in (fm.get("modules") or []) if isinstance(m, str)]
    for anchor in chosen:
        if anchor not in corpus.modules:
            findings.append(Finding(path, 1, "unknown-module",
                                    f"'{anchor}' is not a module in design/modules/"))
    chosen = [m for m in chosen if m in corpus.modules]

    available = set()
    for anchor in chosen:
        available.update(corpus.modules[anchor]["provides"])

    for anchor in chosen:
        for capability, strength, provider in corpus.modules[anchor]["requires"]:
            if strength != "hard":
                continue
            if any(sp in provider for sp in SELF_PROVIDERS):
                continue
            target = provider.split("module:")[-1].strip(" `*").lower()
            if target and target not in chosen:
                findings.append(Finding(
                    path, 1, "invalid-composition",
                    f"module '{anchor}' hard-requires `{capability}` from "
                    f"module:{target}, which the composition does not include"))
            elif capability not in available:
                findings.append(Finding(
                    path, 1, "invalid-composition",
                    f"module '{anchor}' hard-requires `{capability}`, which nothing "
                    f"in the composition provides"))
    return findings


def check_decisions(fm, corpus: Corpus, path) -> List[Finding]:
    """Every decision the chosen modules raise is settled, with a reason where needed."""
    findings = []
    chosen = [m for m in (fm.get("modules") or []) if m in corpus.modules]
    raised = {d for m in chosen for d in corpus.modules[m]["decisions"]}

    settled = {}
    for entry in (fm.get("decisions") or []):
        if isinstance(entry, dict) and entry.get("id"):
            settled[entry["id"]] = entry

    for did in sorted(raised - set(settled)):
        findings.append(Finding(path, 1, "unsettled-decision",
                                f"{did} is raised by the composition but not settled"))

    for did, entry in sorted(settled.items()):
        options = corpus.decisions.get(did)
        if options is None:
            findings.append(Finding(path, 1, "unknown-decision",
                                    f"'{did}' is not in the decision catalogue"))
            continue
        choice = entry.get("choice")
        if not choice:
            findings.append(Finding(path, 1, "unsettled-decision",
                                    f"{did} is listed without a choice"))
        elif choice not in options:
            findings.append(Finding(path, 1, "invalid-choice",
                                    f"'{choice}' is not an option of {did} "
                                    f"(expected one of {sorted(options)})"))
        elif not options[choice] and not entry.get("because"):
            findings.append(Finding(path, 1, "unjustified-choice",
                                    f"{did} chose '{choice}' over the advocated option "
                                    f"without a 'because'"))
    return findings


def declared_types(attrs: List[str]) -> List[str]:
    """The logical types an entity block declares, from its attribute lines only.

    Matching the bare type name against the whole block is not good enough: the
    capability `NaturalKeyLookup` contains `NaturalKey`, so an entity that had lost
    its natural key still looked as though it declared one.
    """
    out = []
    for line in attrs:
        m = ATTRIBUTE_TYPE_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


def check_entities(text: str, path) -> List[Finding]:
    """Entities declare a kind, and a versioned entity carries the identity shape."""
    findings = []
    for name, kind, attrs, lineno in read_entities(text):
        types = declared_types(attrs)
        if kind == "History":
            if "Identifier" not in types:
                findings.append(Finding(path, lineno, "identity-shape",
                                        f"entity '{name}' [kind: History] declares no "
                                        f"`Identifier`"))
            if "NaturalKey" not in types:
                findings.append(Finding(path, lineno, "identity-shape",
                                        f"entity '{name}' [kind: History] declares no "
                                        f"`NaturalKey`"))
    if not read_entities(text):
        findings.append(Finding(path, 1, "no-entities",
                                "the brief declares no entities; a design that models "
                                "nothing cannot be built"))
    return findings


def check_invariants(fm, text: str, corpus: Corpus, path) -> List[Finding]:
    """Every invariant the chosen modules declare is acknowledged by the brief."""
    chosen = [m for m in (fm.get("modules") or []) if m in corpus.modules]
    named = set(INVARIANT_RE.findall(text))
    findings = []
    for anchor in chosen:
        for inv in corpus.modules[anchor]["invariants"]:
            if inv not in named:
                findings.append(Finding(path, 1, "unacknowledged-invariant",
                                        f"{inv} (module '{anchor}') is not acknowledged "
                                        f"in the brief"))
    return findings


def lint_brief(path: Path, design_root: Path = None) -> List[Finding]:
    corpus = Corpus(design_root or (REPO_ROOT / "design"))
    text = path.read_text(encoding="utf-8")
    p = str(path)
    fm, _ = parse_frontmatter(text)

    findings = check_frontmatter(fm, p)
    if fm is None:
        return findings
    findings += check_composition(fm, corpus, p)
    findings += check_decisions(fm, corpus, p)
    findings += check_entities(text, p)
    findings += check_invariants(fm, text, corpus, p)
    # a design brief is platform-agnostic, exactly as design/ is
    findings += lint_text(p, text)
    return sorted(findings, key=lambda f: (f.line, f.rule, f.message))


def main(argv: List[str]) -> int:
    if not argv:
        print("usage: brief_lint.py <brief.md> [...]", file=sys.stderr)
        return 2
    findings = []
    for arg in argv:
        target = Path(arg)
        if not target.is_file():
            print(f"warning: not a file: {arg}", file=sys.stderr)
            continue
        findings += lint_brief(target)
    if not findings:
        print(f"brief-lint: clean ({', '.join(argv)})")
        return 0
    for f in findings:
        print(str(f))
    print(f"\nbrief-lint: {len(findings)} violation(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
