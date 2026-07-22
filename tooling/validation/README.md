<!-- design-lint: ignore-file (documents the SQL tokens the linter matches) -->

# tooling/validation — design linter

`design_lint.py` enforces the [Design Language](../../design/core/DESIGN_LANGUAGE.md)
on everything under `design/`. It is the executable form of the **No-Platform-SQL Rule**
(Design Language Section 8) plus lightweight structural checks. Stdlib-only, Python 3.8+.

## Run it

Lint the whole design hierarchy:

```bash
python tooling/validation/design_lint.py design
```

Lint specific files or folders:

```bash
python tooling/validation/design_lint.py design/modules/domain.md design/patterns
```

Exit code is `0` when clean, `1` when any violation is found. Wire it into CI against
`design/` so a platform-SQL leak fails the build.

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

The rule is designed to catch real entanglement without flagging ordinary English —
the words *table*, *view*, *date*, *index*, and *default* are fine in prose. Only
high-precision tokens that never appear outside SQL are matched.

## Escape hatch

A core/meta document that must legitimately name SQL (the Design Language itself, this
README) opts out with a directive on its first line:

```
<!-- design-lint: ignore-file (reason) -->
```

Module and pattern documents must never use it — they are exactly the content the rule
keeps clean.

## Tests

```bash
python -m unittest discover -s tooling/validation/tests
```
