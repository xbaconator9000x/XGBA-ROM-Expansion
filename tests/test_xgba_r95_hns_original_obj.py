"""R95 nine-frame source-backed Heart & Soul OBJ intake: AUTHORED test bytes only."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r95_hns_original_obj as r95

def fixture(folder):
    root=Path(folder)
    def put(path,data):
        p=root/path
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(data) if isinstance(data,str) else p.write_bytes(data)
    put("include/constants/event_objects.h","#define OBJ_EVENT_GFX_BOY_2_HNS 406\n")
    put("src/data/object_events/object_event_graphics_info.h",
        "const struct ObjectEventGraphicsInfo gObjectEventGraphicsInfo_Boy2_hns = {TAG_NONE, OBJ_EVENT_PAL_TAG_NPC_4_HNS, OBJ_EVENT_PAL_TAG_NONE, 256, 16, 32, 2, SHADOW_SIZE_M, FALSE, FALSE, TRACKS_FOOT, &gObjectEventBaseOam_16x32, sOamTables_16x32, sAnimTable_Standard, sPicTable_Boy2_hns};\n")
    put("src/data/object_events/object_event_pic_tables.h",
        "static const struct SpriteFrameImage sPicTable_Boy2_hns[] = {\n"+
        "".join("overworld_frame(gObjectEventPic_Boy2_hns, 2, 4, %d),\n"%i for i in range(9))+"};\n")
    put("src/data/object_events/object_event_graphics.h",
        'const u32 gObjectEventPic_Boy2_hns[] = INCBIN_U32("graphics/object_events/pics/people/boy_2_hns.4bpp");\n'
        'const u16 gObjectEventPal_Npc4_hns[] = INCBIN_U16("graphics/object_events/palettes/npc_green_hns.gbapal");\n')
    put("src/data/object_events/object_event_anims.h",
        "static const union AnimCmd *const sAnimTable_Standard[] = {\n"
        "[ANIM_STD_FACE_SOUTH] = sAnim_FaceSouth,\n};\n")
    put("graphics/object_events/pics/people/boy_2_hns.png",b"AUTHORED_PNG_STUB_NO_ORIGINAL_ART")
    symbols={
        r95.PIC_BYTES:0x08000200,
        r95.PIC_TABLE:0x08000c00,
        r95.SOURCE_OBJECT:0x08000d00,
        r95.PAL_BYTES:0x08000e00,
        r95.OAM_BYTES:0x08000f00,
        r95.ANIM_TABLE:0x08000f20,
        r95.FIRST_ANIM:0x08000f40
    }
    rom=bytearray(16384)
    for j in range(9):
        off=0x200+j*256
        rom[off:off+256]=bytes([(j*17+i)&255 for i in range(256)])
        struct.pack_into("<IHH",rom,0xc00+j*8,r95.BASE+off,256,0)
    for i,symbol in enumerate((r95.PIC_TABLE,r95.OAM_BYTES,r95.ANIM_TABLE)):
        struct.pack_into("<I",rom,0xd00+i*4,symbols[symbol])
    rom[0xe00:0xe20]=bytes(range(32))
    struct.pack_into("<4H",rom,0xf00,0x8000,0x8000,0,0)
    struct.pack_into("<I",rom,0xf20,symbols[r95.FIRST_ANIM])
    struct.pack_into("<4H",rom,0xf40,0,16,0xfffd,0)
    return root,rom,symbols

class NineFrameSourceBoy2Tests(unittest.TestCase):
    def test_original_9_frames_source_and_r56_metadata_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root,rom,symbols=fixture(d)
            resources,record=r95.extract_original_boy2(root,rom,symbols)
            self.assertEqual(len(resources),5)
            self.assertEqual([name for name,_ in resources],[
                "r56.w2.s0196.meta","r56.w2.s0196.f00",
                "r56.w2.s0196.p00","r56.w2.s0196.o00",
                "r56.w2.s0196.a00"])
            meta=resources[0][1]
            self.assertEqual(meta[:4],b"X56S")
            self.assertEqual(meta[5],2)
            self.assertEqual(struct.unpack_from("<H",meta,6)[0],406)
            self.assertEqual(struct.unpack_from("<H",meta,52)[0],9)
            self.assertEqual(struct.unpack_from("<I",meta,12)[0],2304)
            self.assertEqual(len(resources[1][1]),16384)
            self.assertEqual(resources[1][1][8*256:9*256],rom[0xa00:0xb00])
            self.assertFalse(record["original_directional_animations_complete"])
            self.assertFalse(record["real_gameplay_fly_passed"])
    def test_refuse_repointed_or_shortened_original_frames(self):
        with tempfile.TemporaryDirectory() as d:
            root,rom,symbols=fixture(d)
            struct.pack_into("<I",rom,0xc00+8*8,0x08000200)
            with self.assertRaisesRegex(r95.HnsOriginalObjectError,"SpriteFrameImage"):
                r95.extract_original_boy2(root,rom,symbols)
    def test_refuse_invented_missing_original_source_symbol(self):
        with tempfile.TemporaryDirectory() as d:
            root,rom,symbols=fixture(d)
            del symbols[r95.PIC_BYTES]
            with self.assertRaisesRegex(r95.HnsOriginalObjectError,"linked HnS symbol"):
                r95.extract_original_boy2(root,rom,symbols)
    def test_refuse_wrong_source_graphics_id(self):
        with tempfile.TemporaryDirectory() as d:
            root,rom,symbols=fixture(d)
            (root/"include/constants/event_objects.h").write_text("#define OBJ_EVENT_GFX_BOY_2_HNS 407\n")
            with self.assertRaisesRegex(r95.HnsOriginalObjectError,"graphics ID"):
                r95.extract_original_boy2(root,rom,symbols)
    def test_refuse_unverified_oam_and_animation_backing(self):
        with tempfile.TemporaryDirectory() as d:
            root,rom,symbols=fixture(d)
            struct.pack_into("<H",rom,0xf00,0)
            with self.assertRaisesRegex(r95.HnsOriginalObjectError,"OAM incompatible"):
                r95.extract_original_boy2(root,rom,symbols)
            struct.pack_into("<H",rom,0xf00,0x8000)
            struct.pack_into("<I",rom,0xf20,0x08000000)
            with self.assertRaisesRegex(r95.HnsOriginalObjectError,"first animation not connected"):
                r95.extract_original_boy2(root,rom,symbols)
if __name__=="__main__":unittest.main()
