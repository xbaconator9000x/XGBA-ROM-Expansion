#!/usr/bin/env python3
"""R60: private original Rocket 3.06 FRLG event-sprite importer.

Given the user-owned SHA-pinned original ROM, validate the original graphics
pointer table, 36-byte ObjectEventGraphicsInfo fields, actual SpriteFrameImage
pointer chain and original palette-tag table. Publish only R56 *private*
native page resources: original 4bpp first frame, 16 original colors, source
8-byte OAM, and original animation bytecode. No copyrighted bytes in Git.
No surrogate Emerald art, fabricated game progress, or unsupported 48x48 OAM.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib
from xgba_resource_sidecar import FORMAT, VERSION, load_manifest

SHA_ROCKET="5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca"
GRAPHICS_TABLE=0x5d0b18
GRAPHICS_MAX=588
PALETTE_START=0x5c2000
PALETTE_END=0x5c3200
ROM_BASE=0x08000000
PAGE=16384
SHAPES={(8,8),(8,16),(8,32),(16,8),(16,16),(16,32),
        (32,8),(32,16),(32,32),(32,64),(64,32),(64,64)}

class OriginalSpriteError(ValueError): pass

def pointer(rom:bytes,field:int,required:int=1)->int:
    if field<0 or field+4>len(rom):
        raise OriginalSpriteError("Source pointer field outside original ROM")
    value=struct.unpack_from("<I",rom,field)[0]
    pos=value-ROM_BASE
    if value<ROM_BASE or pos<0 or pos+required>len(rom):
        raise OriginalSpriteError("Source pointer outside original ROM image")
    return pos

def original_object(rom:bytes,graphics_id:int):
    if hashlib.sha256(rom).hexdigest()!=SHA_ROCKET:
        raise OriginalSpriteError("Source Rocket original ROM SHA mismatch")
    if not isinstance(graphics_id,int) or not 0<=graphics_id<=GRAPHICS_MAX:
        raise OriginalSpriteError("No matching original event graphic ID")
    if (pointer(rom,GRAPHICS_TABLE,36)!=0x5c83d4 or
        pointer(rom,GRAPHICS_TABLE+588*4,36)!=0x5c3094):
        raise OriginalSpriteError("Authenticated original graphics root drift")
    info=pointer(rom,GRAPHICS_TABLE+4*graphics_id,36)
    tile,pal_tag,refl,size,w,h,flags,tracks=struct.unpack_from("<8H",rom,info)
    if tile!=0xffff or (w,h) not in SHAPES or size!=w*h//2:
        raise OriginalSpriteError("Unsupported authentic source OBJ shape")
    matches=[]
    for at in range(PALETTE_START,PALETTE_END,4):
        p,tag,pad=struct.unpack_from("<IHH",rom,at)
        if tag==pal_tag and pad==0 and ROM_BASE<=p<=ROM_BASE+len(rom)-32:
            matches.append((at,p-ROM_BASE))
    if len(matches)!=1:
        raise OriginalSpriteError("Original source palette identity ambiguous")
    pal_record,pal_offset=matches[0]
    palette=rom[pal_offset:pal_offset+32]
    oam_offset=pointer(rom,info+16,8)
    oam=rom[oam_offset:oam_offset+8]
    # Validate pointer chain from original descriptor -> image table -> frame0.
    images=pointer(rom,info+28,8)
    frame=pointer(rom,images,size)
    frame_length,unused=struct.unpack_from("<HH",rom,images+4)
    if frame_length!=size:
        raise OriginalSpriteError("Original source frame length mismatched")
    frames=rom[frame:frame+size]
    anim_table=pointer(rom,info+24,4)
    first_anim=pointer(rom,anim_table,4)
    commands=bytearray()
    for i in range(32):
        cmd=rom[first_anim+4*i:first_anim+4*i+4]
        if len(cmd)!=4:raise OriginalSpriteError("Original animation truncated")
        commands.extend(cmd)
        if struct.unpack_from("<H",cmd)[0]>=0xfffd:break
    else:raise OriginalSpriteError("Unbounded original animation commands")
    sections=(frames,palette,oam,bytes(commands))
    meta=bytearray(64)
    meta[:4]=b"X56S"
    meta[4]=1;meta[5]=1
    struct.pack_into("<H",meta,6,graphics_id)
    struct.pack_into("<I",meta,8,info)
    for i,section in enumerate(sections):
        struct.pack_into("<I",meta,12+i*4,len(section))
        struct.pack_into("<I",meta,28+i*4,zlib.crc32(section)&0xffffffff)
        meta[44+i]=(len(section)+PAGE-1)//PAGE
    meta[48:52]=bytes((0,1,w,h))
    struct.pack_into("<H",meta,52,1)
    struct.pack_into("<I",meta,60,zlib.crc32(meta[:60])&0xffffffff)
    audit={"gfx":graphics_id,"info":info,"pal_tag":pal_tag,
           "palette_record":pal_record,"palette_bytes_at":pal_offset,
           "frame_bytes_at":frame,"animation_bytes_at":first_anim,
           "width":w,"height":h,"section_lengths":list(map(len,sections))}
    return bytes(meta),sections,audit

def pack(rom:bytes,gfx_ids:list[int],out:Path):
    if hashlib.sha256(rom).hexdigest()!=SHA_ROCKET:
        raise OriginalSpriteError("Wrong original complete ROM")
    if not gfx_ids or len(gfx_ids)!=len(set(gfx_ids)):
        raise OriginalSpriteError("Nonempty unique graphics IDs required")
    if out.exists() and any(out.iterdir()):
        raise OriginalSpriteError("Refusing private output overwrite")
    out.mkdir(parents=True,exist_ok=True)
    filename="r60-private-original-rocket-sprites.bin"
    resources=[];audits=[]
    with (out/filename).open("xb") as f:
        for gfx in sorted(gfx_ids):
            meta,sections,audit=original_object(rom,gfx)
            audits.append(audit)
            stem=f"r56.w1.s{gfx:04x}"
            pages=[(stem+".meta",meta)]
            pages.extend((stem+"."+k+"00",value.ljust(PAGE,b"\0"))
                         for k,value in zip("fpoa",sections))
            for key,raw in pages:
                offset=f.tell();f.write(raw)
                resources.append({"id":key,"offset":offset,"length":len(raw),
                     "sha256":hashlib.sha256(raw).hexdigest()})
    manifest={"format":FORMAT,"version":VERSION,
      "source_identity":{"id":"original-rocket-3.06-npc-graphics","sha256":SHA_ROCKET},
      "data_file":filename,"resources":resources}
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n")
    load_manifest(out/"manifest.json")
    (out/"source-audit.json").write_text(json.dumps({
         "original_rom_sha256":SHA_ROCKET,
         "original_graphics_root":GRAPHICS_TABLE,
         "source_graphics":audits,"no_public_original_bytes":True,
         "real_original_emerald_fly_accepted":False},indent=2)+"\n")
    return manifest

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rocket",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--ids",type=int,nargs="+",default=[6,9,17,64])
    args=ap.parse_args()
    manifest=pack(args.rocket.read_bytes(),args.ids,args.out)
    print(json.dumps({"status":"R60_PRIVATE_EXACT_ROCKET_ORIGINAL_SPRITES",
      "sources":len(args.ids),"resource_pages":len(manifest["resources"]),
      "actual_three_world_fly":False},sort_keys=True))
if __name__=="__main__":main()
