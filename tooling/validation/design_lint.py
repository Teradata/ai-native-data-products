#!/usr/bin/env python3
"""design_lint — enforce the AI-Native Data Product design language on design/ docs.

This linter is the executable form of the "No-Platform-SQL Rule" (Design Language
Section 8) plus a couple of lightweight structural checks. It is used two ways:

  1. As a CLI, to keep `design/` free of platform SQL:
         python tooling/validation/design_lint.py design
     Exits non-zero if any violation is found.

  2. As a library, so unit tests validating a worked module can assert that a
     specific design document is clean:
         from design_lint import lint_text
         assert lint_text("design/modules/domain.md", text) == []

The token lists below are the authoritative companion to Design Language Section 8;
that section is the human-readable statement, this file is what actually runs.

Stdlib only — runs anywhere Python 3.8+ runs (Teradata, Postgres, DuckDB shops alike).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

# --------------------------------------------------------------------------- #
# Rule vocabulary (authoritative companion to Design Language Section 8)
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

IGNORE_FILE_RE = re.compile(r"<!--\s*design-lint:\s*ignore-file", re.IGNORECASE)
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
    """A file opts out entirely with a `design-lint: ignore-file` directive near the top."""
    for line in text.splitlines()[:5]:
        if IGNORE_FILE_RE.search(line):
            return True
    return False


def find_sql_violations(text: str, path: str = "<text>") -> List[Finding]:
    """Rules 1-3 of Section 8: no SQL fences, no SQL statements, no vendor tokens."""
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


def lint_paths(paths: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    for p in paths:
        target = Path(p)
        if target.is_dir():
            for md in sorted(target.rglob("*.md")):
                findings += lint_file(md)
        elif target.is_file():
            findings += lint_file(target)
        else:
            print(f"warning: path not found: {p}", file=sys.stderr)
    return findings


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
