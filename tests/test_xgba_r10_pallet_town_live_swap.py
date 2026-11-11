"""R10: LIVE external Crystal->Magma swap in FireRed's REAL Pallet Town.

Unlike earlier controlled proof scenes, this source-instruments the existing
FireRed overworld / CB2_NewGame flow, loads unmodified MAP_PALLET_TOWN via
the real game map engine, then hooks game sprite API to show external artwork.
A real mGBA Select button event causes the running GBA game to fetch the second
sidecar resource using the R7 in-core MMIO provider, without ROM reload/reset.

Only actual native mGBA framebuffer screenshots qualify as proof. GIFs are
encoded from those frames without inventing the original graphics pixels.
No Pokémon ROM binaries or licensed game art are distributed by this project.
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

from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"tests"),str(ROOT/"integration/mgba")]
import xgba_resource_integration_smoke as r6
import xgba_resource_sidecar as sidecar
import xgba_r9_packs as packs
import xgba_mgba_run as launcher
import xgba_r10_firered_patch as patch
import test_xgba_r7_mgba_core as r7
import apply_core_patch

NATIVE_SPRITE_RECT=(88,46,152,110)
FIRERED_REAL_MAP=(3,0)  # generated from pinned map_groups.json: PalletTown


def run(args, *, timeout=1600):
    return r7.run(args,timeout=timeout)


def png(path:Path)->Image.Image:
    im=Image.open(path)
    im.load()
    if im.size != (240,160):
        raise AssertionError("R10 native LCD must render exactly 240x160")
    return im.convert("RGB")


def compare_region(a:Path,b:Path,rect)->int:
    x=png(a).crop(rect).getdata()
    y=png(b).crop(rect).getdata()
    return sum(left!=right for left,right in zip(x,y))


def assemble_gif(frames:list[Path], destination:Path):
    images=[png(p) for p in frames]
    images[0].save(destination,format="GIF",save_all=True,
                   append_images=images[1:],duration=165,
                   loop=0,optimize=False,disposal=2)
    return Image.open(destination).n_frames


def create_combined(pre:Path, post:Path, target:Path):
    a,b=png(pre),png(post)
    canvas=Image.new("RGB",(2*480+48,372),(19,28,37))
    draw=ImageDraw.Draw(canvas)
    canvas.paste(a.resize((480,320),Image.Resampling.NEAREST),(16,36))
    canvas.paste(b.resize((480,320),Image.Resampling.NEAREST),(512,36))
    draw.text((16,12),"CRYSTAL — PALLET TOWN BEFORE SELECT",fill=(145,235,255))
    draw.text((512,12),"MAGMA — SAME PALLET TOWN SESSION",fill=(255,202,123))
    canvas.save(target)


class ActualFireRedPalletTownLiveSwap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r6.verify_pins()
        cls.temp=tempfile.TemporaryDirectory(prefix="xgba-r10-pallet-town-")
        cls.addClassCleanup(cls.temp.cleanup)
        root=Path(cls.temp.name)

        originals=patch.make_firered_real_overworld_sources(r7.FIRERED)
        try:
            run(["make","-C",r7.FIRERED,"-j2",
                 "MODERN=1","GAME_VERSION=FIRERED"],timeout=2200)
        finally:
            patch.restore_firered_sources(originals)
        cls.rom=r7.FIRERED/"pokefirered_modern.gba"
        cls.elf=r7.FIRERED/"pokefirered_modern.elf"
        if not cls.rom.is_file() or not cls.elf.is_file():
            raise AssertionError("R10 real source-built FireRed ROM/ELF missing")
        cls.rom_sha=hashlib.sha256(cls.rom.read_bytes()).hexdigest()
        symbols=run(["arm-none-eabi-nm","-g",cls.elf]).stdout
        matches=re.findall(
            r"^([0-9a-fA-F]{8})\s+[A-Za-z]\s+gXgbaR10Proof$",
            symbols,re.M)
        if len(matches)!=1:
            raise AssertionError("R10 real GBA ELF proof symbol absent")
        cls.probe=int(matches[0],16)
        if not 0x02000000<=cls.probe<0x0203FFB0:
            raise AssertionError("R10 game proof is not in GBA EWRAM")

        apply_core_patch.apply(r7.MGBA)
        build=root/"native-build"
        run(["cmake","-S",ROOT/"integration/mgba","-B",build,
             "-DCMAKE_BUILD_TYPE=Release",
             "-DXGBA_MGBA_CHECKOUT="+str(r7.MGBA)],timeout=250)
        run(["cmake","--build",build,
             "--target","xgba-mgba-headless","--parallel","2"],timeout=1100)
        cls.emulator=build/"xgba-mgba-headless"
        if not cls.emulator.is_file():
            raise AssertionError("R10 patched native mGBA not compiled")

        cls.crystal=packs.make_pack("crystal")
        cls.magma=packs.make_pack("magma")
        if cls.crystal==cls.magma or len(cls.crystal)!=len(cls.magma)!=2048:
            raise AssertionError("R10 requires two 2048 byte distinct resources")
        cls.offset_a=r6.RESOURCE_OFFSET
        cls.offset_b=r6.RESOURCE_OFFSET+4096
        data=root/"both-external-resources.bin"
        with data.open("wb") as f:
            f.truncate(cls.offset_b+len(cls.magma))
            f.seek(cls.offset_a)
            f.write(cls.crystal)
            f.seek(cls.offset_b)
            f.write(cls.magma)
        cls.manifest=root/"both-packs.json"
        cls.manifest.write_text(json.dumps({
            "format":sidecar.FORMAT,
            "version":sidecar.VERSION,
            "source_identity":{
                "id":"firered-pallet-town-r10",
                "sha256":cls.rom_sha,
            },
            "data_file":data.name,
            "resources":[{
                "id":"graphic.crystal",
                "offset":cls.offset_a,
                "length":len(cls.crystal),
                "sha256":hashlib.sha256(cls.crystal).hexdigest(),
            },{
                "id":"graphic.magma",
                "offset":cls.offset_b,
                "length":len(cls.magma),
                "sha256":hashlib.sha256(cls.magma).hexdigest(),
            }],
        }),encoding="utf-8")
        cls.output=root/"actual-mgba-frames"
        cls.output.mkdir()
        cls.execution=launcher.launch(
            cls.rom,cls.manifest,"graphic.crystal",
            emulator=cls.emulator,frames=1800,probe_address=cls.probe,
            second_resource_id="graphic.magma",
            r10_dir=cls.output)
        if "PASS_R10_FIRERED_REAL_PALLET_TOWN_LIVE_MMIO_SWITCH" not in cls.execution.stdout:
            raise AssertionError("Game never executed real Pallet Town live switch")
        cls.before=sorted(cls.output.glob("before-*.png"))
        cls.after=sorted(cls.output.glob("after-*.png"))
        if len(cls.before)!=12 or len(cls.after)!=16:
            raise AssertionError("Missing actual same-session mGBA LCD frames")
        cls.pixel_changes=compare_region(
            cls.before[-1],cls.after[-1],NATIVE_SPRITE_RECT)
        cls.background_colors=len(set(
            png(cls.after[-1]).crop((0,0,70,140)).getdata()))
        cls.evidence={
            "milestone":"R10_REAL_FIRE_RED_PALLET_TOWN_LIVE_ASSET_SWAP",
            "game_map":"MAP_PALLET_TOWN",
            "map_group":FIRERED_REAL_MAP[0],
            "map_num":FIRERED_REAL_MAP[1],
            "rom_sha256":cls.rom_sha,
            "rom_reloaded_during_swap":False,
            "same_native_mgba_core_entire_test":True,
            "game_issues_first_and_second_resource_requests":True,
            "button":"GBA SELECT",
            "first_resource":{"id":"graphic.crystal",
                "offset":cls.offset_a,
                "sha256":hashlib.sha256(cls.crystal).hexdigest()},
            "second_resource":{"id":"graphic.magma",
                "offset":cls.offset_b,
                "sha256":hashlib.sha256(cls.magma).hexdigest()},
            "external_bytes_each":2048,
            "pixel_changes_inside_actual_overworld_OBJ":cls.pixel_changes,
            "non_overlay_map_region_unique_colours":cls.background_colors,
            "real_png_sha256_before":[hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in cls.before],
            "real_png_sha256_after":[hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in cls.after],
            "native_execution_log":cls.execution.stdout.strip(),
            "upstream_firered":r6.FIRERED_PIN,
            "upstream_mgba":r6.MGBA_PIN,
            "scope":"Genuine Pallet Town map events, player, tilemaps and game CB2_Overworld; custom XGBA static sprite overlay injected at source for integration proof. Not stock mGBA or drop-in unpatched ROM compatibility.",
        }
        artifact=os.getenv("XGBA_R10_EVIDENCE_DIR")
        if artifact:
            destination=Path(artifact)
            destination.mkdir(parents=True,exist_ok=True)
            for source,target in [(cls.before,"before"),(cls.after,"after")]:
                folder=destination/target
                folder.mkdir()
                for frame in source:
                    shutil.copy2(frame,folder/frame.name)
            shutil.copy2(cls.before[-1],destination/"pallet-town-crystal-before.png")
            shutil.copy2(cls.after[-1],destination/"pallet-town-magma-after.png")
            create_combined(cls.before[-1],cls.after[-1],
                            destination/"pallet-town-real-engine-comparison.png")
            assemble_gif(cls.before+cls.after,destination/"pallet-town-live-select-swap.gif")
            (destination/"proof.json").write_text(
                json.dumps(cls.evidence,indent=2,sort_keys=True)+"\n",
                encoding="utf-8")
            (destination/"README.txt").write_text(
                "XGBA R10: ACTUAL FIRE RED PALLET TOWN OVERWORLD\n"
                "All source game graphics, native map engine, player and NPC "
                "objects from the actual pinned FireRed engine.\n"
                "The new 64x64 overlay object uses FireRed CreateSprite and "
                "LoadSpriteSheet. Crystal and Magma bytes are ONLY in a "
                "post-32MiB sidecar.\n"
                "SELECT sends a real mGBA GBA controller input; the running "
                "game issues another XGBA MMIO request and replaces the "
                "existing sprite VRAM tiles WITHOUT RESETTING THE ROM.\n"
                "PNG frames are direct native mGBA software LCD renderer "
                "output. The animated GIF is assembled only from those "
                "frames. No mock screen or AI-generated pixel data.\n"
                "LIMITATION: source-instrumented real FireRed with custom "
                "overlay; not yet a normal ROM-hacking editor resource API.\n",
                encoding="utf-8")

    def test_real_pallet_town_map_and_native_overworld_engine(self):
        self.assertIn("group3 map0",self.execution.stdout)
        self.assertGreater(self.background_colors,30)

    def test_live_select_requests_second_external_resource_no_reset(self):
        self.assertIn("2_external_fetches",self.execution.stdout)
        self.assertIn("1_Select",self.execution.stdout)
        self.assertIn("1_continuous_session",self.execution.stdout)
        self.assertEqual(self.evidence["rom_sha256"],self.rom_sha)

    def test_real_emulated_lcd_image_changes_with_same_fire_red_rom(self):
        self.assertGreater(self.pixel_changes,250)
        self.assertEqual(png(self.before[-1]).size,(240,160))
        self.assertEqual(png(self.after[-1]).size,(240,160))

    def test_two_separately_verified_resources_are_after_32MiB(self):
        loaded=sidecar.load_manifest(self.manifest)
        self.assertGreater(cls_offset:=loaded.get_resource("graphic.crystal").offset,
                           32*1024*1024)
        self.assertGreater(loaded.get_resource("graphic.magma").offset,cls_offset)
        rom=self.rom.read_bytes()
        self.assertNotIn(self.crystal[:256],rom)
        self.assertNotIn(self.magma[:256],rom)

    def test_uninterrupted_real_game_callback_keeps_running(self):
        self.assertEqual(len(self.before),12)
        self.assertEqual(len(self.after),16)
        self.assertIn("28_genuine_mGBA_LCDC_frames",self.execution.stdout)


if __name__=="__main__":
    unittest.main()
