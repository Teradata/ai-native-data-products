"""Seed data and load mappings: tooling/bindings/seed.py and the examples' load.toml files.

Neither needs a database. The generator is held to what it promises of any specification:
every entity the product loads gets a file, every required attribute is present, every
natural key is unique, every reference names a row its target was given, and the mapping it
writes names those files and keys. Each example's hand-written mapping is held to its
specification and its source files, so a renamed attribute or column fails here rather than
halfway through a load. Loading itself is exercised on the engines (docs/example-runs).

Run:
    python -m unittest discover -s tooling/validation/tests
"""
import csv
import json
import sys
import tempfile
import tomllib
import unittest
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tooling" / "build"))
sys.path.insert(0, str(REPO_ROOT / "tooling" / "bindings"))

from build_context import resolve  # noqa: E402
from org_profile import Configuration  # noqa: E402
import seed  # noqa: E402

CONFIG = Configuration(REPO_ROOT / "config" / "implementation.example.toml", "duckdb",
                       REPO_ROOT / "config" / "design.example.toml")
EXAMPLES = sorted(p for p in (REPO_ROOT / "examples").iterdir() if (p / "load.toml").exists())
SPECS = [p / "design-output" / "design_specification.md" for p in EXAMPLES] + \
    [REPO_ROOT / "tooling" / "evals" / "reference" / "customer-orders.md"]


@lru_cache(maxsize=None)
def context(spec):
    ctx, findings = resolve(Path(spec), CONFIG)
    assert not findings, [str(f) for f in findings]
    return json.dumps(ctx)


def entities(ctx):
    return {x["name"]: x for x in ctx["entities"] + ctx["relations"]}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Generated(unittest.TestCase):
    """seed.py over every specification the repository holds."""

    def test_every_specification_yields_loadable_rows(self):
        for spec in SPECS:
            with self.subTest(spec=spec.relative_to(REPO_ROOT).as_posix()), tempfile.TemporaryDirectory() as tmp:
                ctx = json.loads(context(str(spec)))
                out = Path(tmp)
                counts = seed.generate(ctx, out, max_rows=200, seed=7)
                mapping = tomllib.loads((out / "load.toml").read_text(encoding="utf-8"))["entity"]
                by_name = entities(ctx)
                self.assertEqual([m["name"] for m in mapping], list(counts))
                keys = {}
                for m in mapping:
                    x, rows = by_name[m["name"]], read(out / m["file"])
                    self.assertEqual(len(rows), counts[m["name"]])
                    self.assertGreater(len(rows), 0, m["name"])
                    if "key" in m:
                        values = [r[m["key"]] for r in rows]
                        self.assertEqual(len(values), len(set(values)), f"{m['name']}: duplicate natural keys")
                        keys[m["name"]] = set(values)
                    natural = [n for n in x["identity"]["natural"] if n != m.get("key")]
                    if natural:
                        combos = [tuple(r[n] for n in natural) for r in rows]
                        self.assertEqual(len(combos), len(set(combos)), f"{m['name']}: duplicate identities")
                    for a in x["attributes"]:
                        if a["required"] and not a["references"] and a["type"] != "Identifier" \
                                and not a["derive"] and not set(a["flags"]) & {"current-flag", "deleted-flag"}:
                            self.assertTrue(all(r.get(a["name"]) for r in rows), f"{m['name']}.{a['name']} missing")
                        for r in rows:
                            if a["references"] and r.get(a["name"]):
                                self.assertTrue(any(r[a["name"]] in keys.get(t, ()) for t in a["references"]),
                                                f"{m['name']}.{a['name']} = {r[a['name']]} names no generated row")

    def test_the_same_seed_writes_the_same_files(self):
        ctx = json.loads(context(str(SPECS[0])))
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            seed.generate(ctx, Path(a), seed=3)
            seed.generate(ctx, Path(b), seed=3)
            for path in sorted(Path(a).rglob("*.*")):
                self.assertEqual(path.read_bytes(), (Path(b) / path.relative_to(a)).read_bytes(), path.name)


class ExampleMappings(unittest.TestCase):
    """Each example's load.toml against its specification and its source files."""

    def test_examples_carry_a_mapping(self):
        self.assertGreaterEqual(len(EXAMPLES), 3)

    def test_every_mapping_fits_its_specification_and_files(self):
        for example in EXAMPLES:
            with self.subTest(example=example.name):
                ctx = json.loads(context(str(example / "design-output" / "design_specification.md")))
                by_name = entities(ctx)
                loaded = []
                for m in tomllib.loads((example / "load.toml").read_text(encoding="utf-8"))["entity"]:
                    self.assertIn(m["name"], by_name)
                    x = by_name[m["name"]]
                    path = example / m["file"]
                    self.assertTrue(path.is_file(), m["file"])
                    header = set(read(path)[0])
                    attributes = {a["name"]: a for a in x["attributes"]}
                    for attribute, column in m.get("columns", {}).items():
                        self.assertIn(attribute, attributes, f"{m['name']} has no attribute {attribute}")
                        self.assertIn(column, header, f"{m['file']} has no column {column}")
                    if x["identity"].get("keymap"):
                        self.assertIn("key", m, f"{m['name']} allocates through a keymap: name its key")
                    if "key" in m:
                        self.assertIn(m["key"], header)
                    rule = m.get("valid_from")
                    if rule and "." in rule and rule.split(".")[0] in attributes:
                        pass  # borrowed from a referenced row
                    elif rule:
                        self.assertIn(rule, header, f"{m['name']}: valid_from column {rule}")
                    for a in attributes.values():
                        for target in a["references"]:
                            if target != m["name"] and by_name[target]["module"] == "domain":
                                self.assertIn(target, loaded, f"{m['name']} loads before {target}, which it references")
                    loaded.append(m["name"])


if __name__ == "__main__":
    unittest.main()
