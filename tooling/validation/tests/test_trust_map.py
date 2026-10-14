"""The trust map's read path, executed.

Every scenario here is one the review of #57 asked for. They are behavioural, not
structural: each states a property of the map a consumer depends on, then executes the
shipped SQL to check it holds. That matters because all three read-path defects the
review found were invisible to inspection and obvious the moment the query ran.

The properties, and why each is worth a test rather than a comment:

  * **Areas are graded against the run that produced them.** The map resolves the latest
    entry per area independently, so two entries can come from different runs. Grading
    staleness against the producer's newest run therefore certifies old evidence as
    fresh - a passed check being reported for a state of the product that no longer
    holds, which is the one thing staleness exists to prevent.
  * **The legacy fallback covers legacy producers only.** It exists so a 2.0 producer
    still has a readable one-area map. A malformed 2.1 run that publishes no areas must
    fail VAL-18 instead of being re-dressed as legacy, and a future major version must
    not be mistaken for an old one by a string comparison.
  * **A requested area always answers.** An area with no published entry reads
    `no-evidence` / `unknown`. Dropping the row instead makes an unvalidated area
    indistinguishable from a sound one: the exact failure the map was built to remove.
  * **An area's identity resolves.** `scope_id` typos are silent - a check reporting on
    `MODULE:domian` passes every count-based rule and describes nothing.

Run:
    python -m unittest discover -s tooling/validation/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from td_sqlite import (  # noqa: E402
    SEMANTIC,
    VALIDATION,
    Fixture,
    statement_from,
    ts,
)

CONFORMANCE = VALIDATION / "conformance-queries.sql"
CONSUMER = VALIDATION / "consumer-queries.sql"
SEMANTIC_CHECKS = SEMANTIC / "validation.sql.j2"

PRODUCT = "CALLCENTRE"
PRODUCER = "trust-engine"
PARAMS = {"product_prefix": PRODUCT, "trust_producer": PRODUCER}


class TrustMapCase(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.close)

    def entry(self, scope_kind, scope_id):
        rows = self.fx.trust_map(scope_kind=scope_kind, scope_id=scope_id)
        self.assertEqual(
            len(rows), 1,
            "expected exactly one map entry for %s:%s, got %d - the latest-per-area "
            "projection is not deterministic" % (scope_kind, scope_id, len(rows)))
        return rows[0]

    def conformance(self, marker, params=None):
        """Rows returned by a conformance check. Zero rows means conforming."""
        return self.fx.rows(statement_from(CONFORMANCE, marker), params)


class StalenessIsPerArea(TrustMapCase):
    """Scenario 1-3: mixed-age areas."""

    def test_each_area_is_graded_against_its_own_run(self):
        # Two areas whose latest entries come from runs 29 days apart. Both were 'strong'
        # when recorded; only the older one is past the 7-day default window now.
        self.fx.insert_run(run_id="OLD", completed_dts=ts(-29))
        self.fx.insert_area(run_id="OLD", scope_kind="MODULE", scope_id="search")
        self.fx.insert_run(run_id="NEW", completed_dts=ts(-1))
        self.fx.insert_area(run_id="NEW", scope_kind="MODULE", scope_id="domain")

        stale = self.entry("MODULE", "search")
        fresh = self.entry("MODULE", "domain")

        self.assertEqual(stale["evidence_is_stale"], 1)
        self.assertEqual(
            stale["confidence"], "unknown",
            "a 29-day-old area read at its recorded confidence: staleness is being "
            "evaluated against a newer run than the one that produced this evidence")
        self.assertEqual(
            stale["recorded_confidence"], "strong",
            "the recorded confidence must survive alongside the downgrade, so a "
            "consumer can say what the evidence claimed and when")

        self.assertEqual(fresh["evidence_is_stale"], 0)
        self.assertEqual(fresh["confidence"], "strong")

    def test_a_newer_run_does_not_refresh_an_area_it_did_not_cover(self):
        # The producer's latest run is minutes old but covers only 'domain'. The 'search'
        # entry it left untouched is still 40-day-old evidence and must read that way.
        self.fx.insert_run(run_id="OLD", completed_dts=ts(-40))
        self.fx.insert_area(run_id="OLD", scope_kind="MODULE", scope_id="search")
        self.fx.insert_run(run_id="LATEST", completed_dts=ts())
        self.fx.insert_area(run_id="LATEST", scope_kind="MODULE", scope_id="domain")

        self.assertEqual(
            self.entry("MODULE", "search")["confidence"], "unknown",
            "an area untouched by the newest run was graded by that run's clock")

    def test_a_producer_declared_expiry_overrides_the_default_window(self):
        # Inside the 7-day window, but the producer said this evidence expires sooner.
        self.fx.insert_run(run_id="R1", completed_dts=ts(-2),
                           evidence_expires_dts=ts(-1))
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="domain")

        entry = self.entry("MODULE", "domain")
        self.assertEqual(entry["evidence_is_stale"], 1)
        self.assertEqual(entry["confidence"], "unknown")
        self.assertIn("re-run", entry["recommended_action"].lower())

    def test_the_latest_entry_per_area_breaks_ties_deterministically(self):
        # Two runs completing in the same instant: VAL-09 makes run_id DESC the tie-break,
        # so the projection yields one row rather than an arbitrary one or both.
        same_instant = ts(-1)
        for run_id in ("RUN-A", "RUN-B"):
            self.fx.insert_run(run_id=run_id, completed_dts=same_instant)
        self.fx.insert_area(run_id="RUN-A", area_status="pass", confidence="strong")
        self.fx.insert_area(run_id="RUN-B", area_status="fail", confidence="weak",
                            passed_count=3, failed_count=1, critical_failure_count=1)

        self.assertEqual(self.entry("MODULE", "domain")["run_id"], "RUN-B")


class LegacyFallbackIsScoped(TrustMapCase):
    """Scenario 4-6: legacy runs, and the runs that must not be treated as legacy."""

    def test_a_legacy_run_projects_one_derived_product_entry(self):
        self.fx.insert_run(run_id="L1", payload_schema_version="2.0",
                           completed_dts=ts(-1), total_checks=8, passed_count=8)

        entry = self.entry("PRODUCT", PRODUCT)
        self.assertEqual(entry["map_source"], "DERIVED")
        self.assertEqual(
            entry["confidence"], "partial",
            "a derived entry is capped at 'partial': a run-level pass says nothing "
            "about which areas the run covered")
        self.assertEqual(entry["area_status"], "pass")
        self.assertTrue(entry["open_gaps"], "a derived entry must state its own limits")

    def test_a_malformed_canonical_run_is_not_re_dressed_as_legacy(self):
        # A 2.1 run that published no area rows. It has no map, and that is a defect to
        # report - not a legacy producer to accommodate.
        self.fx.insert_run(run_id="BAD", payload_schema_version="2.1",
                           completed_dts=ts(-1))

        self.assertEqual(
            self.fx.trust_map(), [],
            "a 2.1 run publishing no areas was given a derived PRODUCT entry, which "
            "hides the defect behind a map that looks legitimate")
        self.assertEqual(
            len(self.conformance(
                "VAL-18 (every canonical-schema run publishes at least one area entry")),
            1,
            "the malformed run must be reported by VAL-18 instead")

    def test_the_fallback_is_scoped_to_the_run_not_the_producer(self):
        # The producer published 2.1 areas historically and has now regressed to a 2.0
        # run. The current run still needs a readable map, so the fallback must fire for
        # it despite the older run's area rows existing.
        self.fx.insert_run(run_id="HIST", payload_schema_version="2.1",
                           completed_dts=ts(-3))
        self.fx.insert_area(run_id="HIST", scope_kind="MODULE", scope_id="domain")
        self.fx.insert_run(run_id="NOW", payload_schema_version="2.0",
                           completed_dts=ts(-1), total_checks=6, passed_count=6)

        derived = [r for r in self.fx.trust_map() if r["map_source"] == "DERIVED"]
        self.assertEqual(
            len(derived), 1,
            "the legacy fallback was suppressed by an unrelated older run's area rows, "
            "leaving the current run with no map at all")
        self.assertEqual(derived[0]["run_id"], "NOW")

    def test_an_unregistered_future_version_is_not_treated_as_legacy(self):
        # '10.0' sorts below '2.1' as a string. A lexical test would call this legacy and
        # publish a derived entry over a schema it has never seen.
        self.fx.insert_run(run_id="FUTURE", payload_schema_version="10.0",
                           completed_dts=ts(-1))

        self.assertEqual(
            [r for r in self.fx.trust_map() if r["map_source"] == "DERIVED"], [],
            "a future major version was matched as a legacy binding by string "
            "comparison; legacy versions are enumerated explicitly")

    def test_a_future_version_is_still_held_to_the_canonical_rules(self):
        # The other half of the same rule: excluding registered legacy versions means a
        # future version stays inside every canonical check rather than falling out of it.
        self.fx.insert_run(run_id="FUTURE", payload_schema_version="10.0",
                           completed_dts=ts(-1), agent_use_allowed=0)

        self.assertEqual(
            len(self.conformance("VAL-02")), 1,
            "a 10.0 run escaped VAL-02: the check is selecting records by comparing "
            "payload_schema_version lexically against '2.1'")


class RequestedAreasAlwaysAnswer(TrustMapCase):
    """Scenario 7: a requested area with no published entry."""

    def reconciled(self):
        return self.fx.rows(
            statement_from(CONSUMER, "-- 1. The areas this query plan touches"), PARAMS)

    def test_an_area_with_no_entry_reads_unknown_rather_than_disappearing(self):
        self.fx.insert_run(run_id="R1", completed_dts=ts(-1))
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="domain")
        self.fx.request(("MODULE", "domain"), ("ENTITY", "domain.Ticket"))

        rows = {(r["scope_kind"], r["scope_id"]): r for r in self.reconciled()}

        self.assertEqual(
            len(rows), 2,
            "a requested area vanished from the result: an area the map says nothing "
            "about is indistinguishable from one it passed")
        missing = rows[("ENTITY", "domain.Ticket")]
        self.assertEqual(missing["area_status"], "no-evidence")
        self.assertEqual(missing["confidence"], "unknown")
        self.assertEqual(missing["map_source"], "NONE")
        self.assertTrue(missing["open_gaps"])
        self.assertTrue(missing["recommended_action"])
        self.assertEqual(rows[("MODULE", "domain")]["confidence"], "strong")

    def test_areas_the_request_does_not_touch_are_absent(self):
        # The complement of the rule above: the map does not volunteer unrelated areas,
        # because a failure outside what the query reaches places no constraint on it.
        self.fx.insert_run(run_id="R1", completed_dts=ts(-1))
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="domain")
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="prediction",
                            area_status="fail", confidence="weak",
                            passed_count=3, failed_count=1, critical_failure_count=1)
        self.fx.request(("MODULE", "domain"))

        self.assertEqual([r["scope_id"] for r in self.reconciled()], ["domain"])

    def test_a_requested_area_whose_evidence_is_stale_reads_unknown(self):
        self.fx.insert_run(run_id="R1", completed_dts=ts(-30))
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="domain")
        self.fx.request(("MODULE", "domain"))

        row = self.reconciled()[0]
        self.assertEqual(row["confidence"], "unknown")
        self.assertEqual(row["evidence_is_stale"], 1)
        self.assertEqual(row["recorded_confidence"], "strong")


class AreaIdentityResolves(TrustMapCase):
    """Scenario 8: invalid identifiers."""

    def setUp(self):
        super().setUp()
        self.fx.db.execute(
            "INSERT INTO data_product_map (module_name, is_active) VALUES ('DOMAIN', 1)")
        self.fx.db.execute(
            "INSERT INTO entity_metadata (module_name, entity_name, is_active)"
            " VALUES ('DOMAIN', 'Ticket', 1)")
        self.fx.insert_run(run_id="R1", completed_dts=ts(-1))

    def test_a_module_typo_is_reported(self):
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="domian")

        found = self.conformance("VAL-14 (MODULE scope resolves)")
        self.assertEqual(
            [r["scope_id"] for r in found], ["domian"],
            "a module-scoped area naming no deployed module passed VAL-14; the check "
            "accepts any non-empty string")

    def test_a_real_module_resolves(self):
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="domain")
        self.assertEqual(self.conformance("VAL-14 (MODULE scope resolves)"), [])

    def test_an_inactive_module_does_not_resolve(self):
        self.fx.db.execute("INSERT INTO data_product_map (module_name, is_active)"
                           " VALUES ('SEARCH', 0)")
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="search")

        self.assertEqual(
            [r["scope_id"] for r in self.conformance("VAL-14 (MODULE scope resolves)")],
            ["search"],
            "an area scoped to a module the product has retired resolved anyway")

    def test_a_product_scope_naming_another_product_is_reported(self):
        self.fx.insert_area(run_id="R1", scope_kind="PRODUCT", scope_id="OTHERPRODUCT",
                            checks_expected=1, checks_ran=1, passed_count=1)

        self.assertEqual(
            [r["scope_id"] for r in self.conformance("VAL-14 (PRODUCT scope resolves)")],
            ["OTHERPRODUCT"])

    def test_an_entity_scope_must_be_module_qualified_and_catalogued(self):
        self.fx.insert_area(run_id="R1", scope_kind="ENTITY", scope_id="domain.Ticket")
        self.fx.insert_area(run_id="R1", scope_kind="ENTITY", scope_id="domain.Phantom")

        self.assertEqual(
            [r["scope_id"] for r in self.conformance("VAL-14 (ENTITY scope resolves)")],
            ["domain.Phantom"],
            "an entity-scoped area naming no catalogued entity resolved anyway")

    def test_an_areas_completed_dts_must_match_its_run(self):
        # VAL-09. The trust map joins an area to its own run to date the evidence, so an
        # area carrying a different instant dates itself against a clock it never ran on.
        self.fx.insert_area(run_id="R1", scope_kind="MODULE", scope_id="domain",
                            completed_dts=ts(-9))

        self.assertEqual(
            len(self.conformance("VAL-09: an area's completed_dts")), 1,
            "an area whose completed_dts disagrees with its parent run passed VAL-09")


class TrustRoleIsCanonicalised(unittest.TestCase):
    """Scenario 9: TRUST_GATE and TRUST_MAP are one role under two spellings.

    The manifest treats them as aliases, so the singular-role check has to as well.
    Grouping the raw strings lets a product publish both and pass, which is how a
    product ends up with two trust entrypoints and a reader that picks one by string
    ordering.
    """

    ROLE_CHECK = "INV-SEMANTIC-011: duplicate active role for one product"

    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.close)
        self.query = statement_from(
            SEMANTIC_CHECKS, self.ROLE_CHECK,
            substitutions={"{{ product }}_Semantic.": ""})

    def add_role(self, role, order, product="CALLCENTRE"):
        self.fx.db.execute(
            "INSERT INTO data_product_orientation"
            " (product_id, resource_role, discovery_order, is_active)"
            " VALUES (?, ?, ?, 1)", (product, role, order))

    def test_both_spellings_of_the_trust_role_count_as_a_duplicate(self):
        self.add_role("MANIFEST", 1)
        self.add_role("TRUST_MAP", 2)
        self.add_role("TRUST_GATE", 3)

        found = self.fx.rows(self.query)
        self.assertEqual(
            [r["canonical_resource_role"] for r in found], ["TRUST_MAP"],
            "a product publishing both spellings of the trust role passed the "
            "singular-role check")

    def test_one_spelling_is_not_a_duplicate(self):
        self.add_role("MANIFEST", 1)
        self.add_role("TRUST_GATE", 2)
        self.assertEqual(self.fx.rows(self.query), [])

    def test_an_ordinary_duplicate_role_is_still_reported(self):
        self.add_role("ENTITY_CATALOGUE", 1)
        self.add_role("ENTITY_CATALOGUE", 2)

        self.assertEqual(
            [r["canonical_resource_role"] for r in self.fx.rows(self.query)],
            ["ENTITY_CATALOGUE"])

    def test_a_retired_row_does_not_make_a_duplicate(self):
        self.add_role("TRUST_MAP", 2)
        self.fx.db.execute(
            "INSERT INTO data_product_orientation"
            " (product_id, resource_role, discovery_order, is_active)"
            " VALUES ('CALLCENTRE', 'TRUST_GATE', 3, 0)")

        self.assertEqual(self.fx.rows(self.query), [])


class SemanticStandInsMatchShippedDdl(unittest.TestCase):
    """The fixture's stand-in tables must name columns the shipped DDL still has.

    VAL-14 resolves an area against the Semantic catalogue, so these tests are only
    meaningful while the columns they join on exist. A rename in the Semantic module
    would otherwise leave the checks passing against a schema the product does not have.
    """

    REQUIRED = {
        "01-catalog-tables.sql.j2": ("entity_metadata", ("module_name", "entity_name")),
        "02-discovery-tables.sql.j2": ("data_product_map", ("module_name", "is_active")),
        "09-orientation-manifest.sql.j2": ("data_product_orientation",
                                           ("product_id", "resource_role", "is_active")),
    }

    def test_every_stand_in_column_exists_in_the_shipped_template(self):
        for template, (table, columns) in self.REQUIRED.items():
            text = (SEMANTIC / template).read_text(encoding="utf-8")
            with self.subTest(table=table):
                self.assertIn(
                    table, text,
                    "%s no longer declares %s: the VAL-14 tests join to a stand-in for "
                    "a relation that has moved or been renamed" % (template, table))
                for column in columns:
                    self.assertIn(
                        column, text,
                        "%s.%s is gone from %s; update the stand-in in td_sqlite and the "
                        "conformance query that joins on it"
                        % (table, column, template))


if __name__ == "__main__":
    unittest.main(verbosity=2)
