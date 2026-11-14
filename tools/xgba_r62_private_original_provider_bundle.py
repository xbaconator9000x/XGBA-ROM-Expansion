#!/usr/bin/env python3
"""R62 PRIVATE three-world XGBA provider bundle with authentic Rocket assets.

Combine *existing user-owned private* R48 original NPC dialogue and R49 events, R51 grids, R52
source-versioned layouts, R53 Rocket tiles and R56 Rocket original NPC art.
All input SHA-256 pages are independently verified before the destination
host-manifest is created. This is not a public ROM asset exporter: keep the
result private and never commit its binary or derived tables.

This is the existing XGBA host resource schema, NOT a full native Fly test:
Johto original graphics and general script execution remain absent; three exact original NPC witness scripts are included but not evidence of live gameplay.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib
import xgba_resource_sidecar as sidecar

PAGE=16384
SOURCES={
 "emerald":"a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af",
 "rocket":"5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca",
 "heart_soul":"cdfb9e1f83f72c05cb47af40fdf5635567b1973bcb759e070ad0971f67a49191"}
KEY_ROCKET=(1<<16)|9
ROCKET_LANDING=(14,14)
SLOTS_ROCKET=(6,9,17,64)
ROCKET_TERRAIN=("r53.w1.v2.t00e9ffe0","r53.w1.v2.t00e9ffc8")
class PrivateBundleError(ValueError):pass

def _sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def _json(data:bytes):
    try:return json.loads(data.decode("utf-8"))
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise PrivateBundleError("Invalid input private manifest JSON") from exc

def _valid_pages(entries,reader):
    if not isinstance(entries,list) or not entries:
        raise PrivateBundleError("Expected nonempty source resource manifest")
    result={}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={"id","offset","length","sha256"}:
            raise PrivateBundleError("Malformed original source resource entry")
        rid=entry["id"]
        if not isinstance(rid,str) or not rid.isascii() or not rid or rid in result:
            raise PrivateBundleError("Duplicate or malformed source resource ID")
        if type(entry["length"]) is not int or not 1<=entry["length"]<=PAGE:
            raise PrivateBundleError("Invalid bounded native resource size: "+rid)
        raw=reader(entry)
        if len(raw)!=entry["length"] or _sha(raw)!=entry["sha256"]:
            raise PrivateBundleError("Original source resource SHA mismatch: "+rid)
        result[rid]=raw
    return result

def original_r48_witnesses(z:zipfile.ZipFile)->dict[str,bytes]:
    """Admit only SHA-attested user-owned ORIGINAL three NPC script witnesses.

    R48's original Emerald native interpreter fetches these exact 256-byte
    resource IDs on a *physical* A-button NPC interaction. R62 previously
    exported the R49 event index but omitted all three R48 witness payloads,
    leaving that interaction path unable to load any original dialogue.
    """
    inventory=_json(z.read("private-r48-original-npc-witnesses.json"))
    records=inventory.get("resources")
    if not isinstance(records,list) or len(records)!=3:
        raise PrivateBundleError("Missing complete original R48 source witness catalogue")
    canonical=(
        ("emerald.r48.npc","emerald",0,0,9,2,12,13,17,0x1e8022,0x1e8acf),
        ("rocket.r48.npc","rocket",1,0,9,2,14,13,17,0x215543,0x1dc3364),
        ("heart_soul.r48.npc","heart_soul",2,0,4,7,39,22,406,0x390519,0x3908e6),
    )
    output={}
    for record,expected in zip(records,canonical):
        rid,name,world,group,map_number,npc_id,x,y,gfx,script_at,text_at=expected
        if record.get("id")!=rid or record.get("length")!=256 or \
           record.get("source_sha256")!=SOURCES[name] or \
           record.get("original_npc_id")!=npc_id or \
           record.get("original_script_offset")!=script_at or \
           record.get("original_text_offset")!=text_at:
            raise PrivateBundleError("Original NPC source witness catalogue changed: "+rid)
        payload=z.read(rid+".bin")
        if len(payload)!=256 or _sha(payload)!=record.get("sha256"):
            raise PrivateBundleError("Original NPC SHA integrity failure: "+rid)
        if payload[:4]!=b"X48N" or payload[4]!=1 or \
           tuple(payload[5:9])!=(world,group,map_number,npc_id) or \
           struct.unpack_from("<hhH",payload,9)!=(x,y,gfx) or \
           struct.unpack_from("<II",payload,15)!=(script_at,text_at):
            raise PrivateBundleError("Original NPC source header mismatch: "+rid)
        script_len,text_len=struct.unpack_from("<HH",payload,23)
        if script_len!=9 or not 0<text_len<=210 or 32+script_len+text_len>256:
            raise PrivateBundleError("Original NPC script/text bounds mismatch: "+rid)
        script=payload[32:41]
        if script[:2]!=b"\x0f\x00" or script[2:6]!=struct.pack("<I",0x08000000+text_at) or \
           script[6:]!=b"\x09\x02\x02" or payload[41+text_len-1]!=0xff:
            raise PrivateBundleError("Original NPC interpreter bytecode mismatch: "+rid)
        output[rid]=payload
    return output

def zip_manifest_pages(path:Path,kind:str):
    with zipfile.ZipFile(path) as z:
        if kind=="r49":
            m=_json(z.read("private-manifest.json"))
            if any(m["sources"][name]["sha256"]!=digest
                   for name,digest in SOURCES.items()):
                raise PrivateBundleError("R49 source ROM identity drift")
            entries=m["manifest_resources"]
            def extract(e):return z.read(e["id"]+".bin")
        else:
            m=_json(z.read("manifest.json"))
            data=z.read(m["data_file"])
            def extract(e):
                a=e["offset"];b=a+e["length"]
                return data[a:b] if a>=0 and b<=len(data) else b""
        pages=_valid_pages(entries,extract)
        if kind=="r49":
            for rid,payload in original_r48_witnesses(z).items():
                if rid in pages:raise PrivateBundleError("NPC/resource ID collision")
                pages[rid]=payload
        return pages

def folder_manifest_pages(root:Path,expected_rocket_sha:str):
    m=_json((root/"manifest.json").read_bytes())
    if m["source_identity"]["sha256"]!=expected_rocket_sha:
        raise PrivateBundleError("Wrong original Rocket ROM asset provenance")
    source=(root/m["data_file"]).read_bytes()
    def extract(e):
        a=e["offset"];b=a+e["length"]
        return source[a:b] if a>=0 and b<=len(source) else b""
    return _valid_pages(m["resources"],extract)

def original_rocket_coverage(pages:dict[str,bytes]):
    # Parse original-source R49 binary-search index, event page, layouts and
    # R51 tiles, preserving ALL original source IDs. No inference of NPC art.
    indexed=b"".join(pages[f"r49.index.{i:03}"] for i in range(3))
    found=None
    for i in range(2856):
        k,pg,at,n,header=struct.unpack_from("<IHHII",indexed,i*16)
        if k==KEY_ROCKET:
            found=(pg,at,n,header);break
    if found is None:raise PrivateBundleError("Original Rocket source map absent")
    pg,at,n,header=found
    raw=pages[f"r49.events.{pg:03}"][at:at+n]
    if len(raw)!=n or raw[:4]!=b"X49E" or struct.unpack_from("<I",raw,4)[0]!=KEY_ROCKET:
        raise PrivateBundleError("Rocket authentic R49 map header corrupted")
    cnt=raw[8]; data=raw[32:]
    if zlib.crc32(data)&0xffffffff!=struct.unpack_from("<I",raw,20)[0]:
        raise PrivateBundleError("Rocket original NPC CRC corrupted")
    viewport=[]
    for i in range(cnt):
        p=data[i*24:(i+1)*24]
        gfx=struct.unpack_from("<H",p,1)[0]
        x,y=struct.unpack_from("<hh",p,4)
        if x>=7 and x<=21 and y>=9 and y<=19 and x<24 and y<25:
            viewport.append((p[0],gfx,x,y))
    needed=sorted({gfx for _,gfx,_,_ in viewport})
    if needed!=list(SLOTS_ROCKET):
        raise PrivateBundleError("Authenticated Rocket landing source ID set changed")
    missing=[]
    for gfx in needed:
        prefix=f"r56.w1.s{gfx:04x}"
        for suffix in (".meta",".f00",".p00",".o00",".a00"):
            if prefix+suffix not in pages:missing.append(prefix+suffix)
    source_meta=b"".join(pages[f"r52.mapmeta.{i:03}"] for i in range(6))
    hit=None
    for i in range(2856):
        row=source_meta[i*32:(i+1)*32]
        if struct.unpack_from("<I",row,0)[0]==KEY_ROCKET:
            hit=row;break
    if hit is None or zlib.crc32(hit[:28])&0xffffffff!=struct.unpack_from("<I",hit,28)[0]:
        raise PrivateBundleError("Rocket source map profile CRC mismatch")
    desc=struct.unpack_from("<II",hit,20)
    if tuple(f"r53.w1.v2.t{d:08x}" for d in desc)!=ROCKET_TERRAIN:
        raise PrivateBundleError("Rocket original source terrain identity drift")
    for prefix in ROCKET_TERRAIN:
        meta=pages.get(prefix+".meta")
        if meta is None:missing.append(prefix+".meta");continue
        if meta[:4]!=b"X53T" or zlib.crc32(meta[:60])&0xffffffff!=struct.unpack_from("<I",meta,60)[0]:
            raise PrivateBundleError("Original Rocket tileset metadata corrupted")
        for suffix,n in zip("gmap",meta[34:38]):
            for i in range(n):
                rid=f"{prefix}.{suffix}{i:02}"
                if rid not in pages:missing.append(rid)
    if missing:raise PrivateBundleError("Missing authentic Rocket host pages: "+", ".join(missing))
    palette_contents=[]
    for gfx in needed:
        prefix=f"r56.w1.s{gfx:04x}"
        meta=pages[prefix+".meta"]
        if meta[:4]!=b"X56S" or meta[5]!=1 or struct.unpack_from("<H",meta,6)[0]!=gfx:
            raise PrivateBundleError("Original Rocket object graphics identity drift")
        if zlib.crc32(meta[:60])&0xffffffff!=struct.unpack_from("<I",meta,60)[0]:
            raise PrivateBundleError("Original Rocket sprite metadata CRC mismatch")
        for i,suffix in enumerate(("f","p","o","a")):
            size=struct.unpack_from("<I",meta,12+4*i)[0]
            crc=struct.unpack_from("<I",meta,28+4*i)[0]
            data=pages[f"{prefix}.{suffix}00"][:size]
            if zlib.crc32(data)&0xffffffff!=crc:
                raise PrivateBundleError("Original Rocket sprite section CRC mismatch")
        palette_contents.append(pages[prefix+".p00"][:32])
    return {
      "source_map_key":f"0x{KEY_ROCKET:06x}",
      "original_npcs":cnt,"first_viewport_npcs":len(viewport),
      "first_viewport_original_u16_graphics_ids":needed,
      "distinct_original_npc_palettes":len(set(palette_contents)),
      "unique_original_npc_source_records":len(viewport),
      "source_terrain_primary_secondary":list(desc),
      "source_geometry_integrity":"source-private R51 pages SHA verified",
      "original_Fly_playable":False,"original_script_execution_proven":False
    }

def compile_bundle(r49:Path,r51:Path,r52:Path,r53:Path,r56:Path,out:Path):
    if out.exists() and any(out.iterdir()):
        raise PrivateBundleError("Destination must be empty, never overwrite original assets")
    sources=[("r49",zip_manifest_pages(r49,"r49")),
             ("r51",zip_manifest_pages(r51,"r51")),
             ("r52",zip_manifest_pages(r52,"r52")),
             ("r53",folder_manifest_pages(r53,SOURCES["rocket"])),
             ("r56",folder_manifest_pages(r56,SOURCES["rocket"]))]
    pages={};provenance={}
    for prefix,entries in sources:
        for rid,data in entries.items():
            if rid in pages:raise PrivateBundleError("Collision between original XGBA resources: "+rid)
            pages[rid]=data
            provenance[rid]=prefix
    rocket=original_rocket_coverage(pages)
    out.mkdir(parents=True,exist_ok=True)
    filename="r62-private-original-three-world-provider.bin"
    entries=[]
    with (out/filename).open("xb") as f:
        for rid in sorted(pages):
            raw=pages[rid]
            at=f.tell()
            f.write(raw)
            entries.append({"id":rid,"offset":at,"length":len(raw),"sha256":_sha(raw)})
    identity={"id":"private-all-original-events-with-rocket-source-art",
              "sha256":_sha(json.dumps(SOURCES,sort_keys=True).encode())}
    manifest={"format":sidecar.FORMAT,"version":sidecar.VERSION,
              "source_identity":identity,"data_file":filename,
              "resources":entries}
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n")
    verified=sidecar.load_manifest(out/"manifest.json",
                                  expected_source_identity=identity)
    for rid in sorted(pages):
        data=b"".join(sidecar.iter_resource_chunks(verified,rid))
        if data!=pages[rid]:raise PrivateBundleError("Post-pack original resource drift: "+rid)
    counts={k:sum(v==k for v in provenance.values()) for k,_ in sources}
    report={
      "bundle":"R62 private original three-source event/grid/traits plus Rocket original 4bpp sprites and tiles",
      "ROM_source_sha256":SOURCES,
      "resources_per_provenance":counts,
      "resources":len(entries),"data_bytes":(out/filename).stat().st_size,
      "all_pages_host_SHA_verified":True,
      "rocket_landing_preflight":rocket,
      "heart_soul_original_art_complete":False,
      "cross_world_original_Fly_complete":False,
      "foreign_scripts_warp_events_flags_executable":False,
      "user_supplied_original_ROM_bytes_published_to_GitHub":False
    }
    (out/"private-evidence.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("r49","r51","r52","r53","r56","out"):
        parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(compile_bundle(args.r49,args.r51,args.r52,args.r53,args.r56,args.out),
                     sort_keys=True,indent=2))
if __name__=="__main__":
    main()
