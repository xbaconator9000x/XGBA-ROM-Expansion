#!/usr/bin/env python3
"""R48 source-owned, EXACT original NPC script/text pack from three USER ROMs.

Do not substitute authored dialogue. This strictly checks one authentic object
record in each original ROM and exports its original 9-byte GBA script and
original raw GBA-font dialogue. The only runtime change permitted is relocating
the script's original 0x08/0x09 ROM text pointer into the guest EWRAM buffer.

These three first NPCs are *acceptance witnesses* and not an import limit.
Full source coverage remains required by R47. Output is private, NEVER commit
the resulting .bin files, manifest or original dialogue to public GitHub.

One NPC per world:
  Original Emerald Littleroot 0:9 object 2; at (12,13)
  Original Rocket Edition Littleroot 0:9 object 2; at (14,13)
  Original HnS Goldenrod City 0:4 object 7; at (39,22)
All three scripts have precisely: loadword 0,<original text>; callstd 2; end.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys

import xgba_r34_binary_maps as r34

MAGIC=b"X48N"
VERSION=1
BUFFER_SIZE=256
HEADER_FORMAT="<4sBBBBBhhHIIHH5x"
HEADER_SIZE=struct.calcsize(HEADER_FORMAT)
SCRIPT_BYTES=9
GBA_BASE=0x08000000
START_OFFSET=32*1024*1024+983040
STRIDE=16384

@dataclass(frozen=True)
class Witness:
    name:str
    world:int
    group:int
    map:int
    npc_id:int
    x:int
    y:int
    sprite:int
    script_offset:int
    text_offset:int
    rom_sha256:str

WITNESSES=(
    Witness("emerald",0,0,9,2,12,13,17,0x1E8022,0x1E8ACF,
            "a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af"),
    Witness("rocket",1,0,9,2,14,13,17,0x215543,0x1DC3364,
            "5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca"),
    Witness("heart_soul",2,0,4,7,39,22,406,0x390519,0x3908E6,
            "cdfb9e1f83f72c05cb47af40fdf5635567b1973bcb759e070ad0971f67a49191"),
)


class NotOriginalNpcSource(ValueError):
    pass


def _find_map(discovered,witness):
    matching=[item for item in discovered["maps"]
              if item["group"]==witness.group and item["map"]==witness.map]
    if len(matching)!=1:
        raise NotOriginalNpcSource("Original NPC's numbered map is missing or duplicated")
    return matching[0]


def extract_npc_bytes(witness:Witness,rom:bytes):
    if hashlib.sha256(rom).hexdigest()!=witness.rom_sha256:
        raise NotOriginalNpcSource(f"{witness.name}: original complete game SHA-256 mismatch")
    if not 0xC0<=len(rom)<=64*1024*1024 or len(rom)%4:
        raise NotOriginalNpcSource("Invalid original GBA source length")
    parsed=r34.BinaryMapDiscovery(rom).discover(
        min_root_references=1,allow_null_slots=True)
    m=_find_map(parsed,witness)
    off=m["event_array_offsets"][0]
    if off is None or m["object_count"]<1 or off+m["object_count"]*24>len(rom):
        raise NotOriginalNpcSource("Original ROM object array absent/out of bounds")
    candidates=[]
    for i in range(m["object_count"]):
        raw=rom[off+i*24:off+(i+1)*24]
        if raw[0]==witness.npc_id:
            candidates.append(raw)
    if len(candidates)!=1:
        raise NotOriginalNpcSource("Original NPC local ID ambiguous/missing")
    obj=candidates[0]
    x,y=struct.unpack_from("<hh",obj,4)
    gfx=struct.unpack_from("<H",obj,1)[0]
    address=struct.unpack_from("<I",obj,16)[0]
    if ((x,y,gfx)!=(witness.x,witness.y,witness.sprite) or
        address!=GBA_BASE+witness.script_offset):
        raise NotOriginalNpcSource(f"{witness.name}: original NPC placement, graphics or source script changed")
    start=witness.script_offset
    if start+SCRIPT_BYTES>len(rom):
        raise NotOriginalNpcSource("Original NPC script points outside source ROM")
    script=rom[start:start+SCRIPT_BYTES]
    if script[:2]!=b"\x0f\x00" or script[6:]!=b"\x09\x02\x02":
        raise NotOriginalNpcSource("Original script is not the EXACT verified safe loadword/callstd/end sequence")
    original_text_ptr=struct.unpack_from("<I",script,2)[0]
    if original_text_ptr!=GBA_BASE+witness.text_offset:
        raise NotOriginalNpcSource("Original script pointer no longer points to same NPC's exact dialogue")
    text_end=rom.find(b"\xff",witness.text_offset,
                      min(len(rom),witness.text_offset+BUFFER_SIZE-HEADER_SIZE-SCRIPT_BYTES))
    if text_end<0:
        raise NotOriginalNpcSource("Original dialogue is unterminated/oversize")
    text=rom[witness.text_offset:text_end+1]
    if not text or text[-1]!=0xff or b"\x00\x00\x00" in text:
        # Allow native GBA controls, but reject obvious malformed or blank text.
        raise NotOriginalNpcSource("Original dialogue is invalid")
    header=struct.pack(HEADER_FORMAT,MAGIC,VERSION,
             witness.world,witness.group,witness.map,witness.npc_id,
             x,y,gfx,start,witness.text_offset,len(script),len(text))
    if len(header)!=HEADER_SIZE:
        raise AssertionError("R48 guest C payload ABI mismatch")
    payload=header+script+text
    payload+=bytes([0xff])*(BUFFER_SIZE-len(payload))
    if len(payload)!=BUFFER_SIZE:
        raise NotOriginalNpcSource("Original NPC payload exceeds 256-byte bounded guest arena")
    return payload,{
        "source_rom_sha256":witness.rom_sha256,
        "source_original_map":[witness.group,witness.map],
        "source_npc_local_id":witness.npc_id,
        "original_graphics_id":gfx,
        "original_position":[x,y],
        "original_script_rom_offset":start,
        "original_text_rom_offset":witness.text_offset,
        "exact_original_script_sha256":hashlib.sha256(script).hexdigest(),
        "exact_original_dialogue_sha256":hashlib.sha256(text).hexdigest(),
        "original_bytes_unmodified_in_pack":True,
        "script_pointer_relocation_required_on_guest":True,
        "original_script_executed_in_emerald_engine":False,
    }


def make_source_pack(source_paths:dict[str,Path],dest:Path):
    if set(source_paths)!={w.name for w in WITNESSES}:
        raise NotOriginalNpcSource("Need ALL THREE original user-owned ROM paths")
    dest=Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise NotOriginalNpcSource("Private original source output folder must be empty")
    dest.mkdir(parents=True,exist_ok=True)
    files=[]
    report={"milestone":"R48_ORIGINAL_THREE_ROM_NPC_SCRIPT_AND_DIALOGUE_INGEST",
            "source_authenticity_verified":True,
            "native_original_emerald_guest_script_execution_proven":False,
            "real_fly_to_foreign_original_map_proven":False,
            "all_original_npcs_imported":False,
            "scope":"Three genuine dialogue witnesses, NOT limit of full R47 game data.",
            "sources":{}}
    for witness in WITNESSES:
        path=Path(source_paths[witness.name])
        if not path.is_file():
            raise NotOriginalNpcSource(f"{witness.name}: original source not found")
        blob=path.read_bytes()
        data,provenance=extract_npc_bytes(witness,blob)
        resource=witness.name+".r48.npc"
        offset=START_OFFSET+STRIDE*witness.world
        filename="private-"+resource+".bin"
        (dest/filename).write_bytes(data)
        entry={"id":resource,"offset":offset,"length":len(data),
               "sha256":hashlib.sha256(data).hexdigest()}
        files.append(entry)
        report["sources"][witness.name]={
            **provenance,"private_resource":entry,
        }
    (dest/"r48_private_original_npc_provenance.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report,files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emerald",type=Path,required=True)
    parser.add_argument("--rocket",type=Path,required=True)
    parser.add_argument("--heart-soul",type=Path,required=True)
    parser.add_argument("--private-out",type=Path,required=True)
    args=parser.parse_args()
    report,files=make_source_pack({
        "emerald":args.emerald,"rocket":args.rocket,
        "heart_soul":args.heart_soul},args.private_out)
    print(json.dumps({"status":"PASS_R48_THREE_ORIGINAL_NPC_SCRIPTS_AND_DIALOGUE_EXTRACTED",
          "roms":list(report["sources"]),"assets":[r["id"] for r in files],
          "native_script_execution_proven":False},sort_keys=True))


if __name__=="__main__":
    main()
