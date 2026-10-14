"""Render reusable DuckDB/PostgreSQL bindings from explicit product inputs.

This helper normalises context and checks contracts. SQL belongs in platform
Jinja templates, not in this Python module. It never connects to a database.
"""
import argparse
import copy
import json
from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined

REPO = Path(__file__).resolve().parents[2]
ORDER = ('memory','semantic','domain','observability','search','prediction')
PROFILES = {'CURRENT_STATE','EVENT_APPEND_ONLY','OPERATIONAL_LOG','ASSOCIATION_CURRENT',
            'SCD2_HISTORY','ASSOCIATION_SCD2','SCD2_BITEMPORAL'}
TEMPORAL = {
    'created_dts': ('TIMESTAMPTZ','Physical row creation instant.'),
    'updated_dts': ('TIMESTAMPTZ','Physical row last-change instant.'),
    'valid_from_dts': ('TIMESTAMPTZ','Inclusive business validity start.'),
    'valid_to_dts': ('TIMESTAMPTZ','Exclusive business validity end; infinity is open.'),
    'transaction_from_dts': ('TIMESTAMPTZ','Inclusive knowledge-time start.'),
    'transaction_to_dts': ('TIMESTAMPTZ','Exclusive knowledge-time end; infinity is open.'),
    'is_current': ('BOOLEAN','Both applicable temporal axes are open.'),
    'is_deleted': ('BOOLEAN','Logical deletion tombstone; retained in history.'),
    'deleted_dts': ('TIMESTAMPTZ','Deletion instant; null before deletion.'),
}


def ident(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,62}',value):
        raise ValueError(f'Invalid identifier: {value!r}')
    return '"'+value+'"'


def literal(value):
    if value is None: return 'NULL'
    if isinstance(value,bool): return 'TRUE' if value else 'FALSE'
    if isinstance(value,(int,float)): return str(value)
    return "'"+str(value).replace("'","''")+"'"


def qualified(schema,name):
    return ident(schema)+'.'+ident(name)


def environment(platform):
    if platform not in ('duckdb','postgres'):
        raise ValueError('Only duckdb and postgres are handled by this renderer')
    env=Environment(loader=FileSystemLoader(REPO/'implementation'/platform),
                    undefined=StrictUndefined,keep_trailing_newline=True,autoescape=False)
    env.filters.update(ident=ident,literal=literal)
    env.globals.update(qualified=qualified)
    return env


def prepare(raw,platform):
    context=copy.deepcopy(raw)
    context['platform']=platform
    product=context['product']
    for field in ('id','version','owner','entrypoint','validator'):
        if not product[field]: raise ValueError(f'product.{field} is required')
    product.setdefault('evidence_days',7)
    modules=context['modules']
    if not modules or len(set(modules))!=len(modules) or set(modules)-set(ORDER):
        raise ValueError('Declare a nonempty unique list of module anchors')
    if any(m in modules for m in ('search','prediction')) and 'domain' not in modules:
        raise ValueError('Search and Prediction require Domain')
    containers=context['containers']
    for module in modules: ident(containers[module])
    ident(containers['access'])
    context['schemas']=list(dict.fromkeys([containers[m] for m in ORDER if m in modules]+[containers['access']]))
    if platform=='postgres':
        for tier in ('read','agent','admin'): ident(context['roles'][tier])
        if len(set(context['roles'].values()))!=3: raise ValueError('Role tiers must be distinct')
    supplied=context.get('entities',[])
    entities=[]
    for module in ORDER:
        if module not in modules: continue
        standard=REPO/'implementation'/platform/'modules'/module/'entities.json'
        if standard.exists():
            for e in json.loads(standard.read_text()):
                if e.get('runtime') and not context.get('runtime_memory',False): continue
                e['module']=module
                entities.append(e)
        entities.extend(e for e in supplied if e['module']==module)
    if any(e['module'] not in modules for e in supplied):
        raise ValueError('An entity belongs to an omitted module')
    seen=set()
    for e in entities:
        e.setdefault('schema',containers[e['module']])
        if e['schema']!=containers[e['module']]: raise ValueError('Entity schema contradicts placement')
        e.setdefault('runtime',False)
        e.setdefault('supports_deletion',e['profile'] in ('SCD2_HISTORY','ASSOCIATION_SCD2','SCD2_BITEMPORAL'))
        e.setdefault('natural_key',None)
        e.setdefault('allocation','supplied')
        e.setdefault('constraints',[])
        e.setdefault('current_view','v_'+e['name'])
        e.setdefault('history_function','at_'+e['name'])
        e['history']=e['profile'] in ('SCD2_HISTORY','ASSOCIATION_SCD2','SCD2_BITEMPORAL')
        e['bitemporal']=e['profile']=='SCD2_BITEMPORAL'
        if e['profile'] not in PROFILES: raise ValueError('Unknown temporal profile')
        for name in (e['name'],e['key'],e['current_view'],e['history_function']): ident(name)
        if not e['description'].strip(): raise ValueError('Every entity needs authored meaning')
        e['qualified']=qualified(e['schema'],e['name'])
        e['identity']=e['schema']+'.'+e['name']
        e['view']=qualified(containers['access'],e['current_view'])
        if e['identity'] in seen: raise ValueError('Duplicate entity identity')
        seen.add(e['identity'])
        if e['allocation']=='keymap':
            ident(e['keymap'])
            if not e['natural_key']: raise ValueError('Keymap requires a natural key')
        elif e['allocation'] not in ('inline','supplied'): raise ValueError('Unknown allocation mode')
        names=[]
        for col in e['columns']:
            ident(col['name']); names.append(col['name'])
            if not col['comment'].strip(): raise ValueError('Every column needs authored meaning')
            if col['name'] in TEMPORAL: raise ValueError('Temporal columns are supplied by the shared pattern')
            col.setdefault('nullable',False); col.setdefault('check',None)
            vector=re.fullmatch(r'VECTOR\((\d+)\)',col['type'])
            if vector:
                dim=int(vector[1])
                if not 1<=dim<=65536: raise ValueError('Invalid vector dimension')
                col['type']=f'FLOAT[{dim}]' if platform=='duckdb' else 'DOUBLE PRECISION[]'
                col['dimensions']=dim
                if platform=='postgres':
                    col['check']=f'array_ndims({ident(col["name"])})=1 AND array_lower({ident(col["name"])},1)=1 AND cardinality({ident(col["name"])})={dim} AND array_position({ident(col["name"])},NULL) IS NULL'
            if not re.fullmatch(r'(BIGINT|INTEGER|BOOLEAN|DATE|TIMESTAMPTZ|VARCHAR(?:\(\d+\))?|TEXT|JSONB?|DOUBLE PRECISION|FLOAT\[\d+\]|DOUBLE PRECISION\[\]|DECIMAL\(\d+,\d+\))',col['type']):
                raise ValueError(f'Unsupported bound type: {col["type"]}')
        if len(names)!=len(set(names)) or e['key'] not in names: raise ValueError('Duplicate columns or missing key')
        if e['natural_key'] and e['natural_key'] not in names: raise ValueError('Missing natural key')
        if e['runtime'] and not {'scope_level','scope_identifier'}<=set(names): raise ValueError('Runtime requires explicit scope')
        temporal=['created_dts','updated_dts']
        if e['history']:
            temporal=['valid_from_dts','valid_to_dts']+(['transaction_from_dts','transaction_to_dts'] if e['bitemporal'] else [])+['is_current']+temporal
        if e['supports_deletion']: temporal+=['is_deleted','deleted_dts']
        e['temporal_columns']=[dict(name=n,type=TEMPORAL[n][0],nullable=n=='deleted_dts',comment=TEMPORAL[n][1]) for n in temporal]
        e['all_columns']=e['columns']+e['temporal_columns']
    views=[e['current_view'] for e in entities if not e['runtime']]
    if len(views)!=len(set(views)): raise ValueError('Consumer view names must be unique in the access schema')
    context['entities']=entities
    # Keymaps are persisted governed entities too; include them in metadata and
    # validation without duplicating their CREATE statements emitted with Domain.
    context['keymaps']=[]
    for e in list(entities):
        if e['allocation']!='keymap': continue
        k=copy.deepcopy(e)
        k.update(name=e['keymap'],profile='CURRENT_STATE',allocation='supplied',history=False,bitemporal=False,
                 description='Permanent natural-key allocation for '+e['name']+'. Never recycle or delete mappings.',
                 supports_deletion=False,columns=[c for c in e['columns'] if c['name'] in (e['key'],e['natural_key'])],
                 temporal_columns=[c for c in e['temporal_columns'] if c['name'] in ('created_dts','updated_dts')],
                 current_view='v_'+e['keymap'],is_keymap=True)
        k['qualified']=qualified(k['schema'],k['name']);k['identity']=k['schema']+'.'+k['name']
        k['view']=qualified(containers['access'],k['current_view'])
        k['all_columns']=k['columns']+k['temporal_columns']
        if k['identity'] in seen or k['current_view'] in views: raise ValueError('Keymap name collides with a declared object')
        seen.add(k['identity']);views.append(k['current_view'])
        entities.append(k);context['keymaps'].append(k)
    context.setdefault('relationships',[])
    by_ref={e['module']+'.'+e['name']:e for e in entities}
    for rel in context['relationships']:
        for side in ('source','target'):
            e=by_ref[rel[side]]
            if rel[side+'_column'] not in [c['name'] for c in e['columns']]: raise ValueError('Relationship column is absent')
            rel[side+'_entity']=e
        rel.setdefault('mandatory',False)
    context.setdefault('documentation',[])
    for doc in context['documentation']:
        if doc['module'] not in modules: raise ValueError('Documentation refers to omitted module')
    context.setdefault('searches',[])
    for search in context['searches']:
        search['source_entity']=by_ref[search['source']]
        search['embedding_entity']=by_ref[search['embedding']]
        for name in (search['name'],search['vector_column']): ident(name)
        if not isinstance(search['dimensions'],int) or not 1<=search['dimensions']<=65536: raise ValueError('Invalid dimensions')
        vector=next((col for col in search['embedding_entity']['columns'] if col['name']==search['vector_column']),None)
        if vector is None or vector.get('dimensions')!=search['dimensions']: raise ValueError('Search dimensions must match the declared vector field')
        if search['source_entity']['module']!='domain' or search['embedding_entity']['module']!='search': raise ValueError('Search must join Search vectors to authoritative Domain')
        for col in search['content_columns']:
            if col not in [c['name'] for c in search['source_entity']['columns']]: raise ValueError('Unknown content column')
    if product['entrypoint'] not in {containers['access']+'.'+e['current_view'] for e in entities if not e['runtime']}:
        raise ValueError('Entrypoint must be a declared consumer view')
    return context


def render_product(raw,platform):
    c=prepare(raw,platform); env=environment(platform)
    def render(path,**extra): return env.get_template(path).render(**dict(c,**extra)).strip()+'\n'
    files={'00-placement.sql':render('patterns/object-placement/01-schemas.sql.j2')}
    for i,module in enumerate(ORDER,1):
        if module not in c['modules']: continue
        files[f'{i:02}-{module}.sql']=render(f'modules/{module}/01-tables.sql.j2',module_entities=[e for e in c['entities'] if e['module']==module and not e.get('is_keymap')])
    files['07-comments.sql']=render('patterns/temporal-lifecycle-metadata/02-comments.sql.j2')
    files['08-views.sql']=render('patterns/temporal-lifecycle-metadata/03-access-views.sql.j2')
    if 'search' in c['modules']: files['09-search.sql']=render('modules/search/02-similarity.sql.j2')
    if 'semantic' in c['modules']:
        files['10-registration.sql']=render('modules/semantic/02-registration.sql.j2')
        files['11-discovery.sql']=render('modules/semantic/03-discovery.sql.j2')
    if 'observability' in c['modules'] and 'semantic' in c['modules']:
        files['12-trust.sql']=render('patterns/validation/04-trust-map.sql.j2')
    if 'memory' in c['modules']: files['13-documentation.sql']=render('modules/memory/02-capture.sql.j2')
    files['14-access.sql']=render('patterns/access-layer/01-grants.sql.j2')
    files['deploy.sql']='BEGIN;\nSET TimeZone=\'UTC\';\n'+''.join(files.values())+'COMMIT;\n'
    checks=[]
    for e in c['entities']:
        for kind in ('metadata','temporal'):
            checks.append(dict(test_id=e['identity']+':'+kind,scope_kind='ENTITY',scope_id=e['identity'],
                               sql=render('patterns/validation/01-entity-check.sql.j2',entity=e,check_kind=kind).rstrip(';\n')))
    for r in c['relationships']:
        checks.append(dict(test_id=r['source']+':'+r['source_column'],scope_kind='MODULE',scope_id=r['source_entity']['module'],
                           sql=render('patterns/validation/02-relationship-check.sql.j2',relationship=r).rstrip(';\n')))
    for module in ('semantic','memory'):
        if module in c['modules']:
            checks.append(dict(test_id=module+':coverage',scope_kind='MODULE',scope_id=module,
                               sql=render(f'modules/{module}/validation.sql.j2').rstrip(';\n')))
    manifest=dict(platform=platform,product=c['product'],containers=c['containers'],modules=c['modules'],
                  entities=c['entities'],relationships=c['relationships'],checks=checks)
    files['manifest.json']=json.dumps(manifest,indent=2)+'\n'
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform',required=True,choices=('duckdb','postgres'))
    parser.add_argument('--context',type=Path,required=True)
    parser.add_argument('--placement',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=json.loads(args.context.read_text(encoding='utf-8'))
    raw.update(json.loads(args.placement.read_text(encoding='utf-8')))
    files=render_product(raw,args.platform)
    out=args.output.resolve()
    for reserved in ('design','implementation','examples','roles','tooling'):
        if out.is_relative_to(REPO/reserved): parser.error('Generated output must be outside the skill corpus (use build/ or another repository)')
    if out.exists() and any(out.iterdir()): parser.error('Output directory must be empty; existing products are never overwritten')
    out.mkdir(parents=True,exist_ok=True)
    for name,text in files.items(): (out/name).write_text(text,encoding='utf-8',newline='\n')
    print(f'Rendered {len(files)} files to {out}; no database was modified.')


if __name__=='__main__': main()
