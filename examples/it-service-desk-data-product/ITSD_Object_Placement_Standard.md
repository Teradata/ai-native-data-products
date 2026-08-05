# Object Placement Standard — ITServiceDesk (Teradata)

**Standard version:** 1.0  
**Product:** ITServiceDesk (`ITSD`)  
**Platform:** Teradata Vantage 17.20  
**Separation policy:** STRICT_SEPARATION  

This is a conforming object-placement implementation. It satisfies all eight required
sections defined by the `object-placement` pattern. The build agent MUST read all eight
sections before generating any object, and MUST derive every container from Section 6.

---

## Section 1. Platform Declaration

**Platform and version:** Teradata Vantage 17.20  
**Container term:** DATABASE (Teradata `DATABASE` is the container; there is no `SCHEMA` concept above it)  
**Access principal term:** ROLE  
**Namespace structure:** Flat — databases are directly accessible by name; no hierarchical
catalog; no `catalog.schema.table` syntax (Teradata uses `database.table` only)  
**Maximum container name length:** 30 characters  
**Reserved characters:** space, dot (`.`), slash (`/`), hyphen (`-`)  
**Naming rule for ITSD databases:** alphanumeric and underscore only  
**Reserved words:** standard Teradata SQL reserved words; additionally `DBC`, `SYSLIB`,
`SYSBAR`, `TDSTATS`, `TDWM` are system databases and must not be used  

---

## Section 2. Container Model

**Structure:** child containers only — no structural or parent containers in Teradata.
Each database is a peer-level child container holding objects for exactly one module.

**Containers for this product:**

| Database | Module | Holds |
|---|---|---|
| `ITSD_MEM` | Memory | Tables: the six documentation entities and the five runtime entities the Memory module defines |
| `ITSD_SEM` | Semantic | Tables: EntityMetadata, ColumnMetadata, NamingStandard, TableRelationship, DataProductMap, PrimaryObject |
| `ITSD_DOM` | Domain | Tables: Keymap tables, History tables, Reference tables; Views: *_Current base views |
| `ITSD_OBS` | Observability | Tables: ChangeEvent, DataQualityMetric, DataLineage, LineageRun, ModelPerformance, AgentOutcome |
| `ITSD_SCH` | Search | Tables: EntityEmbedding |
| `ITSD_PRD` | Prediction | Tables: TicketFeatureSet (a FeatureGroup), ModelPrediction |
| `ITSD_ACC` | Access Layer | Views only — all consumer-facing views |

**Rules:**
- Each module has exactly one database.
- No module places objects in another module's database.
- Consumer-facing views always live in `ITSD_ACC`, never in the module database.
  Exception: `_Current` base views in `ITSD_DOM` are tier-1 views for internal module use,
  not consumer-facing; they are not exposed to end users directly.
- No data objects (tables, views) are placed in a parent or structural container; there are
  none in this implementation.
- No physical boundary exists between environments; environment isolation uses separate
  Teradata systems (not separate databases within one system).

---

## Section 3. Naming Pattern

**Container naming pattern:**

```
{ProductCode}_{ModuleAbbrev}
```

| Segment | Position | Values | Mandatory | Separator |
|---|---|---|---|---|
| `ProductCode` | 1 | `ITSD` (fixed) | Yes | `_` |
| `ModuleAbbrev` | 2 | `MEM`, `SEM`, `DOM`, `OBS`, `SCH`, `PRD`, `ACC` | Yes | — |

**Module abbreviations:**

| Module | Abbreviation | Database |
|---|---|---|
| Memory | `MEM` | `ITSD_MEM` |
| Semantic | `SEM` | `ITSD_SEM` |
| Domain | `DOM` | `ITSD_DOM` |
| Observability | `OBS` | `ITSD_OBS` |
| Search | `SCH` | `ITSD_SCH` |
| Prediction | `PRD` | `ITSD_PRD` |
| Access Layer | `ACC` | `ITSD_ACC` |

**Object naming within containers:**

Rule A — container-discriminated (`STRICT_SEPARATION`): the container is the sole type
discriminator. Object names are identical across container types. Type markers on object
names are prohibited.

Worked examples:
- Consumer-facing ticket view: name is `Ticket`, placed in `ITSD_ACC` → `ITSD_ACC.Ticket`
- Ticket history table: name is `Ticket_History`, placed in `ITSD_DOM` → `ITSD_DOM.Ticket_History`
- Ticket current base view: name is `Ticket_Current`, placed in `ITSD_DOM` → `ITSD_DOM.Ticket_Current`
- Entity embedding table: name is `EntityEmbedding`, placed in `ITSD_SCH` → `ITSD_SCH.EntityEmbedding`

**Environment-agnostic rule:** Object names are stable across lifecycle environments
(development, test, production). Only the Teradata system changes between environments;
container names on a given system do not carry environment markers. An object named
`ITSD_DOM.Ticket_History` on the dev system has the same name on production. This is
`INV-MASTER-006` conformant.

**View-tier architecture:**
- **Tier 1 (base views):** `_Current` views in module databases (e.g. `ITSD_DOM.Ticket_Current`).
  Reference base tables in the same database. For internal module use; agents and analysts
  do not query these directly.
- **Tier 2 (consumer views):** All views in `ITSD_ACC`. These are the only views granted
  to end-user roles. Tier 2 views may reference Tier 1 views in module databases via
  cross-database references (e.g. `ITSD_DOM.Ticket_Current`); they never reference raw
  history tables directly.

---

## Section 4. Object Placement Rules

**Separation policy:** `STRICT_SEPARATION`

| Object type | Container | Notes |
|---|---|---|
| Persistent tables (Domain) | `ITSD_DOM` | History, Reference, Keymap tables |
| Persistent tables (Memory) | `ITSD_MEM` | Documentation facet (six entities) and runtime facet (five entities) |
| Persistent tables (Semantic) | `ITSD_SEM` | Catalogue and registry tables |
| Persistent tables (Observability) | `ITSD_OBS` | Event, quality, lineage and outcome entities |
| Persistent tables (Search) | `ITSD_SCH` | EntityEmbedding |
| Persistent tables (Prediction) | `ITSD_PRD` | TicketFeatureSet, ModelPrediction |
| Tier-1 base views (`_Current`) | `ITSD_DOM` | Co-located with Domain base tables; internal use only |
| Tier-2 consumer views | `ITSD_ACC` | All views visible to end-user roles |
| Stored procedures | Same database as the module they primarily serve | No cross-module stored procedures |
| Stored functions (UDFs) | `ITSD_DOM` | UDFs that serve domain transformations |
| Macros | Same database as primary use | Follow object type rules |
| Join indexes | Same database as base table | Always co-located |
| Secondary indexes | Same database as base table | Always co-located |
| Temporary / derived tables (loading) | Spool or `ITSD_DOM` work tables | Cleared after each load |

**Prohibited:**
- Tables in `ITSD_ACC` — this database holds views only
- Consumer-facing views in any module database (ITSD_DOM, ITSD_OBS, etc.)
- Any object in a system database (DBC, SYSLIB, etc.)

---

## Section 5. Separation Policy

**Policy: `STRICT_SEPARATION`**

Each module has exactly one database. Object types are separated by database; no types are
co-located across modules. The container is the sole type discriminator; type markers on
object names are prohibited.

**Rationale:** End users are granted access at the database level to `ITSD_ACC` only.
Module databases are not visible to end users; only the agent role has write-back access to
`ITSD_MEM.AgentSession`. Strict separation ensures that granting a consumer role access to
the views database does not expose base tables in any module database.

**Exceptions:** None. Base `_Current` views live in `ITSD_DOM` as an internal tier, but
they are not granted to end-user roles and do not violate the policy.

**Access implication:** Cross-container view compilation requires implied grants (see
Section 7). These are provisioned before consumer views are created.

---

## Section 6. Derivation Function

```
derive_container(
  object_type,    -- 'table' | 'view_base' | 'view_consumer' | 'procedure'
                  -- | 'function' | 'join_index' | 'macro' | 'temporary'
  module,         -- 'Memory' | 'Semantic' | 'Domain' | 'Observability'
                  --   | 'Search' | 'Prediction' | 'AccessLayer'
  product_code    -- 'ITSD' (fixed)
) -> database_name (string)

MODULE_ABBREV = {
  'Memory':       'MEM',
  'Semantic':     'SEM',
  'Domain':       'DOM',
  'Observability':'OBS',
  'Search':       'SCH',
  'Prediction':   'PRD',
  'AccessLayer':  'ACC'
}

function derive_container(object_type, module, product_code='ITSD'):

  if object_type == 'view_consumer':
    -- Consumer-facing views always go to the access layer, regardless of module
    return f"{product_code}_ACC"

  if object_type == 'temporary':
    -- Teradata spool; no named container
    return 'SPOOL'

  if module not in MODULE_ABBREV:
    STOP("Unknown module: " + module)

  if object_type in ('table', 'view_base', 'procedure', 'function',
                     'join_index', 'macro'):
    abbrev = MODULE_ABBREV[module]
    return f"{product_code}_{abbrev}"

  STOP("Unknown object_type: " + object_type)
```

**Worked examples:**

| Call | Result |
|---|---|
| `derive_container('table', 'Domain')` | `ITSD_DOM` |
| `derive_container('view_consumer', 'Domain')` | `ITSD_ACC` |
| `derive_container('table', 'Search')` | `ITSD_SCH` |
| `derive_container('view_base', 'Domain')` | `ITSD_DOM` |
| `derive_container('table', 'Observability')` | `ITSD_OBS` |
| `derive_container('table', 'Memory')` | `ITSD_MEM` |
| `derive_container('view_consumer', 'Prediction')` | `ITSD_ACC` |

---

## Section 7. Access Model

**Grant level:** database-level for read; object-level for write-back (Memory AgentSession
only). End-user principals are granted roles only; never granted directly on databases or
tables.

**Standard principal types:**

The three roles the access-layer pattern defines. There is no fourth consumer tier: a
reader and an analyst reach the product through the same access container, and the
distinction between them is which views they are pointed at, not which databases they hold
rights on.

| Role | Database access | Write-back |
|---|---|---|
| `ITSD_ROLE_READ` | SELECT on `ITSD_ACC`, `ITSD_SEM` | None |
| `ITSD_ROLE_AGENT` | SELECT on `ITSD_ACC`, `ITSD_SEM` | INSERT on `ITSD_MEM` (runtime entities) and `ITSD_OBS` |
| `ITSD_ROLE_ADMIN` | ALL PRIVILEGES on all `ITSD_*` databases | Full |

Each role carries a comment of one short sentence naming its consumers, never the
containers it reaches: the grant boundary above is the authoritative statement, and a
comment repeating it publishes the access design to anyone who can query the catalogue.

**Prohibitions:**
- Users must never be granted directly on module databases.
- The `ITSD_ACC` database is for views only; no tables should exist here, so table-level
  grants to this database are an error.
- Only `ITSD_ROLE_ADMIN` has read access to `ITSD_DOM`, `ITSD_OBS`, `ITSD_SCH`, `ITSD_PRD`
  and `ITSD_MEM` directly, except the agent append grants on `ITSD_MEM` and `ITSD_OBS`.
- The agent write-back is append-only and reaches the runtime entities. The documentation
  facet is written at deploy time by the capture protocol, not by an agent at runtime.

**Implied grants:** Consumer views in `ITSD_ACC` reference base tables and Tier-1 views in
module databases via cross-database syntax (e.g. `ITSD_DOM.Ticket_Current`). For these
views to compile, the owner of `ITSD_ACC` (or the compilation context) requires SELECT on
each referenced module database. These implied grants must be provisioned as part of Phase
1.5 (before Domain is deployed), not as an afterthought.

**Implied grant SQL:**
```sql
GRANT SELECT ON ITSD_DOM TO ITSD_ACC WITH GRANT OPTION;
GRANT SELECT ON ITSD_OBS TO ITSD_ACC WITH GRANT OPTION;
GRANT SELECT ON ITSD_SCH TO ITSD_ACC WITH GRANT OPTION;
GRANT SELECT ON ITSD_PRD TO ITSD_ACC WITH GRANT OPTION;
GRANT SELECT ON ITSD_SEM TO ITSD_ACC WITH GRANT OPTION;
GRANT SELECT ON ITSD_MEM TO ITSD_ACC WITH GRANT OPTION;
```

These are provisioned in `03_access_phase1.sql`.

---

## Section 8. Validation Procedure

Run after deployment completes. Execute each query via the Teradata MCP Server and verify
the expected result. Halt and report on any failure; do not proceed to dependent objects or
silently auto-correct.

```sql
-- CHECK 1: All ITSD databases exist
SELECT DatabaseName
FROM DBC.DatabasesV
WHERE DatabaseName IN (
  'ITSD_MEM','ITSD_SEM','ITSD_DOM','ITSD_OBS','ITSD_SCH','ITSD_PRD','ITSD_ACC'
)
ORDER BY 1;
-- Expected: 7 rows (one per database)
-- Fail if: any database is missing

-- CHECK 2: All roles exist
SELECT RoleName
FROM DBC.RolesV
WHERE RoleName IN (
  'ITSD_ROLE_READ','ITSD_ROLE_AGENT','ITSD_ROLE_ADMIN'
)
ORDER BY 1;
-- Expected: 3 rows
-- Fail if: any role is missing

-- CHECK 3: No tables exist in ITSD_ACC (views only)
SELECT TableName, TableKind
FROM DBC.TablesV
WHERE DatabaseName = 'ITSD_ACC'
  AND TableKind = 'T';  -- T = table
-- Expected: 0 rows
-- Fail if: any table found in ITSD_ACC

-- CHECK 4: No consumer views outside ITSD_ACC
-- (Tier-1 _Current views in ITSD_DOM are permitted; exclude them)
SELECT DatabaseName, TableName
FROM DBC.TablesV
WHERE DatabaseName IN ('ITSD_MEM','ITSD_SEM','ITSD_DOM','ITSD_OBS','ITSD_SCH','ITSD_PRD')
  AND TableKind = 'V'
  AND TableName NOT LIKE '%_Current';  -- Allow Tier-1 base views in ITSD_DOM
-- Expected: 0 rows
-- Fail if: any non-Current view exists in a module database

-- CHECK 5: Implied grants present for ITSD_ACC
SELECT Grantee, DatabaseName, AccessRight
FROM DBC.AllRightsV
WHERE Grantee = 'ITSD_ACC'
  AND DatabaseName IN ('ITSD_DOM','ITSD_OBS','ITSD_SCH','ITSD_PRD','ITSD_SEM','ITSD_MEM')
  AND AccessRight = 'SEL'
ORDER BY DatabaseName;
-- Expected: 6 rows (one per source module database)
-- Fail if: any module database missing from grant set

-- CHECK 6: End-user roles not granted directly on module databases
SELECT Grantee, DatabaseName
FROM DBC.AllRightsV
WHERE Grantee IN ('ITSD_ROLE_READ','ITSD_ROLE_AGENT')
  AND DatabaseName IN ('ITSD_DOM','ITSD_OBS','ITSD_SCH','ITSD_PRD','ITSD_MEM')
  AND AccessRight = 'SEL';
-- Expected: 0 rows
-- Fail if: any row returned (means a role has been granted beyond its permitted scope)
```

**Halt-and-report rule:** if any check returns an unexpected result, stop further
deployment, report the failing check and its actual output, and do not proceed. Never
silently auto-correct a placement error.
