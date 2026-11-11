"""R6 acceptance: executed ARM/Thumb FireRed in the real pinned mGBA core.

This deliberately refuses to count Python mocks, host-only ROM reads, synthetic
memory-copy tests, missing compilers, or skipped emulator execution as success.
The proof includes six separate game executions and real OBJ VRAM verification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import xgba_resource_integration_smoke as r6


class RealFireRedMgbaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r6.verify_pins()
        cls.result = r6.run_demonstration()

    def test_real_compiled_fire_red_and_mgba_executed(self):
        self.assertEqual(self.result["status"], "REAL_NATIVE_EXECUTED")
        self.assertEqual(self.result["upstream_firered"], r6.FIRERED_PIN)
        self.assertEqual(self.result["upstream_mgba"], r6.MGBA_PIN)
        self.assertRegex(self.result["real_elf_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(self.result["real_rom_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(self.result["asset_offset"], 32 * 1024 * 1024)

    def test_host_sidecar_reaches_actual_gba_graphics_memory(self):
        positive = self.result["cases"]["positive"]
        self.assertIn("PASS_R6_FIRE_RED_EXECUTED mode=positive", positive)
        self.assertIn("copied=1", positive)
        self.assertIn("asset_above_32MiB=1", positive)

    def test_disabled_extension_preserves_original_sprite(self):
        negative = self.result["cases"]["disabled"]
        self.assertIn("PASS_R6_FIRE_RED_EXECUTED mode=disabled", negative)
        self.assertIn("copied=0", negative)

    def test_wrong_game_identity_refused_in_actual_execution(self):
        negative = self.result["cases"]["wrong-rom"]
        self.assertIn("PASS_R6_FIRE_RED_EXECUTED mode=wrong-rom", negative)
        self.assertIn("copied=0", negative)

    def test_truncated_asset_refused_in_actual_execution(self):
        negative = self.result["cases"]["truncate"]
        self.assertIn("PASS_R6_FIRE_RED_EXECUTED mode=truncate", negative)
        self.assertIn("copied=0", negative)

    def test_corrupted_digest_refused_in_actual_execution(self):
        negative = self.result["cases"]["corrupt"]
        self.assertIn("PASS_R6_FIRE_RED_EXECUTED mode=corrupt", negative)
        self.assertIn("copied=0", negative)

    def test_missing_asset_refused_in_actual_execution(self):
        negative = self.result["cases"]["missing"]
        self.assertIn("PASS_R6_FIRE_RED_EXECUTED mode=missing", negative)
        self.assertIn("copied=0")


if __name__ == "__main__":
    unittest.main()
