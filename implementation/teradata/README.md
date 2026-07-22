# Teradata Implementation

Platform-specific implementation of the patterns and modules defined under
[`design/`](../../design). Mirrors the design hierarchy by anchor name.

Each pattern or module has its own directory (e.g. `modules/domain/`) rather
than a single top-level file, since a given implementation is often more than
one artifact — for example a `.sql.j2` template plus supporting files.
