#!/usr/bin/env python3
"""R51 private THREE-original-ROM terrain/collision grid pack for native Emerald.

Preserves every populated original source map's raw 16-bit map cells and
eight-byte border, original dimensions, pointers, source identity and CRC.
All data stay PRIVATE; GitHub CI uses authored small-fixture bytes only.
A 16 KiB XGBA page is a transfer unit, NOT a map size limit: a large original
map may span any number of pages. Guest staging of unsupported large maps
must refuse without dropping those maps from this source store.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

import xgba_resource_sidecar as sidecar

PAGE=16384
INDEX_FORMAT="<IHHIIIIII"
INDEX_SIZE=struct.calcsize(INDEX_FORMAT)
assert INDEX_SIZE==32 and PAGE%INDEX_SIZE==0
SOURCES={
 "emerald": ("a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af",518,0),
 "rocket": ("5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca",1778,0),
 "heart_soul": ("cdfb9e1f83f72c05cb47af40fdf5635567b1973bcb759e070ad0971f67a49191",560,935),
}
# Byte-exact map-group pointer roots verified against the THREE SHA-pinned
# original user-owned images. Group arrays are packed contiguously, and the
# final group's pointer table ends immediately before its root pointer table.
# This avoids false positive layout candidates from unrelated ROM code/data.
ORIGINAL_GROUP_ROOTS={
 "emerald":(0x00486578,34,0x00485d60),
 "rocket":(0x013f1a44,75,0x013efe7c),
 "heart_soul":(0x012df5a4,106,0x012dde48),
}
EXPECTED_MAPS=2856
EXPECTED_NULL_SLOTS=935
# Native Emerald uses (width+15)*(height+14) cells in its backup grid;
# this threshold is NOT a filter for what the immutable source store retains.
GUEST_GRID_CAPACITY=5600

class OriginalGridError(ValueError):
    pass

def _pages(data):
    return [data[i:i+PAGE].ljust(PAGE,b"\x00") for i in range(0,len(data),PAGE)]

def pack_original_grids(sources,*,require_complete=True):
    """sources = {name: (original_rom_bytes, validated_r34_discovery)}.
    Returns (index_pages, terrain_pages, metadata) without ever rewriting ROMs.
    """
    if set(sources)!=set(SOURCES):
        raise OriginalGridError("All three original source namespaces required")
    data=bytearray()
    rows=[]
    source_counts={}
    total_nulls=0
    guest_fit=0
    for world,(name,(sha,expected,expected_nulls)) in enumerate(SOURCES.items()):
        blob,parsed=sources[name]
        if hashlib.sha256(blob).hexdigest()!=sha:
            raise OriginalGridError(name+": SHA-256 of original complete ROM differs")
        maps=sorted(parsed["maps"],key=lambda m:(m["group"],m["map"]))
        holes=parsed["null_slot_count"]
        if require_complete and (len(maps)!=expected or holes!=expected_nulls):
            raise OriginalGridError(name+": missing original maps or null-map holes")
        total_nulls+=holes
        for m in maps:
            group,number=int(m["group"]),int(m["map"])
            w,h=int(m["width"]),int(m["height"])
            begin=int(m["map_grid_offset"])
            border_at=int(m["border_offset"])
            size=w*h*2
            if not (0<=group<=255 and 0<=number<=255 and 1<=w<=2048 and 1<=h<=2048):
                raise OriginalGridError("Invalid original source map key/geometry")
            if size!=m["map_grid_bytes"] or size>len(blob) or begin<0 or begin+size>len(blob):
                raise OriginalGridError("Original grid pointer/bounds mismatch")
            if border_at<0 or border_at+8>len(blob):
                raise OriginalGridError("Original border pointer/bounds mismatch")
            key=(world<<16)|(group<<8)|number
            if rows and key<=rows[-1][0]:
                raise OriginalGridError("Unsorted/duplicate original source map identity")
            segment=blob[begin:begin+size]+blob[border_at:border_at+8]
            if len(data)>0xffffffff-len(segment):
                raise OriginalGridError("Original complete source data exceeds uint32 byte index")
            rows.append((key,w,h,len(data),size,begin,border_at,
                         zlib.crc32(segment)&0xffffffff,int(m["header_offset"])))
            data.extend(segment)
            if size+8<=GUEST_GRID_CAPACITY and (w+15)*(h+14)<=0x2800:
                guest_fit+=1
        source_counts[name]={"maps":len(maps),"original_null_slots":holes,
                              "source_sha256":sha}
    if require_complete and (len(rows)!=EXPECTED_MAPS or total_nulls!=EXPECTED_NULL_SLOTS):
        raise OriginalGridError("Original three-world catalog incomplete")
    index=b"".join(struct.pack(INDEX_FORMAT,*entry) for entry in rows)
    index_pages=_pages(index)
    terrain_pages=_pages(data)
    if len(index_pages)>999 or len(terrain_pages)>99999:
        raise OriginalGridError("R51 resource ID paging exhausted")
    stats={"maps":len(rows),"original_null_map_slots":total_nulls,
           "source_counts":source_counts,"index_pages":len(index_pages),
           "terrain_pages":len(terrain_pages),"terrain_bytes":len(data),
           "native_guest_fit_maps":guest_fit,
           "complete_original_bytes_preserved":True,
           "original_engine_foreign_map_rendered":False,
           "actual_three_world_fly_completed":False}
    return index_pages,terrain_pages,stats

def _original_rom_ptr(blob, value, needed=1):
    """Original physical cart pointer: handle 16 and 32 MiB ROMs equally."""
    at=value-0x08000000
    if value<0x08000000 or not 0<=at<=len(blob)-needed:
        raise OriginalGridError("Original ROM map pointer is out of range")
    return at


def discover_original_geometries(blob, root_offset, group_count,
                                  expected_map_count, expected_null_count,
                                  expected_first_group):
    """Deterministically scan the authenticated *original* packed map tables.

    Source-specific game events/scripts are NOT parsed or translated here;
    only the raw original 24-byte MapLayout prefix and eight-byte border
    are read. Source engine variant bytes are separately retained in R52.
    """
    if not isinstance(blob,(bytes,bytearray)) or root_offset%4 or \
       not 1<=group_count<=255 or root_offset+4*group_count>len(blob):
        raise OriginalGridError("Original map-group table bounds invalid")
    group_starts=[]
    for group in range(group_count):
        pointer=struct.unpack_from("<I",blob,root_offset+group*4)[0]
        offset=_original_rom_ptr(blob,pointer,4)
        if offset>=root_offset or offset%4 or \
           (group_starts and offset<=group_starts[-1]):
            raise OriginalGridError("Source map pointer-group array not packed/ordered")
        group_starts.append(offset)
    if group_starts[0]!=expected_first_group:
        raise OriginalGridError("Authenticated source first map-group root drift")
    roster=[]
    holes=0
    total=0
    for group,start in enumerate(group_starts):
        end=group_starts[group+1] if group+1<group_count else root_offset
        if end<start or (end-start)%4 or not 1<=(end-start)//4<=255:
            raise OriginalGridError("Original source group-map count invalid")
        for number,off in enumerate(range(start,end,4)):
            raw=struct.unpack_from("<I",blob,off)[0]
            total+=1
            if raw==0:
                holes+=1
                continue
            header_offset=_original_rom_ptr(blob,raw,4)
            layout_ptr=struct.unpack_from("<I",blob,header_offset)[0]
            layout_offset=_original_rom_ptr(blob,layout_ptr,24)
            w,h,border,grid,primary,secondary=struct.unpack_from(
                "<6I",blob,layout_offset)
            if not 1<=w<=2048 or not 1<=h<=2048:
                raise OriginalGridError("Original map dimensions outside source contract")
            size=w*h*2
            border_offset=_original_rom_ptr(blob,border,8)
            map_grid_offset=_original_rom_ptr(blob,grid,size)
            _original_rom_ptr(blob,primary,24)
            _original_rom_ptr(blob,secondary,24)
            roster.append({"group":group,"map":number,"width":w,"height":h,
             "map_grid_offset":map_grid_offset,"border_offset":border_offset,
             "map_grid_bytes":size,"header_offset":header_offset,
             "layout_offset":layout_offset})
    if (len(roster)!=expected_map_count or holes!=expected_null_count or
        total!=expected_map_count+expected_null_count):
        raise OriginalGridError("Source original populated/null map count mismatch")
    return {"maps":roster,"null_slot_count":holes,
            "original_map_slots":total,"original_group_count":group_count}


def from_three_original_roms(paths):
    sources={}
    for name,(sha,expected,expected_nulls) in SOURCES.items():
        path=Path(paths[name])
        blob=path.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=sha:
            raise OriginalGridError("Unrecognized original complete source: "+name)
        root,groups,first=ORIGINAL_GROUP_ROOTS[name]
        parsed=discover_original_geometries(blob,root,groups,expected,
                                            expected_nulls,first)
        sources[name]=(blob,parsed)
    return pack_original_grids(sources)

def write_private_pages(index,terrain,stats,out_dir):
    out=Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise OriginalGridError("Private destination must be empty")
    out.mkdir(parents=True,exist_ok=True)
    manifest={"format":sidecar.FORMAT,"version":sidecar.VERSION,
      "source_identity":{"id":"private-original-three-world-grids",
        "sha256":hashlib.sha256("".join(SOURCES[n][0] for n in SOURCES).encode()).hexdigest()},
      "data_file":"private-r51-original-terrain.bin","resources":[]}
    with (out/manifest["data_file"]).open("xb") as handle:
        for kind,pages in (("index",index),("grid",terrain)):
            for number,data in enumerate(pages):
                rid=(f"r51.index.{number:03d}" if kind=="index" else
                     f"r51.grid.{number:05d}")
                offset=handle.tell()
                handle.write(data)
                manifest["resources"].append({"id":rid,"offset":offset,
                    "length":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n")
    (out/"private-report.json").write_text(json.dumps(stats,indent=2,sort_keys=True)+"\n")
    # This is a private payload; the caller must NEVER attach to public PR/CI.
    sidecar.load_manifest(out/"manifest.json")
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in SOURCES:p.add_argument("--"+n.replace("_","-"),type=Path,required=True)
    p.add_argument("--private-out",type=Path,required=True)
    a=p.parse_args()
    paths={n:getattr(a,n) for n in SOURCES}
    idx,grids,stats=from_three_original_roms(paths)
    manifest=write_private_pages(idx,grids,stats,a.private_out)
    print(json.dumps({"native_original_grid_pack":True,"maps":stats["maps"],
      "source_grids_exact_and_private":True,
      "external_pages":len(manifest["resources"]),
      "foreign_fly_actually_executed":False},sort_keys=True))

if __name__=="__main__":
    main()
