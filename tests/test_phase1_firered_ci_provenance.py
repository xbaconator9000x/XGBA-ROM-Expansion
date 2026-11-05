#!/usr/bin/env python3
"""Fail-closed checks for exact-head GitHub Actions and save evidence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from phase1_firered_ci_provenance import (
    EXPECTED_BASE_REF,
    build_run_provenance,
    validate_game_save_evidence,
    validate_required_pr_run,
)

HEAD = "a" * 40
BASE = "b" * 40
MERGE = "c" * 40
REPO = "xbaconator9000x/XGBA-ROM-Expansion"


def pr_context(head=HEAD, base=BASE, base_ref=EXPECTED_BASE_REF):
    return {
        "pull_request": {
            "head": {"sha": head, "ref": "phase1/firered-game-controller-save-observation-20261028",
                     "repo": {"full_name": REPO}},
            "base": {"sha": base, "ref": base_ref},
        }
    }


def environment(sha=MERGE):
    return {
        "GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_REPOSITORY": REPO, "GITHUB_WORKFLOW": "Phase 1 save test",
        "GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/test.yml@refs/pull/28/merge",
        "GITHUB_SHA": sha,
    }


def pr_record(head=HEAD, base_ref=EXPECTED_BASE_REF, conclusion="success"):
    return {
        "event_name": "pull_request", "repository": REPO,
        "head_sha": head, "checked_out_sha": head,
        "base_ref": base_ref, "base_sha": BASE, "current_base_sha": BASE,
        "base_fresh": True, "base_is_ancestor": True,
        "run_id": 1234, "run_attempt": 1,
        "run_url": "https://github.com/" + REPO + "/actions/runs/1234",
        "job_conclusion": conclusion,
    }


def valid_game_save():
    return {
        "case": "pallet_save_dense_confirm",
        "source_fixture": "synthetic_pallet_valid",
        "input_save_origin": "synthetic_fixture",
        "output_save_origin": "game_generated",
        "game_initiated_save_verified": True,
        "physical_save_changed": True,
        "native": {
            "start_menu_save_hits": 1, "save_dialog_do_save_hits": 1,
            "try_saving_data_entry_hits": 1, "try_saving_data_return_hits": 1,
            "first_try_saving_data_return_value": 1,
            "program_flash_sector_and_verify_entry_hits": 14,
            "program_flash_sector_and_verify_return_hits": 14,
            "host_flash_writes": 0, "flash_changed_bytes": 100,
            "flash_program_trace": [{"sector": n} for n in range(14, 28)],
        },
    }


class ExactHeadProvenanceTests(unittest.TestCase):
    def test_exact_fresh_pr_head_is_recorded(self):
        result = build_run_provenance(
            "pull_request", pr_context(), environment(),
            HEAD, current_base_sha=BASE, base_is_ancestor=True,
        )
        self.assertEqual(result["head_sha"], HEAD)
        self.assertEqual(result["base_sha"], BASE)
        self.assertTrue(result["base_fresh"])
        self.assertEqual(result["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertFalse(result["independent_approval"])

    def test_wrong_checked_out_head_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact pull request head"):
            build_run_provenance(
                "pull_request", pr_context(), environment(),
                "d" * 40, current_base_sha=BASE, base_is_ancestor=True,
            )

    def test_wrong_pull_request_head_rejected_by_exact_run_audit(self):
        with self.assertRaisesRegex(AssertionError, "No successful exact-head"):
            validate_required_pr_run([pr_record(head="d" * 40)], HEAD)

    def test_missing_pr_run_rejected(self):
        with self.assertRaisesRegex(AssertionError, "No successful exact-head"):
            validate_required_pr_run([], HEAD)

    def test_stale_base_sha_rejected(self):
        with self.assertRaisesRegex(ValueError, "base SHA is stale"):
            build_run_provenance(
                "pull_request", pr_context(), environment(),
                HEAD, current_base_sha="e" * 40, base_is_ancestor=True,
            )

    def test_base_not_ancestor_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not contain"):
            build_run_provenance(
                "pull_request", pr_context(), environment(),
                HEAD, current_base_sha=BASE, base_is_ancestor=False,
            )

    def test_unexpected_base_branch_rejected(self):
        with self.assertRaisesRegex(ValueError, "unexpected or stale"):
            build_run_provenance(
                "pull_request", pr_context(base_ref="main"), environment(),
                HEAD, current_base_sha=BASE, base_is_ancestor=True,
            )

    def test_pr_run_audit_requires_success_and_expected_base(self):
        with self.assertRaises(AssertionError):
            validate_required_pr_run([pr_record(conclusion="failure")], HEAD)
        with self.assertRaises(AssertionError):
            validate_required_pr_run([pr_record(base_ref="main")], HEAD)
        self.assertEqual(validate_required_pr_run([pr_record()], HEAD), pr_record())

    def test_synthetic_fixture_only_cannot_be_labeled_game_generated(self):
        evidence = valid_game_save()
        evidence["output_save_origin"] = "synthetic_fixture"
        evidence["native"] = {}
        with self.assertRaisesRegex(AssertionError, "mislabeled"):
            validate_game_save_evidence(evidence)

    def test_synthetic_fixture_output_cannot_be_called_game_generated_without_trace(self):
        evidence = valid_game_save()
        evidence["game_initiated_save_verified"] = False
        with self.assertRaisesRegex(AssertionError, "mislabeled"):
            validate_game_save_evidence(evidence)

    def test_synthetic_fixture_without_compiled_game_save_cannot_claim_game_save(self):
        evidence = valid_game_save()
        evidence["native"]["try_saving_data_entry_hits"] = 0
        with self.assertRaisesRegex(AssertionError, "lacks compiled"):
            validate_game_save_evidence(evidence)

    def test_genuine_controller_save_distinguishes_input_and_output_origin(self):
        self.assertTrue(validate_game_save_evidence(valid_game_save()))
        evidence = valid_game_save()
        evidence["game_initiated_save_verified"] = False
        evidence["output_save_origin"] = "unclassified"
        self.assertFalse(validate_game_save_evidence(evidence))


if __name__ == "__main__":
    unittest.main()
