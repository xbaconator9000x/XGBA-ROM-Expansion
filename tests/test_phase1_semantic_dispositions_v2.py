import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts_v4_adapter as adapter
import phase1_semantic_dispositions_v2 as v2


def fixture_receipt(key):
    return {
        "schema": adapter.RECEIPT_SCHEMA,
        "source": {"repository": key[0], "path": key[1]},
    }


def fixture_validated_result(key):
    return {
        "source": f"{key[0]}:{key[1]}",
        "status": "COPILOT_RECEIPT_VALIDATED",
        "pr_jobs": 41,
        "push_jobs": 1,
    }


def fixture_blocked_result(key, blocker):
    return {
        "source": f"{key[0]}:{key[1]}",
        "status": "BLOCKED",
        "blocker": blocker,
    }


def fixture_legacy_gate():
    return {
        "decision": "FAIL_INCOMPLETE",
        "verified_source_manifest_entries": v2.INVENTORY_SIZE,
        "machine_generated_dossiers": v2.INVENTORY_SIZE,
        "p0_review_candidates": v2.LEGACY_P0_CANDIDATES,
        "approved_semantic_dispositions": v2.LEGACY_APPROVALS,
    }


class SemanticDispositionV2Tests(unittest.TestCase):
    def setUp(self):
        self.keys = sorted(adapter.EXPECTED_RECEIPTS)
        self.receipts = [fixture_receipt(key) for key in self.keys]

    def build_report(self, results):
        # These fixtures test report projection only; live CLI always calls the pinned adapter.
        with patch.object(adapter, "validate_receipt_inventory"):
            return v2.build_report(self.receipts, results, fixture_legacy_gate())

    def test_synthetic_fixture_does_not_pass_without_live_adapter_validation(self):
        status, _ = v2._classify_result({"status": "BLOCKED", "blocker": "GitHub API unavailable"})
        self.assertEqual(status, v2.BLOCKED)

    def test_validated_adapter_result_projects_to_separate_v2_counter(self):
        results = [
            fixture_validated_result(self.keys[0]),
            fixture_blocked_result(self.keys[1], "GitHub API unavailable"),
            fixture_blocked_result(self.keys[2], "GitHub API unavailable"),
        ]
        report = self.build_report(results)
        self.assertEqual(report["v2_qualified_semantic_review_count"], 1)
        self.assertEqual(report["legacy_external_independent_approved"], 0)
        self.assertEqual(report["legacy_p0_external_independent_approved"], 0)
        self.assertEqual(report["legacy_p0_review_candidates"], 338)
        self.assertEqual(report["v2_completion_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(report["policy_status"], "PROPOSAL_NOT_ACTIVATED")
        self.assertEqual(report["dispositions"][0]["disposition"], v2.PASSED)

    def test_validated_status_requires_positive_pr_and_push_job_counts(self):
        status, reason = v2._classify_result(
            {"status": "COPILOT_RECEIPT_VALIDATED", "pr_jobs": 41}
        )
        self.assertEqual(status, v2.BLOCKED)
        self.assertIn("job counts", reason)

    def test_partial_review_is_needs_review_and_never_counted(self):
        status, reason = v2._classify_result(
            {"status": "BLOCKED", "blocker": "Receipt has no semantic approval decision"}
        )
        self.assertEqual(status, v2.NEEDS_REVIEW)
        self.assertIn("semantic approval decision", reason)

    def test_unresolved_objection_is_needs_review_and_never_counted(self):
        status, reason = v2._classify_result({
            "status": "BLOCKED",
            "blocker": "Unresolved substantive objection",
        })
        self.assertEqual(status, v2.NEEDS_REVIEW)
        self.assertIn("objection", reason)

    def test_missing_dependency_license_or_whole_file_evidence_is_needs_review(self):
        for blocker in (
            "Dependency closure is incomplete",
            "Licensing is unresolved or lacks rationale",
            "Whole-file line coverage has gaps or invalid ranges",
        ):
            with self.subTest(blocker=blocker):
                status, _ = v2._classify_result({"status": "BLOCKED", "blocker": blocker})
                self.assertEqual(status, v2.NEEDS_REVIEW)

    def test_unverified_compiled_claim_is_needs_review(self):
        status, reason = v2._classify_result({
            "status": "BLOCKED",
            "blocker": "Non-source VERIFIED artifacts require independent byte verification: compiled_native",
        })
        self.assertEqual(status, v2.NEEDS_REVIEW)
        self.assertIn("independent byte verification", reason)

    def test_invalid_evidence_status_is_needs_review(self):
        status, _ = v2._classify_result({
            "status": "BLOCKED",
            "blocker": "Evidence distinction has an unsupported status: compiled_native",
        })
        self.assertEqual(status, v2.NEEDS_REVIEW)

    def test_owner_self_review_or_spoofed_attestation_never_projects_to_pass(self):
        for blocker in (
            "Reviewer authored the source dossier",
            "Authenticated Copilot identity is missing",
            "Quoted attestation marker",
        ):
            with self.subTest(blocker=blocker):
                status, _ = v2._classify_result(
                    {"status": "BLOCKED", "blocker": blocker}
                )
                self.assertEqual(status, v2.BLOCKED)

    def test_duplicate_or_unknown_adapter_result_blocks_every_count(self):
        label = f"{self.keys[0][0]}:{self.keys[0][1]}"
        result = {"source": label, "status": "COPILOT_RECEIPT_VALIDATED"}
        report = self.build_report([result, result])
        self.assertEqual(report["v2_qualified_semantic_review_count"], 0)
        self.assertTrue(all(item["disposition"] == v2.BLOCKED for item in report["dispositions"]))

        report = self.build_report([{
            "source": "other/repo:stale.c",
            "status": "COPILOT_RECEIPT_VALIDATED",
        }])
        self.assertEqual(report["v2_qualified_semantic_review_count"], 0)
        self.assertTrue(all(item["disposition"] == v2.BLOCKED for item in report["dispositions"]))

    def test_missing_adapter_result_is_blocked_not_approved(self):
        report = self.build_report([])
        self.assertEqual(report["v2_qualified_semantic_review_count"], 0)
        self.assertTrue(all(item["disposition"] == v2.BLOCKED for item in report["dispositions"]))

    def test_changed_historical_gate_baseline_fails_closed(self):
        gate = fixture_legacy_gate()
        gate["approved_semantic_dispositions"] = 1
        with self.assertRaisesRegex(ValueError, "Historical legacy gate counts changed"):
            v2._validate_legacy_gate(gate)

    def test_nonvalidated_unknown_status_cannot_be_promoted(self):
        status, _ = v2._classify_result({"status": "APPROVED", "blocker": "arbitrary"})
        self.assertEqual(status, v2.BLOCKED)


if __name__ == "__main__":
    unittest.main()
