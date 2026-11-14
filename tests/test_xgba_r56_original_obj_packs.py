"""R56 original-source object graphics byte and integrity contracts (authored ROM)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r56_original_obj_packs as mod

def specimen():
    rom=bytearray(8192)
    offsets=(512,2048,4096,4608)
    lengths=(1024,32,16,12)
    for j,(off,length) in enumerate(zip(offsets,lengths)):
        struct.pack_into("<I",rom,128+j*4,0x08000000+off)
        rom[off:off+length]=bytes((j*13+i*7+11)&255 for i in range(length))
    item={"world":2,"original_id":0x4000,"descriptor_offset":128,
          "width":32,"height":32,"frame_count":2,"compression":0,
          "sections":{suffix:{"pointer_field_offset":128+j*4,
                               "source_offset":offsets[j],
                               **({"size":lengths[j]} if j else {})}
              for j,suffix in enumerate(mod.SECTIONS)}}
    return bytes(rom),item

class R56OriginalSpriteSource(unittest.TestCase):
    def test_source_ptrs_packed_private_and_page_sha(self):
        rom,item=specimen()
        name,head,parts=mod.extract_sprite(rom,item,expected_world=2)
        self.assertEqual(name,"r56.w2.s4000")
        self.assertEqual(head[:4],b"X56S")
        self.assertEqual(struct.unpack_from("<H",head,6)[0],0x4000)
        self.assertEqual(tuple(map(len,parts)),(1024,32,16,12))
        for i,part in enumerate(parts):
            self.assertEqual(struct.unpack_from("<I",head,28+i*4)[0],
                             __import__("zlib").crc32(part)&0xffffffff)
        with tempfile.TemporaryDirectory() as td:
            compiled=mod.compile_private_originals({
               "emerald":rom,"rocket":rom,"heart_soul":rom},[item],
               strict_sources=False)
            man=mod.write_private_pack(compiled,Path(td)/"private")
            self.assertEqual(len(man["resources"]),5)
            self.assertEqual([e["id"] for e in man["resources"]],
              [name+".meta",name+".f00",name+".p00",name+".o00",name+".a00"])
            for e in man["resources"]:
                self.assertEqual(len(e["sha256"]),64)
            self.assertFalse(json.loads((Path(td)/"private"/"R56_PRIVATE_SOURCE_SCOPE.json")
                    .read_text())["native_original_fly_journey_complete"])
    def test_wrong_source_pointer_rejected(self):
        rom,item=specimen()
        item["sections"]["p"]["source_offset"]+=4
        with self.assertRaises(mod.OriginalObjectSourceError):
            mod.extract_sprite(rom,item,expected_world=2)
    def test_invalid_frame_geometry_rejected(self):
        rom,item=specimen()
        item["width"]=40
        with self.assertRaises(mod.OriginalObjectSourceError):
            mod.extract_sprite(rom,item,expected_world=2)
    def test_duplicate_same_world_original_id_rejected(self):
        rom,item=specimen()
        with self.assertRaises(mod.OriginalObjectSourceError):
            mod.compile_private_originals({
               "emerald":rom,"rocket":rom,"heart_soul":rom},[item,item],
               strict_sources=False)
    def test_source_sha_must_match_private_original(self):
        rom,item=specimen()
        with self.assertRaises(mod.OriginalObjectSourceError):
            mod.compile_private_originals({
               "emerald":rom,"rocket":rom,"heart_soul":rom},[item],
               strict_sources=True)
    def test_offset_must_belong_to_source_descriptor(self):
        rom,item=specimen()
        item["sections"]["f"]["pointer_field_offset"]=400
        with self.assertRaises(mod.OriginalObjectSourceError):
            mod.extract_sprite(rom,item,expected_world=2)
    def test_compression_claim_cannot_cast_raw_as_smol(self):
        rom,item=specimen()
        item["compression"]=6
        with self.assertRaises((mod.OriginalObjectSourceError,IndexError)):
            mod.extract_sprite(rom,item,expected_world=2)
    def test_wrong_original_world_rejected(self):
        rom,item=specimen()
        with self.assertRaises(mod.OriginalObjectSourceError):
            mod.extract_sprite(rom,item,expected_world=1)
if __name__=="__main__":unittest.main()
