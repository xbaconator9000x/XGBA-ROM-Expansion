#!/usr/bin/env python3
"""Offline mutation controls for source and native save-path evidence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from phase1_firered_save_path_closure import validate_native_flash_trace


def successful_trace():
    return [
        {
            "sector": sector,
            "return_value": 0,
            "changed_bytes": 64 + sector,
            "entry_pc": 0x08001234,
            "return_pc": 0x08005678,
            "entry_frame": 300 + sector,
            "return_frame": 301 + sector,
            "dirty_after": 1,
        }
        for sector in range(14, 28)
    ]


class SavePathEvidenceTests(unittest.TestCase):
    def test_game_driven_trace_requires_fourteen_sector_effects(self):
        self.assertEqual(validate_native_flash_trace(successful_trace()), list(range(14, 28)))

    def test_no_input_is_a_distinct_no_program_negative_control(self):
        self.assertEqual(validate_native_flash_trace([], no_save=True), [])
        with self.assertRaises(AssertionError):
            validate_native_flash_trace(successful_trace(), no_save=True)

    def test_sector_corruption_or_duplication_rejected(self):
        rows = successful_trace()
        rows[0]["sector"] = 15
        with self.assertRaises(AssertionError):
            validate_native_flash_trace(rows)

    def test_failed_program_return_rejected(self):
        rows = successful_trace()
        rows[5]["return_value"] = 1
        with self.assertRaises(AssertionError):
            validate_native_flash_trace(rows)

    def test_missing_mapped_flash_byte_effect_rejected(self):
        rows = successful_trace()
        rows[7]["changed_bytes"] = 0
        with self.assertRaises(AssertionError):
            validate_native_flash_trace(rows)

    def test_missing_mgba_dirty_state_rejected(self):
        rows = successful_trace()
        rows[9]["dirty_after"] = 0
        with self.assertRaises(AssertionError):
            validate_native_flash_trace(rows)

    def test_return_pc_mutation_rejected(self):
        rows = successful_trace()
        rows[3]["return_pc"] = 0x02000000
        with self.assertRaises(AssertionError):
            validate_native_flash_trace(rows)

    def test_boolean_cannot_forge_numeric_trace_evidence(self):
        rows = successful_trace()
        rows[2]["changed_bytes"] = True
        with self.assertRaises(AssertionError):
            validate_native_flash_trace(rows)


if __name__ == "__main__":
    unittest.main()
