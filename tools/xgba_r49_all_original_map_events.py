#!/usr/bin/env python3
"""R49 FULL user-ROM original map event page import, not curated NPC demos.

Read every populated map from Emerald, Team Rocket Edition 3.06 and
Heart & Soul 2.0.6. Preserve all 24-byte object/NPC events, 8-byte warp
records, 16-byte coordinate events and 12-byte background interactions
byte-for-byte, including source-specific script pointers and sparse map
IDs. These raw pointers are NOT executable until source-aware relocation,
text, specials and engine compatibility are implemented. Never publish
original-ROM-derived page files or dialogue on public GitHub.

Output 16KiB SHA-backed XGBA pages and a sorted 16-byte/map lookup index.
Each source map's whole event record fits in one page; no event is truncated.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import zlib

import xgba_r34_binary_maps as r34

BASE=32*1024*1024+0x200000
PAGE=16384
RECORD_SIZES=(24,8,16,12)
COUNTS=("object_count","warp_count","coordinate_event_count",
        "background_event_count")
SOURCES={
 "emerald":("a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af",518),
 "rocket":("5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca",1778),
 "heart_soul":("cdfb9e1f83f72c05cb47af40fdf5635567b1973bcb759e070ad0971f67a49191",560),
}
ORIGINAL_EVENT_HEADER="<4sIBBBBIIIII"  # 32 bytes: provenance and source CRC
ORIGINAL_INDEX_ROW="<IHHII"           # 16 bytes: key/page/offset/length/header
assert struct.calcsize(ORIGINAL_EVENT_HEADER)==32
assert struct.calcsize(ORIGINAL_INDEX_ROW)==16


class OriginalEventImportError(ValueError):
    pass


def pack_event_record(source:int,rom:bytes,m:dict):
    key=(source<<16)|(m["group"]<<8)|m["map"]
    counts=tuple(m[name] for name in COUNTS)
    originals=[]
    for i,(num,size) in enumerate(zip(counts,RECORD_SIZES)):
        off=m["event_array_offsets"][i]
        if num:
            if off is None or off<0 or off+num*size>len(rom):
                raise OriginalEventImportError(f"Source event array out of bounds: {key:06x}/{i}")
            originals.append(rom[off:off+num*size])
        else:
            if off is not None:
                raise OriginalEventImportError("Original empty event array should be absent")
            originals.append(b"")
    raw=b"".join(originals)
    if len(raw)!=sum(a*b for a,b in zip(counts,RECORD_SIZES)):
        raise OriginalEventImportError("Original game event bytes were dropped")
    header=struct.pack(ORIGINAL_EVENT_HEADER,b"X49E",key,*counts,
                       m["header_offset"],m["events_offset"],
                       zlib.crc32(raw)&0xffffffff,len(raw),
                       m["script_root_offset"] or 0xffffffff)
    record=header+raw
    if len(record)>PAGE:
        raise OriginalEventImportError("Source map event record exceeds 16KiB; implement multi-page BEFORE import")
    return key,record


def compile_all_original_map_events(private_rom_paths:dict):
    if set(private_rom_paths)!=set(SOURCES):
        raise OriginalEventImportError("All THREE private original ROMs required")
    index=[]
    source_reports={}
    pending=bytearray()
    pages=[]
    for source,(name,expected) in enumerate(SOURCES.items()):
        source_path=Path(private_rom_paths[name])
        if not source_path.is_file():
            raise OriginalEventImportError("Missing original private ROM "+name)
        rom=source_path.read_bytes()
        if hashlib.sha256(rom).hexdigest()!=expected[0]:
            raise OriginalEventImportError("Original complete source ROM SHA mismatch: "+name)
        discovered=r34.BinaryMapDiscovery(rom).discover(
            min_root_references=1,allow_null_slots=True)
        maps=sorted(discovered["maps"],key=lambda m:(m["group"],m["map"]))
        if len(maps)!=expected[1]:
            raise OriginalEventImportError(f"{name}: original map count changed")
        counts=Counter()
        for m in maps:
            key,record=pack_event_record(source,rom,m)
            if index and key<=index[-1][0]:
                raise OriginalEventImportError("Source namespace collision / unexpected map order")
            if len(pending)+len(record)>PAGE:
                pages.append(bytes(pending).ljust(PAGE,b"\0"))
                pending=bytearray()
            if len(pages)>0xffff or len(pending)>0xffff:
                raise OriginalEventImportError("Native source event index exceeds uint16 bounds")
            index.append((key,len(pages),len(pending),len(record),m["header_offset"]))
            pending.extend(record)
            for count_key in COUNTS:
                counts[count_key]+=m[count_key]
            counts["original_map_count"]+=1
        source_reports[name]={
          "sha256":expected[0],"counts":dict(counts),
          "original_map_slots":discovered["slot_count"],
          "null_map_slots":discovered["null_slot_count"],
          "retained_exact_original_pointer_bytes":True,
          "native_interpreter_script_execution_proven":False,
        }
    if pending:
        pages.append(bytes(pending).ljust(PAGE,b"\0"))
    if len(index)!=2856:
        raise OriginalEventImportError("Expected ALL 2,856 original populated map events")
    expected_totals={
       "object_count":17089,"warp_count":7146,
       "coordinate_event_count":2340,"background_event_count":4697,
    }
    totals={kind:sum(d["counts"][kind] for d in source_reports.values())
            for kind in expected_totals}
    if totals!=expected_totals:
        raise OriginalEventImportError(f"Loss of authentic NPC/warp/event data: {totals}")
    idx=b"".join(struct.pack(ORIGINAL_INDEX_ROW,*row) for row in index)
    index_pages=[idx[i:i+PAGE].ljust(PAGE,b"\0")
                 for i in range(0,len(idx),PAGE)]
    proof={
       "milestone":"R49_ALL_ORIGINAL_THREE_GAME_MAP_EVENTS_RETAINED",
       "all_original_maps_indexed":len(index),
       "object_event_records_retained":totals["object_count"],
       "original_warp_records_retained":totals["warp_count"],
       "coordinate_triggers_retained":totals["coordinate_event_count"],
       "background_interactions_retained":totals["background_event_count"],
       "original_event_bytes_are_unmodified":True,
       "original_script_pointers_preserved_not_executed":True,
       "original_engine_foreign_npc_interaction_verified":False,
       "cross_world_fly_verified":False,
       "source_aware_index_bytes":len(idx),
       "external_event_pages":len(pages),
       "external_index_pages":len(index_pages),
       "source_reports":source_reports,
    }
    return index_pages,pages,proof,index


def save_private_pack(output,index_pages,event_pages,proof):
    out=Path(output)
    if out.exists() and any(out.iterdir()):
        raise OriginalEventImportError("Private output directory must be empty")
    out.mkdir(parents=True,exist_ok=True)
    resources=[]
    cur=BASE
    for kind,pages in (("index",index_pages),("events",event_pages)):
        for i,content in enumerate(pages):
            if len(content)!=PAGE:
                raise OriginalEventImportError("Only complete immutable 16KiB pages accepted")
            rid=f"r49.{kind}.{i:03}"
            name=f"{rid}.bin"
            (out/name).write_bytes(content)
            resources.append({
                "id":rid,"relative_file":name,
                "offset":cur,"length":PAGE,
                "sha256":hashlib.sha256(content).hexdigest()})
            cur+=PAGE
    report=dict(proof,manifest_resources=resources,
                private_original_data_do_not_upload=True,
                complete_foreign_events_executable=False)
    (out/"private-r49-original-three-rom-event-import.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--emerald",type=Path,required=True)
    p.add_argument("--rocket",type=Path,required=True)
    p.add_argument("--heart-soul",type=Path,required=True)
    p.add_argument("--private-out",type=Path,required=True)
    a=p.parse_args()
    pages,events,proof,_=compile_all_original_map_events({
        "emerald":a.emerald,"rocket":a.rocket,"heart_soul":a.heart_soul})
    result=save_private_pack(a.private_out,pages,events,proof)
    print(json.dumps({"phase":result["milestone"],
       "maps":proof["all_original_maps_indexed"],
       "original_npcs":proof["object_event_records_retained"],
       "pages":len(pages)+len(events),
       "native_original_engine_fly_passed":False}))


if __name__=="__main__":
    main()
