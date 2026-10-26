"""The portable dialect: the SQL every binding generates unless its own dialect says otherwise.

A platform's dialect subclasses `PortableDialect` and overrides what its engine does
differently: a hook such as `open_end` or `flag_test` where only an expression differs, a
whole method where the statement does. The defaults are written for an engine with ANSI
types, schemas and `COMMENT ON`.

Every method reads the build context and returns SQL; none composes a name, supplies a
default the context does not, or reads anything but its arguments and the context.
"""
import json

from dialect import Dialect


def dictsort(mapping):
    """A mapping's items ordered by key, ignoring case, as the templates ordered them."""
    return sorted(mapping.items(), key=lambda kv: str(kv[0]).lower())


def tojson(value):
    """JSON safe to embed in markup: sorted keys and HTML-sensitive characters escaped."""
    return (json.dumps(value, sort_keys=True).replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026").replace("'", "\\u0027"))


class PortableDialect(Dialect):
    # The deployment phases in order (Master Design §10: Memory and Semantic first, so every
    # other module has somewhere to register as it lands). Each is the method `phase_<name>`
    # and writes the file `NN-<name>.sql`; a phase that renders nothing writes no file.
    PHASES = ("containers", "memory", "semantic", "domain", "observability", "search", "prediction", "comments",
              "views", "similarity", "registration", "discovery", "trust", "documentation", "access")
    # The checks a build manifest carries, each the method `check_<scope>_<name>`. Scope `entity`
    # runs once per persisted relation, `relationship` once per relationship, `module` once where
    # that module is composed, `contract` once where Semantic is, and `product` once.
    CHECKS = (("entity", "metadata"), ("entity", "temporal"), ("relationship", "reference"),
              ("module", "semantic"), ("module", "memory"), ("contract", "identity"), ("contract", "keys"),
              ("contract", "relationships"), ("contract", "access-columns"), ("contract", "composition"),
              ("product", "comment-coverage"))

    # ---- expressions a platform may spell differently --------------------------------------
    open_end = "'infinity'::TIMESTAMPTZ"  # the end of an interval still open
    now = "current_timestamp"
    true, false = "TRUE", "FALSE"
    always = "TRUE"  # a condition that holds for every row

    def flag_test(self, expr):
        return expr

    def flag_not(self, expr):
        return f"NOT {expr}"

    def comment(self, text):
        return self.literal(text)

    def value(self, v):
        """A Python value as SQL."""
        if v is None:
            return "NULL"
        if v is True:
            return self.true
        if v is False:
            return self.false
        if isinstance(v, (int, float)):
            return str(v)
        return self.literal(v)

    # ---- rows -------------------------------------------------------------------------------
    def open_row(self):
        """What an insert writes to a temporal or flag column it is not given."""
        return {"created_dts": self.now, "updated_dts": self.now, "valid_from_dts": self.now,
                "valid_to_dts": self.open_end, "transaction_from_dts": self.now,
                "transaction_to_dts": self.open_end, "is_current": self.true, "is_deleted": self.false,
                "is_active": self.true}

    def insert(self, rel, values, sql=None):
        """One row of a standard-owned relation by logical attribute name: `values` are Python
        values, `sql` SQL expressions; temporal columns not supplied take their open-row values."""
        sql, defaults, names, exprs = sql or {}, self.open_row(), [], []
        for col in rel["columns"]:
            name = col["name"]
            if name in values:
                names.append(col["physical_name"])
                exprs.append(self.value(values[name]))
            elif name in sql:
                names.append(col["physical_name"])
                exprs.append(sql[name])
            elif name in defaults and (col["origin"] == "temporal" or name in ("is_active", "is_deleted")):
                names.append(col["physical_name"])
                exprs.append(defaults[name])
        return f"INSERT INTO {self.qualified(rel['objects']['table'])} ({self.cols(names)})\nVALUES ({', '.join(exprs)});"

    def ref(self, target, match):
        """The key of the current row of `target` whose logical attributes match `match`, so a
        Reference is written as the identifier it refers to."""
        where = "".join(f" {self.ident(target['column_names'][k])} = {self.value(v)} AND" for k, v in dictsort(match))
        return (f"(SELECT {self.ident(target['key_columns'][0])} FROM {self.qualified(target['objects']['table'])} "
                f"WHERE{where} {self.current(target)})")

    @staticmethod
    def member(rel, attribute, value):
        """Whether a relation's Enum attribute permits the value: a row is only written where
        the standard's vocabulary has a value for it."""
        return any(col["name"] == attribute and value in (col.get("members") or []) for col in rel["columns"])

    # ---- the deployment ---------------------------------------------------------------------
    def deploy(self, phases):
        """Every phase in one transaction: all of it applies or none does."""
        body = "\n\n".join(f"-- {p['file']}\n{p['sql']}" for p in phases)
        return f"BEGIN;\nSET TimeZone = 'UTC';\n\n{body}\n\nCOMMIT;"

    def phase_containers(self):
        """Containers the build context places objects in. Adopted containers already exist and
        parent containers hold no objects on this platform, so neither is created here."""
        return "\n".join(f"CREATE SCHEMA {self.ident(c['name'])};"
                         for c in self.ctx["containers"] if c["holds_objects"] and not c["adopted"])

    # ---- tables -------------------------------------------------------------------------------
    @staticmethod
    def required(col):
        return bool(col["required"] or (col["canonical"] and col["name"] != "deleted_dts"))

    def key_default(self, x, col):
        """What generates a key the build allocates, appended to its column."""
        return ""

    def column_checks(self, x, col):
        """Checks a column carries beyond its Enum members."""
        return ""

    def column(self, x, col):
        name = self.ident(col["physical_name"])
        out = f"{name} {col['physical_type']}"
        if col["physical_name"] in x["key_columns"]:
            out += self.key_default(x, col)
        if self.required(col) or col["physical_name"] in x["key_columns"] or col["physical_name"] in x["version_columns"]:
            out += " NOT NULL"
        if col.get("unique") and not x["history"]:
            out += " UNIQUE"
        if col.get("members"):
            out += f" CHECK ({name} IN ({', '.join(self.literal(m) for m in col['members'])}))"
        return out + self.column_checks(x, col)

    def primary_key(self, x):
        cn = x["column_names"]
        if x["history"]:
            out = f"{self.cols(x['version_columns'])}, {self.ident(cn['valid_from_dts'])}"
            if x["bitemporal"]:
                out += f", {self.ident(cn['transaction_from_dts'])}"
            return out
        return self.cols(x["key_columns"])

    def constraints(self, x):
        cn, out = x["column_names"], ""
        if x["history"]:
            closed = f"{self.ident(cn['valid_to_dts'])} = {self.open_end}"
            if x["bitemporal"]:
                closed += f" AND {self.ident(cn['transaction_to_dts'])} = {self.open_end}"
            out += (f",\n    CHECK ({self.ident(cn['valid_from_dts'])} < {self.ident(cn['valid_to_dts'])}),"
                    f"\n    CHECK ({self.ident(cn['is_current'])} = ({closed}))")
            if x["bitemporal"]:
                out += f",\n    CHECK ({self.ident(cn['transaction_from_dts'])} < {self.ident(cn['transaction_to_dts'])})"
        if x["supports_deletion"] and "deleted_dts" in cn:
            out += f",\n    CHECK ({self.ident(cn['is_deleted'])} = ({self.ident(cn['deleted_dts'])} IS NOT NULL))"
        return out

    def keymap_of(self, x):
        k = next((k for k in self.ctx["entities"] if k["name"] == x["identity"]["keymap"]), None)
        return f"{self.qualified(k['objects']['table'])} ({self.cols(k['key_columns'])})" if k else ""

    def history_constraints(self, x):
        """Statements after a versioned table that hold one open version per identity."""
        return ""

    def table(self, x):
        lines = [f"CREATE TABLE {self.qualified(x['objects']['table'])} ("]
        lines += [f"    {self.column(x, col)}," for col in x["columns"]]
        tail = f"    PRIMARY KEY ({self.primary_key(x)}){self.constraints(x)}"
        if x["identity"].get("keymap"):
            tail += f",\n    FOREIGN KEY ({self.cols(x['key_columns'])}) REFERENCES {self.keymap_of(x)}"
        out = "\n".join(lines + [tail, ");"])
        extra = self.history_constraints(x) if x["history"] else ""
        return out + ("\n" + extra if extra else "")

    def before_table(self, x):
        """Statements a table needs created before it, such as its key sequence."""
        return ""

    table_gap = "\n"  # what separates one table's statements from the next

    def module_tables(self, module):
        """Every persisted relation of a module, keymaps first so references to them resolve."""
        ordered = [x for keymaps in (True, False) for x in self.tables()
                   if x["module"] == module and (x["kind"] == "Keymap") == keymaps]
        return self.table_gap.join(self.before_table(x) + self.table(x) for x in ordered)

    def phase_memory(self):
        return self.module_tables("memory")

    def phase_semantic(self):
        return self.module_tables("semantic")

    def phase_domain(self):
        return self.module_tables("domain")

    def phase_observability(self):
        return self.module_tables("observability")

    def phase_search(self):
        return self.module_tables("search")

    def phase_prediction(self):
        return self.module_tables("prediction")

    # ---- Semantic registration ----------------------------------------------------------------
    def key_ref(self, keydef, meta, x, k):
        """The generated id of one key of an entity, found by the entity's identity and the key's name."""
        cn = keydef["column_names"]
        return (f"(SELECT d.{self.ident(keydef['key_columns'][0])} FROM {self.qualified(keydef['objects']['table'])} d\n"
                f" WHERE d.{self.ident(cn['key_name'])} = {self.literal(k['name'])}\n"
                f"   AND d.{self.ident(cn['entity_id'])} = {self.ref(meta, {'entity_name': x['logical_id']})})")

    def phase_registration(self):
        """The product's own description of itself (Semantic): registry, module map, entity,
        column and relationship catalogues, access objects, primary objects, the orientation
        sequence, metrics, synonyms and naming standards. Every row is read from the build
        context."""
        ctx, named, out = self.ctx, self.named, []
        product = ctx["product"]
        registry, manifest = named("DataProductRegistry"), named("DataProductManifest")
        if registry and manifest:
            view = manifest["objects"]["consumer_view"]
            orientation = ctx.get("orientation")
            out.append(self.insert(registry, {
                "product_id": product["code"], "product_name": product["name"],
                "product_description": product["description"], "product_domain": product["domain"],
                "product_version": product["version"], "product_status": "ACTIVE", "owner_team": product["owner"],
                "technical_contact": product.get("technical_contact"),
                "trust_authoritative_producer": product["trust_producer"],
                "approved_entrypoint": view["container"] + "." + view["name"],
                "approved_access_mode": orientation["access_mode"] if isinstance(orientation, dict)
                and "access_mode" in orientation else "VIEW"}))
        dmap = named("DataProductMap")
        if dmap:
            for mc in ctx["module_containers"]:
                if self.member(dmap, "object_type", mc["role"].upper()):
                    out.append(self.insert(dmap, {"module_name": mc["module"].upper(), "object_type": mc["role"].upper(),
                                                  "container_name": mc["container"], "module_version": product["version"],
                                                  "deployment_status": "DEPLOYED"}))
        declaration = named("StandardDeclaration")
        if declaration:
            for d in ctx["standard"]["declarations"]:
                out.append(self.insert(declaration, {"product_id": product["code"], "component_kind": d["kind"],
                                                     "component_name": d["name"], "platform": ctx["standard"]["platform"],
                                                     "standard_version": ctx["standard"]["version"]}))
        meta, colmeta = named("EntityMetadata"), named("ColumnMetadata")
        keydef, keycol = named("KeyDefinition"), named("KeyColumn")
        for x in self.relations():
            if "table" not in x["objects"]:
                continue
            t = x["objects"]["table"]
            if meta:
                out.append(self.insert(meta, {
                    "entity_name": x["logical_id"], "logical_name": x["name"], "entity_description": x["description"],
                    "entity_kind": x["kind"].upper(), "module_name": x["module"].upper(), "container_name": t["container"],
                    "table_name": t["name"],
                    "view_name": x["objects"]["consumer_view"]["name"] if "consumer_view" in x["objects"] else None,
                    "temporal_pattern": x["profile"],
                    "current_flag_column": x["column_names"]["is_current"] if x["history"] else None,
                    "deleted_flag_column": x["column_names"]["is_deleted"] if x["supports_deletion"] else None}))
            if keydef and keycol and meta:
                for k in x["key_defs"]:
                    out.append(self.insert(keydef, {"key_role": k["role"], "key_name": k["name"]},
                                           {"entity_id": self.ref(meta, {"entity_name": x["logical_id"]})}))
                    for i, column in enumerate(k["columns"], 1):
                        out.append(self.insert(keycol, {"ordinal": i, "column_name": column},
                                               {"key_definition_id": self.key_ref(keydef, meta, x, k)}))
            if colmeta:
                for col in x["columns"]:
                    out.append(self.insert(colmeta, {
                        "container_name": t["container"], "table_name": t["name"], "column_name": col["physical_name"],
                        "logical_name": col["name"], "business_description": col["description"] or None,
                        "is_pii": col["marker"] == "pii",
                        "sensitivity_marker": col["marker"].upper().replace("-", "_") if col["marker"] else None,
                        "data_classification": col["classification"], "is_required": col["required"],
                        "declared_type": col["type"], "allowed_values": tojson(col["members"]) if col["members"] else None}))
        rel = named("TableRelationship")
        if rel:
            relcol = named("RelationshipColumn")
            for r in ctx["relationships"]:
                if not (r["source_table"] and r["target_table"]):
                    continue
                out.append(self.insert(rel, {
                    "relationship_name": r["name"], "source_entity": r["source_identity"],
                    "target_entity": r["target_identity"], "relationship_type": "FOREIGN_KEY",
                    "cardinality": "MANY_TO_ONE", "is_mandatory": r["mandatory"]}))
                if relcol:
                    for pair in r["pairs"]:
                        out.append(self.insert(relcol, {"ordinal": pair["ordinal"], "source_column": pair["source_column"],
                                                        "target_column": pair["target_column"]},
                                               {"relationship_id": self.ref(rel, {"relationship_name": r["name"]})}))
        access, acccol = named("AccessObject"), named("AccessColumn")
        surface = {"table": "base", "base_view": "governed", "consumer_view": "current", "function": "history",
                   "procedure": "history"}
        if access:
            for x in self.relations():
                for role, obj in dictsort(x["objects"]):
                    if not (obj and self.member(access, "object_type", role.upper())):
                        continue
                    out.append(self.insert(access, {
                        "object_identity": x["logical_id"] + ":" + surface[role], "container_name": obj["container"],
                        "object_name": obj["name"], "object_type": role.upper(),
                        "access_role": "BASE" if role in ("table", "base_view") else "PASSTHROUGH",
                        "represents_entity": x["logical_id"],
                        "is_agent_consumable": role in ("consumer_view", "function"),
                        "is_primary": role == "consumer_view",
                        "resolves_to_object": x["logical_id"] + ":base" if role != "table" and "table" in x["objects"] else None,
                        "access_note": x["description"]}))
                    if role == "consumer_view" and acccol:
                        for vc in x["view_columns"]:
                            out.append(self.insert(acccol, {
                                "ordinal": vc["ordinal"], "column_name": vc["physical_name"], "source_entity": x["logical_id"],
                                "source_column": vc["physical_name"], "mapping_kind": "PASSTHROUGH"},
                                {"access_object_id": self.ref(access, {"object_identity": x["logical_id"] + ":current"})}))
            for b in ctx["embeddings"]:
                for role, obj in dictsort(b["objects"]):
                    if role in ("function", "procedure"):
                        out.append(self.insert(access, {
                            "object_identity": b["logical_id"], "container_name": obj["container"], "object_name": obj["name"],
                            "object_type": role.upper(), "access_role": "PASSTHROUGH", "represents_entity": None,
                            "is_agent_consumable": True, "is_primary": False,
                            "access_note": f"Similarity search over the {b['name']} embedding of {b['entity']}."}))
        primary = named("PrimaryObject")
        if primary and dmap:
            for x in self.relations():
                for role, obj in dictsort(x["objects"]):
                    if obj and "primary_role" in obj:
                        out.append(self.insert(primary, {
                            "container_name": obj["container"], "object_name": obj["name"], "object_type": role.upper(),
                            "object_role": obj["primary_role"], "usage_guidance": x["description"]},
                            {"module_id": self.ref(dmap, {"module_name": x["module"].upper(), "object_type": role.upper(),
                                                          "container_name": obj["container"]})}))
        orient, orientation = named("DataProductOrientation"), ctx.get("orientation")
        if orient and orientation:
            for res in orientation["resources"]:
                out.append(self.insert(orient, {
                    "product_id": product["code"], "resource_role": res["role"], "container_name": res["object"]["container"],
                    "object_name": res["object"]["name"], "is_required": res["required"], "discovery_order": res["order"]}))
        metric = named("Metric")
        if metric:
            for x in ctx["metrics"]:
                out.append(self.insert(metric, {"metric_name": x["name"], "metric_description": x["description"],
                                                "metric_definition": x["measure"]["text"]}))
                by_metric = {"metric_name": self.ref(metric, {"metric_name": x["name"]})}
                if x["measure"]["sql"]:
                    flt = x.get("filter")
                    text = x["measure"]["sql"] + (" WHERE " + flt["sql"] if flt and flt["sql"] else "")
                    out.append(self.insert(named("MetricExpression"), {"sql_dialect": ctx["platform"]["name"],
                                                                       "expression_text": text}, by_metric))
                ds = named(x["dataset"])
                if ds and "consumer_view" in ds["objects"]:
                    view = ds["objects"]["consumer_view"]
                    out.append(self.insert(named("MetricDataset"), {"container_name": view["container"],
                                                                    "table_name": view["name"], "dataset_role": "PRIMARY"},
                                           by_metric))
        syn = named("SemanticSynonym")
        if syn and meta and colmeta:
            for x in ctx["entities"]:
                if "table" not in x["objects"]:
                    continue
                for s in x.get("synonyms", []):
                    out.append(self.insert(syn, {"object_kind": "ENTITYMETADATA", "synonym_text": s},
                                           {"synonym_object": self.ref(meta, {"entity_name": x["logical_id"]})}))
                for col in x["columns"]:
                    for s in col["synonyms"] or []:
                        out.append(self.insert(syn, {"object_kind": "COLUMNMETADATA", "synonym_text": s},
                                               {"synonym_object": self.ref(colmeta, {
                                                   "container_name": x["objects"]["table"]["container"],
                                                   "table_name": x["objects"]["table"]["name"],
                                                   "column_name": col["physical_name"]})}))
        naming_rel = named("NamingStandard")
        if naming_rel:
            naming = ctx["naming"]
            for role, template in dictsort(naming["objects"]):
                kind = role.split(" ")[0].upper()
                if self.member(naming_rel, "applies_to", kind):
                    out.append(self.insert(naming_rel, {"standard_type": "TEMPLATE", "applies_to": kind,
                                                        "name_template": template,
                                                        "meaning": f"How the organisation names a {role} object."}))
            out.append(self.insert(naming_rel, {"standard_type": "TEMPLATE", "applies_to": "ATTRIBUTE",
                                                "name_template": naming["attributes"],
                                                "meaning": "How the organisation names an attribute."}))
            for name, mapped in dictsort(naming["standard_names"]):
                out.append(self.insert(naming_rel, {"standard_type": "STANDARD_NAME", "applies_to": "ALL",
                                                    "standard_value": name, "mapped_value": mapped,
                                                    "meaning": "The organisation's name for a standard-owned name."}))
        return "\n\n".join(out)

    # ---- similarity search ---------------------------------------------------------------------
    def similarity(self, b):
        """The similarity search object of one `Embedding:` block: it ranks the current vectors
        of its block by the declared similarity, keeps those at or above the declared threshold,
        and returns the embedded entity's identifier with the score. Vectors come from the
        declared encoder outside the database; no binding substitutes one."""
        raise NotImplementedError

    def phase_similarity(self):
        return "\n\n".join(self.similarity(b) for b in self.ctx["embeddings"] if "function" in b["objects"])

    def similarity_filters(self, b, sc, indent="      "):
        """The block's rows: its source attribute and, where declared, its model."""
        lines = [f"    WHERE e.{self.ident(sc['source_attribute'])} = {self.literal(b['name'])}"]
        if b.get("model"):
            lines.append(f"{indent}AND e.{self.ident(sc['embedding_model'])} = {self.literal(b['model'])}")
        return lines

    def similarity_tail(self, b):
        """The threshold, ranking and limit every similarity object applies."""
        lines = [") ranked"]
        if b.get("threshold"):
            lines.append(f"WHERE ranked.similarity >= {b['threshold']}")
        return lines + ["ORDER BY ranked.similarity DESC NULLS LAST, ranked.entity_id",
                        "LIMIT greatest(0, least(result_limit, 1000));"]

    # ---- discovery views ----------------------------------------------------------------------
    def in_product(self, container, name):
        """True for an object of the product: anything in a container it owns, and, in a
        container it adopted, only the tables it adopted (Authoring Standard §4.3)."""
        owned = ", ".join(self.literal(k["name"]) for k in self.ctx["containers"] if k["holds_objects"] and not k["adopted"])
        adopted = "".join(f" OR ({container} = {self.literal(x['objects']['table']['container'])} AND "
                          f"{name} = {self.literal(x['objects']['table']['name'])})"
                          for x in self.relations() if x.get("adopted", False) and "table" in x["objects"])
        return f"({container} IN ({owned}){adopted})"

    def describe(self, view, text, columns):
        """A view's comment and each of its columns' comments."""
        return "\n".join([f"COMMENT ON VIEW {self.qualified(view)} IS {self.comment(text)};"]
                         + [f"COMMENT ON COLUMN {self.qualified(view)}.{self.ident(name)} IS {self.comment(meaning)};"
                            for name, meaning in columns])

    CATALOGUE_NOTE = ("Column-level catalogue of every product container: the structural facts from the system "
                      "catalogue joined to the authored column metadata.")

    def catalogue_columns(self):
        return [("container_name", "Container (schema) that holds the column's table or view."),
                ("table_name", "Table or view that holds the column."), ("column_name", "Physical column name."),
                ("data_type", "Declared platform data type of the column."),
                ("is_nullable", "YES when the column accepts nulls, otherwise NO."),
                ("logical_name", "Name the specification or owning standard gives the column; null when none is registered."),
                ("business_description", "Authored business meaning of the column; null when none is registered."),
                ("is_pii", "True when the column holds personally identifiable information."),
                ("sensitivity_marker", "The specification's sensitivity marker for the column, when it carries one."),
                ("data_classification", "Class the organisation's scheme assigns the column."),
                ("declared_type", "Logical type the specification declares for the column."),
                ("structural_source", "Catalogue that supplied the structural facts."),
                ("description_source", "authored when a business description is registered, missing otherwise.")]

    catalogue_scope = ""  # a condition the catalogue view adds before the product filter

    def column_catalogue(self, catalogue, colmeta):
        c, ident = colmeta["column_names"], self.ident
        return "\n".join([
            f"CREATE VIEW {self.qualified(catalogue['objects']['consumer_view'])} AS",
            "SELECT col.table_schema AS container_name, col.table_name, col.column_name, col.data_type,",
            f"       col.is_nullable, m.{ident(c['logical_name'])} AS logical_name,",
            f"       m.{ident(c['business_description'])} AS business_description, m.{ident(c['is_pii'])} AS is_pii,",
            f"       m.{ident(c['sensitivity_marker'])} AS sensitivity_marker,",
            f"       m.{ident(c['data_classification'])} AS data_classification,",
            f"       m.{ident(c['declared_type'])} AS declared_type,",
            "       'information_schema.columns' AS structural_source,",
            f"       CASE WHEN m.{ident(c['business_description'])} IS NULL THEN 'missing' ELSE 'authored' END AS description_source",
            "FROM information_schema.columns col",
            f"LEFT JOIN {self.qualified(colmeta['objects']['table'])} m",
            f"  ON m.{ident(c['container_name'])} = col.table_schema AND m.{ident(c['table_name'])} = col.table_name",
            f" AND m.{ident(c['column_name'])} = col.column_name",
            f"WHERE {self.catalogue_scope}{self.in_product('col.table_schema', 'col.table_name')};"])

    MANIFEST_NOTE = ("Bootstrap manifest: the approved entrypoint, trust producer, one deployed object per discovery "
                     "resource, and the standard version the product declares.")
    MANIFEST_COLUMNS = [("product_id", "Identifier of the data product."), ("product_name", "Name of the data product."),
                        ("product_version", "Published contract version of the data product."),
                        ("product_status", "Publication lifecycle state of the product."),
                        ("approved_entrypoint", "Consumer object an agent should start from."),
                        ("approved_access_mode", "How the approved entrypoint is reached."),
                        ("trust_authoritative_producer", "Validation producer whose evidence is authoritative for trust.")]

    def manifest_view(self, manifest, registry, orient, decl):
        p, o, ident = registry["column_names"], orient["column_names"], self.ident
        lines = [f"CREATE VIEW {self.qualified(manifest['objects']['consumer_view'])} AS",
                 f"SELECT r.{ident(p['product_id'])} AS product_id, r.{ident(p['product_name'])} AS product_name,",
                 f"       r.{ident(p['product_version'])} AS product_version, r.{ident(p['product_status'])} AS product_status,",
                 f"       r.{ident(p['approved_entrypoint'])} AS approved_entrypoint,",
                 f"       r.{ident(p['approved_access_mode'])} AS approved_access_mode,",
                 f"       r.{ident(p['trust_authoritative_producer'])} AS trust_authoritative_producer"]
        for res in self.ctx["orientation"]["resources"]:
            lines[-1] += ","
            lines.append(f"       max(CASE WHEN o.{ident(o['resource_role'])} = {self.literal(res['role'])} THEN "
                         f"o.{ident(o['container_name'])} || '.' || o.{ident(o['object_name'])} END) AS {ident(res['role'].lower())}")
        if decl:
            d = decl["column_names"]
            lines[-1] += ","
            lines += [f"       (SELECT s.{ident(d['standard_version'])} FROM {self.qualified(decl['objects']['table'])} s",
                      f"         WHERE s.{ident(d['product_id'])} = r.{ident(p['product_id'])} AND s.{ident(d['component_kind'])} = 'STANDARD'",
                      f"           AND s.{ident(d['is_active'])}) AS standard_version"]
        lines += [f"FROM {self.qualified(registry['objects']['table'])} r",
                  f"JOIN {self.qualified(orient['objects']['table'])} o ON o.{ident(o['product_id'])} = r.{ident(p['product_id'])}",
                  f"WHERE r.{ident(p['is_active'])} AND NOT r.{ident(p['is_deleted'])} AND o.{ident(o['is_active'])}",
                  "GROUP BY 1, 2, 3, 4, 5, 6, 7;"]
        return "\n".join(lines)

    def manifest(self, manifest, registry, orient, decl):
        view = manifest["objects"]["consumer_view"]
        tail = [f"COMMENT ON COLUMN {self.qualified(view)}.{self.ident(res['role'].lower())} IS "
                f"{self.comment('Container and object of the ' + res['role'] + ' discovery resource, to use as given.')};"
                for res in self.ctx["orientation"]["resources"]]
        if decl:
            tail.append(f"COMMENT ON COLUMN {self.qualified(view)}.{self.ident('standard_version')} IS "
                        f"{self.comment('Release of the standard the deployment declares it implements; null when no declaration is registered.')};")
        return (self.manifest_view(manifest, registry, orient, decl) + "\n"
                + self.describe(view, self.MANIFEST_NOTE, self.MANIFEST_COLUMNS) + "\n\n" + "\n".join(tail))

    PATHS_NOTE = ("Join paths of up to four steps between entities: one row per step and key position, ready for a "
                  "consumer to assemble the join. A path never revisits an entity.")
    PATHS_COLUMNS = [
        ("path_id", "Ordered legs of the path, each a relationship id followed by > for FORWARD or < for REVERSE."),
        ("origin_entity", "Logical identity of the entity the path starts from."),
        ("destination_entity", "Logical identity of the entity the path ends at."),
        ("hop_count", "Number of relationship steps in the path."), ("hop", "Position of this step in the path, from 1."),
        ("key_ordinal", "Position of the column pair within the join of this step, from 1."),
        ("from_entity", "Logical identity of the entity the step leaves."),
        ("from_column", "Join column on the entity the step leaves."),
        ("to_entity", "Logical identity of the entity the step arrives at."),
        ("to_column", "Join column on the entity the step arrives at."),
        ("relationship_id", "Relationship, which is the join group, this step crosses."),
        ("direction", "FORWARD when crossing from the relationship's source to its target, REVERSE for the other way.")]

    # Arrays, for the recursive walk of relationship paths.
    text_type = "TEXT"

    def array(self, *items):
        return f"ARRAY[{', '.join(items)}]"

    def append(self, array, item):
        return f"{array} || {item}"

    def not_in_array(self, array, item):
        return f"NOT {item} = ANY({array})"

    def positions(self, array, alias, column):
        return f"CROSS JOIN LATERAL generate_series(1, cardinality({array})) AS {alias}({column})"

    def relationship_paths(self, paths, rel, relcol):
        t, u, ident, txt = rel["column_names"], relcol["column_names"], self.ident, self.text_type
        r_tbl, c_tbl = self.qualified(rel["objects"]["table"]), self.qualified(relcol["objects"]["table"])
        join = f"    INNER JOIN {c_tbl} c ON c.{ident(u['relationship_id'])} = r.{ident(t['relationship_id'])}"
        active = f"    WHERE {self.flag_test('r.' + ident(t['is_active']))} AND {self.flag_test('c.' + ident(u['is_active']))}"
        return "\n".join([
            f"CREATE VIEW {self.qualified(paths['objects']['consumer_view'])} AS",
            "WITH RECURSIVE edges AS (",
            f"    SELECT r.{ident(t['relationship_id'])} AS relationship_id, c.{ident(u['ordinal'])} AS key_ordinal, 'FORWARD' AS direction,",
            f"           r.{ident(t['source_entity'])} AS from_entity, c.{ident(u['source_column'])} AS from_column,",
            f"           r.{ident(t['target_entity'])} AS to_entity, c.{ident(u['target_column'])} AS to_column",
            f"    FROM {r_tbl} r", join, active,
            "    UNION ALL",
            f"    SELECT r.{ident(t['relationship_id'])}, c.{ident(u['ordinal'])}, 'REVERSE',",
            f"           r.{ident(t['target_entity'])}, c.{ident(u['target_column'])},",
            f"           r.{ident(t['source_entity'])}, c.{ident(u['source_column'])}",
            f"    FROM {r_tbl} r", join, active,
            "), steps AS (",
            "    SELECT DISTINCT relationship_id, direction, from_entity, to_entity,",
            f"           relationship_id::{txt} || CASE direction WHEN 'FORWARD' THEN '>' ELSE '<' END AS leg",
            "    FROM edges",
            "), walk AS (",
            "    SELECT s.from_entity AS origin_entity, s.to_entity AS destination_entity,",
            f"           {self.array(f's.from_entity::{txt}', f's.to_entity::{txt}')} AS visited, {self.array(f's.leg::{txt}')} AS legs, 1 AS hops",
            "    FROM steps s",
            "    UNION ALL",
            f"    SELECT w.origin_entity, s.to_entity, {self.append('w.visited', f's.to_entity::{txt}')}, "
            f"{self.append('w.legs', f's.leg::{txt}')}, w.hops + 1",
            "    FROM walk w INNER JOIN steps s ON s.from_entity = w.destination_entity",
            f"    WHERE w.hops < {paths['max_hops']} AND {self.not_in_array('w.visited', 's.to_entity')}",
            ")",
            "SELECT array_to_string(w.legs, '') AS path_id, w.origin_entity, w.destination_entity, w.hops AS hop_count, h.hop,",
            "       e.key_ordinal, e.from_entity, e.from_column, e.to_entity, e.to_column, e.relationship_id, e.direction",
            "FROM walk w",
            self.positions("w.legs", "h", "hop"),
            "INNER JOIN edges e",
            f"   ON e.relationship_id::{txt} = substr(w.legs[h.hop], 1, length(w.legs[h.hop]) - 1)",
            "  AND e.direction = CASE substr(w.legs[h.hop], length(w.legs[h.hop]), 1) WHEN '>' THEN 'FORWARD' ELSE 'REVERSE' END;"])

    GRAPH_NOTE = "Table-and-job lineage graph: one edge from each active source to its job and from the job to its target."
    GRAPH_COLUMNS = [("source_node", "Node the edge leaves: a source table or a job."),
                     ("target_node", "Node the edge arrives at: a job or a target table."),
                     ("edge_type", "Kind of relationship the edge records; produces for data flow.")]

    def lineage_graph(self, graph_view, lineage):
        d, ident, t = lineage["column_names"], self.ident, self.qualified(lineage["objects"]["table"])
        active = f"WHERE {self.flag_test(ident(d['is_active']))} AND {ident(d['job_name'])} IS NOT NULL"
        return "\n".join([
            f"CREATE VIEW {self.qualified(graph_view['objects']['consumer_view'])} AS",
            f"SELECT DISTINCT coalesce({ident(d['source_container'])} || '.', '') || coalesce({ident(d['source_table'])}, "
            f"{ident(d['source_system'])}) AS source_node,",
            f"       {ident(d['job_name'])} AS target_node, 'produces' AS edge_type",
            f"FROM {t} {active}", "UNION",
            f"SELECT DISTINCT {ident(d['job_name'])}, coalesce({ident(d['target_container'])} || '.', '') || "
            f"{ident(d['target_table'])}, 'produces'",
            f"FROM {t} {active};"])

    LATEST_NOTE = "Latest recorded run of each active lineage definition."
    LATEST_COLUMNS = [("lineage_id", "Identifier of the lineage definition."), ("source_table", "Table the job reads."),
                      ("target_table", "Table the job writes."), ("job_name", "Name of the job that moves the data."),
                      ("run_dts", "When the latest run was recorded; null when never run."),
                      ("run_status", "Outcome of the latest run; null when never run.")]

    def lineage_run_latest(self, latest, lineage, run):
        d, r, ident = lineage["column_names"], run["column_names"], self.ident
        return "\n".join([
            f"CREATE VIEW {self.qualified(latest['objects']['consumer_view'])} AS",
            "SELECT lineage_id, source_table, target_table, job_name, run_dts, run_status FROM (",
            f"    SELECT d.{ident(d['lineage_id'])} AS lineage_id, d.{ident(d['source_table'])} AS source_table,",
            f"           d.{ident(d['target_table'])} AS target_table, d.{ident(d['job_name'])} AS job_name,",
            f"           r.{ident(r['run_dts'])} AS run_dts, r.{ident(r['run_status'])} AS run_status,",
            f"           row_number() OVER (PARTITION BY d.{ident(d['lineage_id'])}",
            f"                              ORDER BY r.{ident(r['run_dts'])} DESC NULLS LAST, r.{ident(r['lineage_run_id'])} DESC) AS rank",
            f"    FROM {self.qualified(lineage['objects']['table'])} d",
            f"    LEFT JOIN {self.qualified(run['objects']['table'])} r ON r.{ident(r['lineage_id'])} = d.{ident(d['lineage_id'])}",
            f"    WHERE d.{ident(d['is_active'])}",
            ") ranked WHERE rank = 1;"])

    def phase_discovery(self):
        """The standard-owned discovery views (Design Specification Standard §4.1): Semantic's
        column catalogue, manifest and relationship paths, and Observability's lineage views.
        Each is created only where the composition places it, and reads only relations the build
        context places. Every view and every column carries a comment."""
        named, out = self.named, []
        colmeta, catalogue = named("ColumnMetadata"), named("ColumnCatalogue")
        if catalogue and colmeta:
            out.append(self.column_catalogue(catalogue, colmeta) + "\n"
                       + self.describe(catalogue["objects"]["consumer_view"], self.CATALOGUE_NOTE, self.catalogue_columns()))
        registry, orient = named("DataProductRegistry"), named("DataProductOrientation")
        manifest, decl = named("DataProductManifest"), named("StandardDeclaration")
        if manifest and registry and orient:
            out.append(self.manifest(manifest, registry, orient, decl))
        rel, relcol, paths = named("TableRelationship"), named("RelationshipColumn"), named("RelationshipPaths")
        if paths and rel and relcol:
            out.append(self.relationship_paths(paths, rel, relcol) + "\n"
                       + self.describe(paths["objects"]["consumer_view"], self.PATHS_NOTE, self.PATHS_COLUMNS))
        lineage, graph_view = named("DataLineage"), named("LineageGraph")
        if graph_view and lineage:
            out.append(self.lineage_graph(graph_view, lineage) + "\n"
                       + self.describe(graph_view["objects"]["consumer_view"], self.GRAPH_NOTE, self.GRAPH_COLUMNS))
        run, latest = named("LineageRun"), named("LineageRunLatest")
        if latest and lineage and run:
            out.append(self.lineage_run_latest(latest, lineage, run) + "\n"
                       + self.describe(latest["objects"]["consumer_view"], self.LATEST_NOTE, self.LATEST_COLUMNS))
        return "\n\n".join(out)

    # ---- the trust map ------------------------------------------------------------------------
    TRUST_NOTE = ("Trust map: per area, the latest evidence from the designated producer, read at unknown confidence "
                  "once expired. Read it before relying on any other object.")
    TRUST_COLUMNS = [
        ("product_code", "Data product the evidence describes."),
        ("producer_id", "Validation producer whose evidence is read; null when none is designated."),
        ("run_id", "Validation run that supplied the area evidence; null when none exists."),
        ("scope_kind", "Kind of scope the evidence covers, for example MODULE, ENTITY or PRODUCT."),
        ("scope_id", "Identifier of the scope the evidence covers."),
        ("area_status", "Outcome of the area: pass, fail, partial or no-evidence."),
        ("confidence", "Trust confidence for the area; unknown once the evidence has expired."),
        ("checks_expected", "Number of checks the area should have run."),
        ("checks_ran", "Number of checks the area actually ran."),
        ("coverage", "Fraction of expected checks that ran; null when none were expected."),
        ("passed_count", "Number of checks that passed."), ("failed_count", "Number of checks that failed."),
        ("error_count", "Number of checks that errored before producing a result."),
        ("critical_failure_count", "Number of failed checks of critical severity."),
        ("error_failure_count", "Number of failed or errored checks counted against trust."),
        ("open_gaps", "Known gaps in the evidence; states staleness when the evidence has expired."),
        ("recommended_action", "Next step to restore or confirm trust."),
        ("completed_dts", "When the area evidence was completed; null when none exists."),
        ("derived", "True when the entry is derived from a legacy run that published no area records.")]
    double_type = "DOUBLE PRECISION"

    def legacy_versions(self):
        return ", ".join(self.literal(v) for v in self.ctx["quality"]["legacy_wire_versions"])

    def trust_map(self, view, run, area, registry):
        r, a, p, ident = run["column_names"], area["column_names"], registry["column_names"], self.ident
        window = f"INTERVAL '{int(self.ctx['quality']['evidence_window_days'] * 86400)} seconds'"
        area_t, run_t = self.qualified(area["objects"]["table"]), self.qualified(run["objects"]["table"])
        v = self.qualified(view["objects"]["consumer_view"])
        lines = [
            f"CREATE VIEW {v} AS",
            "WITH product AS (",
            f"    SELECT {ident(p['product_id'])} AS product_code, nullif({ident(p['trust_authoritative_producer'])}, '') AS producer_id",
            f"    FROM {self.qualified(registry['objects']['table'])} WHERE {ident(p['is_active'])} AND NOT {ident(p['is_deleted'])}",
            "), evidence AS (",
            f"    SELECT x.{ident(a['product_code'])} AS product_code, x.{ident(a['producer_id'])} AS producer_id,",
            f"           x.{ident(a['run_id'])} AS run_id, x.{ident(a['scope_kind'])} AS scope_kind, x.{ident(a['scope_id'])} AS scope_id,",
            f"           x.{ident(a['area_status'])} AS area_status, x.{ident(a['confidence'])} AS confidence,",
            f"           x.{ident(a['checks_expected'])} AS checks_expected, x.{ident(a['checks_ran'])} AS checks_ran,",
            f"           x.{ident(a['passed_count'])} AS passed_count, x.{ident(a['failed_count'])} AS failed_count,",
            f"           x.{ident(a['error_count'])} AS error_count, x.{ident(a['critical_failure_count'])} AS critical_failure_count,",
            f"           x.{ident(a['error_failure_count'])} AS error_failure_count, x.{ident(a['open_gaps'])} AS open_gaps,",
            f"           x.{ident(a['recommended_action'])} AS recommended_action, x.{ident(a['completed_dts'])} AS completed_dts,",
            f"           y.{ident(r['evidence_expires_dts'])} AS evidence_expires_dts, FALSE AS derived",
            f"    FROM {area_t} x",
            f"    JOIN {run_t} y ON y.{ident(r['product_code'])} = x.{ident(a['product_code'])}",
            f"     AND y.{ident(r['producer_id'])} = x.{ident(a['producer_id'])} AND y.{ident(r['run_id'])} = x.{ident(a['run_id'])}",
            "    UNION ALL",
            f"    SELECT y.{ident(r['product_code'])}, y.{ident(r['producer_id'])}, y.{ident(r['run_id'])}, 'PRODUCT', y.{ident(r['product_code'])},",
            f"           CASE WHEN y.{ident(r['total_checks'])} = 0 THEN 'no-evidence'",
            f"                WHEN y.{ident(r['failed_count'])} = 0 AND y.{ident(r['error_count'])} = 0 THEN 'pass' ELSE 'fail' END,",
            f"           CASE WHEN y.{ident(r['total_checks'])} = 0 THEN 'unknown'",
            f"                WHEN y.{ident(r['critical_failure_count'])} + y.{ident(r['error_failure_count'])} > 0 THEN 'weak'",
            "                ELSE 'partial' END,",
            f"           y.{ident(r['total_checks'])}, y.{ident(r['total_checks'])}, y.{ident(r['passed_count'])}, y.{ident(r['failed_count'])},",
            f"           y.{ident(r['error_count'])}, y.{ident(r['critical_failure_count'])}, y.{ident(r['error_failure_count'])},",
            f"           'Derived from a run with no area records.', NULL, y.{ident(r['completed_dts'])}, y.{ident(r['evidence_expires_dts'])}, TRUE",
            f"    FROM {run_t} y",
            f"    WHERE y.{ident(r['payload_schema_version'])} IN ({self.legacy_versions()})",
            f"      AND NOT EXISTS (SELECT 1 FROM {area_t} x WHERE x.{ident(a['product_code'])} = y.{ident(r['product_code'])}",
            f"                      AND x.{ident(a['producer_id'])} = y.{ident(r['producer_id'])} AND x.{ident(a['run_id'])} = y.{ident(r['run_id'])})",
            "), latest AS (",
            "    SELECT DISTINCT ON (e.product_code, e.producer_id, e.scope_kind, e.scope_id) e.*,",
            f"           current_timestamp > coalesce(e.evidence_expires_dts, e.completed_dts + {window}) AS stale",
            "    FROM evidence e JOIN product p ON p.product_code = e.product_code",
            "     AND (p.producer_id IS NULL OR p.producer_id = e.producer_id)",
            "    ORDER BY e.product_code, e.producer_id, e.scope_kind, e.scope_id, e.completed_dts DESC, e.run_id DESC",
            "), cautious AS (",
            "    SELECT DISTINCT ON (l.product_code, l.scope_kind, l.scope_id) l.*,",
            "           CASE WHEN l.stale THEN 'unknown' ELSE l.confidence END AS read_confidence",
            "    FROM latest l",
            "    ORDER BY l.product_code, l.scope_kind, l.scope_id,",
            "             CASE WHEN l.stale THEN 0 ELSE CASE l.confidence WHEN 'unknown' THEN 0 WHEN 'weak' THEN 1 WHEN 'partial' THEN 2 ELSE 3 END END,",
            "             l.completed_dts DESC, l.run_id DESC, l.producer_id",
            ")",
            "SELECT c.product_code, c.producer_id, c.run_id, c.scope_kind, c.scope_id, c.area_status,",
            "       c.read_confidence AS confidence, c.checks_expected, c.checks_ran,",
            f"       c.checks_ran::{self.double_type} / nullif(c.checks_expected, 0) AS coverage,",
            "       c.passed_count, c.failed_count, c.error_count, c.critical_failure_count, c.error_failure_count,",
            f"       CASE WHEN c.stale THEN 'Evidence is stale since ' || coalesce(c.evidence_expires_dts, c.completed_dts + {window})::{self.text_type} || '.' ELSE c.open_gaps END AS open_gaps,",
            "       CASE WHEN c.stale THEN 'Re-run the validator; disclose unknown confidence.'",
            "            WHEN p.producer_id IS NULL THEN 'No designated producer: cautious per-area fallback. ' || coalesce(c.recommended_action, 'Designate one producer.')",
            "            ELSE c.recommended_action END AS recommended_action,",
            "       c.completed_dts, c.derived",
            "FROM cautious c JOIN product p ON p.product_code = c.product_code",
            "UNION ALL",
            "SELECT p.product_code, p.producer_id, NULL, 'PRODUCT', p.product_code, 'no-evidence', 'unknown',",
            "       0, 0, NULL, 0, 0, 0, 0, 0, 'No published area evidence.', 'Run the validator before reporting confidence.',",
            "       NULL, FALSE",
            "FROM product p WHERE NOT EXISTS (SELECT 1 FROM latest l WHERE l.product_code = p.product_code);",
            f"COMMENT ON VIEW {v} IS {self.comment(self.TRUST_NOTE)};"]
        lines += [f"COMMENT ON COLUMN {v}.{name} IS {self.comment(meaning)};" for name, meaning in self.TRUST_COLUMNS]
        return "\n".join(lines)

    def phase_trust(self):
        """The trust map (Validation §§4, 10, 11): per area, the latest evidence from the
        product's designated producer, read at `unknown` confidence once past its expiry or the
        product's evidence window; a run at a registered legacy wire version, which publishes no
        area records, projected as one PRODUCT entry capped at `partial`; and a `no-evidence`
        entry for a product with nothing published. Where no producer is designated, the most
        cautious producer's entry stands for each area."""
        view, run, area, registry = (self.named(n) for n in ("TrustMap", "ValidationRun", "ValidationArea",
                                                             "DataProductRegistry"))
        return self.trust_map(view, run, area, registry) if view and run and area and registry else ""

    # ---- access -------------------------------------------------------------------------------
    def whole_containers(self):
        """The containers a grant may reach whole: those holding consumer views and no tables,
        where the profile grants at container level."""
        if self.ctx["grant_level"] != "container":
            return []
        mcs = self.ctx["module_containers"]
        tables = [m["container"] for m in mcs if m["role"] == "table"]
        views = list(dict.fromkeys(m["container"] for m in mcs if m["role"] == "consumer_view"))
        return [k for k in views if k not in tables]

    # ---- design memory ------------------------------------------------------------------------
    def similarity_recipe(self, r, b):
        """How a consumer calls a block's similarity search with a query vector and a limit."""
        f = self.qualified(b["objects"]["function"])
        if not r.get("join"):
            return f"SELECT * FROM {f}($1, 10)"
        d = self.named(b["entity"])
        return (f"SELECT s.similarity, d.* FROM {f}($1, 10) s JOIN {self.qualified(d['objects']['consumer_view'])} d "
                f"ON d.{self.ident(d['key_columns'][0])} = s.entity_id ORDER BY s.similarity DESC")

    def recipe_sql(self, r):
        """A cookbook recipe's query, in this platform's dialect, from what the recipe names."""
        kind = r["kind"]
        if kind == "metric":
            x = next(m for m in self.ctx["metrics"] if m["name"] == r["metric"])
            ds = self.named(x["dataset"])
            sql = (f"SELECT {x['measure']['sql']} AS {self.ident('value')} FROM "
                   f"{self.qualified(ds['objects']['consumer_view'])} AS {self.ident(ds['alias'])}")
            flt = x.get("filter")
            return sql + (f" WHERE {flt['sql']}" if flt and flt["sql"] else "")
        if kind == "similarity":
            return self.similarity_recipe(r, next(b for b in self.ctx["embeddings"] if b["name"] == r["embedding"]))
        if kind == "join":
            rel = self.ctx["relationships"][r["relationship"]]
            return (f"SELECT s.*, t.* FROM {self.qualified(rel['source_view'])} s JOIN {self.qualified(rel['target_view'])} t "
                    f"ON s.{self.ident(rel['source_column'])} = t.{self.ident(rel['target_columns'][0])}")
        if kind == "catalogue":
            meta = self.named("EntityMetadata")
            modules = ", ".join(self.literal(m.upper()) for m in r["modules"])
            return (f"SELECT * FROM {self.qualified(meta['objects']['consumer_view'])} "
                    f"WHERE {self.ident(meta['column_names']['module_name'])} IN ({modules})")
        return f"SELECT * FROM {self.qualified(self.named(r['relation'])['objects']['consumer_view'])}"

    def phase_documentation(self):
        """Design memory (Memory §5.2): the records the build context settles, written as rows.
        Nothing is invented: a record the context does not carry is not written."""
        capture, named, out = self.ctx["capture"], self.named, []
        version = self.ctx["product"]["version"]
        registry = named("ModuleRegistry")
        if registry:
            out += [self.insert(registry, {
                "module_name": mod["module"].upper(), "container_name": mod["container"], "deployment_status": "DEPLOYED",
                "module_version": version, "module_purpose": mod["purpose"],
                "key_entities": ", ".join(mod["key_entities"]) or None}) for mod in capture["modules"]]
        decision = named("DesignDecision")
        if decision:
            out += [self.insert(decision, {
                "decision_id": d["decision_id"], "decision_version": 1, "decision_title": d["title"],
                "context": d["context"], "alternatives": d["alternatives"], "rationale": d["rationale"],
                "decision_status": "ACCEPTED", "decision_category": d["category"], "source_module": d["module"].upper()})
                for d in capture["decisions"]]
        glossary = named("BusinessGlossary")
        if glossary:
            out += [self.insert(glossary, {"term": g["term"], "term_category": g["category"], "definition": g["definition"],
                                           "source_module": g["module"].upper()}) for g in capture["glossary"]]
        cookbook = named("QueryCookbook")
        if cookbook:
            out += [self.insert(cookbook, {
                "recipe_id": r["recipe_id"], "recipe_title": r["title"], "use_case": r["use_case"],
                "target_module": r["target_module"].upper(), "query_template": self.recipe_sql(r),
                "complexity": r["complexity"], "is_batch": False, "source_module": r["source_module"].upper()})
                for r in capture["cookbook"]]
        notes = named("ImplementationNote")
        if notes:
            out += [self.insert(notes, {"note_id": n["note_id"], "note_title": n["title"], "note_content": n["content"],
                                        "note_category": n["category"], "severity": n["severity"],
                                        "source_module": n["module"].upper()}) for n in capture["notes"]]
        changes = named("ChangeLog")
        if changes:
            out += [self.insert(changes, {"change_id": c["change_id"], "version_number": c["version"],
                                          "change_title": c["title"], "change_type": c["type"],
                                          "source_module": c["module"].upper()}) for c in capture["change_log"]]
        return "\n\n".join(out)

    # ---- checks: every row a check returns is a defect --------------------------------------
    never = "FALSE"  # a condition no row meets, to start a list of OR'ed defects

    def expected_columns(self, x):
        """Each column the build context places, as one row of `expected(column_name)`."""
        values = ", ".join(f"({self.literal(col['physical_name'])})" for col in x["columns"])
        return f"SELECT expected.column_name FROM (VALUES {values}) expected(column_name)"

    def check_entity_metadata(self, entity):
        """A column the build context places that the table lacks, or one with no description."""
        raise NotImplementedError

    def versions_differ(self, a, b, x):
        cn = x["column_names"]
        tx = (f" AND {a}.{self.ident(cn['transaction_from_dts'])} = {b}.{self.ident(cn['transaction_from_dts'])}"
              if x["bitemporal"] else "")
        return f"NOT ({a}.{self.ident(cn['valid_from_dts'])} = {b}.{self.ident(cn['valid_from_dts'])}{tx})"

    def current_flag_defects(self, x):
        cn, ident = x["column_names"], self.ident
        tx = f" AND a.{ident(cn['transaction_to_dts'])} = {self.open_end}" if x["bitemporal"] else ""
        return [f" OR a.{ident(cn['is_current'])} <> (a.{ident(cn['valid_to_dts'])} = {self.open_end}{tx})"]

    def open_version_defects(self, x, t, ids):
        """More than one open version of an identity, where the schema does not prevent it."""
        return []

    def deletion_defects(self, x):
        cn = x["column_names"]
        return [f" OR a.{self.ident(cn['is_deleted'])} <> (a.{self.ident(cn['deleted_dts'])} IS NOT NULL)"]

    def timestamp_defects(self, x):
        """Non-finite event timestamps."""
        return [f" OR (a.{self.ident(c['physical_name'])} IS NOT NULL AND NOT isfinite(a.{self.ident(c['physical_name'])}))"
                for c in x["columns"] if c["physical_type"] == "TIMESTAMPTZ"
                and c["name"] not in ("valid_to_dts", "transaction_to_dts")]

    def check_entity_temporal(self, entity):
        """The temporal profile's invariants: an empty interval, a current flag that disagrees
        with the open axes, overlapping versions of one identity, a tombstone without its
        instant, a non-finite event timestamp."""
        x, ident = entity, self.ident
        cn, t = x["column_names"], self.qualified(x["objects"]["table"])
        ids = x["version_columns"] or x["key_columns"]
        lines = [f"SELECT {', '.join('a.' + ident(k) for k in ids)} FROM {t} a WHERE {self.never}"]
        if x["history"]:
            lines.append(f" OR a.{ident(cn['valid_from_dts'])} >= a.{ident(cn['valid_to_dts'])}")
            lines += self.current_flag_defects(x)
            if x["bitemporal"]:
                lines.append(f" OR a.{ident(cn['transaction_from_dts'])} >= a.{ident(cn['transaction_to_dts'])}")
            same = "".join(f"a.{ident(k)} = b.{ident(k)} AND " for k in ids)
            lines += [f" OR EXISTS (SELECT 1 FROM {t} b WHERE {same}", f"     {self.versions_differ('a', 'b', x)}",
                      f"     AND a.{ident(cn['valid_from_dts'])} < b.{ident(cn['valid_to_dts'])} AND "
                      f"b.{ident(cn['valid_from_dts'])} < a.{ident(cn['valid_to_dts'])}"]
            if x["bitemporal"]:
                lines.append(f"     AND a.{ident(cn['transaction_from_dts'])} < b.{ident(cn['transaction_to_dts'])} AND "
                             f"b.{ident(cn['transaction_from_dts'])} < a.{ident(cn['transaction_to_dts'])}")
            lines[-1] += ")"
            lines += self.open_version_defects(x, t, ids)
        if x["supports_deletion"] and "deleted_dts" in cn:
            lines += self.deletion_defects(x)
        lines += self.timestamp_defects(x)
        return "\n".join(lines)

    def check_relationship_reference(self, relationship):
        """Current-surface referential coverage, not historical proof: a current reference with
        no current target. A join of several columns resolves only when every pair matches; a
        generic reference is checked only for the rows its discriminator points at this target."""
        r, ident = relationship, self.ident
        pairs, source = r["pairs"], self.named(r["source"])
        where = ""
        if r["discriminator"]:
            where += f"s.{ident(source['column_names'][r['discriminator']])} = {self.literal(r['discriminator_value'])} AND "
        if not r["mandatory"]:
            where += "".join(f"s.{ident(p['source_column'])} IS NOT NULL AND " for p in pairs)
        on = " AND ".join(f"s.{ident(p['source_column'])} = t.{ident(p['target_column'])}" for p in pairs)
        return "\n".join([
            f"SELECT {', '.join('s.' + ident(p['source_column']) for p in pairs)} FROM "
            f"{self.qualified(r['source_view'] or r['source_table'])} s",
            f"LEFT JOIN {self.qualified(r['target_view'] or r['target_table'])} t ON {on}",
            f"WHERE {where}t.{ident(pairs[0]['target_column'])} IS NULL"])

    tables_scope = ""  # a condition the unregistered-table check adds to the catalogue's tables

    def check_module_semantic(self, module):
        """Every table of the product is registered in EntityMetadata, keymaps included: every
        table in a container it owns, and each table it adopted."""
        meta = self.named("EntityMetadata")
        c, ident = meta["column_names"], self.ident
        return "\n".join([
            "SELECT t.table_schema, t.table_name FROM information_schema.tables t",
            f"LEFT JOIN {self.qualified(meta['objects']['table'])} e",
            f"  ON e.{ident(c['container_name'])} = t.table_schema AND e.{ident(c['table_name'])} = t.table_name",
            f"WHERE t.table_type = 'BASE TABLE'{self.tables_scope}",
            f"  AND {self.in_product('t.table_schema', 't.table_name')}",
            f"  AND e.{ident(c['entity_name'])} IS NULL"])

    def check_module_memory(self, module):
        """The capture floor (Memory §5.2) per registered module: three design decisions, three
        glossary terms and one cookbook recipe, never met with generated filler."""
        reg, dd, bg, qc = (self.named(n) for n in ("ModuleRegistry", "DesignDecision", "BusinessGlossary", "QueryCookbook"))
        name = f"r.{self.ident(reg['column_names']['module_name'])}"

        def of(rel, alias):
            return f"{alias}.{self.ident(rel['column_names']['source_module'])} = {name}"
        return "\n".join([
            f"SELECT {name} FROM {self.qualified(reg['objects']['consumer_view'])} r WHERE",
            f"    (SELECT count(*) FROM {self.qualified(dd['objects']['consumer_view'])} d WHERE {of(dd, 'd')}) < 3",
            f" OR (SELECT count(*) FROM {self.qualified(bg['objects']['consumer_view'])} g WHERE {of(bg, 'g')}) < 3",
            f" OR NOT EXISTS (SELECT 1 FROM {self.qualified(qc['objects']['consumer_view'])} q WHERE {of(qc, 'q')})"])

    def owned_containers(self, holding=True):
        """The containers the product creates, as a list of literals: those that hold objects,
        or every one it creates."""
        return ", ".join(self.literal(c["name"]) for c in self.ctx["containers"]
                         if not c["adopted"] and (c["holds_objects"] or not holding))

    def check_product_comment_coverage(self):
        """MetadataCoverageCheck, catalogue-wide: a container, object or column with no comment,
        in every container the product places objects in, so an object the specification never
        mentions is caught too. It reads the platform's own catalogue."""
        raise NotImplementedError

    # ---- checks: the Semantic metadata contract (INV-SEMANTIC-016 to 020) ----------------------
    # A standard-owned relation is read through the physical names the build context places.
    def tbl(self, name):
        return self.qualified(self.named(name)["objects"]["table"])

    def col(self, name, column):
        return self.ident(self.named(name)["column_names"][column])

    def pk(self, name):
        return self.ident(self.named(name)["key_columns"][0])

    def contiguous(self, alias, ordinal):
        """A run of ordinals is 1..n with no gaps and no repeats."""
        o = f"{alias}.{ordinal}"
        return f"count(DISTINCT {o}) <> count(*) OR min({o}) <> 1 OR max({o}) <> count(*)"

    columns_scope = ""  # a condition the contract checks add before reading the catalogue's columns

    def matches(self, expr, pattern):
        return f"{expr} ~ '{pattern}'"

    def not_matches(self, expr, pattern):
        return f"{expr} !~ '{pattern}'"

    def check_contract_identity(self):
        """INV-SEMANTIC-016: identities follow the grammar and carry no placement."""
        en, active = self.col("EntityMetadata", "entity_name"), self.col("EntityMetadata", "is_active")
        oi, a_active = self.col("AccessObject", "object_identity"), self.col("AccessObject", "is_active")
        em, ao = self.tbl("EntityMetadata"), self.tbl("AccessObject")
        return "\n".join([
            f"SELECT e.{en}::TEXT AS identity, 'entity identity is not module.entity in its own module' AS defect",
            f"FROM {em} e", f"WHERE e.{active}",
            f"  AND ({self.not_matches('e.' + en, '^[a-z][a-z0-9_]*[.][a-z][a-z0-9_]*$')}",
            f"       OR e.{en} NOT LIKE lower(e.{self.col('EntityMetadata', 'module_name')}) || '.%')",
            "UNION ALL",
            f"SELECT e.{en}::TEXT, 'entity identity is registered more than once'",
            f"FROM {em} e", f"WHERE e.{active}", f"GROUP BY e.{en}", "HAVING count(*) > 1",
            "UNION ALL",
            f"SELECT a.{oi}::TEXT, 'access identity breaks the grammar'",
            f"FROM {ao} a", f"WHERE a.{a_active}",
            f"  AND NOT ({self.matches('a.' + oi, '^[a-z][a-z0-9_]*[.][a-z][a-z0-9_]*:(base|governed|current|history)$')}",
            f"        OR {self.matches('a.' + oi, '^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$')}",
            f"        OR {self.matches('a.' + oi, '^composite:[a-z][a-z0-9_]*$')})",
            "UNION ALL",
            f"SELECT a.{oi}::TEXT, 'single-entity identity does not match its entity and surface'",
            f"FROM {ao} a", f"WHERE a.{a_active} AND a.{self.col('AccessObject', 'represents_entity')} IS NOT NULL",
            f"  AND a.{oi} <> a.{self.col('AccessObject', 'represents_entity')} || ':' ||",
            f"      CASE a.{self.col('AccessObject', 'object_type')} WHEN 'TABLE' THEN 'base' WHEN 'BASE_VIEW' THEN 'governed'",
            "           WHEN 'CONSUMER_VIEW' THEN 'current' ELSE 'history' END"])

    def check_contract_keys(self):
        """INV-SEMANTIC-017: every entity has a key; the columns of a key are ordered 1..n and
        exist on the entity."""
        c, scope = self.col, self.columns_scope
        em, kd, kc = self.tbl("EntityMetadata"), self.tbl("KeyDefinition"), self.tbl("KeyColumn")
        en, kn = c("EntityMetadata", "entity_name"), c("KeyDefinition", "key_name")
        k_active, c_active = c("KeyDefinition", "is_active"), c("KeyColumn", "is_active")
        entity_of = f"INNER JOIN {em} e ON e.{self.pk('EntityMetadata')} = k.{c('KeyDefinition', 'entity_id')}"
        return "\n".join([
            f"SELECT e.{en}::TEXT AS identity, 'entity has no key definition' AS defect",
            f"FROM {em} e", f"WHERE e.{c('EntityMetadata', 'is_active')}",
            f"  AND NOT EXISTS (SELECT 1 FROM {kd} k",
            f"                  WHERE k.{c('KeyDefinition', 'entity_id')} = e.{self.pk('EntityMetadata')} AND k.{k_active})",
            "UNION ALL",
            f"SELECT e.{en} || '#' || k.{kn}, 'key has no columns'",
            f"FROM {kd} k", entity_of, f"WHERE k.{k_active}",
            f"  AND NOT EXISTS (SELECT 1 FROM {kc} c",
            f"                  WHERE c.{c('KeyColumn', 'key_definition_id')} = k.{self.pk('KeyDefinition')} AND c.{c_active})",
            "UNION ALL",
            f"SELECT e.{en} || '#' || k.{kn}, 'key column ordinals do not run 1..n'",
            f"FROM {kd} k", entity_of,
            f"INNER JOIN {kc} c ON c.{c('KeyColumn', 'key_definition_id')} = k.{self.pk('KeyDefinition')}",
            f"WHERE k.{k_active} AND c.{c_active}", f"GROUP BY e.{en}, k.{kn}",
            f"HAVING {self.contiguous('c', c('KeyColumn', 'ordinal'))}",
            "UNION ALL",
            f"SELECT e.{en} || '#' || k.{kn} || '.' || c.{c('KeyColumn', 'column_name')},",
            "       'key column is absent from its entity'",
            f"FROM {kc} c",
            f"INNER JOIN {kd} k ON k.{self.pk('KeyDefinition')} = c.{c('KeyColumn', 'key_definition_id')}",
            entity_of, f"WHERE c.{c_active}",
            "  AND NOT EXISTS (SELECT 1 FROM information_schema.columns i",
            f"                  WHERE {scope}i.table_schema = e.{c('EntityMetadata', 'container_name')}",
            f"                    AND i.table_name = e.{c('EntityMetadata', 'table_name')}",
            f"                    AND i.column_name = c.{c('KeyColumn', 'column_name')})"])

    def check_contract_relationships(self):
        """INV-SEMANTIC-018: every relationship has at least one column pair; pairs are ordered
        1..n and their columns exist on the entities."""
        c, scope = self.col, self.columns_scope
        tr, rc, em = self.tbl("TableRelationship"), self.tbl("RelationshipColumn"), self.tbl("EntityMetadata")
        rn, r_active, c_active = c("TableRelationship", "relationship_name"), c("TableRelationship", "is_active"), c("RelationshipColumn", "is_active")
        rel_of = f"c.{c('RelationshipColumn', 'relationship_id')} = r.{self.pk('TableRelationship')}"
        en = c("EntityMetadata", "entity_name")
        return "\n".join([
            f"SELECT r.{rn}::TEXT AS identity, 'relationship has no column pair' AS defect",
            f"FROM {tr} r", f"WHERE r.{r_active}",
            f"  AND NOT EXISTS (SELECT 1 FROM {rc} c", f"                  WHERE {rel_of}",
            f"                    AND c.{c_active})",
            "UNION ALL",
            f"SELECT r.{rn}, 'relationship ordinals do not run 1..n'",
            f"FROM {tr} r", f"INNER JOIN {rc} c ON {rel_of}", f"WHERE r.{r_active} AND c.{c_active}", f"GROUP BY r.{rn}",
            f"HAVING {self.contiguous('c', c('RelationshipColumn', 'ordinal'))}",
            "UNION ALL",
            f"SELECT r.{rn}, 'relationship names an unregistered entity'",
            f"FROM {tr} r", f"WHERE r.{r_active}",
            f"  AND (NOT EXISTS (SELECT 1 FROM {em} e WHERE e.{en} = r.{c('TableRelationship', 'source_entity')})",
            f"    OR NOT EXISTS (SELECT 1 FROM {em} e WHERE e.{en} = r.{c('TableRelationship', 'target_entity')}))",
            "UNION ALL",
            f"SELECT r.{rn} || '.' || c.{c('RelationshipColumn', 'ordinal')}, 'relationship column is absent from its entity'",
            f"FROM {rc} c",
            f"INNER JOIN {tr} r ON r.{self.pk('TableRelationship')} = c.{c('RelationshipColumn', 'relationship_id')}",
            f"INNER JOIN {em} s ON s.{en} = r.{c('TableRelationship', 'source_entity')}",
            f"INNER JOIN {em} t ON t.{en} = r.{c('TableRelationship', 'target_entity')}",
            f"WHERE c.{c_active}",
            "  AND (NOT EXISTS (SELECT 1 FROM information_schema.columns i",
            f"                   WHERE {scope}i.table_schema = s.{c('EntityMetadata', 'container_name')} AND i.table_name = s.{c('EntityMetadata', 'table_name')}",
            f"                     AND i.column_name = c.{c('RelationshipColumn', 'source_column')})",
            "    OR NOT EXISTS (SELECT 1 FROM information_schema.columns i",
            f"                   WHERE {scope}i.table_schema = t.{c('EntityMetadata', 'container_name')} AND i.table_name = t.{c('EntityMetadata', 'table_name')}",
            f"                     AND i.column_name = c.{c('RelationshipColumn', 'target_column')}))"])

    def check_contract_access_columns(self):
        """INV-SEMANTIC-019: every consumer view has exactly one mapping row per output column,
        ordered 1..n, and every non-derived source exists."""
        c, scope = self.col, self.columns_scope
        ao, ac, em = self.tbl("AccessObject"), self.tbl("AccessColumn"), self.tbl("EntityMetadata")
        oi, m_active, mc = c("AccessObject", "object_identity"), c("AccessColumn", "is_active"), c("AccessColumn", "column_name")
        obj_of = f"INNER JOIN {ao} a ON a.{self.pk('AccessObject')} = m.{c('AccessColumn', 'access_object_id')}"
        where_obj = (f"{scope}i.table_schema = a.{c('AccessObject', 'container_name')} AND "
                     f"i.table_name = a.{c('AccessObject', 'object_name')}")
        return "\n".join([
            f"SELECT a.{oi} || '.' || i.column_name AS identity, 'output column has no mapping' AS defect",
            f"FROM {ao} a", "INNER JOIN information_schema.columns i", f"   ON {where_obj}",
            f"WHERE a.{c('AccessObject', 'is_active')} AND a.{c('AccessObject', 'object_type')} = 'CONSUMER_VIEW'",
            f"  AND EXISTS (SELECT 1 FROM {em} e WHERE e.{c('EntityMetadata', 'entity_name')} = a.{c('AccessObject', 'represents_entity')})",
            f"  AND NOT EXISTS (SELECT 1 FROM {ac} m",
            f"                  WHERE m.{c('AccessColumn', 'access_object_id')} = a.{self.pk('AccessObject')}",
            f"                    AND m.{mc} = i.column_name AND m.{m_active})",
            "UNION ALL",
            f"SELECT a.{oi} || '.' || m.{mc},", "       'mapping names a column the object does not have, or is repeated'",
            f"FROM {ac} m", obj_of, f"WHERE m.{m_active}",
            "  AND (NOT EXISTS (SELECT 1 FROM information_schema.columns i",
            f"                   WHERE {where_obj}", f"                     AND i.column_name = m.{mc})",
            f"    OR (SELECT count(*) FROM {ac} d",
            f"        WHERE d.{c('AccessColumn', 'access_object_id')} = m.{c('AccessColumn', 'access_object_id')}",
            f"          AND d.{mc} = m.{mc}", f"          AND d.{m_active}) > 1)",
            "UNION ALL",
            f"SELECT a.{oi}, 'mapping ordinals do not run 1..n'",
            f"FROM {ac} m", obj_of, f"WHERE m.{m_active}", f"GROUP BY a.{oi}",
            f"HAVING {self.contiguous('m', c('AccessColumn', 'ordinal'))}",
            "UNION ALL",
            f"SELECT a.{oi} || '.' || m.{mc}, 'non-derived mapping source is absent'",
            f"FROM {ac} m", obj_of, f"WHERE m.{m_active} AND m.{c('AccessColumn', 'mapping_kind')} <> 'DERIVED'",
            f"  AND NOT EXISTS (SELECT 1 FROM {em} e", "                  INNER JOIN information_schema.columns i",
            f"                     ON {scope}i.table_schema = e.{c('EntityMetadata', 'container_name')} AND "
            f"i.table_name = e.{c('EntityMetadata', 'table_name')}",
            f"                  WHERE e.{c('EntityMetadata', 'entity_name')} = m.{c('AccessColumn', 'source_entity')}",
            f"                    AND i.column_name = m.{c('AccessColumn', 'source_column')})"])

    def check_contract_composition(self):
        """INV-SEMANTIC-020: a composite has exactly one anchor, its members are ordered 1..n, and
        every other member joins to a prior member through a registered relationship in a stated
        direction."""
        c = self.col
        cp, tr, em = self.tbl("AccessComposition"), self.tbl("TableRelationship"), self.tbl("EntityMetadata")
        co, active, role = c("AccessComposition", "composite_object"), c("AccessComposition", "is_active"), c("AccessComposition", "member_role")
        me, via, direction = c("AccessComposition", "member_entity"), c("AccessComposition", "via_relationship_id"), c("AccessComposition", "via_direction")
        seq, src, tgt = c("AccessComposition", "member_seq"), c("TableRelationship", "source_entity"), c("TableRelationship", "target_entity")
        return "\n".join([
            f"SELECT c.{co}::TEXT AS identity, 'composite does not have exactly one anchor' AS defect",
            f"FROM {cp} c", f"WHERE c.{active}", f"GROUP BY c.{co}",
            f"HAVING count(*) FILTER (WHERE c.{role} = 'ANCHOR') <> 1",
            "UNION ALL",
            f"SELECT c.{co}, 'member order does not run 1..n'",
            f"FROM {cp} c", f"WHERE c.{active}", f"GROUP BY c.{co}", f"HAVING {self.contiguous('c', seq)}",
            "UNION ALL",
            f"SELECT c.{co} || '.' || c.{me},", "       'member does not join to a prior member through its relationship'",
            f"FROM {cp} c", f"WHERE c.{active} AND c.{role} <> 'ANCHOR'",
            f"  AND NOT EXISTS (SELECT 1 FROM {tr} r", f"                  INNER JOIN {cp} p",
            f"                     ON p.{co} = c.{co}", f"                    AND p.{seq} < c.{seq}",
            f"                  WHERE r.{self.pk('TableRelationship')} = c.{via}",
            f"                    AND ((c.{direction} = 'FORWARD'", f"                          AND r.{src} = p.{me}",
            f"                          AND r.{tgt} = c.{me})", f"                      OR (c.{direction} = 'REVERSE'",
            f"                          AND r.{tgt} = p.{me}", f"                          AND r.{src} = c.{me})))",
            "UNION ALL",
            f"SELECT c.{co} || '.' || c.{me},", "       'anchor carries a join, or the member names an unregistered entity'",
            f"FROM {cp} c", f"WHERE c.{active}", f"  AND ((c.{role} = 'ANCHOR'",
            f"        AND (c.{via} IS NOT NULL OR c.{direction} IS NOT NULL))",
            f"    OR NOT EXISTS (SELECT 1 FROM {em} e",
            f"                   WHERE e.{c('EntityMetadata', 'entity_name')} = c.{me}))"])

    # ---- caller-rendered: what a product's own pipelines run ------------------------------------
    def natural_column(self, keymap):
        n = keymap["column_names"][keymap["identity"]["natural"][0]]
        return n, next(c for c in keymap["columns"] if c["physical_name"] == n)["physical_type"]

    def staged_source(self, staged):
        """A table the caller has written natural values to: {container (null for a session's
        own table), name, column}."""
        source = self.qualified(staged) if staged["container"] else self.ident(staged["name"])
        return source, self.ident(staged["column"])

    def key_allocation(self, keymap, natural_value=None, staged=None):
        """The stable identifier of a natural value, allocated once and never recycled; an
        existing mapping keeps its identifier. Given `staged`, the whole set in one statement,
        NULLs and duplicates ignored, then each staged value with its identifier. The caller
        opens the transaction."""
        n, ntype = self.natural_column(keymap)
        km, cn, ident = self.qualified(keymap["objects"]["table"]), keymap["column_names"], self.ident
        stamps = f"{ident(n)}, {ident(cn['created_dts'])}, {ident(cn['updated_dts'])}"
        key = ident(keymap["key_columns"][0])
        if staged is not None:
            source, v = self.staged_source(staged)
            return "\n".join([
                f"INSERT INTO {km} ({stamps})",
                f"SELECT DISTINCT CAST(s.{v} AS {ntype}), current_timestamp, current_timestamp FROM {source} AS s WHERE s.{v} IS NOT NULL",
                f"ON CONFLICT ({ident(n)}) DO NOTHING;",
                f"SELECT k.{ident(n)}, k.{key} FROM {km} AS k WHERE k.{ident(n)} IN (SELECT s.{v} FROM {source} AS s);"])
        return self.single_key_allocation(keymap, natural_value, km, stamps, key)

    def single_key_allocation(self, keymap, natural_value, km, stamps, key):
        n = self.ident(self.natural_column(keymap)[0])
        return "\n".join([f"INSERT INTO {km} ({stamps})",
                          f"VALUES ({self.literal(natural_value)}, current_timestamp, current_timestamp)",
                          f"ON CONFLICT ({n}) DO UPDATE SET {n} = excluded.{n}", f"RETURNING {key};"])

    def maintenance_lock(self, x, stable_key):
        """A statement serialising writers of one identity, where the platform has one."""
        return None

    def instant(self, text):
        return f"{self.literal(text)}::TIMESTAMPTZ"

    def maintenance_value(self, value, col):
        return self.literal(value)

    def maintenance(self, entity, stable_key, effective_at, recorded_at, replacement_rows):
        """A transaction body closing an identity's current version and writing its replacement
        rows. `replacement_rows` are complete, non-overlapping business intervals for the
        identity, keyed by physical column name; for a bitemporal change, the complete new known
        timeline. Values are literals, never SQL; the caller controls the transaction and runs
        the checks before it commits."""
        x, ident = entity, self.ident
        cn, t, key = x["column_names"], self.qualified(x["objects"]["table"]), ident(x["version_columns"][0])
        out = [s for s in [self.maintenance_lock(x, stable_key)] if s]
        if x["bitemporal"]:
            out.append(f"UPDATE {t} SET {ident(cn['transaction_to_dts'])} = {self.instant(recorded_at)}, "
                       f"{ident(cn['is_current'])} = {self.false}, {ident(cn['updated_dts'])} = {self.now}\n"
                       f"WHERE {key} = {self.maintenance_key(stable_key)} AND {ident(cn['transaction_to_dts'])} = {self.open_end};")
        else:
            at = self.instant(effective_at)
            out.append(f"UPDATE {t} SET {ident(cn['valid_to_dts'])} = {at}, {ident(cn['is_current'])} = {self.false}, "
                       f"{ident(cn['updated_dts'])} = {self.now}\n"
                       f"WHERE {key} = {self.maintenance_key(stable_key)} AND {ident(cn['valid_from_dts'])} < {at} "
                       f"AND {at} < {ident(cn['valid_to_dts'])};")
        names = self.cols(c["physical_name"] for c in x["columns"])
        for row in replacement_rows:
            values = ", ".join(self.maintenance_value(row[c["physical_name"]], c) for c in x["columns"])
            out.append(f"INSERT INTO {t} ({names})\nVALUES ({values});")
        return "\n\n".join(out)

    def maintenance_key(self, stable_key):
        return self.literal(stable_key)

    # ---- descriptions and views -------------------------------------------------------------
    def phase_comments(self):
        """Descriptions from the specification and the module standards (RichMetadata), applied
        after the tables and before anything depends on them."""
        blocks = []
        for x in self.tables():
            t = self.qualified(x["objects"]["table"])
            lines = [f"COMMENT ON TABLE {t} IS {self.comment(x['description'])};"]
            lines += [f"COMMENT ON COLUMN {t}.{self.ident(col['physical_name'])} IS "
                      f"{self.comment(col['description'] or col['name'])};" for col in x["columns"]]
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def current(self, x, alias=""):
        """The predicate of a relation's current, undeleted rows."""
        cn = x["column_names"]
        if x["history"]:
            out = (f"{self.flag_test(alias + self.ident(cn['is_current']))} AND "
                   f"{alias}{self.ident(cn['valid_to_dts'])} = {self.open_end}")
            if x["bitemporal"]:
                out += f" AND {alias}{self.ident(cn['transaction_to_dts'])} = {self.open_end}"
        else:
            out = self.always
        if x["supports_deletion"]:
            out += f" AND {self.flag_not(alias + self.ident(cn['is_deleted']))}"
        return out

    def at(self, x, alias=""):
        """The half-open point-in-time predicate on `valid_at` and, when bitemporal, `known_at`."""
        cn = x["column_names"]
        out = (f"{alias}{self.ident(cn['valid_from_dts'])} <= valid_at AND valid_at < "
               f"{alias}{self.ident(cn['valid_to_dts'])}")
        if x["bitemporal"]:
            out += (f" AND {alias}{self.ident(cn['transaction_from_dts'])} <= known_at AND known_at < "
                    f"{alias}{self.ident(cn['transaction_to_dts'])}")
        if x["supports_deletion"]:
            out += f" AND {self.flag_not(alias + self.ident(cn['is_deleted']))}"
        return out

    def view_column_comments(self, x, view, physical_names):
        by_name = {c["physical_name"]: c for c in x["columns"]}
        return [f"COMMENT ON COLUMN {self.qualified(view)}.{self.ident(n)} IS "
                f"{self.comment(by_name[n]['description'] or by_name[n]['name'])};" for n in physical_names]

    column_comment_gap = "\n\n"  # what separates a view's column comments

    def consumer_view(self, x):
        v, names = x["objects"]["consumer_view"], [c["physical_name"] for c in x["view_columns"]]
        head = "\n".join([f"CREATE VIEW {self.qualified(v)} AS", f"SELECT {self.cols(names)}",
                          f"FROM {self.qualified(x['objects']['table'])}", f"WHERE {self.current(x)};",
                          f"COMMENT ON VIEW {self.qualified(v)} IS {self.comment('Current consumer surface: ' + x['description'])};"])
        return head + "".join(self.column_comment_gap + c for c in self.view_column_comments(x, v, names))

    def point_in_time(self, x):
        """The point-in-time accessor of a versioned relation the binding emits one for."""
        raise NotImplementedError

    def phase_views(self):
        """The consumer view of every relation that has one: current rows only, with every
        column but the open interval ends. Then the point-in-time accessor of every versioned
        relation the binding emits one for. Runtime relations have no consumer view."""
        out = [self.consumer_view(x) for x in self.relations()
               if x["relation"] == "table" and x.get("defined", True) and "consumer_view" in x["objects"]]
        out += [self.point_in_time(x) for x in self.relations()
                if x["relation"] == "table" and x.get("defined", True) and "function" in x["objects"]]
        return "\n\n".join(out)
