#!/usr/bin/env python3
"""R36 full-byte, read-only page import for structurally validated Emerald-family ROMs.

The source ROM is never changed. An entrypoint is a source pointer, NOT a
decoded script or runtime-compatible executable. No ROM data belongs in CI.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import xgba_r34_binary_maps as r34
import xgba_resource_sidecar as sidecar

FORMAT="xgba-binary-rom-pages"
VERSION=1
PAGE_SIZE=16384
PAGES_PER_SHARD=128
MAX_PAGES=4096
MAX_INDEX=128*1024*1024
SOURCE=re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
FILENAME=re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z")
HEX=re.compile(r"[0-9a-f]{64}\Z")

class PageError(ValueError):
    pass

def integer(x,name,low=0,high=1<<64):
    if type(x) is not int or not low<=x<=high:
        raise PageError("Invalid "+name)
    return x

def filename(name):
    if not isinstance(name,str) or FILENAME.fullmatch(name) is None:
        raise PageError("Unsafe shard filename")
    return name

def pairs(items):
    d={}
    for k,v in items:
        if k in d:raise PageError("Duplicate JSON key")
        d[k]=v
    return d

def invalid_constant(x):
    raise PageError("Invalid JSON constant")

def read_json(path):
    path=Path(path).absolute()
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_INDEX:
        raise PageError("Unsafe or oversized page index")
    try:
        doc=json.loads(path.read_bytes().decode("utf8"),object_pairs_hook=pairs,parse_constant=invalid_constant)
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise PageError("Malformed page index") from exc
    if not isinstance(doc,dict) or doc.get("format")!=FORMAT or type(doc.get("version")) is not int or doc["version"]!=VERSION or doc.get("original_rom_bytes_preserved") is not True or doc.get("scripts_executable") is not False or doc.get("battle_data_decoded") is not False:
        raise PageError("Unsupported page index or unsafe compatibility assertion")
    return path,doc

def script_roots(scanner,discovery):
    """Read original source-backed Emerald map and event entrypoint references.

    Map-script records: [u8 type, u32 target] terminated by 0.
    ON_FRAME and ON_WARP: [u16 var,u16 value,u32 target], terminated by 0.
    Object +16, coordinate +12, BG-kind 0..4 +8 are script references.
    Hidden item and secret base numeric payloads are NOT script pointers.
    Any undecodable pointer remains an explicitly recorded unresolved reference.
    """
    data=scanner.data
    out=[]
    counts=Counter()
    errors=Counter()
    examples=[]
    def invalid(why,g,n,i):
        errors[why]+=1
        if len(examples)<32:examples.append({"reason":why,"group":g,"map":n,"slot":i})
    def add(g,n,kind,slot,ptr,**meta):
        if not ptr:
            counts["null_script_pointers"]+=1
            return
        pos=scanner.pointer(ptr)
        if pos is None:
            invalid("out_of_rom_script_pointer",g,n,slot)
            return
        if len(out)>=200000:raise PageError("Script entrypoint budget exceeded")
        e={"group":g,"map":n,"kind":kind,"slot":slot,"source_rom_offset":pos}
        e.update(meta)
        out.append(e);counts[kind]+=1
    for m in discovery["maps"]:
        g,n=m["group"],m["map"]
        pos=m["script_root_offset"]
        if pos is not None:
            terminated=False
            for i in range(64):
                if not scanner.span(pos,1):
                    invalid("truncated_map_script_table",g,n,i);break
                tag=data[pos]
                if not tag:
                    terminated=True
                    break
                if not 1<=tag<=7 or not scanner.span(pos,5):
                    invalid("unknown_map_script_tag_or_truncation",g,n,i);break
                ptr=struct.unpack_from("<I",data,pos+1)[0]
                if tag not in (2,4):
                    add(g,n,"map_script",i,ptr,script_type=tag)
                else:
                    cursor=scanner.pointer(ptr)
                    if cursor is None:
                        invalid("invalid_conditional_map_script_table",g,n,i)
                    else:
                        end=False
                        for j in range(64):
                            if not scanner.span(cursor,2):
                                invalid("truncated_conditional_table",g,n,i);break
                            var=struct.unpack_from("<H",data,cursor)[0]
                            if not var:
                                end=True
                                break
                            if not scanner.span(cursor,8):
                                invalid("truncated_conditional_table",g,n,i);break
                            value,script=struct.unpack_from("<HI",data,cursor+2)
                            add(g,n,"conditional_script",j,script,script_type=tag,source_table_slot=i,var_id=var,comparison_var_or_value=value)
                            cursor+=8
                        if not end:invalid("conditional_table_not_terminated",g,n,i)
                pos+=5
            if not terminated:invalid("map_script_table_not_terminated",g,n,0)
        obj=m["event_array_offsets"][0]
        for i in range(m["object_count"]):
            at=obj+24*i
            add(g,n,"object_event_script",i,struct.unpack_from("<I",data,at+16)[0])
        coord=m["event_array_offsets"][2]
        for i in range(m["coordinate_event_count"]):
            at=coord+16*i
            add(g,n,"coordinate_event_script",i,struct.unpack_from("<I",data,at+12)[0])
        bg=m["event_array_offsets"][3]
        for i in range(m["background_event_count"]):
            at=bg+12*i
            kind=data[at+5]
            if 0<=kind<=4:
                add(g,n,"background_event_script",i,struct.unpack_from("<I",data,at+8)[0],background_kind=kind)
            elif kind==7:counts["hidden_item_records"]+=1
            elif kind==8:counts["secret_base_records"]+=1
            else:counts["unknown_background_event_kinds"]+=1
    return {"source_engine_profile":"pret-emerald-map-event-pointer-structures-only",
            "original_script_entrypoints":out,
            "summary":{"entrypoints":len(out),"unique_entrypoint_offsets":len({r["source_rom_offset"] for r in out}),
                       "counts_by_origin":dict(sorted(counts.items())),
                       "unresolved_reference_counts":dict(sorted(errors.items())),
                       "unresolved_reference_examples":examples,
                       "script_commands_decoded":0,
                       "custom_script_engine_compatibility_proven":False}}

def export_binary_pages(scanner,discovery,directory,source_id,*,pages_per_shard=PAGES_PER_SHARD):
    if not isinstance(source_id,str) or SOURCE.fullmatch(source_id) is None:
        raise PageError("Invalid source namespace")
    if type(pages_per_shard) is not int or not 1<=pages_per_shard<=PAGES_PER_SHARD:
        raise PageError("Invalid pages-per-shard")
    if len(discovery.get("maps",[]))!=discovery.get("map_count") or len(discovery.get("group_map_counts",[]))!=discovery.get("group_count"):
        raise PageError("Unverified original map structure inventory")
    target=Path(directory)
    target.mkdir(parents=True,exist_ok=True)
    if any(target.iterdir()):raise PageError("Destination must be empty")
    identity={"id":source_id,"sha256":scanner.digest}
    n=(scanner.size+PAGE_SIZE-1)//PAGE_SIZE
    if n>MAX_PAGES:raise PageError("Too many source ROM pages")
    pages=[];shards=[]
    try:
        roots=script_roots(scanner,discovery)
        for start in range(0,n,pages_per_shard):
            name=f"{source_id}-pages-{len(shards):05d}"
            manifest=target/(name+".json")
            payload=target/(name+".bin")
            records=[];size=0;sha=hashlib.sha256()
            with payload.open("xb") as f:
                for i in range(start,min(start+pages_per_shard,n)):
                    off=i*PAGE_SIZE
                    raw=scanner.data[off:off+PAGE_SIZE]
                    rid=f"rom.page.{i:06d}"
                    digest=hashlib.sha256(raw).hexdigest()
                    count=f.write(raw)
                    if count!=len(raw):raise PageError("Short output write")
                    records.append({"id":rid,"offset":size,"length":len(raw),"sha256":digest})
                    pages.append({"id":rid,"number":i,"rom_offset":off,"length":len(raw),
                                  "sha256":digest,"manifest":manifest.name})
                    sha.update(raw);size+=len(raw)
                f.flush();os.fsync(f.fileno())
            doc={"format":sidecar.FORMAT,"version":sidecar.VERSION,
                 "source_identity":identity,"data_file":payload.name,"resources":records}
            encoded=(json.dumps(doc,sort_keys=True,separators=(",",":"))+"\n").encode("utf8")
            if len(encoded)>sidecar.MAX_MANIFEST_BYTES:raise PageError("Oversized manifest")
            manifest.write_bytes(encoded)
            verified=sidecar.load_manifest(manifest,expected_source_identity=identity)
            for e in records:
                if sum(len(b) for b in sidecar.iter_resource_chunks(verified,e["id"]))!=e["length"]:
                    raise PageError("Sidecar output readback failed")
            shards.append({"manifest":manifest.name,"data_file":payload.name,
                           "resources":len(records),"bytes":size,"sha256":sha.hexdigest()})
        doc={"format":FORMAT,"version":VERSION,"source_identity":identity,
             "original_rom_bytes_preserved":True,"scripts_executable":False,
             "battle_data_decoded":False,"page_size":PAGE_SIZE,"page_count":n,
             "rom_bytes":scanner.size,"original_map_group_table_offset":discovery["table_offset"],
             "original_group_map_counts":discovery["group_map_counts"],
             "original_map_count":discovery["map_count"],"shards":shards,
             "pages":pages,"script_roots":roots,
             "coverage":{"addressable_source_bytes":scanner.size,"raw_bytes_persisted":scanner.size,
                         "unaddressable_source_bytes":0,"native_emulator_provider_bound":False,
                         "script_bytecode_semantics_implemented":False}}
        encoded=(json.dumps(doc,separators=(",",":"),sort_keys=True)+"\n").encode()
        if len(encoded)>MAX_INDEX:raise PageError("Excessive source index")
        (target/"xgba-binary-rom-pages.json").write_bytes(encoded)
        return doc
    except BaseException:
        for p in target.iterdir():
            if p.is_file():p.unlink()
        raise

class PagedBinaryPool:
    """All original ROM bytes addressable by bounded on-demand verified pages."""
    def __init__(self,index_path,*,max_staged_bytes=16*1024*1024,max_window_bytes=PAGE_SIZE,chunk_size=65536):
        self.max_staged_bytes=integer(max_staged_bytes,"staging budget",1,r34.MAX_ROM_BYTES)
        self.max_window_bytes=integer(max_window_bytes,"window budget",1,PAGE_SIZE)
        self.chunk_size=integer(chunk_size,"chunk size",1,sidecar.MAX_CHUNK_SIZE)
        self._pages={};self._shards={};self._staged={}
        self.source_id=None;self.source_sha256=None
        self.original_group_map_counts=None;self.original_map_group_table_offset=None
        self.rom_bytes=0;self.script_roots=None
        self.open(index_path)

    @property
    def source_ids(self):return (self.source_id,) if self.source_id else ()
    @property
    def resource_count(self):return len(self._pages)
    @property
    def shard_count(self):return len(self._shards)
    @property
    def staged_bytes(self):return sum(len(x) for x in self._staged.values())

    def open(self,index_path):
        path,doc=read_json(index_path)
        identity=doc.get("source_identity")
        if not isinstance(identity,dict) or set(identity)!={"id","sha256"} or not isinstance(identity["id"],str) or SOURCE.fullmatch(identity["id"]) is None or not isinstance(identity["sha256"],str) or HEX.fullmatch(identity["sha256"]) is None:
            raise PageError("Invalid original source identity")
        size=integer(doc.get("rom_bytes"),"ROM size",0,r34.MAX_ROM_BYTES)
        n=integer(doc.get("page_count"),"page count",1,MAX_PAGES)
        if not 0xc0<=size or doc.get("page_size")!=PAGE_SIZE or n!=(size+PAGE_SIZE-1)//PAGE_SIZE:
            raise PageError("Inconsistent ROM page count")
        groups=doc.get("original_group_map_counts")
        if not isinstance(groups,list) or not 8<=len(groups)<=256 or not all(type(i) is int and 1<=i<=256 for i in groups) or doc.get("original_map_count")!=sum(groups):
            raise PageError("Invalid original map group identities")
        table=integer(doc.get("original_map_group_table_offset"),"map group table",0,size-4)
        shard_meta=doc.get("shards");pages=doc.get("pages")
        if not isinstance(shard_meta,list) or not 1<=len(shard_meta)<=2048 or not isinstance(pages,list) or len(pages)!=n:
            raise PageError("Invalid page or shard list")
        manifests={};sha=hashlib.sha256()
        for s in shard_meta:
            if not isinstance(s,dict):raise PageError("Invalid shard")
            name=filename(s.get("manifest"))
            if name in manifests:raise PageError("Duplicate shard")
            sub=path.parent/name
            if sub.is_symlink():raise PageError("Symlinked manifest")
            m=sidecar.load_manifest(sub,expected_source_identity=identity)
            if m.data_path.parent!=path.parent or m.data_path.is_symlink() or m.data_path.name!=filename(s.get("data_file")) or s.get("resources")!=len(m.resources):
                raise PageError("Wrong source shard")
            length=integer(s.get("bytes"),"shard length",1,r34.MAX_ROM_BYTES)
            actual=hashlib.sha256();count=0
            with m.data_path.open("rb") as f:
                for block in iter(lambda:f.read(65536),b""):
                    count+=len(block)
                    if count>length:raise PageError("Oversized sidecar shard")
                    actual.update(block);sha.update(block)
            if count!=length or actual.hexdigest()!=s.get("sha256"):
                raise PageError("Sidecar shard checksum mismatch")
            manifests[name]=m
        if sha.hexdigest()!=identity["sha256"]:
            raise PageError("Whole original ROM SHA-256 mismatch")
        offset_by_shard={name:0 for name in manifests}
        order={name:i for i,name in enumerate(manifests)}
        last=0;seen={name:set() for name in manifests}
        by_id={};byte_total=0
        for i,e in enumerate(pages):
            if not isinstance(e,dict):raise PageError("Invalid page record")
            off=i*PAGE_SIZE
            length=min(PAGE_SIZE,size-off)
            rid=f"rom.page.{i:06d}"
            name=filename(e.get("manifest"))
            if e.get("id")!=rid or e.get("number")!=i or e.get("rom_offset")!=off or e.get("length")!=length:
                raise PageError("Missing or renumbered ROM page")
            m=manifests.get(name)
            record=m.resources.get(rid) if m else None
            if record is None or record.length!=length or record.sha256!=e.get("sha256") or record.offset!=offset_by_shard.get(name) or order[name]<last or order[name]>last+1 or rid in seen[name]:
                raise PageError("Page provenance or contiguous shard order mismatch")
            seen[name].add(rid);offset_by_shard[name]+=length
            last=order[name];byte_total+=length
            by_id[rid]=(off,length,m)
        if byte_total!=size or any(seen[name]!=set(m.resources) for name,m in manifests.items()) or any(offset_by_shard[name]!=shard_meta[i]["bytes"] for i,name in enumerate(manifests)):
            raise PageError("Unindexed or missing source bytes")
        c=doc.get("coverage")
        if not isinstance(c,dict) or c.get("addressable_source_bytes")!=size or c.get("raw_bytes_persisted")!=size or c.get("unaddressable_source_bytes")!=0 or c.get("native_emulator_provider_bound") is not False or c.get("script_bytecode_semantics_implemented") is not False:
            raise PageError("Bad coverage or executable compatibility claim")
        roots=doc.get("script_roots")
        if not isinstance(roots,dict) or not isinstance(roots.get("original_script_entrypoints"),list) or len(roots["original_script_entrypoints"])>200000 or not isinstance(roots.get("summary"),dict):
            raise PageError("Invalid script root census")
        for e in roots["original_script_entrypoints"]:
            if not isinstance(e,dict) or type(e.get("source_rom_offset")) is not int or not 0<=e["source_rom_offset"]<size or type(e.get("group")) is not int or not 0<=e["group"]<len(groups) or type(e.get("map")) is not int or not 0<=e["map"]<groups[e["group"]]:
                raise PageError("Out-of-range script entrypoint")
        if roots["summary"].get("entrypoints")!=len(roots["original_script_entrypoints"]) or roots["summary"].get("script_commands_decoded")!=0 or roots["summary"].get("custom_script_engine_compatibility_proven") is not False:
            raise PageError("Script census improperly claims runtime compatibility")
        # Publish only after every index, full shard and source ROM checksum passes.
        self._pages=by_id;self._shards=manifests;self._staged={}
        self.source_id=identity["id"];self.source_sha256=identity["sha256"]
        self.original_group_map_counts=tuple(groups);self.original_map_group_table_offset=table
        self.rom_bytes=size;self.script_roots=roots
        return self

    def close(self):
        self._pages={};self._shards={};self._staged={}
        self.source_id=None;self.source_sha256=None;self.rom_bytes=0;self.script_roots=None

    def page_at(self,offset):
        if type(offset) is not int or not 0<=offset<self.rom_bytes:
            raise PageError("Original ROM offset outside source")
        i,inside=divmod(offset,PAGE_SIZE)
        return f"rom.page.{i:06d}",inside

    def source_of(self,rid):
        try:off,length,_=self._pages[rid]
        except KeyError as exc:raise PageError("Unknown original ROM page") from exc
        return self.source_id,f"raw_rom/{off:08x}",length

    def read_window(self,rid,start,length):
        if type(start) is not int or type(length) is not int or start<0 or not 0<=length<=self.max_window_bytes:
            raise PageError("Outside transfer window budget")
        try:_,size,m=self._pages[rid]
        except KeyError as exc:raise PageError("Unknown original ROM page") from exc
        if start>size or length>size-start:raise PageError("ROM page window outside bounds")
        data=b"".join(sidecar.iter_resource_chunks(m,rid,self.chunk_size))
        if len(data)!=size:raise PageError("ROM page changed while reading")
        return data[start:start+length]

    def read_rom(self,offset,length):
        if type(offset) is not int or type(length) is not int or offset<0 or not 0<=length<=self.max_window_bytes or offset>self.rom_bytes or length>self.rom_bytes-offset:
            raise PageError("Whole-ROM read exceeds bounds")
        out=bytearray()
        while len(out)<length:
            rid,inside=self.page_at(offset+len(out))
            out.extend(self.read_window(rid,inside,min(length-len(out),PAGE_SIZE-inside)))
        return bytes(out)

    def stage(self,rid):
        try:_,size,m=self._pages[rid]
        except KeyError as exc:raise PageError("Unknown original ROM page") from exc
        old=self._staged.get(rid)
        used=self.staged_bytes-(len(old) if old is not None else 0)
        if size>self.max_staged_bytes-used:raise PageError("Host memory staging budget exceeded")
        candidate=b"".join(sidecar.iter_resource_chunks(m,rid,self.chunk_size))
        if len(candidate)!=size:raise PageError("ROM page changed while staging")
        self._staged[rid]=candidate
        return memoryview(candidate)

    def staged_resource(self,rid):
        try:return memoryview(self._staged[rid])
        except KeyError as exc:raise PageError("Page not staged") from exc

    def unstage(self,rid):self._staged.pop(rid,None)

    def verify_original_rom(self,rom):
        digest=hashlib.sha256();size=0
        with Path(rom).open("rb") as f:
            for block in iter(lambda:f.read(1024*1024),b""):
                size+=len(block);digest.update(block)
        if size!=self.rom_bytes or digest.hexdigest()!=self.source_sha256:
            raise PageError("Original ROM identity mismatch")
        with Path(rom).open("rb") as f:
            for i in range(len(self._pages)):
                rid=f"rom.page.{i:06d}"
                raw=f.read(PAGE_SIZE)
                if self.read_window(rid,0,len(raw))!=raw:
                    raise PageError("ROM source page content mismatch")
        return size

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("rom");p.add_argument("--export",required=True)
    p.add_argument("--source-id",required=True)
    p.add_argument("--counts-only")
    args=p.parse_args(argv)
    try:
        scan=r34.BinaryMapDiscovery(args.rom);found=scan.discover()
        doc=export_binary_pages(scan,found,args.export,args.source_id)
        roots=doc["script_roots"]["summary"]
        summary={"original_rom_unchanged":True,"input_sha256":scan.digest,
                 "original_rom_bytes":scan.size,"pages":doc["page_count"],
                 "shards":len(doc["shards"]),"original_map_ids":doc["original_map_count"],
                 "root_entrypoints":roots["entrypoints"],
                 "unique_entrypoint_offsets":roots["unique_entrypoint_offsets"],
                 "unresolved_references":sum(roots["unresolved_reference_counts"].values()),
                 "runtime_script_compatibility_proven":False}
        if args.counts_only:
            Path(args.counts_only).write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
        print(json.dumps(summary,sort_keys=True))
        return 0
    except (PageError,r34.DiscoveryError,OSError,ValueError) as exc:
        print("XGBA_R36_FAIL_CLOSED: "+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
