"""Fail-closed callback evidence parser tests; not a native execution."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_vfs_fd_callback_native",
    ROOT / "tools/phase1_mgba_vfs_fd_callback_native.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = (
    "PHASE1_GBA_CALLBACK_CASE failure_async_ms=1 failure_rtc=0 "
    "failure_dirty=0 failure_script_events=1 retry_async_ms=0 "
    "retry_script_events=1 retry_rtc=0 new_write_success_async_ms=2 "
    "success_rtc=1 success_script_events=2\n"
    "PHASE1_GBA_CALLBACK_DONE\n"
)


class TestGbaCallbackEvidence(unittest.TestCase):
    def test_positive(self):
        result = runner.parse_output(GOOD)
        self.assertEqual(result["script_notifications_after_failed_sync"], 1)
        self.assertEqual(result["sync_retries_without_new_write"], 0)
        self.assertEqual(result["script_notifications_after_success"], 2)

    def assert_mutation_rejected(self, before, after):
        changed = GOOD.replace(before, after, 1)
        self.assertNotEqual(changed, GOOD)
        with self.assertRaises(ValueError):
            runner.parse_output(changed)

    def test_failed_notification(self):
        self.assert_mutation_rejected("failure_script_events=1",
                                      "failure_script_events=0")

    def test_failed_rtc(self):
        self.assert_mutation_rejected("failure_rtc=0", "failure_rtc=1")

    def test_failed_dirty_cleared(self):
        self.assert_mutation_rejected("failure_dirty=0", "failure_dirty=1")

    def test_retry_without_new_write(self):
        self.assert_mutation_rejected("retry_async_ms=0", "retry_async_ms=1")

    def test_retry_event_count(self):
        self.assert_mutation_rejected("retry_script_events=1",
                                      "retry_script_events=2")

    def test_retry_rtc_count(self):
        self.assert_mutation_rejected("retry_rtc=0", "retry_rtc=1")

    def test_success_rtc_count(self):
        self.assert_mutation_rejected("success_rtc=1", "success_rtc=0")

    def test_success_notification_count(self):
        self.assert_mutation_rejected("success_script_events=2",
                                      "success_script_events=1")

    def test_extra_case_rejected(self):
        changed = GOOD.replace(
            "PHASE1_GBA_CALLBACK_DONE\n",
            "PHASE1_GBA_CALLBACK_CASE injected=1\nPHASE1_GBA_CALLBACK_DONE\n",
        )
        with self.assertRaises(ValueError):
            runner.parse_output(changed)

    def test_duplicate_terminal_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD + "PHASE1_GBA_CALLBACK_DONE\n")

    def test_missing_terminal_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix("PHASE1_GBA_CALLBACK_DONE\n"))

    def test_fixture_hash(self):
        fixture = (ROOT / "tests/phase1_mgba_vfs_fd_callback_native.c").read_bytes()
        self.assertEqual(hashlib.sha256(fixture).hexdigest(),
                         runner.FIXTURE_SHA256)

    def test_internal_evidence_mutations(self):
        self.assertEqual(runner.reject_evidence_mutations(GOOD), 8)


if __name__ == "__main__":
    unittest.main()
