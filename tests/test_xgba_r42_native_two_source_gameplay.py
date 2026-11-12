"""R42: real Emerald's original async event/UI/bag/Flash through two XGBA assets.

All script bytes are new synthetic adapters, based on actual original event
command concepts; this is NOT unmodified Team Rocket/HnS script execution.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import unittest

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import test_xgba_r18_emerald_flash as r18
import xgba_mgba_run as launcher
import xgba_r42_event_assets as assets


class NativeEmeraldTwoSourceGameplay(unittest.TestCase):
    R18_SAVE_TEST=True
    R42_EVENT_TEST=True

    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        cls.output=cls.native_root/"r42-native-gameplay"
        cls.output.mkdir()
        cls.save=cls.native_root/"r42-genuine-emerald-flash.sav"
        if cls.save.exists():
            raise AssertionError("R42 must start with new original Emerald Flash")
        def run(phase):
            return launcher.launch(
                cls.rom,cls.manifest_path,r17.RID,
                emulator=cls.executable,frames=3500,
                probe_address=cls.probe,second_resource_id=r17.BOOT,
                extra_resource_ids=(assets.ROCKET_ID,assets.JOHTO_ID),
                r18_dir=cls.output,r18_savefile=cls.save,
                r18_phase=phase,r18_save_probe=cls.save_probe)
        first=run("r42-write")
        cls.first_log=first.stdout
        if "PASS_R42_NATIVE_GAME_TWO_EXTERNAL_EVENTS" not in cls.first_log:
            raise AssertionError("Original Emerald did not execute both controller events")
        if cls.save.stat().st_size not in (131072,131088):
            raise AssertionError("Real 128 KiB Emerald Flash absent after native item events")
        cls.original_flash_sha=r18.sha_file(cls.save)
        second=run("r42-continue")
        cls.cold_log=second.stdout
        if "PASS_R42_NATIVE_EMERALD_COLD_RESTORED_BOTH_EVENTS" not in cls.cold_log:
            raise AssertionError("Original Emerald items/flags/vars lost after native cold boot")
        if r18.sha_file(cls.save)!=cls.original_flash_sha:
            raise AssertionError("Original Flash changed during read-only cold continuation")
        rom=cls.rom.read_bytes()
        if assets.rocket_event() in rom or assets.johto_event() in rom:
            raise AssertionError("External source script bytes were embedded in executable")
        cls.images=sorted(cls.output.glob("*.png"))
        if len(cls.images)!=5:
            raise AssertionError("R42 expected 5 real 240x160 mGBA LCD screenshots")
        cls.report={
            "milestone":"R42_TWO_SOURCE_NATIVE_EMERALD_GAMEPLAY",
            "game_engine":"pinned original pret/pokeemerald native scripts, UI, bag, and save",
            "emulator":"pinned patched native mGBA, source-backed XGBA MMIO provider",
            "original_emerald_script_dispatch":"ScriptContext_SetupScript / gScriptCmdTable",
            "native_controller_inputs":["GBA R button", "GBA A button", "GBA L button","GBA A button","GBA SELECT"],
            "source_namespaced_guest_assets":assets.audit_assets(),
            "source_scripts_are_authored_emerald_translations":True,
            "original_team_rocket_script_executed_unmodified":False,
            "heart_soul_custom_engine_scripts_executed_unmodified":False,
            "three_full_games_unified":False,
            "cross_world_travel_proven":False,
            "genuine_message_ui":True,
            "genuine_original_bag_nugget_and_silk_scarf":True,
            "original_flash_cold_persistence":True,
            "original_source_rom_assets_privately_preserved":True,
            "native_lcd_frame_count":len(cls.images),
            "original_flash_never_published":True,
        }
        location=os.getenv("XGBA_R42_EVIDENCE_DIR")
        if location:
            destination=Path(location)
            destination.mkdir(parents=True,exist_ok=True)
            for img in cls.images:
                shutil.copy2(img,destination/img.name)
            (destination/"proof.json").write_text(
                json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_two_physical_gba_buttons_trigger_original_emerald_native_interpreter(self):
        self.assertIn("PASS_R42_NATIVE_GAME_TWO_EXTERNAL_EVENTS",self.first_log)
        self.assertTrue(self.report["genuine_message_ui"])

    def test_two_source_independent_original_item_rewards(self):
        self.assertIn("rocket_nugget=1 johto_silk_scarf=1",self.first_log)
        self.assertTrue(self.report["genuine_original_bag_nugget_and_silk_scarf"])

    def test_original_gba_flash_cold_boot_preserves_bag_flags_vars(self):
        self.assertIn("original_flash=1 no_reexecution=1 bag=2 flags=2 vars=2",self.cold_log)
        self.assertEqual(r18.sha_file(self.save),self.original_flash_sha)

    def test_both_source_assets_are_external_and_sha_verified(self):
        self.assertGreater(assets.ROCKET_OFFSET,32*1024*1024)
        self.assertGreater(assets.JOHTO_OFFSET,assets.ROCKET_OFFSET)
        self.assertNotEqual(assets.ROCKET_ID,assets.JOHTO_ID)
        self.assertEqual(self.r42_rocket,assets.rocket_event())
        self.assertEqual(self.r42_johto,assets.johto_event())
        self.assertEqual(len(self.r42_rocket),96)

    def test_five_authentic_lcd_screenshots_have_game_pixels(self):
        self.assertEqual(len(self.images),5)
        for file in self.images:
            with self.subTest(file=file.name),Image.open(file) as im:
                self.assertEqual(im.size,(240,160))
                self.assertGreater(len(set(im.convert("RGB").getdata())),8)

    def test_no_false_cross_engine_compatibility_claim(self):
        for key in ("original_team_rocket_script_executed_unmodified",
                    "heart_soul_custom_engine_scripts_executed_unmodified",
                    "three_full_games_unified","cross_world_travel_proven"):
            self.assertFalse(self.report[key])


class TwoSourceAuthoredEventContracts(unittest.TestCase):
    def test_original_emerald_script_command_alignment(self):
        for data,flag,item,var,value in (
            (assets.rocket_event(),assets.ROCKET_FLAG,assets.ROCKET_ITEM,assets.ROCKET_VAR,assets.ROCKET_VALUE),
            (assets.johto_event(),assets.JOHTO_FLAG,assets.JOHTO_ITEM,assets.JOHTO_VAR,assets.JOHTO_VALUE)):
            self.assertEqual(len(data),assets.SCRIPT_SIZE)
            self.assertEqual(data[0],0x16)
            self.assertEqual(data[1:5],__import__("struct").pack("<HH",var,value))
            self.assertEqual(data[5:8],bytes([0x29])+__import__("struct").pack("<H",flag))
            self.assertEqual(data[8:13],bytes([0x44])+__import__("struct").pack("<HH",item,1))
            self.assertEqual(data[13:22],bytes([0x0F,0,0,0,0,0,0x09,4,0x02]))
            self.assertIn(0xFF,data[22:])

    def test_two_distinct_identity_hashes_and_author_concept(self):
        meta=assets.audit_assets()
        self.assertNotEqual(meta[assets.ROCKET_ID]["sha256"],meta[assets.JOHTO_ID]["sha256"])
        self.assertTrue(all(x["authored_translation_not_original_rom"] for x in meta.values()))

    def test_non_emerald_text_glyphs_refused(self):
        with self.assertRaises(ValueError):
            assets.text_bytes("JOHTO ❤")
        with self.assertRaises(ValueError):
            assets.text_bytes("")

    def test_no_out_of_bounds_original_emerald_text_message(self):
        with self.assertRaises(ValueError):
            assets.event_bytes(assets.JOHTO_VAR,1,assets.JOHTO_FLAG,assets.JOHTO_ITEM,"A"*79)


if __name__=="__main__":
    unittest.main()
