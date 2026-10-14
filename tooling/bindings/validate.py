"""Run a rendered product's checks and publish wire-schema 2.1 evidence where it has a home.

The manifest is trusted build output containing SQL: never run an untrusted manifest. Each
check returns its defects, so a check passes when it returns no rows. Where the product
places `ValidationRun` and `ValidationArea`, one run and its area records are appended,
named as the manifest's build context placed them. Each engine's driver (engines.py) isolates
each check and publishes the evidence in one transaction.
"""
import argparse
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tooling" / "build"))

from binding import load_binding  # noqa: E402
from engines import engine  # noqa: E402

PAYLOAD_SCHEMA_VERSION = "2.1"
COUNTS = ("passed_count", "failed_count", "error_count", "critical_failure_count", "error_failure_count")


def summarize(expected, results, gap=None):
    """One area's wire-schema 2.1 summary. Only ERROR and CRITICAL failures count as such, so
    a failed WARNING leaves partial confidence; an open gap caps confidence at partial."""
    counts = dict.fromkeys(COUNTS, 0)
    for r in results:
        counts[{"PASSED": "passed_count", "FAILED": "failed_count", "ERROR": "error_count"}[r["status"]]] += 1
        if r["status"] != "PASSED" and r["severity"] in ("ERROR", "CRITICAL"):
            counts["error_failure_count" if r["severity"] == "ERROR" else "critical_failure_count"] += 1
    ran, bad = len(results), counts["failed_count"] + counts["error_count"]
    if expected == 0:
        status, confidence = "no-evidence", "unknown"
    elif ran == 0:
        status, confidence = "not-validated", "unknown"
    else:
        status = "fail" if bad else "pass" if ran == expected else "partial"
        confidence = ("weak" if counts["critical_failure_count"] + counts["error_failure_count"] or ran / expected < 0.5
                      else "partial" if bad or ran < expected else "strong")
    if gap and confidence == "strong":
        status, confidence = "partial", "partial"
    return dict(counts, checks_expected=expected, checks_ran=ran, area_status=status, confidence=confidence)


def run_checks(con, manifest):
    driver = engine(manifest["platform"])
    results = []
    for check in manifest["checks"]:
        try:
            with driver.isolate(con):
                count = con.execute("SELECT count(*) FROM (" + check["sql"] + ") defects").fetchone()[0]
            status, error = ("FAILED" if count else "PASSED"), None
        except Exception as exc:  # an erroring check is evidence, never a pass
            count, status, error = 0, "ERROR", str(exc).splitlines()[0]
        results.append({k: check[k] for k in ("test_id", "check", "scope_kind", "scope_id", "module",
                                               "category", "severity")}
                       | {"status": status, "row_count": count, "error_message": error})
    return results


def publish(con, manifest, results, started, producer_id=None, run_id=None):
    """Append one ValidationRun and its ValidationArea records, or nothing if the product
    places no evidence store. Returns the run id."""
    evidence = manifest["evidence"]
    if not (evidence["run"] and evidence["area"]):
        return None
    binding, _ = load_binding(manifest["platform"])
    driver = engine(manifest["platform"])
    marker = driver.marker
    now = datetime.now(timezone.utc)
    run_id = run_id or uuid.uuid4().hex
    product = manifest["product"]["code"]
    producer = producer_id or manifest["product"].get("trust_producer") or "rendered-binding"
    gaps = manifest["gaps"]

    def insert(rel, values):
        names = rel["column_names"]
        for col in ("created_dts", "updated_dts"):
            if col in names:
                values.setdefault(col, now)
        table = rel["objects"]["table"]
        cols = ", ".join(binding.ident(names[k]) for k in values)
        con.execute(f"INSERT INTO {binding.qualified(table['container'], table['name'])} ({cols}) "
                    f"VALUES ({', '.join(marker for _ in values)})", list(values.values()))

    groups = defaultdict(list)
    for r in results:
        groups[r["scope_kind"], r["scope_id"]].append(r)
        if r["scope_kind"] == "ENTITY":
            groups["MODULE", r["module"]].append(r)
    for m in manifest["modules"]:
        groups.setdefault(("MODULE", m), [])
    groups["PRODUCT", product] = list(results)
    totals = summarize(len(results), results, gaps)
    failed = [{k: r[k] for k in ("test_id", "scope_kind", "scope_id", "status", "row_count", "error_message")}
              for r in results if r["status"] != "PASSED"]
    trust = ("UNTRUSTED" if totals["critical_failure_count"] + totals["error_failure_count"] + totals["error_count"]
             else "DEGRADED" if failed or gaps else "TRUSTED")
    with driver.transaction(con):
        insert(evidence["run"], {
            "product_code": product, "producer_id": producer, "producer_version": "2.0",
            "profile_id": "rendered-binding", "profile_version": manifest["platform"],
            "source_format": "NATIVE", "payload_schema_version": PAYLOAD_SCHEMA_VERSION, "run_id": run_id,
            "started_dts": started, "completed_dts": now, "trust_status": trust,
            "total_checks": len(results), **{n: totals[n] for n in COUNTS},
            "repair_candidate_count": 0, "failed_checks_json": json.dumps(failed),
            "evidence_expires_dts": now + timedelta(days=evidence["evidence_window_days"])})
        for (kind, scope), entries in groups.items():
            gap = "; ".join(gaps) if kind == "PRODUCT" and gaps else None
            area = summarize(len(entries), entries, gap)
            if area["confidence"] != "strong" and not gap and entries:
                gap = "Failed or missing checks; inspect the run's failed checks."
            insert(evidence["area"], {
                "product_code": product, "producer_id": producer, "run_id": run_id,
                "scope_kind": kind, "scope_id": scope, **area, "open_gaps": gap,
                "recommended_action": "Repair or supply the missing evidence, then re-run." if gap else None,
                "completed_dts": now})
    return run_id


def validate(con, manifest, producer_id=None, run_id=None):
    started = datetime.now(timezone.utc)
    results = run_checks(con, manifest)
    publish(con, manifest, results, started, producer_id, run_id)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--database", help="DuckDB file path; PostgreSQL reads POSTGRES_DSN and Teradata "
                                            "TERADATA_DSN (teradatasql connection parameters as JSON)")
    parser.add_argument("--producer", help="the producer id to publish as; defaults to the product's trust producer")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    driver = engine(manifest["platform"])
    if driver.platform == "duckdb" and not (args.database and Path(args.database).is_file()):
        parser.error("Provide an existing DuckDB file with --database")
    con = driver.connect(args.database)
    try:
        results = validate(con, manifest, args.producer)
    finally:
        con.close()
    bad = [r for r in results if r["status"] != "PASSED"]
    print(json.dumps(bad, indent=2))
    print(f"{len(results) - len(bad)}/{len(results)} checks passed; {len(manifest['gaps'])} reported gaps.")
    raise SystemExit(bool(bad))


if __name__ == "__main__":
    main()
