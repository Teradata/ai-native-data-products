# Portable Customer360

This worked product uses synthetic Customer, Account, Transaction and Product entities to exercise all six modules. It includes customer changes and deletion, 12 transactions, three toy embeddings, historical engineered features, model outputs, a discovery graph, quality/lineage evidence and both Memory facets.

Follow the [build and client instructions](../../implementation/duckdb/README.md). Output is `customer360.duckdb`, generated locally and excluded from Git. Build with `python examples/customer360-duckdb/build.py`; an optional positional path chooses the output location. The checked SQL can be run directly in CLI/JDBC. Never run the fixture build over a production product.

The [design choices](../../implementation/duckdb/PLATFORM_PROFILE.md#settled-design-questions) are also deployed as Memory decisions. [Object placement](../../implementation/duckdb/patterns/object-placement/) is the conforming placement contract. The SCD2 choice deliberately omits as-known correction semantics; Prediction observation times are availability cutoffs, and retrospective feature rewrites are rejected. All instants are UTC-aware. Deletion is versioned, permanent keys are never recycled, quality lives in Observability, and demo retention is explicit rather than implied regulatory compliance.

`agent_demo.py` takes only the product name and bootstrap convention, follows ordered metadata resources, reads trust and decisions, resolves a two-hop path onto consumable objects, executes it, and reports confidence. `agent_demo.sql` is the CLI bootstrap companion; it returns the actual resources a consumer follows. This distinction avoids pretending static SQL dynamically follows object-name values.

After discovery, try these documented product operations:

```sql
SELECT * FROM search.nearest(search.embed('savings'), 2);
SELECT * FROM prediction.training_at('2025-02-15 00:00:00+00');
SELECT * FROM prediction.enriched;
SELECT * FROM observability.trust_map;
SELECT decision_id, rationale FROM memory.v_design_decision;
```

The toy encoder maps banking words to three axes. It tests retrieval mechanics and model identity, not language understanding. The score is `1 - spend_intensity`, not a calibrated churn prediction. No Domain descriptions are stored outside Domain; joined views retrieve them live.

The build's validation summary can be TRUSTED while external-security, physical-operations and embedding-quality areas remain **unknown**. Consumers read the area map, not just the summary. Revalidate after modifying data; expiry downgrades confidence and does not deny access.
