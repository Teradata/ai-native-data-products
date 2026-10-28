"""Load seed files into a rendered, deployed product, on any binding.

A product's own pipelines load its data; this loads an example's seed files, so an agent or a
test can stand a product up without writing a loader each time. What goes where is declared in
a load mapping (`load.toml`, beside the example's data): one `[[entity]]` per source file,
naming the specification entity it fills, the source column holding its natural key, and the
source column behind any attribute whose name differs. Everything else comes from the build:
names and placement from the rendered build context, key allocation from the binding's dialect,
and how a flag, an open interval end or a vector travels as a parameter from the engine.

    [[entity]]
    name = "Ticket"                 # a specification entity
    file = "data/tickets.csv"       # relative to the mapping
    key = "ticket_id"               # source column of its natural key (keymap or inline)
    valid_from = "created_at"       # start of validity: a source column, or `<reference>.<column>`
    versions = false                # true: one row per version, each closed by the next
    [entity.columns]                # attribute = source column, where the names differ
    opened_dts = "created_at"

A reference attribute's source value is its target's natural key, resolved to the target's
identifier as allocated; load a target before what refers to it. A row referring to a row of
its own entity waits until that row is in. Validity is backfilled: a version is recorded as
known from the moment it became valid, so point-in-time reads before the load see it.

Embeddings are the product's pipeline too. `--embeddings placeholder` writes deterministic
feature-hashing vectors, recorded under the model name `feature-hashing placeholder` so a
similarity search for the declared model never mistakes them for real ones; `--embedder
module:function` writes vectors from a function taking a list of texts and the declared model.

usage: load.py <build dir> <load.toml> [--database FILE] [--deploy] [--embeddings MODE]
PostgreSQL reads POSTGRES_DSN and Teradata TERADATA_DSN, as validate.py does.
"""
import argparse
import csv
import hashlib
import importlib
import json
import math
import re
import sys
import tomllib
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tooling" / "build"))

from binding import load_binding  # noqa: E402
from engines import engine, statements  # noqa: E402
from render import dialect_for  # noqa: E402

PLACEHOLDER_MODEL = "feature-hashing placeholder"
EPOCH = "2000-01-01"


class LoadError(Exception):
    """The mapping does not fit the product, or a source row cannot be loaded."""


def instant(raw):
    """A source date or timestamp as a UTC instant; a date is its midnight."""
    text = raw if "T" in raw or " " in raw else raw + "T00:00:00"
    value = datetime.fromisoformat(text)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class Loader:
    def __init__(self, con, context):
        self.con, self.ctx = con, context
        self.engine = engine(context["platform"]["name"])
        self.binding = load_binding(context["platform"]["name"])[0]
        self.dialect = dialect_for(context)
        self.keys = defaultdict(dict)       # entity -> natural value -> identifier
        self.sources = defaultdict(dict)    # entity -> natural value -> source row
        self.targets = {r["name"]: r["target"] for r in context["relationships"] if r["join_kind"] == "bare"}

    # ---- the build's objects ---------------------------------------------------------
    def named(self, name):
        found = [x for x in self.ctx["entities"] + self.ctx["relations"] if x["name"] == name]
        if not found:
            raise LoadError(f"'{name}' is not an entity of this product")
        return found[0]

    def table(self, x):
        t = x["objects"]["table"]
        return self.binding.qualified(t["container"], t["name"])

    def view(self, x):
        v = x["objects"]["consumer_view"]
        return self.binding.qualified(v["container"], v["name"])

    def query(self, sql):
        return self.con.execute(sql).fetchall()

    def insert(self, x, rows):
        if not rows:
            return
        cn = x["column_names"]
        names = list(dict.fromkeys(k for row in rows for k in row))
        sql = (f"INSERT INTO {self.table(x)} ({', '.join(self.binding.ident(cn[k]) for k in names)}) "
               f"VALUES ({', '.join(self.engine.marker for _ in names)})")
        target = self.con if hasattr(self.con, "executemany") else self.con.cursor()
        target.executemany(sql, [[row.get(k) for k in names] for row in rows])

    # ---- values ----------------------------------------------------------------------
    def value(self, raw, col):
        """A source cell as the parameter its logical type binds to."""
        if raw is None or raw == "":
            return None
        logical = re.split(r"[{(\[]", col["type"])[0]
        if logical == "Flag":
            return self.engine.flag(raw.strip().lower() in ("true", "1", "yes", "y"))
        if logical == "Integer":
            return int(raw)
        if logical == "Decimal":
            return Decimal(raw)
        if logical == "Timestamp":
            return instant(raw)
        if logical == "Date":
            return date.fromisoformat(raw[:10])
        return raw

    def temporal(self, x, valid_from, valid_to, current):
        """The temporal pattern's columns this relation carries, for one version."""
        names = {c["name"] for c in x["columns"]}
        now = datetime.now(timezone.utc)
        out = {}
        for col, v in (("created_dts", now), ("updated_dts", now), ("ingested_dts", now),
                       ("valid_from_dts", valid_from), ("valid_to_dts", valid_to),
                       ("transaction_from_dts", valid_from), ("transaction_to_dts", self.engine.open_end),
                       ("is_current", self.engine.flag(current)), ("is_deleted", self.engine.flag(False))):
            if col in names:
                out[col] = v
        return out

    # ---- keys ------------------------------------------------------------------------
    def allocate(self, keymap, naturals):
        """Each natural value's identifier, through the binding's own key allocation."""
        out = {}
        for natural in dict.fromkeys(naturals):
            *writes, read = statements(self.dialect.key_allocation(self.named(keymap), natural_value=natural))
            for statement in writes:
                self.con.execute(statement)
            out[natural] = self.con.execute(read).fetchone()[0]
        return out

    def read_keys(self, x):
        """Natural value to identifier, read back from an inline entity's table."""
        natural, surrogate = x["identity"]["natural"], x["identity"]["surrogate"]
        if len(natural) != 1 or len(surrogate) != 1:
            return {}
        cn = x["column_names"]
        return {str(n): k for n, k in self.query(
            f"SELECT {self.binding.ident(cn[natural[0]])}, {self.binding.ident(cn[surrogate[0]])} FROM {self.table(x)}")}

    # ---- one mapping entry ------------------------------------------------------------
    def load(self, spec, base):
        x = self.named(spec["name"])
        path = base / spec["file"]
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        columns, key = spec.get("columns", {}), spec.get("key")
        identity = x["identity"]
        keymap = identity.get("keymap")
        surrogate = identity["surrogate"][0] if identity["surrogate"] else None
        if keymap and not key:
            raise LoadError(f"{spec['name']} allocates through {keymap}: its mapping must name `key`")
        if key and rows and key not in rows[0]:
            raise LoadError(f"{path.name} has no column '{key}' for {spec['name']}'s key")
        attributes = [c for c in x["columns"] if c["origin"] == "attribute" and c["name"] not in identity["surrogate"]]
        known = {c["name"] for c in attributes}
        for attribute in columns:
            if attribute not in known:
                raise LoadError(f"{spec['name']} has no attribute '{attribute}'")
        references = {c["name"]: self.targets[f"{spec['name']}.{c['name']}"] for c in attributes
                      if f"{spec['name']}.{c['name']}" in self.targets}
        if key:
            self.sources[spec["name"]].update({r[key]: r for r in rows})
        allocated = self.allocate(keymap, [r[key] for r in rows]) if keymap else {}

        def source(row, attribute):
            return row.get(columns.get(attribute, attribute))

        def valid_from(row):
            rule = spec.get("valid_from")
            if rule and "." in rule and rule.split(".", 1)[0] in references:
                attribute, column = rule.split(".", 1)
                target = self.sources[references[attribute]].get(source(row, attribute))
                raw = target.get(column) if target else None
            else:
                raw = row.get(rule) if rule else None
            return instant(raw or spec.get("default_valid_from", EPOCH))

        closes = {}
        if spec.get("versions"):
            by_key = defaultdict(list)
            for row in rows:
                by_key[row[key]].append(row)
            for versions in by_key.values():
                versions.sort(key=valid_from)
                for earlier, later in zip(versions, versions[1:]):
                    closes[id(earlier)] = valid_from(later)

        def values(row):
            out = {}
            for col in attributes:
                name = col["name"]
                if name in ("is_current", "is_deleted"):
                    continue
                raw = source(row, name)
                if name in references:
                    if raw:
                        target = references[name]
                        if raw not in self.keys[target]:
                            raise LoadError(f"{spec['name']}.{name}: '{raw}' is not a loaded {target}")
                        out[name] = self.keys[target][raw]
                elif raw not in (None, ""):
                    out[name] = self.value(raw, col)
            end = closes.get(id(row))
            out.update(self.temporal(x, valid_from(row), end or self.engine.open_end, end is None))
            if keymap:
                out[surrogate] = allocated[row[key]]
            return out

        own = [a for a, t in references.items() if t == spec["name"]]
        present = {r[key] for r in rows} if key else set()
        pending = rows
        while pending:
            ready = [r for r in pending if not any(
                source(r, a) in present and source(r, a) not in self.keys[spec["name"]] for a in own)]
            if not ready:
                raise LoadError(f"{spec['name']}: rows refer to one another in a cycle")
            self.insert(x, [values(r) for r in ready])
            pending = [r for r in pending if r not in ready]
            if keymap:
                self.keys[spec["name"]].update({r[key]: allocated[r[key]] for r in ready})
            elif key:
                self.keys[spec["name"]].update(self.read_keys(x))
        return len(rows)

    # ---- embeddings -------------------------------------------------------------------
    def embed(self, embedder):
        """Every current subject row's embedding source, embedded and stored, one row per
        subject and embedding; a row the embedding's condition excludes, or with no text,
        gets none."""
        written = {}
        for emb in self.ctx.get("embeddings", []):
            store, subject = self.named(emb["store"]), self.named(emb["entity"])
            alias, key = self.binding.ident(subject["alias"]), self.binding.ident(subject["column_names"][subject["identity"]["surrogate"][0]])
            where = f" WHERE {emb['where']['sql']}" if emb.get("where") else ""
            rows = [(k, t) for k, t in self.query(
                f"SELECT {alias}.{key}, {emb['source']['sql']} FROM {self.view(subject)} {alias}{where}") if t]
            dims = int(emb["dimensions"])
            vectors, model = embedder([t for _, t in rows], emb, dims)
            now = datetime.now(timezone.utc)
            names = {c["name"] for c in store["columns"]}
            out = []
            for (k, _), vec in zip(rows, vectors):
                row = dict(entity_id=k, entity_kind=emb["entity"].upper(), source_attribute=emb["name"],
                           embedding=self.engine.vector(list(vec)), embedding_dimensions=dims,
                           embedding_model=model, embedding_model_version="1", generated_dts=now,
                           **self.temporal(store, now, self.engine.open_end, True))
                out.append({n: v for n, v in row.items() if n in names})
            self.insert(store, out)
            written[f"{emb['store']} ({emb['name']})"] = len(out)
        return written


def placeholder(texts, emb, dims):
    """Deterministic feature hashing of unigrams and bigrams, signed and L2-normalised: close
    texts land close, which is enough to exercise a similarity search, and nothing more."""
    vectors = []
    for text in texts:
        words = re.findall(r"[a-z0-9%]+", text.lower())
        vec = [0.0] * dims
        for gram in words + [f"{a} {b}" for a, b in zip(words, words[1:])]:
            h = int(hashlib.sha256(gram.encode()).hexdigest(), 16)
            vec[h % dims] += 1.0 if (h >> 64) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors, PLACEHOLDER_MODEL


def custom(spec):
    """`module:function`, called with the texts and the declared model; returns vectors."""
    module, _, name = spec.partition(":")
    function = getattr(importlib.import_module(module), name)

    def embed(texts, emb, dims):
        vectors = [list(v) for v in function(texts, emb["model"])]
        if any(len(v) != dims for v in vectors):
            raise LoadError(f"{spec} returned vectors that are not {dims}-dimensional")
        return vectors, emb["model"]
    return embed


def load(con, context, mapping_path, deploy=None, embedder=None):
    """Load every entry of a mapping in order; with `deploy`, the build directory's phases
    first. Returns rows loaded per entity."""
    if deploy:
        manifest = json.loads((deploy / "manifest.json").read_text(encoding="utf-8"))
        driver = engine(context["platform"]["name"])
        for phase in manifest["phases"]:
            driver.apply(con, (deploy / phase).read_text(encoding="utf-8"))
    mapping = tomllib.loads(mapping_path.read_text(encoding="utf-8"))
    loader = Loader(con, context)
    counts = {spec["name"]: loader.load(spec, mapping_path.parent) for spec in mapping.get("entity", [])}
    if embedder:
        counts.update(loader.embed(embedder))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("build", type=Path, help="a render.py output directory")
    parser.add_argument("mapping", type=Path, help="the example's load.toml")
    parser.add_argument("--database", help="DuckDB file path; PostgreSQL reads POSTGRES_DSN and Teradata TERADATA_DSN")
    parser.add_argument("--deploy", action="store_true", help="apply the build's phases before loading")
    parser.add_argument("--embeddings", choices=("none", "placeholder"), default="none")
    parser.add_argument("--embedder", help="module:function computing embeddings with the declared model")
    args = parser.parse_args()
    context = json.loads((args.build / "context.json").read_text(encoding="utf-8"))
    driver = engine(context["platform"]["name"])
    if driver.platform == "duckdb" and not args.database:
        parser.error("Provide a DuckDB file with --database")
    embedder = custom(args.embedder) if args.embedder else placeholder if args.embeddings == "placeholder" else None
    con = driver.connect(args.database)
    try:
        counts = load(con, context, args.mapping, args.build if args.deploy else None, embedder)
    finally:
        con.close()
    for name, n in counts.items():
        print(f"{name}: {n} rows")


if __name__ == "__main__":
    main()
