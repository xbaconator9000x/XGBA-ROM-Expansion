#!/usr/bin/env python3
"""Negative controls for independently observed pinned FireRed/mGBA evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "guard", ROOT / "tools/phase1_save_loader_evidence_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
EVIDENCE = json.loads((ROOT / "tests/evidence/phase1_real_rom_probe_40525408728.json").read_text())

class SaveLoaderEvidenceGuardTests(unittest.TestCase):
    def test_known_observations_stay_inconclusive(self):
        result = guard.verify_observations(EVIDENCE)
        self.assertEqual(result["cases_verified_against_job_log"], 9)
        self.assertFalse(result["loader_entry_return_witnessed"])
        self.assertFalse(result["game_side_save_reload_verified"])
        self.assertEqual(result["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(result["independent_approvals_added"], 0)

    def assert_rejected(self, mutator):
        data = copy.deepcopy(EVIDENCE)
        mutator(data)
        with self.assertRaises(ValueError):
            guard.verify_observations(data)

    def test_reject_fabricated_approval(self):
        self.assert_rejected(lambda d: d.update(independent_approvals=1))

    def test_reject_claimed_loader_success(self):
        self.assert_rejected(lambda d: d.update(classification="GAME_SAVE_RELOAD_CONFIRMED"))

    def test_reject_changed_head(self):
        self.assert_rejected(lambda d: d.update(head_sha="0"*40))

    def test_reject_changed_source_pin(self):
        self.assert_rejected(lambda d: d["source_pins"].update({"src/save.c":"0"*40}))

    def test_reject_missing_case(self):
        self.assert_rejected(lambda d: d["observations"].pop())

    def test_reject_duplicate_case(self):
        self.assert_rejected(lambda d: d["observations"][1].update(case_name="empty"))

    def test_reject_fabricated_status(self):
        self.assert_rejected(lambda d: d["observations"][1].update(save_status=1))

    def test_reject_fabricated_counter(self):
        self.assert_rejected(lambda d: d["observations"][2].update(save_counter=1))

    def test_reject_changed_flash_result(self):
        self.assert_rejected(lambda d: d["observations"][7].update(flash_byte_40=255))

    def test_reject_unverified_source(self):
        with self.assertRaises(ValueError):
            guard.verify_pinned_sources(b"not pinned src/save.c", b"not pinned include/save.h")

if __name__ == "__main__":
    unittest.main()
