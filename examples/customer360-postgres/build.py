"""Build and validate an empty, dedicated PostgreSQL database atomically."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'implementation/postgres'))
from validate import validate


def build(con):
    if con.info.server_version < 160000:
        raise RuntimeError('PostgreSQL 16 or later is required')
    sql = Path(__file__).with_name('build.sql').read_text(encoding='utf-8')
    # The checked SQL is also directly runnable by psql. Python owns this transaction.
    sql = sql.replace('BEGIN TRANSACTION;\n', '', 1).removesuffix('COMMIT;\n')
    with con.transaction():
        con.execute(sql)
        results = validate(con)
        bad = [r for r in results if r['status'] != 'PASSED']
        if bad:
            raise RuntimeError(f'Build rolled back: {bad}')
    return results


if __name__ == '__main__':
    import psycopg
    with psycopg.connect(os.environ['POSTGRES_DSN'], autocommit=True) as con:
        results = build(con)
    print(f'Built customer360; {len(results)} checks passed. See trust_map for unassessed areas.')
