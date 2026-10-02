"""The Organisation Profile Standard as data, and a parser, checker and deriver for a profile.

An organisation profile configures the standards for one organisation on one platform:
placement, naming, principals, classification, retention, environments and adoption. Its
rules live in notation blocks, read by the same parser as a design specification
(`tooling/evals/spec_notation.py`), and everything a profile may contain is read from the
tables of `design/core/ORGANISATION_PROFILE.md`. Nothing about the standard is hard-coded.

Stdlib only.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "evals"))

from design_lint import Finding, parse_frontmatter  # noqa: E402
from spec_notation import (  # noqa: E402
    BACKTICK,
    Block,
    FieldSpec,
    Standard,
    field_tables,
    load_standard,
    parse_blocks,
    table_rows,
)

TIERS = ("ROLE_READ", "ROLE_AGENT", "ROLE_ADMIN")
PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
EXAMPLE = re.compile(
    r"^-\s+(\w+)\s+([a-z-]+)\s+([A-Z]\w*)(?:\s+([A-Z][a-z]+))?\s*->\s*(\S+)\.(\S+)$")
PATH_EXAMPLE = re.compile(
    r"^-\s+(\w+)\s+([a-z-]+)\s+([A-Z]\w*)(?:\s+([A-Z][a-z]+))?\s*->\s*(\S+)$")
PRINCIPAL = re.compile(r"^(create|existing)\s+(\S.*)$")
PROTECTION = re.compile(r"^(none|(mask|exclude) for (.+))$")


# --------------------------------------------------------------------------- #
# The standard
# --------------------------------------------------------------------------- #

@dataclass
class ProfileStandard:
    frontmatter: Dict[str, FieldSpec] = field(default_factory=dict)
    blocks: Dict[str, Dict[str, FieldSpec]] = field(default_factory=dict)
    headings: Dict[str, Tuple[bool, List[str]]] = field(default_factory=dict)
    variables: Set[str] = field(default_factory=set)
    filters: Set[str] = field(default_factory=set)
    roles: Dict[str, bool] = field(default_factory=dict)
    markers: List[str] = field(default_factory=list)
    platforms: Set[str] = field(default_factory=set)
    spec: Optional[Standard] = None  # the Design Specification Standard, for shared types


def load_profile_standard(design_root: Path) -> ProfileStandard:
    text = (design_root / "core" / "ORGANISATION_PROFILE.md").read_text(encoding="utf-8")
    pstd = ProfileStandard()
    tables = field_tables(text)
    pstd.frontmatter = tables.pop("Frontmatter", {})
    pstd.blocks = tables
    header = ""
    for heading, cells in table_rows(text):
        if not cells[0].startswith("`"):
            header = cells[0]
            continue
        key = BACKTICK.findall(cells[0])[0]
        if heading == "Document structure" and len(cells) >= 3:
            pstd.headings[key] = (cells[1] == "yes", BACKTICK.findall(cells[2]))
        elif heading == "Templates" and header == "Variable":
            pstd.variables.add(key)
        elif heading == "Templates" and header == "Filter":
            pstd.filters.add(key)
        elif heading == "Object roles" and len(cells) >= 2:
            pstd.roles[key] = cells[1] == "yes"
    m = re.search(r"sensitivity marker \(([^)]*)\)", text)
    pstd.markers = BACKTICK.findall(m.group(1)) if m else []
    impl = design_root.parent / "implementation"
    pstd.platforms = {p.name for p in impl.iterdir() if p.is_dir()} if impl.is_dir() else set()
    pstd.spec = load_standard(design_root)
    return pstd


# --------------------------------------------------------------------------- #
# A profile
# --------------------------------------------------------------------------- #

@dataclass
class Profile:
    frontmatter: dict
    headings: List[str]
    blocks: Dict[str, Block]
    duplicates: List[Block]
    path: str

    def field(self, block: str, name: str, default=None):
        b = self.blocks.get(block)
        return b.fields.get(name, default) if b else default

    def mapping(self, block: str, name: str) -> Dict[str, str]:
        """An indented `key: value` field as a dict."""
        out = {}
        for line in self.field(block, name, []) or []:
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
        return out

    def containers(self) -> Dict[str, str]:
        b = self.blocks.get("Containers")
        return {k: v for k, v in b.fields.items()} if b else {}


def parse_profile(text: str, pstd: ProfileStandard, path: str = "<profile>") -> Profile:
    fm, _ = parse_frontmatter(text)
    parsed = parse_blocks(text, set(pstd.blocks))
    blocks, duplicates = {}, []
    for b in parsed.blocks:
        if b.kind in blocks:
            duplicates.append(b)
        else:
            blocks[b.kind] = b
    headings = [m.group(1).strip() for m in re.finditer(r"^##\s+(.+)$", text, re.M)]
    return Profile(fm or {}, headings, blocks, duplicates, path)


# --------------------------------------------------------------------------- #
# Templates and derivation
# --------------------------------------------------------------------------- #

def _snake(s: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s).lower()


def _pascal(s: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[_\s]+", s) if part)


FILTERS = {"lower": str.lower, "upper": str.upper, "snake": _snake, "pascal": _pascal}


def template_errors(template: str, pstd: ProfileStandard) -> List[str]:
    if template.count("{") != template.count("}"):
        return [f"'{template}' has unbalanced braces"]
    errors = []
    for body in PLACEHOLDER.findall(template):
        name, *filters = [x.strip() for x in body.split("|")]
        if name not in pstd.variables:
            errors.append(f"'{{{name}}}' is not a template variable")
        errors += [f"'{f}' is not a template filter" for f in filters if f not in pstd.filters]
    return errors


def render(template: str, variables: Dict[str, str]) -> str:
    """Fill a template. `variables["_abbrev"]`, when present, backs the `abbrev` filter."""
    def one(m):
        name, *filters = [x.strip() for x in m.group(1).split("|")]
        value = str(variables[name])
        for f in filters:
            if f == "abbrev":
                value = variables.get("_abbrev", {})[value]
            else:
                value = FILTERS[f](value)
        return value
    return PLACEHOLDER.sub(one, template)


def container_parts(profile: Profile) -> Dict[str, Tuple[str, Optional[str]]]:
    """Each container key's template and parent key (`<template> in <parent>`)."""
    out = {}
    for key, value in profile.containers().items():
        m = re.match(r"^(.*?)\s+in\s+(\w+)$", value)
        out[key] = (m.group(1), m.group(2)) if m else (value, None)
    return out


def container_key(profile: Profile, role: str, module: str, relation: str = None,
                  classification: str = None) -> str:
    """The container key: a relation's own rule, then the role narrowed by class, then the role."""
    rules = profile.mapping("Placement", "Rules")
    candidates = ([relation] if relation else []) + (
        [f"{role} {classification}"] if classification else []) + [role]
    key = next((rules[c] for c in candidates if c in rules), None)
    return module if key == "module" else key


def container_name(profile: Profile, key: str, variables: Dict[str, str],
                   environment: str = None) -> str:
    adopted = profile.mapping("Adoption", "Containers")
    if key in adopted:
        return adopted[key]  # it exists already, under that name, in every environment
    # In a container template, {module} is the container's own key.
    name = render(container_parts(profile)[key][0], dict(variables, module=key))
    template = profile.field("Environments", "Container template")
    if environment and profile.field("Environments", "Isolation") == "container" and template:
        name = render(template, {"container": name, "environment": environment})
    return name


def object_name(profile: Profile, role: str, entity: str, kind: str = None,
                variables: Dict[str, str] = None, standard: bool = False) -> str:
    """An object's physical name. A standard-owned relation takes its mapped name first."""
    if standard and role in ("table", "base_view"):
        mapped = profile.mapping("Naming", "Standard names").get(entity)
        if mapped:
            return mapped
    objects = profile.mapping("Naming", "Objects")
    module = (variables or {}).get("module")
    candidates = [f"{role} {module} {kind}", f"{role} {module}", f"{role} {kind}", role]
    template = next((objects[c] for c in candidates if c in objects), None)
    if template is None:
        raise KeyError(f"naming template for '{role}'")
    return render(template, dict(variables or {}, entity=entity))


def derive(profile: Profile, role: str, module: str, entity: str, kind: str = None,
           variables: Dict[str, str] = None, environment: str = None,
           standard: bool = False, classification: str = None) -> Tuple[str, str]:
    """`(container, object)` for an object: the profile's derivation function."""
    variables = dict(variables or {}, module=module,
                     _abbrev=profile.mapping("Naming", "Abbreviations"))
    key = container_key(profile, role, module, entity if standard else None, classification)
    container = container_name(profile, key, variables, environment)
    return container, object_name(profile, role, entity, kind, variables, standard)


def has_storage(profile: Profile) -> bool:
    return "Storage" in profile.blocks


def derive_path(profile: Profile, role: str, module: str, entity: str, kind: str = None,
                variables: Dict[str, str] = None, environment: str = None,
                standard: bool = False, classification: str = None) -> Optional[str]:
    """The object-store path for an object, or None when it is not held in object storage."""
    if not has_storage(profile):
        return None
    excluded = [x.strip() for x in (profile.field("Storage", "Excluded") or "").split(",") if x.strip()]
    if role in excluded or entity in excluded:
        return None
    rules = profile.mapping("Paths", "Bucket rules")
    candidates = ([f"{role} {classification}"] if classification else []) + [role]
    bucket_key = next((rules[c] for c in candidates if c in rules), None)
    if bucket_key is None:
        if profile.field("Storage", "Scope") == "declared":
            return None
        raise KeyError(f"bucket rule for '{role}'")
    container, obj = derive(profile, role, module, entity, kind, variables, environment,
                            standard, classification)
    full = dict(variables or {}, module=module, container=container, object=obj,
                environment=environment or "", _abbrev=profile.mapping("Naming", "Abbreviations"))
    full["bucket"] = render(profile.mapping("Paths", "Buckets")[bucket_key], full)
    return render(profile.field("Paths", "Path"), full)


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #

def _field_value_errors(value, spec: FieldSpec, pstd: ProfileStandard) -> List[str]:
    t = spec.type
    multi = t in ("templates", "mappings", "examples", "path-examples")
    if multi != isinstance(value, list):
        return ["expects indented lines" if multi else "expects a single-line value"]
    if not value:
        return ["is empty"]
    if t in ("text", "terms"):
        return []
    if t == "integer":
        return [] if re.fullmatch(r"\d+", value) else [f"'{value}' is not an integer"]
    if t == "enum":
        return [] if value in (spec.values or []) else [f"'{value}' is not one of {spec.values}"]
    if t == "duration":
        units = "|".join(sorted(u.rstrip("s") for u in pstd.spec.duration_units))
        return [] if re.fullmatch(rf"\d+\s+(?:{units})s?", value) else [f"'{value}' is not a duration"]
    if t == "template":
        return template_errors(value, pstd)
    if t == "principal":
        m = PRINCIPAL.match(value)
        if not m:
            return [f"'{value}' is not 'create <template>' or 'existing <name>'"]
        return template_errors(m.group(2), pstd) if m.group(1) == "create" else []
    errors = []
    for line in value:
        if t == "examples":
            if not EXAMPLE.match(line):
                errors.append(f"'{line}' is not '- <role> <module> <Entity> [<Kind>] -> <container>.<object>'")
        elif t == "path-examples":
            if not PATH_EXAMPLE.match(line):
                errors.append(f"'{line}' is not '- <role> <module> <Entity> [<Kind>] -> <path>'")
        elif ":" not in line:
            errors.append(f"'{line}' is not '<key>: <value>'")
        elif t == "templates":
            errors += template_errors(line.split(":", 1)[1].strip(), pstd)
    return errors


def check_profile(profile: Profile, pstd: ProfileStandard) -> List[Finding]:
    """Everything the Organisation Profile Standard requires of a profile, short of a product."""
    path, findings = profile.path, []

    def add(rule, message, line=1):
        findings.append(Finding(path, line, rule, message))

    fm = profile.frontmatter
    for name, spec in pstd.frontmatter.items():
        if spec.required and not fm.get(name):
            add("profile-frontmatter", f"missing required key '{name}'")
    for name in sorted(set(fm) - set(pstd.frontmatter)):
        add("profile-frontmatter", f"unknown key '{name}'")
    if fm.get("platform") and fm["platform"] not in pstd.platforms:
        add("profile-frontmatter", f"platform '{fm['platform']}' has no directory under implementation/")

    storage = [h for h in pstd.headings if h.startswith("Storage Section")]
    present_storage = [h for h in storage if h in profile.headings]
    if present_storage and len(present_storage) != len(storage):
        add("missing-heading", "the Storage Section headings are present together or not at all; "
                               f"missing {sorted(set(storage) - set(present_storage))}")
    for heading, (required, blocks) in pstd.headings.items():
        present = heading in profile.headings
        if required and not present:
            add("missing-heading", f"no '## {heading}' heading")
        if required or present:
            for kind in blocks:
                if kind not in profile.blocks:
                    add("missing-block", f"'{heading}' has no {kind}: block")
    for b in profile.duplicates:
        add("duplicate-block", f"{b.kind}: is declared more than once", b.line)

    for kind, b in profile.blocks.items():
        table, where = pstd.blocks[kind], f"{kind}:"
        if b.name != "-":
            add("invalid-value", f"{where} blocks are named -", b.line)
        wildcard = table.get("*")
        for name, spec in table.items():
            if name != "*" and spec.required and name not in b.fields:
                add("missing-field", f"{where} has no '{name}'", b.line)
        for name, value in b.fields.items():
            spec = table.get(name) or wildcard
            at = b.field_lines.get(name, b.line)
            if spec is None:
                add("unknown-field", f"{where} has no field '{name}'", at)
                continue
            for err in _field_value_errors(value, spec, pstd):
                add("invalid-value", f"{where} '{name}': {err}", at)

    if findings:
        return findings  # the remaining checks assume well-formed blocks
    return findings + _check_rules(profile, pstd)


def _check_rules(profile: Profile, pstd: ProfileStandard) -> List[Finding]:
    path, findings = profile.path, []

    def add(rule, message, block):
        b = profile.blocks.get(block)
        findings.append(Finding(path, b.line if b else 1, rule, message))

    containers = profile.containers()
    objects = profile.mapping("Naming", "Objects")
    rules = profile.mapping("Placement", "Rules")
    relations = {name for entities in pstd.spec.module_entities.values() for name in entities}
    relations |= {x for imp in pstd.spec.implicit_relations.values()
                  for x in imp.tables + imp.views + imp.tall}

    modules = set(pstd.spec.module_entities)
    for key in objects:
        role, *qualifiers = key.split()
        if role not in pstd.roles:
            add("invalid-value", f"Naming: '{role}' is not an object role", "Naming")
        for q in qualifiers:
            if q not in modules and not re.fullmatch(r"[A-Z][a-z]+", q):
                add("invalid-value", f"Naming: '{q}' in '{key}' is neither a module nor an "
                                     f"entity kind", "Naming")
    for role, required in pstd.roles.items():
        if required and role not in objects:
            add("missing-field", f"Naming: no template for required role '{role}'", "Naming")
        if required and role not in rules:
            add("missing-field", f"Placement: no rule for required role '{role}'", "Placement")
    scheme_classes = [s.strip() for s in profile.field("Classification", "Scheme", "").split(",")]
    parts = container_parts(profile)
    parents = {p for _, p in parts.values() if p}
    for key, (_, parent) in parts.items():
        if parent and parent not in containers:
            add("invalid-value", f"Containers: '{key}' names parent '{parent}', which is not a "
                                 f"container", "Containers")
        seen, cur = {key}, parent
        while cur and cur in parts:
            if cur in seen:
                add("invalid-value", f"Containers: parents of '{key}' form a cycle", "Containers")
                break
            seen.add(cur)
            cur = parts[cur][1]
    for key, target in rules.items():
        role, *cls = key.split(" ", 1)
        if cls and role in pstd.roles:
            if cls[0] not in scheme_classes:
                add("invalid-value", f"Placement: '{key}' narrows by '{cls[0]}', which is not a "
                                     f"class in the scheme", "Placement")
        elif key not in pstd.roles and key not in relations:
            add("invalid-value", f"Placement: '{key}' is neither an object role nor a "
                                 f"standard-owned relation", "Placement")
        if target != "module" and target not in containers:
            add("invalid-value", f"Placement: '{key}' routes to '{target}', which is not a "
                                 f"container", "Placement")
        if target in parents:
            add("invalid-value", f"Placement: '{key}' routes to parent container '{target}', "
                                 f"which holds no objects", "Placement")
    abbreviations = profile.mapping("Naming", "Abbreviations")
    uses_abbrev = any("abbrev" in v for v in list(containers.values())
                      + list(profile.mapping("Naming", "Objects").values()))
    if uses_abbrev:
        for module in pstd.spec.module_entities:
            if module not in abbreviations:
                add("missing-field", f"Naming: the abbrev filter is used but module '{module}' "
                                     f"has no abbreviation", "Naming")
    for role in profile.mapping("Catalogue", "Layers"):
        if role not in pstd.roles:
            add("invalid-value", f"Catalogue: '{role}' is not an object role", "Catalogue")
    for key in profile.mapping("Adoption", "Column aliases"):
        if not re.fullmatch(r"[A-Za-z]\w*\.[A-Z]\w*\.[a-z_]\w*", key):
            add("invalid-value", f"Adoption: column alias '{key}' is not "
                                 f"'<product_code>.<Entity>.<attribute>'", "Adoption")

    standard = profile.mapping("Naming", "Standard names")
    known = pstd.spec.canonical_attributes | relations
    for logical, physical in standard.items():
        if logical not in known:
            add("invalid-value", f"Naming: '{logical}' is not a standard-owned name", "Naming")
    if len(set(standard.values())) != len(standard):
        add("invalid-value", "Naming: standard names must map one-to-one", "Naming")
    for logical, physical in standard.items():
        if physical in known and physical != logical:
            add("invalid-value", f"Naming: '{logical}' maps onto '{physical}', which another "
                                 f"standard-owned name already holds", "Naming")

    scheme = [s.strip() for s in profile.field("Classification", "Scheme", "").split(",")]
    if profile.field("Classification", "Default") not in scheme:
        add("invalid-value", "Classification: Default is not in the scheme", "Classification")
    markers = profile.mapping("Classification", "Markers")
    for marker in pstd.markers:
        if marker not in markers:
            add("missing-field", f"Classification: no class for marker '{marker}'", "Classification")
    for marker, cls in markers.items():
        if cls not in scheme:
            add("invalid-value", f"Classification: '{cls}' is not in the scheme", "Classification")
    for cls, rule in profile.mapping("Classification", "Protection").items():
        m = PROTECTION.match(rule)
        bad_tiers = [t for t in re.split(r",\s*", m.group(3))] if m and m.group(3) else []
        if cls not in scheme or not m or any(t not in TIERS for t in bad_tiers):
            add("invalid-value", f"Classification: protection '{cls}: {rule}' is invalid", "Classification")

    if profile.field("Environments", "Isolation") == "container":
        template = profile.field("Environments", "Container template") or ""
        if "{container" not in template or "{environment" not in template:
            add("missing-field", "Environments: container isolation needs a Container template "
                                 "using {container} and {environment}", "Environments")

    for key in profile.mapping("Adoption", "Containers"):
        if key not in containers:
            add("invalid-value", f"Adoption: '{key}' is not a container key", "Adoption")
    for key, target in profile.mapping("Adoption", "Entities").items():
        if not re.fullmatch(r"[A-Za-z]\w*\.[A-Z]\w*", key) or "." not in target:
            add("invalid-value", f"Adoption: '{key}: {target}' is not "
                                 f"'<product_code>.<Entity>: <container>.<object>'", "Adoption")

    findings += _check_examples(profile, relations)
    if has_storage(profile):
        findings += _check_path_examples(profile, relations)
    return findings


def _check_path_examples(profile: Profile, relations: Set[str]) -> List[Finding]:
    findings, b = [], profile.blocks["Paths"]
    code = profile.field("Derivation", "Product code")
    lines = profile.field("Paths", "Examples", [])
    if len(lines) < 3:
        findings.append(Finding(profile.path, b.line, "missing-field",
                                "Paths: at least three worked examples are required"))
    for line in lines:
        role, module, entity, kind, path = PATH_EXAMPLE.match(line).groups()
        try:
            got = derive_path(profile, role, module, entity, kind,
                              {"product_code": code, "product": code},
                              standard=entity in relations)
        except (KeyError, TypeError, StopIteration) as exc:
            got = f"<cannot derive: {exc}>"
        if got != path:
            findings.append(Finding(profile.path, b.line, "derivation-mismatch",
                                    f"Paths: '{line}' but the profile derives {got}"))
    return findings


def _check_examples(profile: Profile, relations: Set[str]) -> List[Finding]:
    """The worked derivations must be what the profile actually derives."""
    findings, b = [], profile.blocks["Derivation"]
    code = profile.field("Derivation", "Product code")
    lines = profile.field("Derivation", "Examples", [])
    if len(lines) < 3:
        findings.append(Finding(profile.path, b.line, "missing-field",
                                "Derivation: at least three worked examples are required"))
    for line in lines:
        m = EXAMPLE.match(line)
        role, module, entity, kind, container, obj = m.groups()
        try:
            got = derive(profile, role, module, entity, kind,
                         {"product_code": code, "product": code},
                         standard=entity in relations)
        except (KeyError, TypeError, StopIteration) as exc:
            got = (f"<cannot derive: {exc}>", "")
        if got != (container, obj):
            findings.append(Finding(profile.path, b.line, "derivation-mismatch",
                                    f"Derivation: '{line}' but the profile derives "
                                    f"{got[0]}.{got[1]}"))
    return findings


def lint_profile(path: Path, design_root: Path = None) -> List[Finding]:
    pstd = load_profile_standard(design_root or (REPO_ROOT / "design"))
    profile = parse_profile(path.read_text(encoding="utf-8"), pstd, str(path))
    return check_profile(profile, pstd)


def main(argv: List[str]) -> int:
    if not argv:
        print("usage: org_profile.py <organisation-profile.md> [...]", file=sys.stderr)
        return 2
    findings = []
    for arg in argv:
        findings += lint_profile(Path(arg))
    if not findings:
        print(f"profile-lint: clean ({', '.join(argv)})")
        return 0
    for f in findings:
        print(str(f))
    print(f"\nprofile-lint: {len(findings)} violation(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
