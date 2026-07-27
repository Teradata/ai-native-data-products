<!-- design-lint: ignore-file (documents the SQL tokens the linter matches) -->

# tooling/validation — design linter

`design_lint.py` enforces the [Design Language](../../design/core/DESIGN_LANGUAGE.md)
across both hierarchies. It is the executable form of the **No-Platform-SQL Rule**
(Section 9), the **frontmatter schema** (Section 3.1), and the **decision rules**
(Section 8). Stdlib-only, Python 3.8+.

## Run it

Lint both hierarchies:

```bash
python tooling/validation/design_lint.py design implementation
```

Lint specific files or folders:

```bash
python tooling/validation/design_lint.py design/modules/domain.md design/patterns
```

Exit code is `0` when clean, `1` when any violation is found. Wire it into CI so a
platform-SQL leak, a malformed frontmatter block, or a dangling cross-reference fails
the build.

The no-platform-SQL rules apply to `design/` only — concrete SQL is exactly what
`implementation/` exists to hold. The frontmatter and corpus rules apply to every design
document in both trees.

## Use it in module unit tests

When validating a worked module, import the checks so a test can assert its design
document is clean:

```python
from design_lint import lint_text
assert lint_text("design/modules/domain.md", text) == []
```

## What it checks

| Rule | Fails when… |
|------|-------------|
| `sql-fence` | a code block is tagged ` ```sql ` (or `tsql`, `plsql`, `psql`, `mysql`, `sqlite`). |
| `sql-statement` | a line inside any code block starts with `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `GRANT`, `REVOKE`, or `WITH`. |
| `vendor-token` | a platform data type or vendor token appears anywhere: `VARCHAR`, `BIGINT`, `BYTEINT`, `SMALLINT`, `TINYINT`, `DECIMAL(…)`, `NUMERIC(…)`, `FLOAT32`, `TIMESTAMP(…)`, `PRIMARY INDEX`, `GENERATED ALWAYS AS IDENTITY`, `NOT NULL`, `DEFAULT <value>`, `COMMENT ON`, `::VECTOR`, any `TD_*` function. |
| `unknown-type` | an attribute inside an `Entity:` pseudo-block uses a type not in the logical vocabulary (Design Language Section 4). |
| `invariant-id` | an invariant id does not match `INV-<MODULE>-<NNN>` (Design Language Section 7). |

### Frontmatter and corpus rules

| Rule | Fails when… |
|------|-------------|
| `frontmatter-missing` | a design document has no frontmatter block. |
| `frontmatter-key` | a required key is absent, an unrecognised key is present, or an implementation omits `implements` / `platform`. |
| `frontmatter-enum` | `type`, `status`, `normative`, or a requirement's `strength` carries a value outside its vocabulary. |
| `frontmatter-shape` | a `requires` entry is not a mapping of capability, strength, and provider. |
| `anchor-mismatch` | `anchor` disagrees with the document's location. |
| `unknown-capability` | a capability in `provides` / `requires` is not in the catalogue (Section 6.1). |
| `unknown-anchor` | a `patterns` or `implements` anchor resolves to no document. |
| `unknown-decision` | a declared decision id is not in the decision catalogue. |
| `invalid-choice` | a declared `choice` is not one of that decision's options. |
| `unjustified-choice` | a design departs from the advocated option without a `because` (Section 8.2). |
| `undeclared-decision` | a module describes a `History` entity without declaring how it versions and deletes (Section 8.3). |

The capability and decision catalogues are **read from the documents that define them**,
found by anchor rather than by filename — so adding a capability or a decision needs no
change to the linter.

The rule is designed to catch real entanglement without flagging ordinary English —
the words *table*, *view*, *date*, *index*, and *default* are fine in prose. Only
high-precision tokens that never appear outside SQL are matched.

## Escape hatch

A core/meta document that must legitimately name SQL (the Design Language itself, this
README) opts out in its frontmatter:

```yaml
lint: ignore-file
lint_reason: why this document must name SQL
```

A document without frontmatter uses the legacy directive on its first line:

```
<!-- design-lint: ignore-file (reason) -->
```

The waiver covers the **content** rules only. An opted-out document still has to declare
valid frontmatter, and still contributes its anchor and catalogues to the corpus.

Module and pattern documents must never use it — they are exactly the content the rule
keeps clean.

## Tests

```bash
python -m unittest discover -s tooling/validation/tests
```
