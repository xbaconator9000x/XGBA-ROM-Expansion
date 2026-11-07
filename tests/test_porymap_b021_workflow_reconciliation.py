"""Fail-closed tests for the B021 Porymap workflow provenance observation."""

import copy
import json
import unittest

from tools.porymap_b021_workflow_reconciliation import (
    EVIDENCE_PATH,
    load_reference,
    validate_reconciliation,
)


class PorymapB021WorkflowReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        cls.reference = load_reference()

    def test_exact_source_and_run_evidence_stays_non_approving(self):
        self.assertEqual(validate_reconciliation(self.evidence, self.reference), [])
        self.assertEqual(self.evidence["blocker_deltas"][0]["blocker_id"], "B021")
        self.assertEqual(self.evidence["blocker_deltas"][0]["after"], "BLOCKED")
        self.assertEqual(self.evidence["blocker_deltas"][0]["resolved"], False)
        self.assertEqual(self.evidence["blocker_deltas"][1]["blocker_id"], "B020")
        self.assertEqual(self.evidence["blocker_deltas"][1]["after"], "BLOCKED")
        self.assertEqual(self.evidence["phase1"]["gate"], "FAIL_INCOMPLETE")
        self.assertEqual(self.evidence["phase1"]["approved_dispositions"], 0)

    def test_duplicate_or_missing_blocker_delta_is_rejected(self):
        altered = copy.deepcopy(self.evidence)
        altered["blocker_deltas"].pop()
        self.assertTrue(validate_reconciliation(altered, self.reference))

        altered = copy.deepcopy(self.evidence)
        altered["blocker_deltas"].append(copy.deepcopy(altered["blocker_deltas"][0]))
        self.assertTrue(validate_reconciliation(altered, self.reference))

    def test_invented_run_or_workflow_id_is_rejected(self):
        for field, value in (("run_id", 999), ("attempt", 2)):
            altered = copy.deepcopy(self.evidence)
            altered["workflow_observation"]["required_runs"][0][field] = value
            with self.subTest(field=field):
                self.assertTrue(validate_reconciliation(altered, self.reference))

        altered = copy.deepcopy(self.evidence)
        altered["workflow_observation"]["workflow_id"] = 123
        self.assertTrue(validate_reconciliation(altered, self.reference))

    def test_wrong_event_head_or_fabricated_base_is_rejected(self):
        mutations = (
            lambda value: value["workflow_observation"]["required_runs"][0].update(
                event="pull_request"
            ),
            lambda value: value["workflow_observation"]["required_runs"][0].update(
                head_sha="0" * 40
            ),
            lambda value: value["workflow_observation"]["required_runs"][1].update(
                base_provenance="current_pr_metadata_substituted"
            ),
            lambda value: value["live_pr_observations"]["pr14"].update(
                base_sha="dddd2fd27371eb8f45b36c0403ba8ed38f5b732a"
            ),
        )
        for mutate in mutations:
            altered = copy.deepcopy(self.evidence)
            mutate(altered)
            with self.subTest(mutation=mutate):
                self.assertTrue(validate_reconciliation(altered, self.reference))

    def test_missing_event_or_zero_job_authorization_gate_is_rejected(self):
        altered = copy.deepcopy(self.evidence)
        altered["workflow_observation"]["required_runs"].pop()
        self.assertTrue(validate_reconciliation(altered, self.reference))

        altered = copy.deepcopy(self.evidence)
        run = altered["workflow_observation"]["required_runs"][1]
        run["conclusion"] = "action_required"
        run["job_count"] = 0
        run["job_id"] = None
        run["job_conclusion"] = None
        self.assertTrue(validate_reconciliation(altered, self.reference))

    def test_incomplete_job_steps_are_rejected(self):
        altered = copy.deepcopy(self.evidence)
        run = altered["workflow_observation"]["required_runs"][0]
        run["successful_step_count"] = 9
        run["critical_steps"].pop()
        self.assertTrue(validate_reconciliation(altered, self.reference))

    def test_source_blob_dossier_and_license_mutations_are_rejected(self):
        for field, value in (
            ("git_blob_sha1", "0" * 40),
            ("source_sha256", "0" * 64),
            ("dossier_sha256", "0" * 64),
        ):
            altered = copy.deepcopy(self.evidence)
            altered["source_files"][0][field] = value
            with self.subTest(field=field):
                self.assertTrue(validate_reconciliation(altered, self.reference))

        altered = copy.deepcopy(self.evidence)
        altered["source_trace"]["licensing"]["distribution_clearance"] = "CLEARED"
        self.assertTrue(validate_reconciliation(altered, self.reference))

    def test_blocker_or_source_review_cannot_be_promoted(self):
        mutations = (
            lambda value: value["blocker_deltas"][0].update(
                after="RESOLVED", resolved=True
            ),
            lambda value: value["blocker_deltas"][1].update(after="RESOLVED"),
            lambda value: value["source_trace"]["caller_and_build_analysis"].update(
                whole_file_analysis="COMPLETE"
            ),
            lambda value: value["phase1"].update(
                gate="PASS", approved_dispositions=1
            ),
        )
        for mutate in mutations:
            altered = copy.deepcopy(self.evidence)
            mutate(altered)
            with self.subTest(mutation=mutate):
                self.assertTrue(validate_reconciliation(altered, self.reference))

    def test_evidence_archive_hash_and_source_set_are_pinned(self):
        altered = copy.deepcopy(self.evidence)
        altered["source_registry"]["queue_sha256"] = "0" * 64
        self.assertTrue(validate_reconciliation(altered, self.reference))

        altered = copy.deepcopy(self.evidence)
        altered["source_files"].pop()
        self.assertTrue(validate_reconciliation(altered, self.reference))


if __name__ == "__main__":
    unittest.main()
