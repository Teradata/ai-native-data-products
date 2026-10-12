#!/usr/bin/env python3
"""build_context: resolve a design specification and an organisation profile into the
single build context every platform binding's templates read.

    python tooling/build/build_context.py SPEC.md PROFILE.md [--environment production] [--out context.json]

This is the shared resolution step of the Platform Implementation Authoring Standard (§3).
It runs once, before any template renders, and does everything a template must not:
places every object, names it, names or binds every principal, maps the design's
sensitivity markers onto the organisation's classes, marks adoptions, derives storage
paths, and checks names against the platform's limits. A template then reads resolved
names and never derives one.

The specification is validated by `spec_lint` and the profile by `org_profile`; resolution
does not start on an invalid input. A required fact that is missing fails with a message
naming the fact and the input it should come from. Every default applied is recorded in
`defaults_applied`.

Exit code is 0 with a context written, 1 with findings. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "evals"))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))

from design_lint import Finding, parse_frontmatter  # noqa: E402
from org_profile import (  # noqa: E402
    PRINCIPAL,
    TIERS,
    check_profile,
    container_name,
    container_parts,
    derive,
    derive_path,
    load_profile_standard,
    parse_profile,
    render,
)
from binding import load_binding  # noqa: E402
from expressions import ExpressionError, Node, Unrenderable, functions_used, parse as parse_expression  # noqa: E402
from expressions import references as expression_references, render as render_expression  # noqa: E402
from org_profile import _snake  # noqa: E402
from spec_lint import Corpus, _keys, facet_names, lint_spec, standard  # noqa: E402
from spec_notation import entity_module, parse_specification  # noqa: E402

SCHEMA_VERSION = "1.0"
VIEW_PATTERN = "access-layer"
SENSITIVITY_MARKERS = ("pii", "pii-incidental")
DEFAULT_VERSION = "0.1.0"

# The canonical columns each temporal profile carries (temporal-lifecycle-metadata §4, §7).
# Every profile carries the audit pair; versioned profiles add the validity pair and the
# currency flag; the bitemporal profile adds the transaction-time pair; deletion support
# adds the deletion pair. Tests check every name here is a canonical column of the pattern.
VERSIONED = ("SCD2_HISTORY", "ASSOCIATION_SCD2", "SCD2_BITEMPORAL")
PROFILE_COLUMNS = {
    "SCD2_HISTORY": ["valid_from_dts", "valid_to_dts", "is_current"],
    "ASSOCIATION_SCD2": ["valid_from_dts", "valid_to_dts", "is_current"],
    "SCD2_BITEMPORAL": ["valid_from_dts", "valid_to_dts", "transaction_from_dts",
                        "transaction_to_dts", "is_current"],
}
AUDIT_COLUMNS = ["created_dts", "updated_dts"]
DELETION_COLUMNS = ["is_deleted", "deleted_dts"]


class Resolution:
    """Accumulates the context's defaults and every problem found while building it."""

    def __init__(self, spec_path: str, profile_path: str):
        self.spec_path, self.profile_path = spec_path, profile_path
        self.findings: List[Finding] = []
        self.defaults: List[dict] = []
        self.objects: Dict[Tuple[str, str], str] = {}  # (container, object) -> owner

    def fail(self, rule: str, message: str, source: str = "profile"):
        path = self.profile_path if source == "profile" else self.spec_path
        self.findings.append(Finding(path, 1, rule, message))

    def default(self, where: str, value, source: str):
        self.defaults.append({"field": where, "value": value, "source": source})


def _duration_days(value: str) -> float:
    """Days a retention keeps data; the longer tier of a two-tier retention."""
    if "queryable" in value:
        return max(_duration_days(v.replace("queryable", "").replace("archived", "").strip())
                   for v in value.split(","))
    if value.startswith(("life", "indefinite")):
        return float("inf")
    m = re.match(r"(\d+)\s+(hour|day|week|month|year)s?", value)
    if not m:
        return 0.0
    n, unit = int(m.group(1)), m.group(2)
    return n * {"hour": 1 / 24, "day": 1, "week": 7, "month": 30.4375, "year": 365.25}[unit]


def _fields(block) -> dict:
    return {k.lower().replace(" ", "_"): v for k, v in block.fields.items()}


def resolve(spec_path: Path, profile_path: Path, environment: str = None,
            design_root: Path = None, version: str = None) -> Tuple[dict, List[Finding]]:
    design_root = design_root or (REPO_ROOT / "design")
    r = Resolution(str(spec_path), str(profile_path))

    spec_findings = lint_spec(spec_path, design_root)
    pstd = load_profile_standard(design_root)
    profile = parse_profile(profile_path.read_text(encoding="utf-8"), pstd, str(profile_path))
    profile_findings = check_profile(profile, pstd)
    binding, binding_findings = (load_binding(profile.frontmatter["platform"], design_root.parent)
                                 if profile.frontmatter.get("platform") else (None, []))
    if spec_findings or profile_findings or binding_findings:
        return {}, spec_findings + profile_findings + binding_findings

    text = spec_path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(text)
    std = standard(design_root)
    corpus = Corpus(design_root)
    spec = parse_specification(text, std)
    modules = list(fm.get("modules") or [])
    facets = facet_names(fm)
    code = str(fm["product_code"])
    variables = {"product_code": code, "product": str(fm["product"])}
    settled = {d.get("id"): d.get("choice") for d in (fm.get("decisions") or []) if isinstance(d, dict)}

    if not version:
        version = DEFAULT_VERSION
        r.default("product.version", version, "build_context --version")
    phases = [p.strip() for p in profile.field("Environments", "Phases", "").split(",")]
    if environment and environment not in phases:
        r.fail("unknown-environment", f"environment '{environment}' is not one of {phases}")
    environment = environment or phases[-1]

    platform = {"name": profile.frontmatter["platform"],
                "version": str(profile.frontmatter["platform_version"]).strip('"'),
                **_fields(profile.blocks["Platform"])}
    max_len = int(platform["max_name_length"])
    reserved = {w.strip().upper() for w in platform.get("reserved_words", "").split(",") if w.strip()}

    attribute_template = profile.field("Naming", "Attributes")
    if not attribute_template:
        attribute_template = "{attribute}"
        r.default("naming.attributes", attribute_template, "Organisation Profile Standard §6.3")
    standard_names = profile.mapping("Naming", "Standard names")
    scheme = [s.strip() for s in profile.field("Classification", "Scheme").split(",")]
    markers = profile.mapping("Classification", "Markers")
    protection = profile.mapping("Classification", "Protection")
    default_class = profile.field("Classification", "Default")
    adopted_entities = profile.mapping("Adoption", "Entities")
    aliases = profile.mapping("Adoption", "Column aliases")

    def check_name(name, what):
        if len(name) > max_len:
            r.fail("name-too-long", f"{what} name '{name}' exceeds {max_len} characters")
        if name.upper() in reserved:
            r.fail("reserved-name", f"{what} name '{name}' is a reserved word")

    def place(role, module, entity, kind=None, standard_owned=False, cls=None, relation_rule=None):
        try:
            container, obj = derive(profile, role, module, entity, kind, variables,
                                    environment, standard_owned, cls, relation_rule)
            path = derive_path(profile, role, module, entity, kind, variables, environment,
                               standard_owned, cls) if role == "table" else None
        except KeyError as exc:
            r.fail("unplaceable", f"cannot place {role} for {entity} in module '{module}': "
                                  f"the profile has no container, rule or template for {exc}")
            return None
        check_name(container, "container")
        check_name(obj, "object")
        key, label = (container.upper(), obj.upper()), f"{role} of {entity}"
        if key in r.objects and r.objects[key] != label:
            r.fail("name-collision", f"{container}.{obj} is both {r.objects[key]} and {label}")
        r.objects[key] = label
        placed = {"container": container, "name": obj}
        if path:
            placed["path"] = path
        return placed

    def physical_attribute(entity, name):
        alias = aliases.get(f"{code}.{entity}.{name}")
        if alias:
            return alias
        if name in standard_names:
            return standard_names[name]
        return render(attribute_template, dict(variables, attribute=name))

    def classify(qualifiers):
        for marker in SENSITIVITY_MARKERS:
            if marker in qualifiers:
                cls = markers.get(marker)
                return cls, protection.get(cls, "none")
        return default_class, protection.get(default_class, "none")

    def most_sensitive(classes):
        ranked = [c for c in classes if c in scheme]
        return max(ranked, key=scheme.index) if ranked else default_class

    def bound(logical, where):
        physical = binding.physical_type(logical)
        if physical is None:
            r.fail("unsupported-type", f"{where}: the {binding.platform} binding declares no physical "
                                       f"type for {logical}", "spec")
        return physical

    def shape_attribute(entity_name, a):
        cls, prot = classify(a.qualifiers)
        target = a.qualifiers.get("->")
        out = {
            "name": a.name,
            "physical_name": physical_attribute(entity_name, a.name),
            "type": a.type,
            "physical_type": bound(a.type, f"{entity_name}.{a.name}"),
            "description": a.description,
            "required": "required" in a.qualifiers,
            "unique": "unique" in a.qualifiers,
            "references": [t.strip() for t in target.split("|")] if target else [],
            "discriminator": a.qualifiers.get("discriminator"),
            "derive": a.qualifiers.get("derive"),
            "synonyms": [s.strip() for s in a.qualifiers.get("synonyms", "").split(",") if s.strip()],
            "flags": [q for q in ("current-flag", "deleted-flag") if q in a.qualifiers],
            "canonical": a.name in std.canonical_attributes,
            "classification": cls,
            "protection": prot,
        }
        if a.type.startswith("Enum{"):
            out["members"] = [m.strip() for m in a.type[5:-1].split("|")]
        vector = re.fullmatch(r"Vector\[(\d+)\]", a.type)
        if vector:
            out["dimensions"] = int(vector.group(1))
        return out

    def temporal_columns(entity_name, profile_name, attribute_names, deletion):
        names = PROFILE_COLUMNS.get(profile_name, []) + AUDIT_COLUMNS + (DELETION_COLUMNS if deletion else [])
        out = []
        for name in names:
            if name in attribute_names:
                continue  # the specification declared it; it is the canonical column, not a second one
            logical = "Timestamp" if name.endswith("_dts") else "Flag"
            out.append({"name": name, "physical_name": standard_names.get(name, name),
                        "type": logical, "physical_type": bound(logical, f"{entity_name}.{name}"),
                        "required": name != "deleted_dts",
                        "description": std.canonical_meaning.get(name, "")})
        return out

    def shape(e, module, allocation, keys, standard_owned=False):
        attributes = [shape_attribute(e.name, a) for a in e.attributes.values()]
        names = {a["name"] for a in attributes}
        profile_name = e.header.get("profile")
        deletion = (any("deleted-flag" in a["flags"] or a["name"] == "is_deleted" for a in attributes)
                    or (settled.get("DEC-DELETE-STRATEGY") == "soft-delete" and profile_name in VERSIONED
                        and not standard_owned))
        description = str(e.sections.get("Description") or "").strip()
        if not description:
            description = f"{e.name}, as the {module} module standard defines it."
        surrogate = keys.get("surrogate") or [a.name for a in e.attributes.values() if a.type == "Identifier"][:1]
        return {
            "name": e.name, "kind": e.kind, "module": module, "profile": profile_name,
            "description": description,
            "history": profile_name in VERSIONED,
            "bitemporal": profile_name == "SCD2_BITEMPORAL",
            "supports_deletion": bool(deletion),
            "identity": {"allocation": allocation, "surrogate": surrogate,
                         "natural": keys.get("natural", []),
                         "keymap": keymap_of.get(e.name), "allocates": e.header.get("allocates")},
            "attributes": attributes,
            "temporal": temporal_columns(e.name, profile_name, names, deletion),
        }

    def emitted(item, role_kind, module, name, kind, cls=None, standard_owned=False):
        """Place the extra roles the binding emits for this entity (sequences, functions)."""
        out = {}
        allocation = item["identity"]["allocation"]
        if "sequence" in binding.emits and (
                (kind == "Keymap" and "keymap" in binding.emits["sequence"])
                or (allocation and allocation in binding.emits["sequence"] and allocation != "keymap")):
            out["sequence"] = place("sequence", module, name, kind, standard_owned, cls)
        if "function" in binding.emits and item["profile"] in binding.emits["function"]:
            out["function"] = place("function", module, name, kind, standard_owned, cls)
        return out

    # Standard-owned names never land on a specification attribute's name.
    spec_attributes = {a for e in spec.entities for a in e.attributes}
    for logical, physical in standard_names.items():
        if physical in spec_attributes and physical != logical:
            r.fail("name-collision", f"standard name '{logical}' maps onto '{physical}', which "
                                     f"the specification uses as an attribute name")

    # ---- entities declared by the specification ------------------------------------
    product_choice = settled.get("DEC-SURROGATE-ALLOCATION") or "keymap"
    keymap_of = {e.header["allocates"]: e.name for e in spec.entities
                 if e.kind == "Keymap" and e.header.get("allocates")}
    entities, declared, allocators = [], set(), []
    for e in spec.entities:
        declared.add(e.name)
        module = entity_module(e, std)
        if "module" not in e.header:
            r.default(f"entities.{e.name}.module", module, "Design Specification Standard §3.2")
        if module not in modules:
            r.fail("module-not-included", f"entity '{e.name}' belongs to module '{module}', "
                                          f"which the composition does not include", "spec")
        keys = _keys(e)
        allocation = None
        if e.kind != "Keymap":
            allocation = e.header.get("allocation")
            if not allocation:
                allocation = product_choice
                r.default(f"entities.{e.name}.allocation", allocation, "DEC-SURROGATE-ALLOCATION")
            if allocation == "external-allocator":
                allocators.append(e.name)
        item = shape(e, module, allocation, keys)
        attributes = item["attributes"]
        entity_class = most_sensitive(a["classification"] for a in attributes)
        patterns = [x.lstrip("- ").strip() for x in e.sections.get("Applies patterns", []) or []]
        objects = {}
        adoption = adopted_entities.get(f"{code}.{e.name}")
        if adoption:
            container, obj = adoption.split(".", 1)
            objects["table"] = {"container": container, "name": obj}
        else:
            objects["table"] = place("table", module, e.name, e.kind, cls=entity_class)
        if VIEW_PATTERN in patterns:
            if "base_view" in binding.emits:
                objects["base_view"] = place("base_view", module, e.name, e.kind, cls=entity_class)
            objects["consumer_view"] = place("consumer_view", module, e.name, e.kind, cls=entity_class)
        objects.update(emitted(item, "entity", module, e.name, e.kind, entity_class))
        entities.append({
            **item,
            "classification": entity_class,
            "volume": e.sections.get("Volume"), "features": e.sections.get("Features"),
            "synonyms": [s.strip() for s in str(e.sections.get("Synonyms", "")).split(",") if s.strip()],
            "patterns": patterns,
            "capabilities": [x.lstrip("- ").strip() for x in e.sections.get("Requires capabilities", []) or []],
            "objects": objects,
            "adopted": bool(adoption),
        })

    allocator = profile.field("Adoption", "Allocator")
    if allocators and not allocator:
        r.fail("missing-allocator", f"{', '.join(allocators)} allocate through an external allocator, "
                                    f"but the profile's Adoption block names no Allocator")

    # ---- relations the standards own ------------------------------------------------
    tall = any((e.sections.get("Features") or {}).get("storage") == "tall" for e in spec.entities)
    relations = []
    for module in modules:
        imp = std.implicit_relations.get(module)
        if imp is None:
            continue
        names = []
        if imp.mode == "all":
            names = list(std.module_entities.get(module, {}))
        elif imp.mode == "by facet":
            enabled = {f.split(":", 1)[1] for f in facets if f.startswith(f"{module}:")}
            names = [n for n in std.module_entities.get(module, {})
                     if std.entity_facets.get((module, n)) in enabled]
        tables = names + imp.tables + (imp.tall if tall else [])
        defs = std.module_entity_defs.get(module, {})
        for name in tables:
            if name in declared or "<" in name:
                continue
            definition = defs.get(name) or std.pattern_entity_defs.get(name)
            item = (shape(definition, module, "inline", _keys(definition), standard_owned=True)
                    if definition else {"name": name, "module": module, "kind": "Record",
                                        "profile": None, "description": f"{name}, as its pattern defines it.",
                                        "history": False, "bitemporal": False, "supports_deletion": False,
                                        "identity": {"allocation": None, "surrogate": [], "natural": [],
                                                     "keymap": None, "allocates": None},
                                        "attributes": [], "temporal": []})
            objects = {"table": place("table", module, name, standard_owned=True)}
            if std.entity_facets.get((module, name)) != "runtime":
                if "base_view" in binding.emits:
                    objects["base_view"] = place("base_view", module, name, item["kind"],
                                                 standard_owned=True, relation_rule=False)
                objects["consumer_view"] = place("consumer_view", module, name, item["kind"],
                                                 standard_owned=True, relation_rule=False)
            objects.update(emitted(item, "relation", module, name, item["kind"], standard_owned=True))
            relations.append({**item, "relation": "table", "defined": bool(definition), "objects": objects})
        for name in imp.views:
            relations.append({"name": name, "module": module, "kind": "View", "relation": "view",
                              "defined": False, "profile": None,
                              "description": f"The {name} discovery view the {module} module defines.",
                              "history": False, "bitemporal": False, "supports_deletion": False,
                              "identity": {"allocation": None, "surrogate": [], "natural": [],
                                           "keymap": None, "allocates": None},
                              "attributes": [], "temporal": [],
                              "objects": {"consumer_view": place("consumer_view", module, name,
                                                                 standard_owned=True)}})

    # ---- containers and principals ---------------------------------------------------
    adopted_names = set(profile.mapping("Adoption", "Containers").values())
    adopted_names |= {v.split(".", 1)[0] for v in adopted_entities.values()}
    parts = container_parts(profile)
    name_of = {}
    for key in parts:
        try:
            name_of[key] = container_name(profile, key, dict(variables, module=key,
                                          _abbrev=profile.mapping("Naming", "Abbreviations")),
                                          environment)
        except KeyError:
            continue  # a key no product of this composition reaches
    parent_of = {name_of[k]: name_of.get(p) for k, (_, p) in parts.items() if p and k in name_of}
    containers = {}
    for item in entities + relations:
        for obj in item["objects"].values():
            if obj:
                containers.setdefault(obj["container"], {
                    "name": obj["container"], "adopted": obj["container"] in adopted_names,
                    "parent": parent_of.get(obj["container"]), "holds_objects": True})
    for child in list(containers.values()):
        parent = child["parent"]
        if parent and parent not in containers:
            containers[parent] = {"name": parent, "adopted": parent in adopted_names,
                                  "parent": None, "holds_objects": False}
    principals = {}
    for tier in TIERS:
        m = PRINCIPAL.match(profile.field("Principals", tier))
        name = render(m.group(2), variables) if m.group(1) == "create" else m.group(2)
        principals[tier] = {"name": name, "create": m.group(1) == "create"}
        check_name(name, "principal")

    # ---- product blocks ---------------------------------------------------------------
    def blocks(kind):
        return [dict({"name": b.name}, **_fields(b)) for b in spec.blocks_of(kind)]

    def single(kind):
        found = spec.blocks_of(kind)
        return _fields(found[0]) if found else None

    retention_block = spec.blocks_of("Retention")
    retention = dict(retention_block[0].fields) if retention_block else {}
    bounds = {"minimum": profile.field("Retention", "Audit minimum"),
              "maximum": profile.field("Retention", "Audit maximum"),
              "personal": profile.field("Retention", "Personal data maximum")}
    audit = set(std.module_entities.get("observability", {}))
    audit |= set(std.implicit_relations["observability"].tables) if "observability" in std.implicit_relations else set()
    personal = {n for (m, n), f in std.entity_facets.items() if m == "memory" and f == "runtime"}
    personal |= {e["name"] for e in entities
                 if any(a["classification"] == markers.get("pii") for a in e["attributes"])}
    for entity, value in retention.items():
        days = _duration_days(value)
        if entity in audit and value != "life of product":
            if bounds["minimum"] and days < _duration_days(bounds["minimum"]):
                r.fail("retention-bound", f"{entity} retention '{value}' is below the organisation's "
                                          f"audit minimum of {bounds['minimum']}", "spec")
            if bounds["maximum"] and days > _duration_days(bounds["maximum"]):
                r.fail("retention-bound", f"{entity} retention '{value}' exceeds the organisation's "
                                          f"audit maximum of {bounds['maximum']}", "spec")
        if entity in personal and bounds["personal"] and days > _duration_days(bounds["personal"]):
            r.fail("retention-bound", f"{entity} holds records about people and its retention "
                                      f"'{value}' exceeds the organisation's personal-data maximum "
                                      f"of {bounds['personal']}", "spec")

    graph = single("Graph")
    if "observability:graph-lineage" in facets:
        template = profile.field("Naming", "Graph key")
        if not template:
            r.fail("missing-graph-key", "the product enables graph-lineage, but the profile's Naming "
                                        "block has no Graph key template")
        elif graph is not None:
            graph["graph_key"] = render(template, dict(variables, module="observability"))

    decisions = {}
    for d in fm.get("decisions") or []:
        if isinstance(d, dict) and d.get("id"):
            options = corpus.decisions.get(d["id"], {})
            decisions[d["id"]] = {"choice": d.get("choice"), "because": d.get("because"),
                                  "advocated": bool(options.get(d.get("choice")))}

    # ---- relationships, from every reference ------------------------------------------
    by_name = {x["name"]: x for x in relations + entities}
    physical = {(x["name"], a["name"]): a["physical_name"] for x in entities + relations
                for a in x["attributes"]}
    physical.update({(x["name"], t["name"]): t["physical_name"] for x in entities + relations
                     for t in x["temporal"]})

    def identity_column(target):
        ident = target["identity"]
        names = ident["surrogate"] or ident["natural"]
        return [physical.get((target["name"], n), n) for n in names]

    relationships = []
    for x in entities:
        for a in x["attributes"]:
            for target_name in a["references"]:
                target = by_name.get(target_name)
                if target is None:
                    continue  # a module entity this composition does not include
                relationships.append({
                    "source": x["name"], "source_attribute": a["name"],
                    "source_column": a["physical_name"], "target": target_name,
                    "target_columns": identity_column(target), "mandatory": a["required"],
                    "discriminator": a["discriminator"],
                    "discriminator_value": target_name.upper() if a["discriminator"] else None})

    # ---- expressions, rendered in the binding's dialect ---------------------------------
    measures = {b.name: b.fields.get("Measure") for b in spec.blocks_of("Metric")}

    def expand(node, seen=()):
        """Inline metric('Name') with that metric's own measure."""
        if node.kind == "call" and node.value == "metric" and node.args and node.args[0].kind == "string":
            name = node.args[0].value
            if name in seen or name not in measures:
                return node
            return expand(parse_expression(measures[name]), seen + (name,))
        node.args = [expand(a, seen) for a in node.args]
        node.pairs = [(k, expand(v, seen)) for k, v in node.pairs]
        return node

    def ref_sql(entity, attribute):
        alias = binding.ident(_snake(entity))
        if attribute is None:
            return alias
        return alias + "." + binding.ident(physical.get((entity, attribute), attribute))

    types = {(x["name"], a["name"]): a["type"] for x in entities + relations for a in x["attributes"]}
    types.update({(x["name"], t["name"]): t["type"] for x in entities + relations for t in x["temporal"]})

    def is_flag(entity, attribute):
        return types.get((entity, attribute)) == "Flag"

    def expression(text, condition=False):
        if not text:
            return None
        try:
            node = expand(parse_expression(text))
        except ExpressionError as exc:
            r.fail("invalid-expression", f"'{text}': {exc}", "spec")
            return None
        out = {"text": text, "ast": node.to_dict(),
               "references": [{"entity": e, "attribute": a,
                               "physical_name": physical.get((e, a), a) if a else None}
                              for e, a in expression_references(node)],
               "sql": None, "unsupported": []}
        try:
            out["sql"] = render_expression(node, binding.functions, ref_sql, binding.literal,
                                           is_flag, condition)
        except Unrenderable as exc:
            out["unsupported"] = [str(exc)]
        return out

    for x in entities:
        for a in x["attributes"]:
            if a["derive"]:
                a["derive"] = expression(a["derive"])

    embeddings = blocks("Embedding")
    for b in embeddings:
        b["source"] = expression(b.get("source"))
        b["where"] = expression(b.get("where"), condition=True)
        b["objects"] = {}
        if "embedding" in binding.emits.get("function", []):
            b["objects"]["function"] = place("function", "search", b["name"])
    metrics = blocks("Metric")
    for b in metrics:
        b["measure"] = expression(b.get("measure"))
        b["filter"] = expression(b.get("filter"), condition=True)

    quality = single("Quality")
    if quality:
        rules = []
        for line in quality.get("rules") or []:
            body = line[2:] if line.startswith("- ") else line
            depth, close = 0, len(body)
            for i, ch in enumerate(body):
                depth += ch == "("
                depth -= ch == ")"
                if ch == ")" and depth == 0:
                    close = i
                    break
            check = expression(body[:close + 1])
            thresholds = body[close + 1:].lstrip()[1:].strip()
            fn = check["ast"]["value"] if check else None
            rules.append({"rule": line, "function": fn, "check": check,
                          "arguments": [expression_arg for expression_arg in
                                        ([] if not check else check["ast"].get("args", []))],
                          "thresholds": thresholds})
        quality["rules"] = rules
        quality["weights"] = {k.strip(): int(v.strip().rstrip("%")) for k, v in
                              (w.split(":", 1) for w in quality.get("weights") or [])}

    orientation = single("Orientation")
    if orientation:
        role = "consumer_view" if orientation.get("entrypoint") == "access-layer" else "table"
        module = "semantic" if role == "table" else "domain"
        try:
            orientation["entrypoint_container"] = derive(profile, role, module, "Entry", None,
                                                         variables, environment)[0]
        except KeyError:
            r.fail("unplaceable", "the profile cannot place the orientation entrypoint")

    product = {"name": variables["product"], "code": code, "version": version,
               **(single("Product") or {})}
    context = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {"specification": spec_path.as_posix(), "profile": profile_path.as_posix()},
        "product": product,
        "organisation": profile.frontmatter.get("organisation"),
        "platform": platform,
        "binding": {"platform": binding.platform, "principals": binding.principals,
                    "emits": binding.emits, "identifier_quote": binding.identifier_quote,
                    "literal_quote": binding.literal_quote, "phases": binding.phases,
                    "checks": binding.checks},
        "environment": {"name": environment, "phases": phases,
                        "isolation": profile.field("Environments", "Isolation")},
        "composition": fm.get("composition"),
        "modules": modules,
        "facets": facets,
        "decisions": decisions,
        "product_decisions": blocks("Decision"),
        "separation": _fields(profile.blocks["Separation"]),
        "containers": sorted(containers.values(), key=lambda c: c["name"]),
        "principals": principals,
        "grant_level": profile.field("Principals", "Grant level"),
        "allocator": allocator,
        "entities": entities,
        "relations": relations,
        "relationships": relationships,
        "standard_names": standard_names,
        "classification": {"scheme": scheme, "default": default_class, "markers": markers,
                           "protection": protection},
        "embeddings": embeddings,
        "models": blocks("Model"),
        "metrics": metrics,
        "access_objects": blocks("AccessObject"),
        "glossary": blocks("Glossary"),
        "orientation": orientation,
        "quality": quality,
        "lineage": single("Lineage"),
        "retention": retention,
        "runtime": single("Runtime"),
        "graph": graph,
        "catalogue": _fields(profile.blocks["Catalogue"]) if "Catalogue" in profile.blocks else None,
        "storage": {kind.lower(): _fields(profile.blocks[kind])
                    for kind in ("Storage", "Files", "Partitioning", "Lifecycle", "StorageAccess")
                    if kind in profile.blocks} or None,
        "settings": dict(profile.blocks["Settings"].fields) if "Settings" in profile.blocks else {},
        "defaults_applied": r.defaults,
    }
    return (context if not r.findings else {}), r.findings


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("specification", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--environment")
    parser.add_argument("--version", help="the product version being built")
    parser.add_argument("--out", type=Path, help="write the context here instead of stdout")
    args = parser.parse_args(argv)
    context, findings = resolve(args.specification, args.profile, args.environment,
                                version=args.version)
    if findings:
        for f in findings:
            print(str(f))
        print(f"\nbuild-context: {len(findings)} problem(s); no context written", file=sys.stderr)
        return 1
    out = json.dumps(context, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(out + "\n", encoding="utf-8")
        print(f"build-context: wrote {args.out}")
    else:
        print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
