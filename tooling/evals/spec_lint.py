#!/usr/bin/env python3
"""spec_lint: validate a product design specification against the standards corpus.

`design_lint` checks that the *standards* are well formed. This checks that a
*product design* written against them is complete and conformant, which is the
other half of the question and the one a designer actually faces.

Everything it expects is read from `design/`: the capability graph from the module
Provides/Requires tables, the decisions from the Decisions-to-settle tables and the
catalogue, the invariants from each module's Invariants section. Nothing about any
particular product, and nothing about the standards, is hardcoded here. Add a module
or a decision to the corpus and the validator expects it without being edited.

    python tooling/evals/spec_lint.py tooling/evals/reference/customer-orders.md

Exit code is 0 when the specification conforms, 1 when it does not.

Stdlib only, like the linter it sits beside.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from design_lint import (  # noqa: E402
    Finding,
    load_capability_catalogue,
    load_decision_catalogue,
    parse_frontmatter,
    lint_text,
    load_prohibited_names,
)
from spec_notation import (  # noqa: E402
    CALL,
    OPERATORS,
    REFERENCE,
    Specification,
    Standard,
    load_standard,
    outermost_call,
    parse_specification,
    strip_literals,
)

PRODUCT_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

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
# Reading the specification
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
    """Keys come from the frontmatter table of the Design Specification Standard."""
    findings = []
    if fm is None:
        return [Finding(path, 1, "spec-frontmatter", "design specification has no frontmatter block")]
    keys = standard().frontmatter
    required = {k for k, f in keys.items() if f.required}
    for missing in sorted(required - set(fm)):
        findings.append(Finding(path, 1, "spec-frontmatter",
                                f"missing required key '{missing}'"))
    for unknown in sorted(set(fm) - set(keys)):
        if unknown == "platform":
            findings.append(Finding(path, 1, "platform-reference",
                                    "a specification does not choose its platform; the "
                                    "target is selected at build time"))
        else:
            findings.append(Finding(path, 1, "spec-frontmatter",
                                    f"unknown key '{unknown}'"))
    code = fm.get("product_code")
    if code is not None and not PRODUCT_CODE_RE.match(str(code)):
        findings.append(Finding(path, 1, "spec-frontmatter",
                                f"product_code '{code}' is not identifier-safe"))
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
                                "the specification declares no entities; a design that models "
                                "nothing cannot be built"))
    return findings


def check_invariants(fm, text: str, corpus: Corpus, path) -> List[Finding]:
    """Every invariant the chosen modules declare is acknowledged by the specification."""
    chosen = [m for m in (fm.get("modules") or []) if m in corpus.modules]
    named = set(INVARIANT_RE.findall(text))
    findings = []
    for anchor in chosen:
        for inv in corpus.modules[anchor]["invariants"]:
            if inv not in named:
                findings.append(Finding(path, 1, "unacknowledged-invariant",
                                        f"{inv} (module '{anchor}') is not acknowledged "
                                        f"in the specification"))
    return findings


# --------------------------------------------------------------------------- #
# Notation: what the Design Specification Standard requires
# --------------------------------------------------------------------------- #

_STANDARDS: Dict[Path, Standard] = {}
_PROHIBITED: Dict[Path, dict] = {}


def standard(design_root: Path = None) -> Standard:
    """The Design Specification Standard, read once per design root."""
    root = design_root or (REPO_ROOT / "design")
    if root not in _STANDARDS:
        _STANDARDS[root] = load_standard(root)
    return _STANDARDS[root]


def prohibited_names(design_root: Path = None) -> dict:
    root = design_root or (REPO_ROOT / "design")
    if root not in _PROHIBITED:
        tlm = root / "patterns" / "temporal-lifecycle-metadata.md"
        _PROHIBITED[root] = load_prohibited_names(tlm.read_text(encoding="utf-8"))
    return _PROHIBITED[root]


class NotationContext:
    """What a specification's expressions and references may resolve against."""

    def __init__(self, fm: dict, spec: Specification, std: Standard, corpus: Corpus):
        self.fm, self.spec, self.std = fm, spec, std
        self.modules = [m for m in (fm.get("modules") or []) if isinstance(m, str)]
        self.entities: Dict[str, Set[str]] = {}
        for module in self.modules:
            for name, attrs in std.module_entities.get(module, {}).items():
                self.entities.setdefault(name, set()).update(attrs)
        for entity in spec.entities:
            self.entities[entity.name] = set(entity.attributes)
        self.metrics = {b.name for b in spec.blocks_of("Metric")}
        self.decisions = spec.blocks_of("Decision")
        self.settled = {d.get("id"): d.get("choice")
                        for d in (fm.get("decisions") or []) if isinstance(d, dict)}
        self.anchors = set(corpus.modules) | std.patterns
        self.feature_groups = {b.fields.get("Features") for b in spec.blocks_of("Model")}

    def resolves(self, entity: str, attribute: str = None) -> bool:
        if entity not in self.entities:
            return False
        return (attribute is None or attribute in self.entities[entity]
                or attribute in self.std.canonical_attributes)

    def covered(self, entity: str) -> bool:
        """A `Decision:` block names this entity in `Applies to`."""
        return any(str(d.fields.get("Applies to", "")).strip() == entity for d in self.decisions)


def expression_errors(expr: str, ctx: NotationContext, kind: str) -> List[str]:
    """Problems with an expression used as `kind`: row, aggregate or quality."""
    bare, _, err = strip_literals(expr)
    if err:
        return [err]
    errors, classes = [], set()
    for name in CALL.findall(bare):
        if name in OPERATORS:
            continue
        cls = ctx.std.functions.get(name)
        if cls is None:
            errors.append(f"'{name}' is not in the expression vocabulary")
        else:
            classes.add(cls)
    top = outermost_call(bare)
    if kind == "row" and classes - {"row"}:
        errors.append(f"uses {'/'.join(sorted(classes - {'row'}))} functions where only "
                      f"row functions are allowed")
    elif kind == "aggregate" and (not top or ctx.std.functions.get(top) != "aggregate"):
        errors.append("the outermost function must be an aggregate")
    elif kind == "quality" and (not top or ctx.std.functions.get(top) != "quality"):
        errors.append("a rule's check must be a quality function")
    for entity, attribute in REFERENCE.findall(bare):
        if not ctx.resolves(entity):
            errors.append(f"'{entity}' is not an entity in the specification or its modules")
        elif not ctx.resolves(entity, attribute):
            errors.append(f"'{entity}.{attribute}' does not resolve")
    for _, arg in re.findall(
            r"\b(count_rows|freshness|count_related|days_since_last)\(\s*([A-Za-z]\w*)\s*[,)]", bare):
        if not ctx.resolves(arg):
            errors.append(f"'{arg}' is not an entity in the specification or its modules")
    for name in re.findall(r"\bmetric\(\s*'([^']*)'\s*\)", expr):
        if name not in ctx.metrics:
            errors.append(f"metric '{name}' is not declared")
    return errors


def _duration_re(std: Standard) -> str:
    units = "|".join(sorted(u.rstrip("s") for u in std.duration_units))
    return rf"\d+\s+(?:{units})s?"


def value_errors(value, spec_field, ctx: NotationContext) -> List[str]:
    """Problems with a field value, judged by the field's declared type."""
    std, t = ctx.std, spec_field.type
    multi = t in ("weights", "rules", "flows")
    if multi != isinstance(value, list):
        return ["expects indented lines" if multi else "expects a single-line value"]
    if not value:
        return ["is empty"]
    duration = _duration_re(std)
    if t in ("text", "terms"):
        return []
    if t == "integer":
        return [] if re.fullmatch(r"\d+", value) else [f"'{value}' is not an integer"]
    if t == "number":
        return [] if re.fullmatch(r"\d+(\.\d+)?|\.\d+", value) else [f"'{value}' is not a number"]
    if t == "enum":
        return [] if value in (spec_field.values or []) else [
            f"'{value}' is not one of {spec_field.values}"]
    if t == "module":
        return [] if value in ctx.anchors else [f"'{value}' is not a module or pattern"]
    if t in ("entity", "entities"):
        names = [v.strip() for v in value.split(",")] if t == "entities" else [value]
        return [f"'{n}' is not an entity in the specification or its modules"
                for n in names if not ctx.resolves(n)]
    if t == "reference":
        m = REFERENCE.fullmatch(value)
        if not m:
            return [f"'{value}' is not an attribute reference"]
        return [] if ctx.resolves(*m.groups()) else [f"'{value}' does not resolve"]
    if t in ("expression", "condition"):
        return expression_errors(value, ctx, "row")
    if t == "aggregate":
        return expression_errors(value, ctx, "aggregate")
    if t == "refresh":
        terms = {v.strip() for v in value.split(",")}
        return [f"'{v}' is not a refresh term" for v in sorted(terms - std.refresh_terms)]
    if t == "duration":
        return [] if re.fullmatch(duration, value) else [f"'{value}' is not a duration"]
    if t == "growth":
        units = "|".join(re.escape(u) for u in sorted(std.growth_units))
        return [] if re.fullmatch(rf"\d+\s+(?:{units})", value) else [f"'{value}' is not a growth rate"]
    if t == "retention":
        ok = value == "life of product" or re.fullmatch(rf"{duration}(\s+after\s+.+)?", value)
        return [] if ok else [f"'{value}' is not a retention"]
    if t == "weights":
        return _weights_errors(value, std)
    if t == "rules":
        return [e for line in value for e in _rule_errors(line, ctx)]
    if t == "flows":
        return [e for line in value for e in _flow_errors(line, ctx)]
    return [f"unknown field type '{t}'"]


def _weights_errors(lines: List[str], std: Standard) -> List[str]:
    errors, total = [], 0
    for line in lines:
        m = re.fullmatch(r"([a-z]+):\s*(\d+)%", line)
        if not m:
            errors.append(f"'{line}' is not '<dimension>: <percent>'")
            continue
        if m.group(1) not in std.weight_dimensions:
            errors.append(f"'{m.group(1)}' is not a quality dimension")
        total += int(m.group(2))
    if not errors and total != 100:
        errors.append(f"weights sum to {total}, not 100")
    return errors


def _rule_errors(line: str, ctx: NotationContext) -> List[str]:
    if not line.startswith("- "):
        return [f"'{line}' is not a '- <check>: <thresholds>' line"]
    body = line[2:]
    depth, close = 0, -1
    for i, c in enumerate(body):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                close = i
                break
    if close < 0 or not body[close + 1:].lstrip().startswith(":"):
        return [f"'{line}' is not a '- <check>: <thresholds>' line"]
    check, thresholds = body[:close + 1], body[close + 1:].lstrip()[1:].strip()
    errors = expression_errors(check, ctx, "quality")
    fn = outermost_call(check)
    duration = _duration_re(ctx.std)
    if fn == "freshness":
        ok = re.fullmatch(rf"warn after {duration}, fail after {duration}", thresholds)
    elif fn in ("integrity", "uniqueness"):
        ok = thresholds == "fail on any"
    else:
        m = re.fullmatch(r"pass >= (\d*\.?\d+), warn >= (\d*\.?\d+)", thresholds)
        ok = m and float(m.group(1)) >= float(m.group(2))
    if not ok:
        errors.append(f"thresholds '{thresholds}' do not fit check '{fn}'")
    return errors


def _flow_errors(line: str, ctx: NotationContext) -> List[str]:
    parts = [p.strip() for p in line[2:].split("->")] if line.startswith("- ") else []
    if len(parts) != 3 or not all(parts):
        return [f"'{line}' is not a '- <source> -> <job> -> <entity>' line"]
    return [] if ctx.resolves(parts[2]) else [
        f"flow target '{parts[2]}' is not an entity in the specification or its modules"]


def check_fields(fields: dict, table: dict, ctx, path, lineno, where, line_of=None) -> List[Finding]:
    findings, wildcard = [], table.get("*")
    for name, spec_field in table.items():
        if name != "*" and spec_field.required and name not in fields:
            findings.append(Finding(path, lineno, "missing-field", f"{where} has no '{name}'"))
    for name, value in fields.items():
        spec_field = table.get(name) or wildcard
        at = (line_of or {}).get(name, lineno)
        if spec_field is None:
            findings.append(Finding(path, at, "unknown-field", f"{where} has no field '{name}'"))
            continue
        if spec_field is wildcard and not ctx.resolves(name):
            findings.append(Finding(path, at, "invalid-value",
                                    f"{where}: '{name}' is not an entity in the specification "
                                    f"or its modules"))
        for err in value_errors(value, spec_field, ctx):
            findings.append(Finding(path, at, "invalid-value", f"{where} '{name}' {err}"
                                    if err.startswith(("expects", "is empty")) else
                                    f"{where} '{name}': {err}"))
    return findings


def check_entity_notation(ctx: NotationContext, path) -> List[Finding]:
    std, findings = ctx.std, []
    prohibited = prohibited_names()
    allocation = std.header_qualifiers.get("allocation")
    for e in ctx.spec.entities:
        where = f"entity '{e.name}'"
        for key in sorted(set(e.header) - set(std.header_qualifiers)):
            findings.append(Finding(path, e.line, "unknown-field", f"{where} has no qualifier '{key}'"))
        profile = e.header.get("profile")
        if not profile:
            findings.append(Finding(path, e.line, "missing-profile", f"{where} declares no profile"))
        elif profile not in std.profiles:
            findings.append(Finding(path, e.line, "invalid-value",
                                    f"{where}: '{profile}' is not a temporal profile"))
        elif profile not in std.kind_defaults.get(e.kind, {profile}) and not ctx.covered(e.name):
            findings.append(Finding(path, e.line, "unrecorded-departure",
                                    f"{where} takes profile {profile}, outside the "
                                    f"[kind: {e.kind}] defaults, with no Decision applying to it"))
        alloc = e.header.get("allocation")
        if alloc:
            if allocation and alloc not in (allocation.values or []):
                findings.append(Finding(path, e.line, "invalid-value",
                                        f"{where}: allocation '{alloc}' is not one of "
                                        f"{allocation.values}"))
            elif (ctx.settled.get("DEC-SURROGATE-ALLOCATION") not in (None, alloc)
                  and not ctx.covered(e.name)):
                findings.append(Finding(path, e.line, "unrecorded-departure",
                                        f"{where} allocates '{alloc}' against the product's "
                                        f"DEC-SURROGATE-ALLOCATION with no Decision applying to it"))

        for a in e.attributes.values():
            target = a.qualifiers.get("->")
            if target is not None:
                targets = [t.strip() for t in target.split("|")]
                for t in targets:
                    if not ctx.resolves(t):
                        findings.append(Finding(path, a.line, "unresolved-reference",
                                                f"{where}.{a.name} references '{t}', which is "
                                                f"not an entity in the specification or its modules"))
                if len(targets) > 1:
                    disc = e.attributes.get(a.qualifiers.get("discriminator", ""))
                    members = set(re.findall(r"[A-Z0-9_]+", disc.type[5:])) if (
                        disc and disc.type.startswith("Enum")) else set()
                    if not members >= {t.upper() for t in targets}:
                        findings.append(Finding(path, a.line, "missing-discriminator",
                                                f"{where}.{a.name} has several targets but no "
                                                f"Enum discriminator listing them"))
            if "derive" in a.qualifiers:
                for err in expression_errors(a.qualifiers["derive"], ctx, "row"):
                    findings.append(Finding(path, a.line, "invalid-expression",
                                            f"{where}.{a.name}: {err}"))
            if a.type == "Timestamp" and not a.name.endswith("_dts"):
                findings.append(Finding(path, a.line, "timestamp-name",
                                        f"{where}.{a.name} is a Timestamp not named <event>_dts"))
            conditional = std.conditional_prohibited.get(a.name)
            if a.name in prohibited or (conditional is not None and conditional != profile):
                findings.append(Finding(path, a.line, "prohibited-name",
                                        f"{where}.{a.name} is a name the temporal pattern "
                                        f"prohibits{' outside ' + conditional if conditional else ''}"))

        feature_group = e.name in ctx.feature_groups or "Features" in e.sections
        for section, kinds in std.section_kinds.items():
            needed = e.kind in kinds or ("feature-group" in kinds and feature_group)
            if needed and section not in e.sections:
                findings.append(Finding(path, e.line, "missing-section",
                                        f"{where} has no '{section}:' section"))
        for section, table in std.sections.items():
            if isinstance(e.sections.get(section), dict):
                findings += check_fields(e.sections[section], table, ctx, path, e.line,
                                         f"{where} {section}")
        if feature_group and not any("derive" in a.qualifiers for a in e.attributes.values()):
            findings.append(Finding(path, e.line, "missing-field",
                                    f"{where} is a feature group with no [derive:] attribute"))
    return findings


def check_blocks(ctx: NotationContext, path) -> List[Finding]:
    std, spec, findings = ctx.std, ctx.spec, []
    seen: Dict[Tuple[str, str], int] = {}
    vectors = {int(n) for e in spec.entities for a in e.attributes.values()
               for n in re.findall(r"Vector\[(\d+)\]", a.type)}
    for b in spec.blocks:
        where = f"{b.kind} '{b.name}'"
        unnamed = b.kind in std.unnamed_blocks
        if unnamed != (b.name == "-"):
            findings.append(Finding(path, b.line, "invalid-value",
                                    f"{where}: a {b.kind} block is "
                                    f"{'named -' if unnamed else 'given a name, not -'}"))
        key = (b.kind, b.name)
        if key in seen:
            findings.append(Finding(path, b.line, "duplicate-block",
                                    f"{where} is declared twice (first at line {seen[key]})"))
        seen.setdefault(key, b.line)
        findings += check_fields(b.fields, std.blocks[b.kind], ctx, path, b.line, where,
                                 b.field_lines)
        if b.kind == "Decision" and not re.fullmatch(r"DD-[A-Z]+-\d{3}", b.name):
            findings.append(Finding(path, b.line, "invalid-value",
                                    f"{where}: decision ids are DD-<MODULE>-<NNN>"))
        if b.kind == "Embedding" and vectors and str(b.fields.get("Dimensions", "")).isdigit() \
                and int(b.fields["Dimensions"]) not in vectors:
            findings.append(Finding(path, b.line, "invalid-value",
                                    f"{where}: Dimensions {b.fields['Dimensions']} matches no "
                                    f"Vector attribute ({sorted(vectors)})"))
    for module in ctx.modules:
        for kind in std.module_blocks.get(module, []):
            if not spec.blocks_of(kind):
                findings.append(Finding(path, 1, "missing-block",
                                        f"module '{module}' has no {kind}: block, which it requires"))
    for facet in facet_names(ctx.fm):
        for kind in std.facet_blocks.get(facet, []):
            if not spec.blocks_of(kind):
                findings.append(Finding(path, 1, "missing-block",
                                        f"facet '{facet}' has no {kind}: block, which it requires"))
    return findings


def facet_names(fm: dict) -> List[str]:
    """Facets as `module:facet`; the frontmatter reader returns `- a:b` as a mapping."""
    out = []
    for entry in (fm.get("facets") or []):
        if isinstance(entry, dict):
            out.extend(f"{k}:{v}" for k, v in entry.items())
        else:
            out.append(str(entry))
    return out


def check_platform_names(text: str, std: Standard, path) -> List[Finding]:
    """A specification names no platform, so it can build on any of them."""
    findings, lines = [], text.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        start = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0) + 1
    for lineno in range(start, len(lines)):
        for platform in sorted(std.platforms):
            flags = re.I if platform.islower() else 0
            if re.search(rf"\b{re.escape(platform)}\b", lines[lineno], flags):
                findings.append(Finding(path, lineno + 1, "platform-reference",
                                        f"names the platform '{platform}'"))
    return findings


def check_notation(fm: dict, text: str, corpus: Corpus, path, design_root: Path = None) -> List[Finding]:
    """Everything the Design Specification Standard requires beyond composition and decisions."""
    std = standard(design_root)
    spec = parse_specification(text, std)
    ctx = NotationContext(fm, spec, std, corpus)
    return (check_platform_names(text, std, path) + check_entity_notation(ctx, path)
            + check_blocks(ctx, path))


def lint_spec(path: Path, design_root: Path = None) -> List[Finding]:
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
    findings += check_notation(fm, text, corpus, p, design_root)
    # a design specification is platform-agnostic, exactly as design/ is
    findings += lint_text(p, text)
    return sorted(findings, key=lambda f: (f.line, f.rule, f.message))


def main(argv: List[str]) -> int:
    if not argv:
        print("usage: spec_lint.py <specification.md> [...]", file=sys.stderr)
        return 2
    findings = []
    for arg in argv:
        target = Path(arg)
        if not target.is_file():
            print(f"warning: not a file: {arg}", file=sys.stderr)
            continue
        findings += lint_spec(target)
    if not findings:
        print(f"spec-lint: clean ({', '.join(argv)})")
        return 0
    for f in findings:
        print(str(f))
    print(f"\nspec-lint: {len(findings)} violation(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
