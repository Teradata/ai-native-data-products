---
organisation: IT Service Desk example organisation
platform: duckdb
platform_version: "1.4"
---

# Organisation Profile: IT Service Desk example (DuckDB)

The same organisation as [`teradata.md`](teradata.md), building on DuckDB. A profile is
per platform, so the organisation keeps one for each; its classification and environments
are the same, while placement and names follow what DuckDB's schemas and identifier
rules suit. Every name is derived from the specification's `product_code`.

```bash
python tooling/build/org_profile.py examples/it-service-desk-data-product/profiles/duckdb.md
```

---

## Section 1. Platform Declaration

DuckDB, where the container is a schema within the product's database file. DuckDB has no roles, so each access tier says how it is enforced outside the database.

```
Platform: -
  Container term:  SCHEMA
  Principal term:  ROLE
  Namespace:       flat
  Max name length: 120
  Name characters: lower-case letters, digits and underscore
  Reserved words:  main, information_schema, pg_catalog, temp
```

## Section 2. Container Model

One schema per module and one access schema holding every consumer view.

```
Containers: -
  memory:        {product_code|lower}_{module}
  semantic:      {product_code|lower}_{module}
  domain:        {product_code|lower}_{module}
  observability: {product_code|lower}_{module}
  search:        {product_code|lower}_{module}
  prediction:    {product_code|lower}_{module}
  access:        {product_code|lower}_access
```

## Section 3. Naming Pattern

Lower snake case. A table and its consumer view share a name and are told apart by schema;
point-in-time macros carry `at_`, similarity macros `similar_`, and key sequences `_seq`. The discovery and
trust views keep their logical names in snake case.

```
Naming: -
  Objects:
    table: {entity|snake}
    consumer_view: {entity|snake}
    function: at_{entity|snake}
    function search: similar_{entity|snake}
    sequence: {entity|snake}_seq
  Attributes: {attribute}
  Standard names:
    ColumnCatalogue: column_catalogue
    DataProductManifest: data_product_manifest
    RelationshipPaths: relationship_paths
    LineageGraph: lineage_graph
    LineageRunLatest: lineage_run_latest
    TrustMap: trust_map
```

## Section 4. Object Placement Rules

```
Placement: -
  Rules:
    table: module
    consumer_view: access
    function: module
    sequence: module
```

## Section 5. Separation Policy

```
Separation: -
  Policy:        STRICT_SEPARATION
  Object naming: container-discriminated
```

## Section 6. Derivation Function

```
Derivation: -
  Product code: ITSD
  Examples:
    - table domain Ticket History -> itsd_domain.ticket
    - consumer_view domain Ticket History -> itsd_access.ticket
    - table semantic EntityMetadata -> itsd_semantic.entity_metadata
    - consumer_view observability TrustMap -> itsd_access.trust_map
```

## Section 7. Access Model

No tier is a database principal: the binding creates no roles and issues no grants, and the
build records each tier's enforcement as stated here.

```
Principals: -
  ROLE_READ:   outside read-only file access to the database
  ROLE_AGENT:  outside the agent runtime's own connection, writing runtime Memory and agent outcomes
  ROLE_ADMIN:  outside the product owner's write access to the database file
  Grant level: object
```

## Section 8. Validation Procedure

The binding generates the placement checks from this profile and runs them after each
deployment phase, halting on any failure.

## Classification

```
Classification: -
  Scheme:  Public, Internal, Confidential, Restricted
  Default: Internal
  Markers:
    pii: Restricted
    pii-incidental: Confidential
  Protection:
    Public: none
    Internal: none
    Confidential: none
    Restricted: none
```

## Environments

```
Environments: -
  Phases:    development, test, production
  Isolation: system
```
