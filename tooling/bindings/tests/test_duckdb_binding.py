"""DuckDB behaviour of the Jinja binding, driven only by the generic tooling.

These tests render implementation/duckdb with tooling/bindings/render.py and execute the
result on an actual DuckDB engine. They replace the bespoke compiler tests this binding used
to carry. They skip only when the duckdb driver is not installed, and a skip is a gap.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parent))
from test_bindings import REPO,PLATFORMS,itsd,unrelated,load_itsd,render_product,environment  # noqa: E402
from tooling.bindings.render import prepare  # noqa: E402
from tooling.bindings.validate import validate  # noqa: E402

try:
    import duckdb
except ImportError:  # pragma: no cover - environment without the driver
    duckdb=None


def deploy(con,context):
    files=render_product(context,'duckdb')
    con.execute(files['deploy.sql'].removeprefix('BEGIN;\n').removesuffix('COMMIT;\n'))
    return json.loads(files['manifest.json'])


def plan_change(rows,key,at,attrs,deleted=False):
    """Test-only planner for one stable key of an SCD2_HISTORY entity.

    rows are the existing versions as dicts with ISO-style strings ('infinity' is open). It returns the complete
    replacement rows for the affected segment, or None for an unchanged replay, and rejects a conflicting
    correction at an existing boundary. A real product plans this in its own loader; the binding only
    renders the maintenance statements.
    """
    cover=[r for r in rows if r['valid_from_dts']<=at<r['valid_to_dts']]
    old=cover[0] if cover else None
    if old and all(old[k]==v for k,v in attrs.items()) and old['is_deleted']==deleted: return None
    if old and at==old['valid_from_dts']: raise ValueError('Conflicting correction at an existing boundary')
    later=[r['valid_from_dts'] for r in rows if r['valid_from_dts']>at]
    end=old['valid_to_dts'] if old else (min(later) if later else 'infinity')
    new=dict(old or {},**attrs,valid_from_dts=at,valid_to_dts=end,is_current=end=='infinity',is_deleted=deleted,
             deleted_dts=at if deleted else None)
    return [new]


@unittest.skipUnless('duckdb' in PLATFORMS,'No DuckDB placement input')
@unittest.skipIf(duckdb is None,'Install duckdb for native tests')
class DuckDBBehaviour(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect()
        self.addCleanup(self.con.close)
        self.con.execute("SET TimeZone='UTC'")

    def rows(self,sql):
        return self.con.execute(sql).fetchall()

    def specimen_versions(self):
        return [dict(zip(('valid_from_dts','valid_to_dts','accession','mass','is_deleted'),r)) for r in self.rows(
            "SELECT valid_from_dts::VARCHAR,valid_to_dts::VARCHAR,accession,mass::DOUBLE,is_deleted FROM lab_store.specimen WHERE specimen_id=1 ORDER BY valid_from_dts")]

    def maintain(self,context,entity,rows,key=1,effective='2025-01-01',recorded='2025-01-01'):
        c=standalone_inputs_for(context)
        e=next(x for x in c['entities'] if x['identity']==entity)
        names=[col['name'] for col in e['all_columns']]
        full=[{n:r.get(n) for n in names}|{e['key']:key,'created_dts':'2025-01-01','updated_dts':'2025-01-01'} for r in rows]
        sql=environment('duckdb').get_template('patterns/temporal-lifecycle-metadata/04-maintenance.sql.j2').render(
            **dict(c,entity=e,stable_key=key,effective_at=effective,recorded_at=recorded,replacement_rows=full))
        self.con.execute('BEGIN')
        try:
            self.con.execute(sql);self.con.execute('COMMIT')
        except Exception:
            self.con.execute('ROLLBACK');raise

    def allocate(self,context,natural):
        c=standalone_inputs_for(context)
        e=next(x for x in c['entities'] if x['name']=='specimen' and not x.get('is_keymap'))
        sql=environment('duckdb').get_template('modules/domain/02-key-allocation.sql.j2').render(**dict(c,entity=e,natural_value=natural))
        self.con.execute('BEGIN')
        key=self.con.execute(sql).fetchone()[0]
        self.con.execute('COMMIT')
        return key

    def test_persistent_file_close_reopen_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'itsd.duckdb')
            con=duckdb.connect(path)
            m=deploy(con,itsd('duckdb'));load_itsd(con,m)
            con.execute("INSERT INTO itsd_search.entity_embedding VALUES (1,1,'TICKET','subject_description',?::FLOAT[384],384,'itsd-text-384','configured-at-deployment',current_timestamp,'IN_DATABASE','2026-01-01','infinity',true,current_timestamp,current_timestamp,false,NULL)",[[1.0]+[0.0]*383])
            con.execute('CHECKPOINT');con.close()
            reopened=duckdb.connect(path,read_only=True)
            try:
                self.assertEqual(reopened.execute('SELECT count(*) FROM itsd_access.v_ticket').fetchone()[0],150)
                hit=reopened.execute('SELECT entity_id,similarity FROM itsd_search.similar_tickets(?::DOUBLE[],2)',[[1.0]+[0.0]*383]).fetchone()
                self.assertEqual(hit[0],1);self.assertAlmostEqual(hit[1],1.0,places=5)
                with self.assertRaises(duckdb.InvalidInputException):
                    reopened.execute('DELETE FROM itsd_domain.ticket')
            finally:
                reopened.close()

    def test_no_optional_extension_is_required(self):
        text=render_product(itsd('duckdb'),'duckdb')['deploy.sql'].lower()
        self.assertNotRegex(text,r'(?m)^\s*(install|load|attach)\b')
        for banned in ('vss','hnsw','httpfs','read_parquet'): self.assertNotIn(banned,text)
        m=deploy(self.con,itsd('duckdb'))
        self.assertEqual(self.rows("SELECT count(*) FROM duckdb_extensions() WHERE extension_name='vss' AND loaded"),[(0,)])
        self.assertTrue(m['checks'])

    def test_fixed_size_vector_rejects_wrong_dimension(self):
        c=itsd('duckdb');c['searches'][0]['dimensions']=3
        next(col for e in c['entities'] if e['module']=='search' for col in e['columns'] if col['name']=='embedding')['type']='VECTOR(3)'
        deploy(self.con,c)
        insert="INSERT INTO itsd_search.entity_embedding VALUES (?,1,'TICKET','subject_description',?,3,'itsd-text-384','configured-at-deployment',current_timestamp,'IN_DATABASE','2026-01-01','infinity',true,current_timestamp,current_timestamp,false,NULL)"
        self.con.execute(insert,[1,[1.0,0.0,0.0]])
        with self.assertRaises(duckdb.Error):
            self.con.execute(insert,[2,[1.0,0.0]])
        self.assertEqual(self.rows('SELECT count(*) FROM itsd_search.entity_embedding'),[(1,)])

    def test_half_open_asof_and_consumer_surface_hides_lifecycle(self):
        deploy(self.con,unrelated('duckdb'))
        self.con.execute("INSERT INTO lab_store.accession_map(accession) VALUES ('LAB-1')")
        for frm,to,cur,mass in (('2025-01-01','2025-02-01',False,1.0),('2025-02-01','infinity',True,2.0)):
            self.con.execute(f"INSERT INTO lab_store.specimen VALUES (1,'LAB-1',{mass},'{frm}','{to}',{cur},current_timestamp,current_timestamp,false,NULL)")
        asof=lambda t:self.rows(f"SELECT mass::DOUBLE FROM lab_store.at_specimen('{t}'::TIMESTAMPTZ) WHERE specimen_id=1")
        self.assertEqual(asof('2025-01-31 23:59:59.999999+00'),[(1.0,)])
        self.assertEqual(asof('2025-02-01 00:00:00+00'),[(2.0,)])
        self.assertEqual(asof('2024-12-31 00:00:00+00'),[])
        columns=[r[0] for r in self.rows('DESCRIBE lab_public.v_specimen')]
        for hidden in ('is_deleted','updated_dts','created_dts','valid_to_dts','is_current'): self.assertNotIn(hidden,columns)

    def test_every_history_surface_executes(self):
        m=deploy(self.con,itsd('duckdb'))
        for e in m['entities']:
            if not e['history']: continue
            args="'2026-01-01'::TIMESTAMPTZ"+(",'2026-01-01'::TIMESTAMPTZ" if e['bitemporal'] else '')
            self.rows(f'SELECT * FROM "{e["schema"]}"."{e["history_function"]}"({args})')

    def test_key_allocation_is_permanent_and_idempotent(self):
        deploy(self.con,unrelated('duckdb'))
        first=self.allocate(unrelated('duckdb'),'LAB-1');second=self.allocate(unrelated('duckdb'),'LAB-2')
        self.assertEqual((first,self.allocate(unrelated('duckdb'),'LAB-1'),second),(1,1,2))
        self.assertEqual(self.allocate(unrelated('duckdb'),'LAB-2'),2)
        third=self.allocate(unrelated('duckdb'),'LAB-3')
        # A replayed allocation may consume a sequence value: identifiers are unique and never reused, not contiguous.
        self.assertGreater(third,second)
        self.assertEqual(self.allocate(unrelated('duckdb'),'LAB-3'),third)
        self.assertEqual(self.rows('SELECT count(*) FROM lab_store.accession_map'),[(3,)])
        with self.assertRaises(duckdb.ConstraintException):
            self.con.execute("INSERT INTO lab_store.specimen VALUES (9,'NOT-ALLOCATED',1,'2025-01-01','infinity',true,current_timestamp,current_timestamp,false,NULL)")

    def test_effective_history_replay_late_change_delete_restore(self):
        context=unrelated('duckdb');m=deploy(self.con,context)
        key=self.allocate(context,'LAB-1')
        initial=dict(accession='LAB-1',mass=10.0)
        self.maintain(context,'lab_store.specimen',plan_change([],key,'2025-01-01 00:00:00+00',initial))
        self.assertIsNone(plan_change(self.specimen_versions(),key,'2025-03-01 00:00:00+00',dict(initial)))
        changed=dict(initial,mass=12.0)
        self.maintain(context,'lab_store.specimen',plan_change(self.specimen_versions(),key,'2025-03-01 00:00:00+00',changed),effective='2025-03-01 00:00:00+00')
        self.assertIsNone(plan_change(self.specimen_versions(),key,'2025-03-01 00:00:00+00',changed))
        late=dict(initial,mass=11.0)
        self.maintain(context,'lab_store.specimen',plan_change(self.specimen_versions(),key,'2025-02-01 00:00:00+00',late),effective='2025-02-01 00:00:00+00')
        asof=lambda t:self.rows(f"SELECT mass::DOUBLE FROM lab_store.at_specimen('{t}'::TIMESTAMPTZ) WHERE specimen_id=1")
        self.assertEqual([asof(t) for t in ('2025-01-15 00:00:00+00','2025-02-15 00:00:00+00','2025-03-15 00:00:00+00')],[[(10.0,)],[(11.0,)],[(12.0,)]])
        with self.assertRaises(ValueError):
            plan_change(self.specimen_versions(),key,'2025-03-01 00:00:00+00',dict(initial,mass=99.0))
        self.maintain(context,'lab_store.specimen',plan_change(self.specimen_versions(),key,'2025-04-01 00:00:00+00',changed,deleted=True),effective='2025-04-01 00:00:00+00')
        self.assertEqual(self.rows('SELECT specimen_id FROM lab_public.v_specimen'),[])
        self.maintain(context,'lab_store.specimen',plan_change(self.specimen_versions(),key,'2025-05-01 00:00:00+00',changed),effective='2025-05-01 00:00:00+00')
        self.assertEqual(self.rows('SELECT specimen_id FROM lab_public.v_specimen'),[(1,)])
        check=next(c for c in m['checks'] if c['test_id']=='lab_store.specimen:temporal')
        self.assertEqual(self.rows(check['sql']),[])
        self.assertEqual(self.rows('SELECT count(*) FROM lab_store.specimen WHERE is_current'),[(1,)])

    def test_failed_maintenance_rolls_back(self):
        context=unrelated('duckdb');deploy(self.con,context);key=self.allocate(context,'LAB-1')
        self.maintain(context,'lab_store.specimen',plan_change([],key,'2025-01-01 00:00:00+00',dict(accession='LAB-1',mass=10.0)))
        before=self.specimen_versions()
        bad=dict(accession='OTHER',mass=1.0)
        with self.assertRaises(duckdb.Error):
            self.maintain(context,'lab_store.specimen',plan_change(before,key,'2025-02-01 00:00:00+00',bad),effective='2025-02-01 00:00:00+00')
        self.assertEqual(self.specimen_versions(),before)

    def test_bitemporal_maintenance_keeps_known_history(self):
        context=unrelated('duckdb');context['entities'][0]['profile']='SCD2_BITEMPORAL'
        m=deploy(self.con,context);key=self.allocate(context,'LAB-1')
        common=dict(accession='LAB-1',valid_from_dts='2025-01-01',valid_to_dts='infinity',is_current=True,is_deleted=False,deleted_dts=None)
        self.maintain(context,'lab_store.specimen',[dict(common,mass=10.0,transaction_from_dts='2025-01-01',transaction_to_dts='infinity')],recorded='2025-01-01')
        self.maintain(context,'lab_store.specimen',[dict(common,mass=12.0,transaction_from_dts='2025-03-01',transaction_to_dts='infinity')],recorded='2025-03-01')
        known=lambda t:self.rows(f"SELECT mass::DOUBLE FROM lab_store.at_specimen('2025-02-01'::TIMESTAMPTZ,'{t}'::TIMESTAMPTZ)")
        self.assertEqual((known('2025-02-01'),known('2025-04-01')),([(10.0,)],[(12.0,)]))
        self.assertEqual(self.rows('SELECT count(*) FROM lab_store.specimen'),[(2,)])
        check=next(c for c in m['checks'] if c['test_id']=='lab_store.specimen:temporal')
        self.assertEqual(self.rows(check['sql']),[])

    def test_declared_compositions_execute_with_only_their_dependencies(self):
        for modules in (['domain'],['domain','memory'],['domain','semantic'],['domain','observability'],['domain','search'],
                        ['domain','prediction'],['domain','semantic','observability']):
            with self.subTest(modules=modules):
                con=duckdb.connect()
                try:
                    c=itsd('duckdb');c['modules']=[m for m in c['modules'] if m in modules]
                    c['entities']=[e for e in c['entities'] if e['module'] in modules]
                    if 'search' not in modules: c['searches']=[]
                    c['relationships']=[r for r in c['relationships'] if r['source'].split('.')[0] in modules and r['target'].split('.')[0] in modules]
                    c['documentation']=[d for d in c['documentation'] if d['module'] in modules]
                    c['runtime_memory']='memory' in modules
                    m=deploy(con,c)
                    schemas={r[0] for r in con.execute("SELECT schema_name FROM duckdb_schemas() WHERE database_name=current_database() AND schema_name LIKE 'itsd_%'").fetchall()}
                    self.assertEqual(schemas,{c['containers'][x] for x in modules}|{c['containers']['access']})
                    self.assertEqual(m['modules'],c['modules'])
                    results=validate(con,m)
                    self.assertFalse([r['test_id'] for r in results if r['status']=='ERROR'])
                finally:
                    con.close()

    def test_cli_validate_appends_evidence_and_reports_gaps(self):
        root=REPO/'examples/it-service-desk-data-product'
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'product'
            subprocess.run([sys.executable,str(REPO/'tooling/bindings/render.py'),'--platform','duckdb','--context',str(root/'bindings/context.json'),
                            '--placement',str(root/'duckdb/placement.json'),'--output',str(out)],check=True,capture_output=True)
            database=str(Path(tmp)/'itsd.duckdb')
            con=duckdb.connect(database)
            con.execute((out/'deploy.sql').read_text(encoding='utf-8').removeprefix('BEGIN;\n').removesuffix('COMMIT;\n'));con.close()
            run=subprocess.run([sys.executable,str(REPO/'tooling/bindings/validate.py'),str(out/'manifest.json'),'--database',database],capture_output=True,text=True)
            self.assertEqual(run.returncode,1,run.stderr)
            self.assertIn('memory:coverage',run.stdout)
            con=duckdb.connect(database,read_only=True)
            try:
                self.assertEqual(con.execute('SELECT payload_schema_version,source_format,trust_status FROM itsd_observability.validation_run').fetchall(),[('2.1','NATIVE','UNTRUSTED')])
                self.assertEqual(con.execute("SELECT confidence FROM itsd_access.trust_map WHERE scope_id='access-layer'").fetchall(),[('unknown',)])
                self.assertEqual(con.execute("SELECT confidence FROM itsd_access.trust_map WHERE scope_id='domain'").fetchall(),[('strong',)])
            finally:
                con.close()
            self.assertNotEqual(subprocess.run([sys.executable,str(REPO/'tooling/bindings/validate.py'),str(out/'manifest.json'),'--database',str(Path(tmp)/'missing.duckdb')],capture_output=True).returncode,0)


def standalone_inputs_for(context):
    return prepare(context,'duckdb')


if __name__=='__main__':unittest.main()
