"""R68 original Fly dependency enumeration; authored tiny source records only."""
from __future__ import annotations
import struct
import sys
from pathlib import Path
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r68_fly_resource_closure as r68

def base_pages():
    a={}
    for stem,n in (("r49.index.",3),("r51.index.",6),("r52.mapmeta.",6)):
        for i in range(n):a[f"{stem}{i:03d}"]=bytes(16384)
    # indexes are fixed 2856-row arrays, with two authored records.
    idx=bytearray(a["r49.index.000"])
    grid=bytearray(a["r51.index.000"])
    profile=bytearray(a["r52.mapmeta.000"])
    events=bytearray(16384)
    next_at=0
    for row,(world,mapid,width,height,npc_list,root) in enumerate((
        (1,9,24,25,[(1,6,18,10),(2,17,14,13)],(0xe9ffe0,0xe9ffc8)),
        (2,4,58,46,[(7,406,39,22),(18,16400,42,19)],(0xf885e4,0xf8823c)),
    )):
        key=(world<<16)|mapid
        obj=bytearray(24*len(npc_list))
        for j,(local,gfx,x,y) in enumerate(npc_list):
            p=j*24
            obj[p]=local
            struct.pack_into("<Hhh",obj,p+1,gfx,x,y) if False else None
            struct.pack_into("<H",obj,p+1,gfx)
            struct.pack_into("<hh",obj,p+4,x,y)
            struct.pack_into("<I",obj,p+16,0x08001200+4*j)
        rec=bytearray(32+len(obj))
        rec[:4]=b"X49E"
        struct.pack_into("<I",rec,4,key)
        rec[8]=len(npc_list)
        struct.pack_into("<I",rec,20,zlib.crc32(obj)&0xffffffff)
        rec[32:]=obj
        struct.pack_into("<IHHII",idx,row*16,key,0,next_at,len(rec),0x12340)
        events[next_at:next_at+len(rec)]=rec
        next_at+=len(rec)
        struct.pack_into("<IHH",grid,row*32,key,width,height)
        at=row*32
        struct.pack_into("<I",profile,at,key)
        profile[at+4]=2
        struct.pack_into("<II",profile,at+20,*root)
        struct.pack_into("<I",profile,at+28,
                         zlib.crc32(profile[at:at+28])&0xffffffff)
    a["r49.index.000"]=bytes(idx)
    a["r51.index.000"]=bytes(grid)
    a["r52.mapmeta.000"]=bytes(profile)
    a["r49.events.000"]=bytes(events)
    a["rocket.r48.npc"]=bytes(256)
    return a

class SourceResourceClosureTests(unittest.TestCase):
    def test_worlds_report_missing_original_art_without_fabrication(self):
        a=base_pages()
        rocket=r68.inspect_world(a,"rocket")
        johto=r68.inspect_world(a,"heart_soul")
        self.assertEqual(rocket["first_view_original_gfx_ids"],[6,17])
        self.assertEqual(johto["first_view_original_gfx_ids"],[406,16400])
        self.assertEqual(rocket["first_view_npcs"],2)
        self.assertEqual(johto["first_view_npcs"],2)
        self.assertIn("r56.w2.s4010.meta",johto["missing_original_resource_ids"])
        self.assertIn("r53.w2.v2.t00f885e4.meta",johto["missing_original_resource_ids"])
        self.assertIn("heart_soul.r48.npc",johto["missing_original_resource_ids"])
        self.assertFalse(rocket["original_host_resource_closure"])
        self.assertFalse(johto["native_emerald_cross_world_fly_proven"])
    def test_original_event_crc_fails_closed(self):
        pages=base_pages()
        e=bytearray(pages["r49.events.000"])
        e[33]^=0xff
        pages["r49.events.000"]=bytes(e)
        with self.assertRaisesRegex(r68.ResourceClosureError,"event bytes CRC"):
            r68.inspect_world(pages,"rocket")
    def test_original_profile_crc_fails_closed(self):
        pages=base_pages()
        x=bytearray(pages["r52.mapmeta.000"])
        x[24]^=1
        pages["r52.mapmeta.000"]=bytes(x)
        with self.assertRaisesRegex(r68.ResourceClosureError,"profile CRC"):
            r68.inspect_world(pages,"rocket")
    def test_host_hash_does_not_allow_mutated_asset(self):
        import hashlib,json,tempfile,zipfile
        from xgba_r62_private_original_provider_bundle import SOURCES
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"pack.zip"
            raw=b"AUTHORED RESOURCE ONLY"
            identity={
                "id":"private-all-original-events-with-rocket-source-art",
                "sha256":hashlib.sha256(json.dumps(SOURCES,sort_keys=True).encode()).hexdigest()
            }
            manifest={"source_identity":identity,
                      "data_file":"source.bin",
                      "resources":[{"id":"fixture","offset":0,"length":len(raw),
                                    "sha256":hashlib.sha256(raw).hexdigest()}]}
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("manifest.json",json.dumps(manifest))
                z.writestr("source.bin",raw)
            self.assertEqual(r68.host_pages(path)["fixture"],raw)
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("manifest.json",json.dumps(manifest))
                z.writestr("source.bin",raw[:-1]+b"X")
            with self.assertRaisesRegex(r68.ResourceClosureError,"SHA"):
                r68.host_pages(path)

if __name__=="__main__":unittest.main()
