#!/usr/bin/env python3
"""R56 strict PRIVATE source-owned original NPC frame/palette/OAM/animation pack.

Original 16-bit graphics IDs must be independently resolved from each source
ROM's original object graphics table. This importer checks that each supplied
descriptor's four source pointers REALLY point into the SHA-pinned original
ROM and authenticates the pointed-to bytes. It never guesses an object ID,
manufactures source art, modifies a ROM, or claims a successful Fly.

The authoring input is an audited table-address manifest, not raw arbitrary
replacement PNG art. No ROM bytes or private manifests belong in public Git.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib
import xgba_r53_original_tileset_packs as r53
import xgba_r53_smol as smol
import xgba_r51_original_grid_pages as r51
import xgba_resource_sidecar as sidecar

PAGE=16384
SECTIONS=("f","p","o","a")
MAGIC=b"X56S"
WORLD_NAMES=("emerald","rocket","heart_soul")
SOURCE_SHA=tuple(v[0] for v in r51.SOURCES.values())
SECTION_LIMITS={"f":(32,8192,32),"p":(32,32,32),
                "o":(4,512,4),"a":(4,1024,2)}
class OriginalObjectSourceError(ValueError): pass

def _checked_u32(data:bytes,offset:int)->int:
    if offset<0 or offset+4>len(data):
        raise OriginalObjectSourceError("Original source pointer field outside ROM")
    return struct.unpack_from("<I",data,offset)[0]

def extract_sprite(rom:bytes,record:dict,*,expected_world:int):
    """Return exact unmodified decoded source data + CRC-bound 64-byte metadata.

    The provided original descriptor must *contain* all four raw ROM pointers.
    A fabricated declared source offset that disagrees with any pointer is
    rejected before any content is published. A separate original graphics
    table audit must still validate 16-bit gfx ID -> descriptor ownership.
    """
    if not isinstance(record,dict):
        raise OriginalObjectSourceError("Original sprite entry must be an object")
    world=record.get("world")
    gfx_id=record.get("original_id")
    desc=record.get("descriptor_offset")
    width=record.get("width")
    height=record.get("height")
    frames=record.get("frame_count")
    compression=record.get("compression")
    if type(world) is not int or world!=expected_world or world not in range(3) or \
       type(gfx_id) is not int or not 0<=gfx_id<=65535 or \
       type(desc) is not int or not 0<=desc<=0x01ffffff or \
       type(width) is not int or not 8<=width<=64 or width%8 or \
       type(height) is not int or not 8<=height<=64 or height%8 or \
       type(frames) is not int or not 1<=frames<=8 or \
       type(compression) is not int or compression not in range(7):
        raise OriginalObjectSourceError("Invalid source-qualified 16-bit graphics metadata")
    size=width*height//2*frames
    if size>SECTION_LIMITS["f"][1]:
        raise OriginalObjectSourceError("Original sprite frames exceed GBA bounded size")
    parts=record.get("sections")
    if not isinstance(parts,dict) or set(parts)!=set(SECTIONS):
        raise OriginalObjectSourceError("All four original frame/palette/OAM/animation sections required")
    found=[]
    for kind in SECTIONS:
        item=parts[kind]
        if not isinstance(item,dict) or \
           type(item.get("pointer_field_offset")) is not int or \
           type(item.get("source_offset")) is not int:
            raise OriginalObjectSourceError("Source descriptor must contain original pointer evidence")
        pfield=item["pointer_field_offset"]
        original=item["source_offset"]
        if pfield<desc or pfield+4>desc+64 or (pfield&3) or \
           original<0 or original>=len(rom):
            raise OriginalObjectSourceError("Descriptor pointer identity not bounded")
        if _checked_u32(rom,pfield)!=0x08000000+original:
            raise OriginalObjectSourceError("Original ROM pointer does not match claimed sprite data")
        if kind=="f":
            if compression==0:
                if original+size>len(rom):
                    raise OriginalObjectSourceError("Raw original frames exceed ROM")
                chunk=rom[original:original+size]
            else:
                try:
                    if compression==1:
                        chunk=r53.gba_lz77(rom,original,maximum=SECTION_LIMITS["f"][1])
                    else:
                        if (rom[original]&15)!=compression:
                            raise OriginalObjectSourceError("Original Smol mode mismatches source declaration")
                        chunk=smol.decode(rom,original,max_output=SECTION_LIMITS["f"][1])
                except (r53.TilesetFormatError,smol.SmolError) as exc:
                    raise OriginalObjectSourceError("Invalid original sprite compression: "+str(exc)) from exc
            if len(chunk)!=size:
                raise OriginalObjectSourceError("Original decoded sprite size != authentic OAM frame dimensions")
        else:
            if type(item.get("size")) is not int:
                raise OriginalObjectSourceError("Original non-frame section needs exact size")
            length=item["size"]
            lo,hi,align=SECTION_LIMITS[kind]
            if length<lo or length>hi or length%align or original+length>len(rom):
                raise OriginalObjectSourceError("Original sprite section size is invalid")
            chunk=rom[original:original+length]
        found.append(chunk)
    head=bytearray(64)
    head[:4]=MAGIC
    head[4:6]=bytes((1,world))
    struct.pack_into("<H",head,6,gfx_id)
    struct.pack_into("<I",head,8,desc)
    for i,part in enumerate(found):
        struct.pack_into("<I",head,12+4*i,len(part))
        struct.pack_into("<I",head,28+4*i,zlib.crc32(part)&0xffffffff)
        head[44+i]=(len(part)+PAGE-1)//PAGE
    head[48:52]=bytes((compression,1,width,height))
    struct.pack_into("<H",head,52,frames)
    struct.pack_into("<I",head,60,zlib.crc32(head[:60])&0xffffffff)
    identity=f"r56.w{world}.s{gfx_id:04x}"
    return identity,bytes(head),tuple(found)

def compile_private_originals(roms,definitions,*,strict_sources=True):
    if set(roms)!=set(WORLD_NAMES):
        raise OriginalObjectSourceError("Three source ROMs must be identified by original world")
    if strict_sources:
        for world,name in enumerate(WORLD_NAMES):
            if hashlib.sha256(roms[name]).hexdigest()!=SOURCE_SHA[world]:
                raise OriginalObjectSourceError(name+" original ROM SHA-256 mismatch")
    if not isinstance(definitions,list) or not definitions:
        raise OriginalObjectSourceError("Must supply original source sprite pointer witnesses")
    compiled={}
    for record in definitions:
        world=record.get("world") if isinstance(record,dict) else None
        if type(world) is not int or world not in range(3):
            raise OriginalObjectSourceError("Source world is required")
        identity,meta,sections=extract_sprite(roms[WORLD_NAMES[world]],record,expected_world=world)
        if identity in compiled:
            raise OriginalObjectSourceError("Duplicate world-qualified original graphics ID")
        compiled[identity]=(meta,sections)
    return compiled

def write_private_pack(compiled,private_out:Path):
    root=Path(private_out)
    if root.exists() and any(root.iterdir()):
        raise OriginalObjectSourceError("Private output must be a new empty directory")
    root.mkdir(parents=True,exist_ok=True)
    records=[]
    datafile="r56-private-original-obj-resources.bin"
    with (root/datafile).open("xb") as output:
        for name in sorted(compiled):
            meta,parts=compiled[name]
            resources=[(name+".meta",meta)]
            resources.extend((name+"."+suffix+"00",blob.ljust(PAGE,b"\\x00"))
                             for suffix,blob in zip(SECTIONS,parts))
            for resource,data in resources:
                start=output.tell()
                output.write(data)
                records.append({"id":resource,"offset":start,
                  "length":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    identity={"id":"private-original-three-world-objects",
              "sha256":hashlib.sha256("|".join(SOURCE_SHA).encode()).hexdigest()}
    manifest={"format":sidecar.FORMAT,"version":sidecar.VERSION,
              "source_identity":identity,"data_file":datafile,
              "resources":records}
    (root/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\\n")
    sidecar.load_manifest(root/"manifest.json",expected_source_identity=identity)
    (root/"R56_PRIVATE_SOURCE_SCOPE.json").write_text(json.dumps({
       "exact_original_sprite_entries":len(compiled),
       "original_roms_sha_verified":True,
       "native_emerald_obj_installer_complete":False,
       "native_original_fly_journey_complete":False,
       "original_sprite_id_ownership_requires_table_audit":True,
       "no_public_source_art":True},sort_keys=True,indent=2)+"\\n")
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in WORLD_NAMES:
        parser.add_argument("--"+name.replace("_","-"),type=Path,required=True)
    parser.add_argument("--original-pointer-spec",type=Path,required=True)
    parser.add_argument("--private-out",type=Path,required=True)
    args=parser.parse_args()
    roms={name:getattr(args,name).read_bytes() for name in WORLD_NAMES}
    spec=json.loads(args.original_pointer_spec.read_text())
    compiled=compile_private_originals(roms,spec)
    result=write_private_pack(compiled,args.private_out)
    print(json.dumps({"status":"R56_PRIVATE_ORIGINAL_SPRITE_BYTES_PACKED",
      "source_qualified_ids":len(compiled),"resources":len(result["resources"]),
      "original_fly_complete":False},sort_keys=True))
if __name__=="__main__":
    main()
