"""Fail-closed controls for the pinned mGBA fault-to-observer handoff."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_fault_observer_handoff",
    ROOT / "tools/phase1_mgba_fault_observer_handoff.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
MATRIX = json.loads((ROOT / runner.MATRIX).read_text(encoding="utf-8"))


class TestFaultObserverHandoff(unittest.TestCase):
    def test_canonical_matrix(self):
        self.assertTrue(runner.validate_matrix_payload(copy.deepcopy(MATRIX)))

    def assert_rejected(self, mutate):
        matrix = copy.deepcopy(MATRIX)
        mutate(matrix)
        with self.assertRaises(ValueError):
            runner.validate_matrix_payload(matrix)

    def path(self, matrix, path_id):
        return next(item for item in matrix["path_objections"]
                    if item["id"] == path_id)

    def test_stale_upstream_head_rejected(self):
        self.assert_rejected(lambda m: m.update(pinned_revision="0" * 40))

    def test_false_sync_success_rejected(self):
        self.assert_rejected(
            lambda m: m["native_witness"].update(
                observed="sync_success_after_EIO"
            )
        )

    def test_wrong_native_backend_rejected(self):
        self.assert_rejected(
            lambda m: m["native_witness"].update(
                backend="stdio_vfile_fflush"
            )
        )

    def test_wrong_logger_blob_rejected(self):
        self.assert_rejected(
            lambda m: m["native_witness"].update(
                source_file_git_blob="0" * 40
            )
        )

    def test_wrong_dossier_row_rejected(self):
        self.assert_rejected(
            lambda m: m["native_witness"].update(
                source_dossier_row_sha256="0" * 64
            )
        )

    def test_fabricated_persistence_ack_rejected(self):
        self.assert_rejected(
            lambda m: m["native_witness"].update(
                persistence_acknowledgment=True
            )
        )

    def test_actual_persistence_result_must_remain_unknown(self):
        self.assert_rejected(
            lambda m: m["limitations"].update(
                actual_persistence_result_observed=True
            )
        )

    def test_missing_frontend_logger_cannot_claim_delivery(self):
        self.assert_rejected(
            lambda m: self.path(m, "python").update(
                execution="frontend_log_observed"
            )
        )

    def test_qt_visibility_remains_unproven(self):
        self.assert_rejected(
            lambda m: self.path(m, "qt").update(status="RESOLVED_SOURCE_ONLY")
        )

    def test_sdl_visibility_remains_unproven(self):
        self.assert_rejected(
            lambda m: self.path(m, "sdl").update(status="RESOLVED_SOURCE_ONLY")
        )

    def test_libretro_visibility_remains_unproven(self):
        self.assert_rejected(
            lambda m: self.path(m, "libretro").update(
                status="RESOLVED_SOURCE_ONLY"
            )
        )

    def test_python_visibility_remains_unproven(self):
        self.assert_rejected(
            lambda m: self.path(m, "python").update(
                status="RESOLVED_SOURCE_ONLY"
            )
        )

    def test_headless_visibility_remains_unproven(self):
        self.assert_rejected(
            lambda m: self.path(m, "headless").update(
                status="RESOLVED_SOURCE_ONLY"
            )
        )

    def test_nonobserved_frontend_cannot_be_claimed_runtime_observed(self):
        self.assert_rejected(
            lambda m: m["limitations"].update(
                actual_frontend_log_visibility_observed=True
            )
        )

    def test_stock_game_or_physical_flash_claim_rejected(self):
        def mutate(matrix):
            matrix["limitations"]["stock_game_or_save_file_claim"] = True
        self.assert_rejected(mutate)

    def test_statuses_are_limited_to_source_resolved_or_needs_evidence(self):
        self.assert_rejected(
            lambda m: self.path(m, "core_sync_info_log").update(
                status="APPROVED"
            )
        )

    def test_duplicate_or_missing_path_is_rejected(self):
        self.assert_rejected(lambda m: m["path_objections"].pop())


if __name__ == "__main__":
    unittest.main()
