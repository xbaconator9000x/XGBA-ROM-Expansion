#!/usr/bin/env python3
"""R68 original cross-world Fly resource-closure report from a PRIVATE XGBA pack.

This verifies the exact per-map resources that the original Emerald R58/R57
first-viewport loader must request. It does not inspect, print or distribute
original pixel/dialogue bytes. An eligible original-resource inventory is NOT
proof of a running original Fly, map/NPC spawn or cross-world shared save.

Run: python3 tools/xgba_r68_fly_resource_closure.py --private-pack /path/pack.zip
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

from xgba_r62_private_original_provider_bundle import SOURCES
PAGE=16384
ALL_MAPS=2856
LANDINGS={
    "rocket":{"world":1,"group":0,"map":9,"x":14,"y":14,
              "script_resource":"rocket.r48.npc"},
    "heart_soul":{"world":2,"group":0,"map":4,"x":39,"y":23,
                  "script_resource":"heart_soul.r48.npc"},
}
class ResourceClosureError(ValueError):pass
def _sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def host_pages(path:Path)->dict[str,bytes]:
    """Verify entire host resource archive against SHA and bound every page."""
    with zipfile.ZipFile(path) as z:
        m=json.loads(z.read("manifest.json"))
        if m.get("source_identity",{}).get("id")!=\
           "private-all-original-events-with-rocket-source-art" or \
           m["source_identity"].get("sha256")!=\
              _sha(json.dumps(SOURCES,sort_keys=True).encode()):
            raise ResourceClosureError("Original 3-ROM provider identity mismatch")
        data=z.read(m["data_file"])
        pages={}
        intervals=[]
        for r in m.get("resources",[]):
            if set(r)!={"id","offset","length","sha256"}:
                raise ResourceClosureError("Malformed bounded provider entry")
            rid=r["id"];start=r["offset"];size=r["length"]
            if not isinstance(rid,str) or rid in pages or \
               type(start) is not int or type(size) is not int or \
               start<0 or not 1<=size<=PAGE or start+size>len(data):
                raise ResourceClosureError("Invalid provider resource or range")
            raw=data[start:start+size]
            if _sha(raw)!=r["sha256"]:
                raise ResourceClosureError("Original provider page SHA mismatch")
            pages[rid]=raw
            intervals.append((start,start+size))
        intervals.sort()
        if any(a[1]>b[0] for a,b in zip(intervals,intervals[1:])):
            raise ResourceClosureError("Overlapping host resource boundaries")
        if not pages:raise ResourceClosureError("Empty source provider")
    return pages

def _table(pages:dict[str,bytes],prefix:str,count:int)->bytes:
    try:
        raw=b"".join(pages[f"{prefix}{i:03d}"]
                     for i in range((count+PAGE-1)//PAGE))
    except KeyError as e:
        raise ResourceClosureError("Original source index missing") from e
    if len(raw)<count:raise ResourceClosureError("Truncated source map index")
    return raw[:count]

def inspect_world(pages:dict[str,bytes],name:str)->dict:
    """Return only deterministic original IDs and missing resource names."""
    spec=LANDINGS[name]
    world,group,mapid=spec["world"],spec["group"],spec["map"]
    key=(world<<16)|(group<<8)|mapid
    rows=_table(pages,"r49.index.",ALL_MAPS*16)
    found=None
    for i in range(ALL_MAPS):
        k,pg,at,n,header=struct.unpack_from("<IHHII",rows,i*16)
        if k==key:
            if found is not None:raise ResourceClosureError("Duplicate original map")
            found=(pg,at,n)
    if found is None:raise ResourceClosureError("Missing original source map")
    pg,at,n=found
    raw=pages.get(f"r49.events.{pg:03d}",b"")[at:at+n]
    if len(raw)!=n or len(raw)<32 or raw[:4]!=b"X49E" or \
       struct.unpack_from("<I",raw,4)[0]!=key:
        raise ResourceClosureError("Original source event record invalid")
    count=raw[8]
    src=raw[32:]
    if len(src)<count*24 or \
       zlib.crc32(src)&0xffffffff!=struct.unpack_from("<I",raw,20)[0]:
        raise ResourceClosureError("Original NPC event bytes CRC invalid")
    grid=_table(pages,"r51.index.",ALL_MAPS*32)
    width=height=None
    for i in range(ALL_MAPS):
        if struct.unpack_from("<I",grid,i*32)[0]==key:
            if width is not None:raise ResourceClosureError("Duplicate original grid")
            width,height=struct.unpack_from("<HH",grid,i*32+4)
    if not width or not height or \
       spec["x"]>=width or spec["y"]>=height:
        raise ResourceClosureError("Invalid original Fly map geometry")
    rows=_table(pages,"r52.mapmeta.",ALL_MAPS*32)
    profile=None
    for i in range(ALL_MAPS):
        row=rows[i*32:(i+1)*32]
        if struct.unpack_from("<I",row)[0]==key:
            if profile is not None:raise ResourceClosureError("Duplicate original map profile")
            profile=row
    if profile is None or \
       (zlib.crc32(profile[:28])&0xffffffff)!=\
        struct.unpack_from("<I",profile,28)[0]:
        raise ResourceClosureError("Original source profile CRC invalid")
    if profile[4]!=2:
        raise ResourceClosureError("Unknown original source tile format")
    descriptors=struct.unpack_from("<II",profile,20)
    visible=[]
    for i in range(count):
        p=src[i*24:(i+1)*24]
        local=p[0];gfx=struct.unpack_from("<H",p,1)[0]
        x,y=struct.unpack_from("<hh",p,4)
        if 0<=x<width and 0<=y<height and \
           abs(x-spec["x"])<=7 and abs(y-spec["y"])<=5:
            visible.append((local,gfx,x,y))
    graphics=sorted({rec[1] for rec in visible})
    required={spec["script_resource"]}
    for gfx in graphics:
        prefix=f"r56.w{world}.s{gfx:04x}"
        required.update({prefix+".meta"}|
                        {prefix+"."+s+"00" for s in "fpoa"})
    for desc in descriptors:
        prefix=f"r53.w{world}.v{profile[4]}.t{desc:08x}"
        required.add(prefix+".meta")
        meta=pages.get(prefix+".meta")
        if meta is not None:
            if len(meta)<64 or meta[:4]!=b"X53T" or \
               zlib.crc32(meta[:60])&0xffffffff!=\
                 struct.unpack_from("<I",meta,60)[0]:
                raise ResourceClosureError("Authentic original tileset metadata CRC failed")
            for section,n in zip("gmap",meta[34:38]):
                required.update(f"{prefix}.{section}{i:02d}"
                                for i in range(n))
    missing=sorted(required-set(pages))
    return {
        "world":world,"original_map_key":f"0x{key:06x}",
        "width":width,"height":height,
        "original_npcs_on_map":count,
        "first_view_npcs":len(visible),
        "first_view_original_gfx_ids":graphics,
        "first_view_original_local_ids":[x[0] for x in visible],
        "source_tileset_descriptor_offsets":[f"0x{v:08x}" for v in descriptors],
        "required_original_resource_count":len(required),
        "missing_original_resource_count":len(missing),
        "missing_original_resource_ids":missing,
        "original_host_resource_closure":not missing,
        "native_emerald_cross_world_fly_proven":False,
    }

def analyze_pack(path:Path)->dict:
    pages=host_pages(path)
    results={name:inspect_world(pages,name) for name in LANDINGS}
    return {
        "source_rom_sha256":SOURCES,
        "verified_host_pages":len(pages),
        "worlds":results,
        "three_world_native_emerald_playthrough_proven":False,
        "contains_original_sprite_or_dialogue_bytes_in_report":False,
    }
def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--private-pack",type=Path,required=True)
    a.add_argument("--report",type=Path,default=None,
                   help="Optional source-safe metadata JSON destination")
    args=a.parse_args()
    result=analyze_pack(args.private_pack)
    rendered=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.report:
        args.report.write_text(rendered)
    print(rendered,end="")
if __name__=="__main__":main()
