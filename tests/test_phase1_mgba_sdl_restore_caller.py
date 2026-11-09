import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase1_mgba_sdl_restore_caller",
    ROOT / "tools/phase1_mgba_sdl_restore_caller.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class SDLRestoreCallerTests(unittest.TestCase):
    def setUp(self):
        self.receipt = RUNNER.expected_receipt()

    def test_receipt_is_pinned_and_non_approving(self):
        self.assertEqual(self.receipt["pinned_revision"], RUNNER.PIN)
        self.assertEqual(self.receipt["pinned_tree"], RUNNER.TREE)
        self.assertEqual(self.receipt["status"], "NEEDS_EVIDENCE")
        self.assertEqual(self.receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(self.receipt["independent_approvals"], 0)
        self.assertEqual(len(self.receipt["source_records"]), 1)
        self.assertEqual(len(self.receipt["dependency_identities_reused"]), 2)

    def test_source_records_bind_pinned_mpl_files(self):
        self.assertEqual({row["path"] for row in self.receipt["source_records"]},
                         {"src/platform/sdl/main.c"})
        for row in self.receipt["source_records"]:
            self.assertTrue(row["review_scope"].startswith("PARTIAL_"))
            self.assertEqual(row["license"], "MPL-2.0")
            self.assertEqual(len(row["full_source_sha256"]), 64)
            self.assertEqual(len(row["canonical_dossier_row_sha256"]), 64)

    def test_original_caller_and_callback_are_bound(self):
        self.assertIn(
            "static void _loadState(struct mCoreThread* thread) {",
            self.receipt["extracted_original_body_sha256"],
        )
        self.assertIn(
            "int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {",
            self.receipt["extracted_original_body_sha256"],
        )
        graph = "\n".join(self.receipt["source_call_graph"])
        self.assertIn("discards the bool", graph)
        self.assertIn("clears _state and closes", graph)

    def test_observations_distinguish_error_open_failure_and_retry(self):
        cases = self.receipt["observations"]
        self.assertTrue(cases["loader_failure"]["result_discarded_by_callback"])
        self.assertTrue(cases["loader_failure"]["runloop_reached"])
        self.assertFalse(cases["open_failure"]["callback_invoked"])
        self.assertTrue(cases["retry"]["retry_is_separate_msd_run_invocation"])

    def test_host_and_native_boundaries_are_explicit(self):
        limits = self.receipt["limitations"]
        self.assertTrue(limits["compiled_original_msd_run_function"])
        self.assertEqual(
            limits["core_loader"],
            "HOST_RESULT_FIXTURE_NOT_PINNED_MCORE_IMPLEMENTATION",
        )
        self.assertFalse(limits["full_sdl_frontend_build_or_execution"])
        self.assertFalse(limits["native_user_state_file"])
        self.assertFalse(limits["stock_gameplay_or_physical_flash"])

    def test_source_and_output_mutation_counts(self):
        self.assertEqual(self.receipt["source_mutations_rejected"], 4)
        self.assertEqual(self.receipt["output_mutations_rejected"], 6)

    def test_reused_header_records_are_not_counted_as_reviewed(self):
        for row in self.receipt["dependency_identities_reused"]:
            self.assertEqual(
                row["scope"],
                "IDENTITY_ONLY_REUSED_DEPENDENCY_NOT_COUNTED_AS_REVIEW",
            )

    def test_receipt_mutation_controls(self):
        for path, value in (
            (("status",), "COPILOT_REVIEWED"),
            (("overall",), "PASS"),
            (("independent_approvals",), 1),
            (("limitations", "full_sdl_frontend_build_or_execution"), True),
            (("source_records", 0, "full_source_sha256"), "0" * 64),
        ):
            changed = copy.deepcopy(self.receipt)
            target = changed
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = value
            self.assertNotEqual(changed, RUNNER.expected_receipt())

    def test_output_controls_reject_contradictory_evidence(self):
        expected = "\n".join(RUNNER.EXPECTED_LINES) + "\n" + RUNNER.TERMINAL
        self.assertEqual(RUNNER.parse_output(expected), self.receipt["observations"])
        self.assertEqual(RUNNER.reject_output_mutations(expected), 6)

    def test_machine_receipt_matches_contract(self):
        self.assertEqual(RUNNER.verify_receipt(ROOT), self.receipt)


if __name__ == "__main__":
    unittest.main()
