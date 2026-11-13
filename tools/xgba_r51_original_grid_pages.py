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

import xgba_r34_binary_maps as r34
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

def from_three_original_roms(paths):
    sources={}
    for name,(sha,_,_) in SOURCES.items():
        path=Path(paths[name])
        blob=path.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=sha:
            raise OriginalGridError("Unrecognized original complete source: "+name)
        parsed=r34.BinaryMapDiscovery(blob).discover(
            min_root_references=1,allow_null_slots=True)
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
