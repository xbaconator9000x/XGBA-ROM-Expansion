#!/usr/bin/env python3
"""Fail-closed controls for original pinned SaveConverter native QFile observations."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from phase1_mgba_saveconverter_qfile import parse_output  # noqa: E402

TEMP = (
    "PHASE1_QFILE_CASE temporary open=1 open_error=0 write=30 write_error=0 "
    "close=1 close_error=0 bytes_match=1 dialogs=0"
)
FULL = (
    "PHASE1_QFILE_CASE dev_full open=1 open_error=0 write=30 write_error=0 "
    "close=1 close_error=4 "
    "close_error_text_hex=4e6f207370616365206c656674206f6e20646576696365 "
    "bytes_match=0 dialogs=0"
)
FAILED = (
    "PHASE1_QFILE_CASE open_failure open=0 open_error=5 "
    "open_error_text_hex=4e6f20737563682066696c65206f72206469726563746f7279 "
    "write=-2 close=0 dialogs=1"
)
OUTPUT = "\n".join((TEMP, FULL, FAILED, "PHASE1_QFILE_DONE", ""))


class QFileEvidenceParserTests(unittest.TestCase):
    def assert_rejected(self, output):
        with self.assertRaises(ValueError):
            parse_output(output)

    def test_valid_exact_three_case_control(self):
        evidence = parse_output(OUTPUT)
        self.assertEqual(evidence["temporary"]["write_return"], 30)
        self.assertEqual(evidence["dev_full"]["error_after_close"], 4)
        self.assertEqual(evidence["open_failure"]["dialogs"], 1)

    def test_reject_duplicate_temporary_record(self):
        self.assert_rejected(TEMP + "\n" + OUTPUT)

    def test_reject_duplicate_dev_full_record(self):
        self.assert_rejected(OUTPUT.replace(
            "\nPHASE1_QFILE_DONE\n", "\n" + FULL + "\nPHASE1_QFILE_DONE\n"
        ))

    def test_reject_unexpected_prefix(self):
        self.assert_rejected("UNTRUSTED_OUTPUT\n" + OUTPUT)

    def test_reject_unexpected_suffix(self):
        self.assert_rejected(OUTPUT + "UNTRUSTED_OUTPUT\n")

    def test_reject_duplicate_done_marker(self):
        self.assert_rejected(OUTPUT + "PHASE1_QFILE_DONE\n")

    def test_reject_missing_done_marker(self):
        self.assert_rejected(OUTPUT.replace("PHASE1_QFILE_DONE\n", ""))

    def test_reject_missing_terminal_newline(self):
        self.assert_rejected(OUTPUT.rstrip("\n"))

    def test_reject_swapped_cases(self):
        self.assert_rejected("\n".join((FULL, TEMP, FAILED, "PHASE1_QFILE_DONE", "")))

    def test_reject_missing_dev_full_case(self):
        self.assert_rejected("\n".join((TEMP, FAILED, "PHASE1_QFILE_DONE", "")))

    def test_reject_incorrect_temporary_payload_size(self):
        self.assert_rejected(OUTPUT.replace("write=30", "write=29", 1))

    def test_reject_inconsistent_dev_full_write(self):
        self.assert_rejected(OUTPUT.replace(
            FULL, FULL.replace("write=30", "write=29")
        ))

    def test_reject_forged_temporary_bytes_match(self):
        self.assert_rejected(OUTPUT.replace(
            TEMP, TEMP.replace("bytes_match=1", "bytes_match=0")
        ))

    def test_reject_missing_dev_full_close_error(self):
        self.assert_rejected(OUTPUT.replace(
            FULL, FULL.replace("close_error=4", "close_error=0")
        ))

    def test_reject_invalid_close_error_hex(self):
        self.assert_rejected(OUTPUT.replace(
            "close_error_text_hex=4e6f", "close_error_text_hex=zz6f"
        ))

    def test_reject_suppressed_failed_open_dialog(self):
        self.assert_rejected(OUTPUT.replace(
            FAILED, FAILED.replace("dialogs=1", "dialogs=0")
        ))

    def test_reject_forged_failed_open_success(self):
        self.assert_rejected(OUTPUT.replace(
            FAILED, FAILED.replace("open_error=5", "open_error=0")
        ))


if __name__ == "__main__":
    unittest.main()
