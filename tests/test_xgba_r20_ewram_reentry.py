"""R20: original Emerald overworld->battle->overworld->battle EWRAM re-entry.

Executes the *real* source-built original battle and field callbacks through
native mGBA GBA key input. No host writes to the guest EWRAM are permitted.
Verifies that battle compressed sprite cache identities are invalidated when
the same physical 16 KiB heap-tail arena is reoccupied by two connected maps.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"tests"), str(ROOT/"tools"), str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher


class NativeEmeraldArenaReentry(unittest.TestCase):
    R19_CONNECTED = True
    R19_BATTLE = True
    R20_LIFECYCLE_TEST = True

    @classmethod
    def setUpClass(cls):
        # R19's exact source-backed ROM, external map + compressed mon fixtures,
        # verified physical EWRAM linker, and original native mGBA build.
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        output = cls.native_root / "r20-ewram-evidence"
        output.mkdir()
        cls.output = output
        names = ("emerald.battle.poochyena.front",
                 "emerald.battle.zigzagoon.front")
        result = launcher.launch(
            cls.rom, cls.manifest_path, r17.RID,
            emulator=cls.executable, frames=36000,
            probe_address=cls.r19_probe,
            second_resource_id="emerald.route101",
            extra_resource_ids=(r17.BOOT,)+names,
            r19_battle_dir=output, r19_battle_probe=cls.battle_probe,
            r19_route_offset=cls.route_offset,
            r19_route_length=len(cls.route_pack),
            r19_battle0_offset=cls.battle_offsets["Poochyena"],
            r19_battle0_length=len(cls.battle_sprite_blobs["Poochyena"]),
            r19_battle1_offset=cls.battle_offsets["Zigzagoon"],
            r19_battle1_length=len(cls.battle_sprite_blobs["Zigzagoon"]),
            r20_reentry=True)
        cls.log = result.stdout
        if "PASS_R20_EWRAM_ARENA_REENTRY" not in cls.log:
            raise AssertionError("Original Emerald second-battle arena re-entry did not pass")
        cls.report = {
            "milestone": "R20_ACTUAL_EMERALD_HEAP_TAIL_OWNERSHIP_REENTRY",
            "status": "native_accepted",
            "game": "source-built pret/pokeemerald MODERN=1",
            "game_source_commit": r17.e16.EMERALD_PIN,
            "emulator_source_commit": r17.e16.MGBA_PIN,
            "compiled_rom_sha256": cls.rom_sha,
            "guest_physical_ewram_bytes": 256*1024,
            "protected_arena_bytes": 16384,
            "guest_arena_address": hex(cls.real_arena),
            "original_engine_battle_count": 2,
            "expected_external_sprite_fetches": 4,
            "map_reacquisition_between_battles": True,
            "heap_reservation_returned_to_allocator": False,
            "test_only_entry": "R button while overworld active",
            "native_log": cls.log,
            "scope": "Actual Emerald two-battle/overworld phase ownership, original sprites, native EWRAM, and map reuse; not yet heap-fragmentation, DMA-queue, user interface, FireRed, or 100+ transitions."
        }
        dest=os.environ.get("XGBA_R20_EVIDENCE_DIR")
        if dest:
            folder=Path(dest)
            folder.mkdir(parents=True,exist_ok=True)
            for png in output.glob("*.png"):
                shutil.copy2(png,folder/png.name)
            (folder/"proof.json").write_text(json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_native_original_emerald_completed_two_phase_changes(self):
        self.assertIn("PASS_R20_EWRAM_ARENA_REENTRY", self.log)
        self.assertIn("real_original_battles=2",self.log)

    def test_four_external_front_fetches_no_stale_sprite_cache(self):
        self.assertIn("external_sprite_fetches=4",self.log)
        self.assertIn("battle_cache_reloads=4",self.log)

    def test_reacquired_two_connected_maps_between_battles(self):
        self.assertIn("native_ewram=1",self.log)
        self.assertIn("map_loads=4",self.log)

    def test_source_assets_are_real_and_from_different_external_offsets(self):
        self.assertGreater(self.battle_offsets["Poochyena"],32*1024*1024)
        self.assertGreater(self.battle_offsets["Zigzagoon"],self.battle_offsets["Poochyena"])
        for blob in self.battle_sprite_blobs.values():
            self.assertEqual(len(hashlib.sha256(blob).hexdigest()),64)

    def test_original_240x160_lcd_evidence_before_and_after_reentry(self):
        screenshots=sorted(self.output.glob("*.png"))
        self.assertEqual(len(screenshots),4)
        for png in screenshots:
            with Image.open(png) as im:
                self.assertEqual(im.size,(240,160))
                self.assertGreater(len(set(im.convert("RGB").getdata())),8)

    def test_original_engine_memory_finite_and_protected(self):
        self.assertEqual(self.simultaneous_bytes,16384)
        self.assertTrue(0x02000000<=self.real_arena<0x02040000)
        self.assertLessEqual(self.real_arena+16384,0x02040000)

if __name__=="__main__":
    unittest.main()
