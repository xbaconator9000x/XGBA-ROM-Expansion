"""Fail-closed controls for the pinned VFile allocation witness."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_vfs_fd_allocation_native",
    ROOT / "tools/phase1_mgba_vfs_fd_allocation_native.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\nPHASE1_ALLOC_DONE\n"


class TestVfsFdAllocationEvidence(unittest.TestCase):
    def test_positive_matrix(self):
        result = runner.parse_output(GOOD)
        self.assertTrue(result["normal_open_and_close"]["fd_open_after_close"] is False)
        self.assertTrue(
            result["injected_allocation_failure"]["fd_open_after_return"])
        self.assertFalse(
            result["injected_allocation_failure"]["caller_return"])
        self.assertEqual(result["injected_allocation_failure"]["close_calls"], 0)
        self.assertEqual(result["open_failure_control"]["errno"], "ENOENT")

    def test_contradictory_evidence_rejected(self):
        self.assertEqual(runner.reject_output_mutations(GOOD), 5)

    def test_injected_failure_observation_required(self):
        self.assert_mutation_rejected(
            "allocation_failures=1", "allocation_failures=0")

    def test_descriptor_leak_observation_required(self):
        self.assert_mutation_rejected(
            "close_calls=0 fd_open_after_return=1",
            "close_calls=1 fd_open_after_return=0")

    def test_open_failure_must_not_allocate(self):
        self.assert_mutation_rejected(
            "allocation_attempts=0 allocation_failures=0 errno=ENOENT",
            "allocation_attempts=1 allocation_failures=0 errno=ENOENT")

    def test_source_controls_reject_mutations(self):
        source = (
            "struct VFile* VFileFromFD(int fd) {\n"
            "\tif (fstat(fd, &stat) < 0) {\n\t\tclose(fd);\n\t\treturn 0;\n\t}\n"
            "\tstruct VFileFD* vfd = malloc(sizeof(struct VFileFD));\n"
            "\tif (!vfd) {\n\t\treturn 0;\n\t}\n"
            "}\n"
        )
        cases = (
            ("struct VFileFD* vfd = malloc(sizeof(struct VFileFD));",
             "struct VFileFD* vfd = NULL;"),
            ("if (!vfd) {\n\t\treturn 0;\n\t}",
             "if (!vfd) {\n\t\tclose(fd);\n\t\treturn 0;\n\t}"),
            ("close(fd);\n\t\treturn 0;", "return 0;"),
        )
        for original, replacement in cases:
            changed = source.replace(original, replacement, 1)
            self.assertNotEqual(changed, source)
            with self.assertRaises(ValueError):
                runner.validate_body(
                    changed, runner.FROM_FD_SIGNATURE,
                    runner.FROM_FD_BODY_SHA256,
                    ("struct VFileFD* vfd = malloc(sizeof(struct VFileFD));",
                     "if (!vfd) {\n\t\treturn 0;\n\t}"),
                )

    def test_machine_receipt_identity_and_nonapproval(self):
        receipt_path = ROOT / runner.RECEIPT
        receipt = runner.verify_receipt(receipt_path)
        self.assertEqual(receipt["pinned_revision"], runner.PIN)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            receipt["source_record"]["full_source_sha256"] = "0" * 64
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.verify_receipt(Path(temp.name))
        receipt = runner.verify_receipt(receipt_path)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            json.dump(receipt, temp)
            temp.flush()
            parsed = json.loads(Path(temp.name).read_text(encoding="utf-8"))
        self.assertEqual(parsed["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(parsed["independent_approvals"], 0)
        self.assertEqual(len(hashlib.sha256(GOOD.encode()).hexdigest()), 64)

    def test_harness_hash(self):
        harness = (
            ROOT / "tests/phase1_mgba_vfs_fd_allocation_native.c"
        ).read_bytes()
        self.assertEqual(hashlib.sha256(harness).hexdigest(),
                         runner.HARNESS_SHA256)

    def assert_mutation_rejected(self, before, after):
        changed = GOOD.replace(before, after, 1)
        self.assertNotEqual(changed, GOOD)
        with self.assertRaises(ValueError):
            runner.parse_output(changed)


if __name__ == "__main__":
    unittest.main()
