import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_savestate_restore_consumer",
    ROOT / "tools/phase1_mgba_savestate_restore_consumer.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\n" + runner.TERMINAL


class TestSavestateRestoreConsumerWitness(unittest.TestCase):
    def test_pinned_observations(self):
        observations = runner.parse_output(GOOD)
        self.assertTrue(observations["short_payload"]["mcore_return"])
        self.assertTrue(
            observations["short_payload"]["failed_extdata_allocation_released"]
        )
        self.assertTrue(
            observations["valid_writeback"]["restore_vfile_closed_before_return"]
        )
        self.assertTrue(
            observations["valid_deferred_restore"]["restore_vfile_closed_by_unmask"]
        )

    def test_six_output_mutations_are_rejected(self):
        self.assertEqual(runner.reject_output_mutations(GOOD), 6)

    def test_receipt_is_pinned_and_non_approving(self):
        receipt = runner.verify_receipt(ROOT, None)
        self.assertEqual(receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(receipt["independent_approvals"], 0)
        self.assertEqual(len(receipt["source_records"]), 19)
        self.assertTrue(receipt["nonoverlap"]["distinct_downstream_consumer"])

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            receipt["overall"] = "PASS"
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.verify_receipt(ROOT, None, Path(temp.name))

    def test_receipt_preserves_runtime_limits(self):
        receipt = runner.verify_receipt(ROOT, None)
        limits = receipt["limitations"]
        self.assertTrue(limits["host_memory_vfile_and_allocator_tracking"])
        self.assertFalse(limits["natural_malformed_savestate_observed"])
        self.assertFalse(limits["full_mgba_core_or_frontend_compiled"])
        self.assertFalse(limits["durable_savestate_or_sav_persistence_tested"])
        self.assertFalse(limits["physical_flash_tested"])

    def test_function_hashes_are_concrete(self):
        for _, _, digest, _ in runner.FUNCTIONS.values():
            self.assertRegex(digest, re.compile(r"^[0-9a-f]{64}$"))

    def test_harness_hash(self):
        harness = (
            ROOT / "tests/phase1_mgba_savestate_restore_consumer.c"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(harness).hexdigest(), runner.HARNESS_SHA256
        )

    def test_missing_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix(runner.TERMINAL))


if __name__ == "__main__":
    unittest.main()
