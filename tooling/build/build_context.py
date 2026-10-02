#!/usr/bin/env python3
"""build_context: resolve a design specification and an organisation profile into the
single build context every platform binding's templates read.

    python tooling/build/build_context.py SPEC.md PROFILE.md [--environment production] [--out context.json]

This is the shared resolution step of the Platform Implementation Authoring Standard (§3).
It runs once, before any template renders, and does everything a template must not:
places every object, names it, names or binds every principal, maps the design's
sensitivity markers onto the organisation's classes, marks adoptions, and checks names
against the platform's limits. A template then reads resolved names and never derives one.

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
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "evals"))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "validation"))

from design_lint import Finding, parse_frontmatter  # noqa: E402
from org_profile import (  # noqa: E402
    TIERS,
    PRINCIPAL,
    PROTECTION,
    Profile,
    derive,
    load_profile_standard,
    parse_profile,
    check_profile,
    render,
)
from spec_lint import Corpus, facet_names, lint_spec, standard  # noqa: E402
from spec_notation import entity_module, parse_specification  # noqa: E402

SCHEMA_VERSION = "1.0"
VIEW_PATTERN = "access-layer"


class Resolution:
    """Accumulates the context and every problem found while building it."""

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
    m = re.match(r"(\d+)\s+(hour|day|week|month|year)s?", value)
    if not m:
        return float("inf") if value.startswith("life") else 0.0
    n, unit = int(m.group(1)), m.group(2)
    return n * {"hour": 1 / 24, "day": 1, "week": 7, "month": 30.4375, "year": 365.25}[unit]


def resolve(spec_path: Path, profile_path: Path, environment: str = None,
            design_root: Path = None) -> Tuple[dict, List[Finding]]:
    design_root = design_root or (REPO_ROOT / "design")
    r = Resolution(str(spec_path), str(profile_path))

    spec_findings = lint_spec(spec_path, design_root)
    pstd = load_profile_standard(design_root)
    profile = parse_profile(profile_path.read_text(encoding="utf-8"), pstd, str(profile_path))
    profile_findings = check_profile(profile, pstd)
    if spec_findings or profile_findings:
        return {}, spec_findings + profile_findings

    text = spec_path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(text)
    std = standard(design_root)
    corpus = Corpus(design_root)
    spec = parse_specification(text, std)
    modules = list(fm.get("modules") or [])
    facets = facet_names(fm)
    variables = {"product_code": str(fm["product_code"]), "product": str(fm["product"])}

    phases = [p.strip() for p in profile.field("Environments", "Phases", "").split(",")]
    if environment and environment not in phases:
        r.fail("unknown-environment", f"environment '{environment}' is not one of {phases}")
    environment = environment or phases[-1]

    platform = {
        "name": profile.frontmatter["platform"],
        "version": str(profile.frontmatter["platform_version"]).strip('"'),
        **{k.lower().replace(" ", "_"): v for k, v in profile.blocks["Platform"].fields.items()},
    }
    max_len = int(platform["max_name_length"])
    reserved = {w.strip().upper() for w in platform.get("reserved_words", "").split(",") if w.strip()}

    attribute_template = profile.field("Naming", "Attributes")
    if not attribute_template:
        attribute_template = "{attribute}"
        r.default("naming.attributes", attribute_template, "Organisation Profile Standard §6.3")
    standard_names = profile.mapping("Naming", "Standard names")
    markers = profile.mapping("Classification", "Markers")
    protection = profile.mapping("Classification", "Protection")
    default_class = profile.field("Classification", "Default")
    adopted_entities = profile.mapping("Adoption", "Entities")

    def place(role, module, entity, kind=None, standard_owned=False, owner=None):
        try:
            container, obj = derive(profile, role, module, entity, kind, variables,
                                    environment, standard_owned)
        except KeyError as exc:
            r.fail("unplaceable", f"cannot place {role} for {entity} in module '{module}': "
                                  f"the profile has no container or rule for {exc}")
            return None
        for name, what in ((container, "container"), (obj, "object")):
            if len(name) > max_len:
                r.fail("name-too-long", f"{what} name '{name}' exceeds {max_len} characters")
            if name.upper() in reserved:
                r.fail("reserved-name", f"{what} name '{name}' is a reserved word")
        key = (container.upper(), obj.upper())
        label = owner or f"{role} of {entity}"
        if key in r.objects and r.objects[key] != label:
            r.fail("name-collision", f"{container}.{obj} is both {r.objects[key]} and {label}")
        r.objects[key] = label
        return {"container": container, "name": obj}

    def physical_attribute(name):
        if name in standard_names:
            return standard_names[name]
        return render(attribute_template, dict(variables, attribute=name))

    def classify(qualifiers):
        for marker in ("pii", "pii-incidental"):
            if marker in qualifiers:
                cls = markers.get(marker)
                return cls, protection.get(cls, "none")
        return default_class, protection.get(default_class, "none")

    # ---- entities declared by the specification ------------------------------------
    allocation_choice = next((d.get("choice") for d in (fm.get("decisions") or [])
                              if isinstance(d, dict) and d.get("id") == "DEC-SURROGATE-ALLOCATION"),
                             None)
    entities, declared = [], set()
    for e in spec.entities:
        declared.add(e.name)
        module = entity_module(e, std)
        if "module" not in e.header:
            r.default(f"entities.{e.name}.module", module, "Design Specification Standard §3.2")
        if module not in modules:
            r.fail("module-not-included", f"entity '{e.name}' belongs to module '{module}', "
                                          f"which the composition does not include", "spec")
        surrogate = next((a.name for a in e.attributes.values() if a.type == "Identifier"), None)
        allocation = e.header.get("allocation")
        if surrogate and not allocation and e.kind != "Keymap":
            allocation = allocation_choice
            r.default(f"entities.{e.name}.allocation", allocation, "DEC-SURROGATE-ALLOCATION")
        attributes = []
        for a in e.attributes.values():
            cls, prot = classify(a.qualifiers)
            target = a.qualifiers.get("->")
            attributes.append({
                "name": a.name,
                "physical_name": physical_attribute(a.name),
                "type": a.type,
                "required": "required" in a.qualifiers,
                "unique": "unique" in a.qualifiers,
                "references": [t.strip() for t in target.split("|")] if target else [],
                "discriminator": a.qualifiers.get("discriminator"),
                "derive": a.qualifiers.get("derive"),
                "synonyms": [s.strip() for s in a.qualifiers.get("synonyms", "").split(",") if s.strip()],
                "flags": [q for q in ("current-flag", "deleted-flag") if q in a.qualifiers],
                "classification": cls,
                "protection": prot,
            })
        patterns = [x.lstrip("- ").strip() for x in e.sections.get("Applies patterns", []) or []]
        objects = {}
        adoption = adopted_entities.get(f"{variables['product_code']}.{e.name}")
        if adoption:
            container, obj = adoption.split(".", 1)
            objects["table"] = {"container": container, "name": obj}
        else:
            objects["table"] = place("table", module, e.name, e.kind)
        if VIEW_PATTERN in patterns:
            objects["base_view"] = place("base_view", module, e.name, e.kind)
            objects["consumer_view"] = place("consumer_view", module, e.name, e.kind)
        keys = {}
        for line in e.sections.get("Keys", []) or []:
            if ":" in line:
                k, v = line.split(":", 1)
                keys[k.strip()] = v.strip()
        entities.append({
            "name": e.name, "kind": e.kind, "module": module,
            "profile": e.header.get("profile"), "allocation": allocation,
            "attributes": attributes, "keys": keys,
            "volume": e.sections.get("Volume"), "features": e.sections.get("Features"),
            "synonyms": [s.strip() for s in str(e.sections.get("Synonyms", "")).split(",") if s.strip()],
            "patterns": patterns,
            "capabilities": [x.lstrip("- ").strip() for x in e.sections.get("Requires capabilities", []) or []],
            "objects": objects,
            "adopted": bool(adoption),
        })

    # ---- relations the standards own ------------------------------------------------
    relations = []
    for module in modules:
        mode, extra = std.implicit_relations.get(module, ("none", []))
        names = []
        if mode == "all":
            names = list(std.module_entities.get(module, {}))
        elif mode == "by facet":
            enabled = {f.split(":", 1)[1] for f in facets if f.startswith(f"{module}:")}
            names = [n for n in std.module_entities.get(module, {})
                     if std.entity_facets.get((module, n)) in enabled]
        for name in names + extra:
            if name in declared or "<" in name:
                continue
            relations.append({"name": name, "module": module,
                              "objects": {"table": place("table", module, name,
                                                         standard_owned=True)}})

    # ---- containers and principals ---------------------------------------------------
    adopted_names = set(profile.mapping("Adoption", "Containers").values())
    adopted_names |= {v.split(".", 1)[0] for v in adopted_entities.values()}
    containers = {}
    for item in entities + relations:
        for obj in item["objects"].values():
            if obj:
                containers.setdefault(obj["container"], {
                    "name": obj["container"], "adopted": obj["container"] in adopted_names})
    principals = {}
    for tier in TIERS:
        m = PRINCIPAL.match(profile.field("Principals", tier))
        name = render(m.group(2), variables) if m.group(1) == "create" else m.group(2)
        principals[tier] = {"name": name, "create": m.group(1) == "create"}
        if len(name) > max_len:
            r.fail("name-too-long", f"principal name '{name}' exceeds {max_len} characters")

    # ---- product blocks ---------------------------------------------------------------
    def blocks(kind):
        return [dict({"name": b.name}, **{k.lower().replace(" ", "_"): v
                                          for k, v in b.fields.items()})
                for b in spec.blocks_of(kind)]

    def single(kind):
        found = blocks(kind)
        if not found:
            return None
        found[0].pop("name", None)
        return found[0]

    retention_block = spec.blocks_of("Retention")
    retention = dict(retention_block[0].fields) if retention_block else {}
    bounds = {"minimum": profile.field("Retention", "Audit minimum"),
              "maximum": profile.field("Retention", "Audit maximum")}
    audit = set(std.module_entities.get("observability", {}))
    audit |= set(std.implicit_relations.get("observability", ("", []))[1])
    for entity, value in retention.items():
        if entity not in audit or value == "life of product":
            continue
        days = _duration_days(value)
        if bounds["minimum"] and days < _duration_days(bounds["minimum"]):
            r.fail("retention-bound", f"{entity} retention '{value}' is below the organisation's "
                                      f"minimum of {bounds['minimum']}", "spec")
        if bounds["maximum"] and days > _duration_days(bounds["maximum"]):
            r.fail("retention-bound", f"{entity} retention '{value}' exceeds the organisation's "
                                      f"maximum of {bounds['maximum']}", "spec")

    decisions = {}
    for d in fm.get("decisions") or []:
        if isinstance(d, dict) and d.get("id"):
            options = corpus.decisions.get(d["id"], {})
            decisions[d["id"]] = {"choice": d.get("choice"), "because": d.get("because"),
                                  "advocated": bool(options.get(d.get("choice")))}

    context = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {"specification": spec_path.as_posix(), "profile": profile_path.as_posix()},
        "product": {"name": variables["product"], "code": variables["product_code"]},
        "organisation": profile.frontmatter.get("organisation"),
        "platform": platform,
        "environment": {"name": environment, "phases": phases,
                        "isolation": profile.field("Environments", "Isolation")},
        "composition": fm.get("composition"),
        "modules": modules,
        "facets": facets,
        "decisions": decisions,
        "product_decisions": blocks("Decision"),
        "separation": {k.lower().replace(" ", "_"): v
                       for k, v in profile.blocks["Separation"].fields.items()},
        "containers": sorted(containers.values(), key=lambda c: c["name"]),
        "principals": principals,
        "grant_level": profile.field("Principals", "Grant level"),
        "entities": entities,
        "relations": relations,
        "standard_names": standard_names,
        "classification": {"scheme": [s.strip() for s in
                                      profile.field("Classification", "Scheme").split(",")],
                           "default": default_class, "markers": markers,
                           "protection": protection},
        "embeddings": blocks("Embedding"),
        "models": blocks("Model"),
        "metrics": blocks("Metric"),
        "access_objects": blocks("AccessObject"),
        "orientation": single("Orientation"),
        "quality": single("Quality"),
        "lineage": single("Lineage"),
        "retention": retention,
        "runtime": single("Runtime"),
        "settings": dict(profile.blocks["Settings"].fields) if "Settings" in profile.blocks else {},
        "defaults_applied": r.defaults,
    }
    return (context if not r.findings else {}), r.findings


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("specification", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--environment")
    parser.add_argument("--out", type=Path, help="write the context here instead of stdout")
    args = parser.parse_args(argv)
    context, findings = resolve(args.specification, args.profile, args.environment)
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
