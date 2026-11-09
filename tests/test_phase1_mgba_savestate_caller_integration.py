import hashlib
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_savestate_caller_integration",
    ROOT / "tools/phase1_mgba_savestate_caller_integration.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\n" + runner.TERMINAL


class TestSavestateCallerIntegration(unittest.TestCase):
    def test_receipt_is_pinned_and_non_approving(self):
        restore = runner.load_restore_runner(ROOT)
        receipt = runner.verify_receipt(ROOT, restore)
        self.assertEqual(receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(receipt["independent_approvals"], 0)
        self.assertEqual(len(receipt["source_records"]), 3)
        self.assertEqual(
            receipt["nonoverlap"]["new_executed_caller"],
            "src/platform/libretro/libretro.c::retro_unserialize",
        )

    def test_pinned_observations(self):
        observations = runner.parse_output(GOOD)
        self.assertTrue(observations["short_core_state"]["failure_propagated"])
        self.assertTrue(
            observations["valid_extdata_after_malformed_retry"][
                "restore_vfile_closed_by_unmask"
            ]
        )

    def test_six_output_mutations_are_rejected(self):
        self.assertEqual(runner.reject_output_mutations(GOOD), 6)

    def test_missing_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix(runner.TERMINAL))

    def test_harness_hash(self):
        harness = (
            ROOT / "tests/phase1_mgba_savestate_caller_integration.c"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(harness).hexdigest(), runner.HARNESS_SHA256
        )

    def test_injection_markers_are_bound_to_their_harnesses(self):
        base = (ROOT / runner.BASE_HARNESS).read_text(encoding="utf-8")
        harness = (
            ROOT / "tests/phase1_mgba_savestate_caller_integration.c"
        ).read_text(encoding="utf-8")
        self.assertEqual(base.count("PHASE1_INSERT_PINNED_RESTORE_FUNCTIONS"), 1)
        self.assertEqual(harness.count("PHASE1_INSERT_PINNED_LIBRETRO_UNSERIALIZE"), 1)
        self.assertNotIn("PHASE1_INSERT_PINNED_RESTORE_FUNCTIONS", harness)

    def test_receipt_preserves_native_and_durability_limits(self):
        restore = runner.load_restore_runner(ROOT)
        limitations = runner.verify_receipt(ROOT, restore)["limitations"]
        self.assertTrue(limitations["compiled_unchanged_extracted_libretro_retro_unserialize"])
        self.assertFalse(limitations["native_libretro_or_gui_frontend_executed"])
        self.assertFalse(limitations["naturally_malformed_user_savestate_observed"])
        self.assertFalse(limitations["durable_savestate_or_sav_persistence_tested"])
        self.assertFalse(limitations["stock_gameplay_or_physical_flash_tested"])


if __name__ == "__main__":
    unittest.main()
