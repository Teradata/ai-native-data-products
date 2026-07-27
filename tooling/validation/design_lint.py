#!/usr/bin/env python3
"""design_lint — enforce the AI-Native Data Product design language.

Three families of rule:

  * **No platform SQL** (Design Language Section 9) — applies to `design/` only,
    since concrete SQL is exactly what `implementation/` exists to hold.
  * **Frontmatter** (Section 3.1) — every design document declares a valid,
    correctly anchored machine-readable identity.
  * **Corpus** (Sections 6.1 and 8) — every capability, pattern anchor, and
    decision named in frontmatter resolves, and a design that departs from an
    advocated option records why.

Used two ways:

  1. As a CLI, over both hierarchies:
         python tooling/validation/design_lint.py design implementation
     Exits non-zero if any violation is found.

  2. As a library, so unit tests validating a worked module can assert that a
     specific design document is clean:
         from design_lint import lint_text
         assert lint_text("design/modules/domain.md", text) == []

The vocabularies below are the authoritative companion to those sections; the
sections are the human-readable statement, this file is what actually runs. The
capability and decision catalogues are the exception: they are read from the
documents that define them, so adding a capability or a decision needs no code
change here.

Stdlib only — runs anywhere Python 3.8+ runs (Teradata, Postgres, DuckDB shops alike).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# --------------------------------------------------------------------------- #
# Rule vocabulary (authoritative companion to Design Language Section 9)
# --------------------------------------------------------------------------- #

# SQL-dialect fence tags that are prohibited outright in design/.
SQL_FENCE_TAGS = {"sql", "tsql", "plsql", "psql", "mysql", "sqlite"}

# Statement keywords: a fenced-block line beginning with one of these is SQL.
STATEMENT_KEYWORDS = {
    "SELECT", "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "CREATE", "ALTER", "DROP", "TRUNCATE", "GRANT", "REVOKE", "WITH",
}

# High-precision vendor / platform-type tokens. Every entry here is something that
# only ever appears in SQL — never ordinary English prose — so matching anywhere
# (prose or code) is safe. Deliberately does NOT include bare words like TABLE,
# VIEW, DATE, INDEX, DEFAULT, VECTOR that also occur in normal writing.
VENDOR_TOKEN_PATTERNS = [
    (re.compile(r"\bVARCHAR\b"), "VARCHAR"),
    (re.compile(r"\bN?CHAR\s*\("), "CHAR(n)"),
    (re.compile(r"\bBIGINT\b"), "BIGINT"),
    (re.compile(r"\bSMALLINT\b"), "SMALLINT"),
    (re.compile(r"\bTINYINT\b"), "TINYINT"),
    (re.compile(r"\bBYTEINT\b"), "BYTEINT"),
    (re.compile(r"\bDECIMAL\s*\("), "DECIMAL(...)"),
    (re.compile(r"\bNUMERIC\s*\("), "NUMERIC(...)"),
    (re.compile(r"\bFLOAT32\b"), "FLOAT32"),
    (re.compile(r"\bTIMESTAMP\s*\("), "TIMESTAMP(...)"),
    (re.compile(r"\bPRIMARY\s+INDEX\b"), "PRIMARY INDEX"),
    (re.compile(r"\bUNIQUE\s+PRIMARY\s+INDEX\b"), "UNIQUE PRIMARY INDEX"),
    (re.compile(r"\bGENERATED\s+ALWAYS\s+AS\s+IDENTITY\b"), "GENERATED ALWAYS AS IDENTITY"),
    (re.compile(r"\bNOT\s+NULL\b"), "NOT NULL"),
    (re.compile(r"\bDEFAULT\s+(?:[0-9']|TIMESTAMP\b|DATE\b|CURRENT_)"), "DEFAULT <value>"),
    (re.compile(r"\bCOMMENT\s+ON\b"), "COMMENT ON"),
    (re.compile(r"::\s*VECTOR\b"), "::VECTOR cast"),
    (re.compile(r"\bTD_[A-Za-z_]\w*"), "TD_* function"),
]

# Known logical types (Design Language Section 4). Used by the entity-notation check.
LOGICAL_TYPES = {
    "Identifier", "NaturalKey", "Reference", "Code", "ShortText", "Text",
    "LongText", "Json", "Enum", "Integer", "Decimal", "Timestamp", "Date", "Flag", "Vector",
}

# Labels inside an Entity block that are structure, not attribute declarations.
RESERVED_ENTITY_LABELS = {
    "Entity", "Keys", "surrogate", "natural", "kind",
    "Applies patterns", "Requires capabilities", "Invariants",
}

# Frontmatter vocabulary (authoritative companion to Design Language Section 3.1).
REQUIRED_FM_KEYS = {"title", "anchor", "type", "status", "version", "normative"}
OPTIONAL_FM_KEYS = {
    "provides", "requires", "patterns", "decisions", "supersedes",
    "implements", "platform", "lint", "lint_reason",
}
DOC_TYPES = {"core", "module", "pattern", "implementation", "platform-profile"}
DOC_STATUSES = {"draft", "standard", "deprecated"}
REQUIRE_STRENGTHS = {"hard", "soft"}

# Documents of these types must additionally declare where they belong.
IMPLEMENTATION_TYPES = {"implementation", "platform-profile"}

# A module describing a versioned entity has to have settled these.
HISTORY_DECISIONS = ("DEC-TEMPORAL-PATTERN", "DEC-DELETE-STRATEGY")
HISTORY_KIND_RE = re.compile(r"\[kind:\s*History\]")

IGNORE_FILE_RE = re.compile(r"<!--\s*design-lint:\s*ignore-file", re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
DECISION_DECL_RE = re.compile(r"^\s*Decision:\s*(DEC-[A-Z0-9-]+)\s*$")
OPTION_DECL_RE = re.compile(r"^\s*Option:\s*(\S+)\s*(\[advocated\])?\s*$")
CAPABILITY_ROW_RE = re.compile(r"^\|\s*`([A-Za-z][A-Za-z0-9]*)")
# A glossary entry opens a line as `**Term** — definition`. A bold run at the start of a
# line *without* that separator is a cross-reference that happened to wrap, which reads as
# a phantom entry to anyone (or anything) scanning the left margin.
GLOSSARY_BOLD_RE = re.compile(r"^\*\*([^*]+)\*\*(.*)$")
GLOSSARY_SEPARATOR = " — "
INVARIANT_CANDIDATE_RE = re.compile(r"\bINV-[A-Za-z0-9]+-[A-Za-z0-9]+\b")
INVARIANT_STRICT_RE = re.compile(r"^INV-[A-Z][A-Z0-9]*-\d{3}$")
ATTRIBUTE_LINE_RE = re.compile(r"^\s+([A-Za-z_][A-Za-z0-9_ ]*?)\s*:\s*(\S.*)$")
FENCE_RE = re.compile(r"^\s*```(\S*)")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


def _is_ignored(text: str) -> bool:
    """A file opts out entirely, via frontmatter `lint: ignore-file` or a legacy HTML directive."""
    fm, _ = parse_frontmatter(text)
    if fm and fm.get("lint") == "ignore-file":
        return True
    for line in text.splitlines()[:5]:
        if IGNORE_FILE_RE.search(line):
            return True
    return False


# --------------------------------------------------------------------------- #
# Frontmatter (Design Language Section 3.1)
# --------------------------------------------------------------------------- #

def parse_frontmatter(text: str):
    """Parse the leading YAML frontmatter block.

    Deliberately handles only the subset Section 3.1 defines — scalars, lists of
    scalars, and lists of flat mappings — so the linter stays stdlib-only. Returns
    ``(mapping, line_count)``; ``(None, 0)`` when the document has no frontmatter.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, 0
    block = m.group(1)
    data = {}
    key = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()

        if indent == 0 and not line.startswith("- "):
            key, _, value = line.partition(":")
            key = key.strip()
            value = _strip_comment(value.strip())
            data[key] = value if value else []
            continue

        if key is None:
            continue
        bucket = data.setdefault(key, [])
        if not isinstance(bucket, list):
            bucket = data[key] = []

        if line.startswith("- "):
            item = line[2:].strip()
            if ":" in item:
                k, _, v = item.partition(":")
                bucket.append({k.strip(): _strip_comment(v.strip())})
            else:
                bucket.append(_strip_comment(item))
        elif bucket and isinstance(bucket[-1], dict):
            k, _, v = line.partition(":")
            bucket[-1][k.strip()] = _strip_comment(v.strip())
    return data, m.group(0).count("\n")


def _strip_comment(value: str) -> str:
    """Drop a trailing ` # comment`, which the schema examples use for annotation."""
    idx = value.find(" #")
    return value[:idx].strip() if idx != -1 else value.strip()


def expected_anchor(path: Path) -> str:
    """The anchor a document's location implies.

    A binding README or a platform profile is anchored on its directory — the module,
    pattern, or platform it belongs to. Everything else is anchored on its filename,
    normalised to the kebab-case the anchor vocabulary uses (`MASTER_DESIGN.md` is
    anchored `master-design`).
    """
    if path.stem.lower() == "readme" or path.name == "PLATFORM_PROFILE.md":
        return path.parent.name.lower()
    return path.stem.lower().replace("_", "-")


def find_frontmatter_violations(path: Path, text: str) -> List[Finding]:
    """Section 3.1: frontmatter present, complete, well-typed, and anchored to its filename."""
    p = str(path)
    fm, _ = parse_frontmatter(text)
    if fm is None:
        return [Finding(p, 1, "frontmatter-missing",
                        "design document has no frontmatter block (Design Language S3.1)")]

    findings: List[Finding] = []
    for missing in sorted(REQUIRED_FM_KEYS - set(fm)):
        findings.append(Finding(p, 1, "frontmatter-key",
                                f"missing required frontmatter key '{missing}'"))
    for unknown in sorted(set(fm) - REQUIRED_FM_KEYS - OPTIONAL_FM_KEYS):
        findings.append(Finding(p, 1, "frontmatter-key",
                                f"unknown frontmatter key '{unknown}'"))

    doc_type = fm.get("type")
    if doc_type and doc_type not in DOC_TYPES:
        findings.append(Finding(p, 1, "frontmatter-enum",
                                f"type '{doc_type}' is not one of {sorted(DOC_TYPES)}"))
    status = fm.get("status")
    if status and status not in DOC_STATUSES:
        findings.append(Finding(p, 1, "frontmatter-enum",
                                f"status '{status}' is not one of {sorted(DOC_STATUSES)}"))
    normative = fm.get("normative")
    if normative and normative not in {"true", "false"}:
        findings.append(Finding(p, 1, "frontmatter-enum",
                                f"normative '{normative}' must be true or false"))

    anchor, want = fm.get("anchor"), expected_anchor(path)
    if anchor and anchor != want:
        findings.append(Finding(p, 1, "anchor-mismatch",
                                f"anchor '{anchor}' does not match its location (expected '{want}')"))

    if doc_type in IMPLEMENTATION_TYPES and not fm.get("platform"):
        findings.append(Finding(p, 1, "frontmatter-key",
                                f"type '{doc_type}' requires a 'platform'"))
    if doc_type == "implementation" and not fm.get("implements"):
        findings.append(Finding(p, 1, "frontmatter-key",
                                "type 'implementation' requires an 'implements' anchor"))

    for req in fm.get("requires", []) or []:
        if not isinstance(req, dict):
            findings.append(Finding(p, 1, "frontmatter-shape",
                                    f"requires entry '{req}' must declare capability, strength, provider"))
            continue
        strength = req.get("strength")
        if strength not in REQUIRE_STRENGTHS:
            findings.append(Finding(p, 1, "frontmatter-enum",
                                    f"requires '{req.get('capability')}' has strength "
                                    f"'{strength}' — expected hard or soft"))
    return findings


def find_sql_violations(text: str, path: str = "<text>") -> List[Finding]:
    """Rules 1-3 of Section 9: no SQL fences, no SQL statements, no vendor tokens."""
    findings: List[Finding] = []
    in_fence = False
    fence_lang = ""
    in_entity_block = False

    for lineno, raw in enumerate(text.splitlines(), start=1):
        fence = FENCE_RE.match(raw)
        if fence:
            if not in_fence:
                in_fence = True
                fence_lang = fence.group(1).lower()
                in_entity_block = False
                if fence_lang in SQL_FENCE_TAGS:
                    findings.append(Finding(
                        path, lineno, "sql-fence",
                        f"SQL-tagged code block (```{fence_lang}) is not allowed in design/",
                    ))
            else:
                in_fence = False
                fence_lang = ""
                in_entity_block = False
            continue

        # Rule 2: SQL statement keyword starting a line inside any fenced block.
        if in_fence:
            first = raw.strip().split(" ", 1)[0].upper().rstrip(";(")
            if first in STATEMENT_KEYWORDS:
                findings.append(Finding(
                    path, lineno, "sql-statement",
                    f"SQL statement '{first}' inside a code block belongs in implementation/",
                ))
            if raw.strip().startswith("Entity:"):
                in_entity_block = True

        # Rule 3: vendor / platform-type tokens, anywhere (prose or code).
        for pattern, label in VENDOR_TOKEN_PATTERNS:
            if pattern.search(raw):
                findings.append(Finding(
                    path, lineno, "vendor-token",
                    f"platform SQL token '{label}' — use a logical type instead (Design Language S4)",
                ))

        # Structural: unknown logical type inside an Entity pseudo-block.
        if in_fence and in_entity_block:
            findings.extend(_check_entity_attribute(raw, lineno, path))

    return findings


def _check_entity_attribute(raw: str, lineno: int, path: str) -> List[Finding]:
    m = ATTRIBUTE_LINE_RE.match(raw)
    if not m:
        return []
    key = m.group(1).strip()
    if key in RESERVED_ENTITY_LABELS:
        return []
    rhs = m.group(2).strip()
    base = re.match(r"([A-Za-z_]+)", rhs)
    if not base:
        return []
    type_name = base.group(1)
    # Ignore prose-ish continuation lines: attribute types are capitalised.
    if not type_name[0].isupper():
        return []
    if type_name not in LOGICAL_TYPES:
        return [Finding(
            path, lineno, "unknown-type",
            f"'{type_name}' is not a logical type (Design Language S4)",
        )]
    return []


def find_invariant_violations(text: str, path: str = "<text>") -> List[Finding]:
    """Invariant ids must follow INV-<MODULE>-<NNN> (Design Language Section 7)."""
    findings: List[Finding] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        for tok in INVARIANT_CANDIDATE_RE.findall(raw):
            if not INVARIANT_STRICT_RE.match(tok):
                findings.append(Finding(
                    path, lineno, "invariant-id",
                    f"malformed invariant id '{tok}' — expected INV-<MODULE>-<NNN>",
                ))
    return findings


# --------------------------------------------------------------------------- #
# Corpus checks — cross-document references (Design Language S3.1, S6.1, S8)
# --------------------------------------------------------------------------- #

def load_capability_catalogue(text: str) -> set:
    """Capability names from the Section 6.1 table of the design-language document."""
    names, in_section = set(), False
    for line in text.splitlines():
        if line.startswith("### 6.1"):
            in_section = True
            continue
        if in_section and line.startswith(("### ", "## ")):
            break
        if in_section:
            m = CAPABILITY_ROW_RE.match(line)
            if m:
                names.add(m.group(1))
    return names


def load_decision_catalogue(text: str) -> dict:
    """Decision ids to ``{option: is_advocated}``, read from the catalogue's notation blocks."""
    decisions, current = {}, None
    for line in text.splitlines():
        d = DECISION_DECL_RE.match(line)
        if d:
            current = d.group(1)
            decisions.setdefault(current, {})
            continue
        o = OPTION_DECL_RE.match(line)
        if o and current:
            decisions[current][o.group(1)] = bool(o.group(2))
    return decisions


def find_glossary_violations(text: str, path: str) -> List[Finding]:
    """A glossary stays alphabetical, and every left-margin bold run is a real entry.

    Both failures are the same underlying mistake seen from different angles: a bold
    cross-reference that wraps onto the start of a line looks like a definition, and
    sorts as one. Catching it keeps the glossary scannable and keeps anything that
    parses entries off the left margin honest.
    """
    findings: List[Finding] = []
    entries: List[Tuple[str, int]] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        m = GLOSSARY_BOLD_RE.match(raw)
        if not m:
            continue
        term, rest = m.group(1), m.group(2)
        if term.startswith("End of"):
            continue
        if not rest.startswith(GLOSSARY_SEPARATOR):
            findings.append(Finding(
                path, lineno, "glossary-entry",
                f"'{term}' opens a line but is not an entry — a wrapped cross-reference "
                f"reads as a phantom definition; reflow so it is not at the left margin",
            ))
            continue
        entries.append((term, lineno))

    for (previous, _), (term, lineno) in zip(entries, entries[1:]):
        if term.lower() < previous.lower():
            findings.append(Finding(
                path, lineno, "glossary-order",
                f"'{term}' is out of alphabetical order (follows '{previous}')",
            ))
    return findings


def find_corpus_violations(docs: dict) -> List[Finding]:
    """Every capability, anchor, and decision named in frontmatter must resolve."""
    findings: List[Finding] = []
    capabilities: set = set()
    decisions: dict = {}
    for fm, text, _ in docs.values():
        if fm.get("anchor") == "design-language":
            capabilities = load_capability_catalogue(text)
        if fm.get("anchor") == "advocated-standards":
            decisions = load_decision_catalogue(text)

    anchors = {fm.get("anchor") for fm, _, _ in docs.values() if fm.get("anchor")}

    for path, (fm, text, _) in sorted(docs.items()):
        p = str(path)
        # Capabilities named in provides/requires exist in the catalogue.
        if capabilities:
            named = [c for c in (fm.get("provides") or []) if isinstance(c, str)]
            named += [r.get("capability") for r in (fm.get("requires") or [])
                      if isinstance(r, dict) and r.get("capability")]
            for cap in named:
                if cap not in capabilities:
                    findings.append(Finding(p, 1, "unknown-capability",
                                            f"'{cap}' is not in the capability catalogue "
                                            f"(Design Language S6.1)"))
        # Anchors named in patterns/implements resolve to a document that exists.
        for ref in (fm.get("patterns") or []):
            if isinstance(ref, str) and ref not in anchors:
                findings.append(Finding(p, 1, "unknown-anchor",
                                        f"pattern anchor '{ref}' does not resolve to a document"))
        implements = fm.get("implements")
        if implements and implements not in anchors:
            findings.append(Finding(p, 1, "unknown-anchor",
                                    f"implements anchor '{implements}' does not resolve"))

        # Decisions: known id, valid option, and a reason for departing from the default.
        declared = set()
        for entry in (fm.get("decisions") or []):
            if not isinstance(entry, dict):
                continue
            did = entry.get("id")
            declared.add(did)
            if decisions and did not in decisions:
                findings.append(Finding(p, 1, "unknown-decision",
                                        f"'{did}' is not in the decision catalogue"))
                continue
            choice = entry.get("choice")
            if not choice:
                continue  # the catalogue itself lists ids without choosing
            options = decisions.get(did, {})
            if options and choice not in options:
                findings.append(Finding(p, 1, "invalid-choice",
                                        f"'{choice}' is not an option of {did} "
                                        f"(expected one of {sorted(options)})"))
            elif options and not options[choice] and not entry.get("because"):
                findings.append(Finding(p, 1, "unjustified-choice",
                                        f"{did} chooses '{choice}' over the advocated option "
                                        f"without a 'because' (Design Language S8.2)"))

        if fm.get("anchor") == "glossary":
            findings.extend(find_glossary_violations(text, p))

        # A module with a versioned entity has to have settled how it versions and deletes.
        if fm.get("type") == "module" and HISTORY_KIND_RE.search(text):
            for required in HISTORY_DECISIONS:
                if required not in declared:
                    findings.append(Finding(p, 1, "undeclared-decision",
                                            f"module declares a History entity but does not "
                                            f"declare {required} (Design Language S8.3)"))
    return findings


def lint_text(path: str, text: str) -> List[Finding]:
    """Run all checks on document text. Returns [] for a clean (or ignored) file."""
    if _is_ignored(text):
        return []
    findings = find_sql_violations(text, path)
    findings += find_invariant_violations(text, path)
    return sorted(findings, key=lambda f: (f.line, f.rule))


def lint_file(path: Path) -> List[Finding]:
    text = path.read_text(encoding="utf-8")
    return lint_text(str(path), text)


def is_design_document(path: Path) -> bool:
    """Design documents carry frontmatter; navigation and supporting files do not.

    A README is a design document only when it is the binding document at the root of
    an implementation directory — a README directly under `design/` or a platform root
    is navigation, and the supporting `.md` files inside a binding directory describe
    it rather than declaring it.
    """
    parts = [q.lower() for q in path.parts]
    if path.stem.lower() != "readme":
        return "design" in parts or path.name == "PLATFORM_PROFILE.md"
    return ("modules" in parts or "patterns" in parts) and "implementation" in parts


def lint_paths(paths: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    docs = {}
    for p in paths:
        target = Path(p)
        if target.is_dir():
            files = sorted(target.rglob("*.md"))
        elif target.is_file():
            files = [target]
        else:
            print(f"warning: path not found: {p}", file=sys.stderr)
            continue
        for md in files:
            # The no-platform-SQL rule governs design/ only: concrete SQL is exactly what
            # implementation/ is for, so linting it there would flag the intended content.
            if "design" in [q.lower() for q in md.parts]:
                findings += lint_file(md)
            if not is_design_document(md):
                continue
            # An ignore directive waives the content rules, not the document's identity:
            # it must still declare valid frontmatter and still contributes its anchor
            # and catalogues to the corpus.
            text = md.read_text(encoding="utf-8")
            findings += find_frontmatter_violations(md, text)
            fm, offset = parse_frontmatter(text)
            if fm is not None:
                docs[md] = (fm, text, offset)
    findings += find_corpus_violations(docs)
    return sorted(findings, key=lambda f: (f.path, f.line, f.rule))


def main(argv: List[str]) -> int:
    paths = argv[1:] or ["design"]
    findings = lint_paths(paths)
    if not findings:
        print(f"design-lint: clean ({', '.join(paths)})")
        return 0
    for f in findings:
        print(str(f))
    print(f"\ndesign-lint: {len(findings)} violation(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv))
