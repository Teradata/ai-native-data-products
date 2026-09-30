# DuckDB implementation

A portable binding of the [platform-neutral standards](../../design/), with all six modules and five patterns. The [platform profile](PLATFORM_PROFILE.md) classifies native, adapted, external and unsupported capabilities. DuckDB **1.4.3** is the minimum tested version; the build tooling requires Python **3.10+**.

From the repository root:

```sh
python -m pip install -r examples/customer360-duckdb/requirements.txt
python examples/customer360-duckdb/build.py
python examples/customer360-duckdb/agent_demo.py examples/customer360-duckdb/customer360.duckdb
python implementation/duckdb/validate.py examples/customer360-duckdb/customer360.duckdb
python -m unittest discover -s implementation/duckdb/tests
```

The builder validates a temporary file and publishes only on success. Existing files are protected; `--replace` explicitly rebuilds the synthetic example. Business data and DDL are deterministic; physical audit columns and validation evidence use actual execution instants, and each validation has a unique run id. Database bytes are not expected to be identical.

CLI-only creation also works in a **new empty** database:

```sh
duckdb customer360.duckdb < examples/customer360-duckdb/build.sql
duckdb customer360.duckdb < implementation/duckdb/patterns/validation/conformance.sql
duckdb customer360.duckdb < examples/customer360-duckdb/agent_demo.sql
```

In PowerShell, open `duckdb customer360.duckdb` and use `.read examples/customer360-duckdb/build.sql`. The checked build is ordinary SQL, also executable as a JDBC script. A CLI-only build initially publishes **no evidence / unknown**; run the Python validator to append error-aware wire-schema evidence. SQL conformance output reports counts, not fabricated validation runs.

Open the closed file in DBeaver with its DuckDB connection type and the absolute database path. Use a compatible DuckDB JDBC driver (tested SQL engine 1.4.3), e.g. `jdbc:duckdb:C:/path/customer360.duckdb`, or the equivalent POSIX path. Set `duckdb.read_only=true` for reader connections, and close them before rebuilding. GUI interaction is not part of automated verification; persistent close/reopen and read-only SQL are. The [JDBC connection documentation](https://duckdb.org/docs/stable/clients/java) describes driver properties.

| Schema | Binding |
|---|---|
| domain | Permanent keys, history, current views and as-of macros |
| semantic | Modules, objects, columns, relationships, metrics, synonyms and orientation |
| search | FLOAT arrays, exact similarity and authoritative content join-back |
| prediction | Engineered history, source cutoffs, models and outputs |
| observability | Quality, lineage, executions, validation runs and trust map |
| memory | Versioned design documentation and scoped runtime process state |

The example is intentionally synthetic: its lexical encoder and toy score make no ML-quality claims. No network/model API, external storage, VSS, or experimental persistent index is needed. **Direct access to the file exposes all data.** Logical roles and runtime privacy require an external authenticated application; views and read-only mode do not provide enterprise RBAC.

Implementation sources are `model.py`, `render.py`, authored SQL fragments, `checks.py`, `validate.py` and `temporal.py`. To change a schema or comment, edit the model and regenerate:

```sh
python implementation/duckdb/render.py
python implementation/duckdb/render.py --check
python tooling/catalogue/build_catalogue.py
python tooling/validation/design_lint.py design implementation
python -m unittest discover -s tooling/validation/tests
```

Each generated module `schema.sql` is reusable after creating its schema; consumer views require their module tables. Cross-module functions/discovery and registrations deploy after their dependencies. The full build concatenates these sources, with no runtime DDL parsing or Jinja dependency. Schema changes in real products require reviewed migrations; the fixture builder is not a production migration engine.

## Catalogue

<!-- catalogue:start -->

### Platform profile

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [DuckDB Platform Profile](PLATFORM_PROFILE.md) *(advisory)* | `duckdb` | standard | - | - | - |

### Bindings

| Document | Anchor | Status | Provides | Requires | Decisions |
|---|---|---|---|---|---|
| [DuckDB Access Layer Implementation](patterns/access-layer/README.md) | `access-layer` | standard | `AccessView` | - | - |
| [DuckDB Domain Module Implementation](modules/domain/README.md) | `domain` | standard | `AccessView`, `CurrentStateFilter`, `EntityJoinBack`, `NaturalKeyLookup`, `PointInTimeReconstruction`, `SoftDelete` | `DocumentationCapture`, `MetadataCoverageCheck`, `RichMetadata`, `SemanticRegistration`, `SurrogateKeyAllocation` | - |
| [DuckDB Memory Module Implementation](modules/memory/README.md) | `memory` | standard | `AgentContinuity`, `DocumentationCapture` | - | - |
| [DuckDB Object Placement Implementation](patterns/object-placement/README.md) | `object-placement` | standard | - | - | - |
| [DuckDB Observability Module Implementation](modules/observability/README.md) | `observability` | standard | `AgentOutcomeCapture`, `ChangeEventCapture`, `LineageCapture`, `QualityScore` | - | - |
| [DuckDB Physical Storage Implementation](patterns/physical-storage/README.md) | `physical-storage` | standard | - | - | - |
| [DuckDB Prediction Module Implementation](modules/prediction/README.md) | `prediction` | standard | `AccessView`, `CurrentStateFilter`, `PointInTimeReconstruction` | - | - |
| [DuckDB Search Module Implementation](modules/search/README.md) | `search` | standard | `Embed`, `NearestNeighbors` | - | - |
| [DuckDB Semantic Module Implementation](modules/semantic/README.md) | `semantic` | standard | `SemanticRegistration` | - | - |
| [DuckDB Temporal Lifecycle Metadata Implementation](patterns/temporal-lifecycle-metadata/README.md) | `temporal-lifecycle-metadata` | standard | `CurrentStateFilter`, `PointInTimeReconstruction`, `SoftDelete` | - | - |
| [DuckDB Validation Implementation](patterns/validation/README.md) | `validation` | standard | - | - | - |

<!-- catalogue:end -->
