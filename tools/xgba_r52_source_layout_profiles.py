#!/usr/bin/env python3
"""R52: source-exact versioned layout ABI for ALL 2,856 three-ROM maps.

R51 preserved the original 16-bit map cells but did not retain the distinct
post-24-byte layoutVersion fields in Rocket/HnS. That is an engine-blocking
ABI distinction: original Emerald uses the old 512/512 tileset split and
u16 attributes, while HnS/FRLG family version 2 uses 640/384 and u32
metatile attributes. No native foreign renderer may use the wrong split.

Reads PRIVATE user-owned original ROMs and R51 index bytes; outputs a small
source-qualified 32-byte/map profile table as SHA-backed 16KiB pages.
Never exports ROM images, private tiles, palettes, metatiles or dialogues.
"""
from __future__ import annotations
import argparse
import binascii
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import zipfile

PAGE=16384
ROW=32
ALL_MAPS=2856
SOURCE_NAMES=("emerald","rocket","heart_soul")
EXPECTED_SHA=(
 "a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af",
 "5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca",
 "cdfb9e1f83f72c05cb47af40fdf5635567b1973bcb759e070ad0971f67a49191",
)
LAYOUT_ROW="<I4BHH4BIIII"
assert struct.calcsize(LAYOUT_ROW)==ROW
class LayoutProfileError(ValueError): pass

def _u32(data,off):
    return struct.unpack_from("<I",data,off)[0]

def _ptr(rom,raw,minimum):
    off=raw-0x08000000
    if not 0<=off<=len(rom)-minimum:raise LayoutProfileError("Map layout/tileset source pointer out of bounds")
    return off

def extract_profiles(original_roms:tuple[bytes,...],r51_index:bytes,*,require_complete=True):
    if len(original_roms)!=3 or not len(r51_index)>=ROW*ALL_MAPS:
        raise LayoutProfileError("Missing three source ROMs or incomplete R51 source index")
    for world,(blob,expected) in enumerate(zip(original_roms,EXPECTED_SHA)):
        if hashlib.sha256(blob).hexdigest()!=expected:
            raise LayoutProfileError(f"{SOURCE_NAMES[world]}: complete original ROM SHA mismatch")
    rows=[]
    variants={name:Counter() for name in SOURCE_NAMES}
    source_maps=Counter()
    unsupported=[]
    previous=-1
    for i in range(ALL_MAPS):
        key,w,h,_,grid_bytes,_,_,_,header_off=struct.unpack_from("<IHHIIIIII",r51_index,ROW*i)
        world=key>>16
        if world>2 or key<=previous:raise LayoutProfileError("R51 source map key missing, unsorted or duplicate")
        previous=key
        rom=original_roms[world]
        if not 0<=header_off<=len(rom)-28:raise LayoutProfileError("Original map header offset missing")
        layout_off=_ptr(rom,_u32(rom,header_off),28 if world!=0 else 24)
        original_width,original_height=struct.unpack_from("<II",rom,layout_off)
        if (original_width,original_height)!=(w,h) or grid_bytes!=w*h*2:
            raise LayoutProfileError("Original header geometry differs from R51 indexed grid")
        p_off=_ptr(rom,_u32(rom,layout_off+16),24)
        s_off=_ptr(rom,_u32(rom,layout_off+20),24)
        if world==0:
            version=border_w=border_h=extra=0
        else:
            version,border_w,border_h,extra=rom[layout_off+24:layout_off+28]
        # Version 3 and malformed FRLG-style borders are deliberately retained
        # but not declared compatible with the original Emerald engine.
        known_version=version in (0,1,2)
        has_valid_border=(version!=1 or 1<=border_w<=64 and 1<=border_h<=64)
        supported_schema=known_version and has_valid_border
        primary=640 if version in (1,2) else 512
        pal=7 if version in (1,2) else 6
        attr_width=4 if version==1 else 2
        flags=(int(supported_schema) | (int(version in (1,2))<<1))
        packed=struct.pack(LAYOUT_ROW,key,version,border_w,border_h,extra,
            primary,primary,pal,attr_width,flags,
            (rom[p_off]&1)|((rom[s_off]&1)<<1),layout_off,p_off,s_off,0)
        check=binascii.crc32(packed[:-4])&0xffffffff
        packed=packed[:-4]+struct.pack("<I",check)
        rows.append(packed)
        variants[SOURCE_NAMES[world]][version]+=1
        source_maps[SOURCE_NAMES[world]]+=1
        if not supported_schema:
            unsupported.append({"source":SOURCE_NAMES[world],"group":(key>>8)&255,
              "map":key&255,"layout_version":version,
              "border_dimensions":[border_w,border_h]})
    if require_complete and (len(rows)!=ALL_MAPS or
       tuple(source_maps[n] for n in SOURCE_NAMES)!=(518,1778,560)):
        raise LayoutProfileError("Full three-ROM original-source map roster incomplete")
    raw=b"".join(rows)
    pages=[raw[i:i+PAGE].ljust(PAGE,b"\0") for i in range(0,len(raw),PAGE)]
    report={"maps":len(rows),"profiles_sha256":hashlib.sha256(raw).hexdigest(),
      "variants":{name:{str(k):v for k,v in sorted(variants[name].items())}
                  for name in SOURCE_NAMES},
      "unknown_or_unsafe_layouts":unsupported,
      "pages":len(pages),
      "r51_original_map_geometry_retained":True,
      "source_original_graphics_compatibility_verified":False,
      "actual_interworld_fly_executed":False}
    return pages,report

def export_profiles(pages,report,out):
    out=Path(out)
    if out.exists() and any(out.iterdir()):
        raise LayoutProfileError("Private profile destination must be empty")
    out.mkdir(parents=True,exist_ok=True)
    payload=b"".join(pages)
    (out/"r52-private-source-map-profiles.bin").write_bytes(payload)
    resources=[]
    for i,p in enumerate(pages):
        resources.append({"id":f"r52.mapmeta.{i:03d}","offset":i*PAGE,
            "length":PAGE,"sha256":hashlib.sha256(p).hexdigest()})
    manifest={"format":"xgba-resource-manifest","version":1,
      "source_identity":{"id":"private-three-rom-source-layouts",
         "sha256":hashlib.sha256("".join(EXPECTED_SHA).encode()).hexdigest()},
      "data_file":"r52-private-source-map-profiles.bin","resources":resources}
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n")
    (out/"report.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in SOURCE_NAMES:p.add_argument("--"+n.replace("_","-"),type=Path,required=True)
    p.add_argument("--r51-terrain-pack",type=Path,required=True)
    p.add_argument("--private-out",type=Path,required=True)
    args=p.parse_args()
    originals=tuple(getattr(args,name).read_bytes() for name in SOURCE_NAMES)
    with zipfile.ZipFile(args.r51_terrain_pack) as z:
        # The first six pages are always R51 source-qualified index records.
        index=z.read("private-r51-original-terrain.bin")[:ALL_MAPS*ROW]
    pages,report=extract_profiles(originals,index)
    export_profiles(pages,report,args.private_out)
    print(json.dumps({"status":"PASS_R52_PRIVATE_ORIGINAL_VERSIONED_LAYOUTS",
      "maps":report["maps"],"variants":report["variants"],
      "unknown_or_unsafe":len(report["unknown_or_unsafe_layouts"]),
      "actual_fly":False},sort_keys=True))

if __name__=="__main__":
    main()
