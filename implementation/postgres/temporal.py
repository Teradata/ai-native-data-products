"""Effective-history writes for trusted maintainers; caller owns connection lifetime.

Nested transactions use savepoints. An advisory lock serializes changes for an
entity identity; database exclusion constraints also reject bypassing writers.
This is not a bitemporal correction API.
"""
from datetime import datetime, timezone
from model import ENTITIES

HISTORY = {e.qualified: e for e in ENTITIES if e.history}


def allocate_key(con, entity_name, natural_key):
    e = HISTORY['domain.' + entity_name]
    with con.transaction():
        return con.execute(
            f'INSERT INTO {e.qualified}_keymap ({e.natural},created_dts,updated_dts) '
            f'VALUES (%s,current_timestamp,current_timestamp) ON CONFLICT ({e.natural}) '
            f'DO UPDATE SET {e.natural}=EXCLUDED.{e.natural} RETURNING {e.key}',
            [natural_key]).fetchone()[0]


def apply_change(con, table, key, effective, attributes, deleted=False):
    e = HISTORY[table]  # identifiers come only from the deployment model
    if set(attributes) != {c[0] for c in e.columns} - {e.key}:
        raise ValueError('Supply every business attribute except the stable key')
    with con.transaction():
        if not con.execute('SELECT isfinite(%s::timestamptz)', [effective]).fetchone()[0]:
            raise ValueError('Effective instant must be finite')
        at = con.execute('SELECT %s::timestamptz', [effective]).fetchone()[0]
        types = {n: t.split(' NOT NULL')[0].split(' CHECK')[0] for n,t,_ in e.columns}
        normalized = con.execute('SELECT '+','.join('%s::'+types[n] for n in attributes), list(attributes.values())).fetchone()
        attributes = dict(zip(attributes,normalized))
        con.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', [table+':'+str(key)])
        if e.schema == 'domain':
            allocated = con.execute(f'SELECT {e.natural} FROM {table}_keymap WHERE {e.key}=%s FOR UPDATE', [key]).fetchone()
            if not allocated or allocated[0] != attributes[e.natural]:
                raise ValueError('Allocate the permanent natural key before writing history')
        if e.schema == 'prediction':
            available = attributes.get('observation_dts', attributes.get('prediction_dts'))
            if at < available:
                raise ValueError('Validity cannot precede feature or prediction availability')
        # Avoid decoding PostgreSQL infinity through the Python datetime adapter.
        selected = ','.join(n for n,_,_ in e.columns)+',valid_from_dts,valid_to_dts::text AS valid_to_dts,is_deleted'
        cur = con.execute(f'SELECT {selected} FROM {table} WHERE {e.key}=%s AND valid_from_dts<=%s AND %s<valid_to_dts FOR UPDATE', [key,at,at])
        found = cur.fetchone()
        old = dict(zip([c.name for c in cur.description],found)) if found else None
        if old and all(old[n] == attributes[n] for n in attributes) and old['is_deleted'] == deleted:
            return False
        if old and old['valid_from_dts'] == at:
            raise ValueError('Conflicting change at an existing boundary')
        if e.schema == 'prediction' and con.execute(
            f'SELECT 1 FROM {table} WHERE {e.key}=%s AND valid_from_dts>=%s', [key,at]
        ).fetchone():
            raise ValueError('Retrospective prediction changes require bitemporal storage')
        now = datetime.now(timezone.utc)
        if old:
            end = old['valid_to_dts']
            con.execute(f'UPDATE {table} SET valid_to_dts=%s,is_current=false,updated_dts=%s WHERE {e.key}=%s AND valid_from_dts=%s', [at,now,key,old['valid_from_dts']])
        else:
            successor = con.execute(f'SELECT min(valid_from_dts)::text FROM {table} WHERE {e.key}=%s AND valid_from_dts>%s', [key,at]).fetchone()[0]
            end = successor or 'infinity'
        values = {e.key:key, **attributes, 'valid_from_dts':at,'valid_to_dts':end,
                  'is_current':end=='infinity','is_deleted':deleted,'deleted_dts':at if deleted else None,
                  'created_dts':now,'updated_dts':now}
        con.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('%s' for _ in values)})", list(values.values()))
        if con.execute("SELECT to_regclass('observability.change_event') IS NOT NULL").fetchone()[0]:
            con.execute('''INSERT INTO observability.change_event
                (table_name,change_type,change_dts,changed_by,records_affected,batch_key,created_dts,updated_dts)
                VALUES (%s,%s,%s,'temporal-writer',%s,%s,%s,%s)''',
                [table,'UPDATE' if old else 'INSERT',now,2 if old else 1,now.isoformat(),now,now])
        return True
