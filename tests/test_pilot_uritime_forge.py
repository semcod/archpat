"""Integration tests for ARP-001..ARP-003 and the Section 12 uritime/URT/Forge/Polycell vertical pilot."""

from __future__ import annotations

import unittest

from archpat.pilot_uritime_forge import EcosystemRoots, run_vertical_pilot, verify_contract_corpus


class TestPilotUritimeForge(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.roots = EcosystemRoots()
        missing = cls.roots.missing_paths()
        if missing:
            raise unittest.SkipTest(f"Local PC ecosystem checkouts not present: {missing}")

    def test_contract_corpus_positive_and_negative(self) -> None:
        corpus = verify_contract_corpus(self.roots)
        self.assertTrue(corpus["all_passed"], f"Failed corpus checks: {corpus['checks']}")
        self.assertEqual(corpus["evidence_level"], "contract_verified")
        self.assertGreaterEqual(corpus["total"], 12)
        names = {c["name"]: c for c in corpus["checks"]}
        self.assertTrue(names["nl_uri_schema_matches_forge_copy"]["passed"])
        self.assertTrue(names["urievents_command_unpinned_input"]["passed"])
        self.assertTrue(names["autodo_reject_http_url"]["passed"])
        self.assertTrue(names["urt_missing_timezone_rejected"]["passed"])
        self.assertTrue(names["polycell_invalid_urn_rejected"]["passed"])
        self.assertTrue(names["polycell_backlog_reconciliation_examples"]["passed"])

    def test_vertical_pilot_all_five_story_acceptance_criteria_and_forge(self) -> None:
        result = run_vertical_pilot(self.roots)
        self.assertEqual(result["story_id"], "exercise-feedback")
        self.assertFalse(result["archpat_proposal"]["execution_ready"])
        self.assertTrue(result["all_acceptance_passed"], f"Acceptance failures: {result['acceptance']}")
        self.assertEqual(result["evidence_level"], "integration_verified")

        # 1 command + 1 query + ownership + pure replay
        self.assertEqual(result["command_binding"]["process_uri"], "urn:poa:exercise.review#v1")
        self.assertEqual(result["command_binding"]["accepted_version"], 1)
        self.assertGreaterEqual(result["command_binding"]["exported_urt_records"], 2)
        self.assertEqual(
            result["query_binding"]["events_before_query"],
            result["query_binding"]["events_after_query"],
        )
        self.assertTrue(result["query_binding"]["replay_matches_live"])

        # Real Forge qualification point
        forge = result["forge_qualification"]
        self.assertEqual(forge["checks_status"], "PASS")
        self.assertTrue(forge["fresh_publish_precondition"]["publishable"])
        self.assertFalse(forge["stale_publish_precondition"]["publishable"])
        self.assertIn("base_snapshot_changed", forge["stale_publish_precondition"]["reasons"])


if __name__ == "__main__":
    unittest.main()
