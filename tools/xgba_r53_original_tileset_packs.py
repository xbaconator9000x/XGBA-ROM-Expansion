#!/usr/bin/env python3
"""R53 private genuine-source tileset compiler for original Emerald, Rocket and HnS.

Reads the SHA-pinned *user-owned* original ROMs and R51/R52 source indexes.
For each distinct source tileset descriptor, decodes exactly the game's original
4bpp graphics, original 8-word metatiles, full metadata and palette slots.
It writes only to a PRIVATE local XGBA host-side resource pack. Public tests
use wholly authored graphics fixtures, never copyrighted source asset bytes.

Critical safety: a compressed descriptor MUST use a valid GBA BIOS LZ77 0x10
stream. Alternate compression and malformed pointers are quarantined, not
guessed, silently reinterpreted as raw 4bpp, or substituted with Emerald art.

The standard resource adapter only transfers <=16KiB at once; larger tilesets
are split into SHA-verified 16KiB resources with separate CRC-protected 64-byte
metadata. This is a source asset pipeline, NOT evidence of live foreign Fly.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

import xgba_r51_original_grid_pages as r51
import xgba_resource_sidecar as sidecar
import xgba_r53_smol as smol

PAGE=16384
META_BYTES=64
R51_INDEX_BYTES=32
R52_INDEX_BYTES=32
WORLDS=("emerald","rocket","heart_soul")
SHA=tuple(v[0] for v in r51.SOURCES.values())
ALL_MAPS=2856
MAX_DECODE=65536
MAX_TILES=1024
GRAPHIC_SECTIONS=("g","m","a","p")
MAP_FMT="<IHHIIIIII"
R52_FMT="<I4BHH4BIIII"

class TilesetFormatError(ValueError):
    pass

def _u32(blob,off):
    if off<0 or off>len(blob)-4:raise TilesetFormatError("ROM u32 source out of range")
    return struct.unpack_from("<I",blob,off)[0]

def _ptr(blob,raw,length):
    if not (0x08000000<=raw<0x08000000+len(blob)):
        raise TilesetFormatError("Source ROM pointer not in original cartridge")
    start=raw-0x08000000
    if length<0 or length>len(blob)-start:
        raise TilesetFormatError("Source ROM pointer length exceeds image")
    return start

def gba_lz77(blob,off,*,maximum=MAX_DECODE):
    """Strict BIOS LZ77 0x10 decoder; no unbounded allocations or bad backrefs."""
    if off<0 or off+4>len(blob) or blob[off]!=0x10:
        raise TilesetFormatError("Unsupported compressed tileset header (not 0x10 LZ77)")
    size=blob[off+1] | blob[off+2]<<8 | blob[off+3]<<16
    if not 1<=size<=maximum:
        raise TilesetFormatError("LZ77 output size exceeds bounded native graphic limit")
    i=off+4
    out=bytearray()
    while len(out)<size:
        if i>=len(blob):raise TilesetFormatError("Truncated LZ77 flags")
        flags=blob[i];i+=1
        for bit in range(8):
            if len(out)==size:break
            if not (flags&(0x80>>bit)):
                if i>=len(blob):raise TilesetFormatError("Truncated LZ77 literal")
                out.append(blob[i]);i+=1
            else:
                if i+2>len(blob):raise TilesetFormatError("Truncated LZ77 match")
                a,b=blob[i:i+2];i+=2
                run=(a>>4)+3
                dist=((a&15)<<8 | b)+1
                if dist>len(out) or len(out)+run>size:
                    raise TilesetFormatError("Invalid LZ77 backref length or displacement")
                for _ in range(run):out.append(out[-dist])
    return bytes(out)

def descriptor_asset(blob,world,version,desc_offset,is_secondary):
    """Decode one ORIGINAL source tileset, failing closed on unverified formats."""
    if not (0<=world<3 and 0<=version<=3 and 0<=desc_offset<=len(blob)-24):
        raise TilesetFormatError("Invalid original tileset descriptor identity")
    desc=blob[desc_offset:desc_offset+24]
    compressed=desc[0]&1
    # HnS uses additional packed bits for night-time palette swaps; retain
    # descriptor bytes for provenance rather than mistaking flags for a pointer.
    declared_secondary=desc[1]
    if declared_secondary not in (0,1) or declared_secondary!=int(is_secondary):
        raise TilesetFormatError("Original tileset primary/secondary flag mismatch")
    tiles_ptr,pal_ptr,meta_ptr,attr_ptr=struct.unpack_from("<4I",desc,4)
    primary_count=640 if version in (1,2) else 512
    tile_count=(1024-primary_count) if is_secondary else primary_count
    meta_count=tile_count
    pal_count=(13-(7 if version in (1,2) else 6)) if is_secondary else (7 if version in (1,2) else 6)
    attr_bytes=4 if version==1 else 2
    if not (0<tile_count<=MAX_TILES and 0<pal_count<=13):
        raise TilesetFormatError("Original source tileset dimensions invalid")
    tile_at=_ptr(blob,tiles_ptr,4 if compressed else tile_count*32)
    if compressed:
        # Modern Emerald-derived hacks (including HnS) use packed 'Smol'
        # modes 1–6 instead of only legacy BIOS LZ77 0x10. The original
        # source uses a low-nibble mode field and a bitstream header.
        # Decode only attested formats, never reinterpret as raw graphics.
        try:
            if blob[tile_at] == 0x10:
                graphics=gba_lz77(blob,tile_at)
            elif (blob[tile_at]&0x0f) in (1,2,3,4,5,6):
                graphics=smol.decode(blob,tile_at,max_output=MAX_DECODE)
            else:
                raise TilesetFormatError(
                    "Unsupported original source compressed tileset format")
        except smol.SmolError as exc:
            raise TilesetFormatError("Invalid original Smol compressed tileset: "+str(exc)) from exc
        # Native Emerald reserves 512 secondary tile slots, but the
        # ORIGINAL LZ77/Smol data often holds far fewer. The field renderer
        # clears VRAM at map load and copies only the decompressed source
        # length; do NOT require exactly 512 (or 384) source tiles.
        # Preserve the exact decoded byte length, not a padded/fabricated
        # copy of the source graphics. The guest uses AllocZeroed for the
        # unused reserved slots, exactly mirroring cleared BG VRAM.
        if not 32<=len(graphics)<=tile_count*32 or len(graphics)%32:
            raise TilesetFormatError(
                "Original graphics size outside reserved source tile capacity")
    else:
        graphics=bytes(blob[tile_at:tile_at+tile_count*32])
    metatiles=bytes(blob[_ptr(blob,meta_ptr,meta_count*16):][:meta_count*16])
    attributes=bytes(blob[_ptr(blob,attr_ptr,meta_count*attr_bytes):][:meta_count*attr_bytes])
    # Secondary GBA tilesets have full palette arrays including the primary
    # slots; the original field renderer selects only the secondary range.
    pal_start=0 if not is_secondary else (7 if version in (1,2) else 6)*32
    palettes=bytes(blob[_ptr(blob,pal_ptr,pal_start+pal_count*32)+pal_start:][:pal_count*32])
    if not 32<=len(graphics)<=tile_count*32 or len(graphics)%32 or \
       len(metatiles)!=meta_count*16 or \
       len(attributes)!=meta_count*attr_bytes or len(palettes)!=pal_count*32:
        raise TilesetFormatError("Original tileset arrays have inconsistent lengths")
    sections=(graphics,metatiles,attributes,palettes)
    head=bytearray(META_BYTES)
    head[:4]=b"X53T"
    head[4:8]=bytes((world,version,int(is_secondary),compressed))
    struct.pack_into("<5I",head,8,desc_offset,*map(len,sections))
    struct.pack_into("<2H",head,28,tile_count,meta_count)
    struct.pack_into("<6B",head,32,attr_bytes,pal_count,
                     *[(len(part)+PAGE-1)//PAGE for part in sections])
    for i,part in enumerate(sections):
        struct.pack_into("<I",head,40+4*i,zlib.crc32(part)&0xffffffff)
    struct.pack_into("<I",head,56,zlib.crc32(desc)&0xffffffff)
    struct.pack_into("<I",head,60,zlib.crc32(head[:60])&0xffffffff)
    ident=f"r53.w{world}.v{version}.t{desc_offset:08x}"
    return ident,bytes(head),sections

def source_tilesets(roms,r51_index,r52_index,*,strict_sources=True):
    """Dedup by (world,version,descriptor) and flag unsupported, never conceal."""
    if len(roms)!=3 or len(r51_index)<ALL_MAPS*R51_INDEX_BYTES or \
       len(r52_index)<ALL_MAPS*R52_INDEX_BYTES:
        raise TilesetFormatError("Three source ROMs and full source map indexes required")
    if strict_sources:
        for i,blob in enumerate(roms):
            if hashlib.sha256(blob).hexdigest()!=SHA[i]:
                raise TilesetFormatError(f"{WORLDS[i]} original full-ROM SHA mismatch")
    compiled={}
    errors={}
    map_ok=0
    usage=Counter()
    for i in range(ALL_MAPS):
        rk=struct.unpack_from(MAP_FMT,r51_index,i*R51_INDEX_BYTES)[0]
        p=struct.unpack_from(R52_FMT,r52_index,i*R52_INDEX_BYTES)
        key,version,_,_,_,_,_,_,_,flags,_,_,primary,secondary,_=p
        if key!=rk or key>>16>=3:
            raise TilesetFormatError("R51 and R52 original source map identities diverge")
        world=key>>16
        if not (flags&1):
            errors[f"map.{key:08x}"]="Unsupported original source layout version"
            continue
        wanted=[(world,version,primary,False),(world,version,secondary,True)]
        map_fail=False
        for w,v,desc,second in wanted:
            identity=(w,v,desc)
            if identity not in compiled and identity not in errors:
                try:compiled[identity]=descriptor_asset(roms[w],w,v,desc,second)
                except TilesetFormatError as exc:
                    errors[identity]=str(exc)
            if identity in errors:
                map_fail=True
            else:usage[identity]+=1
        if not map_fail:map_ok+=1
    return compiled,errors,{"maps":ALL_MAPS,"two_original_tilesets_decodable_maps":map_ok,
       "distinct_decoded_original_tilesets":len(compiled),
       "unsupported_source_tilesets":len([k for k in errors if isinstance(k,tuple)]),
       "unsupported_source_map_layouts":len([k for k in errors if isinstance(k,str)]),
       "source_roms_sha_verified":strict_sources,
       "actual_original_emerald_fly_completed":False,
       "graphics_not_installed_into_original_emerald_yet":True}

def write_private_pack(compiled,errors,report,out):
    out=Path(out)
    if out.exists() and any(out.iterdir()):
        raise TilesetFormatError("Private R53 output directory must be empty")
    out.mkdir(parents=True,exist_ok=True)
    identity={"id":"private-original-three-world-tilesets",
       "sha256":hashlib.sha256("".join(SHA).encode()).hexdigest()}
    filename="r53-private-original-source-tilesets.bin"
    entries=[]
    with (out/filename).open("xb") as fd:
        for k in sorted(compiled):
            resource,header,sections=compiled[k]
            pairs=[(resource+".meta",header)]
            for prefix,source in zip(GRAPHIC_SECTIONS,sections):
                for i,off in enumerate(range(0,len(source),PAGE)):
                    pairs.append((f"{resource}.{prefix}{i:02d}",
                        source[off:off+PAGE].ljust(PAGE,b"\x00")))
            for rid,payload in pairs:
                off=fd.tell()
                fd.write(payload)
                entries.append({"id":rid,"offset":off,"length":len(payload),
                               "sha256":hashlib.sha256(payload).hexdigest()})
    manifest={"format":sidecar.FORMAT,"version":sidecar.VERSION,
       "source_identity":identity,"data_file":filename,"resources":entries}
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n")
    (out/"private-report.json").write_text(json.dumps({
       **report,"unreadable_source_records":{str(k):v for k,v in errors.items()}},
       sort_keys=True,indent=2)+"\n")
    sidecar.load_manifest(out/"manifest.json",expected_source_identity=identity)
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in WORLDS:p.add_argument("--"+name.replace("_","-"),type=Path,required=True)
    p.add_argument("--r51-pack",type=Path,required=True)
    p.add_argument("--r52-pack",type=Path,required=True)
    p.add_argument("--private-out",type=Path,required=True)
    args=p.parse_args()
    roms=tuple(getattr(args,n).read_bytes() for n in WORLDS)
    with zipfile.ZipFile(args.r51_pack) as z:
        r51_bytes=z.read("private-r51-original-terrain.bin")[:ALL_MAPS*R51_INDEX_BYTES]
    with zipfile.ZipFile(args.r52_pack) as z:
        r52_bytes=z.read("r52-private-source-map-profiles.bin")[:ALL_MAPS*R52_INDEX_BYTES]
    compiled,errors,report=source_tilesets(roms,r51_bytes,r52_bytes)
    manifest=write_private_pack(compiled,errors,report,args.private_out)
    print(json.dumps({"distinct_original_tilesets":len(compiled),
      "decodable_original_maps":report["two_original_tilesets_decodable_maps"],
      "quarantined_original_source_descriptors":report["unsupported_source_tilesets"],
      "verified_private_resources":len(manifest["resources"]),
      "foreign_fly_complete":False},sort_keys=True))

if __name__=="__main__":main()
