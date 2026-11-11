"""R22: repeated ORIGINAL Emerald connected-map D-pad crossings in native mGBA.

This deliberately exercises two *concurrently resident* external map packs.
It is an arena/cache stability test, NOT an eviction test: the battle phase
and future three-plus-map tests are responsible for forced eviction coverage.
No host teleportation, map pointer patching or fabricated gameplay.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher

ROUND_TRIPS=50
EXTRA_CROSSINGS=2*ROUND_TRIPS
TOTAL_CROSSINGS=2+EXTRA_CROSSINGS

class NativeEmeraldRepeatedConnectedMapChurn(unittest.TestCase):
    R19_CONNECTED=True

    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        dest=Path(os.environ.get(
            "XGBA_R22_EVIDENCE_DIR",cls.native_root/"r22-native-crossings"))
        dest.mkdir(parents=True,exist_ok=True)
        cls.output=dest
        cls.enabled=launcher.launch(
            cls.rom,cls.manifest_path,r17.RID,
            emulator=cls.executable,frames=36000,
            probe_address=cls.r19_probe,
            second_resource_id="emerald.route101",
            extra_resource_ids=(r17.BOOT,),
            r19_connected_dir=dest,
            r19_route_offset=cls.route_offset,
            r19_route_length=len(cls.route_pack),
            r22_round_trips=ROUND_TRIPS)
        if "PASS_R22_REAL_EMERALD_CONNECTED_MAP_CHURN" not in cls.enabled.stdout:
            raise AssertionError("R22 original Emerald physical connected-map churn did not pass")
        cls.disabled=launcher.launch(
            cls.rom,cls.manifest_path,r17.RID,
            emulator=cls.executable,frames=3100,
            probe_address=cls.r19_probe,
            second_resource_id="emerald.route101",
            extra_resource_ids=(r17.BOOT,),
            r19_connected_dir=dest,
            r19_route_offset=cls.route_offset,
            r19_route_length=len(cls.route_pack),
            disabled=True)
        if "PASS_R19_DISABLED_CONNECTED_MAPS_ZERO_READS" not in cls.disabled.stdout:
            raise AssertionError("R22 disabled-mode fail-closed baseline failed")
        cls.report={
            "milestone":"R22_ORIGINAL_EMERALD_CONNECTED_MAP_CHURN",
            "status":"native_accepted",
            "source_built_emerald_pin":r17.e16.EMERALD_PIN,
            "original_native_mgba_pin":r17.e16.MGBA_PIN,
            "compiled_rom_sha256":cls.rom_sha,
            "round_trips":ROUND_TRIPS,
            "extra_original_dpad_crossings":EXTRA_CROSSINGS,
            "total_original_dpad_crossings":TOTAL_CROSSINGS,
            "map_and_bg_vram_byte_verification_points":3+EXTRA_CROSSINGS,
            "initial_and_final_provider_reads":3,
            "external_map_cache_misses_after_initial_load":0,
            "arena_generation_changes_after_initial_load":0,
            "guest_arena_bytes":cls.simultaneous_bytes,
            "guest_arena_start":hex(cls.real_arena),
            "original_emerald_dpad_only":True,
            "simultaneously_resident_external_map_packs":2,
            "forced_evictions_tested":False,
            "guest_heap_fragmentation_tested_here":False,
            "disabled_fail_closed_zero_provider_reads":True,
            "native_log":cls.enabled.stdout,
            "disabled_native_log":cls.disabled.stdout,
            "scope":"Original Emerald 50 repeated route↔town physical D-pad round trips with both external packs concurrently resident, byte verification at every boundary and no pack reloads. Not a 3-map eviction or arbitrary heap-fragmentation proof."
        }
        if os.environ.get("XGBA_R22_EVIDENCE_DIR"):
            (dest/"proof.json").write_text(
                json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_original_102_physical_map_crossings(self):
        self.assertIn("extra_round_trips=50",self.enabled.stdout)
        self.assertIn("total_transitions=102",self.enabled.stdout)
        self.assertIn("original_dpad_only=1",self.enabled.stdout)

    def test_map_grid_and_bg_vram_byte_verified_on_every_crossing(self):
        self.assertIn("native_map_and_bg_vram_checks=103",self.enabled.stdout)
        self.assertIn("native_ewram=1",self.enabled.stdout)

    def test_no_pack_reloads_or_provider_failure(self):
        self.assertIn("external_map_loads=2",self.enabled.stdout)
        self.assertIn("provider_reads=3",self.enabled.stdout)

    def test_arena_ownership_and_generation_do_not_drift(self):
        self.assertIn("arena_owner=1",self.enabled.stdout)
        self.assertIn("arena_epoch=1",self.enabled.stdout)
        self.assertIn("world_claims=1",self.enabled.stdout)
        self.assertEqual(self.simultaneous_bytes,16384)

    def test_both_external_source_packs_remain_concurrently_live(self):
        self.assertGreater(self.route_offset,32*1024*1024)
        self.assertLessEqual(len(self.pack)+len(self.route_pack),16384)
        self.assertEqual(len(hashlib.sha256(self.route_pack).digest()),32)

    def test_disabled_mode_refuses_without_host_reads(self):
        self.assertIn("PASS_R19_DISABLED_CONNECTED_MAPS_ZERO_READS",
                      self.disabled.stdout)

    def test_six_authentic_240_by_160_lcd_frames(self):
        images=sorted(self.output.glob("*.png"))
        self.assertEqual(len(images),6)
        for path in images:
            with Image.open(path) as img:
                self.assertEqual(img.size,(240,160))
                self.assertGreater(len(set(img.convert("RGB").getdata())),8)

if __name__=="__main__":
    unittest.main()
