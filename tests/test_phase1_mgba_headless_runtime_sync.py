import copy
import json
import unittest
from pathlib import Path

from tools.phase1_mgba_headless_runtime_sync import (
    MATRIX,
    expected_matrix,
    validate_matrix,
)


ROOT = Path(__file__).resolve().parents[1]


class HeadlessRuntimeSyncTests(unittest.TestCase):
    def setUp(self):
        self.matrix = expected_matrix()

    def test_committed_report_is_fail_closed(self):
        committed = json.loads((ROOT / MATRIX).read_text(encoding="utf-8"))
        self.assertTrue(validate_matrix(committed))
        self.assertEqual(committed["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(committed["status"], "NEEDS_EVIDENCE")

    def test_source_rows_bind_original_identity_and_review_scope(self):
        paths = {row["path"] for row in self.matrix["source_records"]}
        self.assertEqual(len(paths), 13)
        new_paths = {
            row["path"] for row in self.matrix["source_records"]
            if row["review_scope"] == "bounded_new_runtime_path_review"
        }
        self.assertEqual(new_paths, {
            "src/core/scripting.c",
            "src/script/context.c",
            "src/script/engines/lua.c",
            "src/gba/memory.c",
            "src/util/vfs.c",
            "src/util/vfs/vfs-fd.c",
        })

    def test_cannot_invent_gui_frontend_or_physical_persistence(self):
        for section, key in (
            ("local_execution", "native_frontend_ui_observed"),
            ("local_execution", "full_gui_frontend_observed"),
            ("local_execution", "durable_persistence_or_power_loss_observed"),
            ("local_execution", "physical_flash_observed"),
            ("local_execution", "stock_gameplay_observed"),
            ("local_execution", "independent_semantic_approval"),
            ("local_execution", "gate_or_approval_state_changed"),
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.matrix)
                changed[section][key] = True
                with self.assertRaises(ValueError):
                    validate_matrix(changed)

    def test_post_open_fstat_failure_contract_is_distinct_and_non_approving(self):
        case = self.matrix["fstat_failure_contract"]
        self.assertIn("VFileFromFD -> fstat", case["pinned_call_path"])
        self.assertEqual(case["expected_fstat_marker"],
                             "operation=fstat injected=1 result=-1 errno=EIO")
        self.assertEqual(case["expected_close_marker"],
                             "operation=close injected=0 result=0 errno=none")
        self.assertEqual(case["expected_script_observation"], "loadSaveFile=false")
        self.assertFalse(case["persistence_claim"])
        self.assertEqual(case["status"], "REQUIRED_IN_EXISTING_CI")

        for key, value in (
                ("expected_fstat_marker", "operation=open injected=1 result=-1"),
                ("expected_close_marker", "operation=close injected=0 result=-1"),
                ("expected_script_observation", "loadSaveFile=true"),
                ("persistence_claim", True),
                ("status", "PASSED"),
        ):
                changed = copy.deepcopy(self.matrix)
                changed["fstat_failure_contract"][key] = value
                with self.assertRaises(ValueError):
                    validate_matrix(changed)

    def test_cannot_claim_sync_failure_propagates_as_process_error(self):
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["injected_sync_failure"]["process_exit_status"] = 1
        with self.assertRaises(ValueError):
            validate_matrix(changed)
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["injected_sync_failure"]["error_propagated_to_process_status"] = True
        with self.assertRaises(ValueError):
            validate_matrix(changed)

    def test_teardown_ms_sync_failure_has_no_mgba_error_channel(self):
        teardown = self.matrix["local_execution"]["teardown_sync_failure"]
        self.assertEqual(teardown["teardown_ms_sync"], "returned -1 with errno EIO")
        self.assertFalse(teardown["unmap_ms_sync_return_observed_by_mGBA"])
        self.assertIsNone(teardown["mGBA_log_for_teardown_error"])
        for key, value in (
            ("teardown_ms_sync", "returned success"),
            ("unmap_ms_sync_return_observed_by_mGBA", True),
            ("mGBA_log_for_teardown_error", "Savedata failed to sync!"),
            ("process_exit_status", 1),
        ):
            changed = copy.deepcopy(self.matrix)
            changed["local_execution"]["teardown_sync_failure"][key] = value
            with self.assertRaises(ValueError):
                validate_matrix(changed)

    def test_teardown_failure_reopen_is_not_a_persistence_receipt(self):
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["cold_process_reopen_after_teardown_failure"][
            "same_os_page_cache_durability_claim"
        ] = True
        with self.assertRaises(ValueError):
            validate_matrix(changed)
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["cold_process_reopen_after_teardown_failure"][
            "script_read_sram_byte"
        ] = "0x43"
        with self.assertRaises(ValueError):
            validate_matrix(changed)

    def test_failed_save_reopen_contract_is_caller_observed_and_non_approving(self):
        case = self.matrix["reopen_failure_contract"]
        self.assertEqual(case["expected_api_result"], False)
        self.assertEqual(case["expected_script_observation"], "loadSaveFile=false")
        self.assertEqual(case["expected_headless_process_exit_status"], 0)
        self.assertFalse(case["expected_headless_script_load_error_log"])
        self.assertEqual(case["evidence_class"],
                         "COMPILED_PINNED_HEADLESS_PROCESS_WITH_HOST_OPEN_FAULT_INJECTION")
        self.assertFalse(case["persistence_claim"])
        self.assertEqual(case["status"], "REQUIRED_IN_EXISTING_CI")

        for key, value in (
            ("expected_api_result", True),
            ("expected_script_observation", "loadSaveFile=true"),
            ("expected_headless_process_exit_status", 1),
            ("persistence_claim", True),
            ("status", "PASSED"),
        ):
            changed = copy.deepcopy(self.matrix)
            changed["reopen_failure_contract"][key] = value
            with self.assertRaises(ValueError):
                validate_matrix(changed)

    def test_cannot_drop_observed_callback_or_teardown_or_failure_logger(self):
        for key, value in (("save_sync_callback_attempts", 0), ("mGBA_log", "Savedata synced"),
                           ("teardown_unmap_attempts", 0)):
            changed = copy.deepcopy(self.matrix)
            changed["local_execution"]["injected_sync_failure"][key] = value
            with self.assertRaises(ValueError):
                validate_matrix(changed)
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["injected_sync_failure"]["additional_save_sync_callbacks"] = 1
        with self.assertRaises(ValueError):
            validate_matrix(changed)

    def test_cannot_fabricate_cold_process_reopen(self):
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["cold_process_reopen_after_failed_sync"]["separate_headless_process"] = False
        with self.assertRaises(ValueError):
            validate_matrix(changed)
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["cold_process_reopen_after_failed_sync"]["preceded_by_successful_teardown_unmap"] = False
        with self.assertRaises(ValueError):
            validate_matrix(changed)
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["cold_process_reopen_after_failed_sync"]["script_read_sram_byte"] = "0x42"
        with self.assertRaises(ValueError):
            validate_matrix(changed)

    def test_cannot_change_pinned_source_or_dossier_hashes(self):
        changed = copy.deepcopy(self.matrix)
        changed["source_records"][0]["git_blob"] = "0" * 40
        with self.assertRaises(ValueError):
            validate_matrix(changed)
        changed = copy.deepcopy(self.matrix)
        changed["source_records"][0]["canonical_dossier_row_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_matrix(changed)
        changed = copy.deepcopy(self.matrix)
        changed["machine_dossier"]["compressed_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_matrix(changed)

    def test_cannot_promote_source_or_ci_evidence_to_independent_receipt(self):
        changed = copy.deepcopy(self.matrix)
        changed["local_execution"]["independent_semantic_approval"] = True
        with self.assertRaises(ValueError):
            validate_matrix(changed)
        changed = copy.deepcopy(self.matrix)
        changed["evidence_class"] = "INDEPENDENT_APPROVED"
        with self.assertRaises(ValueError):
            validate_matrix(changed)

    def test_dependency_edges_are_not_silently_removed(self):
        changed = copy.deepcopy(self.matrix)
        changed["dependency_edges"].pop()
        with self.assertRaises(ValueError):
            validate_matrix(changed)


if __name__ == "__main__":
    unittest.main()
