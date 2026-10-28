"""Generate seed files and their load mapping for any product, from its build context.

A product being designed has no data yet, and a build is only shown to work once rows are in
it. This writes one CSV per Domain entity and the `load.toml` that `load.py` reads, so any
specification can be deployed, loaded and validated on any binding without a hand-written
data set. The rows are structurally valid, not realistic: every value has its attribute's
logical type, an `Enum` takes one of its members, a required attribute is always present, a
reference names a row of its target, each natural key is unique, and each entity has the
rows its `Volume:` gives at first load. Business rules beyond the types (an end after a
start, a score in range) are not known to the generator and do not hold.

The output is deterministic for a seed. Columns take the attributes' own names, so the mapping
needs no column renames; a keymap-allocated entity's natural key is a column named as on its
keymap.

usage: seed.py <build dir> --output DIR [--max-rows N] [--seed N]
"""
import argparse
import csv
import json
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path

START, END = date(2020, 1, 1), date(2026, 6, 30)
SEEDED_KINDS = ("History", "Reference", "Relationship", "Record")


def snake(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower()


def code(entity):
    """A short prefix for an entity's generated keys: its capitals, ConfigurationItem -> CI."""
    return "".join(c for c in entity if c.isupper()) or entity[:3].upper()


class Generator:
    def __init__(self, context, rng, max_rows):
        self.ctx, self.rng, self.max_rows = context, rng, max_rows
        self.entities = {x["name"]: x for x in context["entities"]}
        self.keys = {}  # entity -> generated natural key values, in row order

    def seeded(self):
        """The Domain entities the product loads, each after the entities it references."""
        chosen = [x for x in self.entities.values() if x["module"] == "domain" and x["kind"] in SEEDED_KINDS]
        names, ordered = {x["name"] for x in chosen}, []
        while chosen:
            ready = [x for x in chosen if all(t in {o["name"] for o in ordered} or t == x["name"] or t not in names
                                              for a in x["attributes"] for t in a["references"])]
            if not ready:
                raise ValueError("the product's references form a cycle between entities")
            ordered += ready
            chosen = [x for x in chosen if x not in ready]
        return ordered

    def key_column(self, x):
        """The source column holding an entity's natural key, or None if it has no single one."""
        identity = x["identity"]
        if identity.get("keymap"):
            return self.entities[identity["keymap"]]["identity"]["natural"][0]
        natural = identity["natural"]
        if len(natural) == 1 and not next(a for a in x["attributes"] if a["name"] == natural[0])["references"]:
            return natural[0]
        return None

    def value(self, x, a, n, row):
        logical = re.split(r"[{(\[]", a["type"])[0]
        rng = self.rng
        if logical == "Enum":
            return rng.choice(a["members"])
        if logical in ("NaturalKey", "Code"):
            return f"{code(x['name'])}-{n:05d}"
        if logical == "Flag":
            return rng.choice(["true", "false"])
        if logical == "Integer":
            return str(rng.randint(0, 100))
        if logical == "Decimal":
            precision, scale = (int(p) for p in re.findall(r"\d+", a["type"])[:2])
            return f"{rng.uniform(0, min(10 ** (precision - scale - 1), 100000)):.{scale}f}"
        if logical == "Date":
            return (START + timedelta(days=rng.randint(0, (END - START).days))).isoformat()
        if logical == "Timestamp":
            day = START + timedelta(days=rng.randint(0, (END - START).days))
            return datetime.combine(day, datetime.min.time()).replace(hour=rng.randint(0, 23), minute=rng.randint(0, 59)).isoformat()
        if logical == "Json":
            return "{}"
        words = a["name"].replace("_", " ")
        if logical == "ShortText":
            return f"{words} {n}"
        return f"Sample {words} for {x['name']} {n}."

    def rows(self, x):
        attributes = [a for a in x["attributes"]
                      if a["type"] != "Identifier" and not a["derive"] and not a["type"].startswith("Vector")
                      and not set(a["flags"]) & {"current-flag", "deleted-flag"}]
        discriminators = {a["discriminator"]: a for a in attributes if a["discriminator"]}
        key = self.key_column(x)
        wanted = int((x.get("volume") or {}).get("initial") or 20)
        wanted = max(1, min(wanted, self.max_rows))
        natural = [n for n in x["identity"]["natural"] if n != key]
        rows, seen = [], set()
        attempts = 0
        while len(rows) < wanted and attempts < wanted * 20:
            attempts += 1
            n = len(rows) + 1
            row = {}
            if key:
                row[key] = f"{code(x['name'])}-{n:05d}"
            for a in attributes:
                if a["name"] in discriminators:
                    continue
                if a["references"]:
                    pool = [(t, k) for t in a["references"] for k in
                            (self.keys.get(t, []) if t != x["name"] else [r[key] for r in rows] if key else [])]
                    if not pool or (not a["required"] and self.rng.random() < 0.2):
                        continue
                    target, value = self.rng.choice(pool)
                    row[a["name"]] = value
                    if a["discriminator"]:
                        row[a["discriminator"]] = target.upper()
                elif a["required"] or a["name"] in natural or self.rng.random() >= 0.15:
                    row[a["name"]] = self.value(x, a, n, row)
            if "valid_from_dts" in x["column_names"]:
                row["valid_from"] = (START + timedelta(days=self.rng.randint(0, (END - START).days))).isoformat()
            identity = tuple(row.get(c) for c in natural)
            if natural and identity in seen:
                continue
            seen.add(identity)
            rows.append(row)
        if key:
            self.keys[x["name"]] = [r[key] for r in rows]
        columns = ([key] if key else []) + [a["name"] for a in attributes if a["name"] != key] \
            + (["valid_from"] if "valid_from_dts" in x["column_names"] else [])
        return columns, rows


def generate(context, output, max_rows=500, seed=0):
    """Write the seed files and load.toml under `output`; returns rows written per entity."""
    gen = Generator(context, random.Random(seed), max_rows)
    data = output / "data"
    data.mkdir(parents=True, exist_ok=True)
    mapping = ["# Seed load generated by tooling/bindings/seed.py: structurally valid rows, not realistic ones.",
               "# Read by tooling/bindings/load.py, in order. Paths are relative to this file.", ""]
    counts = {}
    for x in gen.seeded():
        columns, rows = gen.rows(x)
        name = f"{snake(x['name'])}.csv"
        with (data / name).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        counts[x["name"]] = len(rows)
        mapping += ["[[entity]]", f'name = "{x["name"]}"', f'file = "data/{name}"']
        key = gen.key_column(x)
        if key:
            mapping.append(f'key = "{key}"')
        if "valid_from" in columns:
            mapping.append('valid_from = "valid_from"')
        mapping.append("")
    (output / "load.toml").write_text("\n".join(mapping), encoding="utf-8", newline="\n")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("build", type=Path, help="a render.py output directory, for any target")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=500, help="cap on rows per entity; default 500")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    context = json.loads((args.build / "context.json").read_text(encoding="utf-8"))
    for name, n in generate(context, args.output, args.max_rows, args.seed).items():
        print(f"{name}: {n} rows")


if __name__ == "__main__":
    main()
