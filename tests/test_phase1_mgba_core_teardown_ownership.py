import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_core_teardown_ownership",
    ROOT / "tools/phase1_mgba_core_teardown_ownership.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\nPHASE1_CORE_TEARDOWN_DONE\n"


class TestCoreTeardownOwnershipEvidence(unittest.TestCase):
    def test_positive_observations(self):
        result = runner.parse_output(GOOD)
        self.assertEqual(result["cases"], ["normal", "sync_and_close_failure"])
        self.assertFalse(result["core_deinit_has_error_return"])
        self.assertTrue(result["savedata_refs_cleared_before_board_free"])
        self.assertTrue(
            result["close_failure_orphans_backend_wrapper_from_production_owner"])
        self.assertFalse(result["production_retry_after_close_failure"])
        self.assertTrue(result["harness_only_close_retry"])
        self.assertFalse(result["page_cache_or_durable_save_claim"])

    def test_output_mutations_rejected(self):
        self.assertEqual(runner.reject_output_mutations(GOOD), 10)

    def test_receipt_is_non_approving_and_source_bound(self):
        receipt = runner.load_receipt()
        self.assertEqual(receipt["independent_approvals"], 0)
        self.assertEqual(receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(receipt["status"], "NEEDS_EVIDENCE")
        self.assertEqual(receipt["distinct_scope"]["new_original_files"], 0)
        self.assertEqual(
            set(record["path"] for record in receipt["source_records"]),
            {
                "include/mgba-util/vfs.h",
                "src/util/vfs/vfs-fd.c",
                "src/gba/savedata.c",
                "src/gba/gba.c",
                "src/gba/core.c",
            },
        )
        self.assertTrue(all(
            record["license"] == "MPL-2.0" and
            record["whole_file_semantic_coverage"] is False
            for record in receipt["source_records"]
        ))

    def test_harness_hash_matches_receipt(self):
        receipt = runner.load_receipt()
        digest = hashlib.sha256(runner.HARNESS.read_bytes()).hexdigest()
        self.assertEqual(digest, receipt["harness_sha256"])

    def test_receipt_mutation_is_not_accepted(self):
        receipt = json.loads(runner.RECEIPT.read_text(encoding="utf-8"))
        receipt["independent_approvals"] = 1
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.load_receipt(Path(temp.name))

    def test_terminal_marker_required(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix(
                "PHASE1_CORE_TEARDOWN_DONE\n"))


if __name__ == "__main__":
    unittest.main()
