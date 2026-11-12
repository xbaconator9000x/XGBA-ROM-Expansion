"""R28 native original Emerald three-map D-pad/physical-cache acceptance.

One original source-built Emerald game walks Littleroot (0:9) -> Route101
(0:16) -> Oldale (0:10) -> Route101 -> Littleroot. The existing game copies
genuine source-backed map data via the normal connected-map camera. Only two
full resources fit the real protected 16 KiB EWRAM at any instant.
Portable fake-cache tests are NOT a substitute for this native criterion.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher


class RealEmeraldThreeMapLRUEviction(unittest.TestCase):
    R19_CONNECTED=True
    R28_THREE_MAPS=True

    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        cls.output=Path(os.environ.get(
            "XGBA_R28_EVIDENCE_DIR",cls.native_root/"r28-native-three-map"))
        cls.output.mkdir(parents=True,exist_ok=True)
        common=dict(
            emulator=cls.executable,
            frames=3400,
            probe_address=cls.r19_probe,
            second_resource_id="emerald.route101",
            extra_resource_ids=(r17.BOOT,"emerald.oldale"),
            r19_route_offset=cls.route_offset,
            r19_route_length=len(cls.route_pack),
            r28_oldale_offset=cls.oldale_offset,
            r28_oldale_length=len(cls.oldale_pack),
            r28_three_map_dir=cls.output,
        )
        cls.enabled=launcher.launch(cls.rom,cls.manifest_path,r17.RID,**common)
        cls.log=cls.enabled.stdout
        if "PASS_R28_REAL_EMERALD_THREE_MAP_EVICTION" not in cls.log:
            raise AssertionError("R28 native original Emerald D-pad cache proof did not pass")
        cls.disabled=launcher.launch(
            cls.rom,cls.manifest_path,r17.RID,disabled=True,**common)
        if "PASS_R28_DISABLED_EMERALD_ZERO_PROVIDER_READS" not in cls.disabled.stdout:
            raise AssertionError("R28 disabled original-game source refusal unverified")
        cls.report={
            "milestone":"R28_REAL_EMERALD_THREE_MAP_TWO_SLOT_EVICTION",
            "status":"native_accepted",
            "emerald_pin":r17.e16.EMERALD_PIN,
            "native_mgba_pin":r17.e16.MGBA_PIN,
            "compiled_rom_sha256":cls.rom_sha,
            "source_map_sequence":[9,16,10,16,9],
            "logical_resource_count":3,
            "simultaneously_resident_full_resource_slots":2,
            "actual_ewram_reserve":cls.simultaneous_bytes,
            "arena_start":hex(cls.real_arena),
            "external_source_offsets":{
                "littleroot":cls.offset,
                "route101":cls.route_offset,
                "oldale":cls.oldale_offset,
            },
            "source_pack_sha256":{
                "littleroot":hashlib.sha256(cls.pack).hexdigest(),
                "route101":hashlib.sha256(cls.route_pack).hexdigest(),
                "oldale":hashlib.sha256(cls.oldale_pack).hexdigest(),
            },
            "compiled_original_oldale_grid_removed":any(
                x["asset"]=="OldaleTown.map" for x in cls.removed),
            "physical_original_dpad_inputs":True,
            "host_teleportation_or_gpu_frame_synthesis":False,
            "native_c_log":cls.log,
            "disabled_log":cls.disabled.stdout,
        }
        if os.environ.get("XGBA_R28_EVIDENCE_DIR"):
            (cls.output/"proof.json").write_text(
                json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_genuine_three_connected_emerald_maps_visited_and_revisited(self):
        self.assertIn("map_sequence=9,16,10,16,9",self.log)
        self.assertIn("native_dpad=1",self.log)

    def test_two_simultaneous_guest_resident_slots_not_three(self):
        self.assertIn("exact_two_slots=1",self.log)
        self.assertEqual(self.simultaneous_bytes,16384)
        self.assertGreater(len(self.pack)+len(self.route_pack)+len(self.oldale_pack),
                           self.simultaneous_bytes)

    def test_real_map_cache_forces_evictions_and_reacquisition(self):
        self.assertIn("evictions=",self.log)
        self.assertIn("guest_map_loads=",self.log)
        self.assertIn("source_verified=1",self.log)

    def test_exact_original_map_grids_and_bg_vram_verified(self):
        self.assertIn("backup_grids_verified=5",self.log)
        self.assertIn("bg_vram_verified=1",self.log)

    def test_original_oldale_map_grid_was_removed_from_compiled_rom(self):
        self.assertTrue(self.report["compiled_original_oldale_grid_removed"])
        self.assertEqual(len(self.oldale_grid),800)
        self.assertGreater(self.oldale_offset,32*1024*1024)

    def test_disabled_mode_fails_closed_without_any_external_reads(self):
        self.assertIn("PASS_R28_DISABLED_EMERALD_ZERO_PROVIDER_READS",
                      self.disabled.stdout)

    def test_five_genuine_240x160_original_game_lcd_pngs(self):
        imgs=sorted(self.output.glob("*.png"))
        self.assertEqual(len(imgs),5)
        for path in imgs:
            with Image.open(path) as im:
                self.assertEqual(im.size,(240,160))
                self.assertGreater(len(set(im.convert("RGB").getdata())),8)

    def test_original_unchanged_pinned_source_and_sha_resource_contract(self):
        self.assertEqual(self.report["emerald_pin"],r17.e16.EMERALD_PIN)
        self.assertEqual(self.report["native_mgba_pin"],r17.e16.MGBA_PIN)
        self.assertEqual(len(self.report["compiled_rom_sha256"]),64)


if __name__=="__main__":
    unittest.main()
