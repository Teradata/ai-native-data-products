"""The database drivers the binding tools and tests run rendered SQL through, one per platform.

Each engine states how to connect, its driver's parameter marker, how to isolate one check so
a failing one leaves the session usable, and how to make a group of writes atomic. Drivers
differ; the SQL each runs is the binding's own, rendered from its templates. Nothing here
holds platform SQL beyond transaction control.
"""
import json
import re
import os
from contextlib import contextmanager, nullcontext


class Engine:
    platform = None
    marker = "?"

    def connect(self, database=None):
        raise NotImplementedError

    def isolate(self, con):
        """Wrap one check, so an error in it does not poison what follows."""
        return nullcontext()

    def describe(self, con):
        """The engine version and driver a connection reaches, for the conformance report."""
        raise NotImplementedError

    @contextmanager
    def transaction(self, con):
        con.execute("BEGIN")
        try:
            yield
        except Exception:
            con.execute("ROLLBACK")
            raise
        con.execute("COMMIT")


class PostgreSQL(Engine):
    platform = "postgres"
    marker = "%s"
    environment = "POSTGRES_DSN"

    def connect(self, database=None):
        import psycopg
        return psycopg.connect(database or os.environ[self.environment], autocommit=True)

    def isolate(self, con):
        return con.transaction()

    def transaction(self, con):
        return con.transaction()

    def describe(self, con):
        import psycopg
        return f"PostgreSQL {con.execute('SHOW server_version').fetchone()[0].split()[0]} through psycopg {psycopg.__version__}"


class DuckDB(Engine):
    platform = "duckdb"

    def connect(self, database=None):
        import duckdb
        return duckdb.connect(database)

    def describe(self, con):
        import duckdb
        return f"DuckDB {con.execute('SELECT version()').fetchone()[0]} through the duckdb {duckdb.__version__} Python driver"


class TeradataCursor:
    """Rows as tuples, as the other drivers return them; teradatasql returns lists."""

    def __init__(self, cur):
        self.raw = cur

    def fetchone(self):
        row = self.raw.fetchone()
        return None if row is None else tuple(row)

    def fetchall(self):
        return [tuple(row) for row in self.raw.fetchall()]


class TeradataConnection:
    """teradatasql through the `execute` shape the other drivers share. Each request commits
    on its own unless a transaction is open; a failed request rolls back only itself."""

    def __init__(self, con):
        self.raw = con

    def execute(self, sql, params=None):
        cur = self.raw.cursor()
        cur.execute(sql, params or None)
        return TeradataCursor(cur)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


class Teradata(Engine):
    platform = "teradata"
    environment = "TERADATA_DSN"

    def connect(self, database=None):
        """`database` or the environment variable holds the teradatasql connection parameters
        as JSON, for example {"host": ..., "user": ..., "password": ...}. A request whose
        response is lost on the network would otherwise wait forever, so one fails after ten
        minutes unless the parameters set `request_timeout` themselves."""
        import teradatasql
        params = json.loads(database or os.environ[self.environment])
        params.setdefault("request_timeout", "600")
        return TeradataConnection(teradatasql.connect(**params))

    def describe(self, con):
        import teradatasql
        version = con.execute("SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'VERSION'").fetchone()[0]
        return f"Teradata {version} through teradatasql {teradatasql.__version__}"

    @contextmanager
    def transaction(self, con):
        con.raw.autocommit = False
        try:
            yield
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.raw.autocommit = True


ENGINES = {e.platform: e for e in (PostgreSQL(), DuckDB(), Teradata())}


PROCEDURE_START = re.compile(r"\s*(CREATE|REPLACE)\s+PROCEDURE\b", re.I)
BLOCK_WORD = re.compile(r"(BEGIN|END)\b(\s+(IF|WHILE|LOOP|FOR|CASE|REPEAT)\b)?", re.I)


def statements(sql):
    """Rendered SQL as its statements, split on semicolons outside string literals and line
    comments, for a driver that takes one statement per request. A stored procedure is one
    statement, its body's semicolons included, through the `END` that closes its outer
    `BEGIN`."""
    out, buf, quoted, depth, procedure, started, i = [], [], False, 0, False, False, 0
    while i < len(sql):
        if not quoted and sql.startswith("--", i):
            end = sql.find("\n", i)
            i = len(sql) if end < 0 else end
            continue
        ch = sql[i]
        if not started and not ch.isspace():
            started, procedure = True, bool(PROCEDURE_START.match(sql, i))
        if ch == "'":
            quoted = not quoted
        elif procedure and not quoted and not (i and (sql[i - 1].isalnum() or sql[i - 1] == "_")):
            word = BLOCK_WORD.match(sql, i)
            if word:
                depth += 1 if word.group(1).upper() == "BEGIN" else (0 if word.group(2) else -1)
                buf.append(word.group(0))
                i = word.end()
                continue
        if ch == ";" and not quoted and depth == 0:
            out.append("".join(buf).strip() + (";" if procedure else ""))  # a procedure needs its END;
            buf, started = [], False
        else:
            buf.append(ch)
        i += 1
    out.append("".join(buf).strip())
    return [s for s in out if s]


def engine(platform):
    if platform not in ENGINES:
        raise KeyError(f"no driver is declared for the {platform} binding; engine coverage is a gap")
    return ENGINES[platform]
