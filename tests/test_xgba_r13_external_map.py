"""R13: original FireRed house layout physically outside the ROM.
Build the real pinned game with its house blockdata and border replaced by
zeros. Guest fetches original bytes via XGBA and uses native map/warp loader.
Only native screenshots and hashes are published, not ROMs or source assets.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
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

def sha(b):
    return hashlib.sha256(b).hexdigest()

class ExternalMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r6.verify_pins()
        cls.temp=tempfile.TemporaryDirectory(prefix="xgba-r13-")
        cls.addClassCleanup(cls.temp.cleanup)
        root=Path(cls.temp.name)
        layout=r7.FIRERED/"data/layouts/PalletTown_PlayersHouse_1F"
        block=layout/"map.bin"
        border=layout/"border.bin"
        a,b=block.read_bytes(),border.read_bytes()
        if len(a)!=260 or len(b)!=8:
            raise AssertionError("Pinned house layout dimensions drift")
        cls.payload=a+b
        injection=patch.INJECT
        patch.INJECT=(ROOT/"integration/fire_red/xgba_r13_map.inc").read_text()
        originals={}
        try:
            originals=patch.make_firered_real_overworld_sources(r7.FIRERED)
            world=r7.FIRERED/"src/overworld.c"
            s=world.read_text()
            s=patch.replace_once(s,"        return gMapLayouts[mapLayoutId - 1];",
                "        return XgbaR13Layout(gMapLayouts[mapLayoutId - 1]);",
                "R13 native GetMapLayout")
            world.write_text(s)
            block.write_bytes(bytes(len(a)))
            border.write_bytes(bytes(len(b)))
            r7.run(["make","-C",r7.FIRERED,"-j2","MODERN=1","GAME_VERSION=FIRERED"],timeout=2200)
        finally:
            patch.INJECT=injection
            patch.restore_firered_sources(originals)
            block.write_bytes(a)
            border.write_bytes(b)
        cls.rom=r7.FIRERED/"pokefirered_modern.gba"
        elf=r7.FIRERED/"pokefirered_modern.elf"
        rom=cls.rom.read_bytes()
        if a in rom:
            raise AssertionError("R13 original full house map still inside ROM")
        if len(rom)>32*1024*1024:
            raise AssertionError("R13 ROM exceeds real cartridge window")
        cls.rom_sha=sha(rom)
        nm=r7.run(["arm-none-eabi-nm","-g",elf]).stdout
        matches=re.findall(r"^([0-9a-fA-F]{8})\s+[A-Za-z]\s+gXgbaR13Proof$",nm,re.M)
        if len(matches)!=1:
            raise AssertionError("Missing real game probe")
        cls.probe=int(matches[0],16)
        apply_core_patch.apply(r7.MGBA)
        build=root/"build"
        r7.run(["cmake","-S",ROOT/"integration/mgba","-B",build,
            "-DCMAKE_BUILD_TYPE=Release","-DXGBA_MGBA_CHECKOUT="+str(r7.MGBA)],timeout=250)
        r7.run(["cmake","--build",build,"--target","xgba-mgba-headless","--parallel","2"],timeout=1100)
        cls.emulator=build/"xgba-mgba-headless"
        cls.offset=32*1024*1024+8192
        data=root/"house.bin"
        with data.open("wb") as f:
            f.seek(cls.offset)
            f.write(cls.payload)
        manifest=root/"manifest.json"
        manifest.write_text(json.dumps({
            "format":sidecar.FORMAT,"version":sidecar.VERSION,
            "source_identity":{"id":"firered-r13-external-house","sha256":cls.rom_sha},
            "data_file":data.name,
            "resources":[{"id":"map.pallet.house","offset":cls.offset,
                "length":len(cls.payload),"sha256":sha(cls.payload)}]
        }))
        cls.logs={}
        cls.folders={}
        for mode in ("enabled","disabled"):
            folder=root/mode
            folder.mkdir()
            result=launcher.launch(cls.rom,manifest,"map.pallet.house",
                emulator=cls.emulator,frames=1800,probe_address=cls.probe,
                r13_dir=folder,disabled=mode=="disabled")
            cls.logs[mode]=result.stdout
            cls.folders[mode]=folder
            if "PASS_R13_REAL_FIRERED_EXTERNAL_MAP mode="+mode not in result.stdout:
                raise AssertionError("Native R13 evidence absent")
        target=os.getenv("XGBA_R13_EVIDENCE_DIR")
        if target:
            dest=Path(target)
            dest.mkdir(parents=True,exist_ok=True)
            for mode,folder in cls.folders.items():
                out=dest/mode
                out.mkdir()
                for image in folder.glob("*.png"):
                    shutil.copy2(image,out/image.name)
            (dest/"proof.json").write_text(json.dumps({
                "milestone":"R13_REAL_EXTERNAL_MAP",
                "rom_sha256":cls.rom_sha,"rom_size":len(rom),
                "external_offset":cls.offset,"payload_bytes":len(cls.payload),
                "layout":"MAP_PALLET_TOWN_PLAYERS_HOUSE_1F",
                "width":13,"height":10,"border_width":2,"border_height":2,
                "payload_sha256":sha(cls.payload),"map_sha256":sha(a),
                "border_sha256":sha(b),"original_full_map_absent_from_rom":True,
                "native_logs":cls.logs,
                "firered_pin":r6.FIRERED_PIN,"mgba_pin":r6.MGBA_PIN,
                "scope":"Full metatile grid and border external; native layout metadata, tilesets, events and scripts remain in ROM. SELECT invokes standard DoWarp; not a physical door-input test. No ROM or source map bytes exported."
            },indent=2))

    def test_real_external_map_entry_return_reentry(self):
        self.assertIn("transitions=3 reads=2 native_grid_sha_verified=1",self.logs["enabled"])
    def test_disabled_refuses_entry_without_host_reads(self):
        self.assertIn("transitions=0 reads=0 native_grid_sha_verified=0",self.logs["disabled"])
    def test_real_lcd_frames(self):
        for mode,count in (("enabled",4),("disabled",2)):
            images=sorted(self.folders[mode].glob("*.png"))
            self.assertEqual(len(images),count)
            for path in images:
                with Image.open(path) as image:
                    self.assertEqual(image.size,(240,160))
            self.assertNotEqual(images[0].read_bytes(),images[1].read_bytes()) if mode=="enabled" else None
    def test_original_house_absent_and_payload_above_boundary(self):
        self.assertNotIn(self.payload[:260],self.rom.read_bytes())
        self.assertGreater(self.offset,32*1024*1024)

if __name__=="__main__":
    unittest.main()
