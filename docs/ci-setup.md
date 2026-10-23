# Setting up CI

How to make the `validate` workflow (`.github/workflows/validate.yml`) a working, required check
for `main`. Steps 1 to 3 need a Teradata system you control; steps 4 and 5 need admin rights on
the GitHub repository. Do them in order: a check can only be made required once it has run.

## What the workflow does

One job, `validate`, on every pull request and every push to `main`:

1. Starts a PostgreSQL 16 service container and installs the drivers (`duckdb`, `pytz`,
   `psycopg`, `teradatasql`).
2. Runs the validation suite (`tooling/validation/tests`): design lint, frontmatter, catalogue,
   specification and profile linting, resolver tests, binding-package hygiene, skill routing and
   the skill package.
3. Runs `tooling/bindings/conformance.py --check`. It runs the binding tests on DuckDB,
   PostgreSQL and Teradata, regenerates every binding's `CONFORMANCE.md`, and fails if a test
   fails, a test is skipped, or a committed report differs from the regenerated one.
4. Uploads the regenerated reports as the `conformance-reports` artifact, whatever happened.
5. Fails if any test anywhere reports a skip. A missing engine is a gap, never a pass.

The Teradata tests are the only ones that need something outside the runner: a Teradata system,
named by the `TERADATA_TEST_DSN` secret. Until that secret exists, CI runs without Teradata, as
described next.

## Without a Teradata system

There is no permanent Teradata system for CI yet. With `TERADATA_TEST_DSN` unset, the workflow
passes `--trust-committed teradata` to `conformance.py`:

- The Teradata engine tests skip, as before. Their outcomes come from the live run that the
  committed `implementation/teradata/CONFORMANCE.md` records, and the log says so in one line
  naming the engine version of that run.
- The committed report is trusted only if it records a clean live run: an engine version on its
  `Engine evidence:` line and every engine test passing. Otherwise the run fails as before.
- Everything else in the Teradata report is still regenerated and compared: the rendering,
  dialect and package tests, and every gap. An engine test the committed report does not carry,
  such as a new one, still fails the run, so it needs a new live run.
- DuckDB and PostgreSQL run in CI as always, and any skip of theirs fails the run.

**This trusts whoever ran the tests.** A pull request that changes the Teradata binding or its
tests must carry a Teradata report regenerated from a live run against the change. Run it with
the DSN set and commit the report:

```bash
TERADATA_TEST_DSN='{"host": "<host>", "user": "<user>", "password": "<password>"}'   python tooling/bindings/conformance.py --platform teradata
```

Reviewers check that the report's diff matches the change. Once a permanent system exists and the
secret is set (steps 1 to 4), the flag is no longer passed and every run is a live run again.

## 1. Choose a Teradata system for CI

It must be:

- **Disposable, or at least dedicated to these tests.** The tests create, and drop, every
  database and role whose name starts `anptest_`, and nothing else. Do not share the system with
  anything that uses that prefix.
- **Reachable from GitHub-hosted runners** on the Teradata port (1025). Those runners' addresses
  vary, so a system behind an IP allowlist needs a self-hosted runner instead
  (`runs-on: self-hosted` in the workflow).
- **Up whenever CI runs.** ClearScape Analytics environments stop when idle and can expire. A
  stopped or expired system makes CI fail with connection errors. For a required check, use a
  system that stays up, or accept that someone restarts it before merging.
- **Version 17.20 or later.** The binding has been tested on 20.00.24.

## 2. Create the CI user

Run as an administrator (on ClearScape, the environment's top user). Choose your own password,
and keep it out of the repository.

```sql
CREATE USER anp_ci FROM DBC AS
    PERM = 20e9,               -- two reference products deploy at once: 7 databases x 1 GB each
    SPOOL = 20e9,
    PASSWORD = "<choose one>";

GRANT CREATE DATABASE, DROP DATABASE ON anp_ci TO anp_ci;   -- the test databases live in its space
GRANT CREATE ROLE TO anp_ci;                                 -- the profiles create the product's roles
```

On ClearScape, `FROM DBC` may not be permitted. Use the environment's top user instead
(`FROM demo_user`), or run the tests as that user if it holds the `CREATE ROLE` right.

Space: each test product's databases get the binding's default `Container space` (1 GB each),
and the suite deploys the IT Service Desk and Customer Orders products at the same time, so
allow at least 15 GB of permanent space.

Check the user can do what the tests do, logged in as `anp_ci`:

```sql
CREATE DATABASE anptest_probe AS PERM = 1e6;
CREATE ROLE anptest_probe_role;
DROP ROLE anptest_probe_role;
DROP DATABASE anptest_probe;
```

## 3. Run the Teradata tests once by hand

Before trusting CI with the system, run the suite against it locally:

```bash
export TERADATA_TEST_DSN='{"host": "<host>", "user": "anp_ci", "password": "<password>"}'
python -m unittest tooling.bindings.tests.test_bindings.Teradata -v
```

Expect 19 tests to pass in 17 to 55 minutes, depending on the system's load (column comments and
other dictionary work are the slow part). When it finishes, no `anptest_` database or role is
left behind.

If a run is killed partway, its session can stay alive on the server and hold locks that make
the next run hang. Find and abort it as an administrator:

```sql
LOCKING ROW FOR ACCESS SELECT SessionNo, UserName, LogonTime FROM DBC.SessionInfoV WHERE UserName = 'ANP_CI';
SELECT SYSLIB.AbortSessions(1, 'ANP_CI', <session number>, 'Y', 'Y');
```

## 4. Add the secret

The secret is the teradatasql connection parameters, as one line of JSON:

```json
{"host": "<host>", "user": "anp_ci", "password": "<password>"}
```

Add it with the GitHub CLI, from a file so the password does not reach your shell history:

```bash
gh secret set TERADATA_TEST_DSN --repo Teradata/ai-native-data-products < teradata_ci_dsn.json
```

Or in the browser: **Settings → Secrets and variables → Actions → New repository secret**,
named `TERADATA_TEST_DSN`.

Optional keys: `"request_timeout"`, in seconds, after which one request fails rather than
waits. The test driver defaults it to 600, so a lost network response fails the run instead of
hanging it until the job's 60-minute timeout.

**Pull requests from forks get no secrets.** On those, the Teradata engine outcomes come from
the committed report, as [without a system](#without-a-teradata-system). A maintainer should
re-run the check on a branch of this repository before merging a change to the Teradata binding.

## 5. First green run

1. Push a branch, or re-run the latest workflow run (**Actions → validate → Re-run all jobs**).
2. If it fails with *CONFORMANCE.md is out of date*, the reports changed. That is expected the
   first time Teradata runs in CI, because the committed reports were generated on another
   machine. Download the `conformance-reports` artifact from the run, copy each
   `<platform>/CONFORMANCE.md` over `implementation/<platform>/CONFORMANCE.md`, read the diff,
   and commit it.
3. Re-run. Every remaining failure is a real one.

## 6. Make the check required

Once `validate` has run at least once on the repository, protect `main`. With a ruleset
(**Settings → Rules → Rulesets → New branch ruleset**):

- Target: the default branch.
- **Require a pull request before merging.**
- **Require status checks to pass**, and add `validate`.
- Optionally, **Require branches to be up to date before merging**. This makes each pull request
  re-run against the latest `main`, which on a 20-to-55-minute check is slow but catches
  conflicts between bindings.

Or with classic branch protection: **Settings → Branches → Add branch protection rule** for
`main`, **Require status checks to pass before merging**, and select `validate`.

Record in `REMAINING_WORK.md` (task 3) that enforcement is configured, since the Authoring
Standard (§9) asks maintainers to describe enforcement as manual until it is.

## Living with it

- **Runs are serialised.** The job's concurrency group `teradata-engine` lets one run use the
  Teradata system at a time, because every run owns the same `anptest_` prefix. Others queue; a
  newer push to the same branch cancels its own older run.
- **When a change alters a report**, CI fails with *out of date* and lists any gap the committed
  report does not carry. Commit the regenerated report from the artifact. A pull request must not
  add a gap (§8.1), so a new gap row in that diff is a review question, not a formality.
- **When the system expires or the password changes**, update the secret (step 4). Nothing in
  the repository names the system.
- **Locally without Teradata**, the suite still runs: the Teradata engine tests skip and the
  run reports it. `conformance.py` without `--check` regenerates the reports, and without every
  engine it writes reports showing the skips, so commit DuckDB and PostgreSQL reports from CI
  and the Teradata report from a live run, never from a partial local run.
