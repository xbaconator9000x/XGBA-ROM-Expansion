"""Fail-closed stdio VFile source and evidence controls."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_vfs_stdio_native",
    ROOT / "tools/phase1_mgba_vfs_stdio_native.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\nPHASE1_STDIO_DONE\n"


class TestVfsStdioEvidence(unittest.TestCase):
    def test_positive_matrix(self):
        result = runner.parse_output(GOOD)
        self.assertEqual(len(result["cases"]), 7)
        self.assertTrue(result["raw_short_write_reported_as_load_success"])
        self.assertTrue(result["unmask_load_failure_result_ignored"])
        self.assertTrue(result["unload_ignores_close_failure"])

    def assert_mutation_rejected(self, before, after):
        changed = GOOD.replace(before, after, 1)
        self.assertNotEqual(changed, GOOD)
        with self.assertRaises(ValueError):
            runner.parse_output(changed)

    def test_backend_selection(self):
        self.assert_mutation_rejected(
            "backend=stdio", "backend=fd")

    def test_mapped_unmap_short_write(self):
        self.assert_mutation_rejected(
            "written=3 data_cleared=1", "written=4096 data_cleared=1")

    def test_raw_load_short_write_result(self):
        self.assert_mutation_rejected(
            "written=3 load_result=1", "written=3 load_result=0")

    def test_unmask_short_read(self):
        self.assert_mutation_rejected(
            "read_bytes=32 requested=4096", "read_bytes=4096 requested=4096")

    def test_injected_flush_failure(self):
        self.assert_mutation_rejected(
            "sync_result=0 injected=1", "sync_result=1 injected=1")

    def test_dev_full_flush_failure(self):
        self.assert_mutation_rejected(
            "dev_full_clean write_errors=1", "dev_full_clean write_errors=0")

    def test_close_failure_lifecycle(self):
        self.assert_mutation_rejected(
            "wrapper_retained=1", "wrapper_retained=0")

    def test_child_process_visibility(self):
        self.assert_mutation_rejected(
            "child_byte=212", "child_byte=0")

    def test_missing_terminal_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix("PHASE1_STDIO_DONE\n"))

    def test_duplicate_terminal_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD + "PHASE1_STDIO_DONE\n")

    def test_extra_case_rejected(self):
        changed = GOOD.replace(
            "PHASE1_STDIO_DONE\n",
            "PHASE1_STDIO_CASE extra=1\nPHASE1_STDIO_DONE\n",
        )
        with self.assertRaises(ValueError):
            runner.parse_output(changed)

    def test_reordered_cases_rejected(self):
        lines = GOOD.splitlines(keepends=True)
        lines[0], lines[1] = lines[1], lines[0]
        with self.assertRaises(ValueError):
            runner.parse_output("".join(lines))

    def test_missing_function_rejected(self):
        with self.assertRaises(ValueError):
            runner.extract_function("void other(void) {}", "void target(void)",
                                    "0" * 64)

    def test_ambiguous_function_rejected(self):
        sample = "void target(void) {}\nvoid target(void) {}"
        digest = hashlib.sha256("void target(void) {}".encode()).hexdigest()
        with self.assertRaises(ValueError):
            runner.extract_function(sample, "void target(void)", digest)

    def test_nested_function_extraction(self):
        body = "void target(void) { if (1) { return; } }"
        digest = hashlib.sha256(body.encode()).hexdigest()
        self.assertEqual(
            runner.extract_function(body + "\nint after;", "void target(void)",
                                     digest),
            body,
        )

    def test_fixture_hash(self):
        fixture = (
            ROOT / "tests/phase1_mgba_vfs_stdio_native.c"
        ).read_bytes()
        self.assertEqual(hashlib.sha256(fixture).hexdigest(),
                         runner.FIXTURE_SHA256)

    def test_internal_evidence_mutations(self):
        self.assertEqual(runner.reject_evidence_mutations(GOOD), 10)


if __name__ == "__main__":
    unittest.main()
