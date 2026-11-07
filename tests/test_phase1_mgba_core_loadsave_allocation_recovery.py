"""Fail-closed controls for the pinned core-caller allocation recovery witness."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_core_loadsave_allocation_recovery",
    ROOT / "tools/phase1_mgba_core_loadsave_allocation_recovery.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\nPHASE1_CALLER_DONE\n"
PINNED_CALLER = """bool mCoreLoadSaveFile(struct mCore* core, const char* path, bool temporary) {
\tstruct VFile* vf = VFileOpen(path, O_CREAT | O_RDWR);
\tif (!vf) {
\t\treturn false;
\t}
\tif (temporary) {
\t\treturn core->loadTemporarySave(core, vf);
\t} else {
\t\treturn core->loadSave(core, vf);
\t}
}"""


class TestCoreLoadSaveAllocationRecovery(unittest.TestCase):
    def test_positive_caller_matrix(self):
        result = runner.parse_output(GOOD)
        self.assertTrue(result["normal_caller"]["target_fd_open"] is False)
        self.assertFalse(result["allocation_failure"]["caller_return"])
        self.assertEqual(result["allocation_failure"]["save_callbacks"], 0)
        self.assertTrue(result["allocation_failure"]["leaked_fd_open"])
        retry = result["retry_after_allocation_failure"]
        self.assertFalse(retry["failure_return"])
        self.assertTrue(retry["retry_return"])
        self.assertTrue(retry["leaked_first_fd_open"])
        self.assertTrue(retry["retry_fd_closed"])
        self.assertEqual(result["open_failure_control"]["errno"], "ENOENT")

    def test_six_output_mutations_are_rejected(self):
        self.assertEqual(runner.reject_output_mutations(GOOD), 6)

    def test_source_mutations_are_rejected(self):
        sources = {"src/core/core.c": PINNED_CALLER}
        self.assertEqual(runner.reject_source_mutations(sources), 3)

    def test_receipt_pins_caller_and_nonapproval(self):
        path = ROOT / runner.RECEIPT
        receipt = runner.verify_receipt(path)
        self.assertEqual(receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(receipt["independent_approvals"], 0)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            receipt["source_records"][0]["full_source_sha256"] = "0" * 64
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.verify_receipt(Path(temp.name))
        receipt = runner.verify_receipt(path)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            receipt["real_gba_savedata_callback_executed"] = True
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.verify_receipt(Path(temp.name))

    def test_narrow_fixture_and_host_fault_must_be_disclosed(self):
        receipt = runner.verify_receipt(ROOT / runner.RECEIPT)
        self.assertTrue(receipt["caller_core_struct_is_narrow_fixture"])
        self.assertTrue(receipt["host_allocator_fault_injection"])
        self.assertFalse(receipt["natural_os_allocation_failure_observed"])
        self.assertFalse(receipt["native_mgba_frontend_executed"])

    def test_harness_hash(self):
        harness = (
            ROOT / "tests/phase1_mgba_core_loadsave_allocation_recovery.c"
        ).read_bytes()
        self.assertEqual(hashlib.sha256(harness).hexdigest(),
                         runner.HARNESS_SHA256)

    def test_missing_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix("PHASE1_CALLER_DONE\n"))


if __name__ == "__main__":
    unittest.main()
