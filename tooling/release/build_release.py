"""Generate and check the release bundle: release/vX.Y.Z/*.json.

The bundle describes the consumer contract of a deployed AI-Native Data Product for the
version in the root VERSION file. It is generated from the repository: the build context the
resolver produces for the reference product, the bindings' declarations, and the example and
binding directories. It is committed, so a tag checkout carries the contract. It is not a
module: it has no design document, no binding directory and no deployed container.

    python tooling/release/build_release.py           # write release/vX.Y.Z/
    python tooling/release/build_release.py --check   # exit 1 when committed files are stale
"""
import argparse
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tooling" / "build"))
sys.path.insert(0, str(REPO / "tooling" / "bindings"))

import build_context  # noqa: E402
from binding import load_binding  # noqa: E402
from build_context import STANDARD_PATTERNS  # noqa: E402
from org_profile import _snake  # noqa: E402
import render  # noqa: E402

REFERENCE = REPO / "examples" / "it-service-desk-data-product"
REFERENCE_SPEC = REFERENCE / "design-output" / "design_specification.md"
CONTRACT_PLATFORM = "postgres"
MODULES = ("memory", "semantic", "domain", "observability", "search", "prediction")

# The placement-independent identities every consumer follows (design/modules/semantic.md, INV-SEMANTIC-016).
IDENTITY_GRAMMAR = [
    {"kind": "entity", "form": "module.entity", "pattern": "^[a-z][a-z0-9_]*[.][a-z][a-z0-9_]*$", "example": "domain.ticket"},
    {"kind": "entity surface", "form": "module.entity:surface (base, governed, current or history)",
     "pattern": "^[a-z][a-z0-9_]*[.][a-z][a-z0-9_]*:(base|governed|current|history)$", "example": "domain.ticket:current"},
    {"kind": "module-owned object", "form": "module:object (composite is reserved)",
     "pattern": "^(?!composite:)[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$", "example": "observability:trust_map"},
    {"kind": "composite access object", "form": "composite:name", "pattern": "^composite:[a-z][a-z0-9_]*$",
     "example": "composite:ticket_enriched"}]


def read_version(repo=REPO):
    """Return the standard version from VERSION, which must be MAJOR.MINOR.PATCH."""
    version = (repo / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"VERSION must be MAJOR.MINOR.PATCH, not {version!r}")
    return version


def _platforms(repo=REPO):
    return sorted(p.name for p in (repo / "implementation").iterdir() if p.is_dir() and (p / "README.md").exists())


def _build(platform, repo=REPO):
    """Resolve and render the reference product on one platform: its context and rendered files."""
    context, findings = build_context.resolve(REFERENCE_SPEC, REFERENCE / "profiles" / f"{platform}.md")
    if findings:
        raise ValueError(f"the reference product does not resolve on {platform}: " + "; ".join(map(str, findings)))
    return context, render.render_context(context)


def _view_columns_from_comments(sql):
    """Column names per view, from the COMMENT statements. Every view column carries one."""
    columns = {}
    for schema, view, quoted, bare in re.findall(r'COMMENT ON COLUMN "([^"]+)"\."([^"]+)"\.(?:"([^"]+)"|(\w+))', sql):
        columns.setdefault((schema, view), []).append(quoted or bare)
    return columns


def build_contract(repo=REPO):
    """contract.json: what an agent reading a deployed product can rely on."""
    context, files = _build(CONTRACT_PLATFORM, repo)
    sql = files["deploy.sql"]
    comment_columns = _view_columns_from_comments(sql)
    metadata = {m: [] for m in MODULES}
    surface = []
    for x in context["relations"]:
        view = x["objects"].get("consumer_view")
        if x["relation"] == "table" and x.get("defined"):
            metadata[x["module"]].append({
                "name": x["name"], "identity": x["logical_id"], "profile": x["profile"],
                "keys": [{"role": k["role"], "name": k["name"], "columns": k["columns"]} for k in x["key_defs"]],
                "columns": [{"name": a["name"], "type": a["type"], "required": bool(a["required"])} for a in x["attributes"]]
                           + [{"name": t["name"], "type": t["type"], "required": True} for t in x["temporal"]]})
        if view:
            if x["relation"] == "table":
                identity, columns = x["logical_id"] + ":current", [c["name"] for c in x["view_columns"]]
            else:
                identity = f"{x['module']}:{_snake(x['name'])}"
                columns = comment_columns.get((view["container"], view["name"]), [])
            surface.append({"relation": x["name"], "identity": identity, "columns": columns})
    resources = sorted(context["orientation"]["resources"], key=lambda r: r["order"])
    return {"standard_version": read_version(repo), "modules": list(MODULES), "patterns": list(STANDARD_PATTERNS),
            "identity_grammar": IDENTITY_GRAMMAR,
            "metadata_entities": {m: sorted(items, key=lambda i: i["name"]) for m, items in metadata.items()},
            "access_surface": sorted(surface, key=lambda s: s["identity"]),
            "discovery_roles": [{"role": r["role"], "relation": r["relation"], "required": r["required"],
                                 "discovery_order": r["order"]} for r in resources]}


def build_bindings(repo=REPO):
    """bindings.json: per platform, what is present and whether it declares the version."""
    result = []
    for platform in _platforms(repo):
        base = repo / "implementation" / platform
        binding, _ = load_binding(platform)
        declares = any("StandardDeclaration" in f.read_text(encoding="utf-8", errors="ignore")
                       for f in base.rglob("*.j2"))
        result.append({
            "platform": platform,
            "modules": sorted(p.name for p in (base / "modules").iterdir() if p.is_dir()) if (base / "modules").exists() else [],
            "patterns": sorted(p.name for p in (base / "patterns").iterdir() if p.is_dir()) if (base / "patterns").exists() else [],
            "conformance_documents": [n for n in ("CONFORMANCE.md", "PLATFORM_PROFILE.md") if (base / n).exists()],
            "declared_checks": sorted(binding.checks),
            "declared_gaps": sorted(binding.gaps),
            "declares_standard_version": declares})
    return {"standard_version": read_version(repo), "bindings": result}


def build_examples(repo=REPO):
    """examples.json: each example, the platforms it covers and its README."""
    platforms = _platforms(repo)
    result = []
    for example in sorted(p for p in (repo / "examples").iterdir() if p.is_dir() and (p / "README.md").exists()):
        covered = [p for p in platforms if (example / p).is_dir() or example.name.endswith("-" + p)
                   or (example / "profiles" / f"{p}.md").exists()]
        result.append({"example": example.name, "platforms": covered, "readme": f"examples/{example.name}/README.md"})
    return {"standard_version": read_version(repo), "examples": result}


def build_checks(repo=REPO):
    """checks.json: the checks a conforming deployment of the reference product runs, per platform."""
    rendered = {}
    for platform in _platforms(repo):
        if not (REFERENCE / "profiles" / f"{platform}.md").exists():
            continue
        _, files = _build(platform, repo)
        manifest = json.loads(files["manifest.json"])
        rendered[platform] = sorted({(c["scope_kind"], c["check"]) for c in manifest["checks"]})
    return {"standard_version": read_version(repo),
            "rendered_checks": {p: [{"scope_kind": s, "check": c} for s, c in items] for p, items in rendered.items()}}


def render_bundle(repo=REPO):
    """Return {relative path: text} for every generated bundle file."""
    directory = f"release/v{read_version(repo)}"
    builders = {"contract.json": build_contract, "bindings.json": build_bindings,
                "examples.json": build_examples, "checks.json": build_checks}
    return {f"{directory}/{name}": json.dumps(build(repo), indent=2, ensure_ascii=False) + "\n"
            for name, build in builders.items()}


def authored_problems(repo=REPO):
    """Authored documents the current version must have; return a list of problems."""
    version = read_version(repo)
    problems = []
    if not (repo / f"release/migrations/v{version}.md").exists():
        problems.append(f"release/migrations/v{version}.md is missing")
    compat = repo / "release/COMPATIBILITY.md"
    if not compat.exists() or not re.search(rf"^\|\s*{re.escape(version)}\s*\|", compat.read_text(encoding="utf-8"), re.M):
        problems.append(f"release/COMPATIBILITY.md has no row for {version}")
    return problems


def stale_files(repo=REPO):
    """Bundle files whose committed content differs from what the sources generate."""
    stale = []
    for relative, text in render_bundle(repo).items():
        path = repo / relative
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            stale.append(relative)
    return stale


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 when the committed bundle is stale or incomplete")
    args = parser.parse_args()
    if args.check:
        problems = [f"stale: {f}" for f in stale_files()] + authored_problems()
        print("\n".join(problems) if problems else "Release bundle is current.")
        raise SystemExit(bool(problems))
    for relative, text in render_bundle().items():
        path = REPO / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", relative)


if __name__ == "__main__":
    main()
