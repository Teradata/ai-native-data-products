"""The Platform Layout Standard as data, and a checker and exporter for platform profiles.

Every `implementation/{platform}/PLATFORM_PROFILE.md` declares one `Layout:` block under a
`Layout` heading. The block's fields, types and permitted values are read from the field
table of `design/core/PLATFORM_LAYOUT.md`; nothing about the standard is hard-coded here.

    python tooling/build/platform_layout.py                 # check every platform
    python tooling/build/platform_layout.py teradata        # check one
    python tooling/build/platform_layout.py --json          # export every layout as JSON

The JSON export is the machine-readable platform layout that evaluators load, so the prose
profile and the definition evaluators read cannot drift apart.

Stdlib only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "evals"))

from design_lint import Finding  # noqa: E402
from spec_notation import FieldSpec, field_tables, parse_blocks  # noqa: E402

STANDARD = REPO_ROOT / "design" / "core" / "PLATFORM_LAYOUT.md"
IMPLEMENTATION = REPO_ROOT / "implementation"
BLOCK = "Layout"
HEADING = re.compile(r"^##\s+(?:[\d.]+\s+)?Layout\s*$", re.M)


def load_standard(path: Path = STANDARD) -> Dict[str, FieldSpec]:
    """The `Layout:` field table of the Platform Layout Standard."""
    table = field_tables(path.read_text(encoding="utf-8")).get(BLOCK)
    if not table:
        raise ValueError(f"{path} defines no `{BLOCK}:` field table")
    return table


def platforms() -> List[str]:
    return sorted(p.name for p in IMPLEMENTATION.iterdir() if p.is_dir() and not p.name.startswith("_"))


def profile_path(platform: str) -> Path:
    return IMPLEMENTATION / platform / "PLATFORM_PROFILE.md"


def _terms(value: str) -> List[str]:
    return [t.strip() for t in value.split(",") if t.strip()]


def read_layout(text: str):
    """(blocks, fields) for the profile text: every `Layout:` block found, and the first one's fields."""
    blocks = [b for b in parse_blocks(text, {BLOCK}).blocks if b.kind == BLOCK]
    return blocks, (blocks[0].fields if blocks else {})


def check_text(text: str, path: str, table: Dict[str, FieldSpec]) -> List[Finding]:
    """Everything the Platform Layout Standard requires of one platform profile."""
    findings: List[Finding] = []

    def add(rule: str, message: str, line: int = 1) -> None:
        findings.append(Finding(path, line, rule, message))

    if not HEADING.search(text):
        add("missing-heading", "no '## Layout' heading")
    blocks, fields = read_layout(text)
    if not blocks:
        add("missing-block", "no Layout: block")
        return findings
    for extra in blocks[1:]:
        add("duplicate-block", "Layout: is declared more than once", extra.line)
    block = blocks[0]
    if block.name != "-":
        add("invalid-value", "Layout: blocks are named -", block.line)
    for name, spec in table.items():
        if spec.required and name not in fields:
            add("missing-field", f"Layout: has no '{name}'", block.line)
    for name, value in fields.items():
        at = block.field_lines.get(name, block.line)
        spec = table.get(name)
        if spec is None:
            add("unknown-field", f"Layout: has no field '{name}'", at)
        elif isinstance(value, list) or not value:
            add("invalid-value", f"Layout: '{name}' expects a single-line value", at)
        elif spec.type == "enum" and value not in (spec.values or []):
            add("invalid-value", f"Layout: '{name}': '{value}' is not one of {spec.values}", at)
        elif spec.type == "terms" and not _terms(value):
            add("invalid-value", f"Layout: '{name}' is empty", at)
    return findings


def check_platform(platform: str, table: Dict[str, FieldSpec] = None) -> List[Finding]:
    path = profile_path(platform)
    if not path.is_file():
        return [Finding(str(path), 1, "missing-profile", f"{platform} has no PLATFORM_PROFILE.md")]
    return check_text(path.read_text(encoding="utf-8"), str(path), table or load_standard())


def export_layout(platform: str, table: Dict[str, FieldSpec] = None) -> dict:
    """The platform's layout as plain data: terms fields become lists."""
    table = table or load_standard()
    _, fields = read_layout(profile_path(platform).read_text(encoding="utf-8"))
    out = {"platform": platform}
    for name, value in fields.items():
        spec = table.get(name)
        out[name] = _terms(value) if spec and spec.type == "terms" else value
    return out


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    wanted = [a for a in argv if not a.startswith("--")] or platforms()
    unknown = sorted(set(wanted) - set(platforms()))
    if unknown:
        print(f"platform-layout: no such platform: {', '.join(unknown)}", file=sys.stderr)
        return 2
    table = load_standard()
    findings: List[Finding] = []
    for platform in wanted:
        findings += check_platform(platform, table)
    if findings:
        for f in findings:
            print(str(f))
        print(f"\nplatform-layout: {len(findings)} violation(s)", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps([export_layout(p, table) for p in wanted], indent=2))
    else:
        print(f"platform-layout: clean ({', '.join(wanted)})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
