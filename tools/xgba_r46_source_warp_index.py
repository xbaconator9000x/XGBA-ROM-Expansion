#!/usr/bin/env python3
"""R46: build original, source-scoped map/warp routing tables from 1–3 user ROMs.

This is executable input for the engine's xgba_r46_source_warps.h resolver.
It preserves (source, original_group, original_map) identities, original
intra-world warp indices, destinations, dimensions, and actual ROM header
offsets. It does NOT insert fictional cross-world transitions: explicit
portals must be authored separately. It is NOT a claim of native GBA warp
execution in the actual original Emerald map engine.

All source binaries and extracted warp tables stay PRIVATE. Public CI
generates only independently authored synthetic fixtures.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

import xgba_r34_binary_maps as r34

SOURCE_IDS={"emerald":0,"rocket":1,"heart_soul":2}
MAP_FORMAT="<IHHHHI"    # xgba_r46_source_warps.h struct XgbaR46Map
WARP_FORMAT="<hhBBBB"   # xgba_r46_source_warps.h struct XgbaR46Warp
PAGE=16384
MAX_ROM=64*1024*1024


class WarpIndexError(ValueError):
    pass


def parse_source(item):
    if "=" not in item:raise WarpIndexError("Use --source emerald=/private/file.gba")
    name,value=item.split("=",1)
    if name not in SOURCE_IDS or not value:
        raise WarpIndexError("Source must be emerald, rocket or heart_soul")
    return name,Path(value)


def map_key(source,group,map_number):
    if source not in SOURCE_IDS or not (0<=group<=255 and 0<=map_number<=255):
        raise WarpIndexError("Original map group/number exceeds native key")
    return (SOURCE_IDS[source]<<16)|(group<<8)|map_number


def build_indexes(sources):
    if not 1<=len(sources)<=3 or len({s for s,_ in sources})!=len(sources):
        raise WarpIndexError("Use 1–3 unique original source worlds")
    maps=[]
    warps=[]
    source_reports={}
    source_owners={}
    for source,path in sorted(sources,key=lambda x:SOURCE_IDS[x[0]]):
        if not path.is_file() or not 192<=path.stat().st_size<=MAX_ROM:
            raise WarpIndexError("Missing/oversize private source ROM")
        rom=path.read_bytes()
        engine=r34.BinaryMapDiscovery(rom)
        discovered=engine.discover(min_root_references=1,allow_null_slots=True)
        parsed=discovered["maps"]
        records={}
        for m in parsed:
            key=map_key(source,m["group"],m["map"])
            if key in records:raise WarpIndexError("Duplicate ORIGINAL source map")
            count=m["warp_count"]
            off=m["event_array_offsets"][1]
            if count and (off is None or off<0 or off+count*8>len(rom)):
                raise WarpIndexError("Warp array violates actual ROM bounds")
            if count>255:raise WarpIndexError("GBA original warp count too large")
            if m["width"]>65535 or m["height"]>65535:
                raise WarpIndexError("Original GBA layout dimension exceeds native range")
            records[key]=(m,[
                struct.unpack_from(WARP_FORMAT,rom,off+8*i)
                for i in range(count)])
        source_owners[source]=records
        source_reports[source]={
            "rom_sha256":hashlib.sha256(rom).hexdigest(),
            "original_map_group_root_offset":discovered["table_offset"],
            "original_populated_map_count":len(records),
            "original_zero_pointer_slots":discovered["null_slot_count"],
            "original_numeric_slots":discovered["slot_count"],
            "original_warp_count":sum(len(v[1]) for v in records.values()),
            "world_isolated":True,
        }
    # Sort by the full 24-bit source-aware key. A colliding numeric
    # (group,map) in another world must have a DIFFERENT key and warp range.
    for source in sorted(source_owners,key=lambda s:SOURCE_IDS[s]):
        for key,(m,original_warps) in sorted(source_owners[source].items()):
            maps.append((key,m["width"],m["height"],len(warps),len(original_warps),m["header_offset"]))
            warps.extend(original_warps)
    if len(maps)>65535 or len(warps)>65535:
        raise WarpIndexError("Original source index exceeds bounded native table capacity")
    count=Counter()
    for source in sorted(source_owners,key=lambda s:SOURCE_IDS[s]):
        for key,(m,original_warps) in sorted(source_owners[source].items()):
            for _,_,elevation,dest_warp,dest_map,dest_group in original_warps:
                if dest_group==127 and dest_map==127:
                    count["dynamic_original_destination"]+=1
                    continue
                dest_key=map_key(source,dest_group,dest_map)
                dest=source_owners[source].get(dest_key)
                if dest is None:
                    count["missing_or_null_original_destination"]+=1
                elif dest_warp>=len(dest[1]):
                    count["invalid_or_special_original_destination_warp_index"]+=1
                else:
                    count["source_local_warp_resolves"]+=1
    binary_maps=b"".join(struct.pack(MAP_FORMAT,*m) for m in maps)
    binary_warps=b"".join(struct.pack(WARP_FORMAT,*w) for w in warps)
    if len(binary_maps)!=16*len(maps) or len(binary_warps)!=8*len(warps):
        raise AssertionError("C ABI packed header size changed")
    if len(set(row[0] for row in maps))!=len(maps) or any(a[0]>=b[0] for a,b in zip(maps,maps[1:])):
        raise WarpIndexError("Source-aware native map table not strictly ordered")
    report={
        "phase":"R46_ACTUAL_SOURCE_SCOPED_ORIGINAL_MAP_WARP_ENGINE_INPUT",
        "native_original_emerald_overworld_warps_executed":False,
        "original_pokemon_multi_world_party_events_saves_playable":False,
        "source_originals_preserved_no_mutation":True,
        "original_map_ids_not_renumbered":True,
        "original_warps_not_redirected_to_other_source":True,
        "explicit_cross_world_portal_definitions":0,
        "world_count":len(source_owners),
        "map_records":len(maps),
        "warp_records":len(warps),
        "map_binary_sha256":hashlib.sha256(binary_maps).hexdigest(),
        "warp_binary_sha256":hashlib.sha256(binary_warps).hexdigest(),
        "original_warp_destination_classification":dict(sorted(count.items())),
        "sources":source_reports,
        "binary_abi":{"maps":"<IHHHHI/16 bytes","warps":"<hhBBBB/8 bytes",
                       "page_size":PAGE,"max_guest_resource":PAGE},
    }
    return binary_maps,binary_warps,report


def write_private_output(destination,bmaps,bwarps,report):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    for stem,blob in (("map",bmaps),("warp",bwarps)):
        # Exact 16 KiB page boundaries so the existing native XGBA sidecar
        # importer can append each record shard as an immutable resource.
        for offset in range(0,len(blob),PAGE):
            index=offset//PAGE
            (destination/f"r46.{stem}.{index:03}.bin").write_bytes(blob[offset:offset+PAGE])
    (destination/"r46_source_scoped_warp_summary.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",action="append",required=True,
                   help="emerald=/private/path.gba ; rocket=... ; heart_soul=...")
    p.add_argument("--private-out",type=Path,required=True)
    a=p.parse_args(argv)
    src=[parse_source(v) for v in a.source]
    bm,bw,report=build_indexes(src)
    write_private_output(a.private_out,bm,bw,report)
    print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
