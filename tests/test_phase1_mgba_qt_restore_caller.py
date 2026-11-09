import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase1_mgba_qt_restore_caller",
    ROOT / "tools/phase1_mgba_qt_restore_caller.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class QtRestoreCallerTests(unittest.TestCase):
    def setUp(self):
        self.receipt = RUNNER.expected_receipt()

    def test_receipt_is_pinned_and_non_approving(self):
        self.assertEqual(self.receipt["pinned_revision"], RUNNER.PIN)
        self.assertEqual(self.receipt["pinned_tree"], RUNNER.TREE)
        self.assertEqual(self.receipt["status"], "NEEDS_EVIDENCE")
        self.assertEqual(self.receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(self.receipt["independent_approvals"], 0)
        self.assertEqual(len(self.receipt["source_records"]), 9)
        RUNNER.verify_receipt(ROOT)

    def test_receipt_binds_each_file_and_partial_scope(self):
        paths = {record["path"] for record in self.receipt["source_records"]}
        self.assertEqual(paths, set(RUNNER.SOURCES))
        for record in self.receipt["source_records"]:
            self.assertTrue(record["review_scope"].startswith("PARTIAL_"))
            self.assertEqual(record["license"], "MPL-2.0")
            self.assertTrue(record["git_blob"])
            self.assertEqual(len(record["full_source_sha256"]), 64)
            self.assertEqual(len(record["canonical_dossier_row_sha256"]), 64)

    def test_source_controls_cover_result_cleanup_and_open_boundaries(self):
        self.assertEqual(self.receipt["source_mutations_rejected"], 7)
        self.assertIn(
            "void CoreController::loadState(const QString& path, int flags)",
            self.receipt["extracted_original_body_sha256"],
        )
        self.assertIn(
            "VFile* VFileDevice::open(const QString& path, int mode)",
            self.receipt["extracted_original_body_sha256"],
        )

    def test_receipt_does_not_claim_full_frontend_or_backend_execution(self):
        limits = self.receipt["limitations"]
        self.assertTrue(limits["native_qt6core_qiodevice"])
        self.assertFalse(limits["full_qt_frontend_build"])
        self.assertFalse(limits["qt_widgets_or_window_execution"])
        self.assertFalse(limits["sdl_frontend_build_or_execution"])
        self.assertFalse(limits["native_filesystem_open"])
        self.assertEqual(
            limits["mcore_save_and_load_implementation"],
            "HOST_FIXTURE_NOT_PINNED_CORE",
        )

    def test_observations_keep_failure_recovery_and_retry_distinct(self):
        observations = self.receipt["observations"]
        self.assertFalse(observations["rejected_state"]["load_result"])
        self.assertTrue(observations["rejected_state"]["qiodevice_closed"])
        self.assertTrue(observations["backup_recovery"]["original_state_restored"])
        self.assertTrue(observations["filename_retry"]["load_result"])
        self.assertFalse(observations["filename_open_failure"]["mcore_load_or_save_called"])

    def test_receipt_mutations_are_rejected(self):
        for path, key in (
            (("status",), "COPILOT_REVIEWED"),
            (("overall",), "PASS"),
            (("independent_approvals",), 1),
            (("limitations", "full_qt_frontend_build"), True),
            (("source_records", 0, "full_source_sha256"), "0" * 64),
        ):
            changed = copy.deepcopy(self.receipt)
            target = changed
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = key
            with self.assertRaises(ValueError):
                RUNNER.require(
                    changed == RUNNER.expected_receipt(),
                    "mutated receipt should differ",
                )

    def test_output_controls_reject_missing_or_contradictory_evidence(self):
        expected = "\n".join(RUNNER.EXPECTED_LINES) + "\n" + RUNNER.TERMINAL
        self.assertEqual(RUNNER.parse_output(expected), self.receipt["observations"])
        self.assertEqual(RUNNER.reject_output_mutations(expected), 8)

    def test_source_call_graph_distinguishes_qt_and_sdl(self):
        graph = "\n".join(self.receipt["source_call_graph"])
        self.assertIn("Qt Window file dialog", graph)
        self.assertIn("VFileOpen with a Qt QBuffer fixture", graph)
        self.assertIn("ignores mCoreLoadStateNamed's bool", graph)
        self.assertIn("no direct log call", graph)


if __name__ == "__main__":
    unittest.main()
