"""R9 controlled, controllable GBA overworld scene and three real mGBA runs.

Acceptance is NOT a simulated overworld or a painted screenshot. A real
source-compiled FireRed ARM/Thumb ROM sets up tile-based GBA BG0 and OAM,
loads its scenery emblem from one of TWO external resource sidecars beyond
32 MiB using R7 MMIO, then reads real GBA KEYINPUT for sprite movement.
The native emulator drives actual input and records 16 actual LCD frames
per run. Pillow assembles those REAL captures into downloadable GIFs.
This is a controlled proof map, not yet an integrated stock FireRed route.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"tests"),str(ROOT/"integration/mgba")]
import xgba_resource_sidecar as sidecar
import xgba_resource_integration_smoke as r6
import xgba_r9_packs as packs
import xgba_mgba_run as launcher
import test_xgba_r7_mgba_core as r7
import test_xgba_r8_visible_sprite as r8
import apply_core_patch

SCENE_CODE = r"""
/* R9: game-side, tile-based top-down proof scene with independently
 * movable player. The original ROM contains these map/palette rules and
 * player tiles; it DOES NOT contain the crystal/magma external emblem. */
static void XgbaR9OverworldScene(u16 externalTile)
{
    XgbaR8Present(externalTile);
    volatile u16 *bgPalette=(volatile u16*)0x05000000u;
    volatile u16 *objPalette=(volatile u16*)0x05000200u;
    volatile u32 *bgTiles=(volatile u32*)0x06000000u;
    volatile u16 *bgMap=(volatile u16*)0x0600F800u;
    volatile u32 *objTiles=(volatile u32*)0x06012000u;
    volatile u16 *oam=(volatile u16*)0x07000000u;
    bgPalette[0]=(2u|(8u<<5)|(5u<<10)); /* green backdrop */
    bgPalette[1]=(5u|(18u<<5)|(8u<<10));/* grass */
    bgPalette[2]=(3u|(12u<<5)|(5u<<10));/* shaded grass */
    bgPalette[3]=(16u|(12u<<5)|(7u<<10));/* earth path */
    bgPalette[4]=(24u|(20u<<5)|(10u<<10));/* light soil */
    bgPalette[5]=(31u|(31u<<5)|(8u<<10));/* flower */
    bgPalette[6]=(5u|(9u<<5)|(14u<<10));/* rock */
    /* Warm magma is truly red/orange on-screen, not a PNG filter. */
    objPalette[5]=(31u|(5u<<5)|(3u<<10));
    objPalette[7]=(31u|(14u<<5)|(2u<<10));
    for(u32 row=0; row<8; ++row)
    {
        bgTiles[0*8+row]=0x11111111u; /* 8x8 grass */
        bgTiles[1*8+row]=row&1u ? 0x12111211u:0x11121112u;
        bgTiles[2*8+row]=0x33333333u; /* trail */
        bgTiles[3*8+row]=row==3||row==4 ? 0x11555111u:0x11111111u;
        bgTiles[4*8+row]=row&1u ? 0x66666666u:0x66444466u;
    }
    for(u32 y=0; y<32; ++y)
        for(u32 x=0; x<32; ++x) {
            u32 cell=(x+3u*y)%13u==0u ? 3u : 1u;
            if(y>=12u && y<=15u)
                cell=2u;
            if(x>=27u && y<9u)
                cell=4u;
            bgMap[y*32u+x]=(u16)cell;
        }
    /* Player native 16x16 OBJ, four 8x8 4bpp tiles, deliberately
     * drawn in original game code so both packs share the SAME ROM. */
    for(u32 tile=0; tile<4; ++tile)
        for(u32 row=0; row<8; ++row) {
            u32 pixel=(tile<2u ? 4u : 7u);
            u32 pattern=pixel*0x11111111u;
            if(tile<2u && (row==0u || row==7u))
                pattern=0x66666666u;
            if(tile>=2u && row==7u)
                pattern=0x11111111u;
            objTiles[tile*8u+row]=pattern;
        }
    oam[1*4+0]=92u;
    oam[1*4+1]=24u|(1u<<14); /* square 16x16 */
    oam[1*4+2]=256u;        /* 1D OBJ tiles at 0x06012000 */
    oam[1*4+3]=0u;
    *(volatile u16*)0x04000008u=(31u<<8); /* BG0 tilemap base 31 */
    *(volatile u16*)0x04000010u=0u;       /* BG0 scroll X */
    *(volatile u16*)0x04000012u=0u;       /* BG0 scroll Y */
    *(volatile u16*)0x04000000u=0x1140u; /* BG0+OBJ+1D mode0 */
}
"""

MOVEMENT_LOOP = r"""
/* The actual FireRed ARM code polls hardware GBA KEYINPUT each frame.
 * Host cannot write player coordinates, OAM, or game RAM. */
static void XgbaR9MotionLoop(void)
{
    volatile u16 *oam=(volatile u16*)0x07000000u;
    volatile u16 *vcount=(volatile u16*)0x04000006u;
    volatile u16 *keyinput=(volatile u16*)0x04000130u;
    gXgbaR7Probe.player_x=24u;
    gXgbaR7Probe.player_y=92u;
    gXgbaR7Probe.frame_count=0u;
    while(gXgbaR7Probe.state==3u)
    {
        while(*vcount>=160u)
            ;
        while(*vcount<160u)
            ;
        u16 keys=*keyinput;
        if(!(keys & (1u<<4)) && gXgbaR7Probe.player_x<210u)
            gXgbaR7Probe.player_x+=2u;
        if(!(keys & (1u<<5)) && gXgbaR7Probe.player_x>2u)
            gXgbaR7Probe.player_x-=2u;
        if(!(keys & (1u<<7)) && gXgbaR7Probe.player_y<140u)
            gXgbaR7Probe.player_y+=2u;
        if(!(keys & (1u<<6)) && gXgbaR7Probe.player_y>2u)
            gXgbaR7Probe.player_y-=2u;
        oam[1*4+0]=(u16)gXgbaR7Probe.player_y;
        oam[1*4+1]=(u16)gXgbaR7Probe.player_x|(1u<<14);
        ++gXgbaR7Probe.frame_count;
    }
}
"""


def setup_scene_code():
    # Reuse the proven R7/R8 native game-side loading path verbatim.
    r8.prepare_r8_game()
    s=r7.R7_GAME_CODE
    if s.count('struct XgbaR7Probe {') != 1:
        raise AssertionError("R8 game probe changed")
    s=s.replace('struct XgbaR7Probe {', SCENE_CODE+'\nstruct XgbaR7Probe {')
    marker='    volatile u32 tile;\n};'
    if s.count(marker)!=1:
        raise AssertionError("R8 native scene probe layout changed")
    s=s.replace(marker,'    volatile u32 tile;\n    volatile u32 player_x;\n    volatile u32 player_y;\n    volatile u32 frame_count;\n};')
    anchor='static void XgbaR7GameRun(void)'
    if s.count(anchor)!=1:
        raise AssertionError("R8 game entry changed")
    s=s.replace(anchor,MOVEMENT_LOOP+'\n'+anchor)
    old='    XgbaR8Present(gXgbaR7Probe.tile);'
    if s.count(old)!=1:
        raise AssertionError("R8 tile draw call changed")
    s=s.replace(old,'    XgbaR9OverworldScene(gXgbaR7Probe.tile);')
    old='    while (gXgbaR7Probe.state == 3)\n        ;'
    if s.count(old)!=1:
        raise AssertionError("R8 wait probe changed")
    s=s.replace(old,'    XgbaR9MotionLoop();')
    r7.R7_GAME_CODE=s


def png(path):
    im=Image.open(path)
    im.load()
    if im.size!=(240,160):
        raise AssertionError("R9 frame not genuine GBA LCD dimensions")
    return im.convert("RGB")


def pixel_difference(first,second,region=(0,0,240,160)):
    a=png(first).crop(region)
    b=png(second).crop(region)
    return sum(x!=y for x,y in zip(a.getdata(),b.getdata()))


def frames_to_gif(frames,output):
    # Each frame is a real native mGBA screenshot; GIF conversion is only
    # palette encoding and frame ordering, never synthetic rendering.
    images=[png(f) for f in frames]
    images[0].save(output,format="GIF",save_all=True,
                   append_images=images[1:],duration=140,
                   loop=0,optimize=False,disposal=2)
    proof=Image.open(output)
    if getattr(proof,"n_frames",0)<6:
        raise AssertionError("R9 animated proof lacks distinct emulator frames")


def write_triptych(screen_paths,destination):
    images=[png(p) for p in screen_paths]
    scale=2
    sep=20
    width=3*240*scale+4*sep
    out=Image.new("RGB",(width,160*scale+64),(18,25,33))
    draw=ImageDraw.Draw(out)
    labels=["PACK A — CRYSTAL","PACK B — MAGMA","EXTENSION OFF"]
    for i,(image,label) in enumerate(zip(images,labels)):
        x=sep+i*(240*scale+sep)
        out.paste(image.resize((240*scale,160*scale),Image.Resampling.NEAREST),(x,46))
        draw.text((x,16),label,fill=(235,245,255))
    out.save(destination)


class R9TwoPackOverworld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r6.verify_pins()
        cls.tmp=tempfile.TemporaryDirectory(prefix="xgba-r9-real-")
        cls.addClassCleanup(cls.tmp.cleanup)
        root=Path(cls.tmp.name)
        setup_scene_code()
        cls.rom,cls.probe=r7.compiled_firered()
        cls.rom_sha=hashlib.sha256(cls.rom.read_bytes()).hexdigest()
        apply_core_patch.apply(r7.MGBA)
        build=root/"native-build"
        r7.run(["cmake","-S",ROOT/"integration/mgba","-B",build,
                "-DCMAKE_BUILD_TYPE=Release",
                "-DXGBA_MGBA_CHECKOUT="+str(r7.MGBA)],timeout=240)
        r7.run(["cmake","--build",build,"--target","xgba-mgba-headless",
                "--parallel","2"],timeout=950)
        emulator=build/"xgba-mgba-headless"
        if not emulator.is_file():
            raise AssertionError("R9 native mGBA emulator executable absent")
        cls.packs={}
        cls.logs={}
        cls.frames={}
        cls.hashes={}
        for kind in ("crystal","magma","fallback"):
            pack_name="crystal" if kind=="fallback" else kind
            payload=packs.make_pack(pack_name)
            folder=root/kind
            folder.mkdir()
            data=folder/"resource.bin"
            with data.open("wb") as f:
                f.truncate(r6.RESOURCE_OFFSET+len(payload))
                f.seek(r6.RESOURCE_OFFSET)
                f.write(payload)
            manifest=folder/"manifest.json"
            manifest.write_text(json.dumps({
                "format":sidecar.FORMAT,
                "version":sidecar.VERSION,
                "source_identity":{"id":"xgba-r9-identical-rom",
                                   "sha256":cls.rom_sha},
                "data_file":data.name,
                "resources":[{
                    "id":"graphic.smoke",
                    "offset":r6.RESOURCE_OFFSET,
                    "length":len(payload),
                    "sha256":hashlib.sha256(payload).hexdigest(),
                }]
            }),encoding="utf-8")
            capture=folder/"frames"
            capture.mkdir()
            out=launcher.launch(cls.rom,manifest,"graphic.smoke",
                                emulator=emulator,frames=800,
                                probe_address=cls.probe,
                                scene_dir=capture,
                                disabled=kind=="fallback")
            files=sorted(capture.glob("frame-*.png"))
            if len(files)!=16:
                raise AssertionError("R9 mGBA did not capture 16 raw frames")
            cls.logs[kind]=out.stdout.strip()
            cls.frames[kind]=files
            cls.hashes[kind]=hashlib.sha256(payload).hexdigest()
            cls.packs[kind]=manifest
            if "PASS_R9_REAL_GBA_KEY_INPUT_MOVEMENT" not in out.stdout:
                raise AssertionError("R9 physical KEYINPUT sprite movement absent")
        cls.diff_packs=pixel_difference(
            cls.frames["crystal"][8],cls.frames["magma"][8],(88,48,152,112))
        cls.diff_fallback=pixel_difference(
            cls.frames["crystal"][8],cls.frames["fallback"][8],(88,48,152,112))
        cls.diff_movement={
            key:pixel_difference(paths[2],paths[14],(15,80,85,145))
            for key,paths in cls.frames.items()
        }
        folder_name=os.getenv("XGBA_R9_EVIDENCE_DIR")
        if folder_name:
            out=Path(folder_name)
            out.mkdir(parents=True,exist_ok=True)
            for kind,paths in cls.frames.items():
                dest=out/kind
                dest.mkdir()
                for frame in paths:
                    shutil.copy2(frame,dest/frame.name)
                frames_to_gif(paths,out/f"{kind}-real-mgba.gif")
                shutil.copy2(paths[8],out/f"{kind}-screenshot.png")
            write_triptych([cls.frames[x][8] for x in
                            ("crystal","magma","fallback")],
                           out/"r9-three-runs-comparison.png")
            proof={
                "milestone":"R9_REAL_FIRE_RED_TWO_PACK_DPAD_SCENE",
                "rom_sha256_identical_across_runs":cls.rom_sha,
                "pinned_firered":r6.FIRERED_PIN,
                "pinned_mgba":r6.MGBA_PIN,
                "resource_offset":r6.RESOURCE_OFFSET,
                "resource_bytes":2048,
                "pack_sha256":{"crystal":cls.hashes["crystal"],
                               "magma":cls.hashes["magma"]},
                "crystal_vs_magma_center_pixel_differences":cls.diff_packs,
                "crystal_vs_disabled_center_pixel_differences":cls.diff_fallback,
                "input_movement_pixel_differences":cls.diff_movement,
                "emulator_logs":cls.logs,
                "frame_sha256":{
                    k:[hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in files]
                    for k,files in cls.frames.items()
                },
                "note":"GIFs encode sixteen authentic emulator screenshots per run. The proof scene is a custom, game-controlled tilemap in a source-built FireRed executable; not an unmodified canonical FireRed route or GUI release.",
            }
            (out/"proof.json").write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n")
            (out/"README.txt").write_text(
                "XGBA R9 evidence: Same FireRed ROM SHA for three runs. "
                "Resource pack A crystal, pack B magma, disabled fallback.\n"
                "All raw frames were rendered by native pinned mGBA while "
                "compiled ARM/Thumb FireRed handled GBA D-pad inputs.\n"
                "The 3-panel comparison only scales/labels genuine frames; "
                "GIFs encode actual frames. Neither is an AI mock-up.\n"
                "Controlled proof overworld scene, not yet the stock FireRed "
                "overworld event/map engine.\n")

    def test_same_rom_for_both_packs_and_fallback(self):
        self.assertEqual(len(self.rom_sha),64)
        self.assertNotEqual(self.hashes["crystal"],self.hashes["magma"])
        for manifest in self.packs.values():
            obj=sidecar.load_manifest(manifest)
            self.assertEqual(obj.source_identity.sha256,self.rom_sha)
            self.assertGreater(obj.get_resource("graphic.smoke").offset,32*1024*1024)

    def test_real_native_emulator_displays_both_distinct_external_packs(self):
        self.assertGreater(self.diff_packs,350)
        self.assertIn("enabled=1 requests=1 failures=0 host_lookups=1 bytes=2048",
                      self.logs["crystal"])
        self.assertIn("enabled=1 requests=1 failures=0 host_lookups=1 bytes=2048",
                      self.logs["magma"])

    def test_real_directional_player_control_and_distinct_frame_positions(self):
        for kind in ("crystal","magma","fallback"):
            self.assertIn("PASS_R9_REAL_GBA_KEY_INPUT_MOVEMENT",self.logs[kind])
            self.assertGreater(self.diff_movement[kind],20)
            self.assertEqual(len(self.frames[kind]),16)

    def test_extension_disabled_keeps_game_functional_without_external_reads(self):
        self.assertIn("enabled=0 requests=0 failures=0 host_lookups=0 bytes=0",
                      self.logs["fallback"])
        self.assertGreater(self.diff_fallback,350)

    def test_native_game_screen_dimensions_and_sidecar_asset_is_external(self):
        for kind in ("crystal","magma","fallback"):
            self.assertEqual(png(self.frames[kind][8]).size,(240,160))
        rom=self.rom.read_bytes()
        for kind in ("crystal","magma"):
            self.assertNotIn(packs.make_pack(kind)[:128],rom)


if __name__=="__main__":
    unittest.main()
