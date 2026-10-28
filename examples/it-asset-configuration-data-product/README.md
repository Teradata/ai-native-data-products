# IT Asset Configuration: a worked example

A Traditional Data Product (Domain, Semantic, Observability and Memory's documentation facet), built on PostgreSQL. It is the configuration register behind the [IT Service Desk](../it-service-desk-data-product/) example: the devices, applications, servers and shared platforms its customers' tickets were about, and how they depend on one another.

Everything in this directory is input, apart from the reference design specification in [`design-output/`](design-output/), which is the design phase's expected output and the build input. Running the example produces DDL, a deployed database and a trust map, and those belong in a product repository of their own.

## What the product does

It answers what an item is, where it is, who owns it, when it falls out of support, what depends on it, and which tickets it was involved in. Its dependency network is the example's graph: an application runs on a virtual server, which is hosted on a cluster node, which connects through a core switch; every customer's applications depend on one shared identity platform.

Six entities: `ConfigurationItem` (History, `SCD2_HISTORY`, keymap), `ItemType` and `Location` (Reference, inline), `ItemDependency` and `AffectedItem` (Relationship), and the item keymap.

## What is supplied

| File | What it is |
|---|---|
| [`CMDB_Reference_Brief.md`](CMDB_Reference_Brief.md) | The fixed input: intake blocks for each phase, every catalogued decision pre-settled with its reason. |
| [`design-output/design_specification.md`](design-output/design_specification.md) | The reference design specification, validated by `spec_lint`. |
| [`config/`](../../config/) | The organisation profile, shared with the IT Service Desk: one organisation, three products. Target `postgres` places a schema per module and creates three roles. |
| `data/configuration_items.csv` | 235 items: 20 customers' devices, applications, servers and databases, and the provider's shared platforms. One live laptop lacks an end-of-support date, and two laptops share a serial number. |
| `data/ci_relationships.csv` | 300 dependencies of four kinds, up to three hops deep: application, server, cluster node, core switch. |
| `data/ticket_item_links.csv` | 161 links from the service desk's 150 tickets to the items they affected; an identity fault often also links the customer application it took down. |
| `data/ci_types.csv`, `data/locations.csv` | 17 item types on two levels; 11 datacentres, cloud regions and office sites. |

The seed data is generated from the service desk's own files: every `customer_id` and `ticket_id` here exists there. Breached hardware tickets lean towards each customer's oldest device, so the question "do tickets on ageing items breach more?" has an answer to find.

## What it deliberately exercises

- **A composition other than the maximal one.** No Search, Prediction or runtime Memory; each absence is recorded and reviewed as a coverage gap by design.
- **A departure on the temporal pattern.** `DEC-TEMPORAL-PATTERN` is `scd2`, with its reason: `ConfigurationItem` takes `SCD2_HISTORY`, so no transaction time.
- **`regulatory` retention**, the two-tier form, where the service desk took `bounded`.
- **Relationship entities**, which the service desk has none of, including one with two references to the same target, each naming its own join.
- **References to another product**, held as that product's natural keys and recorded as an open gap rather than claimed as checked.

## Running it

Follow the [IT Service Desk README](../it-service-desk-data-product/README.md)'s steps with this brief, and target `postgres`. To render the build directly:

```bash
python tooling/evals/spec_lint.py examples/it-asset-configuration-data-product/design-output/design_specification.md
python tooling/bindings/render.py examples/it-asset-configuration-data-product/design-output/design_specification.md config/implementation.example.toml --target postgres --output build/cmdb-postgres
```

Apply the phases in `manifest.json` order, load the five source files, then run `tooling/bindings/validate.py build/cmdb-postgres/manifest.json` with `POSTGRES_DSN` set. The corpus ships no product loader: loading is the product's own pipeline.
