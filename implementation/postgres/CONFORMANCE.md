<!-- design-lint: ignore-file (implementation evidence index, not a design document) -->

# PostgreSQL conformance scope

The profile in [checks.py](checks.py) defines 542 violation queries over this fixed product. The SQL build, full profile and Python integration suite have run against PostgreSQL 18.3 through PGlite 0.5.8 and Psycopg 3.3.6. This is actual PostgreSQL execution, but does not establish native server concurrency, authentication transport, durability or PostgreSQL 16 compatibility. The version target still needs a native server matrix.

| Contract | Executable evidence | Limit |
|---|---|---|
| Domain identity, meaning, join-back | DOM-KEY, META, JOIN, BOUNDARY; native keymap FK and temporal tests | Keymap retention and privileged maintenance require operational controls |
| Semantic discovery, metrics, synonyms | SEM/REL inventory, registered resources, recursive paths, cookbook/demo execution | Fixed product model, not automatic arbitrary-schema discovery |
| Search ownership and provenance | SEARCH, JOIN, BOUNDARY; dimension rejection, ranking and live content join-back | Toy lexical quality unassessed; approximate indexing absent |
| Prediction ownership and cutoffs | PRED, JOIN, BOUNDARY; training cutoff tests | SCD2 only, no as-known correction history |
| Observability quality and lineage | OBS/VAL, event-only allowlists and append tests | No automatic capture for arbitrary maintainer SQL |
| Memory documentation and privacy | DOC/MEM-SCOPE/BOUNDARY; cookbook and authenticated RLS tests | Shared scopes and pooled end-user identity not implemented |
| Temporal lifecycle | TLM profile/type/finite/interval/view checks; overlapping history rejection; replay, late change and tombstone tests | Native concurrent-writer stress tests outstanding |
| Validation wire 2.1 | VAL counts, vocabularies, parentage; error savepoints, append, authority and expiry behavior | Count-only native producer, no legacy importer |
| Access layer | Reader view success, base/history/runtime denial; scope spoof and outcome-update rejection | Login provisioning and operator access review remain unknown |
| Object placement | PLACE and deployed resource inventory | One dedicated database; fixed roles require unused cluster names |
| Physical storage | Transactional build and rollback behavior | Backup, recovery, replication and performance remain unknown |

Strong confidence means the defined native checks for that area passed. It does not certify omitted capabilities. Access operations, physical storage and embedding quality retain explicit unknown areas. SQL-only counts are not published validation evidence.
