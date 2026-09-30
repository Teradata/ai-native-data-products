"""A metadata-driven consumer; initial knowledge is only product + bootstrap table.

Resource identities are read verbatim. Execute authored cookbook SQL only in a
trusted synthetic file, read-only; a production host must authorize query content.
"""
import argparse
import re


def identity(value):
    if not re.fullmatch(r"[a-z_][a-z_0-9]*\.[a-z_][a-z_0-9]*", value):
        raise ValueError("Invalid registered object identity")
    return ".".join('"'+part+'"' for part in value.split("."))


def discover(con, product="customer360"):
    registry = con.execute("SELECT * FROM semantic.data_product_registry WHERE product_id=?", [product])
    record = registry.fetchone()
    if record is None:
        raise ValueError("Unknown product")
    product_record = dict(zip([c[0] for c in registry.description], record))
    # The binding bootstrap convention includes this ordered orientation relation.
    resources = con.execute("SELECT resource_role,object_identity FROM semantic.data_product_orientation WHERE product_id=? ORDER BY discovery_order", [product]).fetchall()
    data = {}
    for role, name in resources:
        cursor = con.execute("SELECT * FROM "+identity(name))
        names = [c[0] for c in cursor.description]
        data[role] = [dict(zip(names, r)) for r in cursor.fetchall()]
    objects = data["OBJECT_CATALOGUE"]
    approved = product_record["approved_entrypoint"]
    access = next(a for a in objects if a["object_identity"] == approved and a["is_agent_consumable"])
    historical_entities = {e["entity_name"] for e in data["ENTITY_CATALOGUE"] if e["temporal_pattern"]=="SCD2_HISTORY"}
    paths = [p for p in data["RELATIONSHIP_PATHS"] if p["source_entity"] == access["represents_entity"]
             and p["hops"]==2 and p["target_entity"] in historical_entities]
    if not paths:
        raise ValueError("No two-hop relationship discovered")
    # Select a path by registered endpoint identity, without physical names in code.
    path = sorted(paths, key=lambda p: p["target_entity"])[0]
    by_entity = {a["represents_entity"]: a["object_identity"] for a in objects if a["is_agent_consumable"] and a["access_role"]=="PASSTHROUGH"}
    from_objects = [by_entity[e] for e in path["visited"]]
    # Predicates are authored product metadata: trusted just as cookbook SQL is.
    sql = "SELECT count(*) AS related_rows FROM " + ", ".join(identity(o) for o in from_objects) + " WHERE " + path["join_path"]
    result = con.execute(sql).fetchall()
    used = {e.split(".")[0] for e in path["visited"]}
    confidence = []
    for module in sorted(used):
        candidates = [t for t in data["TRUST_MAP"] if t["scope_kind"]=="MODULE" and t["scope_id"]==module]
        confidence.extend(candidates or [dict(scope_id=module, confidence="unknown",
                                             recommended_action="No area evidence; validate and disclose this gap.")])
    return dict(product=product, modules=data["MODULE_MAP"], path=path, sql=sql, result=result,
                confidence=confidence, decisions=data["DESIGN_DECISIONS"], fields=data["COLUMN_CATALOGUE"])


if __name__ == "__main__":
    import duckdb
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("--product", default="customer360")
    args = parser.parse_args()
    with duckdb.connect(args.database, read_only=True) as con:
        found = discover(con, args.product)
    print("Modules:", ", ".join(m["module_name"] for m in found["modules"]))
    print("Discovered query:", found["sql"])
    print("Result:", found["result"])
    print("Confidence:", [(t["scope_id"],t["confidence"],t["recommended_action"]) for t in found["confidence"]])
