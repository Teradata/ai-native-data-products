# Semantic — Data Product Orientation Layer (Teradata / MCP)

Binding of [`design/modules/semantic.md`](../../../../design/modules/semantic.md) §4. Product-first
discovery: a client orients to the product before touching module maps or data. Backed by
`governance.data_product_registry` (`03-registry.sql`); the manifest is stored in `manifest_json`.

## MCP resource / tool shapes

MCP servers expose the orientation layer as **resources first** (context) and **tools second**
(actions):

```text
/resources
  /products
  /products/{product_id}/manifest
  /products/{product_id}/contract
  /products/{product_id}/semantic
  /products/{product_id}/lineage
  /products/{product_id}/quality
  /products/{product_id}/policy
  /products/{product_id}/physical-map

/tools
  search_data_products
  describe_data_product
  get_recommended_entrypoint
  query_product_data
  explain_access_path
```

## Metadata-first handshake

1. Client asks what products are available.
2. Server returns products and manifest resources (from `data_product_registry`).
3. Client reads the selected product's manifest.
4. Server recommends navigation: contract → semantic model → policy → quality → lineage → data access.
5. Client queries data **only** through the approved entrypoint.

## Discovery manifest (stored in `manifest_json`, exposed at `/products/{id}/manifest`)

```yaml
data_product_id: call_centre.customer_experience
name: Customer Experience Data Product
version: 1.0.0

entrypoints:
  orientation: mcp://products/call_centre/customer_experience/manifest
  contract: mcp://products/call_centre/customer_experience/contract
  semantic_model: mcp://products/call_centre/customer_experience/semantic
  lineage: mcp://products/call_centre/customer_experience/lineage
  quality: mcp://products/call_centre/customer_experience/quality
  policy: mcp://products/call_centre/customer_experience/access-policy
  data_access: mcp://products/call_centre/customer_experience/data

recommended_navigation:
  - contract
  - semantic_model
  - policy
  - quality
  - lineage
  - data_access
```

The manifest tells the agent what the product is, what it means, what it trusts, what it may access,
and how to proceed. The registry also names the **gate-authoritative producer** the
[validation pattern](../../patterns/validation/) reads, so trust evaluation precedes analytical use.

## Required documentation record

When the orientation layer is deployed, generate `DD-DISCOVERY-001` in the product's Memory
documentation facet (recording why agents read the manifest before metadata maps or data) — per the
Memory capture protocol.
