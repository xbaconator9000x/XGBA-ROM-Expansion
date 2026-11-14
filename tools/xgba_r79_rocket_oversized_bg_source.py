#!/usr/bin/env python3
"""R79 — private FULL 480-tile Rocket source preservation + bounded native view.

Exact-owner source only: pinned original Rocket v3.06 ROM; no original bytes,
source pack or game image may be put into public GitHub. Original graphics
beyond the native 384-tile secondary BG limit are preserved in a separate
SHA-authenticated resource instead of silently discarded. This proves static
metatile render reachability and NULL tileset callback, NOT arbitrary scripts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib
import xgba_r53_original_tileset_packs as r53

SOURCE_SHA="5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca"
GRAPHICS_SHA="e850da1f22da1b3bff80750b1c2c65d4607589681d2c9189b39d1719eede7835"
DESCRIPTOR=0x00ea0300
WORLD,VERSION=1,2
CORE_TILES=384
SOURCE_TILES=480
METATILES=196
PAGE=16384
STEM="r53.w1.v2.t00ea0300"
class SourceCapacityError(ValueError):pass

def validate_full_source_graphics(graphics:bytes,metatiles:bytes,callback:int):
    """Independent safe static reachability proof; wholly authored fixtures OK."""
    if len(graphics)!=SOURCE_TILES*32 or len(metatiles)!=METATILES*16:
        raise SourceCapacityError("Wrong original graphics/metatile dimensions")
    if callback!=0:
        raise SourceCapacityError("Source tileset has a runtime animation callback")
    refs=struct.unpack("<"+str(len(metatiles)//2)+"H",metatiles)
    secondary=[(entry&1023)-640 for entry in refs if (entry&1023)>=640]
    if not secondary:
        raise SourceCapacityError("No genuine original secondary tiles referenced")
    maximum=max(secondary)
    if maximum>=CORE_TILES:
        raise SourceCapacityError("Source metatiles use tiles beyond the GBA native allocation")
    return {"source_tiles":SOURCE_TILES,"native_render_tiles":CORE_TILES,
            "source_unused_tail_tiles":SOURCE_TILES-CORE_TILES,
            "max_static_secondary_tile_index":maximum,
            "tile_animation_callback":callback,
            "static_reachability_valid":True,
            "general_script_vram_writes_proven_absent":False}

def authenticate_original_descriptor(rom:bytes):
    if hashlib.sha256(rom).hexdigest()!=SOURCE_SHA:
        raise SourceCapacityError("Wrong complete original Rocket 3.06 ROM SHA-256")
    desc=rom[DESCRIPTOR:DESCRIPTOR+24]
    if len(desc)!=24 or desc[:4]!=bytes((1,1,0,0)):
        raise SourceCapacityError("Original secondary compressed descriptor changed")
    gp,pp,mp,ap,callback=struct.unpack_from("<5I",desc,4)
    if callback:
        raise SourceCapacityError("Original source tileset animation callback is not NULL")
    def offset(raw,size):
        at=raw-0x08000000
        if raw<0x08000000 or at<0 or at+size>len(rom):
            raise SourceCapacityError("Original ROM graphic pointer out of bounds")
        return at
    g_at=offset(gp,8)
    try:
        graphics=r53.gba_lz77(rom,g_at) if rom[g_at]==0x10 else r53.smol.decode(
            rom,g_at,max_output=65536)
    except (r53.TilesetFormatError,r53.smol.SmolError) as err:
        raise SourceCapacityError("Original compressed source rejected: "+str(err)) from err
    if hashlib.sha256(graphics).hexdigest()!=GRAPHICS_SHA:
        raise SourceCapacityError("Original full 480-tile source graphics SHA mismatch")
    metatiles=rom[offset(mp,METATILES*16):][:METATILES*16]
    attrs=rom[offset(ap,METATILES*2):][:METATILES*2]
    if ap-0x08000000 + METATILES*2 != mp-0x08000000:
        raise SourceCapacityError("Original source attribute/metatile span not contiguous")
    palettes=rom[offset(pp,13*32)+7*32:][:6*32]
    proof=validate_full_source_graphics(graphics,metatiles,callback)
    if proof["max_static_secondary_tile_index"]!=341:
        raise SourceCapacityError("Original static metatile reachability witness changed")
    proof["original_source_graphics_sha256"]=GRAPHICS_SHA
    proof["original_source_rom_sha256"]=SOURCE_SHA
    proof["original_descriptor"]=f"0x{DESCRIPTOR:08x}"
    proof["original_descriptor_crc32"]=zlib.crc32(desc)&0xffffffff
    return graphics,metatiles,attrs,palettes,proof

def native_source_meta(graphics,metatiles,attrs,palettes,desc_crc):
    sections=(graphics[:CORE_TILES*32],metatiles,attrs,palettes)
    head=bytearray(64)
    head[:4]=b"X53T"
    head[4:8]=bytes((WORLD,VERSION,1,1))
    struct.pack_into("<5I",head,8,DESCRIPTOR,*map(len,sections))
    struct.pack_into("<2H",head,28,CORE_TILES,METATILES)
    head[32:38]=bytes((2,6,1,1,1,1))
    for i,part in enumerate(sections):
        struct.pack_into("<I",head,40+i*4,zlib.crc32(part)&0xffffffff)
    struct.pack_into("<I",head,56,desc_crc)
    struct.pack_into("<I",head,60,zlib.crc32(head[:60])&0xffffffff)
    return [(STEM+".meta",bytes(head))]+[
        (STEM+"."+kind+"00",part.ljust(PAGE,b"\0"))
        for kind,part in zip("gmap",sections)]

def extend_private_pack(parent:Path,original_rom:Path,dest:Path):
    if dest.exists():
        raise SourceCapacityError("Refuse overwriting owner-private original resource pack")
    rom=original_rom.read_bytes()
    graphics,metatiles,attrs,palettes,proof=authenticate_original_descriptor(rom)
    with zipfile.ZipFile(parent) as z:
        manifest=json.loads(z.read("manifest.json"))
        payload=bytearray(z.read(manifest["data_file"]))
        names=set()
        entries=list(manifest["resources"])
        ranges=[]
        for e in entries:
            ident=e["id"]
            lo=e["offset"];size=e["length"]
            if ident in names or not 1<=size<=PAGE or lo<0 or lo+size>len(payload):
                raise SourceCapacityError("Corrupt/overlapping original pack index")
            names.add(ident);ranges.append((lo,lo+size))
            if hashlib.sha256(payload[lo:lo+size]).hexdigest()!=e["sha256"]:
                raise SourceCapacityError("Original parent resource hash differs")
        ranges.sort()
        if any(ranges[i][1]>ranges[i+1][0] for i in range(len(ranges)-1)):
            raise SourceCapacityError("Original parent host resource ranges overlap")
    def append(name,data):
        if name in names or not 1<=len(data)<=PAGE:
            raise SourceCapacityError("Duplicate/new oversized native resource")
        at=len(payload);payload.extend(data);names.add(name)
        entries.append({"id":name,"offset":at,"length":len(data),
                        "sha256":hashlib.sha256(data).hexdigest()})
    for name,data in native_source_meta(graphics,metatiles,attrs,palettes,
                                        proof["original_descriptor_crc32"]):
        append(name,data)
    # Native consumes only g00's 384 referenced tiles, while the original
    # *complete* 480 tiles remain byte-for-byte preserved in the PRIVATE pack.
    append(STEM+".full_original00",graphics.ljust(PAGE,b"\0"))
    append(STEM+".original_tail00",graphics[CORE_TILES*32:].ljust(PAGE,b"\0"))
    manifest["resources"]=entries
    with zipfile.ZipFile(dest,"x",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(manifest["data_file"],payload)
        z.writestr("manifest.json",json.dumps(manifest,sort_keys=True)+"\n")
        z.writestr("r79-private-source-reachability.json",
                   json.dumps({**proof,
                    "whole_original_graphics_retained_privately":True,
                    "native_gameplay_accepted":False,
                    "no_public_original_bytes":True},indent=2))
    with zipfile.ZipFile(dest) as z:
        m=json.loads(z.read("manifest.json"));data=z.read(m["data_file"])
        for e in m["resources"]:
            if hashlib.sha256(data[e["offset"]:e["offset"]+e["length"]]).hexdigest()!=e["sha256"]:
                raise SourceCapacityError("Output SHA-verification failed")
        assert m["resources"][-7]["id"]==STEM+".meta"
    return {**proof,"old_resources":len(entries)-7,"new_resources":7,
            "all_resources_sha256_valid":len(entries),
            "source_full_original_480_tiles_still_retained":True,
            "actual_native_foreign_warp_completed":False}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--parent-private-pack",type=Path,required=True)
    a.add_argument("--original-rocket",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    opts=a.parse_args()
    print(json.dumps(extend_private_pack(opts.parent_private_pack,
              opts.original_rocket,opts.out),indent=2,sort_keys=True))
if __name__=="__main__":main()
