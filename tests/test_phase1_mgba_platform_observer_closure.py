"""Fail-closed controls for pinned mGBA platform observer dispositions."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_platform_observer_closure",
    ROOT / "tools/phase1_mgba_platform_observer_closure.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
MATRIX = json.loads((ROOT / runner.MATRIX).read_text(encoding="utf-8"))


class TestPlatformObserverClosure(unittest.TestCase):
    def test_canonical_matrix(self):
        self.assertTrue(runner.validate_matrix_payload(copy.deepcopy(MATRIX)))

    def assert_rejected(self, mutate):
        matrix = copy.deepcopy(MATRIX)
        mutate(matrix)
        with self.assertRaises(ValueError):
            runner.validate_matrix_payload(matrix)

    def path(self, matrix, path_id):
        return next(item for item in matrix["platform_paths"] if item["id"] == path_id)

    def source(self, matrix, path):
        return next(item for item in matrix["reviewed_new_files"] if item["path"] == path)

    def test_wrong_repository_pin(self):
        self.assert_rejected(lambda m: m.update(pinned_revision="0" * 40))

    def test_wrong_source_blob(self):
        self.assert_rejected(
            lambda m: self.source(m, "src/platform/3ds/main.c").update(
                git_blob_sha="0" * 40
            )
        )

    def test_wrong_source_sha256(self):
        self.assert_rejected(
            lambda m: self.source(m, "src/platform/psp2/sce-vfs.c").update(
                source_sha256="0" * 64
            )
        )

    def test_wrong_dossier_row_hash(self):
        self.assert_rejected(
            lambda m: self.source(m, "src/platform/wii/main.c").update(
                dossier_row_sha256="0" * 64
            )
        )

    def test_stale_dossier_identity(self):
        self.assert_rejected(
            lambda m: m["machine_dossier"].update(sha256="0" * 64)
        )

    def test_missing_platform_handoff(self):
        self.assert_rejected(lambda m: m["platform_paths"].pop())

    def test_unproven_switch_backend_cannot_be_asserted(self):
        self.assert_rejected(
            lambda m: self.path(m, "switch").update(
                selected_vfile_backend="ENABLE_VFS_FILE"
            )
        )

    def test_unproven_wii_backend_cannot_be_asserted(self):
        self.assert_rejected(
            lambda m: self.path(m, "wii").update(
                selected_vfile_backend="ENABLE_VFS_FD"
            )
        )

    def test_conditional_logger_cannot_be_called_unconditional(self):
        self.assert_rejected(
            lambda m: self.path(m, "3ds").update(
                observer_route="unconditional_on_screen_error"
            )
        )

    def test_logger_absence_must_drop_message(self):
        self.assert_rejected(
            lambda m: m["shared_contract"]["gui_logger"].update(
                missing_vfile="message_is_displayed"
            )
        )

    def test_short_log_write_cannot_be_claimed_checked(self):
        self.assert_rejected(
            lambda m: m["shared_contract"]["gui_logger"].update(
                write_handling="short_writes_detected_and_retried"
            )
        )

    def test_gui_shutdown_cannot_claim_persistence_acknowledgment(self):
        self.assert_rejected(
            lambda m: m["shared_contract"]["gui_shutdown"].update(
                result="successful_save_is_reported_to_host"
            )
        )

    def test_lifecycle_callbacks_are_not_save_receipts(self):
        self.assert_rejected(
            lambda m: m["shared_contract"]["gui_shutdown"].update(
                callback_distinction="gameUnloaded_is_a_persistence_receipt"
            )
        )

    def test_windows_vdir_wrapper_cannot_be_classified_as_vfile_backend(self):
        self.assert_rejected(
            lambda m: self.path(m, "windows_vdir").update(
                classification="native_windows_vfile_backend"
            )
        )

    def test_source_only_cannot_claim_native_frontend_execution(self):
        self.assert_rejected(
            lambda m: m["limits"].update(native_platform_runtime_observed=True)
        )

    def test_source_only_cannot_claim_real_log_display(self):
        self.assert_rejected(
            lambda m: m["limits"].update(real_frontend_log_display_observed=True)
        )

    def test_source_only_cannot_claim_physical_durability(self):
        self.assert_rejected(
            lambda m: m["limits"].update(physical_flash_or_power_loss_evidence=True)
        )

    def test_source_only_cannot_be_semantic_approval(self):
        self.assert_rejected(
            lambda m: m["limits"].update(semantic_approval=True)
        )


if __name__ == "__main__":
    unittest.main()
