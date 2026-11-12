#!/usr/bin/env python3
"""R32: inventory ALL tracked input-source files and optionally shard their bytes.

Source metadata and raw assets are catalogued, not automatically made executable.
Game identifiers, save data and script semantics are never rewritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile

FORMAT="xgba-whole-corpus-index"
VERSION=1
BLOCK=1024*1024
MAX_FILES=250000
MAX_FILE_BYTES=256*1024*1024
MAX_TOTAL_BYTES=8*1024*1024*1024
MAX_INDEX_BYTES=256*1024*1024
MAX_SHARD_ENTRIES=384
MAX_SHARD_BYTES=256*1024*1024
SOURCE_ID=re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

class CorpusError(ValueError):
    pass

def category(path):
    p=path.lower()
    name=PurePosixPath(p).name
    if p.startswith(("data/maps/","data/layouts/","maps/")):
        return "map_events_scripts" if name.endswith((".inc",".s")) or "script" in name or "event" in name else "maps_and_layouts"
    if p.startswith(("data/scripts/","scripts/")) or name=="event_scripts.s":
        return "map_events_scripts"
    if "wild_encounter" in p or "/encounters/" in p:return "wild_encounters"
    if "battle_script" in p or "battle_ai" in p or "battle_anim" in p:return "battles_and_ai"
    if p.startswith(("graphics/","sprites/","assets/graphics/","tilesets/")):return "graphics_and_tilesets"
    if p.startswith(("sound/","audio/","music/","sfx/")):return "audio_and_music"
    if "trainer" in p:return "trainers"
    if "learnset" in p or "egg_move" in p or "battle_moves" in p or "/moves/" in p:return "moves_and_learnsets"
    if "abilit" in p:return "abilities"
    if "species" in p or "pokedex" in p or "evolution" in p or "/pokemon/" in p:return "pokemon_and_species"
    if "item" in p or "berry" in p:return "items_and_inventory"
    if "text" in p or "dialog" in p or "charmap" in p:return "text_and_dialogue"
    if p.startswith(("src/","include/","asm/","constants/","lib/","libagbsyscall/")):
        return "engine_code_and_definitions"
    if p.startswith("data/"):return "other_game_data"
    return "unclassified_preserved"

def enumerate_files(root):
    if (root/".git").exists():
        r=subprocess.run(["git","-C",str(root),"ls-files","--cached","-z"],capture_output=True)
        if r.returncode:raise CorpusError("Git source enumeration failed")
        return sorted({p.decode("utf8") for p in r.stdout.split(b"\0") if p}), True
    result=[]
    for parent,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=sorted(x for x in dirs if x not in (".git",".hg",".svn","__pycache__",".cache","build","build_modern"))
        result.extend((Path(parent)/name).relative_to(root).as_posix() for name in sorted(files))
    return sorted(result),False

def digest_file(path,max_bytes=MAX_FILE_BYTES):
    st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_size>max_bytes:
        raise CorpusError("Unsafe or oversized input file: "+str(path))
    h=hashlib.sha256()
    count=0
    with path.open("rb",buffering=0) as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise CorpusError("Source file changed type")
        for block in iter(lambda:f.read(BLOCK),b""):
            count+=len(block)
            if count>max_bytes:raise CorpusError("Input file grew beyond limit")
            h.update(block)
    if count!=st.st_size:raise CorpusError("Source file mutated while hashing")
    return h.hexdigest(),count

def safe_path(root,rel):
    parts=PurePosixPath(rel).parts
    if not rel or rel.startswith("/") or "\\" in rel or any(p in ("",".","..") for p in parts):
        raise CorpusError("Unsafe relative source path")
    path=root/rel
    try:path.resolve(strict=True).relative_to(root)
    except ValueError as exc:raise CorpusError("Source path escapes root") from exc
    return path

def read_map_json(root,rel):
    p=safe_path(root,rel)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>32*1024*1024:
        raise CorpusError("Missing/unsafe map metadata: "+rel)
    try:return json.loads(p.read_text(encoding="utf8"))
    except (ValueError,UnicodeError) as exc:raise CorpusError("Malformed map metadata: "+rel) from exc

def original_maps(source,root,paths):
    if "data/maps/map_groups.json" not in paths:return [],[]
    d=read_map_json(root,"data/maps/map_groups.json")
    if not isinstance(d,dict) or not isinstance(d.get("group_order"),list):
        raise CorpusError("Map-group data malformed")
    maps=[]
    names=set()
    by_constant={}
    for group,group_name in enumerate(d["group_order"]):
        members=d.get(group_name)
        if not isinstance(members,list) or group>65535:raise CorpusError("Invalid original map-group data")
        for number,name in enumerate(members):
            if not isinstance(name,str) or not name or name in (".","..") or "/" in name or "\\" in name or number>65535 or name in names:
                raise CorpusError("Invalid or duplicate original map identity")
            names.add(name)
            rel=f"data/maps/{name}/map.json"
            m={"source_id":source,"group":group,"map":number,"name":name,
               "original_constant":None,"metadata_file":rel,"connections":[],
               "parse_status":"metadata_unavailable"}
            if rel in paths:
                metadata=read_map_json(root,rel)
                if not isinstance(metadata,dict) or metadata.get("name")!=name or not isinstance(metadata.get("id"),str):
                    raise CorpusError("Original map metadata drift: "+name)
                key=metadata["id"]
                if key in by_constant:raise CorpusError("Duplicate original map constant")
                by_constant[key]=(group,number)
                m["original_constant"]=key
                m["parse_status"]="original_metadata_parsed"
                links=metadata.get("connections")
                # Original pokeemerald explicitly uses JSON null on indoor maps.
                # That is the source engine's valid "no connections" encoding.
                if links is None:links=[]
                if not isinstance(links,list):raise CorpusError("Invalid original map connections")
                for c in links:
                    if not isinstance(c,dict) or not isinstance(c.get("map"),str):
                        raise CorpusError("Invalid map connection")
                    m["connections"].append({"target_original_constant":c["map"],
                                             "direction":c.get("direction"),
                                             "offset":c.get("offset")})
            maps.append(m)
    unresolved=[]
    for m in maps:
        for edge in m["connections"]:
            dest=by_constant.get(edge["target_original_constant"])
            if dest is None:
                unresolved.append({"map":m["name"],"target":edge["target_original_constant"]})
            else:
                edge["target_group"],edge["target_map"]=dest
    return maps,unresolved

def inspect_source(source_id,source_dir,*,max_files=MAX_FILES,max_file_bytes=MAX_FILE_BYTES,
                   max_total_bytes=MAX_TOTAL_BYTES):
    if not isinstance(source_id,str) or not SOURCE_ID.fullmatch(source_id):
        raise CorpusError("Invalid source namespace")
    root=Path(source_dir).resolve(strict=True)
    if not root.is_dir():raise CorpusError("Source root is not a directory")
    files,tracked=enumerate_files(root)
    if not files or len(files)>max_files:raise CorpusError("No files or source corpus exceeds file limit")
    entries=[]
    total=0
    snapshot=hashlib.sha256(b"xgba-corpus-snapshot-v1\0")
    ids=set()
    for rel in files:
        path=safe_path(root,rel)
        digest,size=digest_file(path,max_file_bytes)
        total+=size
        if total>max_total_bytes:raise CorpusError("Complete source exceeds byte limit")
        logical="corpus."+hashlib.sha256((source_id+"\0"+rel).encode("utf8")).hexdigest()
        if logical in ids:raise CorpusError("Full identity collision")
        ids.add(logical)
        entries.append({"source_id":source_id,"path":rel,"resource_id":logical,
                        "sha256":digest,"bytes":size,"category":category(rel),
                        "storage_status":"inventory_only","runtime_status":"unadapted_original_bytes"})
        snapshot.update(rel.encode("utf8")+b"\0"+size.to_bytes(8,"big")+bytes.fromhex(digest))
    maps,unresolved=original_maps(source_id,root,set(files))
    counts=Counter(e["category"] for e in entries)
    sizes=Counter()
    for e in entries:sizes[e["category"]]+=e["bytes"]
    return {"source_id":source_id,"source_snapshot_sha256":snapshot.hexdigest(),
            "git_tracked_only":tracked,"file_count":len(entries),"byte_count":total,
            "category_counts":dict(sorted(counts.items())),
            "category_bytes":dict(sorted(sizes.items())),
            "resources":entries,"original_maps":maps,"unresolved_connections":unresolved,
            "runtime_compatible_resources":0}

def summarize(sources):
    if not sources or len(set(s["source_id"] for s in sources))!=len(sources):
        raise CorpusError("Source IDs must be unique")
    identity=Counter()
    paths=Counter()
    cats=Counter()
    for s in sources:
        for m in s["original_maps"]:identity[(m["group"],m["map"])]+=1
        for e in s["resources"]:
            paths[e["path"]]+=1
            cats[e["category"]]+=1
    return {"source_count":len(sources),
            "catalogued_files":sum(s["file_count"] for s in sources),
            "catalogued_bytes":sum(s["byte_count"] for s in sources),
            "original_map_count":sum(len(s["original_maps"]) for s in sources),
            "original_map_identity_collision_count":sum(n-1 for n in identity.values() if n>1),
            "overlapping_source_paths":sum(n-1 for n in paths.values() if n>1),
            "unresolved_original_map_connections":sum(len(s["unresolved_connections"]) for s in sources),
            "category_counts":dict(sorted(cats.items())),
            "runtime_compatible_resources":sum(s["runtime_compatible_resources"] for s in sources)}

def write_shard(dest,root,source,index,entries):
    import xgba_resource_sidecar as sidecar
    prefix=f"{source['source_id']}-{index:05d}"
    payload=dest/(prefix+".bin")
    manifest=dest/(prefix+".json")
    fd,name=tempfile.mkstemp(prefix=".xgba-",dir=dest)
    temp=Path(name)
    os.close(fd)
    records=[]
    offset=0
    try:
        with temp.open("wb",buffering=0) as out:
            for e in entries:
                original=safe_path(root,e["path"])
                if original.lstat().st_size!=e["bytes"]:raise CorpusError("Source changed before packing")
                h=hashlib.sha256()
                count=0
                with original.open("rb",buffering=0) as inp:
                    for block in iter(lambda:inp.read(BLOCK),b""):
                        count+=len(block)
                        if count>e["bytes"]:raise CorpusError("Source grew before packing")
                        h.update(block)
                        if out.write(block)!=len(block):
                            raise CorpusError("Short write while packing source")
                if count!=e["bytes"] or h.hexdigest()!=e["sha256"]:
                    raise CorpusError("Source changed since inventory: "+e["path"])
                records.append({"id":e["resource_id"],"offset":offset,
                                "length":count,"sha256":e["sha256"]})
                offset+=count
            out.flush();os.fsync(out.fileno())
        if payload.exists() or manifest.exists():raise CorpusError("Refusing to overwrite existing shard")
        os.replace(temp,payload)
        doc={"format":sidecar.FORMAT,"version":sidecar.VERSION,
             "source_identity":{"id":source["source_id"],
                                "sha256":source["source_snapshot_sha256"]},
             "data_file":payload.name,"resources":records}
        encoded=(json.dumps(doc,sort_keys=True,separators=(",",":"))+"\n").encode("utf8")
        if len(encoded)>sidecar.MAX_MANIFEST_BYTES:raise CorpusError("Shard exceeds sidecar-v1 manifest cap")
        manifest.write_bytes(encoded)
        verified=sidecar.load_manifest(manifest)
        if len(verified.resources)!=len(entries):raise CorpusError("Sidecar reader rejected shard")
        # The v1 reader validates metadata bounds, not payload digests on load.
        # Consume every resource to verify the actual packed output bytes too.
        for e in entries:
            readback=0
            for block in sidecar.iter_resource_chunks(verified,e["resource_id"]):
                readback+=len(block)
            if readback!=e["bytes"]:
                raise CorpusError("Sidecar readback length mismatch")
        for e,record in zip(entries,records):
            e["storage_status"]="verified_sidecar"
            e["shard"]=manifest.name
            e["shard_offset"]=record["offset"]
        return {"manifest":manifest.name,"data_file":payload.name,
                "resources":len(entries),"payload_bytes":offset}
    except BaseException:
        temp.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)
        payload.unlink(missing_ok=True)
        raise

def export_corpus(sources,roots,output,*,pack=False,
                  max_shard_entries=MAX_SHARD_ENTRIES,max_shard_bytes=MAX_SHARD_BYTES):
    if len(sources)!=len(roots):raise CorpusError("Missing source roots")
    if type(max_shard_entries) is not int or not 1<=max_shard_entries<=1024:
        raise CorpusError("Invalid shard entry count")
    if type(max_shard_bytes) is not int or not 1<=max_shard_bytes<=MAX_TOTAL_BYTES:
        raise CorpusError("Invalid shard byte bound")
    dest=Path(output)
    dest.mkdir(parents=True,exist_ok=True)
    if any(dest.iterdir()):raise CorpusError("Output directory must be empty")
    shards=[]
    try:
        if pack:
            for source,root in zip(sources,roots):
                root=Path(root).resolve(strict=True)
                current=[]
                size=0
                index=0
                for e in source["resources"]:
                    if e["bytes"]==0:
                        e["storage_status"]="verified_empty_source"
                        continue
                    if e["bytes"]>max_shard_bytes:raise CorpusError("File exceeds shard bound")
                    if current and (len(current)>=max_shard_entries or size+e["bytes"]>max_shard_bytes):
                        shards.append(write_shard(dest,root,source,index,current))
                        current=[];size=0;index+=1
                    current.append(e);size+=e["bytes"]
                if current:shards.append(write_shard(dest,root,source,index,current))
        report={"format":FORMAT,"version":VERSION,
                "storage_mode":"complete_sharded_sidecar" if pack else "inventory_only",
                "source_reports":sources,"shards":shards,"summary":summarize(sources),
                "guarantees":{
                    "original_map_ids_renumbered":False,
                    "unknown_files_discarded":False,
                    "runtime_compatibility_implied":False,
                    "party_inventory_persistence_implemented":False,
                    "binary_rom_hack_decoding_implemented":False,
                    "corpus_bytes_in_public_ci_artifacts":False}}
        raw=(json.dumps(report,separators=(",",":"),sort_keys=True)+"\n").encode("utf8")
        if len(raw)>MAX_INDEX_BYTES:raise CorpusError("Complete corpus index exceeds limit")
        (dest/"xgba-whole-corpus-index.json").write_bytes(raw)
        return report
    except BaseException:
        for f in dest.iterdir():
            if f.is_file():f.unlink()
        raise

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",action="append",required=True,metavar="ID=PATH")
    p.add_argument("--output",required=True)
    p.add_argument("--pack",action="store_true")
    p.add_argument("--max-shard-entries",type=int,default=MAX_SHARD_ENTRIES)
    p.add_argument("--max-shard-bytes",type=int,default=MAX_SHARD_BYTES)
    p.add_argument("--summary-output")
    a=p.parse_args(argv)
    try:
        inputs=[]
        for spec in a.source:
            source,separator,path=spec.partition("=")
            if not separator or not path:raise CorpusError("Source must be ID=PATH")
            inputs.append((source,Path(path)))
        if len(set(x[0] for x in inputs))!=len(inputs):raise CorpusError("Duplicate source namespace")
        sources=[inspect_source(n,path) for n,path in inputs]
        report=export_corpus(sources,[path for _,path in inputs],a.output,
                             pack=a.pack,max_shard_entries=a.max_shard_entries,
                             max_shard_bytes=a.max_shard_bytes)
        summary=dict(report["summary"])
        summary.update(storage_mode=report["storage_mode"],shard_count=len(report["shards"]))
        if a.summary_output:Path(a.summary_output).write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
        print(json.dumps(summary,sort_keys=True))
        return 0
    except (OSError,ValueError,UnicodeError) as ex:
        print("XGBA_WHOLE_CORPUS_FAIL_CLOSED: "+str(ex),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
