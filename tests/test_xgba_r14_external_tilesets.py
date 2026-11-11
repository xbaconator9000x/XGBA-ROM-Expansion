"""R14 actual FireRed D-pad door + seamless connected Route1 with external tilesets.
Both complete secondary tilesets and both map layouts are extracted from pinned
source-built game assets; their compiled ROM ranges are zeroed. The normal
game map engine uses EWRAM-backed layouts/tilesets, not a host-rendered scene.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"tests"),str(ROOT/"integration/mgba")]
import test_xgba_r7_mgba_core as r7
import xgba_resource_integration_smoke as r6
import xgba_resource_sidecar as sidecar
import xgba_r10_firered_patch as patch
import xgba_mgba_run as launcher
import apply_core_patch

def sha(b): return hashlib.sha256(b).hexdigest()
def symbols(elf):
    out=r7.run(["arm-none-eabi-nm","-S","--defined-only",elf]).stdout
    # GNU nm -S omits the size column on assembler-defined layout labels.
    # The address is still sufficient to inspect a MapLayout's ROM pointers.
    return {m[3]:(int(m[1],16),int(m[2],16) if m[2] else 0) for m in re.finditer(
        r"^([0-9a-fA-F]+)(?:\s+([0-9a-fA-F]+))?\s+[A-Za-z]\s+(\S+)$",out,re.M)}

def tileset_parts(rom,syms,name):
    parts=[]
    for stem in ("gTilesetTiles_","gTilesetPalettes_","gMetatiles_","gMetatileAttributes_"):
        symbol=stem+name
        address,size=syms[symbol]
        offset=address-0x08000000
        if not size or offset<0 or offset+size>len(rom):
            raise AssertionError("Invalid source ROM symbol "+symbol)
        parts.append((symbol,rom[offset:offset+size]))
    return parts

def pack(layout,parts):
    chunks=[layout[0],layout[1]]+[b for _,b in parts]
    payload=bytearray(32)
    offsets=[]
    for blob in chunks:
        while len(payload)%4:payload.append(0)
        offsets.append(len(payload))
        payload.extend(blob)
    if len(payload)>16384:
        raise AssertionError("External pack exceeds 16 KiB mailbox")
    struct.pack_into("<8I",payload,0,0x52313450,len(payload),*offsets)
    return bytes(payload)

class NativeNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r6.verify_pins()
        cls.tmp=tempfile.TemporaryDirectory(prefix="xgba-r14-")
        cls.addClassCleanup(cls.tmp.cleanup)
        root=Path(cls.tmp.name)
        fr=r7.FIRERED
        rom=fr/"pokefirered_modern.gba"
        elf=fr/"pokefirered_modern.elf"
        def build():
            r7.run(["make","-C",fr,"-j2","MODERN=1","GAME_VERSION=FIRERED"],timeout=2200)
        # First compile the exact upstream assets to recover real GBA LZ/palette bytes.
        build()
        original=rom.read_bytes()
        syms=symbols(elf)
        definitions=[]
        for name,tiles,w,h in (("Route1","PalletTown",24,40),
                              ("PalletTown_PlayersHouse_1F","GenericBuilding1",13,10)):
            folder=fr/"data/layouts"/name
            grid=(folder/"map.bin").read_bytes()
            border=(folder/"border.bin").read_bytes()
            if len(grid)!=w*h*2 or len(border)!=8:
                raise AssertionError("Pinned map geometry drift")
            parts=tileset_parts(original,syms,tiles)
            definitions.append((name,grid,border,parts,pack((grid,border),parts)))
        route,house=definitions
        config=root/"r14-config.h"
        config.write_text("#define R14_ROUTE_SIZE %du\n#define R14_HOUSE_SIZE %du\n"%(len(route[4]),len(house[4])))
        inj=patch.INJECT
        patch.INJECT=(ROOT/"integration/fire_red/xgba_r14_nav.inc").read_text().replace(
            "__R14_CONFIG__",config.as_posix())
        originals={}
        try:
            originals=patch.make_firered_real_overworld_sources(fr)
            world=fr/"src/overworld.c"
            s=world.read_text()
            s=patch.replace_once(s,"        return gMapLayouts[mapLayoutId - 1];",
                "        return R14Resolve(gMapLayouts[mapLayoutId - 1],gSaveBlock1Ptr->location.mapGroup,gSaveBlock1Ptr->location.mapNum);","R14 layout")
            s=patch.replace_once(s,"    return gMapGroups[mapGroup][mapNum];",
                "    return R14Header(gMapGroups[mapGroup][mapNum],mapGroup,mapNum);","R14 connected map header")
            s=patch.replace_once(s,"MAP_NUM(MAP_PALLET_TOWN), -1, 10, 13);",
                "MAP_NUM(MAP_PALLET_TOWN), -1, 6, 8);\n"
                "    FlagSet(FLAG_SYS_POKEMON_GET);\n"
                "    FlagSet(FLAG_HIDE_OAK_IN_PALLET_TOWN);\n"
                "    VarSet(VAR_MAP_SCENE_PALLET_TOWN_OAK, 1);","R14 natural door approach and post-Oak fixture")
            world.write_text(s)
            build()
        finally:
            patch.INJECT=inj
            patch.restore_firered_sources(originals)
        finalsyms=symbols(elf)
        arena_addr,arena_size=finalsyms["gXgbaR14Arena"]
        if arena_size!=max(len(route[4]),len(house[4])) or not (
                0x02000000<=arena_addr and arena_addr+arena_size<=0x02040000):
            raise AssertionError("R14 shared arena does not fit exact EWRAM bounds")
        binary=bytearray(rom.read_bytes())
        # Strip exact compiled ROM symbol ranges after linking. No stock layout
        # or secondary tile bytes can satisfy the subsequent guest accesses.
        removed=[]
        for name,grid,border,parts,payload in definitions:
            matches=[m.start() for m in re.finditer(re.escape(grid),binary)]
            if len(matches)!=1: raise AssertionError("Expected unique map grid "+name)
            off=matches[0]
            binary[off:off+len(grid)]=bytes(len(grid))
            # Locate the actual border via layout struct pointer in ELF.
            layout_symbol=name+"_Layout"
            addr,_=finalsyms[layout_symbol]
            border_addr=struct.unpack_from("<I",binary,addr-0x08000000+8)[0]
            bo=border_addr-0x08000000
            if binary[bo:bo+8]!=border:raise AssertionError("Wrong compiled border "+name)
            binary[bo:bo+8]=bytes(8)
            removed.append({"map":name,"grid_offset":off,"border_offset":bo})
            for symbol,data in parts:
                addr,size=finalsyms[symbol]
                off=addr-0x08000000
                if size!=len(data) or binary[off:off+size]!=data:
                    raise AssertionError("Compiled secondary tileset symbol drift "+symbol)
                binary[off:off+size]=bytes(size)
                removed.append({"symbol":symbol,"rom_offset":off,"bytes":size,"sha256":sha(data)})
            if grid in binary:raise AssertionError("Original full map remains in ROM")
        if len(binary)>32*1024*1024:raise AssertionError("ROM too large")
        rom.write_bytes(binary)
        cls.rom_sha=sha(binary)
        cls.probe=finalsyms["gXgbaR14Proof"][0]
        if not 0x02000000<=cls.probe<0x02040000:raise AssertionError("Invalid guest proof")
        apply_core_patch.apply(r7.MGBA)
        native=root/"build"
        r7.run(["cmake","-S",ROOT/"integration/mgba","-B",native,
            "-DCMAKE_BUILD_TYPE=Release","-DXGBA_MGBA_CHECKOUT="+str(r7.MGBA)],timeout=250)
        r7.run(["cmake","--build",native,"--target","xgba-mgba-headless","--parallel","2"],timeout=1100)
        offsets=[32*1024*1024+8192,32*1024*1024+32768]
        ids=["map.route1.tiles","map.house.tiles"]
        data=root/"external.bin"
        with data.open("wb") as f:
            for offset,definition in zip(offsets,definitions):
                f.seek(offset);f.write(definition[4])
        resources=[{"id":id,"offset":off,"length":len(d[4]),"sha256":sha(d[4])}
            for id,off,d in zip(ids,offsets,definitions)]
        manifest=root/"manifest.json"
        manifest.write_text(json.dumps({"format":sidecar.FORMAT,"version":sidecar.VERSION,
            "source_identity":{"id":"firered-r14-nav","sha256":cls.rom_sha},
            "data_file":data.name,"resources":resources}))
        cls.output=root/"evidence";cls.output.mkdir()
        result=launcher.launch(rom,manifest,ids[0],emulator=native/"xgba-mgba-headless",
            frames=1800,probe_address=cls.probe,second_resource_id=ids[1],r14_dir=cls.output)
        cls.log=result.stdout
        if "PASS_R14_REAL_DOOR_AND_CONNECTED_ROUTE_EXTERNAL_TILESETS" not in cls.log:
            raise AssertionError("Native R14 proof absent")
        cls.report={"milestone":"R14_PHYSICAL_NAV_EXTERNAL_SECONDARY_TILESETS",
            "rom_sha256":cls.rom_sha,"rom_size":len(binary),"resources":resources,
            "stripped_compiled_ranges":removed,"native_log":cls.log,
            "shared_arena":{"address":arena_addr,"bytes":arena_size,
                "pack_bytes":[len(route[4]),len(house[4])],
                "stock_heap_size":0x1C000,"expected_reads":3},
            "firered_pin":r6.FIRERED_PIN,"mgba_pin":r6.MGBA_PIN,
            "scope":"Real D-pad input; native door warp and seamless Route1 connection. Entire indoor/outdoor secondary tileset (LZ graphics, palettes, metatiles, attributes) externally staged. Primary tilesets, map events/scripts/metadata remain ROM-resident. Post-Oak starting fixture. No raw game assets exported."}
        target=os.getenv("XGBA_R14_EVIDENCE_DIR")
        if target:
            dest=Path(target);dest.mkdir(parents=True,exist_ok=True)
            for img in cls.output.glob("*.png"):shutil.copy2(img,dest/img.name)
            (dest/"proof.json").write_text(json.dumps(cls.report,indent=2))
    def test_real_dpad_door_and_route_connection(self):
        self.assertIn("physical_dpad=1",self.log)
    def test_actual_native_grid_and_bg_vram(self):
        self.assertIn("native_map_grid=1 native_bg_vram=1",self.log)
    def test_external_resource_integrity_and_rom_removal(self):
        self.assertIn("reads=3 shared_arena=1",self.log)
        self.assertEqual(self.report["shared_arena"]["bytes"],
                         max(self.report["shared_arena"]["pack_bytes"]))
        self.assertEqual(len(self.report["stripped_compiled_ranges"]),10)
        self.assertTrue(all(r["offset"]>32*1024*1024 for r in self.report["resources"]))
    def test_real_lcd_screenshots(self):
        images=sorted(self.output.glob("*.png"))
        self.assertEqual(len(images),4)
        for img in images:
            with Image.open(img) as im:self.assertEqual(im.size,(240,160))
        self.assertNotEqual(images[0].read_bytes(),images[1].read_bytes())
        self.assertNotEqual(images[2].read_bytes(),images[3].read_bytes())

if __name__=="__main__":unittest.main()
