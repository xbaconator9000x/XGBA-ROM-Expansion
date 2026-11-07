"""Fail-closed, source-independent controls for the native EEPROM witness log parser."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase1_eeprom_tail", ROOT / "tools/phase1_mgba_saveconverter_eeprom_tail.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SMALL = (
    "PHASE1_EEPROM_CASE eeprom512_plus16 size=528 payload=512 "
    "source_tail=a0a1a2a3a4a5a6a7a8a9aaabacadaeaf "
    "converted_tail_hex=5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a "
    "converted_tail_preserved=0 roundtrip_tail_preserved=0 payload_roundtrip=PASS\n"
)
LARGE = (
    "PHASE1_EEPROM_CASE eeprom8k_plus16 size=8208 payload=8192 "
    "source_tail=c0c1c2c3c4c5c6c7c8c9cacbcccdcecf "
    "converted_tail_hex=00000000000000000000000000000000 "
    "converted_tail_preserved=0 roundtrip_tail_preserved=0 payload_roundtrip=PASS\n"
)
VALID = SMALL + LARGE + "PHASE1_EEPROM_DONE\n"


class EEPROMEvidenceParserTests(unittest.TestCase):
    def test_two_valid_cases(self):
        cases = MODULE.parse_cases(VALID)
        self.assertEqual(set(cases), {"eeprom512_plus16", "eeprom8k_plus16"})
        self.assertTrue(all(not x["converted_tail_preserved"] for x in cases.values()))

    def test_rejects_contradictory_preservation_flag(self):
        bad = VALID.replace("converted_tail_preserved=0", "converted_tail_preserved=1", 1)
        with self.assertRaises(ValueError):
            MODULE.parse_cases(bad)

    def test_rejects_identical_tail_but_false_flag(self):
        bad = VALID.replace("5a" * 16, "a0a1a2a3a4a5a6a7a8a9aaabacadaeaf", 1)
        with self.assertRaises(ValueError):
            MODULE.parse_cases(bad)

    def test_rejects_duplicate_case(self):
        with self.assertRaises(ValueError):
            MODULE.parse_cases(SMALL + SMALL + LARGE + "PHASE1_EEPROM_DONE\n")

    def test_rejects_unparsed_extra_case(self):
        with self.assertRaises(ValueError):
            MODULE.parse_cases(VALID + "PHASE1_EEPROM_CASE malformed\n")

    def test_rejects_wrong_source_sentinel(self):
        with self.assertRaises(ValueError):
            MODULE.parse_cases(VALID.replace("a0a1a2a3", "f0f1f2f3", 1))

    def test_rejects_missing_completion(self):
        with self.assertRaises(ValueError):
            MODULE.parse_cases(SMALL + LARGE)

    def test_rejects_duplicate_completion(self):
        with self.assertRaises(ValueError):
            MODULE.parse_cases(VALID + "PHASE1_EEPROM_DONE\n")

    def test_harness_pin_is_nonempty(self):
        self.assertEqual(MODULE.HARNESS_SHA256,
                         "90ef78f72ba584bb60e2edbd9e4e51ff0f68b279192fb8b9da7c00003b2f4e9b")


if __name__ == "__main__":
    unittest.main()
