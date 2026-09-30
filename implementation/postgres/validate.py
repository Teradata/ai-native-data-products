"""Execute the native profile and append validation wire-schema 2.1 evidence."""
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import uuid
from checks import profile


UNASSESSED = {
    ("PATTERN", "access-layer"): "Native grants and USER row policies are deployed. Login provisioning, membership and operational access review require operator evidence.",
    ("PATTERN", "physical-storage"): "External object storage is not deployed; OS permissions and backup policy require operator evidence.",
    ("CAPABILITY", "Embed"): "The toy lexical encoder is reproducible but semantic retrieval quality is not assessed.",
}


def summarize(expected, results):
    counts = dict(passed_count=0, failed_count=0, error_count=0, critical_failure_count=0, error_failure_count=0)
    for result in results:
        counts[{"PASSED": "passed_count", "FAILED": "failed_count", "ERROR": "error_count"}[result["status"]]] += 1
        if result["status"] != "PASSED" and result["severity"] in ("ERROR", "CRITICAL"):
            counts["error_failure_count" if result["severity"] == "ERROR" else "critical_failure_count"] += 1
    ran = len(results)
    failures = counts["failed_count"] + counts["error_count"]
    if expected == 0:
        status, confidence = "no-evidence", "unknown"
    elif ran == 0:
        status, confidence = "not-validated", "unknown"
    else:
        status = "fail" if failures else "pass" if ran == expected else "partial"
        confidence = ("weak" if counts["critical_failure_count"]+counts["error_failure_count"] or ran/expected<0.5
                      else "partial" if failures or ran<expected else "strong")
    return dict(counts, checks_expected=expected, checks_ran=ran, area_status=status, confidence=confidence)


def append(con, table, values, now):
    values = dict(values, created_dts=now, updated_dts=now)
    con.execute(f"INSERT INTO observability.{table} ({','.join(values)}) VALUES ({','.join('%s' for _ in values)})", list(values.values()))


def validate(con, checks=None, run_id=None):
    # Savepoints preserve the transaction after an individual SQL error.
    with con.transaction():
        return _validate(con, checks, run_id)


def _validate(con, checks=None, run_id=None):
    checks = profile() if checks is None else checks
    started = datetime.now(timezone.utc)
    run_id = run_id or started.strftime("%Y%m%dT%H%M%S%fZ-")+uuid.uuid4().hex[:8]
    results = []
    for check in checks:
        try:
            with con.transaction():
                count = con.execute("SELECT count(*) FROM ("+check.sql+") violations").fetchone()[0]
            status, error = ("FAILED" if count else "PASSED"), None
        except Exception as exc:
            count, status, error = 0, "ERROR", str(exc)
        results.append(dict(test_id=check.test_id, scope_kind=check.scope_kind, scope_id=check.scope_id,
                            category=check.category, severity=check.severity, status=status, row_count=count, error_message=error))
    completed = datetime.now(timezone.utc)
    total = summarize(len(checks), results)
    status = ("UNTRUSTED" if total["error_count"]+total["critical_failure_count"]+total["error_failure_count"]
              else "DEGRADED" if total["failed_count"] else "TRUSTED")
    groups = defaultdict(list)
    for r in results:
        groups[r["scope_kind"], r["scope_id"]].append(r)
    for scope in UNASSESSED:
        groups.setdefault(scope, [])
    try:
        count_names = ("passed_count", "failed_count", "error_count", "critical_failure_count", "error_failure_count")
        append(con, "validation_run", dict(product_prefix="customer360", producer_id="postgres-reference", run_id=run_id,
               producer_version="1.0", profile_id="portable-baseline", profile_version="1.0", source_format="NATIVE",
               payload_schema_version="2.1", started_dts=started, completed_dts=completed, trust_status=status,
               agent_use_allowed="go", total_checks=len(results), **{n: total[n] for n in count_names},
               data_product_trust_score=None, performance_readiness_score=None, operational_readiness_score=None,
               repair_candidate_count=0, failed_checks_json=None, repair_candidates_json=None,
               evidence_expires_dts=completed+timedelta(days=7)), completed)
        for (kind, scope), entries in groups.items():
            area = summarize(len(entries), entries)
            gap = UNASSESSED.get((kind, scope)) or ("Failed checks or incomplete coverage; inspect validation_check." if area["confidence"] != "strong" else None)
            append(con, "validation_area", dict(product_prefix="customer360", producer_id="postgres-reference", run_id=run_id,
                   area_id=run_id+":"+kind+":"+scope, payload_schema_version="2.1", scope_kind=kind, scope_id=scope,
                   **area, open_gaps=gap, recommended_action="Supply external evidence or repair and rerun applicable checks." if gap else None,
                   completed_dts=completed), completed)
        for result in results:
            append(con, "validation_check", dict(result, check_result_id=run_id+":"+result["test_id"], run_id=run_id, checked_dts=completed), completed)
    except Exception:
        raise
    return results


def main():
    import psycopg
    with psycopg.connect(os.environ['POSTGRES_DSN'], autocommit=True) as con:
        results = validate(con)
    bad = [r for r in results if r["status"] != "PASSED"]
    for r in bad:
        print(r)
    print(f"{len(results)-len(bad)}/{len(results)} checks passed; external areas remain explicitly unassessed.")
    raise SystemExit(bool(bad))


if __name__ == "__main__":
    main()
