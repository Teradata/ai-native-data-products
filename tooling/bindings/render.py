"""Render a platform binding from a design specification and an organisation profile.

The build context is resolved first (tooling/build/build_context.py), from the specification,
the profile and the binding's own declarations. This module then renders the binding's
declared phases, deploy script and validation checks from that context alone. SQL lives in
the binding's templates; this module selects and orders them, and never connects to a
database.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tooling" / "build"))

import build_context  # noqa: E402
from binding import load_binding  # noqa: E402

RESERVED = ("design", "implementation", "examples", "roles", "tooling")


class RenderError(Exception):
    """The inputs do not resolve, or the binding cannot render them."""


def environment(binding, context):
    """A Jinja environment over the binding's templates, with its quoting and the context's
    relations by logical name. Templates read the context; they derive no names."""
    env = Environment(loader=FileSystemLoader(REPO / "implementation" / binding.platform),
                      undefined=StrictUndefined, keep_trailing_newline=True, autoescape=False)
    by_name = {x["name"]: x for x in context["entities"] + context["relations"]}
    env.filters.update(
        ident=binding.ident,
        literal=lambda v: "NULL" if v is None else binding.literal(v),
        qualified=lambda obj: binding.qualified(obj["container"], obj["name"]))
    env.globals.update(named=by_name.get)
    return env


def _tidy(text):
    return re.sub(r"\n[ \t]*(\n[ \t]*)+", "\n\n", text).strip()


def persisted(context):
    """The relations a binding creates: placed tables that are defined and not adopted."""
    return [x for x in context["entities"] + context["relations"]
            if "table" in x["objects"] and x.get("defined", True) and not x.get("adopted", False)]


def gaps(context):
    """What the specification asks for that this binding does not render, from the context."""
    out = []

    def walk(node, where):
        if isinstance(node, dict):
            if "text" in node and node.get("unsupported"):
                out.append(f"{where}: '{node['text']}' uses {', '.join(node['unsupported'])}, "
                           f"which the binding does not render")
                return
            for k, v in node.items():
                walk(v, f"{where}.{k}" if where else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{v.get('name', i) if isinstance(v, dict) else i}]")

    for key in ("entities", "metrics", "embeddings", "quality"):
        walk(context.get(key), key)
    for b in context.get("embeddings", []):
        if not ({"function", "procedure"} & set(b["objects"])):
            out.append(f"embeddings[{b['name']}]: the binding emits no similarity search object")
    unread = [x["name"] for x in context["entities"] + context["relations"]
              if x.get("history") and "consumer_view" in x["objects"]
              and not {"function", "procedure", "base_view"} & set(x["objects"])]
    if unread:
        out.append(f"history: {', '.join(unread)} have no history surface consumers can be granted "
                   f"(temporal-lifecycle-metadata §9)")
    for a in context.get("access_objects", []):
        out.append(f"access_objects[{a['name']}]: composite access objects are not rendered")
    out += [f"capture: {g}" for g in context.get("capture", {}).get("gaps", [])]
    binding, _ = load_binding(context["platform"]["name"])
    runtime = [x["name"] for x in context["relations"] if x.get("runtime")]
    if runtime and binding.runtime_scope != "enforced":
        out.append(f"runtime: {', '.join(runtime)} are not restricted to the requesting identity's scope "
                   f"on this platform (access-layer §4)")
    if "observability:graph-lineage" in context.get("facets", []):
        out.append("facets: the graph-lineage exposure is not rendered")
    if context.get("catalogue"):
        out.append("catalogue: the organisation catalogue registration is not rendered")
    protected = sorted({(c["classification"], c["protection"]) for x in context["entities"] + context["relations"]
                        for c in x.get("columns", [])
                        if c.get("protection", "none") != "none"})
    out += [f"classification: {cls} data is to be protected '{how}', which the binding does not render"
            for cls, how in protected]
    if context.get("storage"):
        out.append("storage: the profile holds tables in object storage, which the binding does not render; "
                   "tables are created in the platform's own storage")
    return out


def render_context(context):
    """Every file the binding renders for a resolved context: its phases, deploy script and
    manifest. A phase whose template renders nothing for this composition emits no file."""
    binding, findings = load_binding(context["platform"]["name"])
    if findings:
        raise RenderError("; ".join(str(f) for f in findings))
    if not binding.phases:
        raise RenderError(f"the {binding.platform} binding declares no Phases")
    env = environment(binding, context)

    def render(template, **extra):
        return _tidy(env.get_template(template).render(**dict(context, **extra)))

    files, phases = {}, []
    for name, template in binding.phases.items():
        sql = render(template)
        if sql:
            files[name] = sql + "\n"
            phases.append({"file": name, "sql": sql})
    if binding.deploy:
        files["deploy.sql"] = render(binding.deploy, phases=phases) + "\n"

    checks, counters = [], {}

    def add(name, scope_kind, scope_id, module, sql):
        counters[name] = counters.get(name, 0) + 1
        checks.append({"test_id": f"{context['product']['code']}-{name.upper()}-{counters[name]:03d}",
                       "check": name, "scope_kind": scope_kind, "scope_id": scope_id,
                       "module": module, "category": "STRUCTURAL", "severity": "ERROR",
                       "sql": sql.rstrip(";").rstrip()})

    for key, template in binding.checks.items():
        scope, name = key.split(" ", 1)
        if scope == "entity":
            for x in persisted(context):
                add(name, "ENTITY", x["name"], x["module"], render(template, entity=x))
        elif scope == "relationship":
            for r in context["relationships"]:
                add(name, "ENTITY", r["source"], r["source_module"], render(template, relationship=r))
        elif scope == "module" and name in context["modules"]:
            add("module", "MODULE", name, name, render(template, module=name))

    def placed(name):
        x = next((x for x in context["relations"] if x["name"] == name), None)
        return x and {"objects": x["objects"], "column_names": x.get("column_names", {})}

    manifest = {
        "platform": binding.platform,
        "product": context["product"],
        "modules": context["modules"],
        "containers": context["containers"],
        "phases": [p["file"] for p in phases],
        "checks": checks,
        "evidence": {"run": placed("ValidationRun"), "area": placed("ValidationArea"),
                     "evidence_window_days": context["quality"]["evidence_window_days"]},
        "gaps": gaps(context),
        "defaults_applied": context["defaults_applied"],
    }
    files["manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    files["context.json"] = json.dumps(context, indent=2) + "\n"
    return files


def render_product(spec, profile, environment_name=None, version=None):
    """Resolve the inputs into a build context and render the binding the profile names."""
    context, findings = build_context.resolve(Path(spec), Path(profile), environment_name,
                                              version=version)
    if findings:
        raise RenderError("\n".join(str(f) for f in findings))
    return render_context(context)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="the design specification")
    parser.add_argument("profile", type=Path, help="the organisation profile; it names the platform")
    parser.add_argument("--environment", help="the lifecycle phase to place for")
    parser.add_argument("--version", help="the product version, when the specification leaves it open")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if any(out.is_relative_to(REPO / r) for r in RESERVED):
        parser.error("Generated output must be outside the skill corpus (use build/ or another repository)")
    if out.exists() and any(out.iterdir()):
        parser.error("Output directory must be empty; existing products are never overwritten")
    try:
        files = render_product(args.spec, args.profile, args.environment, args.version)
    except RenderError as exc:
        parser.exit(1, f"render: {exc}\n")
    out.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    manifest = json.loads(files["manifest.json"])
    print(f"Rendered {len(files)} files to {out}; no database was modified.")
    for gap in manifest["gaps"]:
        print(f"  gap: {gap}")


if __name__ == "__main__":
    main()
