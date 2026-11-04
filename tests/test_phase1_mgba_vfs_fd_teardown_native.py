"""Fail-closed teardown evidence controls; not a native execution."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_vfs_fd_teardown_native",
    ROOT / "tools/phase1_mgba_vfs_fd_teardown_native.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\nPHASE1_TEARDOWN_DONE\n"


class TestVfsFdTeardownEvidence(unittest.TestCase):
    def test_positive_matrix(self):
        result = runner.parse_output(GOOD)
        self.assertEqual(len(result["cases"]), 6)
        self.assertTrue(result["close_failure_return_ignored_by_gba_unload"])
        self.assertFalse(result["unmap_error_return_channel"])
        self.assertFalse(result["savedata_updated_reference_in_unload"])

    def assert_mutation_rejected(self, before, after):
        changed = GOOD.replace(before, after, 1)
        self.assertNotEqual(changed, GOOD)
        with self.assertRaises(ValueError):
            runner.parse_output(changed)

    def test_sync_failure(self):
        self.assert_mutation_rejected("sync_errors=1", "sync_errors=0")

    def test_unmap_failure(self):
        self.assert_mutation_rejected("unmap_errors=1", "unmap_errors=0")

    def test_close_failure(self):
        self.assert_mutation_rejected("close_errors=1", "close_errors=0")

    def test_orphan_mapping(self):
        self.assert_mutation_rejected("orphan_map_read=163", "orphan_map_read=0")

    def test_retry_close(self):
        self.assert_mutation_rejected("retry_close=1", "retry_close=0")

    def test_fresh_process_read(self):
        self.assert_mutation_rejected(
            "fresh_process_byte=229", "fresh_process_byte=0")

    def test_short_masked_read(self):
        self.assert_mutation_rejected(
            "short_read=32 requested=4096", "short_read=4096 requested=4096")

    def test_combined_event_order(self):
        self.assert_mutation_rejected("trace=SUCSUC", "trace=SUC")

    def test_memory_unmap_contract(self):
        self.assert_mutation_rejected(
            "borrowed_unmap_live=1", "borrowed_unmap_live=0")

    def test_missing_terminal_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix("PHASE1_TEARDOWN_DONE\n"))

    def test_duplicate_terminal_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD + "PHASE1_TEARDOWN_DONE\n")

    def test_extra_case_rejected(self):
        changed = GOOD.replace(
            "PHASE1_TEARDOWN_DONE\n",
            "PHASE1_TEARDOWN_CASE injected=1\nPHASE1_TEARDOWN_DONE\n",
        )
        with self.assertRaises(ValueError):
            runner.parse_output(changed)

    def test_reordered_cases_rejected(self):
        lines = GOOD.splitlines(keepends=True)
        lines[0], lines[1] = lines[1], lines[0]
        with self.assertRaises(ValueError):
            runner.parse_output("".join(lines))

    def test_noncanonical_decimal_rejected(self):
        self.assert_mutation_rejected("sync_calls=1", "sync_calls=01")

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
            ROOT / "tests/phase1_mgba_vfs_fd_teardown_native.c"
        ).read_bytes()
        self.assertEqual(hashlib.sha256(fixture).hexdigest(),
                         runner.FIXTURE_SHA256)

    def test_internal_evidence_mutations(self):
        self.assertEqual(runner.reject_evidence_mutations(GOOD), 11)


if __name__ == "__main__":
    unittest.main()
