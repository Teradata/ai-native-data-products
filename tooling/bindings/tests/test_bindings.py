"""Contract and native execution tests for reusable bindings (not product outputs).

Run with Jinja2 and DuckDB installed. Set POSTGRES_TEST_DSN for PostgreSQL tests
against a disposable database, as a role allowed to create roles and extensions.
Every PostgreSQL deployment/test is rolled back; no existing objects are dropped.
"""
import copy
import csv
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import sys
import unittest

REPO=Path(__file__).resolve().parents[3]
PLATFORMS=tuple(p.name for p in sorted((REPO/'examples/it-service-desk-data-product').iterdir()) if (p/'placement.json').exists())
assert PLATFORMS, 'No binding placement inputs found'
sys.path.insert(0,str(REPO))
from tooling.bindings.render import render_product,environment,prepare,qualified
from tooling.bindings.validate import validate,summarize


def itsd(platform):
    root=REPO/'examples/it-service-desk-data-product'
    c=json.loads((root/'bindings/context.json').read_text())
    c.update(json.loads((root/platform/'placement.json').read_text()))
    return c


def unrelated(platform='postgres'):
    """A second, unrelated product. Role names are supplied only to a platform whose binding supports roles."""
    roles=dict(roles=dict(read='lab_reader',agent='lab_agent',admin='lab_admin')) if platform=='postgres' else {}
    return dict(product=dict(id='laboratory',version='2.1',owner='Lab steward',entrypoint='lab_public.v_specimen',validator='lab-checks'),
        modules=['domain','memory'],containers=dict(domain='lab_store',memory='lab_notes',access='lab_public'),
        runtime_memory=False,**roles,
        entities=[dict(module='domain',name='specimen',key='specimen_id',natural_key='accession',keymap='accession_map',allocation='keymap',
                       profile='SCD2_HISTORY',description="A laboratory's specimen, unrelated to IT support.",columns=[
                       dict(name='specimen_id',type='BIGINT',nullable=False,comment='Stable specimen identity.'),
                       dict(name='accession',type='VARCHAR',nullable=False,comment='Accession identifier.'),
                       dict(name='mass',type='DECIMAL(12,4)',nullable=True,comment='Measured mass in grams.')])])


def load_itsd(con,m):
    """Test-only source loading. This is not a deployable product loader or ML pipeline."""
    pg=m['platform']=='postgres';mark='%s' if pg else '?';maps={}
    def insert(table,values,key=None):
        sql=f'INSERT INTO {table} ({",".join(qualified_column(k) for k in values)}) VALUES ({",".join(mark for _ in values)})'
        if key:sql+=' RETURNING '+qualified_column(key)
        cur=con.execute(sql,list(values.values()))
        return cur.fetchone()[0] if key else None
    def qualified_column(n):return '"'+n+'"'
    now=datetime.now(timezone.utc)
    for name,file in [('category','categories'),('agent','agents'),('customer','customers'),('ticket','tickets')]:
        e=next(e for e in m['entities'] if e['module']=='domain' and e['name']==name)
        with (REPO/f'examples/it-service-desk-data-product/data/{file}.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        maps[name]={}
        if name!='category':
            for row in rows:
                maps[name][row[name+'_id']]=insert(qualified(e['schema'],e['keymap']),{e['natural_key']:row[name+'_id']},e['key'])
        for row in rows:
            values={}
            renames={'category_key':'category_id','opened_dts':'created_at','source_updated_dts':'updated_at',
                     'first_response_dts':'first_response_at','resolved_dts':'resolved_at','closed_dts':'closed_at'}
            for c in e['columns']:
                n=c['name']
                if n==e['key']:
                    if name!='category':values[n]=maps[name][row[name+'_id']]
                    continue
                if n==e['natural_key'] and name!='category':values[n]=row[name+'_id'];continue
                val=row.get(renames.get(n,n)) or None
                target={'customer_id':'customer','assigned_agent_id':'agent','category_id':'category','parent_category_id':'category'}.get(n)
                if target and val is not None:val=maps[target][val]
                elif val is not None:
                    if c['type']=='BOOLEAN':val=val.lower()=='true'
                    elif c['type'] in ('INTEGER','BIGINT'):val=int(val)
                    elif c['type']=='TIMESTAMPTZ':val=datetime.fromisoformat(val).replace(tzinfo=timezone.utc)
                values[n]=val
            values.update(created_dts=now,updated_dts=now)
            if e['history']:
                values.update(valid_from_dts=values.get('opened_dts','2020-01-01T00:00:00Z'),valid_to_dts='infinity',is_current=True)
            if e['bitemporal']:values.update(transaction_from_dts='2026-07-01T00:00:00Z',transaction_to_dts='infinity')
            if e['supports_deletion']:values.update(is_deleted=False,deleted_dts=None)
            key=insert(e['qualified'],values,e['key'])
            if name=='category':maps[name][row['category_id']]=key
    return maps


def standalone_inputs(platform):
    """Inputs for the templates a caller renders directly rather than through render_product."""
    c=prepare(itsd(platform),platform)
    keymapped=next(e for e in c['entities'] if e['allocation']=='keymap' and not e.get('is_keymap'))
    history=next(e for e in c['entities'] if e['name']=='ticket')
    row={col['name']:None for col in history['all_columns']}
    return c,keymapped,history,row


def render_standalone(platform,keymapped,history,row,c):
    env=environment(platform)
    allocation=env.get_template('modules/domain/02-key-allocation.sql.j2').render(**dict(c,entity=keymapped,natural_value="T-1'; DROP"))
    maintenance=env.get_template('patterns/temporal-lifecycle-metadata/04-maintenance.sql.j2').render(
        **dict(c,entity=history,stable_key=1,effective_at='2026-01-01',recorded_at='2026-02-01',replacement_rows=[row]))
    return allocation,maintenance


def publish_area(con,marker,m,run_id,producer,scope,summary,completed,gap=None):
    """Test-only: publish an area row the way a producer would, for trust-map consumer cases."""
    values=dict(product_prefix=m['product']['id'],producer_id=producer,run_id=run_id,area_id=f'{run_id}:MODULE:{scope}',
        payload_schema_version='2.1',scope_kind='MODULE',scope_id=scope,**summary,open_gaps=gap,
        recommended_action=None if gap is None else 'rerun',completed_dts=completed,created_dts=completed,updated_dts=completed)
    schema=m['containers']['observability']
    con.execute(f'INSERT INTO "{schema}"."validation_area" ({",".join(values)}) VALUES ({",".join(marker for _ in values)})',list(values.values()))


class Rendering(unittest.TestCase):
    def test_every_template_is_rendered_and_clean(self):
        import re
        from unittest import mock
        from jinja2 import FileSystemLoader
        original=FileSystemLoader.get_source
        for p in PLATFORMS:
            seen=set()
            def spy(loader,env,name,_seen=seen,_p=p):
                if Path(loader.searchpath[0]).name==_p: _seen.add(name)
                return original(loader,env,name)
            with self.subTest(platform=p), mock.patch.object(FileSystemLoader,'get_source',spy):
                files=render_product(itsd(p),p)
                c,keymapped,history,row=standalone_inputs(p)
                allocation,maintenance=render_standalone(p,keymapped,history,row,c)
                self.assertIn('RETURNING',allocation.upper())
                self.assertIn("'T-1''; DROP'",allocation)
                self.assertIn('INSERT INTO',maintenance)
                declared={str(t.relative_to(REPO/'implementation'/p)).replace('\\','/') for t in (REPO/'implementation'/p).rglob('*.sql.j2')}
                self.assertEqual(declared-seen,set(),'Templates no test renders')
                for name,text in files.items():
                    if name.endswith('.sql'):
                        self.assertNotRegex(text,r'\{\{|\{%|\{#',name)
                        self.assertNotIn('None',re.sub(r"'[^']*'",'',text),name)

    def test_cli_refuses_reserved_and_existing_output(self):
        import subprocess,tempfile
        root=REPO/'examples/it-service-desk-data-product'
        for p in PLATFORMS:
            with tempfile.TemporaryDirectory() as tmp:
                cmd=[sys.executable,str(REPO/'tooling/bindings/render.py'),'--platform',p,'--context',str(root/'bindings/context.json'),
                     '--placement',str(root/p/'placement.json'),'--output']
                first=subprocess.run(cmd+[str(Path(tmp)/'out')],capture_output=True,text=True)
                self.assertEqual(first.returncode,0,first.stderr)
                self.assertTrue((Path(tmp)/'out/deploy.sql').is_file() and (Path(tmp)/'out/manifest.json').is_file())
                self.assertNotEqual(subprocess.run(cmd+[str(Path(tmp)/'out')],capture_output=True,text=True).returncode,0)
            self.assertNotEqual(subprocess.run(cmd+[str(REPO/'implementation'/p/'generated')],capture_output=True,text=True).returncode,0)
            self.assertFalse((REPO/'implementation'/p/'generated').exists())

    def test_two_products_and_two_platforms(self):
        for p in PLATFORMS:
            for c in (itsd(p),unrelated(p)):
                with self.subTest(platform=p,product=c['product']['id']):
                    files=render_product(c,p)
                    self.assertNotIn('customer360',files['deploy.sql'].lower())
                    self.assertNotIn('{{',files['deploy.sql'])
                    self.assertTrue(files['deploy.sql'].endswith('COMMIT;\n'))
                    if c['product']['id']=='laboratory':
                        self.assertNotIn('ticket',files['deploy.sql'].lower())
                        self.assertNotIn('CREATE SCHEMA "itsd_',files['deploy.sql'])

    def test_missing_names_and_strict_templates(self):
        from jinja2 import UndefinedError
        with self.assertRaises(UndefinedError):
            environment(PLATFORMS[0]).get_template('patterns/object-placement/01-schemas.sql.j2').render()
        c=unrelated(PLATFORMS[0]);del c['containers']['domain']
        with self.assertRaises(KeyError):render_product(c,PLATFORMS[0])
        c=unrelated(PLATFORMS[0]);c['entities'][0]['profile']='UNDECLARED'
        with self.assertRaises(ValueError):render_product(c,PLATFORMS[0])

    def test_unsupported_role_setting_fails_rather_than_being_ignored(self):
        for p in PLATFORMS:
            if p=='postgres': continue
            c=itsd(p);c['roles']=dict(read='r',agent='a',admin='d')
            with self.subTest(platform=p),self.assertRaisesRegex(ValueError,'Unsupported setting'):
                render_product(c,p)

    def test_module_dependency_and_naming_collisions(self):
        c=itsd(PLATFORMS[0]);c['modules'].remove('domain')
        with self.assertRaises(ValueError):render_product(c,PLATFORMS[0])
        c=unrelated(PLATFORMS[0]);c['entities'].append(copy.deepcopy(c['entities'][0]))
        with self.assertRaises(ValueError):render_product(c,PLATFORMS[0])

    def test_all_profiles_and_different_dimensions(self):
        for p in PLATFORMS:
            c=itsd(p)
            c['searches'][0]['dimensions']=7
            e=next(e for e in c['entities'] if e['module']=='search')
            next(col for col in e['columns'] if col['name']=='embedding')['type']='VECTOR(7)'
            text=render_product(c,p)['deploy.sql']
            self.assertIn('FLOAT[7]' if p=='duckdb' else 'cardinality("embedding")=7',text)
            for profile in ('CURRENT_STATE','EVENT_APPEND_ONLY','OPERATIONAL_LOG','ASSOCIATION_CURRENT','SCD2_HISTORY','ASSOCIATION_SCD2','SCD2_BITEMPORAL'):
                small=unrelated(p);small['entities'][0]['profile']=profile
                self.assertIn('CREATE TABLE',render_product(small,p)['deploy.sql'])


class EngineTests:
    def deploy(self,context):
        files=render_product(context,self.platform)
        sql=files['deploy.sql'].removeprefix('BEGIN;\n').removesuffix('COMMIT;\n')
        self.con.execute(sql)
        return json.loads(files['manifest.json'])

    def test_itsd_rows_and_governed_inventory(self):
        m=self.deploy(itsd(self.platform));load_itsd(self.con,m)
        for name,count in [('ticket',150),('agent',12),('customer',20),('category',15)]:
            self.assertEqual(self.con.execute(f'SELECT count(*) FROM itsd_access.v_{name}').fetchone()[0],count)
        results=validate(self.con,m)
        bad=[r for r in results if r['status']!='PASSED']
        self.assertEqual([r['test_id'] for r in bad],['memory:coverage'])
        # An input brief is not a completed documentation/ML deployment. Preserve gaps.
        self.assertTrue(self.con.execute("SELECT count(*) FROM itsd_access.trust_map WHERE confidence<>'strong'").fetchone()[0])
        self.assertEqual(self.con.execute('SELECT count(*) FROM itsd_access.v_model_prediction').fetchone()[0],0)

    def test_unrelated_minimal_composition_executes(self):
        m=self.deploy(unrelated(self.platform))
        self.con.execute("INSERT INTO lab_store.accession_map(accession) VALUES ('LAB-1')")
        self.con.execute("INSERT INTO lab_store.specimen VALUES (1,'LAB-1',12.5,'2026-01-01','infinity',true,current_timestamp,current_timestamp,false,NULL)")
        self.assertEqual(float(self.con.execute('SELECT mass FROM lab_public.v_specimen').fetchone()[0]),12.5)
        self.assertFalse(any(r['status']=='ERROR' for r in validate(self.con,m)))

    def test_bitemporal_correction_preserves_known_history(self):
        m=self.deploy(itsd(self.platform));load_itsd(self.con,m)
        self.con.execute("UPDATE itsd_domain.ticket SET transaction_to_dts='2026-08-01',is_current=false WHERE ticket_id=1")
        e=next(e for e in m['entities'] if e['name']=='ticket')
        columns=[c['name'] for c in e['all_columns']]
        expr=["'P1'" if n=='priority' else "'2026-08-01'::TIMESTAMPTZ" if n=='transaction_from_dts' else "'infinity'::TIMESTAMPTZ" if n=='transaction_to_dts' else 'true' if n=='is_current' else n for n in columns]
        self.con.execute('INSERT INTO itsd_domain.ticket SELECT '+','.join(expr)+' FROM itsd_domain.ticket WHERE ticket_id=1')
        self.assertEqual(self.con.execute("SELECT priority FROM itsd_domain.at_ticket('2026-07-10'::TIMESTAMPTZ,'2026-07-20'::TIMESTAMPTZ) WHERE ticket_id=1").fetchone()[0],'P4')
        self.assertEqual(self.con.execute("SELECT priority FROM itsd_domain.at_ticket('2026-07-10'::TIMESTAMPTZ,'2026-08-20'::TIMESTAMPTZ) WHERE ticket_id=1").fetchone()[0],'P1')
        check=next(c for c in m['checks'] if c['test_id']=='itsd_domain.ticket:temporal')
        self.assertEqual(self.con.execute(check['sql']).fetchall(),[])

    def test_validation_errors_publish_without_false_success(self):
        m=self.deploy(itsd(self.platform))
        m['checks']=[dict(test_id='broken',scope_kind='MODULE',scope_id='domain',sql='SELECT * FROM missing_table'),
                     dict(test_id='after',scope_kind='MODULE',scope_id='domain',sql='SELECT 1 WHERE false')]
        result=validate(self.con,m)
        self.assertEqual([r['status'] for r in result],['ERROR','PASSED'])
        self.assertEqual(self.con.execute("SELECT confidence FROM itsd_access.trust_map WHERE scope_id='domain'").fetchone()[0],'weak')

    def test_search_dimension_and_authoritative_joinback(self):
        c=itsd(self.platform)
        c['searches'][0]['dimensions']=7
        emb=next(e for e in c['entities'] if e['module']=='search')
        next(col for col in emb['columns'] if col['name']=='embedding')['type']='VECTOR(7)'
        m=self.deploy(c);load_itsd(self.con,m)
        e=next(e for e in m['entities'] if e['module']=='search')
        now=datetime.now(timezone.utc)
        values=dict(embedding_id=1,entity_id=1,entity_kind='TICKET',source_attribute='subject_description',embedding=[1.0]+[0.0]*6,
            embedding_dimensions=7,embedding_model='itsd-text-384',embedding_model_version='configured-at-deployment',generated_dts=now,computation_method='IN_DATABASE',
            valid_from_dts=now,valid_to_dts='infinity',is_current=True,created_dts=now,updated_dts=now,is_deleted=False,deleted_dts=None)
        marker='%s' if self.platform=='postgres' else '?'
        self.con.execute(f'INSERT INTO {e["qualified"]} ({",".join(values)}) VALUES ({",".join(marker for _ in values)})',list(values.values()))
        self.con.execute("UPDATE itsd_domain.ticket SET subject='Authoritative source update' WHERE ticket_id=1")
        row=self.con.execute(f'SELECT entity_id,subject FROM itsd_search.similar_tickets({marker}::DOUBLE PRECISION[],3)',[[1.0]+[0.0]*6]).fetchone()
        self.assertEqual(row,(1,'Authoritative source update'))

    def test_minimal_domain_without_soft_dependencies(self):
        c=unrelated(self.platform);c['modules']=['domain'];c['containers'].pop('memory')
        m=self.deploy(c)
        self.assertEqual(m['modules'],['domain'])
        self.assertFalse(any(r['status']!='PASSED' for r in validate(self.con,m)))

    marker=property(lambda self:'%s' if self.platform=='postgres' else '?')

    def scalar(self,sql):
        return self.con.execute(sql).fetchall()

    def test_shared_trust_cases_producer_and_sql_consumer(self):
        cases=json.loads((Path(__file__).parent/'trust_cases.json').read_text())
        m=self.deploy(itsd(self.platform));base=datetime.now(timezone.utc)
        for i,case in enumerate(cases):
            summary=summarize(case['expected'],[dict(status=s,severity=v) for s,v in case['outcomes']])
            self.assertEqual((summary['area_status'],summary['confidence']),(case['area_status'],case['confidence']),case['name'])
            validate(self.con,dict(m,checks=[]),run_id=f'fixture-{i}')
            gap=None if summary['confidence']=='strong' else 'fixture gap'
            publish_area(self.con,self.marker,m,f'fixture-{i}',m['product']['validator'],'fixture-area',summary,base+timedelta(seconds=i),gap)
            self.assertEqual(self.scalar("SELECT area_status,confidence FROM itsd_access.trust_map WHERE scope_id='fixture-area'"),
                             [(case['area_status'],case['confidence'])],case['name'])

    def test_append_failures_errors_and_warning_severity(self):
        m=self.deploy(itsd(self.platform))
        results=validate(self.con,dict(m,checks=[dict(test_id='t-fail',scope_kind='MODULE',scope_id='domain',sql='SELECT 1'),
                                               dict(test_id='t-error',scope_kind='MODULE',scope_id='search',sql='SELECT * FROM missing_table')]))
        self.assertEqual([r['status'] for r in results],['FAILED','ERROR'])
        self.assertEqual(self.scalar('SELECT trust_status,failed_count,error_count FROM itsd_observability.validation_run'),[('UNTRUSTED',1,1)])
        self.assertEqual(self.scalar("SELECT row_count,error_message IS NULL FROM itsd_observability.validation_check WHERE test_id='t-fail'"),[(1,True)])
        validate(self.con,dict(m,checks=[dict(test_id='t-warn',scope_kind='MODULE',scope_id='domain',sql='SELECT 1',severity='WARNING')]))
        self.assertEqual(self.scalar("SELECT confidence FROM itsd_access.trust_map WHERE scope_id='domain'"),[('partial',)])
        self.assertEqual(self.scalar('SELECT count(*) FROM itsd_observability.validation_run'),[(2,)])

    def test_latest_evidence_per_area_and_staleness(self):
        m=self.deploy(itsd(self.platform));now=datetime.now(timezone.utc);producer=m['product']['validator']
        strong=summarize(1,[dict(status='PASSED',severity='ERROR')])
        validate(self.con,dict(m,checks=[]),run_id='first');validate(self.con,dict(m,checks=[]),run_id='second')
        publish_area(self.con,self.marker,m,'first',producer,'fixture-a',strong,now)
        publish_area(self.con,self.marker,m,'second',producer,'fixture-b',strong,now+timedelta(seconds=1))
        self.assertEqual(self.scalar("SELECT confidence FROM itsd_access.trust_map WHERE scope_id IN ('fixture-a','fixture-b') ORDER BY scope_id"),[('strong',),('strong',)])
        self.con.execute("UPDATE itsd_observability.validation_run SET evidence_expires_dts=current_timestamp-INTERVAL '1 day' WHERE run_id='first'")
        self.assertEqual(self.scalar("SELECT confidence FROM itsd_access.trust_map WHERE scope_id IN ('fixture-a','fixture-b') ORDER BY scope_id"),[('unknown',),('strong',)])

    def test_designated_producer_and_cautious_fallback(self):
        m=self.deploy(itsd(self.platform));now=datetime.now(timezone.utc);producer=m['product']['validator']
        good=summarize(1,[dict(status='PASSED',severity='ERROR')]);bad=summarize(1,[dict(status='FAILED',severity='ERROR')])
        validate(self.con,dict(m,checks=[]),run_id='ours')
        validate(self.con,dict(m,product=dict(m['product'],validator='other-producer'),checks=[]),run_id='other')
        publish_area(self.con,self.marker,m,'ours',producer,'fixture-p',good,now)
        publish_area(self.con,self.marker,m,'other','other-producer','fixture-p',bad,now+timedelta(seconds=1),'other gap')
        self.assertEqual(self.scalar("SELECT confidence FROM itsd_access.trust_map WHERE scope_id='fixture-p'"),[('strong',)])
        self.con.execute("UPDATE itsd_semantic.data_product_registry SET trust_authoritative_producer=''")
        row=self.scalar("SELECT confidence,recommended_action FROM itsd_access.trust_map WHERE scope_id='fixture-p'")[0]
        self.assertEqual(row[0],'weak');self.assertIn('cautious',row[1])

    def test_mutations_are_detected(self):
        m=self.deploy(itsd(self.platform));load_itsd(self.con,m)
        def failing(test_id):
            check=next(c for c in m['checks'] if c['test_id']==test_id)
            return self.con.execute(check['sql']).fetchall()
        self.assertEqual(failing('itsd_domain.ticket:metadata'),[]);self.assertEqual(failing('semantic:coverage'),[])
        self.con.execute('CREATE TABLE itsd_domain.stray(x INTEGER)')
        self.assertTrue(failing('semantic:coverage'))
        self.con.execute("COMMENT ON COLUMN itsd_domain.ticket.subject IS ''")
        self.assertTrue(failing('itsd_domain.ticket:metadata'))
        relationship=next(c for c in m['checks'] if c['test_id']=='domain.ticket:customer_id')
        self.assertEqual(self.con.execute(relationship['sql']).fetchall(),[])
        self.con.execute("UPDATE itsd_domain.customer SET is_deleted=true,deleted_dts=current_timestamp WHERE customer_id=1")
        self.assertTrue(self.con.execute(relationship['sql']).fetchall())

    def test_overlapping_history_is_detected(self):
        m=self.deploy(unrelated(self.platform))
        self.con.execute("INSERT INTO lab_store.accession_map(accession) VALUES ('LAB-1')")
        for frm,to,cur in (('2025-01-01','2025-02-01',False),('2025-02-01','infinity',True)):
            self.con.execute(f"INSERT INTO lab_store.specimen VALUES (1,'LAB-1',1.5,'{frm}','{to}',{cur},current_timestamp,current_timestamp,false,NULL)")
        check=next(c for c in m['checks'] if c['test_id']=='lab_store.specimen:temporal')
        self.assertEqual(self.con.execute(check['sql']).fetchall(),[])
        self.con.execute("UPDATE lab_store.specimen SET valid_to_dts='2025-02-10' WHERE valid_from_dts='2025-01-01'")
        self.assertTrue(self.con.execute(check['sql']).fetchall())

    def test_active_lineage_and_runtime_privacy_metadata(self):
        self.deploy(itsd(self.platform))
        for i,(src,dst,job) in enumerate((('src.a','stage.a','load_a'),('stage.a','mart.a','build_a'))):
            self.con.execute(f"INSERT INTO itsd_observability.data_lineage VALUES ({i+1},'{src}','{dst}','{job}','sql',true,current_timestamp,NULL,current_timestamp,current_timestamp)")
        self.assertEqual(self.scalar('SELECT count(*) FROM itsd_access.lineage_graph'),[(4,)])
        self.con.execute('UPDATE itsd_observability.data_lineage SET is_active=false,retired_dts=current_timestamp WHERE lineage_id=1')
        self.assertEqual(self.scalar('SELECT count(*) FROM itsd_access.lineage_graph'),[(2,)])
        self.assertEqual(self.scalar("SELECT count(*) FROM itsd_semantic.access_object WHERE represents_entity='itsd_memory.agent_session' AND is_agent_consumable"),[(0,)])
        with self.assertRaises(Exception):
            self.con.execute("INSERT INTO itsd_memory.agent_session (session_id,session_key,agent_key,user_key,session_start_dts,session_status,session_goal,scope_level,scope_identifier,created_dts,updated_dts) VALUES (1,'s','a','u',current_timestamp,'ACTIVE','g','USER',NULL,current_timestamp,current_timestamp)")

    def test_relationship_paths_use_declared_joins(self):
        self.deploy(itsd(self.platform))
        direct=self.scalar("SELECT join_path FROM itsd_access.relationship_paths WHERE source_entity='itsd_domain.ticket' AND target_entity='itsd_domain.customer' AND hops=1")
        self.assertEqual(direct,[('itsd_domain.ticket.customer_id = itsd_domain.customer.customer_id',)])
        self.assertTrue(self.scalar("SELECT 1 FROM itsd_access.relationship_paths WHERE source_entity='itsd_domain.customer' AND target_entity='itsd_domain.agent' AND hops=2"))


@unittest.skipUnless('duckdb' in PLATFORMS,'DuckDB binding is on a separate branch')
class DuckDB(EngineTests,unittest.TestCase):
    platform='duckdb'
    def setUp(self):
        try:import duckdb
        except ImportError:self.skipTest('Install DuckDB for native tests')
        self.con=duckdb.connect()
        self.addCleanup(self.con.close)


@unittest.skipUnless('postgres' in PLATFORMS and os.environ.get('POSTGRES_TEST_DSN'),'Set POSTGRES_TEST_DSN for native PostgreSQL tests')
class PostgreSQL(EngineTests,unittest.TestCase):
    platform='postgres'
    def setUp(self):
        import psycopg
        self.con=psycopg.connect(os.environ['POSTGRES_TEST_DSN'],autocommit=True)
        self.addCleanup(self.con.close)
        self.tx=self.con.transaction(force_rollback=True);self.tx.__enter__()
        self.addCleanup(self.tx.__exit__,None,None,None)

    def test_consumer_role_denies_base_tables_and_history(self):
        import psycopg
        self.deploy(itsd('postgres'))
        self.con.execute('SET LOCAL ROLE itsd_role_read')
        self.assertEqual(self.con.execute('SELECT count(*) FROM itsd_access.v_ticket').fetchone()[0],0)
        for sql in ['SELECT * FROM itsd_domain.ticket', 'SELECT * FROM itsd_memory.agent_session',
                    "SELECT * FROM itsd_domain.at_ticket(current_timestamp,current_timestamp)"]:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.con.transaction():self.con.execute(sql)

    def test_runtime_scopes_use_authenticated_login(self):
        import psycopg
        self.deploy(itsd('postgres'))
        self.con.execute('CREATE ROLE binding_test_user LOGIN')
        self.con.execute('GRANT itsd_role_agent TO binding_test_user')
        self.con.execute("INSERT INTO itsd_memory.agent_session VALUES (1,'s','a','u',current_timestamp,NULL,'ACTIVE','Investigate process','{}','USER','binding_test_user',current_timestamp,current_timestamp)")
        self.con.execute('SET SESSION AUTHORIZATION binding_test_user')
        try:
            self.assertEqual(self.con.execute('SELECT count(*) FROM itsd_memory.agent_session').fetchone()[0],1)
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.con.transaction():self.con.execute("UPDATE itsd_memory.agent_session SET scope_identifier='somebody_else'")
        finally:self.con.execute('RESET SESSION AUTHORIZATION')


if __name__=='__main__':unittest.main()
