"""Transactional SCD2 effective-change writer for the declared model.

Call on an exclusive writer connection, outside an existing transaction. It splits
late intervals at the actual effective instant, ignores unchanged/replayed input,
and rejects conflicting replacements at an already recorded boundary. This is
effective history, not bitemporal correction. Arbitrary SQL can bypass it.
"""
from datetime import datetime, timezone
from model import ENTITIES

HISTORY = {e.qualified: e for e in ENTITIES if e.history}


def record_change(con, table, kind, count, now):
    """Soft composition: emit aggregate audit evidence when Observability exists."""
    present = con.execute("SELECT count(*) FROM duckdb_tables() WHERE database_name=current_database() AND schema_name='observability' AND table_name='change_event'").fetchone()[0]
    if present:
        con.execute("""INSERT INTO observability.change_event
            SELECT coalesce(max(change_event_id),0)+1,?,?,?,'temporal-writer',?,?,?,?
            FROM observability.change_event""", [table,kind,now,count,now.isoformat(),now,now])


def apply_change(con, table, key, effective, attributes, deleted=False):
    e = HISTORY[table]  # trusted deployment model, never interpolate arbitrary SQL identifiers
    names = [c[0] for c in e.columns]
    if set(attributes) != set(names) - {e.key}:
        raise ValueError("Supply every business attribute except the stable key")
    at = con.execute("SELECT ?::TIMESTAMPTZ", [effective]).fetchone()[0]
    if not con.execute("SELECT isfinite(?::TIMESTAMPTZ)", [effective]).fetchone()[0]:
        raise ValueError("Effective instant must be finite")
    # Normalize inputs through the declared SQL types before change detection:
    # a timestamp string and a returned datetime may represent the same value.
    types = {name: typ.split(" NOT NULL")[0].split(" CHECK")[0] for name, typ, _ in e.columns}
    normalized = con.execute("SELECT " + ",".join("?::"+types[n] for n in attributes), list(attributes.values())).fetchone()
    attributes = dict(zip(attributes, normalized))
    now = datetime.now(timezone.utc)
    con.execute("BEGIN")
    try:
        if e.schema == "domain":
            allocated = con.execute(f"SELECT {e.natural} FROM {table}_keymap WHERE {e.key}=?", [key]).fetchone()
            if allocated is None or allocated[0] != attributes[e.natural]:
                raise ValueError("Allocate the permanent keymap identity before writing history")
        if e.schema == "prediction" and at < con.execute(
            "SELECT ?::TIMESTAMPTZ", [attributes.get("observation_dts", attributes.get("prediction_dts"))]
        ).fetchone()[0]:
            raise ValueError("Feature or prediction cannot be valid before availability")
        existing = con.execute(f"SELECT * FROM {table} WHERE {e.key}=? AND valid_from_dts<=? AND ?<valid_to_dts",
                               [key, at, at])
        found = existing.fetchone()
        old = dict(zip([x[0] for x in existing.description], found)) if found else None
        if old and all(old[n] == attributes[n] for n in attributes) and old["is_deleted"] == deleted:
            con.execute("COMMIT")
            return False
        if old and at == old["valid_from_dts"]:
            raise ValueError("Conflicting correction at an existing boundary; requires an explicit correction policy")
        if e.schema == "prediction" and con.execute(
            f"SELECT count(*) FROM {table} WHERE {e.key}=? AND valid_from_dts>=?", [key, at]
        ).fetchone()[0]:
            raise ValueError("Retrospective feature rewrites require bitemporal storage")
        if old:
            end = old["valid_to_dts"]
            # DuckDB's Python conversion represents infinity as datetime.max;
            # preserve the sentinel via SQL rather than round-tripping that value.
            end = "infinity" if old["is_current"] else end
            con.execute(f"UPDATE {table} SET valid_to_dts=?,is_current=false,updated_dts=? WHERE {e.key}=? AND valid_from_dts=?",
                        [at, now, key, old["valid_from_dts"]])
        else:
            successor = con.execute(f"SELECT min(valid_from_dts) FROM {table} WHERE {e.key}=? AND valid_from_dts>?", [key, at]).fetchone()[0]
            end = successor or "infinity"
        values = {e.key: key, **attributes, "valid_from_dts": at, "valid_to_dts": end,
                  "is_current": end == "infinity", "is_deleted": deleted, "deleted_dts": at if deleted else None,
                  "created_dts": now, "updated_dts": now}
        con.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", list(values.values()))
        record_change(con,table,"UPDATE" if old else "INSERT",2 if old else 1,now)
        con.execute("COMMIT")
        return True
    except Exception:
        con.execute("ROLLBACK")
        raise


def allocate_key(con, entity_name, natural_key):
    """Serial writer allocation under an explicit transaction; never MAX on history.

    Keymaps must never delete rows. A sequence is preferred for a concurrent host;
    this reference serializes allocation and fails/retries a competing transaction.
    """
    e = HISTORY["domain." + entity_name]
    con.execute("BEGIN")
    try:
        found = con.execute(f"SELECT {e.key} FROM {e.qualified}_keymap WHERE {e.natural}=?", [natural_key]).fetchone()
        if found:
            con.execute("COMMIT")
            return found[0]
        key = con.execute(f"SELECT coalesce(max({e.key}),0)+1 FROM {e.qualified}_keymap").fetchone()[0]
        con.execute(f"INSERT INTO {e.qualified}_keymap VALUES (?,?,current_timestamp,current_timestamp)", [key, natural_key])
        record_change(con,e.qualified+"_keymap","INSERT",1,datetime.now(timezone.utc))
        con.execute("COMMIT")
        return key
    except Exception:
        con.execute("ROLLBACK")
        raise
