# Shared DuckDB and PostgreSQL input

`context.json` is declarative input to the reusable platform templates. It references the existing IT Service Desk brief and the same four CSV sources; it contains no rendered deployment SQL, database or completed application.

The original reference brief and Teradata placement standard are unchanged. For these two bindings, sections 3a/3b provide the business requirements. The original private GitHub/PAT, commit-author, MCP, bteq and Teradata physical-design instructions are not prerequisites for DuckDB/PostgreSQL. Use your chosen output repository and database connection. Platform placement is explicitly supplied by each sibling `placement.json`.

| Shared requirement | Input |
|---|---|
| Ticket, Agent, Customer | Permanent keymaps and SCD2_BITEMPORAL history |
| Category | Inline CURRENT_STATE reference; parent-category relationship |
| Search | One embedding entity; 384-dimensional vectors and source_attribute facet |
| Prediction | Wide TicketFeatureSet with the ten declared features; ModelPrediction with probability bounds |
| Observability | Separate quality, lineage, execution and validation structures |
| Memory | Documentation and optional scoped runtime entities |
| Retention | Three years, recorded as a design decision; no automatic deletion |

Source `created_at`/`updated_at` become Ticket `opened_dts`/`source_updated_dts`; physical row audit time remains `created_dts`/`updated_dts`. Source natural identifiers are resolved through keymaps/reference allocation. Null source values retain their meaning. Normalise naive source timestamp strings to the brief's declared UTC zone, never the machine's local zone.

The shared snapshots do not supply historical corrections. Tests construct a separate correction to prove two-axis reconstruction; do not present those test mutations as real source history. At initial ingestion record when each fact became known independently from its business effective time.

`itsd-text-384` is a declared deployment model slot, not an included encoder. Configure a real model/version before generating embeddings; do not replace 384 dimensions with a toy lexical model. Use subject plus description for the first facet and resolution_notes only when present for the second. The initial similar_tickets function covers the subject_description facet; another search declaration can bind resolution_notes with the same table. Model metadata, feature SQL, scoring artefacts and retrieval-quality evidence are builder inputs. No fabricated embeddings, breach probabilities or full documentation corpus are shipped.

The seven supplied decisions are traceable to the reference brief. The builder must complete per-module decisions, glossary, cookbook and other required capture. The validator deliberately reports memory:coverage until this is done. These inputs begin a design/build cycle; a successful render is not a completed or fully conformant data product.
