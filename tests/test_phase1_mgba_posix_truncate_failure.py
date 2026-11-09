import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase1_mgba_posix_truncate_failure",
    ROOT / "tools/phase1_mgba_posix_truncate_failure.py",
)
witness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(witness)


class PosixTruncateFailureControls(unittest.TestCase):
    def setUp(self):
        self.output = "\n".join(witness.EXPECTED_LINES) + "\n"

    def test_exact_native_harness_observations(self):
        observations = witness.parse_output(self.output)
        self.assertTrue(observations["normal_growth_returned_true_and_cleaned_up"])
        self.assertTrue(observations["injected_eio_and_enospc_each_reached_sigbus"])
        self.assertFalse(observations["truncate_failure_propagated_to_gba_loadsave"])
        self.assertTrue(observations["separate_retry_after_fault_removal_succeeded"])
        self.assertFalse(observations["durability_claim"])

    def test_output_mutation_controls(self):
        self.assertEqual(witness.reject_output_mutations(self.output), 8)

    def test_missing_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "observations changed"):
            witness.parse_output(self.output.replace("injected_EIO", "eio", 1))

    def test_receipt_is_pinned_and_non_approving(self):
        receipt = witness.load_receipt()
        self.assertEqual(receipt["status"], "NEEDS_EVIDENCE")
        self.assertEqual(receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(receipt["independent_approvals"], 0)

    def test_receipt_approval_mutation_is_rejected(self):
        receipt = witness.load_receipt()
        receipt["status"] = "APPROVED"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "remain non-approving"):
                witness.load_receipt(path)


if __name__ == "__main__":
    unittest.main()
