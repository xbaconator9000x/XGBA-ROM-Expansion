"""Fail-closed cross-backend save-error observer matrix controls."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_cross_backend_observability",
    ROOT / "tools/phase1_mgba_cross_backend_observability.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

MATRIX = json.loads(
    (ROOT / runner.MATRIX).read_text(encoding="utf-8")
)


class TestCrossBackendObservability(unittest.TestCase):
    def test_canonical_matrix(self):
        self.assertTrue(runner.validate_matrix_payload(copy.deepcopy(MATRIX)))

    def assert_rejected(self, mutate):
        matrix = copy.deepcopy(MATRIX)
        mutate(matrix)
        with self.assertRaises(ValueError):
            runner.validate_matrix_payload(matrix)

    def edge(self, matrix, edge_id):
        return next(edge for edge in matrix["edges"] if edge["id"] == edge_id)

    def control(self, matrix, control_id):
        return next(
            item for item in matrix["injected_failure_controls"]
            if item["id"] == control_id
        )

    def test_wrong_repository_pin(self):
        self.assert_rejected(lambda m: m.update(pinned_revision="0" * 40))

    def test_wrong_source_blob(self):
        self.assert_rejected(
            lambda m: m["reviewed_new_files"][0].update(git_blob_sha="0" * 40)
        )

    def test_wrong_source_byte_hash(self):
        self.assert_rejected(
            lambda m: m["reviewed_new_files"][0].update(source_sha256="0" * 64)
        )

    def test_stale_dossier_hash(self):
        self.assert_rejected(
            lambda m: m["machine_dossier"].update(sha256="0" * 64)
        )

    def test_wrong_canonical_dossier_row(self):
        self.assert_rejected(
            lambda m: m["reviewed_new_files"][0].update(
                dossier_row_sha256="0" * 64
            )
        )

    def test_invented_error_propagation(self):
        self.assert_rejected(
            lambda m: self.edge(m, "fd_sync_to_savedata_clean").update(
                classification="propagated"
            )
        )

    def test_conditional_logger_routes_are_not_runtime_observations(self):
        for edge_id in (
            "qt_sync_warning_log",
            "sdl_sync_warning_log",
            "libretro_sync_warning_log",
            "python_sync_warning_log",
        ):
            with self.subTest(edge_id=edge_id):
                self.assert_rejected(
                    lambda m: self.edge(m, edge_id).update(
                        execution="prior_native_failure"
                    )
                )

    def test_sync_failure_log_is_not_a_persistence_status(self):
        def mutate(matrix):
            edge = self.edge(matrix, "qt_sync_warning_log")
            edge["host_status"] = "persistence_success"

        self.assert_rejected(mutate)

    def test_python_logger_route_requires_optional_logger_contract(self):
        self.assert_rejected(
            lambda m: self.edge(m, "python_sync_warning_log").update(
                host_status="unconditional_python_error"
            )
        )

    def test_unexecuted_platform_cannot_claim_execution(self):
        self.assert_rejected(
            lambda m: self.edge(m, "other_platforms").update(
                execution="prior_native_failure"
            )
        )

    def test_unexecuted_platform_cannot_claim_propagation(self):
        def mutate(matrix):
            edge = self.edge(matrix, "other_platforms")
            edge["classification"] = "propagated"
            edge["execution"] = "prior_native_failure"

        self.assert_rejected(mutate)

    def test_injected_failure_cannot_claim_persistence_success(self):
        self.assert_rejected(
            lambda m: self.edge(m, "stdio_sync_to_savedata_clean").update(
                persistence_success_claim=True
            )
        )

    def test_injected_backend_failure_cannot_be_rewritten_as_success(self):
        self.assert_rejected(
            lambda m: self.control(m, "stdio_flush_eio").update(
                backend_result="true"
            )
        )

    def test_failure_control_cannot_claim_success(self):
        self.assert_rejected(
            lambda m: self.control(m, "fd_close_eio").update(
                persistence_success_claim=True
            )
        )

    def test_wrong_license_is_rejected(self):
        self.assert_rejected(
            lambda m: m["reviewed_new_files"][0].update(license="MIT")
        )

    def test_missing_failure_control_is_rejected(self):
        self.assert_rejected(
            lambda m: m["injected_failure_controls"].pop()
        )

    def test_duplicate_edge_is_rejected(self):
        self.assert_rejected(
            lambda m: m["edges"].append(copy.deepcopy(m["edges"][0]))
        )

    def test_claimed_durability_is_rejected(self):
        self.assert_rejected(
            lambda m: m["claims"].update(
                physical_flash_or_power_loss_evidence=True
            )
        )


if __name__ == "__main__":
    unittest.main()
