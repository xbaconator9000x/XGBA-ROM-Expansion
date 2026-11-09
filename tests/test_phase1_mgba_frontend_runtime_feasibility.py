import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase1_mgba_frontend_runtime_feasibility",
    ROOT / "tools/phase1_mgba_frontend_runtime_feasibility.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class FrontendRuntimeFeasibilityTests(unittest.TestCase):
    def setUp(self):
        self.matrix = RUNNER.expected_matrix()

    def test_exact_matrix_is_non_approving(self):
        self.assertTrue(RUNNER.validate_matrix_payload(self.matrix))
        self.assertEqual(self.matrix["status"], "NEEDS_EVIDENCE")
        self.assertEqual(self.matrix["overall"], "FAIL_INCOMPLETE")
        committed = RUNNER.json.loads(
            (ROOT / RUNNER.MATRIX).read_text(encoding="utf-8")
        )
        self.assertTrue(RUNNER.validate_matrix_payload(committed))

    def test_source_rows_distinguish_new_review_from_reused_identity(self):
        reviewed = [
            row for row in self.matrix["source_records"]
            if row["review_scope"] == "reviewed_for_runtime_feasibility"
        ]
        reused = [
            row for row in self.matrix["source_records"]
            if row["review_scope"] == "reused_identity_only"
        ]
        self.assertEqual(len(reviewed), 6)
        self.assertEqual(len(reused), 4)
        self.assertEqual(len({row["path"] for row in self.matrix["source_records"]}), 10)

    def test_cannot_claim_frontend_runtime_or_log_delivery(self):
        for key in (
            "qt_frontend_executed",
            "sdl_frontend_executed",
            "actual_frontend_fault_injection",
            "frontend_save_failure_or_log_delivery_observed",
            "cold_process_sav_reopen_observed",
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.matrix)
                changed["execution_contract"][key] = True
                with self.assertRaises(ValueError):
                    RUNNER.validate_matrix_payload(changed)

    def test_cannot_claim_successful_qt_build_or_headless_save_run(self):
        changed = copy.deepcopy(self.matrix)
        changed["runtime_attempts"]["qt"]["build"] = "SUCCEEDED"
        with self.assertRaises(ValueError):
            RUNNER.validate_matrix_payload(changed)

        changed = copy.deepcopy(self.matrix)
        changed["runtime_attempts"]["sdl"]["build"] = "SUCCEEDED"
        with self.assertRaises(ValueError):
            RUNNER.validate_matrix_payload(changed)

        changed = copy.deepcopy(self.matrix)
        changed["runtime_attempts"]["headless"]["execution"] = "SAVE_LIFECYCLE_OBSERVED"
        with self.assertRaises(ValueError):
            RUNNER.validate_matrix_payload(changed)

    def test_cannot_promote_dirty_clear_or_teardown_to_persistence_ack(self):
        changed = copy.deepcopy(self.matrix)
        changed["execution_contract"][
            "dirty_to_clean_is_persistence_acknowledgment"
        ] = True
        with self.assertRaises(ValueError):
            RUNNER.validate_matrix_payload(changed)

        changed = copy.deepcopy(self.matrix)
        changed["source_observations"][2]["finding"] += (
            "; successful persistence is acknowledged"
        )
        with self.assertRaises(ValueError):
            RUNNER.validate_matrix_payload(changed)

    def test_cannot_claim_gameplay_flash_or_independent_approval(self):
        for key in (
            "stock_gameplay",
            "physical_flash",
            "independent_semantic_approval",
            "gate_or_approval_state_changed",
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.matrix)
                changed["execution_contract"][key] = True
                with self.assertRaises(ValueError):
                    RUNNER.validate_matrix_payload(changed)

    def test_wrong_pin_tree_or_dossier_hash_is_rejected(self):
        for location, key in (
            (("pinned_revision",), "bad"),
            (("pinned_tree",), "bad"),
            (("machine_dossier", "compressed_sha256"), "bad"),
        ):
            with self.subTest(location=location):
                changed = copy.deepcopy(self.matrix)
                target = changed
                for part in location[:-1]:
                    target = target[part]
                target[location[-1]] = key
                with self.assertRaises(ValueError):
                    RUNNER.validate_matrix_payload(changed)

    def test_source_hash_or_dossier_row_mismatch_is_rejected(self):
        for key in ("git_blob", "full_source_sha256",
                    "canonical_dossier_row_sha256"):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.matrix)
                changed["source_records"][0][key] = "0" * 64
                with self.assertRaises(ValueError):
                    RUNNER.validate_matrix_payload(changed)

    def test_cannot_remove_qt_filter_or_conditional_sink_limitation(self):
        changed = copy.deepcopy(self.matrix)
        changed["source_observations"][1]["finding"] = (
            "Qt always displays all save failure logs."
        )
        with self.assertRaises(ValueError):
            RUNNER.validate_matrix_payload(changed)

    def test_unresolved_runtime_evidence_cannot_be_removed(self):
        changed = copy.deepcopy(self.matrix)
        changed["unresolved"] = []
        with self.assertRaises(ValueError):
            RUNNER.validate_matrix_payload(changed)


if __name__ == "__main__":
    unittest.main()
