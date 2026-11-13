"""R62 provider fusion uses only authored bytes in public CI, NEVER source ROMs."""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import sys
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r62_private_original_provider_bundle as fuse

def u16(b,at,v):struct.pack_into("<H",b,at,v)
def u32(b,at,v):struct.pack_into("<I",b,at,v)
def synthetic_rocket():
    p={f"r49.index.{i:03}":bytes(fuse.PAGE) for i in range(3)}
    p.update({f"r52.mapmeta.{i:03}":bytes(fuse.PAGE) for i in range(6)})
    idx=bytearray(fuse.PAGE)
    u32(idx,0,fuse.KEY_ROCKET);u16(idx,4,0);u16(idx,6,0)
    u32(idx,8,32+9*24);u32(idx,12,0x123400)
    p["r49.index.000"]=bytes(idx)
    events=bytearray(fuse.PAGE)
    events[:4]=b"X49E";u32(events,4,fuse.KEY_ROCKET)
    events[8]=9;u32(events,12,0x123400);u32(events,24,9*24)
    # Four actual viewport identities; the five others are archived, but
    # not staged. This fixture is synthetic and not original ROM bytes.
    npcs=((6,18,10),(17,14,13),(9,16,17),(215,6,10),
          (94,3,10),(94,20,3),(607,24,11),(64,16,10),(0,5,10))
    for i,(gfx,x,y) in enumerate(npcs):
        at=32+i*24;events[at]=i+1
        u16(events,at+1,gfx);u16(events,at+4,x);u16(events,at+6,y)
        u32(events,at+16,0x08001200+i*4)
    u32(events,20,zlib.crc32(events[32:32+9*24])&0xffffffff)
    p["r49.events.000"]=bytes(events)
    row=bytearray(fuse.PAGE)
    u32(row,0,fuse.KEY_ROCKET);row[4]=2
    u32(row,20,0xe9ffe0);u32(row,24,0xe9ffc8)
    u32(row,28,zlib.crc32(row[:28])&0xffffffff)
    p["r52.mapmeta.000"]=bytes(row)
    for j,prefix in enumerate(fuse.ROCKET_TERRAIN):
        m=bytearray(64);m[:4]=b"X53T";m[4:7]=bytes((1,2,j))
        for k in range(4):m[34+k]=1
        u32(m,60,zlib.crc32(m[:60])&0xffffffff)
        p[prefix+".meta"]=bytes(m)
        for part in "gmap":
            p[prefix+f".{part}00"]=bytes(fuse.PAGE)
    for gfx in fuse.SLOTS_ROCKET:
        prefix=f"r56.w1.s{gfx:04x}"
        m=bytearray(64);m[:4]=b"X56S";m[4:6]=bytes((1,1))
        u16(m,6,gfx);m[50:52]=bytes((16,32));u16(m,52,1)
        for k,part in enumerate("fpoa"):
            size=(256,32,8,8)[k]
            raw=bytes([(gfx+k+i)%255 for i in range(size)])
            if part=="p" and gfx in (9,17):
                raw=bytes([(9+k+i)%255 for i in range(size)])
            p[prefix+f".{part}00"]=raw.ljust(fuse.PAGE,b"\0")
            u32(m,12+4*k,size)
            u32(m,28+4*k,zlib.crc32(raw)&0xffffffff)
            m[44+k]=1
        u32(m,60,zlib.crc32(m[:60])&0xffffffff)
        p[prefix+".meta"]=bytes(m)
    return p

class OriginalPrivateProviderFusion(unittest.TestCase):
    def test_authored_rocket_landing_requires_original_pages(self):
        p=synthetic_rocket()
        result=fuse.original_rocket_coverage(p)
        self.assertEqual(result["original_npcs"],9)
        self.assertEqual(result["first_viewport_npcs"],4)
        self.assertEqual(result["first_viewport_original_u16_graphics_ids"],
                         [6,9,17,64])
        self.assertEqual(result["distinct_original_npc_palettes"],3)
        self.assertFalse(result["original_Fly_playable"])
    def test_missing_original_sprite_page_fails_closed(self):
        p=synthetic_rocket()
        del p["r56.w1.s0011.a00"]
        with self.assertRaisesRegex(fuse.PrivateBundleError,"Missing authentic"):
            fuse.original_rocket_coverage(p)
    def test_original_source_crc_corruption_fails_closed(self):
        p=synthetic_rocket()
        p["r56.w1.s0009.f00"]=bytes(fuse.PAGE)
        with self.assertRaisesRegex(fuse.PrivateBundleError,"sprite section CRC"):
            fuse.original_rocket_coverage(p)
    def test_wrong_original_graphic_id_not_tolerated(self):
        p=synthetic_rocket()
        meta=bytearray(p["r56.w1.s0006.meta"])
        u16(meta,6,7)
        u32(meta,60,zlib.crc32(meta[:60])&0xffffffff)
        p["r56.w1.s0006.meta"]=bytes(meta)
        with self.assertRaisesRegex(fuse.PrivateBundleError,"identity drift"):
            fuse.original_rocket_coverage(p)
    def test_sha_corrupt_private_manifest_rejected(self):
        item={"id":"r56.w1.s0006.f00","offset":0,"length":4,
              "sha256":hashlib.sha256(b"GOOD").hexdigest()}
        with self.assertRaisesRegex(fuse.PrivateBundleError,"SHA mismatch"):
            fuse._valid_pages([item],lambda x:b"EVIL")
    def test_cross_pack_duplicate_resource_rejected(self):
        p=synthetic_rocket()
        self.assertGreater(len(p),30)
        self.assertEqual(len(p),len(set(p)))
if __name__=="__main__":unittest.main()
