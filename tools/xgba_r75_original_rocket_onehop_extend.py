#!/usr/bin/env python3
"""R75 OWNER-PRIVATE extension of R64 provider, original Rocket one-hop assets.

Run with the owner-owned ORIGINAL Rocket ROM. Never commit the output ZIP,
private original map manifests, game graphics, ROMs or saves to public Git.
All new R53/R56 resource bytes are source-authenticated by the established
R53 descriptor and R60 original graphics pointer-table parsers. Original R64
records are verified, preserved verbatim and not silently replaced.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, zipfile, zlib
from pathlib import Path
import xgba_r53_original_tileset_packs as r53
import xgba_r60_original_rocket_sprites as r60
from xgba_r68_fly_resource_closure import host_pages, ResourceClosureError

PAGE=16384
ORIGINAL_ROCKET_SHA=r60.SHA_ROCKET
ROCKET_SOURCE_MAPS={
  0x012302:(0x00e9ff80,0x00e9fdd0),
  0x012300:(0x00e9ff80,0x00ea0300),
  0x012304:(0x00e9ff80,0x00ea02e8),
}
FIRST_HOP_SOURCE_GFX=(5,26,46,59,100,105,215)
class PrivateOneHopError(ValueError):pass

def source_map_tiles(pages:dict[str,bytes],key:int)->tuple[int,int,int]:
    """Read authenticated R52 original source owner/format/descriptors."""
    try:
        buf=b"".join(pages[f"r52.mapmeta.{i:03d}"] for i in range(6))
    except KeyError as exc:raise PrivateOneHopError("Missing original R52 index") from exc
    found=[]
    for i in range(2856):
        row=buf[i*32:(i+1)*32]
        if len(row)<32:raise PrivateOneHopError("Original R52 index truncated")
        if struct.unpack_from("<I",row)[0]!=key:continue
        if zlib.crc32(row[:28])&0xffffffff!=struct.unpack_from("<I",row,28)[0]:
            raise PrivateOneHopError("Original map profile CRC mismatch")
        found.append((row[4],*struct.unpack_from("<II",row,20)))
    if len(found)!=1:raise PrivateOneHopError("Source map missing or duplicated")
    return found[0]

def required_rocket_tiles(pages:dict[str,bytes]):
    found=set()
    for key,expected in ROCKET_SOURCE_MAPS.items():
        version,primary,secondary=source_map_tiles(pages,key)
        if version!=2 or (primary,secondary)!=expected:
            raise PrivateOneHopError("Original Rocket one-hop R52 descriptor drift")
        found.add((primary,False));found.add((secondary,True))
    return sorted(found)

def add_page(data:bytearray,entries:list,existing:set,
             name:str,value:bytes):
    if not isinstance(name,str) or name in existing:
        raise PrivateOneHopError("Duplicate private source resource ID")
    if not 1<=len(value)<=PAGE:
        raise PrivateOneHopError("Original resource exceeds one guest MMIO page")
    offset=len(data);data.extend(value);existing.add(name)
    entries.append({"id":name,"offset":offset,"length":len(value),
                    "sha256":hashlib.sha256(value).hexdigest()})

def extend(private_parent:Path,original_rocket:Path,private_output:Path,
           *,allow_incomplete:bool=False)->dict:
    if private_output.exists():raise PrivateOneHopError("Refusing overwrite of private pack")
    rom=original_rocket.read_bytes()
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_ROCKET_SHA:
        raise PrivateOneHopError("Original complete Rocket 3.06 ROM SHA mismatch")
    verified=host_pages(private_parent) # SHA, range, source identity, no duplicates
    with zipfile.ZipFile(private_parent) as z:
        manifest=json.loads(z.read("manifest.json"))
        payload=bytearray(z.read(manifest["data_file"]))
    entries=list(manifest["resources"])
    existing={r["id"] for r in entries}
    additions=[];failures=[]
    for offset,secondary in required_rocket_tiles(verified):
        try:
            stem,meta,sections=r53.descriptor_asset(
                rom,1,2,offset,secondary)
            source_pages=[(stem+".meta",meta)]
            for letter,raw in zip("gmap",sections):
                for index,start in enumerate(range(0,len(raw),PAGE)):
                    source_pages.append((f"{stem}.{letter}{index:02d}",
                                         raw[start:start+PAGE].ljust(PAGE,b"\x00")))
            for name,value in source_pages:
                add_page(payload,additions,existing,name,value)
        except (r53.TilesetFormatError,PrivateOneHopError) as exc:
            failures.append({"type":"tileset","source_descriptor":f"0x{offset:08x}",
                             "reason":str(exc)})
    for gfx in FIRST_HOP_SOURCE_GFX:
        try:
            meta,sections,_audit=r60.original_object(rom,gfx)
            stem=f"r56.w1.s{gfx:04x}"
            source_pages=[(stem+".meta",meta)]+[
               (stem+"."+letter+"00",raw.ljust(PAGE,b"\x00"))
               for letter,raw in zip("fpoa",sections)]
            for name,value in source_pages:
                add_page(payload,additions,existing,name,value)
        except (r60.OriginalSpriteError,PrivateOneHopError) as exc:
            failures.append({"type":"sprite","original_graphics_id":gfx,
                             "reason":str(exc)})
    if failures and not allow_incomplete:
        raise PrivateOneHopError("Authentic sources refused; explicit --allow-incomplete required: "+
                                 json.dumps(failures))
    manifest["resources"]=entries+additions
    with zipfile.ZipFile(private_output,"x",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(manifest["data_file"],payload)
        z.writestr("manifest.json",json.dumps(manifest,sort_keys=True)+"\n")
    output=host_pages(private_output)
    if len(output)!=len(verified)+len(additions):
        raise PrivateOneHopError("Private extension integrity/count mismatch")
    for key,old in verified.items():
        if output[key]!=old:raise PrivateOneHopError("Parent resource mutated")
    return {"original_rocket_sha256":ORIGINAL_ROCKET_SHA,
            "verified_unchanged_original_resource_count":len(verified),
            "new_original_source_resource_count":len(additions),
            "verified_private_output_resources":len(output),
            "original_one_hop_sprites_requested":len(FIRST_HOP_SOURCE_GFX),
            "source_tileset_descriptors_requested":len(required_rocket_tiles(verified)),
            "quarantined_assets":failures,
            "native_emerald_original_gameplay_passed":False,
            "private_pack_never_publish_publicly":True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-parent",required=True,type=Path)
    p.add_argument("--original-rocket",required=True,type=Path)
    p.add_argument("--private-output",required=True,type=Path)
    p.add_argument("--allow-incomplete",action="store_true")
    args=p.parse_args()
    print(json.dumps(extend(args.private_parent,args.original_rocket,
                            args.private_output,allow_incomplete=args.allow_incomplete),
                     sort_keys=True,indent=2))
if __name__=="__main__":main()
