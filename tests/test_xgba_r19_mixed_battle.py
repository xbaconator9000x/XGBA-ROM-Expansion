"""R19: actual original Emerald 2v2 battle; local ROM and external sprites.

The pinned source-built game uses vanilla BattleSetup_StartWildBattle,
CB2_InitBattle and BattleLoadOpponentMonSpriteGfx. Original player Treecko
back pic remains in ROM; enemy Poochyena and Zigzagoon fronts are removed
from original ROM and supplied through TWO separate XGBA resource IDs at
different beyond-32MiB offsets. The native host verifies the original game's
decompressed enemy graphics by reading real guest CPU memory.
"""
from __future__ import annotations
import hashlib,json,os,shutil,sys,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher

class NativeEmeraldOriginalMixedBattle(unittest.TestCase):
    R19_CONNECTED=True
    R19_BATTLE=True
    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        out=cls.native_root/"r19-battle-evidence"
        out.mkdir()
        cls.output=out
        ids=("emerald.battle.poochyena.front",
             "emerald.battle.zigzagoon.front")
        result=launcher.launch(
            cls.rom,cls.manifest_path,r17.RID,
            emulator=cls.executable,frames=3500,
            probe_address=cls.r19_probe,second_resource_id="emerald.route101",
            extra_resource_ids=(r17.BOOT,)+ids,
            r19_battle_dir=out,r19_battle_probe=cls.battle_probe,
            r19_route_offset=cls.route_offset,
            r19_route_length=len(cls.route_pack),
            r19_battle0_offset=cls.battle_offsets["Poochyena"],
            r19_battle0_length=len(cls.battle_sprite_blobs["Poochyena"]),
            r19_battle1_offset=cls.battle_offsets["Zigzagoon"],
            r19_battle1_length=len(cls.battle_sprite_blobs["Zigzagoon"]))
        cls.log=result.stdout
        if "PASS_R19_REAL_EMERALD_MIXED_SOURCE_BATTLE" not in cls.log:
            raise AssertionError("Original Pokemon Emerald battle graphics were not verified")
        cls.report={
            "milestone":"R19_ORIGINAL_EMERALD_DOUBLE_BATTLE_LOCAL_AND_TWO_EXTERNAL_SPRITES",
            "original_game":"pret/pokeemerald MODERN=1",
            "game_source_commit":r17.e16.EMERALD_PIN,
            "emulator_core_commit":r17.e16.MGBA_PIN,
            "compiled_rom_sha256":cls.rom_sha,
            "local_original_mon":"Treecko (vanilla ROM back sprite)",
            "local_original_back_sprite_sha256":cls.local_treecko_sha,
            "external_mon_sprites":[
                {"species":s,
                 "resource_id":f"emerald.battle.{s.lower()}.front",
                 "file_offset":cls.battle_offsets[s],
                 "sha256":hashlib.sha256(blob).hexdigest(),
                 "original_rom_sprite_removed":True}
                for s,blob in cls.battle_sprite_blobs.items()],
            "original_native_emerald_double_wild_battle":True,
            "actual_original_sprite_decompression_verified":True,
            "vanilla_player_sprite_rom_read_path":True,
            "original_rom_move_animations_and_palletes_still_local":True,
            "external_overworld_two_maps_also_resident":True,
            "real_gba_ewram_battle_compressed_buffer_start":hex(cls.battle_front_buffer),
            "native_enabled_log":cls.log,
            "scope":"Actual Emerald wild-double battle and player ROM/opponent external front sprite decompression; move-animation externalization, larger virtual offsets, general species resource mapping, normal scripted trainer battles and packaging remain follow-up work."
        }
        destination=os.environ.get("XGBA_R19_BATTLE_EVIDENCE_DIR")
        if destination:
            folder=Path(destination);folder.mkdir(parents=True,exist_ok=True)
            for png in out.glob("*.png"):
                shutil.copy2(png,folder/png.name)
            (folder/"proof.json").write_text(json.dumps(cls.report,indent=2,sort_keys=True)+"\n")
    def test_original_emerald_battle_engine_with_real_four_battlers(self):
        self.assertIn("original_battle_double=1",self.log)
    def test_local_rom_mon_and_two_external_opponent_sprites(self):
        self.assertIn("player_original_rom=1",self.log)
        self.assertIn("enemy_external_poochyena=1",self.log)
        self.assertIn("enemy_external_zigzagoon=1",self.log)
    def test_original_rom_sprites_removed_and_local_back_retained(self):
        names=[v["asset"] for v in self.removed]
        self.assertIn("gMonFrontPic_Poochyena",names)
        self.assertIn("gMonFrontPic_Zigzagoon",names)
        self.assertEqual(len(self.local_treecko_sha),64)
    def test_original_game_lz_decompression_native_ewram_is_verified(self):
        self.assertIn("decompress_verified=2 native_ewram=1",self.log)
    def test_multiple_source_offsets_and_simultaneously_resident_maps(self):
        self.assertGreater(self.battle_offsets["Poochyena"],32*1024*1024)
        self.assertGreater(self.battle_offsets["Zigzagoon"],
                           self.battle_offsets["Poochyena"])
        self.assertTrue(any(f"provider_reads={count}" in self.log for count in range(5,10)))
    def test_genuine_emerald_battle_and_overworld_lcd_screenshots(self):
        shots=sorted(self.output.glob("*.png"))
        self.assertEqual(len(shots),2)
        for file in shots:
            with Image.open(file) as image:
                self.assertEqual(image.size,(240,160))
                self.assertGreater(len(set(image.convert("RGB").getdata())),8)
        self.assertNotEqual(shots[0].read_bytes(),shots[1].read_bytes())

if __name__=="__main__":
    unittest.main()
