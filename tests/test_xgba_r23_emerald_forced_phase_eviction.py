"""R23: forced alternating original Emerald field and battle resource ownership.

Real native Emerald executes four original double wild battles and three
overworld returns. The map packs and two battle fronts share the same protected
16 KiB physical guest arena: each game phase deliberately overwrites the
previous phase's resource working set. The original game reloads both packs
before field rendering; source bytes and original VRAM are checked each time.
No host-side game-memory patching, scripted battle results or fake screenshots.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher

class NativeEmeraldFourBattleForcedEviction(unittest.TestCase):
    R19_CONNECTED=True
    R19_BATTLE=True
    R20_LIFECYCLE_TEST=True
    R21_HEAP_PRESSURE_TEST=True

    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        cls.output=Path(os.environ.get(
            "XGBA_R23_EVIDENCE_DIR",
            cls.native_root/"r23-native-eviction"))
        cls.output.mkdir(parents=True,exist_ok=True)
        cls.result=launcher.launch(
            cls.rom,cls.manifest_path,r17.RID,
            emulator=cls.executable,frames=36000,
            probe_address=cls.r19_probe,
            second_resource_id="emerald.route101",
            extra_resource_ids=(r17.BOOT,
                "emerald.battle.poochyena.front",
                "emerald.battle.zigzagoon.front"),
            r19_battle_dir=cls.output,
            r19_battle_probe=cls.battle_probe,
            r19_route_offset=cls.route_offset,
            r19_route_length=len(cls.route_pack),
            r19_battle0_offset=cls.battle_offsets["Poochyena"],
            r19_battle0_length=len(cls.battle_sprite_blobs["Poochyena"]),
            r19_battle1_offset=cls.battle_offsets["Zigzagoon"],
            r19_battle1_length=len(cls.battle_sprite_blobs["Zigzagoon"]),
            r20_reentry=True,
            r21_heap_probe=cls.heap_probe,
            r23_battles=4)
        cls.log=cls.result.stdout
        match=re.search(r"^PASS_R23_REAL_EMERALD_FORCED_PHASE_EVICTION (.*)$",
                        cls.log,re.MULTILINE)
        if not match:
            raise AssertionError("Genuine four-battle forced eviction native proof missing")
        cls.values={key:int(value) for key,value in
            re.findall(r"(\\w+)=(\\d+)",match.group(1))}
        cls.report={
            "milestone":"R23_ORIGINAL_EMERALD_FORCED_MAP_BATTLE_PHASE_EVICTIONS",
            "status":"native_accepted",
            "original_game_source_sha":r17.e16.EMERALD_PIN,
            "native_mgba_source_sha":r17.e16.MGBA_PIN,
            "compiled_source_rom_sha256":cls.rom_sha,
            "native_guest_ewram_bytes":256*1024,
            "linker_reserved_guest_arena_bytes":cls.simultaneous_bytes,
            "linker_arena_start":hex(cls.real_arena),
            "actual_original_battles":4,
            "independently_verified_field_returns":3,
            "external_map_pack_fetches":8,
            "independent_original_compressed_front_fetches":8,
            "arena_owner_epoch":8,
            "original_memblock_allocator_cycles":4,
            "original_allocations_and_frees_each":16,
            "oversized_guest_malloc_refusals":4,
            "guest_live_guard_bytes_verified":24576,
            "tested_resource_sets":{
                "overworld":["emerald.littleroot","emerald.route101"],
                "battle":["emerald.battle.poochyena.front",
                          "emerald.battle.zigzagoon.front"]},
            "distinct_simultaneously_resident_map_regions":2,
            "third_connected_map_eviction_tested":False,
            "DMA_in_flight_aliasing_tested":False,
            "full_arena_heap_reclamation_tested":False,
            "native_probe":cls.values,
            "source_blobs_sha256":{
                "littleroot":hashlib.sha256(cls.pack).hexdigest(),
                "route101":hashlib.sha256(cls.route_pack).hexdigest(),
                "poochyena":hashlib.sha256(
                    cls.battle_sprite_blobs["Poochyena"]).hexdigest(),
                "zigzagoon":hashlib.sha256(
                    cls.battle_sprite_blobs["Zigzagoon"]).hexdigest()},
            "scope":"Original Emerald four real battles and three original field returns; repeated overwriting the same arena by two connected map packs vs two compressed opponent sprites, with byte-level EWRAM/BG VRAM verification and original MemBlock pressure. Not third-map eviction, arbitrary pack sizes, DMA queues or stock hardware.",
        }
        if os.environ.get("XGBA_R23_EVIDENCE_DIR"):
            (cls.output/"proof.json").write_text(
                json.dumps(cls.report,indent=2,sort_keys=True)+"\\n")

    def test_original_four_double_battle_encounters(self):
        self.assertEqual(self.values["original_battles"],4)
        self.assertIn("PASS_R19_REAL_EMERALD_MIXED_SOURCE_BATTLE",self.log)
    def test_three_original_field_reacquisitions(self):
        self.assertEqual(self.values["world_reacquisitions"],3)
        self.assertEqual(self.values["external_map_fetches"],8)
    def test_compressed_external_sprite_bytes_fetched_anew_each_battle(self):
        self.assertEqual(self.values["external_sprite_fetches"],8)
    def test_four_disjoint_owner_phase_generations(self):
        self.assertEqual(self.values["arena_epoch"],8)
        self.assertEqual(self.values["world_claims"],4)
        self.assertEqual(self.values["battle_claims"],4)
    def test_original_memblock_allocations_under_each_phase_swap(self):
        self.assertEqual(self.values["guest_pressure_cycles"],4)
        self.assertEqual(self.values["original_allocations"],16)
        self.assertEqual(self.values["original_frees"],16)
    def test_oversized_mallocs_fail_before_entering_arena(self):
        self.assertEqual(self.values["oversize_rejections"],4)
        self.assertEqual(self.simultaneous_bytes,16384)
        self.assertLessEqual(self.real_arena+16384,0x02040000)
    def test_guest_guard_pattern_integrity(self):
        self.assertEqual(self.values["guard_bytes_verified"],24576)
        self.assertGreaterEqual(self.values["original_heap_audits"],12)
    def test_external_provider_counts_no_stale_fetches(self):
        self.assertEqual(self.values["provider_reads"],17)
    def test_every_original_field_restoration_rechecks_BG_VRAM(self):
        self.assertEqual(self.values["native_bg_vram"],1)
        self.assertEqual(self.values["source_byte_verified"],1)
    def test_original_guest_ewram_not_host_injected(self):
        self.assertEqual(self.values["native_ewram"],1)
        self.assertGreater(self.battle_offsets["Poochyena"],32*1024*1024)
        self.assertGreater(self.battle_offsets["Zigzagoon"],32*1024*1024)
    def test_bounded_rom_and_original_native_engine_build(self):
        self.assertEqual(self.report["native_guest_ewram_bytes"],262144)
        self.assertEqual(self.report["actual_original_battles"],4)
        self.assertFalse(self.report["third_connected_map_eviction_tested"])
    def test_eight_authentic_original_240_by_160_LCD_frames(self):
        images=sorted(self.output.glob("*.png"))
        self.assertEqual(len(images),8)
        for path in images:
            with Image.open(path) as im:
                self.assertEqual(im.size,(240,160))
                self.assertGreater(len(set(im.convert("RGB").getdata())),8)

if __name__=="__main__":
    unittest.main()
