"""Small, explicit deployment model; no database or template dependency.

Columns are (name, SQL type/constraints, authored meaning). The compiler adds
canonical audit/lifecycle fields, comments and deployment-time registrations.
This model is also the inventory used by conformance checks, never inferred
from object names at consumer query time.
"""
from dataclasses import dataclass, field


@dataclass
class Entity:
    schema: str
    name: str
    description: str
    columns: list
    key: str
    profile: str = "CURRENT_STATE"
    natural: str = ""
    runtime: bool = False
    constraints: list = field(default_factory=list)

    @property
    def qualified(self):
        return f"{self.schema}.{self.name}"

    @property
    def history(self):
        return self.profile in ("SCD2_HISTORY", "ASSOCIATION_SCD2")


ENTITIES = []


def entity(schema, name, description, columns, key, **kwargs):
    result = Entity(schema, name, description, columns, key, **kwargs)
    ENTITIES.append(result)
    return result


def c(name, meaning, typ="VARCHAR NOT NULL"):
    return name, typ, meaning


def identifier(name, target):
    return c(name, f"Stable surrogate identifying {target}; never recycled.", "BIGINT NOT NULL")


def instant(name, meaning, nullable=False):
    return c(name, meaning, "TIMESTAMPTZ" + ("" if nullable else " NOT NULL"))


AUDIT = [instant("created_dts", "Instant this physical row was created."),
         instant("updated_dts", "Instant this physical row was last changed.")]
TEMPORAL = [instant("valid_from_dts", "Inclusive business validity start."),
            instant("valid_to_dts", "Exclusive business validity end; infinity means open."),
            c("is_current", "Convenience flag agreeing with the open validity end.", "BOOLEAN NOT NULL"),
            c("is_deleted", "This version records logical deletion; retained for audit.", "BOOLEAN NOT NULL"),
            instant("deleted_dts", "Effective deletion instant; null until deletion.", True)]
SCOPE = [c("scope_level", "Privacy scope; USER ownership is checked against authenticated session_user.",
           "VARCHAR NOT NULL CHECK (scope_level IN ('USER','TEAM','ORGANIZATION','AGENT'))"),
         c("scope_identifier", "Owner identity within the declared privacy boundary.")]

for name, attrs, description in [
    ("customer", [c("display_name", "Synthetic customer display name; never copied to enhancement tables."),
                  c("segment", "Customer service segment assigned by the source.")], "Authoritative synthetic customer identity and segment history."),
    ("product", [c("product_name", "Human-facing name of the financial offering."),
                 c("description", "Authoritative description used for retrieval.")], "Financial offering reference set, versioned when its meaning changes."),
    ("account", [identifier("customer_id", "domain.customer"), identifier("product_id", "domain.product")],
     "Account ownership and offering history; connects customers to products."),
    ("transaction", [identifier("account_id", "domain.account"),
                     c("amount", "Signed transaction amount in AUD.", "DECIMAL(18,2) NOT NULL"),
                     instant("posted_dts", "Instant the source posted the transaction.")],
     "Authoritative posted transactions, with correction history.")]:
    entity("domain", name + "_keymap", f"Permanent natural-key allocation for {name}.",
           [identifier(name + "_id", name), c(name + "_key", "Immutable originating-system business identifier.")],
           name + "_id", natural=name + "_key", constraints=[f"UNIQUE ({name}_key)"])
    entity("domain", name, description,
           [identifier(name + "_id", name), c(name + "_key", "Originating-system business identifier.")] + attrs,
           name + "_id", profile="SCD2_HISTORY", natural=name + "_key")

entity("semantic", "data_product_registry", "Product-first discovery anchor; one row per portable product.", [
    c("product_id", "Stable product name supplied to discovery."), c("product_version", "Published contract version."),
    c("product_status", "Publication lifecycle state."), c("owner_team", "Team responsible for this product."),
    c("trust_authoritative_producer", "Validator whose latest area evidence defines the trust map."),
    c("approved_entrypoint", "Fully qualified approved initial business surface."),
    c("approved_access_mode", "VIEW for this server binding."),
    c("max_evidence_age_days", "Maximum evidence age before confidence becomes unknown.", "INTEGER NOT NULL")], "product_id")
entity("semantic", "data_product_map", "Deployed module discovery map, not design rationale.", [
    c("module_name", "Module anchor in the six-module composition."), c("container_name", "Exact deployed schema."),
    c("module_purpose", "Capability supplied by the module."), c("deployment_status", "DEPLOYED for included modules."),
    c("module_version", "Module contract version.")], "module_name")
entity("semantic", "entity_metadata", "Authored meaning and temporal contract of every governed table.", [
    c("entity_name", "Unique qualified logical entity identity."), c("entity_description", "Purpose and business meaning."),
    c("module_name", "Owning module anchor."), c("container_name", "Exact deployed schema."), c("table_name", "Exact deployed base table."),
    c("view_name", "Canonical consumable view; null for private runtime state.", "VARCHAR"),
    c("surrogate_key_column", "Stable identity column."), c("natural_key_column", "Business-key column or record key."),
    c("temporal_pattern", "Canonical temporal profile for this persisted table."),
    c("current_flag_column", "Stored currency flag where versioned.", "VARCHAR"),
    c("deleted_flag_column", "Stored logical deletion flag where supported.", "VARCHAR"),
    c("standalone_reason", "Reason an entity needs no relationship traversal.", "VARCHAR")], "entity_name")
entity("semantic", "column_metadata", "Authored column meaning kept separately from physical catalogue facts.", [
    c("column_metadata_id", "Stable schema.table.column metadata key."), c("container_name", "Exact schema."),
    c("table_name", "Exact object name."), c("column_name", "Exact field name."),
    c("business_description", "Meaning, units and provenance of the value."),
    c("is_pii", "Whether real deployments could hold personal information.", "BOOLEAN NOT NULL"),
    c("is_sensitive", "Whether consumers need handling restrictions.", "BOOLEAN NOT NULL"),
    c("data_classification", "Handling classification; synthetic example is PUBLIC."),
    c("source", "Authored source of the semantic description.")], "column_metadata_id")
entity("semantic", "table_relationship", "Registered joins including semantic references without physical foreign keys.", [
    c("relationship_id", "Stable relationship identity."), c("source_entity", "Qualified referencing entity."),
    c("source_column", "Referencing field."), c("target_entity", "Qualified referenced entity."),
    c("target_column", "Referenced field."), c("cardinality", "Cardinality on current consumable surfaces."),
    c("relationship_type", "FOREIGN_KEY or semantic association."),
    c("is_mandatory", "Whether each source row must resolve.", "BOOLEAN NOT NULL")], "relationship_id")
entity("semantic", "access_object", "Authoritative access classification established from generated view structure.", [
    c("object_identity", "Exact qualified consumable object."), c("access_role", "BASE, PASSTHROUGH or COMPOSITE."),
    c("represents_entity", "Entity represented; null for composite objects.", "VARCHAR"),
    c("object_grain", "One row represents this unit."),
    c("is_agent_consumable", "Whether this is a public analytical surface.", "BOOLEAN NOT NULL"),
    c("resolves_to_object", "Base object exposed by a passthrough.", "VARCHAR"), c("access_note", "Filtering and safe-use guidance.")], "object_identity")
entity("semantic", "access_composition", "Declared members of joined surfaces; consumers never parse DDL.", [
    c("access_composition_id", "Composite and member identity."), c("composite_object", "Exact joined view."),
    c("member_entity", "Qualified catalogued member."), c("member_role", "ANCHOR or joined-member role."),
    c("join_path", "Explicit join predicate; empty for anchor."),
    c("is_grain_contributor", "Whether member changes row grain.", "BOOLEAN NOT NULL")], "access_composition_id")
entity("semantic", "primary_object", "Module entrypoints with explicit roles and identities.", [
    c("object_identity", "Verbatim deployed object identity."), c("module_name", "Owning module."),
    c("object_type", "VIEW in this binding."), c("object_role", "Controlled discovery role."),
    c("usage_guidance", "How an agent should use this object.")], "object_identity")
entity("semantic", "data_product_orientation", "Ordered resources resolved before analytical use.", [
    c("resource_role", "One resource role per row."), c("product_id", "Registry product name."),
    c("object_identity", "Verbatim database resource name."),
    c("discovery_order", "Ascending navigation order; trust precedes analytics.", "INTEGER NOT NULL"),
    c("is_required", "Missing required resources fail conformance.", "BOOLEAN NOT NULL")], "resource_role")
entity("semantic", "naming_standard", "Declared signals aid authors; consumers use registered identities.", [
    c("standard_value", "Naming token or pattern."), c("meaning", "Meaning of the convention."), c("applies_to", "Object or column scope.")], "standard_value")
entity("semantic", "metric", "Business measures with explicit grain and additivity.", [
    c("metric_name", "Unique business measure."), c("metric_description", "Meaning and exclusions."),
    c("unit", "Measure unit."), c("aggregation_type", "Aggregation rule."), c("grain_description", "Evaluation grain."),
    c("is_additive", "Whether additive across all dimensions including time.", "BOOLEAN NOT NULL")], "metric_name")
entity("semantic", "metric_expression", "One expression per metric and SQL dialect.", [
    c("expression_id", "Metric-dialect key."), c("metric_name", "Registered metric."), c("sql_dialect", "Expression dialect."),
    c("expression_text", "Calculation expression.")], "expression_id", constraints=["UNIQUE(metric_name, sql_dialect)"])
entity("semantic", "metric_dataset", "Datasets required by a metric without expression parsing.", [
    c("metric_dataset_id", "Metric-entity key."), c("metric_name", "Registered metric."),
    c("entity_name", "Registered dataset."), c("dataset_role", "PRIMARY or JOINED.")], "metric_dataset_id")
entity("semantic", "semantic_synonym", "Aliases for resolver matching, distinct from glossary definitions.", [
    c("synonym_id", "Object-alias key."), c("object_kind", "ENTITY, COLUMN or METRIC."),
    c("object_name", "Registered entity, field or metric identity."), c("synonym_text", "Alternative consumer term.")], "synonym_id", constraints=["UNIQUE(object_kind, object_name, synonym_text)"])
entity("semantic", "model_metadata", "Versioned model identity and computation provenance.", [
    c("model_key", "Model and version identity."), c("model_version", "Reproducible model version."),
    c("model_purpose", "Embedding or scoring purpose and limitations."),
    c("dimensions", "Embedding dimension; null for scalar scoring.", "INTEGER"),
    c("computation_logic", "Reproducible model computation description.")], "model_key")
entity("semantic", "feature_definition", "Engineering definitions; values belong to Prediction.", [
    c("feature_name", "Registered engineered feature."), c("feature_version", "Engineering version."),
    c("computation_logic", "Transformation and leakage cutoff."), c("source_entity", "Authoritative source dataset."),
    c("refresh_frequency", "Refresh schedule."), c("unit", "Normalised unit and bounds.")], "feature_name")
entity("semantic", "role_policy", "Native PostgreSQL group roles and enforcement boundary.", [
    c("role_name", "Product logical tier name."), c("description", "Intended audience only."),
    c("enforcement", "Native grants and runtime row security.")], "role_name")

DOCS = {
    "module_registry": ("module_name", [c("module_name", "Module whose design is documented."), c("container_name", "Deployment schema."), c("deployment_status", "Deployment decision."), c("module_version", "Release version."), c("module_purpose", "Why the module is included.")]),
    "design_decision": ("decision_id", [c("decision_id", "Stable decision reference."), c("decision_version", "Decision revision.", "INTEGER NOT NULL"), c("decision_title", "Question settled."), c("context", "Constraints motivating this decision."), c("alternatives", "Other choices considered."), c("rationale", "Reason for the selected choice."), c("consequences", "Limits and obligations of this choice."), c("decision_status", "Approval state."), c("decision_category", "Decision concern."), c("source_module", "Module whose design this affects.")]),
    "business_glossary": ("term", [c("term", "Business term being defined."), c("term_category", "Kind of term."), c("definition", "Business definition and usage."), c("source_module", "Module owning the definition.")]),
    "query_cookbook": ("recipe_id", [c("recipe_id", "Stable recipe identity."), c("recipe_title", "Question the recipe answers."), c("use_case", "Intended consumer use."), c("target_module", "Module or CROSS composition."), c("query_template", "Executable PostgreSQL SQL, never result data."), c("complexity", "Expected query complexity."), c("is_batch", "Whether intended for batch only.", "BOOLEAN NOT NULL"), c("source_module", "Module responsible for recipe correctness.")]),
    "implementation_note": ("note_id", [c("note_id", "Stable operational note identity."), c("note_title", "Operational concern."), c("note_content", "How to operate within this constraint."), c("note_category", "Type of guidance."), c("source_module", "Module affected.")]),
    "change_log": ("change_id", [c("change_id", "Stable change identity."), c("version_number", "Product release."), c("change_title", "What changed and why."), c("change_type", "Release change category."), c("source_module", "Module affected."), c("related_decision_id", "Decision explaining the change.")]),
}
for name, (key, columns) in DOCS.items():
    entity("memory", name, "Versioned design memory: " + name.replace("_", " ") + ".", columns + [
        c("authored_by", "Accountable design author."), c("source_artifact", "Source design or deployment artefact."),
        instant("authored_dts", "Instant this documentation revision was authored.")], key, natural=key, profile="SCD2_HISTORY")

RUNTIME = {
    "agent_session": ("session_id", [identifier("session_id", "session"), c("session_key", "External session identity."), c("agent_key", "Executing agent."), c("user_key", "Pseudonymous user identity."), instant("session_start_dts", "Session start."), instant("session_end_dts", "Session end; null while active.", True), c("session_status", "ACTIVE, COMPLETED or ABANDONED."), c("session_goal", "Process goal, never query results."), c("session_context", "Process context only.", "JSONB")]),
    "agent_interaction": ("interaction_id", [identifier("interaction_id", "interaction"), identifier("session_id", "memory.agent_session"), c("interaction_seq", "Ordering within session.", "INTEGER NOT NULL"), instant("interaction_dts", "Interaction occurred."), c("interaction_type", "QUERY, ACTION, DECISION or EXPLANATION."), c("referenced_tables", "Table-level references only."), c("query_executed", "SQL performed; parameter values must be redacted."), c("query_result_count", "Aggregate result count only.", "INTEGER"), c("outcome_status", "Execution result status.")]),
    "learned_strategy": ("strategy_id", [identifier("strategy_id", "strategy"), c("strategy_name", "Reusable process strategy."), c("strategy_category", "Type of process learning."), c("strategy_pattern", "Approach, without business content."), c("success_rate", "Observed success fraction.", "DECIMAL(5,4) CHECK(success_rate BETWEEN 0 AND 1)"), c("times_used", "Observed usage count.", "INTEGER"), c("is_validated", "Whether strategy has supporting evidence.", "BOOLEAN NOT NULL")]),
    "user_preference": ("preference_id", [identifier("preference_id", "preference"), c("user_key", "Pseudonymous preference owner."), c("preference_category", "Presentation or analysis preference kind."), c("preference_name", "Preference setting."), c("preference_value", "Preference value, never Domain content.")]),
    "discovered_pattern": ("pattern_id", [identifier("pattern_id", "pattern"), c("pattern_name", "Observed process pattern."), c("pattern_type", "Pattern class."), c("pattern_definition", "Table-level pattern metadata.", "JSONB"), c("sample_size", "Aggregate count analysed.", "INTEGER"), c("involved_tables", "Table-level references only."), c("is_validated", "Whether evidence supports the pattern.", "BOOLEAN NOT NULL")]),
}
for name, (key, columns) in RUNTIME.items():
    entity("memory", name, "Private runtime process metadata: " + name.replace("_", " ") + ".",
           columns + SCOPE, key, runtime=True)

entity("search", "entity_embedding", "Versioned vectors and identifiers; content obtained by Domain join-back.", [
    identifier("embedding_id", "embedding"), identifier("entity_id", "domain.product"),
    c("entity_kind", "Generic reference discriminator.", "VARCHAR NOT NULL CHECK(entity_kind='PRODUCT')"),
    c("source_module", "Owner of authoritative input."), c("source_attribute", "Attribute encoded by the model."),
    c("embedding", "Synthetic three-axis vector; not a general semantic language model.", "DOUBLE PRECISION[] NOT NULL"),
    c("embedding_dimensions", "Fixed dimensionality for this model family.", "INTEGER NOT NULL CHECK(embedding_dimensions=3)"),
    c("embedding_model", "Registered embedding model key."), c("embedding_model_version", "Producer model version."),
    instant("generated_dts", "When vector was computed."), c("computation_method", "IN_DATABASE toy lexical encoder.")],
    "embedding_id", profile="SCD2_HISTORY", natural="embedding_id")
entity("prediction", "feature_value", "Point-in-time engineered spend intensity; no raw Domain attributes.", [
    identifier("feature_value_id", "feature"), identifier("entity_id", "domain.customer"),
    c("entity_kind", "Reference discriminator.", "VARCHAR NOT NULL CHECK(entity_kind='CUSTOMER')"),
    c("feature_name", "Registered feature definition."), c("feature_version", "Engineering revision."),
    c("value_numeric", "Clipped total AUD spend divided by 1000.", "DECIMAL(18,4) NOT NULL CHECK(value_numeric BETWEEN 0 AND 1)"),
    instant("observation_dts", "Source cutoff and first availability of the computed feature.")],
    "feature_value_id", profile="SCD2_HISTORY", natural="feature_value_id")
entity("prediction", "model_prediction", "Reproducible illustrative score; not a calibrated probability.", [
    identifier("prediction_id", "prediction"), identifier("entity_id", "domain.customer"),
    c("entity_kind", "Reference discriminator.", "VARCHAR NOT NULL CHECK(entity_kind='CUSTOMER')"),
    c("model_key", "Registered scoring model."), c("model_version", "Scoring revision."),
    c("prediction_value", "Toy score equal to one minus spend intensity.", "DECIMAL(10,6) NOT NULL CHECK(prediction_value BETWEEN 0 AND 1)"),
    instant("prediction_dts", "When inference occurred."), instant("feature_observation_dts", "Exact feature snapshot used.")],
    "prediction_id", profile="SCD2_HISTORY", natural="prediction_id")

OBS = {
    "change_event": ("change_event_id", [identifier("change_event_id", "change event"), c("table_name", "Qualified changed table; no row identifiers."), c("change_type", "Mutation kind."), instant("change_dts", "Change occurred."), c("changed_by", "Responsible producer."), c("records_affected", "Aggregate count only.", "INTEGER NOT NULL"), c("batch_key", "Producing run identity.")]),
    "data_quality_metric": ("quality_metric_id", [identifier("quality_metric_id", "quality measurement"), c("table_name", "Qualified measured table."), c("metric_name", "Data quality dimension."), c("metric_value", "Measured fraction, independently of validation coverage.", "DECIMAL(10,4) NOT NULL"), instant("measured_dts", "Measurement instant."), c("quality_threshold", "Acceptance threshold.", "DECIMAL(5,4) NOT NULL"), c("is_threshold_met", "Measurement meets declared threshold.", "BOOLEAN NOT NULL"), c("sample_size", "Measured population size.", "INTEGER NOT NULL")]),
    "lineage_run": ("lineage_run_id", [identifier("lineage_run_id", "flow execution"), identifier("lineage_id", "observability.data_lineage"), instant("run_dts", "Execution instant."), c("run_status", "SUCCESS, FAILED, PARTIAL or RUNNING."), c("records_read", "Input count.", "INTEGER"), c("records_written", "Output count.", "INTEGER"), c("batch_key", "Execution batch identity.")]),
    "model_performance": ("performance_id", [identifier("performance_id", "model measurement"), c("model_key", "Measured model."), c("model_version", "Measured revision."), c("metric_name", "Performance dimension, separate from predictions."), c("metric_value", "Measured metric in named units.", "DECIMAL(10,6)"), instant("evaluation_dts", "Evaluation instant."), c("sample_size", "Evaluation population.", "INTEGER")]),
    "agent_outcome": ("outcome_id", [identifier("outcome_id", "agent outcome"), c("agent_key", "Acting agent."), c("session_key", "Process session identifier."), c("action_type", "Process action."), instant("action_dts", "Action instant."), c("tables_accessed", "Table-level references only."), c("outcome_status", "Execution result."), c("records_processed", "Aggregate count, never result rows.", "INTEGER")]),
}
for name, (key, columns) in OBS.items():
    entity("observability", name, "Append-only operational evidence: " + name.replace("_", " ") + ".", columns, key, profile="EVENT_APPEND_ONLY")
entity("observability", "data_lineage", "Flow definitions retained independently of executions.", [
    identifier("lineage_id", "flow"), c("source_table", "Qualified source table."), c("target_table", "Qualified target table."),
    c("job_name", "Producing transformation."), c("transformation_logic", "Transformation definition, without business data."),
    c("is_active", "Owner enables or retires a flow; transitions true to false on retirement.", "BOOLEAN NOT NULL"),
    instant("registered_dts", "Flow registered."), instant("retired_dts", "Retirement; null while active.", True)], "lineage_id")
entity("observability", "retention_policy", "Operator-applied retention obligations, not automatic deletion.", [
    c("policy_id", "Table or facet retention identity."), c("retention_days", "Null means product lifetime.", "INTEGER"),
    c("rationale", "Why this retention period is used."), c("owner", "Operator accountable for archival and deletion.")], "policy_id")

RUN_ID = [c("product_prefix", "Product evaluated."), c("producer_id", "Validator identity."), c("run_id", "Unique append-only execution identity.")]
COUNTS = [c(n, meaning, "INTEGER NOT NULL CHECK (" + n + ">=0)") for n, meaning in [
    ("passed_count", "Checks with PASSED status."), ("failed_count", "Checks with FAILED status."),
    ("error_count", "Checks that could not execute."), ("critical_failure_count", "Failed or errored CRITICAL checks."),
    ("error_failure_count", "Failed or errored ERROR-severity checks.")]]
entity("observability", "validation_run", "Validation wire schema 2.1 run evidence; advisory, never an access gate.", RUN_ID + [
    c("producer_version", "Validator version."), c("profile_id", "Executed profile."), c("profile_version", "Profile version."),
    c("source_format", "Evidence interchange format."), c("payload_schema_version", "Validation wire schema version."),
    instant("started_dts", "Validation started."), instant("completed_dts", "Validation completed."),
    c("trust_status", "Advisory product summary.", "VARCHAR NOT NULL CHECK(trust_status IN ('TRUSTED','DEGRADED','UNTRUSTED'))"),
    c("agent_use_allowed", "Deprecated compatibility field; always go, never authoritative."),
    c("total_checks", "Executed check count.", "INTEGER NOT NULL")] + COUNTS + [
    c(n, "Optional readiness score; null means unassessed.", f"INTEGER CHECK({n} BETWEEN 0 AND 100)") for n in
    ("data_product_trust_score", "performance_readiness_score", "operational_readiness_score")] + [
    c("repair_candidate_count", "True repair proposal count.", "INTEGER NOT NULL"),
    c("failed_checks_json", "Optional capped failure detail; counts remain authoritative.", "JSONB"),
    c("repair_candidates_json", "Optional capped proposals, never executable authority.", "JSONB"),
    instant("evidence_expires_dts", "Evidence expiry.", True)], "run_id", profile="EVENT_APPEND_ONLY")
entity("observability", "validation_area", "Per-area check coverage and confidence for each validation run.", RUN_ID + [
    c("area_id", "Run-scope composite identity."), c("payload_schema_version", "Validation wire schema version."),
    c("scope_kind", "PRODUCT, MODULE, ENTITY, PATTERN or CAPABILITY."), c("scope_id", "Resolvable area identity."),
    c("checks_expected", "Checks defined by the profile.", "INTEGER NOT NULL"),
    c("checks_ran", "Checks executed.", "INTEGER NOT NULL")] + COUNTS + [
    c("area_status", "pass, fail, partial, not-validated or no-evidence."), c("confidence", "strong, partial, weak or unknown."),
    c("open_gaps", "Coverage limits, required below strong.", "VARCHAR"), c("recommended_action", "How to raise confidence.", "VARCHAR"),
    instant("completed_dts", "Parent run completion instant.")], "area_id", profile="EVENT_APPEND_ONLY")
entity("observability", "validation_check", "Individual executed check identity and error evidence.", [
    c("check_result_id", "Run and test identity."), c("run_id", "Parent validation run."), c("test_id", "Stable product-family check identifier."),
    c("scope_kind", "Area kind."), c("scope_id", "Area identity."), c("category", "Check family."), c("severity", "Failure impact."),
    c("status", "PASSED, FAILED or ERROR."), c("row_count", "True violating row count.", "INTEGER NOT NULL"),
    c("error_message", "Execution error only.", "VARCHAR"), instant("checked_dts", "Check execution time.")], "check_result_id", profile="EVENT_APPEND_ONLY")

MODULES = {
    "domain": "Authoritative business facts with historical reconstruction",
    "semantic": "Product-first discovery and authored business meaning",
    "search": "Portable exact vector retrieval with Domain join-back",
    "prediction": "Engineered historical features and reproducible model scores",
    "observability": "Separate quality, lineage, execution and validation evidence",
    "memory": "Versioned design rationale and scoped agent process continuity",
}
