#!/usr/bin/env python3
"""R41: read-only, REAL three-source Emerald-family structural integration trial.

Input ROM bytes stay PRIVATE and untouched; only aggregate counts and SHA
identities are exportable. This is a cross-source map/event compatibility
attempt, not native quest execution or a merged playable game.
"""
from __future__ import annotations

import argparse
from collections import Counter, OrderedDict
import hashlib
import json
import mmap
from pathlib import Path
import random
import re
import sys

import xgba_r34_binary_maps as r34

PAGE=16384
MAX_SOURCES=3
MAX_BYTES=64*1024*1024
CACHE_BYTES=32768
ID=re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
NATIVE_INTEROP_PROVEN=False


class TrialError(ValueError):
    pass


def _source_arg(text):
    if "=" not in text:
        raise TrialError("Use source_id=/absolute/path/to/user-owned.gba")
    sid,fn=text.split("=",1)
    if not ID.fullmatch(sid) or not fn:
        raise TrialError("Unsafe source ID or missing ROM path")
    return sid,Path(fn)


class SourceReader:
    """Read-only file-backed paged source with 2×16 KiB cache maximum."""

    def __init__(self,paths):
        if not 1<=len(paths)<=MAX_SOURCES or len({sid for sid,_ in paths})!=len(paths):
            raise TrialError("Expected 1–3 different named source worlds")
        self.handles={}
        self.maps={}
        self.cache=OrderedDict()
        self.hits=0
        self.misses=0
        self.evictions=0
        try:
            for sid,path in paths:
                handle=path.open("rb")
                n=path.stat().st_size
                if not PAGE<=n<=MAX_BYTES or n%PAGE:
                    handle.close()
                    raise TrialError("Source GBA size not a bounded multiple of 16 KiB")
                mapping=mmap.mmap(handle.fileno(),0,access=mmap.ACCESS_READ)
                self.handles[sid]=handle
                self.maps[sid]=mapping
        except BaseException:
            self.close()
            raise

    def close(self):
        for m in self.maps.values():m.close()
        for f in self.handles.values():f.close()
        self.maps.clear()
        self.handles.clear()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def page(self,sid,index):
        if sid not in self.maps or type(index) is not int or index<0 or index*PAGE>=len(self.maps[sid]):
            raise TrialError("Invalid source-local page lookup")
        key=(sid,index)
        if key in self.cache:
            self.hits+=1
            self.cache.move_to_end(key)
            return self.cache[key]
        self.misses+=1
        data=self.maps[sid][index*PAGE:(index+1)*PAGE]
        while self.cache and len(self.cache)*PAGE+len(data)>CACHE_BYTES:
            self.cache.popitem(last=False)
            self.evictions+=1
        self.cache[key]=data
        assert sum(map(len,self.cache.values()))<=CACHE_BYTES
        return data

    def read(self,sid,offset,length):
        src=self.maps.get(sid)
        if src is None or type(offset) is not int or type(length) is not int or \
           offset<0 or not 0<=length<=PAGE or offset+length>len(src):
            raise TrialError("Invalid source-local read/window")
        if not length:return b""
        page=offset//PAGE
        inside=offset%PAGE
        a=self.page(sid,page)[inside:inside+length]
        if len(a)<length:
            a+=self.page(sid,page+1)[:length-len(a)]
        return a


def run_trial(paths, *, windows=20000, seed=0x58474241):
    if type(windows) is not int or not 0<=windows<=100000:
        raise TrialError("Windows must be a bounded non-negative integer")
    if type(seed) is not int or not 0<=seed<2**32:
        raise TrialError("Invalid deterministic seed")
    with SourceReader(paths) as reader:
        result={"phase":"R41_ACTUAL_SOURCE_BINARY_MAP_AND_EVENT_STRUCTURE_INTEGRATION",
                "real_user_supplied_roms":True,
                "read_only_all_original_bytes_preserved":True,
                "zero_map_slots_not_renumbered":True,
                "all_nonzero_map_pointers_structurally_checked":True,
                "actual_guest_ewram_allocated_bytes":0,
                "host_staging_limit_bytes":CACHE_BYTES,
                "native_guest_multi_rom_scripts_executed":False,
                "native_cross_world_warp_proven":False,
                "shared_native_flash_save_proven":False,
                "three_game_playable_build_proven":False,
                "source_worlds":{}}
        owned_maps={}
        total_pages=0
        for sid,path in paths:
            blob=reader.maps[sid]
            sha=hashlib.sha256(blob).hexdigest()
            checker=hashlib.sha256()
            page_count=len(blob)//PAGE
            for i in range(page_count):
                chunk=reader.page(sid,i)
                checker.update(chunk)
            if checker.hexdigest()!=sha:
                raise TrialError("Page-by-page original ROM SHA mismatch")
            total_pages+=page_count
            engine=r34.BinaryMapDiscovery(blob[:])
            if engine.digest!=sha:
                raise TrialError("Binary map parser source identity mismatch")
            parsed=engine.discover(min_root_references=1,allow_null_slots=True)
            maps=parsed["maps"]
            ids={(rec["group"],rec["map"]) for rec in maps}
            if len(ids)!=len(maps):
                raise TrialError("Duplicate original source map identity")
            if len(ids)+parsed["null_slot_count"]!=parsed["slot_count"]:
                raise TrialError("An original numeric map slot was dropped")
            owned_maps[sid]={ (r["group"],r["map"]):r for r in maps}
            first=owned_maps[sid].get((0,9))
            result["source_worlds"][sid]={
                "bytes":len(blob),"pages":page_count,
                "original_rom_sha256":sha,
                "gba_game_code":engine.game_code,
                "gba_title":engine.title,
                "map_group_root_offset":parsed["table_offset"],
                "original_group_count":parsed["group_count"],
                "original_numeric_map_slots":parsed["slot_count"],
                "structurally_valid_nonnull_maps":parsed["map_count"],
                "original_zero_pointer_map_holes":parsed["null_slot_count"],
                "active_original_numeric_map_ids_preserved":True,
                "map_scripts_with_source_pointers":sum(m["script_root_offset"] is not None for m in maps),
                "object_event_count":sum(m["object_count"] for m in maps),
                "warp_event_count":sum(m["warp_count"] for m in maps),
                "coord_event_count":sum(m["coordinate_event_count"] for m in maps),
                "background_event_count":sum(m["background_event_count"] for m in maps),
                "connections":sum(m["connection_count"] for m in maps),
                "example_map_group0_9":None if first is None else {
                    "width":first["width"],"height":first["height"],
                    "objects":first["object_count"],
                    "warps":first["warp_count"]},
                "full_engine_semantic_compatibility_certified":False}
        if len({x["gba_game_code"] for x in result["source_worlds"].values()})>1:
            raise TrialError("Source ROM game-code families differ")
        if set(x["gba_game_code"] for x in result["source_worlds"].values())!={"BPEE"}:
            raise TrialError("Known Emerald-family input required")
        all_ids=set().union(*(set(m) for m in owned_maps.values()))
        shared=Counter()
        dimension_mismatch=0
        collision_examples=[]
        for key in sorted(all_ids):
            worlds={sid:m[key] for sid,m in owned_maps.items() if key in m}
            shared[len(worlds)]+=1
            if len(worlds)<2:continue
            dims={(m["width"],m["height"]) for m in worlds.values()}
            if len(dims)>1:
                dimension_mismatch+=1
                if len(collision_examples)<20:
                    collision_examples.append({"original_group":key[0],"original_map":key[1],
                        "dimensions_by_source":{sid:[m["width"],m["height"]] for sid,m in worlds.items()}})
        result["cross_source_collisions"]={
            "distinct_original_numeric_map_ids":len(all_ids),
            "ids_present_in_all_three":shared[3],
            "ids_present_in_exactly_two":shared[2],
            "ids_present_in_one":shared[1],
            "duplicate_numeric_ids_with_different_map_geometry":dimension_mismatch,
            "dimension_collision_samples":collision_examples,
            "cross_source_id_translation_required":shared[2]+shared[3]>0,
        }
        rng=random.Random(seed)
        sids=list(reader.maps)
        mismatches=0
        for iteration in range(windows):
            sid=sids[iteration%len(sids)]
            data=reader.maps[sid]
            pos=rng.randrange(len(data))
            size=rng.randrange(1,min(PAGE,len(data)-pos)+1)
            if reader.read(sid,pos,size)!=data[pos:pos+size]:
                mismatches+=1
                raise TrialError("Source collision or random page mismatch")
        result["test_results"]={
            "total_original_bytes":sum(len(x) for x in reader.maps.values()),
            "original_pages_read_and_sha_verified":total_pages,
            "random_source_isolated_windows_verified":windows,
            "random_byte_mismatches":mismatches,
            "cache_hits":reader.hits,
            "cache_misses":reader.misses,
            "cache_evictions":reader.evictions,
            "maximum_guest_read_window_bytes":PAGE,
            "host_cache_within_32768_bytes":sum(map(len,reader.cache.values()))<=CACHE_BYTES,
            "accepted_3_real_sources_with_sparse_hns_compatible_map_ids":len(paths)==3,
            "passed":True}
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",action="append",required=True,
                        help="repeat as emerald=/private/file.gba, rocket=..., heart_soul=...")
    parser.add_argument("--windows",type=int,default=20000)
    parser.add_argument("--out",type=Path,
                        help="aggregate JSON ONLY; never exports ROM bytes or extracted maps")
    args=parser.parse_args(argv)
    try:
        inputs=[_source_arg(x) for x in args.source]
        report=run_trial(inputs,windows=args.windows)
        if args.out:
            args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except (TrialError,r34.DiscoveryError,ValueError,OSError) as e:
        print("XGBA_R41_FAIL_CLOSED: "+str(e),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
