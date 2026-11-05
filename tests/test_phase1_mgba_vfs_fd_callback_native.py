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
    "success_rtc=1 success_script_events=2 failure_info_logs=1 "
    "failure_info_message=1 failure_info_level=8 success_info_logs=1 "
    "persistence_ack=0\n"
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

    def test_failed_sync_info_log_event(self):
        self.assert_mutation_rejected("failure_info_logs=1",
                                      "failure_info_logs=0")

    def test_failed_sync_info_log_message(self):
        self.assert_mutation_rejected("failure_info_message=1",
                                      "failure_info_message=0")

    def test_failed_sync_log_must_remain_info_level(self):
        self.assert_mutation_rejected("failure_info_level=8",
                                      "failure_info_level=2")

    def test_successful_sync_log_control(self):
        self.assert_mutation_rejected("success_info_logs=1",
                                      "success_info_logs=0")

    def test_failed_sync_cannot_claim_persistence_acknowledgment(self):
        self.assert_mutation_rejected("persistence_ack=0",
                                      "persistence_ack=1")

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

    # Native evidence must have one canonical decimal representation per value.
    # The original parser accepted zero-padded and Unicode decimal digits.
    def test_noncanonical_leading_zero_failed_sync(self):
        self.assert_mutation_rejected("failure_async_ms=1", "failure_async_ms=01")

    def test_noncanonical_leading_zero_failed_rtc(self):
        self.assert_mutation_rejected("failure_rtc=0", "failure_rtc=00")

    def test_noncanonical_negative_zero_dirty(self):
        self.assert_mutation_rejected("failure_dirty=0", "failure_dirty=-0")

    def test_noncanonical_leading_zero_failed_event(self):
        self.assert_mutation_rejected("failure_script_events=1", "failure_script_events=001")

    def test_noncanonical_leading_zero_retry(self):
        self.assert_mutation_rejected("retry_async_ms=0", "retry_async_ms=00")

    def test_noncanonical_leading_zero_retry_event(self):
        self.assert_mutation_rejected("retry_script_events=1", "retry_script_events=01")

    def test_noncanonical_leading_zero_retry_rtc(self):
        self.assert_mutation_rejected("retry_rtc=0", "retry_rtc=00")

    def test_noncanonical_leading_zero_success_sync(self):
        self.assert_mutation_rejected("new_write_success_async_ms=2",
                                      "new_write_success_async_ms=02")

    def test_noncanonical_leading_zero_success_rtc(self):
        self.assert_mutation_rejected("success_rtc=1", "success_rtc=01")

    def test_noncanonical_leading_zero_success_event(self):
        self.assert_mutation_rejected("success_script_events=2",
                                      "success_script_events=02")

    def test_noncanonical_unicode_decimal_digit(self):
        self.assert_mutation_rejected("failure_async_ms=1", "failure_async_ms=\u0661")

    def test_missing_source_function_rejected(self):
        with self.assertRaises(ValueError):
            runner.extract_function("void other(void) {}", "void target(void)")

    def test_ambiguous_source_function_rejected(self):
        with self.assertRaises(ValueError):
            runner.extract_function("void target(void) {}\nvoid target(void) {}",
                                    "void target(void)")

    def test_unbalanced_source_function_rejected(self):
        with self.assertRaises(ValueError):
            runner.extract_function("void target(void) { if (1) { return; }",
                                    "void target(void)")

    def test_nested_source_function_extraction(self):
        source = "void target(void) { if (1) { return; } }\nint after;"
        self.assertEqual(runner.extract_function(source, "void target(void)"),
                         "void target(void) { if (1) { return; } }")

    def test_fixture_hash(self):
        fixture = (ROOT / "tests/phase1_mgba_vfs_fd_callback_native.c").read_bytes()
        self.assertEqual(hashlib.sha256(fixture).hexdigest(),
                         runner.FIXTURE_SHA256)

    def test_internal_evidence_mutations(self):
        self.assertEqual(runner.reject_evidence_mutations(GOOD), 13)


if __name__ == "__main__":
    unittest.main()
