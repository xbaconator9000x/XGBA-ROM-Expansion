import copy
import json
import unittest
from pathlib import Path

from tools.phase1_mgba_headless_timeout_diagnostic import (
    MATRIX,
    expected_diagnostic,
    validate_payload,
)


ROOT = Path(__file__).resolve().parents[1]


class HeadlessTimeoutDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.payload = expected_diagnostic(ROOT)

    def test_committed_report_matches_exact_non_approving_contract(self):
        committed = json.loads((ROOT / MATRIX).read_text(encoding="utf-8"))
        self.assertTrue(validate_payload(committed, ROOT))
        self.assertEqual(committed["status"], "NEEDS_EVIDENCE")
        self.assertEqual(committed["overall"], "FAIL_INCOMPLETE")

    def test_signal_controls_are_labeled_synthetic_with_exact_results(self):
        term, interrupt = self.payload["bounded_signal_controls"]
        self.assertFalse(term["mGBA_process"])
        self.assertEqual(term["shell_exit_status"], 143)
        self.assertEqual(term["elapsed_seconds"], 0.40)
        self.assertEqual(term["stdout_lines"], ["CONTROL_STARTED"])
        self.assertEqual(interrupt["shell_exit_status"], 0)
        self.assertEqual(
            interrupt["stdout_lines"],
            ["CONTROL_STARTED", "SIGINT_HANDLER_RAN"],
        )

    def test_prior_actual_attempt_does_not_invent_exit_or_runtime(self):
        attempt = self.payload["prior_actual_headless_attempt"]
        self.assertIsNone(attempt["exact_exit_status"])
        self.assertIsNone(attempt["exact_runtime_seconds"])
        self.assertFalse(attempt["stdout_or_stderr_artifact_retained"])
        changed = copy.deepcopy(self.payload)
        changed["prior_actual_headless_attempt"]["exact_exit_status"] = 143
        with self.assertRaises(ValueError):
            validate_payload(changed, ROOT)

    def test_timeout_handler_cannot_be_mislabeled_sigterm(self):
        changed = copy.deepcopy(self.payload)
        changed["headless_source_diagnosis"]["signal_handler"] = "SIGINT and SIGTERM"
        with self.assertRaises(ValueError):
            validate_payload(changed, ROOT)

    def test_cannot_invent_headless_save_or_cold_reopen(self):
        for key in (
            "headless_save_lifecycle_observed",
            "cold_process_sav_reopen_observed",
            "frontend_native_execution_observed",
            "actual_mgba_frontend_fault_injection",
            "logger_delivery_observed",
            "missing_logger_control_repeated",
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.payload)
                changed["execution_contract"][key] = True
                with self.assertRaises(ValueError):
                    validate_payload(changed, ROOT)

    def test_cannot_claim_dirty_clear_or_teardown_is_durable(self):
        changed = copy.deepcopy(self.payload)
        changed["execution_contract"][
            "dirty_to_clean_is_persistence_acknowledgment"
        ] = True
        with self.assertRaises(ValueError):
            validate_payload(changed, ROOT)

    def test_cannot_claim_gameplay_flash_approval_or_gate_change(self):
        for key in (
            "durable_persistence_or_power_loss_evidence",
            "stock_gameplay",
            "physical_flash",
            "independent_semantic_approval",
            "gate_or_approval_state_changed",
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.payload)
                changed["execution_contract"][key] = True
                with self.assertRaises(ValueError):
                    validate_payload(changed, ROOT)

    def test_stale_source_or_dossier_identity_is_rejected(self):
        for section, key in (
            ("source_records", "git_blob"),
            ("source_records", "full_source_sha256"),
            ("source_records", "canonical_dossier_row_sha256"),
        ):
            changed = copy.deepcopy(self.payload)
            changed[section][0][key] = "0" * 64
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_payload(changed, ROOT)
        changed = copy.deepcopy(self.payload)
        changed["machine_dossier"]["compressed_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_payload(changed, ROOT)

    def test_cancelled_package_install_is_not_a_qt_build_failure(self):
        changed = copy.deepcopy(self.payload)
        changed["qt_build_diagnosis"]["latest_push_workflow"]["conclusion"] = "failure"
        with self.assertRaises(ValueError):
            validate_payload(changed, ROOT)


if __name__ == "__main__":
    unittest.main()
