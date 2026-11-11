"""R19: real Pokemon Emerald camera crosses between two fully external maps.

Original Littleroot and Route101 grid/borders are removed from the compiled
ROM, both independently hash-verified in simultaneously resident EWRAM, while
the shared original Petalburg secondary tile graphics are stripped from ROM.
mGBA executes the original Emerald field camera, controller and BG renderer.
"""
from __future__ import annotations
import hashlib,json,os,shutil,sys,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher

class NativeEmeraldConnectedExternalMaps(unittest.TestCase):
    R19_CONNECTED=True
    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        output=cls.native_root/"r19-evidence"
        output.mkdir()
        cls.out=output
        launch=lambda disabled=False: launcher.launch(
            cls.rom,cls.manifest_path,r17.RID,
            emulator=cls.executable,frames=3100,
            probe_address=cls.r19_probe,
            second_resource_id="emerald.route101",
            r19_connected_dir=output,
            r19_route_offset=cls.route_offset,
            r19_route_length=len(cls.route_pack),
            disabled=disabled)
        cls.enabled=launch()
        if "PASS_R19_REAL_EMERALD_CONNECTED_DPAD" not in cls.enabled.stdout:
            raise AssertionError("Original Emerald native connected-map movement did not pass")
        cls.disabled=launch(True)
        if "PASS_R19_DISABLED_CONNECTED_MAPS_ZERO_READS" not in cls.disabled.stdout:
            raise AssertionError("Native XGBA-disabled connected-map refusal not verified")
        cls.report={
            "milestone":"R19_EMERALD_CONNECTED_MAPS_TWO_SIMULTANEOUS_EXTERNAL_PACKS",
            "engine":"pret/pokeemerald MODERN=1",
            "emerald_source_commit":r17.e16.EMERALD_PIN,
            "native_mgba_commit":r17.e16.MGBA_PIN,
            "compiled_source_rom_sha256":cls.rom_sha,
            "map_sequence":"Littleroot Town (0:9) -> Route 101 (0:16) -> Littleroot (0:9)",
            "external_resources":[
                {"id":r17.RID,"logical_offset":cls.offset,
                 "sha256":hashlib.sha256(cls.pack).hexdigest(),
                 "guest_resident_bytes":len(cls.pack)},
                {"id":"emerald.route101","logical_offset":cls.route_offset,
                 "sha256":hashlib.sha256(cls.route_pack).hexdigest(),
                 "guest_resident_bytes":len(cls.route_pack)}],
            "real_guest_ewram_simultaneous_arena_bytes":cls.simultaneous_bytes,
            "native_linker_audited_guest_start":hex(cls.real_arena),
            "original_asset_ranges_removed_from_rom":cls.removed,
            "real_gba_camera_connected_transition":True,
            "original_emerald_player_dpad":True,
            "real_native_ewram_and_bg_vram_verified":True,
            "disabled_fail_closed_no_provider_reads":True,
            "native_enabled_log":cls.enabled.stdout,
            "native_disabled_log":cls.disabled.stdout,
            "scope":"Two source-backed original Emerald connected maps and shared secondary tileset with simultaneous residency; does not prove external battle sprite, multi-file packs, Emerald GUI save or generic arbitrary-map system."
        }
        path=os.environ.get("XGBA_R19_EVIDENCE_DIR")
        if path:
            dest=Path(path);dest.mkdir(parents=True,exist_ok=True)
            for shot in output.glob("*.png"):
                shutil.copy2(shot,dest/shot.name)
            (dest/"proof.json").write_text(json.dumps(cls.report,indent=2,sort_keys=True)+"\n")
    def test_two_original_rom_maps_and_secondary_assets_stripped(self):
        names=[v["asset"] for v in self.removed]
        self.assertIn("Route101.map",names)
        self.assertIn("Route101.border",names)
        self.assertIn("LittlerootTown.map",names)
        self.assertEqual(len(self.removed),8)
    def test_simultaneously_resident_guest_memory_is_audited(self):
        self.assertLessEqual(self.simultaneous_bytes,16384)
        self.assertGreaterEqual(self.simultaneous_bytes,len(self.pack)+len(self.route_pack))
        self.assertIn("concurrent_packs=2",self.enabled.stdout)
    def test_real_gba_dpad_littleroot_route101_and_return(self):
        self.assertIn("map_sequence=9,16,9",self.enabled.stdout)
        self.assertIn("transitions=2",self.enabled.stdout)
    def test_actual_ewram_map_grid_and_decompressed_bg_vram(self):
        self.assertIn("native_bg_vram=1 native_map_grid=1",self.enabled.stdout)
    def test_native_disabled_mode_fails_closed_without_reads(self):
        self.assertIn("PASS_R19_DISABLED_CONNECTED_MAPS_ZERO_READS",self.disabled.stdout)
    def test_three_native_original_emerald_lcd_frames(self):
        shots=sorted(self.out.glob("*.png"))
        self.assertEqual(len(shots),3)
        for shot in shots:
            with Image.open(shot) as image:
                self.assertEqual(image.size,(240,160))
                self.assertGreater(len(set(image.convert("RGB").getdata())),8)

if __name__=="__main__":
    unittest.main()
