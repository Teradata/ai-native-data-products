"""A platform binding's declarations, read from its binding.toml.

The Platform Implementation Authoring Standard §5.1 has every binding declare, as data,
its quoting, the object roles it emits, its settings, its physical type for each logical
type, and its SQL fragment for each expression function. The resolver reads them here and
only substitutes, so platform SQL stays in the binding and tooling holds none. The
standard's field tables are the schema: a `[binding]` key is a field name in snake_case.

Stdlib only (tomllib, Python 3.11 or later).
"""
from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "evals"))

from design_lint import LOGICAL_TYPES, Finding  # noqa: E402
from spec_notation import field_tables  # noqa: E402

DECLARATIONS = "binding.toml"
BLOCKS = ("Binding", "Types", "Functions")
EXTRA_FRAGMENTS = {"duration", "map case", "true", "false", "null", "flag test"}


@dataclass
class Binding:
    platform: str
    identifier_quote: str = '"'
    literal_quote: str = "'"
    principals: str = "native"
    runtime_scope: str = "unsupported"
    emits: Dict[str, List[str]] = field(default_factory=dict)
    settings: Dict[str, Dict[str, str]] = field(default_factory=dict)  # name -> {values, default}
    gaps: Dict[str, str] = field(default_factory=dict)
    types: Dict[str, str] = field(default_factory=dict)
    functions: Dict[str, str] = field(default_factory=dict)
    path: str = ""

    def ident(self, name: str) -> str:
        q = self.identifier_quote
        return q + str(name).replace(q, q + q) + q

    def literal(self, text: str) -> str:
        q = self.literal_quote
        return q + str(text).replace(q, q + q) + q

    def qualified(self, container: str, name: str) -> str:
        return self.ident(container) + "." + self.ident(name)

    def physical_type(self, logical: str) -> Optional[str]:
        """The physical type for a logical type such as `Decimal(10,4)` or `Vector[384]`."""
        m = re.fullmatch(r"(\w+)(?:\{.*\}|\((\d+)\s*,\s*(\d+)\)|\[(\d+)\])?", logical)
        if not m or m.group(1) not in self.types:
            return None
        out = self.types[m.group(1)]
        if m.group(2):
            out = out.replace("{p}", m.group(2)).replace("{s}", m.group(3))
        if m.group(4):
            out = re.sub(r"\{dim\*(\d+)\}", lambda n: str(int(m.group(4)) * int(n.group(1))), out)
            out = out.replace("{dim}", m.group(4))
        return out


def snake(name: str) -> str:
    """A field, block or setting name as a TOML key: `Identifier quote` is `identifier_quote`
    and `StorageAccess` is `storage_access`."""
    return re.sub(r"[^a-z0-9]+", "_", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()).strip("_")


def load_binding(platform: str, repo_root: Path = None) -> (Optional[Binding], List[Finding]):
    """The binding's declarations, and every problem with them."""
    root = repo_root or REPO_ROOT
    path = root / "implementation" / platform / DECLARATIONS
    where = str(path)
    if not path.is_file():
        return None, [Finding(where, 1, "binding-declaration", f"no {DECLARATIONS} for '{platform}'")]
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return None, [Finding(where, 1, "binding-declaration", f"not valid TOML: {exc}")]
    findings: List[Finding] = []

    def fail(message):
        findings.append(Finding(where, 1, "binding-declaration", message))

    for table in ("binding", "types", "functions"):
        if not isinstance(data.get(table), dict):
            fail(f"no [{table}] table")
    if findings:
        return None, findings
    standard = field_tables((root / "design" / "core" / "IMPLEMENTATION_AUTHORING.md").read_text(encoding="utf-8"))
    known = {snake(name): spec for name, spec in standard.get("Binding", {}).items()}
    fields = data["binding"]
    for name, spec in known.items():
        if spec.required and name not in fields:
            fail(f"[binding] has no '{name}'")
    for name in fields:
        if name not in known:
            fail(f"[binding] has no field '{name}'")

    b = Binding(platform, path=where)
    b.identifier_quote = fields.get("identifier_quote", '"')
    b.literal_quote = fields.get("literal_quote", "'")
    b.principals = fields.get("principals", "native")
    b.runtime_scope = fields.get("runtime_scope", "unsupported")
    if b.runtime_scope not in ("enforced", "unsupported"):
        fail(f"[binding] runtime_scope '{b.runtime_scope}' is not enforced or unsupported")
    if b.principals not in ("native", "unsupported"):
        fail(f"[binding] principals '{b.principals}' is not native or unsupported")
    b.emits = {k: list(v) for k, v in fields.get("emits", {}).items()}
    b.settings = {k: dict(v) for k, v in fields.get("settings", {}).items()}
    for name, setting in b.settings.items():
        if set(setting) != {"values", "default"}:
            fail(f"[binding.settings] {name} is not {{ values, default }}")
    try:
        b.gaps = {g["area"]: g["gap"] for g in fields.get("gaps", [])}
    except (KeyError, TypeError):
        return None, findings + [Finding(where, 1, "binding-declaration", "gaps need area and gap")]
    b.types = dict(data["types"])
    b.functions = dict(data["functions"])
    vocabulary = {name for name, _ in _function_names(root)} | EXTRA_FRAGMENTS
    for name in b.types:
        if name not in LOGICAL_TYPES:
            fail(f"[types] '{name}' is not a logical type")
    for name in b.functions:
        if name.split("/")[0] not in vocabulary:
            fail(f"[functions] '{name}' is not in the expression vocabulary")
    return b, findings


def _function_names(root: Path):
    text = (root / "design" / "core" / "DESIGN_SPECIFICATION.md").read_text(encoding="utf-8")
    return re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*(row|aggregate|quality)\s*\|", text, re.M)
