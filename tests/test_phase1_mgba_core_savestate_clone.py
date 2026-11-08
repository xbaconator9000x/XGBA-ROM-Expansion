import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_core_savestate_clone",
    ROOT / "tools/phase1_mgba_core_savestate_clone.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\n" + runner.TERMINAL


class TestCoreSavestateCloneCaller(unittest.TestCase):
    def test_pinned_observations(self):
        result = runner.parse_output(GOOD)
        self.assertTrue(result["normal_clone"]["savedata_extdata_present"])
        self.assertEqual(
            result["fixture_zero_result_no_save"],
            result["fixture_zero_result_failure"],
        )
        self.assertTrue(
            result["fixture_zero_result_failure"]["caller_return"]
        )
        self.assertFalse(
            result["fixture_zero_result_failure"]["savedata_extdata_present"]
        )
        self.assertEqual(
            result["no_savedata_flag_control"]["clone_callback_calls"], 0
        )
        self.assertTrue(result["retry_after_zero_result"]["payload_matches"])

    def test_six_output_mutations_are_rejected(self):
        self.assertEqual(runner.reject_output_mutations(GOOD), 6)

    def test_receipt_is_pinned_and_non_approving(self):
        receipt = runner.verify_receipt(ROOT / runner.RECEIPT)
        self.assertEqual(receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(receipt["independent_approvals"], 0)
        self.assertEqual(len(receipt["source_records"]), 10)
        self.assertTrue(receipt["prior_witness_nonoverlap"][
            "distinct_from_prior_restore_body"
        ])

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            receipt["status"] = "APPROVED"
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.verify_receipt(Path(temp.name))

    def test_receipt_does_not_promote_fixture_to_native_evidence(self):
        receipt = runner.verify_receipt(ROOT / runner.RECEIPT)
        self.assertTrue(receipt["host_vfile_fixture"])
        self.assertTrue(receipt["clone_callback_is_test_fixture"])
        self.assertFalse(receipt["original_gba_clone_callback_executed"])
        self.assertFalse(receipt["native_mgba_frontend_executed"])
        self.assertFalse(receipt["durable_persistence_tested"])
        self.assertFalse(receipt["physical_flash_tested"])

    def test_pinned_body_hashes_are_concrete(self):
        self.assertRegex(runner.MCORE_SAVE_BODY_SHA256, re.compile(r"^[0-9a-f]{64}$"))
        self.assertNotIn("dossier-verified", runner.MCORE_SAVE_BODY_SHA256)

    def test_harness_hash(self):
        harness = (ROOT / "tests/phase1_mgba_core_savestate_clone.c").read_bytes()
        self.assertEqual(hashlib.sha256(harness).hexdigest(),
                         runner.HARNESS_SHA256)

    def test_missing_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix(runner.TERMINAL))


if __name__ == "__main__":
    unittest.main()
