"""Executable violations queries. Each result row is a defect, never a pass flag."""
from dataclasses import dataclass
from model import ENTITIES, MODULES
from render import columns, relationships, literal


@dataclass
class Check:
    test_id: str
    scope_kind: str
    scope_id: str
    sql: str
    severity: str = "ERROR"
    category: str = "STRUCTURAL"


def profile():
    checks = []
    def add(area, name, sql, kind="MODULE", category="STRUCTURAL", severity="ERROR"):
        checks.append(Check("C360-"+name, kind, area, sql, severity, category))
    modules = ",".join("("+literal(m)+")" for m in MODULES)
    add("semantic", "SEM-001", f"SELECT col0 FROM (VALUES {modules}) m(col0) WHERE col0 NOT IN (SELECT module_name FROM semantic.data_product_map)")
    expected_tables = ",".join("("+literal(e.qualified)+")" for e in ENTITIES)
    add("semantic", "SEM-002", f"SELECT col0 FROM (VALUES {expected_tables}) e(col0) WHERE col0 NOT IN (SELECT entity_name FROM semantic.entity_metadata)")
    add("semantic", "SEM-003", """SELECT t.schema_name,t.table_name FROM (SELECT current_database() AS database_name,n.nspname AS schema_name,c.relname AS table_name,  false AS internal FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE c.relkind IN ('r','p') AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) t
        LEFT JOIN semantic.entity_metadata e ON e.container_name=t.schema_name AND e.table_name=t.table_name
        WHERE t.database_name=current_database() AND NOT t.internal AND e.entity_name IS NULL""")
    add("semantic", "SEM-004", """SELECT e.entity_name FROM semantic.entity_metadata e LEFT JOIN (SELECT current_database() AS database_name,n.nspname AS schema_name,c.relname AS table_name,  false AS internal FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE c.relkind IN ('r','p') AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) t
        ON t.database_name=current_database() AND t.schema_name=e.container_name AND t.table_name=e.table_name WHERE t.table_name IS NULL""")
    add("semantic", "SEM-005", """SELECT p.object_identity FROM semantic.primary_object p LEFT JOIN (SELECT current_database() AS database_name,n.nspname AS schema_name,c.relname AS view_name,  false AS internal,pg_catalog.obj_description(c.oid) AS comment  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE c.relkind='v' AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) v
        ON v.database_name=current_database() AND v.schema_name||'.'||v.view_name=p.object_identity WHERE v.view_name IS NULL
        OR p.object_role NOT IN ('AGENT_ENTRYPOINT','ANALYTICAL_QUERY','REFERENCE_LOOKUP','RELATIONSHIP_BRIDGE','LINEAGE_EVIDENCE','OPERATIONAL_METRIC','WRITE_TARGET','INTERNAL_SUPPORT')""")
    add("semantic", "SEM-006", """SELECT a.object_identity FROM semantic.access_object a LEFT JOIN semantic.entity_metadata e ON a.represents_entity=e.entity_name
        WHERE a.access_role<>'COMPOSITE' AND e.entity_name IS NULL
        UNION ALL SELECT composite_object FROM semantic.access_composition GROUP BY composite_object HAVING count(*) FILTER(WHERE member_role='ANCHOR')<>1""")
    add("semantic", "SEM-007", """SELECT a.object_identity FROM semantic.access_object a LEFT JOIN (SELECT current_database() AS database_name,n.nspname AS schema_name,c.relname AS view_name,  false AS internal,pg_catalog.obj_description(c.oid) AS comment  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE c.relkind='v' AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) v
        ON v.database_name=current_database() AND v.schema_name||'.'||v.view_name=a.object_identity
        WHERE a.is_agent_consumable AND v.view_name IS NULL""")
    add("semantic", "SEM-008", """SELECT resource_role FROM semantic.data_product_orientation o LEFT JOIN (SELECT current_database() AS database_name,n.nspname AS schema_name,c.relname AS view_name,  false AS internal,pg_catalog.obj_description(c.oid) AS comment  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE c.relkind='v' AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) v
        ON v.database_name=current_database() AND v.schema_name||'.'||v.view_name=o.object_identity
        WHERE o.is_required AND v.view_name IS NULL""")
    add("semantic", "SEM-009", """SELECT role FROM (VALUES ('MANIFEST'),('TRUST_MAP'),('MODULE_MAP'),('OBJECT_CATALOGUE'),('ENTITY_CATALOGUE'),('COLUMN_CATALOGUE'),('RELATIONSHIP_CATALOGUE')) r(role)
        WHERE NOT EXISTS(SELECT 1 FROM semantic.data_product_orientation o WHERE o.resource_role=r.role AND o.is_required)
        UNION ALL SELECT resource_role FROM semantic.data_product_orientation WHERE resource_role NOT IN ('MANIFEST','TRUST_MAP')
        AND discovery_order <= (SELECT discovery_order FROM semantic.data_product_orientation WHERE resource_role='TRUST_MAP')""")
    add("semantic", "SEM-010", """SELECT entity_name FROM semantic.entity_metadata e WHERE standalone_reason IS NULL AND NOT EXISTS
        (SELECT 1 FROM semantic.table_relationship r WHERE e.entity_name IN (r.source_entity,r.target_entity))""")
    add("semantic", "SEM-011", """SELECT m.metric_name FROM semantic.metric m WHERE NOT EXISTS(SELECT 1 FROM semantic.metric_expression x WHERE x.metric_name=m.metric_name)
        OR (SELECT count(*) FROM semantic.metric_dataset d WHERE d.metric_name=m.metric_name AND d.dataset_role='PRIMARY')<>1
        UNION ALL SELECT d.metric_name FROM semantic.metric_dataset d LEFT JOIN semantic.entity_metadata e ON e.entity_name=d.entity_name WHERE e.entity_name IS NULL""")
    add("semantic", "SEM-012", """SELECT synonym_id FROM semantic.semantic_synonym s WHERE
        (object_kind='ENTITY' AND NOT EXISTS(SELECT 1 FROM semantic.entity_metadata e WHERE e.entity_name=s.object_name)) OR
        (object_kind='COLUMN' AND NOT EXISTS(SELECT 1 FROM semantic.column_metadata c WHERE c.column_metadata_id=s.object_name)) OR
        (object_kind='METRIC' AND NOT EXISTS(SELECT 1 FROM semantic.metric m WHERE m.metric_name=s.object_name)) OR object_kind NOT IN ('ENTITY','COLUMN','METRIC')""")
    add("semantic", "SEM-013", "SELECT product_id FROM semantic.data_product_registry WHERE trust_authoritative_producer IS NULL OR trust_authoritative_producer<>'postgres-reference'")
    add("semantic", "SEM-014", """SELECT represents_entity FROM semantic.access_object WHERE is_agent_consumable AND access_role='PASSTHROUGH'
        GROUP BY represents_entity HAVING count(*)<>1""")
    add("semantic", "SEM-015", """SELECT container_name,table_name,column_name FROM semantic.column_catalogue
        WHERE NOT documentation_covered OR nullif(business_description,'') IS NULL""", category="SEMANTIC")
    add("semantic", "SEM-016", """SELECT v.schema_name,v.view_name FROM (SELECT current_database() AS database_name,n.nspname AS schema_name,c.relname AS view_name,  false AS internal,pg_catalog.obj_description(c.oid) AS comment  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE c.relkind='v' AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) v WHERE v.database_name=current_database()
        AND NOT v.internal AND (nullif(v.comment,'') IS NULL OR NOT EXISTS(SELECT 1 FROM semantic.access_object a
        WHERE a.object_identity=v.schema_name||'.'||v.view_name AND a.is_agent_consumable))""", category="SEMANTIC")
    add("semantic", "SEM-017", """SELECT a.composite_object FROM semantic.access_composition a LEFT JOIN semantic.entity_metadata e
        ON e.entity_name=a.member_entity WHERE e.entity_name IS NULL""")
    # Declared tables/columns, authored descriptions and physical comments, profiles,
    # full/current surfaces, temporal types and actual interval semantics.
    for index, e in enumerate(ENTITIES):
        tag = f"{index:03}"
        add(e.schema, "META-"+tag, f"""SELECT c.column_name FROM (SELECT current_database() AS database_name, n.nspname AS schema_name, c.relname AS table_name,  a.attname AS column_name, pg_catalog.format_type(a.atttypid,a.atttypmod) AS data_type,  NOT a.attnotnull AS is_nullable, pg_catalog.col_description(c.oid,a.attnum) AS comment  FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE a.attnum>0 AND NOT a.attisdropped AND c.relkind IN ('r','v','p')  AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) c LEFT JOIN semantic.column_metadata m
            ON m.container_name=c.schema_name AND m.table_name=c.table_name AND m.column_name=c.column_name
            WHERE c.database_name=current_database() AND c.schema_name='{e.schema}' AND c.table_name='{e.name}'
            AND (nullif(c.comment,'') IS NULL OR nullif(m.business_description,'') IS NULL)""", category="SEMANTIC")
        expected = ",".join("("+literal(n)+")" for n, _, _ in columns(e))
        add("temporal-lifecycle-metadata", "TLM-COLS-"+tag,
            f"SELECT col0 FROM (VALUES {expected}) c(col0) WHERE col0 NOT IN (SELECT column_name FROM (SELECT current_database() AS database_name, n.nspname AS schema_name, c.relname AS table_name,  a.attname AS column_name, pg_catalog.format_type(a.atttypid,a.atttypmod) AS data_type,  NOT a.attnotnull AS is_nullable, pg_catalog.col_description(c.oid,a.attnum) AS comment  FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE a.attnum>0 AND NOT a.attisdropped AND c.relkind IN ('r','v','p')  AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) WHERE database_name=current_database() AND schema_name='{e.schema}' AND table_name='{e.name}')", kind="PATTERN")
        add("temporal-lifecycle-metadata", "TLM-PROFILE-"+tag,
            f"SELECT entity_name FROM semantic.entity_metadata WHERE entity_name='{e.qualified}' AND temporal_pattern<>'{e.profile}'", kind="PATTERN")
        add("temporal-lifecycle-metadata", "TLM-TYPE-"+tag,
            f"SELECT column_name FROM (SELECT current_database() AS database_name, n.nspname AS schema_name, c.relname AS table_name,  a.attname AS column_name, pg_catalog.format_type(a.atttypid,a.atttypmod) AS data_type,  NOT a.attnotnull AS is_nullable, pg_catalog.col_description(c.oid,a.attnum) AS comment  FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE a.attnum>0 AND NOT a.attisdropped AND c.relkind IN ('r','v','p')  AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) WHERE database_name=current_database() AND schema_name='{e.schema}' AND table_name='{e.name}' AND ((right(column_name,4)='_dts' AND data_type<>'timestamp with time zone') OR (left(column_name,3)='is_' AND data_type<>'boolean'))", kind="PATTERN")
        if not e.history:
            add("temporal-lifecycle-metadata", "TLM-PROHIBITED-"+tag,
                f"SELECT column_name FROM (SELECT current_database() AS database_name, n.nspname AS schema_name, c.relname AS table_name,  a.attname AS column_name, pg_catalog.format_type(a.atttypid,a.atttypmod) AS data_type,  NOT a.attnotnull AS is_nullable, pg_catalog.col_description(c.oid,a.attnum) AS comment  FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE a.attnum>0 AND NOT a.attisdropped AND c.relkind IN ('r','v','p')  AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) WHERE database_name=current_database() AND schema_name='{e.schema}' AND table_name='{e.name}' AND column_name IN ('valid_from_dts','valid_to_dts','is_current','is_deleted')", kind="PATTERN")
        else:
            key = e.natural or e.key
            add("temporal-lifecycle-metadata", "TLM-INTERVAL-"+tag,
                f"SELECT {e.key} FROM {e.qualified} WHERE valid_from_dts>=valid_to_dts OR is_current<>(valid_to_dts='infinity'::TIMESTAMPTZ) OR is_deleted<>(deleted_dts IS NOT NULL)", kind="PATTERN")
            add("temporal-lifecycle-metadata", "TLM-OVERLAP-"+tag,
                f"SELECT a.{e.key} FROM {e.qualified} a JOIN {e.qualified} b ON a.{key}=b.{key} AND a.valid_from_dts<b.valid_from_dts AND b.valid_from_dts<a.valid_to_dts", kind="PATTERN")
            add("temporal-lifecycle-metadata", "TLM-CURRENT-"+tag,
                f"SELECT {key} FROM {e.qualified} GROUP BY {key} HAVING count(*) FILTER(WHERE is_current)>1", kind="PATTERN")
            exposed = ",".join(n for n, _, _ in e.columns+[columns(e)[len(e.columns)]])
            add("temporal-lifecycle-metadata", "TLM-SURFACE-"+tag,
                f"(SELECT {exposed} FROM {e.schema}.v_{e.name} EXCEPT SELECT {exposed} FROM {e.qualified} WHERE is_current AND valid_to_dts='infinity'::TIMESTAMPTZ AND NOT is_deleted) UNION ALL (SELECT {exposed} FROM {e.qualified} WHERE is_current AND valid_to_dts='infinity'::TIMESTAMPTZ AND NOT is_deleted EXCEPT SELECT {exposed} FROM {e.schema}.v_{e.name})", kind="PATTERN")
        for n, _, _ in columns(e):
            if n.endswith("_dts") and n not in ("valid_from_dts", "valid_to_dts"):
                add("temporal-lifecycle-metadata", "TLM-FINITE-"+tag+"-"+n,
                    f"SELECT {e.key} FROM {e.qualified} WHERE {n} IS NOT NULL AND NOT isfinite({n})", kind="PATTERN")
        if e.runtime:
            add("memory", "MEM-SCOPE-"+tag, f"SELECT {e.key} FROM {e.qualified} WHERE scope_level NOT IN ('USER','TEAM','ORGANIZATION','AGENT') OR nullif(scope_identifier,'') IS NULL")
        if e.schema == "domain" and e.history:
            add("domain", "DOM-KEY-"+tag, f"SELECT h.{e.key} FROM {e.qualified} h LEFT JOIN {e.qualified}_keymap k ON h.{e.key}=k.{e.key} AND h.{e.natural}=k.{e.natural} WHERE k.{e.key} IS NULL")
        # No unexpected attributes in enhancement/evidence/runtime tables: changes
        # to permitted content require an explicit model review and metadata update.
        if e.schema in ("search", "prediction", "observability") or e.runtime:
            allowed = ",".join(literal(n) for n, _, _ in columns(e))
            add(e.schema, "BOUNDARY-"+tag, f"SELECT column_name FROM (SELECT current_database() AS database_name, n.nspname AS schema_name, c.relname AS table_name,  a.attname AS column_name, pg_catalog.format_type(a.atttypid,a.atttypmod) AS data_type,  NOT a.attnotnull AS is_nullable, pg_catalog.col_description(c.oid,a.attnum) AS comment  FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace  WHERE a.attnum>0 AND NOT a.attisdropped AND c.relkind IN ('r','v','p')  AND n.nspname IN ('domain','semantic','search','prediction','observability','memory')) WHERE database_name=current_database() AND schema_name='{e.schema}' AND table_name='{e.name}' AND column_name NOT IN ({allowed})")
    for i, (a, ac, b, bc) in enumerate(relationships()):
        ea = next(e for e in ENTITIES if e.qualified == a)
        eb = next(e for e in ENTITIES if e.qualified == b)
        # Runtime has no public view; validation is a trusted administrative action.
        av = a if ea.runtime else ea.schema+".v_"+ea.name
        bv = b if eb.runtime else eb.schema+".v_"+eb.name
        add(ea.schema, f"JOIN-{i:03}", f"SELECT a.{ac} FROM {av} a LEFT JOIN {bv} b ON a.{ac}=b.{bc} WHERE b.{bc} IS NULL")
        add("semantic", f"REL-{i:03}", f"SELECT {literal(a)} WHERE NOT EXISTS(SELECT 1 FROM semantic.table_relationship WHERE source_entity={literal(a)} AND source_column={literal(ac)} AND target_entity={literal(b)} AND target_column={literal(bc)})")
    add("search", "SEARCH-001", """SELECT embedding_id FROM search.entity_embedding e LEFT JOIN semantic.model_metadata m ON e.embedding_model=m.model_key
        WHERE m.model_key IS NULL OR e.embedding_model_version<>m.model_version OR e.embedding_dimensions<>m.dimensions
        OR cardinality(e.embedding)<>e.embedding_dimensions OR search.cosine(e.embedding,e.embedding) IS NULL OR search.cosine(e.embedding,e.embedding)<=0""")
    add("prediction", "PRED-001", "SELECT feature_value_id FROM prediction.feature_value WHERE observation_dts>valid_from_dts OR value_numeric NOT BETWEEN 0 AND 1")
    add("prediction", "PRED-002", """SELECT p.prediction_id FROM prediction.model_prediction p LEFT JOIN prediction.feature_value f
        ON p.entity_id=f.entity_id AND p.feature_observation_dts=f.observation_dts
        WHERE f.feature_value_id IS NULL OR f.observation_dts>p.prediction_dts OR p.prediction_dts<p.valid_from_dts
        OR p.prediction_value<>1-f.value_numeric""")
    add("prediction", "PRED-003", """SELECT f.feature_value_id FROM prediction.feature_value f WHERE NOT EXISTS
        (SELECT 1 FROM domain.customer c WHERE c.customer_id=f.entity_id AND c.valid_from_dts<=f.observation_dts AND f.observation_dts<c.valid_to_dts AND NOT c.is_deleted)""")
    add("prediction", "PRED-004", """SELECT p.prediction_id FROM prediction.model_prediction p JOIN semantic.model_metadata m USING(model_key)
        WHERE p.model_version<>m.model_version OR p.prediction_dts>p.valid_from_dts""")
    add("observability", "OBS-001", "SELECT source_node FROM semantic.lineage_graph EXCEPT (SELECT source_table FROM observability.data_lineage WHERE is_active UNION SELECT job_name FROM observability.data_lineage WHERE is_active)")
    add("observability", "OBS-002", "SELECT policy_id FROM observability.retention_policy WHERE (policy_id='definitions' AND retention_days IS NOT NULL) OR (policy_id='events' AND retention_days IS NULL)")
    for module in MODULES:
        add("memory", "DOC-"+module, f"""SELECT '{module}' WHERE
            (SELECT count(*) FROM memory.v_design_decision WHERE source_module='{module}')<3 OR
            (SELECT count(*) FROM memory.v_business_glossary WHERE source_module='{module}')<3 OR
            (SELECT count(*) FROM memory.v_query_cookbook WHERE source_module='{module}')<1 OR
            (SELECT count(*) FROM memory.v_change_log WHERE source_module='{module}')<1 OR
            (SELECT count(*) FROM memory.v_module_registry WHERE module_name='{module}')<>1""")
    add("memory", "DOC-SPECIAL", """SELECT id FROM (VALUES ('DD-ACCESS-001'),('DD-DISCOVERY-001')) x(id)
        WHERE id NOT IN (SELECT decision_id FROM memory.v_design_decision)
        UNION ALL SELECT 'QC-SEMANTIC-002' WHERE NOT EXISTS(SELECT 1 FROM memory.v_query_cookbook WHERE recipe_id='QC-SEMANTIC-002')""")
    add("memory", "DOC-PAIRS", """SELECT a.module_name,b.module_name FROM semantic.data_product_map a CROSS JOIN semantic.data_product_map b
        WHERE a.module_name<b.module_name AND NOT EXISTS(SELECT 1 FROM memory.v_query_cookbook c WHERE c.target_module='CROSS'
        AND (c.recipe_id='QC-CROSS-'||upper(a.module_name)||'-'||upper(b.module_name) OR c.recipe_id='QC-CROSS-'||upper(b.module_name)||'-'||upper(a.module_name)))""")
    add("object-placement", "PLACE-001", """SELECT table_schema,table_name FROM information_schema.tables
        WHERE table_catalog=current_database() AND table_schema NOT IN ('domain','semantic','search','prediction','observability','memory','pg_catalog','information_schema') AND table_schema NOT LIKE 'pg_%'""", kind="PATTERN")
    add("validation", "VAL-001", """SELECT run_id FROM observability.validation_run WHERE total_checks<>passed_count+failed_count+error_count
        OR agent_use_allowed<>'go' OR payload_schema_version<>'2.1' OR producer_id IS NULL
        OR ((error_count>0 OR error_failure_count>0 OR critical_failure_count>0) AND trust_status<>'UNTRUSTED')""", kind="PATTERN")
    add("validation", "VAL-002", """SELECT area_id FROM observability.validation_area WHERE checks_ran<>passed_count+failed_count+error_count
        OR checks_ran>checks_expected OR (confidence='strong' AND (checks_ran<>checks_expected OR checks_ran=0 OR failed_count+error_count>0))
        OR (confidence<>'strong' AND (open_gaps IS NULL OR recommended_action IS NULL))
        OR (area_status IN ('no-evidence','not-validated') AND confidence<>'unknown')""", kind="PATTERN")
    add("validation", "VAL-003", """SELECT area_id FROM observability.validation_area a WHERE
        scope_kind NOT IN ('PRODUCT','MODULE','ENTITY','PATTERN','CAPABILITY') OR
        area_status NOT IN ('pass','fail','partial','not-validated','no-evidence') OR confidence NOT IN ('strong','partial','weak','unknown') OR
        (scope_kind='MODULE' AND scope_id NOT IN (SELECT module_name FROM semantic.data_product_map)) OR
        (scope_kind='ENTITY' AND scope_id NOT IN (SELECT entity_name FROM semantic.entity_metadata)) OR
        (scope_kind='PRODUCT' AND scope_id NOT IN (SELECT product_id FROM semantic.data_product_registry)) OR
        (scope_kind='PATTERN' AND scope_id NOT IN ('temporal-lifecycle-metadata','object-placement','physical-storage','validation','access-layer')) OR
        (scope_kind='CAPABILITY' AND scope_id NOT IN ('Embed'))""", kind="PATTERN")
    add("validation", "VAL-004", """SELECT c.check_result_id FROM observability.validation_check c LEFT JOIN observability.validation_area a
        ON c.run_id=a.run_id AND c.scope_kind=a.scope_kind AND c.scope_id=a.scope_id WHERE a.area_id IS NULL
        UNION ALL SELECT r.run_id FROM observability.validation_run r WHERE NOT EXISTS
        (SELECT 1 FROM observability.validation_area a WHERE a.run_id=r.run_id)""", kind="PATTERN")
    add("validation", "VAL-005", """SELECT a.area_id FROM observability.validation_area a LEFT JOIN observability.validation_check c
        ON a.run_id=c.run_id AND a.scope_kind=c.scope_kind AND a.scope_id=c.scope_id
        GROUP BY a.area_id,a.checks_ran,a.passed_count,a.failed_count,a.error_count,a.critical_failure_count,a.error_failure_count
        HAVING a.checks_ran<>count(c.check_result_id) OR a.passed_count<>count(*) FILTER(WHERE c.status='PASSED')
        OR a.failed_count<>count(*) FILTER(WHERE c.status='FAILED') OR a.error_count<>count(*) FILTER(WHERE c.status='ERROR')
        OR a.critical_failure_count<>count(*) FILTER(WHERE c.status<>'PASSED' AND c.severity='CRITICAL')
        OR a.error_failure_count<>count(*) FILTER(WHERE c.status<>'PASSED' AND c.severity='ERROR')""", kind="PATTERN")
    return checks
