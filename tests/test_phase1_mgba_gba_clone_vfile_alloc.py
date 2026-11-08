import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_gba_clone_vfile_alloc",
    ROOT / "tools/phase1_mgba_gba_clone_vfile_alloc.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\n" + runner.TERMINAL


class TestGbaCloneVFileAllocationWitness(unittest.TestCase):
    def test_pinned_observations(self):
        observations = runner.parse_output(GOOD)
        failure = observations["injected_vfile_wrapper_allocation_failure"]
        self.assertTrue(failure["mcore_caller_return"])
        self.assertTrue(failure["clone_buffer_freed_by_gba_callback"])
        self.assertFalse(failure["savedata_extdata_present"])
        self.assertTrue(
            observations["successful_clone"]["payload_matches"]
        )
        self.assertTrue(
            observations["retry_after_wrapper_failure"]["payload_matches"]
        )

    def test_six_output_mutations_are_rejected(self):
        self.assertEqual(runner.reject_output_mutations(GOOD), 6)

    def test_receipt_is_pinned_and_non_approving(self):
        old = runner.load_old_runner(ROOT)
        receipt = runner.verify_receipt(ROOT, old)
        self.assertEqual(receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(receipt["independent_approvals"], 0)
        self.assertGreaterEqual(len(receipt["source_records"]), 15)
        self.assertTrue(
            receipt["prior_witness_nonoverlap"][
                "distinct_failure_injection_boundary"
            ]
        )

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            receipt["overall"] = "PASS"
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.verify_receipt(ROOT, old, Path(temp.name))

    def test_receipt_preserves_host_and_runtime_limits(self):
        receipt = runner.verify_receipt(ROOT, runner.load_old_runner(ROOT))
        flags = receipt["evidence_flags"]
        self.assertTrue(flags["host_wrapper_allocation_fault_injected"])
        self.assertFalse(flags["natural_os_allocation_failure_observed"])
        self.assertFalse(flags["native_mgba_frontend_executed"])
        self.assertFalse(flags["durable_persistence_tested"])
        self.assertFalse(flags["physical_flash_tested"])

    def test_function_hashes_are_concrete(self):
        for value in (
            runner.SIZE_BODY_SHA256,
            runner.VFILE_FROM_MEMORY_BODY_SHA256,
        ):
            self.assertRegex(value, re.compile(r"^[0-9a-f]{64}$"))

    def test_harness_hash(self):
        harness = (
            ROOT / "tests/phase1_mgba_gba_clone_vfile_alloc.c"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(harness).hexdigest(), runner.HARNESS_SHA256
        )

    def test_missing_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix(runner.TERMINAL))


if __name__ == "__main__":
    unittest.main()
