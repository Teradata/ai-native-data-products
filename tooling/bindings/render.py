"""Generate a platform binding's SQL from a design specification and an organisation's configuration.

The build context is resolved first (tooling/build/build_context.py), from the specification,
the configuration and the binding's own declarations. This module then asks the platform's
dialect (implementation/{platform}/dialect.py) for each deployment phase, the deploy script
and each validation check, from that context alone, and writes them with a manifest. SQL lives
in the dialects; this module orders and writes what they return, and never connects to a
database. The same inputs give the same files, byte for byte.

Stdlib only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tooling" / "build"))

import build_context  # noqa: E402
from binding import load_binding  # noqa: E402
from dialect import dialect_class  # noqa: E402

RESERVED = ("config", "design", "implementation", "examples", "roles", "tooling")


class RenderError(Exception):
    """The inputs do not resolve, or the binding cannot render them."""


def dialect_for(context):
    """The dialect of the platform a context names, over that context: for callers that render
    what a product's own pipelines run, such as key allocation and maintenance."""
    binding, findings = load_binding(context["platform"]["name"])
    if findings:
        raise RenderError("; ".join(str(f) for f in findings))
    return dialect_class(binding.platform)(binding, context)


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
    for r in context["relationships"]:
        if r["unpaired_target_columns"]:
            out.append(f"relationships[{r['name']}]: the target identity has {len(r['unpaired_target_columns']) + 1} "
                       f"columns and the reference carries one; only the first is paired")
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
    manifest. A phase that renders nothing for this composition writes no file."""
    dialect = dialect_for(context)
    binding = dialect.binding

    files, phases = {}, []
    for i, phase in enumerate(dialect.PHASES):
        sql = _tidy(dialect.phase(phase))
        if sql:
            name = f"{i:02d}-{phase}.sql"
            files[name] = sql + "\n"
            phases.append({"file": name, "sql": sql})
    files["deploy.sql"] = _tidy(dialect.deploy(phases)) + "\n"

    checks, counters = [], {}

    def add(name, scope_kind, scope_id, module, sql):
        counters[name] = counters.get(name, 0) + 1
        checks.append({"test_id": f"{context['product']['code']}-{name.upper()}-{counters[name]:03d}",
                       "check": name, "scope_kind": scope_kind, "scope_id": scope_id,
                       "module": module, "category": "STRUCTURAL", "severity": "ERROR",
                       "sql": sql.rstrip(";").rstrip()})

    def check(scope, name, **item):
        return _tidy(dialect.check(scope, name, **item))

    for scope, name in dialect.CHECKS:
        if scope == "entity":
            for x in persisted(context):
                add(name, "ENTITY", x["name"], x["module"], check(scope, name, entity=x))
        elif scope == "relationship":
            for r in context["relationships"]:
                add(name, "ENTITY", r["source"], r["source_module"], check(scope, name, relationship=r))
        elif scope == "module" and name in context["modules"]:
            add("module", "MODULE", name, name, check(scope, name, module=name))
        elif scope == "contract" and "semantic" in context["modules"]:
            add(f"contract-{name}", "MODULE", "semantic", "semantic", check(scope, name))
        elif scope == "product":
            add(name, "PRODUCT", context["product"]["code"], None, check(scope, name))

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


def render_product(spec, configuration, environment_name=None, version=None):
    """Resolve the inputs into a build context and render the binding its target names."""
    context, findings = build_context.resolve(Path(spec), configuration, environment_name,
                                              version=version)
    if findings:
        raise RenderError("\n".join(str(f) for f in findings))
    return render_context(context)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="the design specification")
    parser.add_argument("implementation", type=Path, help="the organisation's implementation configuration")
    parser.add_argument("--target", required=True, help="the deployment target under [targets]; it names the platform")
    parser.add_argument("--design", type=Path, help="the design configuration; default: the sibling design file")
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
        files = render_product(args.spec, build_context.Configuration(args.implementation, args.target, args.design),
                               args.environment, args.version)
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
