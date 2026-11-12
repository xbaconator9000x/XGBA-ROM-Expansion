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
from xgba_r27_huge_map_geometry import plan_map, source_tiled_grid
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
        stress=getattr(cls,"R27_MAP_SHAPE",None)
        if stress:
            if bool(getattr(cls,"R19_CONNECTED",False)) or bool(getattr(cls,"R19_BATTLE",False)):
                raise AssertionError("R27 single-map geometry fixture cannot conflate connected-map proofs")
            w,h=stress
            # The unmodified source map is 20x20. Build a synthetic stress
            # grid from its real metatiles; no host-side map memory injection.
            original_pack=r14.pack((grid,border),parts)
            cls.geometry_plan=plan_map(
                w,h,base_pack_without_grid=len(original_pack)-len(grid))
            cls.native_grid=source_tiled_grid(grid,w,h)
        else:
            cls.native_grid=grid
        cls.pack=r14.pack((cls.native_grid,border),parts)
        if stress and len(cls.pack)!=cls.geometry_plan.packed_bytes:
            raise AssertionError("R27 packed payload differs from actual 4-byte aligned assets")
        cls.resource_bytes=len(cls.pack)
        r19=bool(getattr(cls,"R19_CONNECTED",False))
        r19_battle=bool(getattr(cls,"R19_BATTLE",False))
        r28=bool(getattr(cls,"R28_THREE_MAPS",False))
        r26_leases=bool(getattr(cls,"R26_LEASE_TEST",False))
        if r28 and (not r19 or r19_battle or stress):
            raise AssertionError("R28 three-map native fixture is distinct from R27 and battle test modes")
        if r19_battle and not r19:
            raise AssertionError("Real mixed-source battle must preserve connected map residency")
        if r19:
            route_layout=EMERALD/"data/layouts/Route101"
            cls.route_grid=(route_layout/"map.bin").read_bytes()
            cls.route_border=(route_layout/"border.bin").read_bytes()
            if len(cls.route_grid)!=800 or len(cls.route_border)!=8:
                raise AssertionError("Pinned original Route 101 external geometry drift")
            cls.route_pack=r14.pack((cls.route_grid,cls.route_border),parts)
            # R28 uses two fixed 8 KiB physical slots in the actual reserved
            # 16 KiB heap tail, not merely the sum of the packed payloads.
            # Keep R19's historical tightly packed layout unchanged.
            if r28:
                if cls.resource_bytes>8192 or len(cls.route_pack)>8192:
                    raise AssertionError("R28 full source packs exceed their 8 KiB physical slots")
                cls.route_pack_offset=8192
            else:
                cls.route_pack_offset=(cls.resource_bytes+3)&~3
            if cls.route_pack_offset+len(cls.route_pack)>16384:
                raise AssertionError("Two simultaneous full maps exceed current Emerald 16KiB live arena")
            if r28:
                oldale_layout=EMERALD/"data/layouts/OldaleTown"
                cls.oldale_grid=(oldale_layout/"map.bin").read_bytes()
                cls.oldale_border=(oldale_layout/"border.bin").read_bytes()
                if len(cls.oldale_grid)!=800 or len(cls.oldale_border)!=8:
                    raise AssertionError("Pinned original OldaleTown layout drift")
                cls.oldale_pack=r14.pack((cls.oldale_grid,cls.oldale_border),parts)
                if (len(cls.oldale_pack)>8192 or
                    cls.route_pack_offset+len(cls.oldale_pack)>16384 or
                    len(cls.pack)+len(cls.route_pack)+len(cls.oldale_pack)<=16384):
                    raise AssertionError("R28 requires 2 fitting packs but 3 over budget")
        if r19_battle:
            cls.battle_original_compressed={}
            for species_name in ("Poochyena","Zigzagoon"):
                sym="gMonFrontPic_"+species_name
                if sym not in native_symbols:
                    raise AssertionError("Actual original compiled Emerald sprite symbol missing "+sym)
                address,length=native_symbols[sym]
                begin=address-0x08000000
                blob=orig_rom[begin:begin+length]
                if not 16<=len(blob)<=8192 or blob[0]!=0x10:
                    raise AssertionError("Original Emerald front battle graphic is not valid bounded LZ77: "+sym)
                cls.battle_original_compressed[species_name]=blob
        if cls.resource_bytes>16384:
            raise AssertionError("Emerald original full tileset exceeds one synchronous 16 KiB XGBA read; must implement chunking, never drop assets")
        if r19:
            resources=[
                Resource("emerald_littleroot_pack",8192 if r28 else len(cls.pack)),
                Resource("emerald_route101_pack",8192 if r28 else len(cls.route_pack))]
            phases=[Phase("original_emerald_connected_maps",
                          ("emerald_littleroot_pack","emerald_route101_pack"),
                          transient_heap_bytes=12288)]
            if r19_battle:
                # Critical: battle reuses (does not add to) the EWRAM
                # working set previously occupied by connected maps.
                # Reserve actual fixed-size 8 KiB scratch slots, rather than
                # only the compressed asset lengths, and fail on overflow.
                resources += [
                    Resource("emerald_battle_enemy_front_slot0",8192),
                    Resource("emerald_battle_enemy_front_slot1",8192)]
                phases.append(Phase(
                    "original_emerald_double_battle",
                    ("emerald_battle_enemy_front_slot0",
                     "emerald_battle_enemy_front_slot1"),
                    transient_heap_bytes=12288))
            budget=plan_residency(
                resources,phases,symbol_prefix="gXgbaR17")
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
        if stress:
            config.write_text(config.read_text()+
                f"#define XGBA_R27_STRESS_WIDTH {stress[0]}u\n"
                f"#define XGBA_R27_STRESS_HEIGHT {stress[1]}u\n")
        r18=bool(getattr(cls,"R18_SAVE_TEST",False))
        if r18:
            config.write_text(config.read_text()+"\n#define XGBA_R18_SAVE_TEST 1\n")
        if r19_battle:
            config.write_text(config.read_text()+
                "\n#define XGBA_R19_BATTLE_TEST 1\n"
                f"#define XGBA_R19_POOCHYENA_FRONT_BYTES {len(cls.battle_original_compressed['Poochyena'])}u\n"
                f"#define XGBA_R19_ZIGZAGOON_FRONT_BYTES {len(cls.battle_original_compressed['Zigzagoon'])}u\n")
        r21=bool(getattr(cls,"R21_HEAP_PRESSURE_TEST",False))
        if r21 and not r19_battle:
            raise AssertionError("R21 allocator pressure requires original R19 battle engine")
        if r21:
            config.write_text(config.read_text()+"\n#define XGBA_R21_PRESSURE_TEST 1\n")
        if getattr(cls,"R20_LIFECYCLE_TEST",False):
            if not r19_battle:
                raise AssertionError("R20 re-entry fixture requires R19 original mixed battle")
            config.write_text(config.read_text()+"\n#define XGBA_R20_LIFECYCLE_TEST 1\n")
        if r28:
            config.write_text(config.read_text()+
                "\n#define XGBA_R28_THREE_MAPS 1\n"+
                f"#define XGBA_R28_OLDALE_BYTES {len(cls.oldale_pack)}u\n")
        if r19:
            config.write_text(config.read_text()+
                "\n#define XGBA_R19_CONNECTED_MAPS 1\n"
                "#define XGBA_R19_NATIVE_TEST_OPEN_ROUTE 1\n"
                f"#define XGBA_R19_LITTLEROOT_BYTES {len(cls.pack)}u\n"
                f"#define XGBA_R19_ROUTE_BYTES {len(cls.route_pack)}u\n"
                f"#define XGBA_R19_ROUTE_OFFSET {cls.route_pack_offset}u\n"
                f"#define XGBA_R19_RESERVE {budget.reserve_bytes}u\n")

        # Instrument original decomp and patch engine resets/actual linker
        # without overwriting or re-implementing its maps or tileset renderer.
        originals={}
        try:
            originals=patch.patch_emerald_littleroot_sources(EMERALD,config,r18_save=r18,r19_connected=r19,r19_battle=r19_battle,r26_leases=r26_leases)
            originals.update(patch_emerald_heap_tail(EMERALD,
                reserve_bytes=budget.reserve_bytes,replace_once=e16.one,
                r21_pressure=r21))
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
            if r28:
                oldale_matches=[m.start() for m in re.finditer(
                    re.escape(cls.oldale_grid),stripped)]
                if len(oldale_matches)!=1:
                    raise AssertionError("Original compiled Oldale grid not uniquely identifiable")
                om=oldale_matches[0]
                stripped[om:om+len(cls.oldale_grid)]=bytes(len(cls.oldale_grid))
                removed.append({"asset":"OldaleTown.map","bytes":len(cls.oldale_grid),
                                "offset":om,"sha256":sha(cls.oldale_grid)})
                oldale_address,_=syms["OldaleTown_Layout"]
                oldale_border_addr=struct.unpack_from(
                    "<I",stripped,oldale_address-0x08000000+8)[0]
                ob=oldale_border_addr-0x08000000
                if stripped[ob:ob+8]!=cls.oldale_border:
                    raise AssertionError("Original compiled Oldale border pointer drift")
                stripped[ob:ob+8]=bytes(8)
                removed.append({"asset":"OldaleTown.border","bytes":8,
                                "offset":ob,"sha256":sha(cls.oldale_border)})
        for symbol,blob in parts:
            address,size=syms[symbol]
            off=address-0x08000000
            if size!=len(blob) or stripped[off:off+size]!=blob:
                raise AssertionError("Compiled original Emerald tileset symbol drift "+symbol)
            stripped[off:off+size]=bytes(size)
            removed.append({"asset":symbol,"bytes":size,"offset":off,"sha256":sha(blob)})
        if r19_battle:
            # A Pokemon front sprite entry still has its original table
            # pointer; changing the battle loader is mandatory because the
            # genuine game ROM bytes are deliberately zeroed here.
            cls.battle_sprite_blobs={}
            for species_name,baseline_blob in cls.battle_original_compressed.items():
                sym="gMonFrontPic_"+species_name
                address,length=syms[sym]
                start=address-0x08000000
                blob=bytes(stripped[start:start+length])
                if blob!=baseline_blob:
                    raise AssertionError("Rebuilt Emerald front sprite no longer matches unmodified source "+sym)
                stripped[start:start+length]=bytes(length)
                cls.battle_sprite_blobs[species_name]=blob
                removed.append({"asset":sym,"bytes":length,"offset":start,"sha256":sha(blob)})
            # Treecko remains ROM-resident and will use the vanilla back
            # sprite and normal battle engine palette/animation tables.
            tree_addr,tree_len=syms["gMonBackPic_Treecko"]
            tree_start=tree_addr-0x08000000
            cls.local_treecko_sha=sha(stripped[tree_start:tree_start+tree_len])
            if tree_len<16 or stripped[tree_start]!=0x10:
                raise AssertionError("Vanilla Treecko sprite missing from local ROM")
        if (len(stripped)>32*1024*1024 or grid in stripped or
            (r19 and cls.route_grid in stripped) or
            (r28 and cls.oldale_grid in stripped)):
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
                if r28:
                    cls.oldale_offset=32*1024*1024+131072
                    fp.seek(cls.oldale_offset);fp.write(cls.oldale_pack)
            if r19_battle:
                cls.battle_offsets={
                    "Poochyena":32*1024*1024+131072,
                    "Zigzagoon":32*1024*1024+1048576,
                }
                for species_name,blob in cls.battle_sprite_blobs.items():
                    fp.seek(cls.battle_offsets[species_name]);fp.write(blob)
        manifest=root/"manifest.json"
        manifest.write_text(json.dumps({
            "format":sidecar.FORMAT,"version":sidecar.VERSION,
            "source_identity":{"id":"pokeemerald-r17-native-map","sha256":cls.rom_sha},
            "data_file":data.name,
            "resources":[
                {"id":RID,"offset":cls.offset,"length":len(cls.pack),"sha256":sha(cls.pack)},
                {"id":BOOT,"offset":boot_offset,"length":64,"sha256":sha(r6.PAYLOAD)}
            ]+([{"id":"emerald.route101","offset":cls.route_offset,
                 "length":len(cls.route_pack),"sha256":sha(cls.route_pack)}] if r19 else [])+
            ([{"id":"emerald.oldale","offset":cls.oldale_offset,
               "length":len(cls.oldale_pack),"sha256":sha(cls.oldale_pack)}]
             if r28 else [])+
            ([{"id":"emerald.battle."+species.lower()+".front",
               "offset":cls.battle_offsets[species],
               "length":len(blob),"sha256":sha(blob)}
              for species,blob in cls.battle_sprite_blobs.items()] if r19_battle else [])
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
            if r19_battle:
                cls.battle_probe=syms["gXgbaR19BattleProof"][0]
                if r21:
                    cls.heap_probe=syms["gXgbaR21HeapProof"][0]
                    if not 0x02000000<=cls.heap_probe<0x02040000:
                        raise AssertionError("R21 original malloc proof not in native EWRAM")
                # R19 battle uses the phase-shared, linker-audited heap tail;
                # there is intentionally NO extra 16 KiB EWRAM global symbol.
                cls.battle_front_buffer=real_arena
                if budget.reserve_bytes!=16384 or not 0x02000000<=cls.battle_probe<0x02040000 or not (
                        0x02000000<=cls.battle_front_buffer<
                        cls.battle_front_buffer+16384<=0x02040000):
                    raise AssertionError("R19 mixed battle proof/sprite buffers exceed real 256KiB EWRAM")
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
        if stress:
            if f"PASS_R27_REAL_EMERALD_HUGE_MAP width={stress[0]} height={stress[1]}" not in cls.log:
                raise AssertionError("Original Emerald large-geometry native proof absent")
            cls.report["milestone"]="R27_ORIGINAL_EMERALD_HUGE_MAP_GEOMETRY"
            cls.report["synthetic_test_grid_from_original_tiles"]=True
            cls.report["stressed_map_geometry"]={"width":stress[0],"height":stress[1]}
            cls.report["full_ewram_backup_cells"]=cls.geometry_plan.backup_cells
            cls.report["complete_full_secondary_tileset"]=True
            cls.report["original_emerald_native_all_map_cells_checked"]=stress[0]*stress[1]
            cls.report["scope"]="Native original Emerald engine draws an XGBA-supplied synthetic 64x64 or 128x32 map built from the original Littleroot metatile bytes, plus the complete original Petalburg tileset; does not prove arbitrary giant maps or three-map eviction."
        output=os.getenv("XGBA_R27_EVIDENCE_DIR" if stress else "XGBA_R17_EVIDENCE_DIR")
        if output:
            dest=Path(output);dest.mkdir(parents=True,exist_ok=True)
            for path in cls.output.glob("*.png"):
                shutil.copy2(path,dest/(f"{stress[0]}x{stress[1]}-"+path.name if stress else path.name))
            (dest/(f"proof-{stress[0]}x{stress[1]}.json" if stress else "proof.json")).write_text(json.dumps(cls.report,indent=2,sort_keys=True))

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
