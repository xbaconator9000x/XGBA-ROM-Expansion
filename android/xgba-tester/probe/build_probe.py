#!/usr/bin/env python3
"""R43: build the actual homebrew GBA ARM guest + SHA verified XGBA ZIP.

Only test-authored data and standard GBA startup header. Never embed any
commercial original game asset, save or source ROM in public CI artifacts.

Optional private mode: --emerald --rocket --heart-soul use local original GBA
SHA-256 digests as SOURCE DATA fingerprints, never upload their bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

BASE=32*1024*1024
GAME_CODE=b"XGBP"
WORLD_NAMES=("emerald.world","rocket.world","heart_soul.world")
WORLD_OFFSETS=(BASE+16384,BASE+32768,BASE+49152)
WORLD_LENGTH=64
SOURCE_ID="xgba-r43-homebrew-cartridge"

# Standard public GBA cartridge header logo sequence (156 bytes);
# solely a console boot signature, not a copied Pokémon sprite/game.
GBA_BOOT_SIGNATURE=bytes.fromhex(
    "24 FF AE 51 69 9A A2 21 3D 84 82 0A 84 E4 09 AD "
    "11 24 8B 98 C0 81 7F 21 A3 52 BE 19 93 09 CE 20 "
    "10 46 4A 4A F8 27 31 EC 58 C7 E8 33 82 E3 CE BF "
    "85 F4 DF 94 CE 4B 09 C1 94 56 8A C0 13 72 A7 FC "
    "9F 84 4D 73 A3 CA 9A 61 58 97 A3 27 FC 03 98 76 "
    "23 1D C7 61 03 04 AE 56 BF 38 84 00 40 A7 0E FD "
    "FF 52 FE 03 6F 95 30 F1 97 FB C0 85 60 D6 80 25 "
    "A9 63 BE 03 01 4E 38 E2 F9 A2 34 FF BB 3E 03 44 "
    "78 00 90 CB 88 11 3A 94 65 C0 7C 63 87 F0 3C AF "
    "D6 25 E4 8B 38 0A AC 72 21 D4 F8 07"
)


def sha(source):
    if isinstance(source,(bytes,bytearray)):
        return hashlib.sha256(source).hexdigest()
    digest=hashlib.sha256()
    with Path(source).open("rb") as file:
        for block in iter(lambda:file.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


def make_rom(arm,output):
    arm=Path(arm).read_bytes()
    if len(GBA_BOOT_SIGNATURE)!=156:
        raise ValueError("GBA boot signature length mismatched")
    if len(arm)<64 or len(arm)>2*1024*1024:
        raise ValueError("Expected authored freestanding ARM7 program under 2 MiB")
    header=bytearray(192)
    # ARM branch from 0x08000000 to 0x080000C0 (PC+0xB8)
    struct.pack_into("<I",header,0,0xEA00002E)
    header[4:160]=GBA_BOOT_SIGNATURE
    header[0xA0:0xAC]=b"XGBA PROBE  "
    header[0xAC:0xB0]=GAME_CODE
    header[0xB0:0xB2]=b"01"
    header[0xB2]=0x96
    header[0xBC]=0
    header[0xBD]=(-sum(header[0xA0:0xBD])-0x19)&255
    payload=bytes(header)+arm
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(payload)
    return payload


def world_message(name, original=None):
    # Source SHA binds a visible READ-ONLY fingerprint to locally supplied
    # original data; neither original bytes nor Nintendo graphics are copied.
    prefix={"emerald.world":"EMERALD","rocket.world":"ROCKET",
            "heart_soul.world":"JOHTO"}[name]
    if original is None:
        message=prefix+" DEMO SOURCE"
    else:
        original=Path(original)
        if not original.is_file() or original.stat().st_size not in (16*1024*1024,32*1024*1024):
            raise ValueError("Private source must be an original 16/32 MiB GBA ROM")
        message=prefix+" "+sha(original)[:16].upper()
    if not re.fullmatch("[A-Z0-9 ]+",message):
        raise ValueError("Text not covered by authored 5x7 font")
    encoded=message.encode("ascii")
    return encoded+b"\0"*(WORLD_LENGTH-len(encoded))


def build_bundle(program,output, originals=(None,None,None)):
    p=Path(program).read_bytes()
    if p[:4]!=struct.pack("<I",0xEA00002E) or p[0xAC:0xB0]!=GAME_CODE:
        raise ValueError("R43 test ROM has no authored XGBA homebrew startup")
    out=Path(output)
    out.parent.mkdir(parents=True,exist_ok=True)
    resources=[]
    sidecar=out.parent/"sidecar.bin"
    with sidecar.open("wb") as data:
        for name,offset,original in zip(WORLD_NAMES,WORLD_OFFSETS,originals):
            text=world_message(name,original)
            if len(text)!=WORLD_LENGTH:
                raise ValueError("Unexpected authored world resource size")
            data.seek(offset)
            data.write(text)
            resources.append({"id":name,"offset":offset,
                              "length":len(text),"sha256":sha(text)})
    manifest={"format":"xgba-resource-manifest","version":1,
              "source_identity":{"id":SOURCE_ID,"sha256":sha(p)},
              "data_file":"sidecar.bin","resources":resources}
    m=out.parent/"manifest.json"
    m.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf8")
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as package:
        package.writestr("game.gba",p)
        package.write(m,"manifest.json")
        package.write(sidecar,"sidecar.bin")
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm-binary",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--emerald",type=Path)
    parser.add_argument("--rocket",type=Path)
    parser.add_argument("--heart-soul",type=Path)
    args=parser.parse_args()
    folder=args.out.parent
    game=folder/"game.gba"
    make_rom(args.arm_binary,game)
    report=build_bundle(game,args.out,(args.emerald,args.rocket,args.heart_soul))
    print(json.dumps({"game_sha256":report["source_identity"]["sha256"],
                      "source_resources":list(WORLD_NAMES),
                      "actual_original_source_files_supplied":sum(
                          x is not None for x in (args.emerald,args.rocket,args.heart_soul)),
                      "original_rom_bytes_in_zip":False,
                      "sidecar_beyond_32MiB":True,
                      "output":str(args.out)},sort_keys=True))


if __name__=="__main__":
    main()
