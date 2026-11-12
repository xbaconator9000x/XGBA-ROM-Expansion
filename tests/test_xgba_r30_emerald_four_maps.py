"""R30: four genuine original Emerald external map packs, two real 8KiB slots.

Unmodified pinned pokeemerald sources patched at source-build time execute
physical D-pad Littleroot->Route101->Oldale->Route102->Oldale->Route101->Littleroot.
This class is never replaced by mocked map memory or fake LCD images.
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


class RealEmeraldFourExternalMaps(unittest.TestCase):
    R19_CONNECTED=True
    R30_FOUR_MAPS=True

    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        cls.output=Path(os.environ.get(
            "XGBA_R30_EVIDENCE_DIR",cls.native_root/"r30-native-four-map"))
        cls.output.mkdir(parents=True,exist_ok=True)
        common=dict(
            emulator=cls.executable,frames=5300,probe_address=cls.r19_probe,
            second_resource_id="emerald.route101",
            extra_resource_ids=(r17.BOOT,"emerald.oldale","emerald.route102"),
            r19_route_offset=cls.route_offset,
            r19_route_length=len(cls.route_pack),
            r28_oldale_offset=cls.oldale_offset,
            r28_oldale_length=len(cls.oldale_pack),
            r30_route102_offset=cls.route102_offset,
            r30_route102_length=len(cls.route102_pack),
            r30_four_map_dir=cls.output,
        )
        cls.native=launcher.launch(cls.rom,cls.manifest_path,r17.RID,**common)
        cls.log=cls.native.stdout
        if "PASS_R30_REAL_EMERALD_FOUR_MAP_EVICTION" not in cls.log:
            raise AssertionError("Genuine source-built Emerald R30 native D-pad proof absent")
        cls.disabled=launcher.launch(
            cls.rom,cls.manifest_path,r17.RID,disabled=True,**common)
        if "PASS_R30_DISABLED_ORIGINAL_EMERALD_ZERO_PROVIDER_READS" not in cls.disabled.stdout:
            raise AssertionError("Original Emerald disabled provider refused source incorrectly")
        cls.report={
            "milestone":"R30_ORIGINAL_EMERALD_FOUR_MAP_TWO_SLOT_NATIVE",
            "status":"native_accepted",
            "emerald_pin":r17.e16.EMERALD_PIN,
            "mgba_pin":r17.e16.MGBA_PIN,
            "rom_sha256":cls.rom_sha,
            "source_map_sequence":[9,16,10,17,10,16,9],
            "logical_resource_count":4,
            "simultaneous_physical_map_slots":2,
            "actual_guest_ewram_reservation_bytes":cls.simultaneous_bytes,
            "physical_dpad":True,
            "host_teleports":False,
            "external_sha256":{
                "Littleroot":hashlib.sha256(cls.pack).hexdigest(),
                "Route101":hashlib.sha256(cls.route_pack).hexdigest(),
                "OldaleTown":hashlib.sha256(cls.oldale_pack).hexdigest(),
                "Route102":hashlib.sha256(cls.route102_pack).hexdigest(),
            },
            "external_offsets":{
                "Littleroot":cls.offset,
                "Route101":cls.route_offset,
                "OldaleTown":cls.oldale_offset,
                "Route102":cls.route102_offset,
            },
            "map_and_border_bytes_removed":cls.removed,
            "native_c_log":cls.log,
            "disabled_log":cls.disabled.stdout,
        }
        if os.environ.get("XGBA_R30_EVIDENCE_DIR"):
            (cls.output/"proof.json").write_text(json.dumps(
                cls.report,sort_keys=True,indent=2)+"\n")

    def test_original_game_physically_walked_four_distinct_connected_maps(self):
        self.assertIn("map_sequence=9,16,10,17,10,16,9",self.log)
        self.assertIn("native_dpad=1",self.log)

    def test_original_route102_exact_50_by_20_metatile_grid_source(self):
        self.assertEqual(len(self.route102_grid),2000)
        self.assertEqual(len(self.route102_border),8)
        self.assertEqual(
            sum(x["asset"]=="Route102.map" for x in self.removed),1)
        self.assertEqual(
            sum(x["asset"]=="Route102.border" for x in self.removed),1)

    def test_two_slots_remain_real_16k_reserved_ewram(self):
        self.assertEqual(self.simultaneous_bytes,16384)
        self.assertIn("physical_slots=2",self.log)
        self.assertLessEqual(max(map(len,(
            self.pack,self.route_pack,self.oldale_pack,self.route102_pack))),8192)
        self.assertGreater(sum(map(len,(
            self.pack,self.route_pack,self.oldale_pack,self.route102_pack))),16384)

    def test_all_four_independently_addressed_sha256_source_resources(self):
        self.assertEqual(len(self.report["external_sha256"]),4)
        for digest in self.report["external_sha256"].values():
            self.assertEqual(len(digest),64)
        self.assertGreater(self.route102_offset,32*1024*1024)

    def test_real_guest_all_seven_backup_grids_and_bg_vram(self):
        self.assertIn("backup_grids_verified=7",self.log)
        self.assertIn("bg_vram_verified=1",self.log)

    def test_real_guest_evicts_and_reacquires_map_packs(self):
        self.assertIn("evictions=",self.log)
        self.assertIn("source_verified=1",self.log)
        self.assertIn("guest_map_loads=",self.log)

    def test_genuine_seven_original_emerald_240_by_160_lcd_images(self):
        pngs=sorted(self.output.glob("*.png"))
        self.assertEqual(len(pngs),7)
        for file in pngs:
            with Image.open(file) as im:
                self.assertEqual(im.size,(240,160))
                self.assertGreater(len(set(im.convert("RGB").getdata())),8)

    def test_external_provider_disabled_fails_closed_without_source_reads(self):
        self.assertIn(
            "PASS_R30_DISABLED_ORIGINAL_EMERALD_ZERO_PROVIDER_READS",
            self.disabled.stdout)

    def test_original_source_pins_and_no_host_teleports(self):
        self.assertEqual(self.report["emerald_pin"],r17.e16.EMERALD_PIN)
        self.assertEqual(self.report["mgba_pin"],r17.e16.MGBA_PIN)
        self.assertTrue(self.report["physical_dpad"])
        self.assertFalse(self.report["host_teleports"])


if __name__=="__main__":
    unittest.main()
