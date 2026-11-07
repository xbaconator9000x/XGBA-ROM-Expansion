"""Fail-closed tests for the pinned mGBA observer receipt eligibility report."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/phase1_mgba_observer_receipt_eligibility.py"
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_observer_receipt_eligibility", TOOL
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

MANIFEST = json.loads((ROOT / runner.MANIFEST).read_text(encoding="utf-8"))
CROSS = json.loads((ROOT / runner.CROSS_MATRIX).read_text(encoding="utf-8"))
PLATFORM = json.loads((ROOT / runner.PLATFORM_MATRIX).read_text(encoding="utf-8"))
HANDOFF = json.loads((ROOT / runner.HANDOFF_MATRIX).read_text(encoding="utf-8"))
HEAD = "a" * 40


def complete_ci_evidence(head=HEAD):
    return {
        event: {
            "event": event,
            "head_sha": head,
            "branch": runner.BRANCH,
            "workflow_id": runner.WORKFLOW_ID,
            "conclusion": "success",
            "run_id": 1001 if event == "pull_request" else 1002,
        }
        for event in ("pull_request", "push")
    }


def build(evidence=None, head=HEAD):
    return runner.build_report(
        MANIFEST, CROSS, PLATFORM, HANDOFF, head, evidence
    )


class TestObserverReceiptEligibility(unittest.TestCase):
    def assert_rejected_report(self, mutate, evidence=None):
        report = build(evidence)
        mutate(report)
        with self.assertRaises(ValueError):
            runner.validate_report(
                report, MANIFEST, CROSS, PLATFORM, HANDOFF, HEAD, evidence
            )

    def test_canonical_manifest(self):
        self.assertTrue(runner.validate_manifest(copy.deepcopy(MANIFEST)))

    def test_source_rows_are_distinct_and_not_registered_as_approvals(self):
        report = build()
        self.assertEqual(len(report["source_records"]), 16)
        self.assertEqual(len({
            record["path"] for record in report["source_records"]
        }), 16)
        self.assertTrue(all(
            record["source_review_status"] == runner.RECEIPT_STATUS
            and not record["independent_approval"]
            and not record["receipt_eligible"]
            for record in report["source_records"]
        ))
        self.assertEqual(report["eligibility"]["status"], "FAIL_INCOMPLETE")
        self.assertEqual(report["eligibility"]["independent_approvals_claimed"], 0)

    def test_missing_exact_head_ci_events_block_eligibility(self):
        report = build()
        self.assertEqual(
            report["ci_evidence"]["blockers"],
            ["missing_exact_head_pull_request_run", "missing_exact_head_push_run"],
        )
        self.assertTrue(all(
            "missing_exact_head_pull_request_run" in record["eligibility_blockers"]
            and "missing_exact_head_push_run" in record["eligibility_blockers"]
            for record in report["source_records"]
        ))

    def test_valid_pr_and_push_runs_do_not_create_independent_approval(self):
        evidence = complete_ci_evidence()
        report = build(evidence)
        self.assertTrue(report["ci_evidence"]["descriptor_consistent_with_contract"])
        self.assertEqual(report["eligibility"]["eligible_records"], 0)
        self.assertEqual(report["eligibility"]["status"], "FAIL_INCOMPLETE")
        self.assertFalse(report["evidence_limits"]["github_api_evidence_source_authenticated"])
        self.assertTrue(all(
            "independent_per_file_attribution_missing" in record["eligibility_blockers"]
            for record in report["source_records"]
        ))

    def test_stale_pr_run_rejected(self):
        evidence = complete_ci_evidence()
        evidence["pull_request"]["head_sha"] = "b" * 40
        report = build(evidence)
        self.assertIn("stale_or_wrong_head_pull_request_run",
                      report["ci_evidence"]["blockers"])

    def test_wrong_event_rejected(self):
        evidence = complete_ci_evidence()
        evidence["push"]["event"] = "workflow_dispatch"
        report = build(evidence)
        self.assertIn("wrong_event_for_push_run", report["ci_evidence"]["blockers"])

    def test_unsuccessful_or_wrong_workflow_runs_rejected(self):
        evidence = complete_ci_evidence()
        evidence["push"]["conclusion"] = "action_required"
        evidence["pull_request"]["workflow_id"] += 1
        report = build(evidence)
        self.assertIn("unsuccessful_push_run", report["ci_evidence"]["blockers"])
        self.assertIn("wrong_workflow_for_pull_request_run",
                      report["ci_evidence"]["blockers"])

    def test_duplicate_run_id_rejected(self):
        evidence = complete_ci_evidence()
        evidence["push"]["run_id"] = evidence["pull_request"]["run_id"]
        report = build(evidence)
        self.assertIn("pr_and_push_must_be_distinct_runs",
                      report["ci_evidence"]["blockers"])

    def test_unrecognized_ci_claim_fields_rejected(self):
        evidence = complete_ci_evidence()
        evidence["push"]["approved_by"] = "external reviewer"
        with self.assertRaises(ValueError):
            build(evidence)

    def test_frontend_log_paths_remain_unobserved(self):
        report = build()
        self.assertEqual(
            {path["id"] for path in report["unresolved_frontend_observers"]},
            {"qt", "sdl", "libretro", "python", "headless"},
        )
        self.assertTrue(all(
            path["status"] == "NEEDS_EVIDENCE"
            for path in report["unresolved_frontend_observers"]
        ))

    def test_platform_runtime_paths_remain_unobserved(self):
        report = build()
        self.assertEqual(len(report["unresolved_platform_observers"]), 8)
        self.assertTrue(all(
            path["status"] == "NEEDS_EVIDENCE"
            and path["execution"] == "pinned_source_only_no_platform_runtime"
            for path in report["unresolved_platform_observers"]
        ))

    def test_host_logger_and_dirty_callback_are_not_persistence_or_frontend_evidence(self):
        report = build()
        self.assertEqual(
            report["evidence_limits"]["native_class"],
            "compiled_linux_host_source_extraction",
        )
        self.assertFalse(report["evidence_limits"]["native_frontend_delivery_observed"])
        self.assertFalse(
            report["evidence_limits"]["dirty_to_clean_is_persistence_acknowledgment"]
        )
        self.assertFalse(report["evidence_limits"]["physical_flash_or_power_loss_evidence"])

    def test_mismatched_hash_and_duplicate_source_identity_rejected(self):
        mutated = copy.deepcopy(CROSS)
        mutated["reviewed_new_files"][0]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            runner.build_report(MANIFEST, mutated, PLATFORM, HANDOFF, HEAD)
        mutated = copy.deepcopy(CROSS)
        mutated["reviewed_new_files"][1]["path"] = mutated["reviewed_new_files"][0]["path"]
        with self.assertRaises(ValueError):
            runner.build_report(MANIFEST, mutated, PLATFORM, HANDOFF, HEAD)

    def test_false_approved_or_external_human_claim_rejected(self):
        self.assert_rejected_report(
            lambda report: report["source_records"][0].update(
                source_review_status="APPROVED"
            )
        )
        self.assert_rejected_report(
            lambda report: report["source_records"][0]["reviewer_attribution"].update(
                reviewer="independent human", independent=True
            )
        )

    def test_false_frontend_and_durability_claims_rejected(self):
        self.assert_rejected_report(
            lambda report: report["evidence_limits"].update(
                native_frontend_delivery_observed=True
            )
        )
        self.assert_rejected_report(
            lambda report: report["evidence_limits"].update(
                dirty_to_clean_is_persistence_acknowledgment=True
            )
        )
        self.assert_rejected_report(
            lambda report: report["evidence_limits"].update(
                physical_flash_or_power_loss_evidence=True
            )
        )
        self.assert_rejected_report(
            lambda report: report["evidence_limits"].update(
                native_class="native_frontend_execution"
            )
        )

    def test_stale_pin_or_manifest_rejected(self):
        mutated = copy.deepcopy(HANDOFF)
        mutated["pinned_revision"] = "0" * 40
        with self.assertRaises(ValueError):
            runner.build_report(MANIFEST, CROSS, PLATFORM, mutated, HEAD)
        mutated_manifest = copy.deepcopy(MANIFEST)
        mutated_manifest["ci_contract"]["required_events"] = ["pull_request"]
        with self.assertRaises(ValueError):
            runner.validate_manifest(mutated_manifest)

    def test_stale_dossier_and_row_hashes_rejected(self):
        mutated = copy.deepcopy(CROSS)
        mutated["machine_dossier"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            runner.build_report(MANIFEST, mutated, PLATFORM, HANDOFF, HEAD)
        mutated = copy.deepcopy(CROSS)
        mutated["reviewed_new_files"][0]["dossier_row_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            runner.build_report(MANIFEST, mutated, PLATFORM, HANDOFF, HEAD)

    def test_invalid_exact_head_rejected(self):
        with self.assertRaises(ValueError):
            build(head="not-a-commit")


if __name__ == "__main__":
    unittest.main()
