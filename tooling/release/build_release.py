"""Generate and check the release bundle: release/vX.Y.Z/*.json.

The bundle describes the consumer contract of a deployed AI-Native Data Product for the
version in the root VERSION file. It is generated from repository sources (entity
declarations, the Postgres reference rendering, binding and example directories) and
committed, so a tag checkout carries the contract. It is not a module: it has no design
document, no binding directory and no deployed container.

    python tooling/release/build_release.py           # write release/vX.Y.Z/
    python tooling/release/build_release.py --check   # exit 1 when committed files are stale
"""
import argparse
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tooling.bindings.render import ORDER, PATTERNS, render_product  # noqa: E402

REFERENCE = REPO / "examples/it-service-desk-data-product"
REFERENCE_PLATFORM = "postgres"
CHECK_FILE_NAMES = ("conformance-queries.sql", "conformance.sql", "comment-coverage.sql",
                    "validation.sql", "validation.sql.j2", "checks.py")


def read_version(repo=REPO):
    """Return the standard version from VERSION, which must be MAJOR.MINOR.PATCH."""
    version = (repo / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"VERSION must be MAJOR.MINOR.PATCH, not {version!r}")
    return version


def _reference_sql(repo):
    """Render the reference composition; return its deploy SQL and check manifest."""
    context = json.loads((repo / "examples/it-service-desk-data-product/bindings/context.json").read_text(encoding="utf-8"))
    context.update(json.loads((repo / f"examples/it-service-desk-data-product/{REFERENCE_PLATFORM}/placement.json").read_text(encoding="utf-8")))
    files = render_product(context, REFERENCE_PLATFORM)
    return files["deploy.sql"], json.loads(files["manifest.json"]), context["containers"]["access"]


def _standard_entities(repo):
    """Standard-owned metadata entities per module, from the declarations the bindings deploy."""
    modules = {}
    for module in ORDER:
        path = repo / "implementation" / REFERENCE_PLATFORM / "modules" / module / "entities.json"
        if not path.exists():
            modules[module] = []
            continue
        modules[module] = [
            {"name": e["name"], "key": e["key"], "profile": e["profile"], "description": e["description"],
             "columns": [{"name": c["name"], "type": c["type"], "nullable": c.get("nullable", False), "comment": c["comment"]}
                         for c in e["columns"]]}
            for e in json.loads(path.read_text(encoding="utf-8"))]
    return modules


def _access_surface(sql, access_schema, standard_names):
    """Standard-owned access objects and their columns, read from the rendered comments.

    Every view and view column carries a comment (the comment-coverage check), so the
    COMMENT statements enumerate the surface exactly.
    """
    schema = re.escape(access_schema)
    views = re.findall(rf'COMMENT ON VIEW "{schema}"\."(\w+)"', sql)
    columns = {}
    for view, column in re.findall(rf'COMMENT ON COLUMN "{schema}"\."(\w+)"\."?(\w+)"?', sql):
        columns.setdefault(view, []).append(column)
    owned = [v for v in dict.fromkeys(views) if not v.startswith("v_") or v[2:] in standard_names]
    return [{"name": v, "columns": columns.get(v, [])} for v in owned]


def _discovery_roles(sql):
    """Discovery roles in the order an agent reads them, from the registration rows."""
    rows = re.findall(r"data_product_orientation\" VALUES\n \('(\w+)','[^']+','\w+\.(\w+)',(\d+),", sql)
    return [{"role": r, "object": o, "discovery_order": int(n)} for r, o, n in sorted(rows, key=lambda x: int(x[2]))]


def build_contract(repo=REPO):
    """contract.json: what an agent reading a deployed product can rely on."""
    version = read_version(repo)
    sql, _, access_schema = _reference_sql(repo)
    modules = _standard_entities(repo)
    names = {e["name"] for entities in modules.values() for e in entities}
    return {"standard_version": version, "modules": list(ORDER), "patterns": list(PATTERNS),
            "metadata_entities": modules,
            "access_surface": _access_surface(sql, access_schema, names),
            "discovery_roles": _discovery_roles(sql)}


def _platform_dirs(repo):
    return sorted(p for p in (repo / "implementation").iterdir() if p.is_dir() and (p / "README.md").exists())


def build_bindings(repo=REPO):
    """bindings.json: per platform, what is present and whether it declares the version."""
    result = []
    for platform in _platform_dirs(repo):
        declares = any("standard_declaration" in f.read_text(encoding="utf-8", errors="ignore")
                       for f in platform.rglob("*") if f.is_file() and f.suffix in (".json", ".j2", ".sql", ".py")
                       and "__pycache__" not in f.parts)
        result.append({
            "platform": platform.name,
            "modules": sorted(p.name for p in (platform / "modules").iterdir() if p.is_dir()) if (platform / "modules").exists() else [],
            "patterns": sorted(p.name for p in (platform / "patterns").iterdir() if p.is_dir()) if (platform / "patterns").exists() else [],
            "conformance_documents": [n for n in ("CONFORMANCE.md", "PLATFORM_PROFILE.md") if (platform / n).exists()],
            "declares_standard_version": declares})
    return {"standard_version": read_version(repo), "bindings": result}


def build_examples(repo=REPO):
    """examples.json: each example, the platforms it covers and its README."""
    platforms = [p.name for p in _platform_dirs(repo)]
    result = []
    for example in sorted(p for p in (repo / "examples").iterdir() if p.is_dir() and (p / "README.md").exists()):
        covered = [p for p in platforms if (example / p).is_dir() or example.name.endswith("-" + p)]
        result.append({"example": example.name, "platforms": covered, "readme": f"examples/{example.name}/README.md"})
    return {"standard_version": read_version(repo), "examples": result}


def _check_kind(check):
    """Product-neutral name for a rendered check, so the index does not name the reference product."""
    tid, scope = check["test_id"], check["scope_kind"]
    if scope == "ENTITY":
        return "entity:" + tid.rsplit(":", 1)[1]
    if scope == "PRODUCT":
        return tid.rsplit(":", 1)[1]
    return tid if tid.endswith(":coverage") else "relationship"


def build_checks(repo=REPO):
    """checks.json: the checks a conforming deployment runs, plus each platform's check files."""
    _, manifest, _ = _reference_sql(repo)
    rendered = sorted({(c["scope_kind"], _check_kind(c)) for c in manifest["checks"]})
    files = {p.name: sorted(str(f.relative_to(repo)).replace("\\", "/") for f in p.rglob("*")
                            if f.is_file() and f.name in CHECK_FILE_NAMES and "__pycache__" not in f.parts)
             for p in _platform_dirs(repo)}
    return {"standard_version": read_version(repo),
            "rendered_checks": {REFERENCE_PLATFORM: [{"scope_kind": s, "check": k} for s, k in rendered]},
            "check_files": files}


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
