"""The Design Specification Standard, read as data, and a parser for a specification.

`spec_lint` checks a design specification; the build-context tooling will read one. Both
need the same two things, so they live here:

  * `Standard`: what a specification may contain, read from
    `design/core/DESIGN_SPECIFICATION.md` (field tables, types, enumerations, module
    requirements, the expression vocabulary) and from the temporal pattern (profiles,
    kind defaults, canonical and prohibited names). Nothing about the standard is
    hard-coded here: change a table there and the parser follows.
  * `parse_specification`: the specification's entities and blocks as plain data.

Stdlib only, like the linters beside it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

BACKTICK = re.compile(r"`([^`]+)`")
ENUM_LEAD = re.compile(r"^`[^`]+`(?:(?:, | or )`[^`]+`)*")
HEADING = re.compile(r"^(#{2,4})\s+(?:[\d.]+\s+)?(.*?)\s*$")
FIELD_ROW = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*(yes|no)\s*\|\s*([a-z]+)\s*\|\s*(.*?)\s*\|\s*$")
TWO_COL_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$")
FUNCTION_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*(row|aggregate|quality)\s*\|")
FENCE = re.compile(r"^\s*(```|~~~)")
BLOCK_START = re.compile(r"^([A-Z][A-Za-z]*):\s*(.*?)\s*$")
HEADER_QUALIFIER = re.compile(r"\[(\w+):\s*([^\]]+)\]")
ATTRIBUTE = re.compile(r"^\s{2,}([a-z_][A-Za-z0-9_]*)\s*:\s*(\S.*)$")
LOGICAL_TYPE = re.compile(
    r"^(Enum\{[^}]*\}|Decimal\(\s*\d+\s*,\s*\d+\s*\)|Vector\[\d+\]|[A-Z][A-Za-z]*)")
ENTITY_SECTION = re.compile(r"^\s{2}([A-Z][A-Za-z ]*?):\s*(.*?)\s*$")
SUB_FIELD = re.compile(r"^\s{4,}([a-z][a-z ]*?):\s*(.+?)\s*$")
BLOCK_FIELD = re.compile(r"^\s{2}(\S[^:]*?):\s*(.*?)\s*$")
LIST_LINE = re.compile(r"^\s{4,}(.+?)\s*$")


# --------------------------------------------------------------------------- #
# The standard
# --------------------------------------------------------------------------- #

@dataclass
class FieldSpec:
    name: str
    required: bool
    type: str
    values: Optional[List[str]]  # the enumeration, for type `enum`


@dataclass
class Standard:
    types: Set[str] = field(default_factory=set)
    frontmatter: Dict[str, FieldSpec] = field(default_factory=dict)
    header_qualifiers: Dict[str, FieldSpec] = field(default_factory=dict)
    section_kinds: Dict[str, List[str]] = field(default_factory=dict)
    sections: Dict[str, Dict[str, FieldSpec]] = field(default_factory=dict)
    blocks: Dict[str, Dict[str, FieldSpec]] = field(default_factory=dict)
    module_blocks: Dict[str, List[str]] = field(default_factory=dict)
    facet_blocks: Dict[str, List[str]] = field(default_factory=dict)
    functions: Dict[str, str] = field(default_factory=dict)
    refresh_terms: Set[str] = field(default_factory=set)
    duration_units: Set[str] = field(default_factory=set)
    growth_units: Set[str] = field(default_factory=set)
    weight_dimensions: Set[str] = field(default_factory=set)
    platforms: Set[str] = field(default_factory=set)
    profiles: Set[str] = field(default_factory=set)
    kind_defaults: Dict[str, Set[str]] = field(default_factory=dict)
    canonical_attributes: Set[str] = field(default_factory=set)
    conditional_prohibited: Dict[str, str] = field(default_factory=dict)  # name -> profile
    module_entities: Dict[str, Dict[str, Set[str]]] = field(default_factory=dict)
    patterns: Set[str] = field(default_factory=set)
    unnamed_blocks: Set[str] = field(default_factory=set)
    implicit_relations: Dict[str, Tuple[str, List[str]]] = field(default_factory=dict)
    entity_facets: Dict[Tuple[str, str], str] = field(default_factory=dict)


def _enum(cell: str) -> Optional[List[str]]:
    m = ENUM_LEAD.match(cell)
    return BACKTICK.findall(m.group(0)) if m else None


def _heading_key(text: str) -> str:
    """`Embedding:` for a block heading, otherwise the heading text itself."""
    ticks = BACKTICK.findall(text)
    return ticks[0].rstrip(":") if ticks else text


def table_rows(text: str) -> List[Tuple[str, List[str]]]:
    """Every table row in a standards document, with the heading key it sits under.

    Header and separator rows are skipped. Shared by every reader of a standard's tables.
    """
    rows, heading = [], ""
    for line in text.splitlines():
        h = HEADING.match(line)
        if h:
            heading = _heading_key(h.group(2))
            continue
        row = line.strip()
        if not row.startswith("|") or re.fullmatch(r"\|[\s|:-]*", row):
            continue
        rows.append((heading, [c.strip() for c in row.strip("|").split("|")]))
    return rows


def field_tables(text: str) -> Dict[str, Dict[str, FieldSpec]]:
    """`| `Field` | yes/no | type | value |` tables, keyed by heading."""
    tables: Dict[str, Dict[str, FieldSpec]] = {}
    heading = ""
    for line in text.splitlines():
        h = HEADING.match(line)
        if h:
            heading = _heading_key(h.group(2))
            continue
        fm = FIELD_ROW.match(line.strip())
        if fm:
            name, req, ftype, cell = fm.groups()
            tables.setdefault(heading, {})[name] = FieldSpec(
                name, req == "yes", ftype, _enum(cell) if ftype == "enum" else None)
    return tables


def entity_module(entity: "Entity", std: "Standard") -> str:
    """The module an entity belongs to: declared, else the module whose standard defines
    an entity of that name, else `domain` (Design Specification Standard §3.2)."""
    declared = entity.header.get("module")
    if declared:
        return declared
    for module, entities in sorted(std.module_entities.items()):
        if entity.name in entities:
            return module
    return "domain"


def load_standard(design_root: Path) -> Standard:
    std = Standard()
    text = (design_root / "core" / "DESIGN_SPECIFICATION.md").read_text(encoding="utf-8")
    heading = ""
    for line in text.splitlines():
        h = HEADING.match(line)
        if h:
            heading = _heading_key(h.group(2))
            continue
        row = line.strip()
        if row.startswith("Named `-`"):
            std.unnamed_blocks.add(heading)
            continue
        fm = FIELD_ROW.match(row)
        if fm:
            name, req, ftype, cell = fm.groups()
            spec = FieldSpec(name, req == "yes", ftype, _enum(cell) if ftype == "enum" else None)
            if heading == "Frontmatter":
                std.frontmatter[name] = spec
            elif heading == "Entity header qualifiers":
                std.header_qualifiers[name] = spec
            elif heading in ("Volume", "Features"):
                std.sections.setdefault(heading, {})[name] = spec
            else:
                std.blocks.setdefault(heading, {})[name] = spec
            continue
        fn = FUNCTION_ROW.match(row)
        if fn:
            std.functions[fn.group(1)] = fn.group(2)
            continue
        two = TWO_COL_ROW.match(row)
        if two:
            key, cell = two.groups()
            if heading == "Field types":
                std.types.add(key)
                if key == "refresh":
                    std.refresh_terms = set(BACKTICK.findall(cell))
                elif key == "duration":
                    std.duration_units = set(BACKTICK.findall(cell))
                elif key == "growth":
                    std.growth_units = set(BACKTICK.findall(cell))
            elif heading == "Module requirements":
                std.module_blocks[key] = BACKTICK.findall(cell)
            elif heading == "Standard-owned relations":
                ticks = BACKTICK.findall(cell)
                std.implicit_relations[key] = (ticks[0] if ticks else "none",
                                               [x for x in ticks[1:] if re.fullmatch(r"[A-Z]\w+", x)])
            elif heading == "Entity sections":
                std.section_kinds[key] = (["feature-group"] if "feature group" in cell
                                          else BACKTICK.findall(cell))

    for facet, block in re.findall(r"with the `([a-z]+:[a-z-]+)` facet also requires a `(\w+)` block",
                                   text):
        std.facet_blocks.setdefault(facet, []).append(block)
    m = re.search(r"Weight dimensions are (.+?)\.", text)
    if m:
        std.weight_dimensions = set(BACKTICK.findall(m.group(1)))
    m = re.search(r"or one of (.+?);", text)
    if m:
        std.platforms = {p.strip() for p in re.split(r",\s*|\s+or\s+", m.group(1)) if p.strip()}
    impl = design_root.parent / "implementation"
    if impl.is_dir():
        std.platforms |= {p.name for p in impl.iterdir() if p.is_dir()}

    _load_temporal(std, design_root / "patterns" / "temporal-lifecycle-metadata.md")
    std.patterns = {p.stem for p in (design_root / "patterns").glob("*.md")}
    for p in sorted((design_root / "modules").glob("*.md")):
        module_text = p.read_text(encoding="utf-8")
        spec = parse_specification(module_text, std=None)
        std.module_entities[p.stem] = {e.name: set(e.attributes) for e in spec.entities}
        # Entities under an `Entity Model: <X> Facet` heading belong to that facet.
        facet, lines = None, module_text.split("\n")
        starts = {e.line: e.name for e in spec.entities}
        for number, line in enumerate(lines, start=1):
            h = re.match(r"^##\s+(?:[\d.]+\s+)?(.*)$", line)
            if h:
                f = re.search(r"(\w+) Facet", h.group(1))
                facet = f.group(1).lower() if f else None
            if number in starts and facet:
                std.entity_facets[(p.stem, starts[number])] = facet
    return std


def _load_temporal(std: Standard, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    heading = ""
    for line in text.splitlines():
        h = HEADING.match(line)
        if h:
            heading = h.group(2)
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if heading.startswith("Canonical columns"):
            for name in BACKTICK.findall(cells[0]):
                if "<" not in name:
                    std.canonical_attributes.add(name)
        elif heading.startswith("Prohibited generic names") and len(cells) >= 3:
            scope = cells[2]
            if "except on" in scope:
                profile = BACKTICK.findall(scope)
                for name in BACKTICK.findall(cells[0]):
                    std.conditional_prohibited[name] = profile[0] if profile else ""
        elif heading.startswith("Table Metadata Profiles"):
            uppercase = [t for t in BACKTICK.findall(cells[1]) if re.fullmatch(r"[A-Z][A-Z0-9_]+", t)]
            kind = BACKTICK.findall(cells[0])
            if kind and re.fullmatch(r"[A-Z][a-z]+", kind[0]):
                std.kind_defaults[kind[0]] = set(uppercase)
            else:
                std.profiles.update(uppercase)


# --------------------------------------------------------------------------- #
# A specification
# --------------------------------------------------------------------------- #

@dataclass
class Attribute:
    name: str
    type: str
    qualifiers: Dict[str, str]  # flag qualifiers map to ""
    line: int


@dataclass
class Entity:
    name: str
    kind: str
    header: Dict[str, str]
    attributes: Dict[str, Attribute]
    sections: Dict[str, object]  # "Volume" -> {field: value}; "Synonyms" -> str; others -> list
    line: int


@dataclass
class Block:
    kind: str
    name: str
    fields: Dict[str, object]  # str, or a list of lines for weights/rules/flows
    field_lines: Dict[str, int]
    line: int


@dataclass
class Specification:
    entities: List[Entity] = field(default_factory=list)
    blocks: List[Block] = field(default_factory=list)

    def entity(self, name: str) -> Optional[Entity]:
        return next((e for e in self.entities if e.name == name), None)

    def blocks_of(self, kind: str) -> List[Block]:
        return [b for b in self.blocks if b.kind == kind]


def split_qualifiers(rest: str) -> Tuple[List[str], str]:
    """Bracketed qualifiers in order, and the trailing `//` comment.

    A qualifier may hold an expression with its own brackets, braces and quoted text,
    so this scans rather than matching a pattern.
    """
    quals, i, n = [], 0, len(rest)
    while i < n:
        if rest.startswith("//", i):
            return quals, rest[i + 2:].strip()
        if rest[i] == "[":
            depth, j, quote = 0, i, False
            while j < n:
                c = rest[j]
                if c == "'":
                    quote = not quote
                elif not quote and c in "[({":
                    depth += 1
                elif not quote and c in "])}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            quals.append(rest[i + 1:j].strip())
            i = j + 1
            continue
        i += 1
    return quals, ""


def _parse_attribute(line: str, lineno: int) -> Optional[Attribute]:
    m = ATTRIBUTE.match(line)
    if not m:
        return None
    name, rest = m.groups()
    t = LOGICAL_TYPE.match(rest)
    if not t:
        return None
    quals, _ = split_qualifiers(rest[t.end():])
    parsed = {}
    for q in quals:
        if q.startswith("->"):
            parsed["->"] = q[2:].strip()
        elif ":" in q:
            key, value = q.split(":", 1)
            parsed[key.strip()] = value.strip()
        else:
            parsed[q] = ""
    return Attribute(name, t.group(1), parsed, lineno)


def parse_specification(text: str, std: Optional[Standard]) -> Specification:
    """Entities and blocks from every fenced block in `text`.

    With `std` absent only `Entity:` blocks are read: that is how a module standard's own
    entities are loaded before the standard itself is complete.
    """
    return parse_blocks(text, set(std.blocks) if std else set())


def parse_blocks(text: str, known: Set[str]) -> Specification:
    """`Entity:` blocks and blocks of the `known` kinds, from every fenced block in `text`.

    A design specification and an organisation profile share this notation.
    """
    spec, lines = Specification(), text.split("\n")
    infence, current = False, None
    for idx, line in enumerate(lines, start=1):
        if FENCE.match(line):
            infence, current = not infence, None
            continue
        if not infence:
            continue
        start = BLOCK_START.match(line)
        if start and (start.group(1) == "Entity" or start.group(1) in known):
            kind, rest = start.groups()
            if kind == "Entity":
                km = re.match(r"(\S+)", rest)
                header = dict(HEADER_QUALIFIER.findall(rest))
                current = Entity(km.group(1) if km else "", header.pop("kind", ""), header,
                                 {}, {}, idx)
                spec.entities.append(current)
            else:
                current = Block(kind, rest, {}, {}, idx)
                spec.blocks.append(current)
            current._open = None  # the multi-line field or section being filled
            continue
        if current is None or not line.strip():
            continue
        if isinstance(current, Entity):
            _entity_line(current, line, idx)
        else:
            _block_line(current, line, idx)
    return spec


def _entity_line(entity: Entity, line: str, idx: int) -> None:
    attr = _parse_attribute(line, idx)
    if attr and re.match(r"^\s{2}\S", line):
        entity.attributes[attr.name] = attr
        entity._open = None
        return
    sec = ENTITY_SECTION.match(line)
    if sec:
        name, value = sec.groups()
        if value:
            entity.sections[name] = value
            entity._open = None
        else:
            entity.sections[name] = {} if name in ("Volume", "Features") else []
            entity._open = name
        return
    open_ = entity._open
    if open_ is None:
        return
    holder = entity.sections[open_]
    if isinstance(holder, dict):
        sub = SUB_FIELD.match(line)
        if sub:
            holder[sub.group(1)] = sub.group(2)
    else:
        holder.append(line.strip())


def _block_line(block: Block, line: str, idx: int) -> None:
    if re.match(r"^\s{2}\S", line):
        f = BLOCK_FIELD.match(line)
        if f:
            name, value = f.groups()
            block.fields[name] = value if value else []
            block.field_lines[name] = idx
            block._open = None if value else name
        return
    item = LIST_LINE.match(line)
    if item and block._open:
        block.fields[block._open].append(item.group(1))


# --------------------------------------------------------------------------- #
# Expressions
# --------------------------------------------------------------------------- #

REFERENCE = re.compile(r"\b([A-Z][A-Za-z0-9]*)\.([a-z_][a-z0-9_]*)\b")
CALL = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(")
OPERATORS = {"and", "or", "not"}


def strip_literals(expr: str) -> Tuple[str, List[str], Optional[str]]:
    """The expression with quoted text and map literals blanked, the quoted texts, and
    an error if quotes, parentheses or braces are unbalanced."""
    quoted = re.findall(r"'([^']*)'", expr)
    if expr.count("'") % 2:
        return expr, quoted, "unbalanced quote"
    bare = re.sub(r"'[^']*'", "''", expr)
    if bare.count("(") != bare.count(")"):
        return bare, quoted, "unbalanced parentheses"
    if bare.count("{") != bare.count("}"):
        return bare, quoted, "unbalanced braces"
    bare = re.sub(r"\{[^{}]*\}", "{}", bare)
    return bare, quoted, None


def outermost_call(expr: str) -> Optional[str]:
    m = re.match(r"^\s*([a-z_][a-z0-9_]*)\s*\(", expr)
    if not m:
        return None
    depth = 0
    for i in range(m.end() - 1, len(expr)):
        if expr[i] == "(":
            depth += 1
        elif expr[i] == ")":
            depth -= 1
            if depth == 0:
                return m.group(1) if not expr[i + 1:].strip() else None
    return None
