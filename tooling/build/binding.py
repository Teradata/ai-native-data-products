"""A platform binding's declarations, read from its PLATFORM_PROFILE.md.

The Platform Implementation Authoring Standard §5.1 has every binding declare, as data,
its quoting, the object roles it emits, its settings, its physical type for each logical
type, and its SQL fragment for each expression function. The resolver reads them here and
only substitutes, so platform SQL stays in the binding and tooling holds none.

Stdlib only.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "evals"))

from design_lint import LOGICAL_TYPES, Finding  # noqa: E402
from spec_notation import field_tables, parse_blocks  # noqa: E402

BLOCKS = ("Binding", "Types", "Functions")
# entity and relationship run once per item; module once per included module; contract once for the
# Semantic module's metadata contract (INV-SEMANTIC-016 to 020); product once for the whole product.
CHECK_SCOPES = ("entity", "relationship", "module", "contract", "product")
EXTRA_FRAGMENTS = {"duration", "map case", "true", "false", "null", "flag test"}


@dataclass
class Binding:
    platform: str
    identifier_quote: str = '"'
    literal_quote: str = "'"
    principals: str = "native"
    runtime_scope: str = "unsupported"
    emits: Dict[str, List[str]] = field(default_factory=dict)
    settings: Dict[str, str] = field(default_factory=dict)
    phases: Dict[str, str] = field(default_factory=dict)
    checks: Dict[str, str] = field(default_factory=dict)
    gaps: Dict[str, str] = field(default_factory=dict)
    deploy: Optional[str] = None
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


def _mapping(lines) -> Dict[str, str]:
    out = {}
    for line in lines or []:
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def load_binding(platform: str, repo_root: Path = None) -> (Optional[Binding], List[Finding]):
    """The binding's declarations, and every problem with them."""
    root = repo_root or REPO_ROOT
    path = root / "implementation" / platform / "PLATFORM_PROFILE.md"
    findings: List[Finding] = []
    if not path.is_file():
        return None, [Finding(str(path), 1, "binding-declaration", f"no PLATFORM_PROFILE.md for '{platform}'")]
    standard = field_tables((root / "design" / "core" / "IMPLEMENTATION_AUTHORING.md").read_text(encoding="utf-8"))
    vocabulary = {name for name, _ in _function_names(root)} | EXTRA_FRAGMENTS
    spec = parse_blocks(path.read_text(encoding="utf-8"), set(BLOCKS))
    blocks = {b.kind: b for b in spec.blocks}
    for kind in BLOCKS:
        if kind not in blocks:
            findings.append(Finding(str(path), 1, "binding-declaration", f"no {kind}: block"))
    if findings:
        return None, findings
    b = Binding(platform, path=str(path))
    fields = blocks["Binding"].fields
    for name, spec_field in standard.get("Binding", {}).items():
        if spec_field.required and name not in fields:
            findings.append(Finding(str(path), blocks["Binding"].line, "binding-declaration",
                                    f"Binding: has no '{name}'"))
    for name in fields:
        if name not in standard.get("Binding", {}):
            findings.append(Finding(str(path), blocks["Binding"].line, "binding-declaration",
                                    f"Binding: has no field '{name}'"))
    b.identifier_quote = fields.get("Identifier quote", '"')
    b.literal_quote = fields.get("Literal quote", "'")
    b.principals = fields.get("Principals", "native")
    b.runtime_scope = fields.get("Runtime scope", "unsupported")
    if b.runtime_scope not in ("enforced", "unsupported"):
        findings.append(Finding(str(path), blocks["Binding"].line, "binding-declaration",
                                f"Binding: Runtime scope '{b.runtime_scope}' is not enforced or unsupported"))
    if b.principals not in ("native", "unsupported"):
        findings.append(Finding(str(path), blocks["Binding"].line, "binding-declaration",
                                f"Binding: Principals '{b.principals}' is not native or unsupported"))
    b.emits = {k: [x.strip() for x in v.split(",") if x.strip()]
               for k, v in _mapping(fields.get("Emits")).items()}
    b.settings = _mapping(fields.get("Settings"))
    b.phases = _mapping(fields.get("Phases"))
    b.checks = _mapping(fields.get("Checks"))
    b.gaps = _mapping(fields.get("Gaps"))
    b.deploy = fields.get("Deploy")
    for key in b.checks:
        scope = key.split(" ")[0]
        if scope not in CHECK_SCOPES or len(key.split(" ")) != 2:
            findings.append(Finding(str(path), blocks["Binding"].line, "binding-declaration",
                                    f"Binding: check '{key}' is not '<{'|'.join(CHECK_SCOPES)}> <check>'"))
    templates = root / "implementation" / platform
    for name in list(b.phases.values()) + list(b.checks.values()) + ([b.deploy] if b.deploy else []):
        if not (templates / name).is_file():
            findings.append(Finding(str(path), blocks["Binding"].line, "binding-declaration",
                                    f"Binding: template '{name}' does not exist"))
    b.types = dict(blocks["Types"].fields)
    b.functions = dict(blocks["Functions"].fields)
    for name in b.types:
        if name not in LOGICAL_TYPES:
            findings.append(Finding(str(path), blocks["Types"].line, "binding-declaration",
                                    f"Types: '{name}' is not a logical type"))
    for name in b.functions:
        if name.split("/")[0] not in vocabulary:
            findings.append(Finding(str(path), blocks["Functions"].line, "binding-declaration",
                                    f"Functions: '{name}' is not in the expression vocabulary"))
    return b, findings


def _function_names(root: Path):
    text = (root / "design" / "core" / "DESIGN_SPECIFICATION.md").read_text(encoding="utf-8")
    return re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*(row|aggregate|quality)\s*\|", text, re.M)
