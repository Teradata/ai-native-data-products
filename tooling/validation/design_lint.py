#!/usr/bin/env python3
"""design_lint: enforce the AI-Native Data Product design language.

Three families of rule:

  * **No platform SQL** (the No-Platform-SQL Rule): applies to `design/` only,
    since concrete SQL is exactly what `implementation/` exists to hold.
  * **Frontmatter** (the Frontmatter section): every design document declares a valid,
    correctly anchored machine-readable identity.
  * **Corpus** (the capability catalogue and Decisions): every capability and decision a document
    names *in its body* resolves against the catalogues, and a standard that
    recommends other than the advocated option says why.
  * **TLM-04** (prohibited generic names): applies to `implementation/` only, over SQL
    and template artifacts, since that is where a column name is actually spelled.

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
change here. The prohibited-name table is read the same way, from the temporal
pattern that declares it: the pattern stays the one place a temporal column is
named, and this file only enforces what it says.

Stdlib only: runs anywhere Python 3.8+ runs (Teradata, Postgres, DuckDB shops alike).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# --------------------------------------------------------------------------- #
# Rule vocabulary (authoritative companion to the No-Platform-SQL Rule)
# --------------------------------------------------------------------------- #

# SQL-dialect fence tags that are prohibited outright in design/.
SQL_FENCE_TAGS = {"sql", "tsql", "plsql", "psql", "mysql", "sqlite"}

# Statement keywords: a fenced-block line beginning with one of these is SQL.
STATEMENT_KEYWORDS = {
    "SELECT", "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "CREATE", "ALTER", "DROP", "TRUNCATE", "GRANT", "REVOKE", "WITH",
}

# High-precision vendor / platform-type tokens. Every entry here is something that
# only ever appears in SQL: never ordinary English prose: so matching anywhere
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

# Known logical types (the Logical Type Vocabulary). Used by the entity-notation check.
LOGICAL_TYPES = {
    "Identifier", "NaturalKey", "Reference", "Code", "ShortText", "Text",
    "LongText", "Json", "Enum", "Integer", "Decimal", "Timestamp", "Date", "Flag", "Vector",
}

# Labels inside an Entity block that are structure, not attribute declarations.
RESERVED_ENTITY_LABELS = {
    "Entity", "Keys", "surrogate", "natural", "kind",
    "Applies patterns", "Requires capabilities", "Invariants",
}

# Frontmatter vocabulary (authoritative companion to the Frontmatter section).
REQUIRED_FM_KEYS = {"title", "anchor", "type", "status", "version", "normative"}
# Frontmatter is identity only (What frontmatter is not for). A document's substance: what it provides,
# requires, applies, and asks a designer to settle: is read from the body, where it can
# carry its reasoning. Keys outside this set are rejected rather than silently tolerated,
# so substance cannot drift back into the header.
OPTIONAL_FM_KEYS = {"supersedes", "implements", "platform", "lint", "lint_reason"}
DOC_TYPES = {"core", "module", "pattern", "implementation", "platform-profile"}
DOC_STATUSES = {"draft", "standard", "deprecated"}

# Documents of these types must additionally declare where they belong.
IMPLEMENTATION_TYPES = {"implementation", "platform-profile"}

# A module describing a versioned entity has to say how it versions and how it deletes.
HISTORY_DECISIONS = ("DEC-TEMPORAL-PATTERN", "DEC-DELETE-STRATEGY")
HISTORY_KIND_RE = re.compile(r"\[kind:\s*History\]")

# The spine every module document carries, so an agent can find the same thing in the same
# place in any of them. Presence and naming are checked; order and numbering are not, and
# a module is free to add its own sections anywhere between these.
MODULE_SPINE = (
    "Purpose",
    "Scope and Boundaries",
    "Entity Model",
    "Applied Patterns",
    "Capabilities and Composition",
    "Integration with Other Modules",
    "Invariants",
    "Designer Responsibilities",
    "Implementation",
)
SECTION_HEADING_RE = re.compile(r"^## \d+\.\s*(.+?)\s*$", re.M)

# Body tables the corpus checks read. A capability row names the capability in the first
# cell; a decisions row names the decision, then the recommended option.
BODY_CAPABILITY_RE = re.compile(r"`([A-Za-z][A-Za-z0-9]*)[`({]")
DECISION_ROW_RE = re.compile(r"^\|\s*`(DEC-[A-Z0-9-]+)`\s*\|\s*`([a-z0-9-]+)`\s*\|(.*)\|")

IGNORE_FILE_RE = re.compile(r"<!--\s*design-lint:\s*ignore-file", re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
DECISION_DECL_RE = re.compile(r"^\s*Decision:\s*(DEC-[A-Z0-9-]+)\s*$")
OPTION_DECL_RE = re.compile(r"^\s*Option:\s*(\S+)\s*(\[advocated\])?\s*$")
CAPABILITY_ROW_RE = re.compile(r"^\|\s*`([A-Za-z][A-Za-z0-9]*)")
# A glossary entry opens a line as `**Term**: definition`. A bold run at the start of a
# line *without* that separator is a cross-reference that happened to wrap, which reads as
# a phantom entry to anyone (or anything) scanning the left margin.
GLOSSARY_BOLD_RE = re.compile(r"^\*\*([^*]+)\*\*(.*)$")
GLOSSARY_SEPARATOR = ": "
INVARIANT_CANDIDATE_RE = re.compile(r"\bINV-[A-Za-z0-9]+-[A-Za-z0-9]+\b")
INVARIANT_STRICT_RE = re.compile(r"^INV-[A-Z][A-Z0-9]*-\d{3}$")
ATTRIBUTE_LINE_RE = re.compile(r"^\s+([A-Za-z_][A-Za-z0-9_ ]*?)\s*:\s*(\S.*)$")
FENCE_RE = re.compile(r"^\s*```(\S*)")


# TLM-04: the prohibited-name table lives in the temporal pattern, section 4.2, and is
# read from there rather than copied here. A row contributes only when its Scope cell
# says the name is prohibited on every profile: `effective_date` / `expiration_date`
# are permitted on a `CURRENT_STATE` entity, and which profile an entity declares is in
# the Semantic entity metadata, not in the file being linted. A name carrying a
# parenthetical qualifier is skipped for the same reason: `created_date` is prohibited
# *as audit* and legal as a day-grain event column, and nothing in a `CREATE TABLE`
# says which it is. Both are left to the catalogue check that can resolve them
# (`conformance-queries.sql` §1b), which is why this set matches that file's §1 exactly.
TEMPORAL_PATTERN_ANCHOR = "temporal-lifecycle-metadata"
PROHIBITED_ROW_RE = re.compile(r"^\|(.+?)\|(.+?)\|(.+?)\|\s*$")
ALL_PROFILES_SCOPE = "all profiles"
BACKTICKED_RE = re.compile(r"`([^`]+)`")
PLAIN_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Artifacts a column name is spelled in. Markdown is excluded on purpose: a README or a
# pattern document is where these names are legitimately discussed, quoted, and given
# their replacements, and flagging that would make the rule unstatable.
#
# `.dcl` is here because a deployed product's access layer ships as
# `00-access/{ProductName}_access_layer.dcl` (see the access-layer binding). Point this
# linter at a generated product tree as well as at the corpus:
#     python tooling/validation/design_lint.py design implementation path/to/product
# The design tree has to be among the paths either way, since the prohibited-name table
# is read from the pattern document rather than copied here.
SQL_ARTIFACT_SUFFIXES = (".sql", ".sql.j2", ".dcl", ".dcl.j2")

# Comment length. Teradata rejects a COMMENT ON longer than 255 characters with
# [5550] Comment string is longer than permitted, and the failure is quiet in the way
# that matters: CREATE runs first, so the object exists and is left undescribed.
# The limit is characters rather than bytes (DBC stores comments as VARCHAR(510)
# CHARACTER SET UNICODE), so prose carrying an em dash is not penalised for it and a
# plain len() is the right measure.
#
# A literal containing Jinja control flow is skipped: its static length is the sum of
# every branch, not what any deployment sees. Those are measured after rendering, by
# tooling/validation/tests/test_templates_render.py, which is also where a simple
# {{ placeholder }} gets its real width.
COMMENT_LIMIT = 255
COMMENT_RE = re.compile(r"COMMENT ON [A-Z]+ ([^\n]+?) IS\s*'(.*?)';", re.S)
JINJA_CONTROL_RE = re.compile(r"\{%")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


def _has_legacy_directive(text: str) -> bool:
    """The legacy HTML directive, which a document without frontmatter uses to opt out.

    Kept separate from `_is_ignored` because the two escape hatches waive different
    things. The frontmatter key waives the content rules of a document that has, by
    definition, declared an identity. The HTML directive exists for a document that
    declares none, so waiving the content rules and then failing it for the missing
    frontmatter leaves it with no way to opt out at all.
    """
    return any(IGNORE_FILE_RE.search(line) for line in text.splitlines()[:5])


def _is_ignored(text: str) -> bool:
    """A file opts out entirely, via frontmatter `lint: ignore-file` or a legacy HTML directive."""
    fm, _ = parse_frontmatter(text)
    if fm and fm.get("lint") == "ignore-file":
        return True
    return _has_legacy_directive(text)


# --------------------------------------------------------------------------- #
# Frontmatter (Design Language: Frontmatter)
# --------------------------------------------------------------------------- #

def parse_frontmatter(text: str):
    """Parse the leading YAML frontmatter block.

    Deliberately handles only the subset the Frontmatter section defines: scalars, lists of
    scalars, and lists of flat mappings: so the linter stays stdlib-only. Returns
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

    A binding README or a platform profile is anchored on its directory: the module,
    pattern, or platform it belongs to. Everything else is anchored on its filename,
    normalised to the kebab-case the anchor vocabulary uses (`MASTER_DESIGN.md` is
    anchored `master-design`).
    """
    if path.stem.lower() == "readme" or path.name == "PLATFORM_PROFILE.md":
        return path.parent.name.lower()
    return path.stem.lower().replace("_", "-")


def find_frontmatter_violations(path: Path, text: str) -> List[Finding]:
    """Frontmatter present, complete, well-typed, and anchored to its filename."""
    p = str(path)
    fm, _ = parse_frontmatter(text)
    if fm is None:
        return [Finding(p, 1, "frontmatter-missing",
                        "design document has no frontmatter block (Design Language: Frontmatter)")]

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

    return findings


def find_sql_violations(text: str, path: str = "<text>") -> List[Finding]:
    """The No-Platform-SQL Rule: no SQL fences, no SQL statements, no vendor tokens."""
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
                    f"platform SQL token '{label}': use a logical type instead (Design Language: Logical Type Vocabulary)",
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
    """Invariant ids must follow INV-<MODULE>-<NNN> (Design Language: Invariants)."""
    findings: List[Finding] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        for tok in INVARIANT_CANDIDATE_RE.findall(raw):
            if not INVARIANT_STRICT_RE.match(tok):
                findings.append(Finding(
                    path, lineno, "invariant-id",
                    f"malformed invariant id '{tok}': expected INV-<MODULE>-<NNN>",
                ))
    return findings


# --------------------------------------------------------------------------- #
# Corpus checks: cross-document references (Frontmatter, capability catalogue, Decisions)
# --------------------------------------------------------------------------- #

def load_capability_catalogue(text: str) -> set:
    """Capability names from the capability catalogue in the design-language document."""
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


def load_prohibited_names(text: str) -> dict:
    """Prohibited temporal column names to their canonical replacement (TLM-04).

    Read from the prohibited-generic-names table in the temporal pattern, so the pattern
    remains the single place a temporal column is named and this linter needs no edit
    when the table changes. Only rows scoped to every profile contribute; see the note
    on ``TEMPORAL_PATTERN_ANCHOR`` for what is deliberately left out and why.
    """
    names = {}
    for line in text.splitlines():
        m = PROHIBITED_ROW_RE.match(line.strip())
        if not m:
            continue
        prohibited_cell, canonical_cell, scope_cell = m.groups()
        if scope_cell.strip().lower() != ALL_PROFILES_SCOPE:
            continue
        # Parentheticals are annotation on both sides of the row ("(a `Flag`)"), never
        # part of the name being named.
        canonical = BACKTICKED_RE.findall(re.sub(r"\([^)]*\)", "", canonical_cell))
        if not canonical:
            continue
        replacement = " / ".join(canonical)
        for part in prohibited_cell.split(","):
            if "(" in part:  # a qualified entry: not decidable from the file alone
                continue
            for token in BACKTICKED_RE.findall(part):
                if PLAIN_IDENTIFIER_RE.match(token):
                    names[token] = replacement
    return names


def mask_sql_noise(text: str) -> str:
    """Blank out everything in a SQL artifact that is not an identifier.

    Comments and string literals are replaced with spaces, newlines preserved, so line
    numbers still point at the source. This is what lets the rule be stated without
    exceptions: `conformance-queries.sql` scans *for* the prohibited names and
    `10-documentation-tables.sql.j2` explains in its header which spellings it replaced,
    and neither is a column named that way. A prohibited name inside SQL embedded in a
    string literal (a stored `Query_Cookbook` recipe) is invisible here, which is the
    accepted cost of not needing an allowlist.
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":                     # -- line comment
            j = text.find("\n", i)
            j = n if j == -1 else j
        elif ch == "/" and nxt == "*":                   # /* block comment */
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
        elif ch == "{" and nxt == "#":                   # {# jinja comment #}
            j = text.find("#}", i + 2)
            j = n if j == -1 else j + 2
        elif ch == "'":                                  # 'string literal', '' escapes
            j = i + 1
            while j < n:
                if text[j] == "'":
                    if j + 1 < n and text[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
        else:
            out.append(ch)
            i += 1
            continue
        out.append("".join(c if c == "\n" else " " for c in text[i:j]))
        i = j
    return "".join(out)


def find_prohibited_name_violations(text: str, path: str, names: dict) -> List[Finding]:
    """TLM-04: no prohibited generic temporal names in a SQL artifact."""
    if not names:
        return []
    findings: List[Finding] = []
    pattern = re.compile(r"\b(" + "|".join(sorted(names, key=len, reverse=True)) + r")\b")
    for lineno, raw in enumerate(mask_sql_noise(text).splitlines(), start=1):
        for tok in pattern.findall(raw):
            findings.append(Finding(
                path, lineno, "tlm-04",
                f"prohibited temporal column name '{tok}': use '{names[tok]}' "
                f"(temporal-lifecycle-metadata, prohibited generic names)",
            ))
    return findings


def find_comment_length_violations(text: str, path: str,
                                   limit: int = COMMENT_LIMIT) -> List[Finding]:
    """No COMMENT ON longer than the platform's limit (Teradata [5550])."""
    findings: List[Finding] = []
    for m in COMMENT_RE.finditer(text):
        target, body = m.group(1), m.group(2)
        if JINJA_CONTROL_RE.search(body):
            continue
        if len(body) <= limit:
            continue
        line = text.count("\n", 0, m.start()) + 1
        findings.append(Finding(
            path, line, "comment-length",
            f"comment on {target.strip()} is {len(body)} characters, over the {limit} "
            f"limit: the object is created and left undescribed when the comment is "
            f"rejected",
        ))
    return findings


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
                f"'{term}' opens a line but is not an entry: a wrapped cross-reference "
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


def read_document_capabilities(text: str) -> dict:
    """Capabilities a document names, as ``{"provides": [...], "requires": [...]}``.

    Read from the body rather than frontmatter (What frontmatter is not for): the tables carry a *why*
    column and can say a provider is `self` *or* `platform`, nuance a header list drops.
    """
    found = {"provides": [], "requires": []}
    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("**Provides"):
            section = "provides"
            continue
        if stripped.startswith("**Requires"):
            section = "requires"
            continue
        if section is None:
            continue
        if stripped.startswith("|"):
            # A row's first cell may name several capabilities at once, where one line of
            # prose covers them all ("CurrentStateFilter, NaturalKeyLookup, AccessView").
            cell = stripped.strip("|").split("|")[0]
            found[section].extend(BODY_CAPABILITY_RE.findall(cell))
        elif stripped:
            # Any non-table line closes the table: including a heading, which is how a
            # Decisions table two sections later once got read as a list of capabilities.
            section = None
    return found


def read_document_decisions(text: str) -> List[Tuple[str, str, str]]:
    """Decisions a document asks a designer to settle: ``(id, recommended, rationale)``.

    Read from the Decisions-to-settle table under Designer Responsibilities, which is
    where a designer meets them and where the design skill picks them up.
    """
    found = []
    for line in text.splitlines():
        m = DECISION_ROW_RE.match(line.strip())
        if m:
            found.append((m.group(1), m.group(2), m.group(3)))
    return found


def find_spine_violations(text: str, path: str) -> List[Finding]:
    """Every module document carries the canonical spine sections, by name.

    A module may add sections of its own anywhere, and the numbering is its business: what has to hold is that the same concern is findable under the same heading in every
    module. A section may carry a subtitle after a colon (`Entity Model: Runtime Facet`); the head of the heading is what must match.
    """
    headings = []
    for name in SECTION_HEADING_RE.findall(text):
        headings.append(re.split(r"\s*:\s*", name)[0].strip())
    missing = [s for s in MODULE_SPINE if s not in headings]
    return [Finding(path, 1, "module-spine",
                    f"module is missing the '{s}' section: every module carries the same "
                    f"spine so an agent finds the same concern in the same place")
            for s in missing]


def find_corpus_violations(docs: dict) -> List[Finding]:
    """Every capability and decision a document names in its body must resolve."""
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
        is_catalogue = fm.get("anchor") == "advocated-standards"

        # Capabilities named in the body's Provides / Requires tables exist in the catalogue.
        if capabilities and fm.get("anchor") != "design-language":
            named = read_document_capabilities(text)
            for cap in named["provides"] + named["requires"]:
                if cap not in capabilities:
                    findings.append(Finding(p, 1, "unknown-capability",
                                            f"'{cap}' is not in the capability catalogue "
                                            f"(Design Language: capability catalogue)"))

        implements = fm.get("implements")
        if implements and implements not in anchors:
            findings.append(Finding(p, 1, "unknown-anchor",
                                    f"implements anchor '{implements}' does not resolve"))
        for ref in (fm.get("supersedes") or []):
            if isinstance(ref, str) and ref not in anchors:
                findings.append(Finding(p, 1, "unknown-anchor",
                                        f"supersedes anchor '{ref}' does not resolve"))

        # Decisions a document asks a designer to settle: known id, valid option, and a
        # reason whenever the standard recommends other than the advocated option.
        listed = set()
        if not is_catalogue and fm.get("anchor") != "design-language":
            for did, recommended, rationale in read_document_decisions(text):
                listed.add(did)
                if decisions and did not in decisions:
                    findings.append(Finding(p, 1, "unknown-decision",
                                            f"'{did}' is not in the decision catalogue"))
                    continue
                options = decisions.get(did, {})
                if options and recommended not in options:
                    findings.append(Finding(p, 1, "invalid-choice",
                                            f"'{recommended}' is not an option of {did} "
                                            f"(expected one of {sorted(options)})"))
                elif options and not options[recommended] and "because" not in rationale.lower():
                    findings.append(Finding(p, 1, "unjustified-choice",
                                            f"{did} recommends '{recommended}' over the advocated "
                                            f"option without saying why (Design Language: Decisions)"))

        if fm.get("anchor") == "glossary":
            findings.extend(find_glossary_violations(text, p))
        if fm.get("type") == "module":
            findings.extend(find_spine_violations(text, p))

        # A module with a versioned entity has to say how it versions and how it deletes.
        if fm.get("type") == "module" and HISTORY_KIND_RE.search(text):
            for required in HISTORY_DECISIONS:
                if required not in listed:
                    findings.append(Finding(p, 1, "undeclared-decision",
                                            f"module describes a History entity but does not ask "
                                            f"the designer to settle {required} (Design Language: "
                                            f"Decisions)"))
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
    an implementation directory: a README directly under `design/` or a platform root
    is navigation, and the supporting `.md` files inside a binding directory describe
    it rather than declaring it.
    """
    parts = [q.lower() for q in path.parts]
    if path.stem.lower() != "readme":
        return "design" in parts or path.name == "PLATFORM_PROFILE.md"
    return ("modules" in parts or "patterns" in parts) and "implementation" in parts


def is_sql_artifact(path: Path) -> bool:
    """A file whose content spells column names: `.sql` or a `.sql.j2` template."""
    return path.name.endswith(SQL_ARTIFACT_SUFFIXES)


def lint_paths(paths: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    docs = {}
    sql_artifacts: List[Path] = []
    for p in paths:
        target = Path(p)
        if target.is_dir():
            files = sorted(target.rglob("*.md"))
            sql_artifacts += [q for q in sorted(target.rglob("*")) if is_sql_artifact(q)]
        elif target.is_file():
            files = [target] if target.suffix == ".md" else []
            if is_sql_artifact(target):
                sql_artifacts.append(target)
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
            text = md.read_text(encoding="utf-8")
            # The frontmatter key `lint: ignore-file` waives the content rules, not the
            # document's identity: it is declared *in* frontmatter, so the document has
            # one and still has to get it right. The legacy HTML directive is the opt-out
            # for a document carrying no frontmatter at all, and waives the identity rules
            # too: holding it to a block it opted out of declaring leaves it no way out.
            # Either way, a document that does have frontmatter still contributes its
            # anchor and catalogues to the corpus.
            if not _has_legacy_directive(text):
                findings += find_frontmatter_violations(md, text)
            fm, offset = parse_frontmatter(text)
            if fm is not None:
                docs[md] = (fm, text, offset)
    findings += find_corpus_violations(docs)

    # TLM-04 runs last: the prohibited names come from the temporal pattern, which has
    # to be loaded before any artifact can be checked against it. Lint a tree with no
    # pattern document in it and the check is silently inert, which is correct: there is
    # nothing to enforce, as opposed to nothing prohibited.
    prohibited = {}
    for fm, text, _ in docs.values():
        if fm.get("anchor") == TEMPORAL_PATTERN_ANCHOR and fm.get("type") == "pattern":
            prohibited = load_prohibited_names(text)
    for sql in sql_artifacts:
        sql_text = sql.read_text(encoding="utf-8")
        findings += find_prohibited_name_violations(sql_text, str(sql), prohibited)
        findings += find_comment_length_violations(sql_text, str(sql))
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
