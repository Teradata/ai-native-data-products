"""Build, validate, close and atomically publish a synthetic portable database."""
import argparse
from pathlib import Path
import sys
import tempfile
import os

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "implementation/duckdb"))
from validate import validate


def build(path, replace=False):
    import duckdb
    path = Path(path).resolve()
    if path.stem in ("domain", "semantic", "search", "prediction", "observability", "memory"):
        raise ValueError("Database catalogue name must not collide with a module schema")
    if path.exists() and not replace:
        raise FileExistsError(f"{path} exists; --replace explicitly rebuilds the synthetic fixture")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="customer360-build-", dir=path.parent) as directory:
        pending = Path(directory) / "customer360.duckdb"
        with duckdb.connect(str(pending)) as con:
            con.execute((HERE / "build.sql").read_text(encoding="utf-8"))
            results = validate(con)
            bad = [r for r in results if r["status"] != "PASSED"]
            if bad:
                raise RuntimeError(f"Validation failed; target not replaced: {bad}")
            con.execute("CHECKPOINT")
        os.replace(pending, path)
    return len(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", nargs="?", default=str(HERE / "customer360.duckdb"))
    parser.add_argument("--replace", action="store_true", help="Replace an existing synthetic example after successful validation")
    args = parser.parse_args()
    print(f"Built {args.database}; {build(args.database, args.replace)} checks passed.")
