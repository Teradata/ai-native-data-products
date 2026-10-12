"""Execute a rendered manifest and append wire-schema 2.1 evidence when available.

The manifest is trusted build output, containing SQL. Do not execute an untrusted
manifest. PostgreSQL uses savepoints for errors; DuckDB checks run in autocommit.
"""
import argparse
from collections import defaultdict
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import uuid

try:
    from .render import qualified
except ImportError:
    from render import qualified


def summarize(expected,results):
    """Wire-schema 2.1 area summary. A result may carry a severity (default ERROR); only
    ERROR and CRITICAL failures are counted as such, so a failed WARNING leaves partial confidence."""
    counts=dict(passed_count=0,failed_count=0,error_count=0,critical_failure_count=0,error_failure_count=0)
    for r in results:
        counts[{'PASSED':'passed_count','FAILED':'failed_count','ERROR':'error_count'}[r['status']]]+=1
        severity=r.get('severity','ERROR')
        if r['status']!='PASSED' and severity in ('ERROR','CRITICAL'):
            counts['error_failure_count' if severity=='ERROR' else 'critical_failure_count']+=1
    ran=len(results);bad=counts['failed_count']+counts['error_count']
    if expected==0: status,confidence='no-evidence','unknown'
    elif ran==0: status,confidence='not-validated','unknown'
    else:
        status='fail' if bad else 'pass' if ran==expected else 'partial'
        confidence=('weak' if counts['critical_failure_count']+counts['error_failure_count'] or ran/expected<0.5
                    else 'partial' if bad or ran<expected else 'strong')
    return dict(counts,checks_expected=expected,checks_ran=ran,area_status=status,confidence=confidence)


def validate(con,manifest,run_id=None):
    postgres=manifest['platform']=='postgres'
    started=datetime.now(timezone.utc)
    results=[]
    for check in manifest['checks']:
        try:
            with con.transaction() if postgres else nullcontext():
                count=con.execute('SELECT count(*) FROM ('+check['sql']+') defects').fetchone()[0]
            status='FAILED' if count else 'PASSED';error=None
        except Exception as exc:
            count=0;status='ERROR';error=str(exc)
        results.append(dict(test_id=check['test_id'],scope_kind=check['scope_kind'],scope_id=check['scope_id'],
                            category=check.get('category','STRUCTURAL'),severity=check.get('severity','ERROR'),
                            status=status,row_count=count,error_message=error))
    if 'observability' not in manifest['modules']: return results
    now=datetime.now(timezone.utc);run_id=run_id or uuid.uuid4().hex
    product=manifest['product'];schema=manifest['containers']['observability']
    groups=defaultdict(list)
    entity_modules={e['identity']:e['module'] for e in manifest['entities']}
    for r in results:
        groups[r['scope_kind'],r['scope_id']].append(r)
        if r['scope_kind']=='ENTITY': groups['MODULE',entity_modules[r['scope_id']]].append(r)
    for m in manifest['modules']: groups.setdefault(('MODULE',m),[])
    gaps={('PATTERN','access-layer'):'Authentication and operator membership review require deployment evidence.',
          ('PATTERN','physical-storage'):'Backup, durability and operational storage checks are not covered by structural validation.'}
    if 'search' in manifest['modules']: gaps['CAPABILITY','Embed']='No encoder quality or model execution is established by schema conformance.'
    if 'prediction' in manifest['modules']: gaps['MODULE','prediction']='Structural checks do not establish feature pipeline or model predictive quality.'
    for scope in gaps: groups.setdefault(scope,[])
    def insert(table,values):
        values=dict(values,created_dts=now,updated_dts=now)
        marker='%s' if postgres else '?'
        con.execute(f'INSERT INTO {qualified(schema,table)} ({",".join(values)}) VALUES ({",".join(marker for _ in values)})',list(values.values()))
    if not postgres: con.execute('BEGIN')
    try:
        with con.transaction() if postgres else nullcontext():
            totals=summarize(len(results),results)
            names=('passed_count','failed_count','error_count','critical_failure_count','error_failure_count')
            insert('validation_run',dict(product_prefix=product['id'],producer_id=product['validator'],run_id=run_id,
                producer_version='2.0',profile_id='rendered-binding',profile_version='1.0',source_format='NATIVE',payload_schema_version='2.1',
                started_dts=started,completed_dts=now,trust_status='UNTRUSTED' if totals['error_count']+totals['critical_failure_count']+totals['error_failure_count'] else 'DEGRADED',
                agent_use_allowed='go',total_checks=len(results),**{n:totals[n] for n in names},
                data_product_trust_score=None,performance_readiness_score=None,operational_readiness_score=None,
                repair_candidate_count=0,failed_checks_json=None,repair_candidates_json=None,evidence_expires_dts=now+timedelta(days=product['evidence_days'])))
            for (kind,scope),entries in groups.items():
                area=summarize(len(entries),entries)
                gap=gaps.get((kind,scope))
                if gap and area['confidence']=='strong': area['confidence']='partial';area['area_status']='partial'
                if area['confidence']!='strong' and not gap: gap='Missing coverage or failed checks; inspect individual evidence.'
                insert('validation_area',dict(product_prefix=product['id'],producer_id=product['validator'],run_id=run_id,
                    area_id=run_id+':'+kind+':'+scope,payload_schema_version='2.1',scope_kind=kind,scope_id=scope,**area,
                    open_gaps=gap,recommended_action='Supply missing evidence or repair and rerun.' if gap else None,completed_dts=now))
            for r in results:
                insert('validation_check',dict(r,check_result_id=run_id+':'+r['test_id'],run_id=run_id,checked_dts=now))
        if not postgres: con.execute('COMMIT')
    except Exception:
        if not postgres: con.execute('ROLLBACK')
        raise
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--database',help='DuckDB file path; PostgreSQL uses POSTGRES_DSN')
    args=parser.parse_args();m=json.loads(args.manifest.read_text(encoding='utf-8'))
    if m['platform']=='postgres':
        import psycopg
        con=psycopg.connect(os.environ['POSTGRES_DSN'],autocommit=True)
    else:
        import duckdb
        if not args.database or not Path(args.database).is_file(): parser.error('Provide an existing DuckDB file with --database')
        con=duckdb.connect(args.database)
    try: results=validate(con,m)
    finally: con.close()
    bad=[r for r in results if r['status']!='PASSED']
    print(json.dumps(bad,indent=2))
    print(f'{len(results)-len(bad)}/{len(results)} structural checks passed; review coverage gaps separately.')
    raise SystemExit(bool(bad))


if __name__=='__main__':main()
