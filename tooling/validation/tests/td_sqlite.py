"""Run the validation pattern's shipped Teradata SQL against SQLite.

The trust map's read path is logic, and the review of #57 found three defects in it that
no amount of reading the file had caught: staleness graded against the wrong run, a
legacy fallback that swallowed a malformed run, and a requested area that vanished
instead of reporting itself unknown. Each is a behaviour, so each needs a test that
states the behaviour and executes it.

Nothing in `tooling/` may depend on a live Teradata, so the SQL is translated and run on
stdlib `sqlite3`. That buys the tests teeth at the cost of one obvious risk: a translator
can quietly mistranslate, and a test over a mistranslation is worse than no test. Two
things hold that risk down.

  * **The SQL is read from the shipped files**, never retyped here. Reverting a fix in
    `04-trust-map-views.sql` fails these tests, which is the whole point.
  * **The translator refuses to guess.** Every rewrite is explicit and narrow, and
    `_assert_translated` raises `UntranslatedSql` if any Teradata construct survives it.
    A new construct in the shipped SQL breaks the harness loudly rather than being
    silently dropped from the statement it was load-bearing in.

What this does *not* test is Teradata's own semantics: `QUALIFY` becomes a wrapped
`ROW_NUMBER`, an `INTERVAL` becomes `datetime(...)`, and a zone-qualified timestamp
becomes ISO text. Those are faithful for the comparisons the trust map makes and are not
faithful in general. Conformance against the real platform stays the deployed
`conformance-queries.sql`; this is the regression net underneath it.

Timestamps are ISO `YYYY-MM-DD HH:MM:SS` UTC text, which SQLite's `CURRENT_TIMESTAMP`
also produces, so the pattern's `<` comparisons sort correctly as strings.
"""
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION = REPO_ROOT / "implementation" / "teradata" / "patterns" / "validation"
SEMANTIC = REPO_ROOT / "implementation" / "teradata" / "modules" / "semantic"

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


class UntranslatedSql(Exception):
    """A construct the translator does not handle survived translation."""


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ts(offset_days=0, offset_hours=0):
    """An ISO timestamp offset from now, for building fresh and stale evidence."""
    return (now() + timedelta(days=offset_days, hours=offset_hours)).strftime(TS_FORMAT)


# --- lexing helpers ---------------------------------------------------------------
# Every position-sensitive rewrite works over a copy with string literals blanked, so a
# keyword or a parenthesis inside a comment string can never be mistaken for syntax.

def _mask_strings(sql):
    out = []
    in_str = False
    i = 0
    while i < len(sql):
        c = sql[i]
        if in_str:
            if c == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    out.append("  ")
                    i += 2
                    continue
                in_str = False
            out.append(" ")
        elif c == "'":
            in_str = True
            out.append(" ")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _token_positions(sql, token):
    masked = _mask_strings(sql)
    return [m.start() for m in re.finditer(r"\b" + token + r"\b", masked)]


def _depth_at(sql, pos):
    masked = _mask_strings(sql)[:pos]
    return masked.count("(") - masked.count(")")


def _call_bounds(sql, name, start=0):
    """(call_start, close_idx, inner_text) for the next balanced `name(...)` call."""
    masked = _mask_strings(sql)
    m = re.compile(r"\b" + name + r"\s*\(", re.I).search(masked, start)
    if not m:
        return None
    open_idx = m.end() - 1
    depth = 0
    for i in range(open_idx, len(masked)):
        if masked[i] == "(":
            depth += 1
        elif masked[i] == ")":
            depth -= 1
            if depth == 0:
                return m.start(), i, sql[open_idx + 1:i]
    raise UntranslatedSql("unbalanced parentheses after %s" % name)


def _split_top_level(text, keyword):
    """Split on `keyword` at paren depth 0. Returns the parts, keyword removed."""
    parts = []
    last = 0
    for pos in _token_positions(text, keyword):
        if _depth_at(text, pos) == 0:
            parts.append(text[last:pos])
            last = pos + len(keyword)
    parts.append(text[last:])
    return [p.strip() for p in parts]


# --- statement splitting ---------------------------------------------------------

def split_statements(text):
    """Split a .sql file into statements, each keeping the comments that precede it.

    The leading comments are the only stable handle on an individual query in
    `conformance-queries.sql`, which is a flat sequence of checks identified by the
    `-- VAL-nn` line above each one.
    """
    statements = []
    buf = []
    in_str = False
    i = 0
    while i < len(text):
        c = text[i]
        buf.append(c)
        if in_str:
            if c == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    buf.append(text[i + 1])
                    i += 2
                    continue
                in_str = False
        elif c == "'":
            in_str = True
        elif c == "-" and i + 1 < len(text) and text[i + 1] == "-":
            end = text.find("\n", i)
            if end == -1:
                end = len(text)
            buf.append(text[i + 1:end])
            i = end
            continue
        elif c == ";":
            statements.append("".join(buf))
            buf = []
        i += 1
    tail = "".join(buf)
    if tail.strip():
        statements.append(tail)
    return [s for s in statements if s.strip()]


def strip_comments(sql):
    out = []
    in_str = False
    i = 0
    while i < len(sql):
        c = sql[i]
        if in_str:
            out.append(c)
            if c == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    out.append(sql[i + 1])
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if c == "'":
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "-" and i + 1 < len(sql) and sql[i + 1] == "-":
            end = sql.find("\n", i)
            if end == -1:
                break
            i = end
            continue
        out.append(c)
        i += 1
    return "".join(out)


# --- rewrites --------------------------------------------------------------------

def _rewrite_position(sql):
    """POSITION('x' IN col) -> INSTR(col, 'x')"""
    while True:
        found = _call_bounds(sql, "POSITION")
        if not found:
            return sql
        start, close, inner = found
        parts = _split_top_level(inner, "IN")
        if len(parts) != 2:
            raise UntranslatedSql("unsupported POSITION argument: %r" % inner)
        needle, haystack = parts
        sql = sql[:start] + "INSTR(%s, %s)" % (haystack, needle) + sql[close + 1:]


def _rewrite_substring(sql):
    """SUBSTRING(col FROM a [FOR b]) -> SUBSTR(col, a[, b])"""
    searched = 0
    while True:
        found = _call_bounds(sql, "SUBSTRING", searched)
        if not found:
            return sql
        start, close, inner = found
        parts = _split_top_level(inner, "FROM")
        if len(parts) != 2:
            raise UntranslatedSql("unsupported SUBSTRING argument: %r" % inner)
        column, rest = parts
        bounds = _split_top_level(rest, "FOR")
        args = ", ".join([column] + bounds)
        sql = sql[:start] + "SUBSTR(%s)" % args + sql[close + 1:]
        searched = start


def _rewrite_qualify(sql):
    """QUALIFY <window expr> = n -> the window expression projected and filtered outside.

    SQLite has no QUALIFY and forbids window functions in WHERE, so the enclosing SELECT
    is wrapped: the window expression joins its select list under a private alias, and
    the predicate becomes a WHERE on the wrapper. The wrapper projects `*`, so the
    result carries one extra column; nothing in the shipped SQL reads these relations
    with `SELECT *`, so the views' column contracts are unaffected.
    """
    while True:
        positions = _token_positions(sql, "QUALIFY")
        if not positions:
            return sql
        idx = positions[0]
        depth = _depth_at(sql, idx)

        select_start = None
        for pos in _token_positions(sql, "SELECT"):
            if pos < idx and _depth_at(sql, pos) == depth:
                select_start = pos
        if select_start is None:
            raise UntranslatedSql("QUALIFY with no enclosing SELECT at the same depth")

        masked = _mask_strings(sql)
        end = len(sql)
        running = depth
        for i in range(idx, len(sql)):
            if masked[i] == "(":
                running += 1
            elif masked[i] == ")":
                running -= 1
                if running < depth:
                    end = i
                    break
            elif masked[i] == ";" and running == depth:
                end = i
                break

        inner = sql[select_start:idx]
        predicate = sql[idx + len("QUALIFY"):end]
        m = re.match(r"^\s*(?P<expr>.+?)\s*=\s*(?P<value>\d+)\s*$", predicate, re.S)
        if not m:
            raise UntranslatedSql("unsupported QUALIFY predicate: %r" % predicate)

        from_pos = None
        for pos in _token_positions(inner, "FROM"):
            if _depth_at(inner, pos) == 0:
                from_pos = pos
                break
        if from_pos is None:
            raise UntranslatedSql("QUALIFY block has no top-level FROM")

        ranked = (inner[:from_pos].rstrip()
                  + "\n    , " + m.group("expr") + " AS _row_pick\n"
                  + inner[from_pos:])
        sql = (sql[:select_start]
               + "SELECT * FROM (\n" + ranked
               + "\n) AS _ranked WHERE _row_pick = " + m.group("value") + "\n"
               + sql[end:])


# Constructs that must not survive translation. Each is either rewritten above or the
# statement carrying it is dropped; anything left means the harness has gone stale
# against the shipped SQL and must be extended rather than trusted.
_UNTRANSLATED = (
    "QUALIFY", "LOCKING", "MULTISET", "PRIMARY INDEX", "COLLECT STATISTICS",
    "CHARACTER SET", "INTERVAL", "BYTEINT", "SMALLINT", "POSITION(", "SUBSTRING(",
    "DECIMAL(", "WITH TIME ZONE", "GENERATED ALWAYS", "REPLACE VIEW", "{db}", "{sem}",
)


def _assert_translated(sql):
    masked = _mask_strings(sql).upper()
    for token in _UNTRANSLATED:
        # Keyword tokens match on word boundaries: a rewrite is free to introduce an
        # alias containing one, and a substring test would flag its own output.
        if re.fullmatch(r"[\w ]+", token):
            hit = re.search(r"\b" + token.replace(" ", r"\s+") + r"\b", masked)
        else:
            hit = token.upper() in masked
        if hit:
            raise UntranslatedSql(
                "%r survived translation - extend td_sqlite for the construct the "
                "shipped SQL now uses:\n%s" % (token, sql.strip()[:400]))


def translate(sql):
    """Translate one Teradata statement, or None where it has no SQLite equivalent."""
    s = strip_comments(sql)
    if not s.strip():
        return None
    if re.match(r"^\s*(COLLECT STATISTICS|COMMENT ON)\b", s, re.I):
        return None

    s = s.replace("{db}.", "").replace("{sem}.", "")
    s = re.sub(r"\bLOCKING ROW FOR ACCESS\b", "", s, flags=re.I)
    s = re.sub(r"\bREPLACE VIEW\b", "CREATE VIEW", s, flags=re.I)
    s = re.sub(r"\bCREATE MULTISET TABLE\b", "CREATE TABLE", s, flags=re.I)
    s = re.sub(r"\s+CHARACTER SET (LATIN|UNICODE)\b", "", s, flags=re.I)
    s = re.sub(r"\bTIMESTAMP\(\d+\)\s+WITH TIME ZONE\b", "TEXT", s, flags=re.I)
    s = re.sub(r"\bJSON\(\d+\)", "TEXT", s, flags=re.I)
    s = re.sub(r"\b(BYTEINT|SMALLINT)\b", "INTEGER", s, flags=re.I)
    s = re.sub(r"\s+GENERATED ALWAYS AS IDENTITY\b", "", s, flags=re.I)
    s = re.sub(r"\bCURRENT_TIMESTAMP\(\d+\)", "CURRENT_TIMESTAMP", s, flags=re.I)
    s = re.sub(r"\bDECIMAL\(\s*\d+\s*,\s*\d+\s*\)", "REAL", s, flags=re.I)
    s = re.sub(r"([\w.]+)\s*\+\s*INTERVAL\s*'(\d+)'\s*DAY\b",
               r"datetime(\1, '+\2 days')", s, flags=re.I)
    s = _rewrite_position(s)
    s = _rewrite_substring(s)
    s = re.sub(r"\)\s*PRIMARY INDEX\s*\([^)]*\)\s*;", ");", s, flags=re.I)
    s = _rewrite_qualify(s)

    _assert_translated(s)
    return s


# --- the fixture -----------------------------------------------------------------

# Stand-ins for the Semantic catalogue relations VAL-14 resolves an area against, and for
# the caller-populated request relation. The shipped DDL for the catalogue tables is a
# Jinja template importing the temporal macros, and loading it would drag the whole
# temporal block into a fixture that needs two columns from each. The names are asserted
# against the shipped templates by test_trust_map.SemanticStandInsMatchShippedDdl, so
# this cannot drift silently.
_STAND_INS = (
    "CREATE TABLE entity_metadata (module_name TEXT, entity_name TEXT, is_active INTEGER)",
    "CREATE TABLE data_product_map (module_name TEXT, is_active INTEGER)",
    "CREATE TABLE data_product_orientation ("
    " product_id TEXT, resource_role TEXT, discovery_order INTEGER, is_active INTEGER)",
    # Populated by the consumer per request, not deployed by the product, so it has no
    # shipped DDL of its own (consumer-queries.sql query 1).
    "CREATE TABLE requested_validation_scope (scope_kind TEXT, scope_id TEXT)",
)

RUN_DEFAULTS = dict(
    product_prefix="CALLCENTRE", producer_id="trust-engine", producer_version="1.0",
    profile_id=None, profile_version=None, source_format="NATIVE",
    payload_schema_version="2.1", run_id="R1",
    started_dts=None, completed_dts=None,
    trust_status="TRUSTED", agent_use_allowed=1,
    total_checks=10, passed_count=10, failed_count=0, error_count=0,
    critical_failure_count=0, error_failure_count=0,
    data_product_trust_score=100, performance_readiness_score=None,
    operational_readiness_score=None, repair_candidate_count=0,
    failed_checks_json=None, repair_candidates_json=None, evidence_expires_dts=None,
)

AREA_DEFAULTS = dict(
    product_prefix="CALLCENTRE", producer_id="trust-engine", run_id="R1",
    scope_kind="MODULE", scope_id="domain",
    checks_expected=4, checks_ran=4,
    passed_count=4, failed_count=0, error_count=0,
    critical_failure_count=0, error_failure_count=0,
    area_status="pass", confidence="strong",
    open_gaps=None, recommended_action=None, completed_dts=None,
)


class Fixture:
    """An in-memory deployment of the validation pattern's shipped relations."""

    FILES = ("01-validation-run.sql", "03-validation-area.sql",
             "02-views.sql", "04-trust-map-views.sql")

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        for statement in _STAND_INS:
            self.db.execute(statement)
        for name in self.FILES:
            self.load(VALIDATION / name)

    def close(self):
        self.db.close()

    def load(self, path):
        for raw in split_statements(path.read_text(encoding="utf-8")):
            translated = translate(raw)
            if translated is None:
                continue
            try:
                self.db.execute(translated)
            except sqlite3.Error as exc:
                raise AssertionError(
                    "%s: %s\n%s" % (path.name, exc, translated.strip()[:600])) from exc

    # -- population ---------------------------------------------------------------

    def insert_run(self, **overrides):
        row = dict(RUN_DEFAULTS)
        row.update(overrides)
        if row["completed_dts"] is None:
            row["completed_dts"] = ts()
        if row["started_dts"] is None:
            row["started_dts"] = row["completed_dts"]
        self._insert("validation_run", row)
        return row

    def insert_area(self, **overrides):
        row = dict(AREA_DEFAULTS)
        row.update(overrides)
        if row["completed_dts"] is None:
            # The area inherits its run's completion instant (VAL-09); defaulting to the
            # parent run's value rather than to now() keeps a fixture honest by default.
            parent = self.db.execute(
                "SELECT completed_dts FROM validation_run"
                " WHERE product_prefix = ? AND producer_id = ? AND run_id = ?",
                (row["product_prefix"], row["producer_id"], row["run_id"])).fetchone()
            row["completed_dts"] = parent["completed_dts"] if parent else ts()
        if row["confidence"] != "strong":
            row["open_gaps"] = row["open_gaps"] or "Fixture gap."
            row["recommended_action"] = row["recommended_action"] or "Fixture action."
        self._insert("validation_area", row)
        return row

    def request(self, *scopes):
        self.db.executemany(
            "INSERT INTO requested_validation_scope (scope_kind, scope_id) VALUES (?, ?)",
            scopes)

    def _insert(self, table, row):
        columns = ", ".join(row)
        markers = ", ".join("?" for _ in row)
        self.db.execute("INSERT INTO %s (%s) VALUES (%s)" % (table, columns, markers),
                        tuple(row.values()))

    # -- reading ------------------------------------------------------------------

    def rows(self, sql, params=None):
        return [dict(r) for r in self.db.execute(sql, params or {}).fetchall()]

    def trust_map(self, **filters):
        where = " AND ".join("%s = :%s" % (k, k) for k in filters) or "1 = 1"
        return self.rows("SELECT * FROM validation_trust_map WHERE " + where, filters)


def statement_from(path, marker, substitutions=None):
    """The translated statement whose leading comments contain `marker`.

    `substitutions` is applied to the file text first, for the one template in scope
    here (`modules/semantic/validation.sql.j2`) whose only Jinja is `{{ product }}`
    interpolation. A plain replace is exact for that; it is not a Jinja renderer, and a
    template that grows a `{% %}` block needs the real thing instead.
    """
    text = path.read_text(encoding="utf-8")
    for old, new in (substitutions or {}).items():
        text = text.replace(old, new)
    matches = [s for s in split_statements(text) if marker in s]
    if not matches:
        raise AssertionError(
            "no statement in %s carries the marker %r - the check was renamed or "
            "removed, and the test that depends on it is now vacuous"
            % (path.name, marker))
    if len(matches) > 1:
        raise AssertionError(
            "the marker %r matches %d statements in %s; make it unambiguous"
            % (marker, len(matches), path.name))
    return translate(matches[0])
