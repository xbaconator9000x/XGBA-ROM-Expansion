"""R17 actual Pokémon Emerald Littleroot map + full secondary tileset external.

Unlike the R16 boot-only bridge, this compiles and runs original Emerald's
NewGameInitData, gMapLayouts, field camera, collision map and CB2_Overworld.
Original Littleroot 20x20 map grid, border and Petalburg secondary tileset
graphics/palettes/metatiles/attributes are zeroed from the executable ROM.
The real GBA game reobtains the original bytes from validated >32MiB sidecar,
copies native tiles into BG VRAM and processes actual D-pad controller input.
"""
from __future__ import annotations

import hashlib,json,os,re,shutil,struct,sys,tempfile,unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"tests"),str(ROOT/"integration/mgba")]
import test_xgba_r7_mgba_core as r7
import test_xgba_r14_external_tilesets as r14
import xgba_r16_emerald_decomp_patch as e16
import xgba_r17_emerald_patch as patch
from xgba_r17_emerald_heap import patch_emerald_heap_tail
from xgba_memory_plan import Resource,Phase,plan_residency
import xgba_resource_sidecar as sidecar
import xgba_resource_integration_smoke as r6
import xgba_mgba_run as launcher
import apply_core_patch

EMERALD=ROOT/"upstream/pokeemerald"
MGBA=ROOT/"upstream/mgba"
LAYOUT="LittlerootTown"
TILESET="Petalburg"
RID="emerald.littleroot"
BOOT="emerald.bridge"

def sha(data):return hashlib.sha256(data).hexdigest()

class ActualEmeraldLittlerootExternalMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for checkout,pin in ((EMERALD,e16.EMERALD_PIN),(MGBA,e16.MGBA_PIN)):
            actual=r7.run(["git","-C",checkout,"rev-parse","HEAD"]).stdout.strip()
            if actual!=pin:raise AssertionError(f"Refusing unpinned source {checkout}: {actual}")
        cls.contract=e16.verify_source_contract(EMERALD)
        cls.temp=tempfile.TemporaryDirectory(prefix="xgba-r17-native-emerald-")
        cls.addClassCleanup(cls.temp.cleanup)
        root=Path(cls.temp.name)
        rom=EMERALD/"pokeemerald_modern.gba"
        elf=EMERALD/"pokeemerald_modern.elf"
        def build():
            r7.run(["make","-C",EMERALD,"-j2","MODERN=1"],timeout=2700)

        # Original untouched upstream build identifies exact source assets.
        build()
        orig_rom=rom.read_bytes()
        native_symbols=r14.symbols(elf)
        layout=EMERALD/"data/layouts"/LAYOUT
        grid=(layout/"map.bin").read_bytes()
        border=(layout/"border.bin").read_bytes()
        if len(grid)!=20*20*2 or len(border)!=8:
            raise AssertionError("Pinned genuine Emerald Littleroot map geometry drift")
        parts=r14.tileset_parts(orig_rom,native_symbols,TILESET)
        cls.pack=r14.pack((grid,border),parts)
        cls.resource_bytes=len(cls.pack)
        r19=bool(getattr(cls,"R19_CONNECTED",False))
        if r19:
            route_layout=EMERALD/"data/layouts/Route101"
            cls.route_grid=(route_layout/"map.bin").read_bytes()
            cls.route_border=(route_layout/"border.bin").read_bytes()
            if len(cls.route_grid)!=800 or len(cls.route_border)!=8:
                raise AssertionError("Pinned original Route 101 external geometry drift")
            cls.route_pack=r14.pack((cls.route_grid,cls.route_border),parts)
            cls.route_pack_offset=(cls.resource_bytes+3)&~3
            if cls.route_pack_offset+len(cls.route_pack)>16384:
                raise AssertionError("Two simultaneous full maps exceed current Emerald 16KiB live arena")
        if cls.resource_bytes>16384:
            raise AssertionError("Emerald original full tileset exceeds one synchronous 16 KiB XGBA read; must implement chunking, never drop assets")
        if r19:
            budget=plan_residency(
                [Resource("emerald_littleroot_pack",len(cls.pack)),
                 Resource("emerald_route101_pack",len(cls.route_pack))],
                [Phase("original_emerald_connected_maps",
                       ("emerald_littleroot_pack","emerald_route101_pack"),
                       transient_heap_bytes=12288)],
                symbol_prefix="gXgbaR17")
        else:
            budget=plan_residency(
                [Resource("emerald_littleroot_pack",len(cls.pack))],
                [Phase("original_emerald_overworld",("emerald_littleroot_pack",),
                       transient_heap_bytes=12288)],
                symbol_prefix="gXgbaR17")
        config=root/"r17-config.h"
        config.write_text(
            f"#define XGBA_R17_PACK_SIZE {len(cls.pack)}u\n"
            f"#define XGBA_R17_RESERVE {budget.reserve_bytes}u\n")
        r18=bool(getattr(cls,"R18_SAVE_TEST",False))
        if r18:
            config.write_text(config.read_text()+"\n#define XGBA_R18_SAVE_TEST 1\n")
        if r19:
            config.write_text(config.read_text()+
                "\n#define XGBA_R19_CONNECTED_MAPS 1\n"
                f"#define XGBA_R19_LITTLEROOT_BYTES {len(cls.pack)}u\n"
                f"#define XGBA_R19_ROUTE_BYTES {len(cls.route_pack)}u\n"
                f"#define XGBA_R19_ROUTE_OFFSET {cls.route_pack_offset}u\n"
                f"#define XGBA_R19_RESERVE {budget.reserve_bytes}u\n")

        # Instrument original decomp and patch engine resets/actual linker
        # without overwriting or re-implementing its maps or tileset renderer.
        originals={}
        try:
            originals=patch.patch_emerald_littleroot_sources(EMERALD,config,r18_save=r18,r19_connected=r19)
            originals.update(patch_emerald_heap_tail(EMERALD,
                reserve_bytes=budget.reserve_bytes,replace_once=e16.one))
            build()
        finally:
            e16.restore_sources(originals)
        syms=r14.symbols(elf)
        real_arena,real_end=budget.verify_linker({k:v[0] for k,v in syms.items()})
        if real_end>0x02040000 or not 0x02000000<=real_arena<0x02040000:
            raise AssertionError("Native Emerald map arena violates physical EWRAM")
        cls.probe=syms["gXgbaR17Proof"][0]
        if not 0x02000000<=cls.probe<0x02040000:
            raise AssertionError("R17 emitted guest proof is not native Emerald EWRAM")

        stripped=bytearray(rom.read_bytes())
        removed=[]
        matches=[m.start() for m in re.finditer(re.escape(grid),stripped)]
        if len(matches)!=1:raise AssertionError("Expected original compiled Littleroot map exactly once")
        m=matches[0]
        stripped[m:m+len(grid)]=bytes(len(grid))
        removed.append({"asset":"LittlerootTown.map","bytes":len(grid),"offset":m,"sha256":sha(grid)})
        address,size=syms["LittlerootTown_Layout"]
        border_addr=struct.unpack_from("<I",stripped,address-0x08000000+8)[0]
        b=border_addr-0x08000000
        if stripped[b:b+8]!=border:
            raise AssertionError("Original Emerald layout border pointer does not match source")
        stripped[b:b+8]=bytes(8)
        removed.append({"asset":"LittlerootTown.border","bytes":len(border),"offset":b,"sha256":sha(border)})
        if r19:
            # Source-backed native Route101, still sharing Petalburg graphics:
            # both grid/border packs must coexist during connected camera pan.
            route_matches=[m.start() for m in re.finditer(re.escape(cls.route_grid),stripped)]
            if len(route_matches)!=1:
                raise AssertionError("Original compiled Route101 grid not uniquely identifiable")
            rm=route_matches[0]
            stripped[rm:rm+len(cls.route_grid)]=bytes(len(cls.route_grid))
            removed.append({"asset":"Route101.map","bytes":len(cls.route_grid),
                            "offset":rm,"sha256":sha(cls.route_grid)})
            route_address,_=syms["Route101_Layout"]
            route_border_addr=struct.unpack_from("<I",stripped,
                                                 route_address-0x08000000+8)[0]
            rb=route_border_addr-0x08000000
            if stripped[rb:rb+8]!=cls.route_border:
                raise AssertionError("Route101 original border pointer/bytes drift")
            stripped[rb:rb+8]=bytes(8)
            removed.append({"asset":"Route101.border","bytes":8,"offset":rb,
                            "sha256":sha(cls.route_border)})
        for symbol,blob in parts:
            address,size=syms[symbol]
            off=address-0x08000000
            if size!=len(blob) or stripped[off:off+size]!=blob:
                raise AssertionError("Compiled original Emerald tileset symbol drift "+symbol)
            stripped[off:off+size]=bytes(size)
            removed.append({"asset":symbol,"bytes":size,"offset":off,"sha256":sha(blob)})
        if len(stripped)>32*1024*1024 or grid in stripped or (r19 and cls.route_grid in stripped):
            raise AssertionError("Original Emerald map still embedded or ROM window exceeded")
        rom.write_bytes(stripped)
        cls.rom_sha=sha(stripped)
        cls.removed=removed
        apply_core_patch.apply(MGBA)
        native=root/"mgba-build"
        r7.run(["cmake","-S",ROOT/"integration/mgba","-B",native,
                "-DCMAKE_BUILD_TYPE=Release","-DXGBA_MGBA_CHECKOUT="+str(MGBA)],timeout=240)
        r7.run(["cmake","--build",native,"--target","xgba-mgba-headless",
                "--parallel","2"],timeout=1100)
        exe=native/"xgba-mgba-headless"
        if not exe.is_file():raise AssertionError("Native patched mGBA absent")
        cls.offset=32*1024*1024+8192
        boot_offset=32*1024*1024+32768
        data=root/"extracted-assets.bin"
        with data.open("wb") as fp:
            fp.seek(cls.offset);fp.write(cls.pack)
            fp.seek(boot_offset);fp.write(r6.PAYLOAD)
            if r19:
                cls.route_offset=32*1024*1024+65536
                fp.seek(cls.route_offset);fp.write(cls.route_pack)
        manifest=root/"manifest.json"
        manifest.write_text(json.dumps({
            "format":sidecar.FORMAT,"version":sidecar.VERSION,
            "source_identity":{"id":"pokeemerald-r17-native-map","sha256":cls.rom_sha},
            "data_file":data.name,
            "resources":[
                {"id":RID,"offset":cls.offset,"length":len(cls.pack),"sha256":sha(cls.pack)},
                {"id":BOOT,"offset":boot_offset,"length":64,"sha256":sha(r6.PAYLOAD)}
            ]+([{"id":"emerald.route101","offset":cls.route_offset,
                 "length":len(cls.route_pack),"sha256":sha(cls.route_pack)}] if r19 else [])
        }))
        cls.rom=rom;cls.elf=elf;cls.executable=exe
        cls.manifest_path=manifest
        cls.native_root=root
        cls.output=root/"littleroot-lcd";cls.output.mkdir()
        if r18:
            cls.save_probe=syms["gXgbaR18Proof"][0]
            if not 0x02000000<=cls.save_probe<0x02040000:
                raise AssertionError("R18 native game Flash proof not in EWRAM")
            return
        if r19:
            cls.r19_probe=syms["gXgbaR19MapProof"][0]
            if not 0x02000000<=cls.r19_probe<0x02040000:
                raise AssertionError("R19 actual connected-map proof not in Emerald EWRAM")
            cls.simultaneous_bytes=budget.reserve_bytes
            cls.real_arena=real_arena
            return
        result=launcher.launch(rom,manifest,RID,
            emulator=exe,frames=2700,probe_address=cls.probe,
            second_resource_id=BOOT,r17_emerald_map_dir=cls.output)
        cls.log=result.stdout
        if "PASS_R17_REAL_EMERALD_EXTERNAL_MAP_AND_SECONDARY_TILESET" not in cls.log:
            raise AssertionError("Real original Emerald map/tileset callback absent")
        cls.disabled_dir=root/"disabled";cls.disabled_dir.mkdir()
        disabled=launcher.launch(rom,manifest,RID,
            emulator=exe,frames=1500,probe_address=cls.probe,
            second_resource_id=BOOT,r17_emerald_map_dir=cls.disabled_dir,disabled=True)
        cls.disabled_log=disabled.stdout
        if "PASS_R17_DISABLED_EMERALD_MAP_FAIL_CLOSED" not in cls.disabled_log:
            raise AssertionError("Disabled native Emerald did not refuse missing map pack")

        cls.report={
            "milestone":"R17_SOURCE_BUILT_EMERALD_NATIVE_EXTERNAL_LITTLEROOT",
            "actual_game":"pret/pokeemerald MODERN=1",
            "emerald_pin":e16.EMERALD_PIN,"mgba_pin":e16.MGBA_PIN,
            "original_emerald_map":"LittlerootTown group 0 map 9",
            "secondary_tileset":"Petalburg",
            "rom_sha256":cls.rom_sha,
            "native_ewram_arena":hex(real_arena),
            "arena_reserved_bytes":budget.reserve_bytes,
            "native_ewram_linker_end":hex(real_end),
            "original_rom_assets_zeroed":removed,
            "original_full_littleroot_grid_not_in_rom":True,
            "external_offset":cls.offset,
            "external_bytes":cls.resource_bytes,
            "external_pack_sha256":sha(cls.pack),
            "native_memory_vram_and_grid_verified":True,
            "physical_dpad":True,
            "enabled_log":cls.log,"disabled_log":cls.disabled_log,
            "scope":"Real Emerald map geometry/border and full secondary tileset stripped and externally supplied; original CB2_NewGame, native field map, collision, tile renderer and controller. Title and truck intro bypassed in test-only fixture. One external map, not general map transitions or Emerald save/reboot."
        }
        output=os.getenv("XGBA_R17_EVIDENCE_DIR")
        if output:
            dest=Path(output);dest.mkdir(parents=True,exist_ok=True)
            for path in cls.output.glob("*.png"):
                shutil.copy2(path,dest/path.name)
            (dest/"proof.json").write_text(json.dumps(cls.report,indent=2,sort_keys=True))

    def test_original_game_loaded_source_stripped_external_littleroot(self):
        self.assertIn("map=0:9 native_grid=1",self.log)
        self.assertEqual(len(self.removed),6)
    def test_original_emerald_bg_vram_and_tileset_are_external(self):
        self.assertIn("native_bg_vram=1",self.log)
        self.assertGreater(self.resource_bytes,800)
    def test_real_dpad_changes_original_player_coords(self):
        self.assertIn("physical_dpad=1",self.log)
    def test_disable_is_fail_closed_without_any_host_read(self):
        self.assertIn("host_reads=0",self.disabled_log)
    def test_native_gba_240x160_lcd_screenshots(self):
        files=sorted(self.output.glob("*.png"))
        self.assertEqual(len(files),2)
        for file in files:
            with Image.open(file) as im:
                self.assertEqual(im.size,(240,160))
                self.assertGreater(len(set(im.convert("RGB").getdata())),8)
    def test_actual_linker_budget_and_source_identity(self):
        self.assertTrue(self.probe>=0x02000000)
        self.assertGreater(self.offset,32*1024*1024)
        self.assertLessEqual(self.resource_bytes,16384)
        self.assertTrue(self.rom_sha)

if __name__=="__main__":
    unittest.main()
