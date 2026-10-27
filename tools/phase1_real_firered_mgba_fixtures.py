#!/usr/bin/env python3
"""Deterministic native Flash fixtures. Do not mistake a synthetic save for an in-game save."""
from pathlib import Path
import argparse, hashlib, json, struct

SECTOR=4096
SIG=0x08012025
def sector(index, counter, valid=True, marker=0):
    b=bytearray(SECTOR)
    # SaveBlock2 filler_B20 (offset 0xB80): distinct payload witness.
    # A single aligned marker byte gives a 16-bit additive checksum of marker.
    b[0xB80] = marker
    struct.pack_into("<HHII", b, 0xFF4, index, marker, SIG if valid else 0, counter)
    return b

def slot(data, physical, counter, corrupt=None, mixed=False):
    for i in range(14):
        ident = ({"id": 14, "id15": 15, "id65535": 65535}.get(corrupt, i) if i == 6 else i)
        good = not (corrupt == "signature" and i == 6)
        c = counter + (1 if mixed and i == 13 else 0)
        data[(physical*14+i)*SECTOR:(physical*14+i+1)*SECTOR]=sector(ident,c,good,(0xA5 if physical == 0 else 0x5A) if i == 0 else 0)

def emit(root, rom):
    root.mkdir(parents=True,exist_ok=True)
    records=[]
    variants={
        "empty":(False,False,None,False),
        "slot0":(True,False,None,False),
        "both":(True,True,None,False),
        "malformed_id14":(True,True,"id",False),
        "mixed_counters":(True,True,None,True),
        "malformed_id15":(True,True,"id15",False),
        "malformed_id65535":(True,True,"id65535",False),
        "older_slot_fallback":(True,True,"signature",False),
    }
    for name,(old,new,corrupt,mixed) in variants.items():
        b=bytearray(bytes([0xFF])*(32*SECTOR))
        if old:slot(b,0,0)
        if new:slot(b,1,1,corrupt,mixed)
        p=root/(name+".sav");p.write_bytes(b)
        records.append({"name":name,"sha256":hashlib.sha256(b).hexdigest(),"size":len(b),"fixture_not_game_generated":True})
    original=Path(rom).read_bytes()
    assert len(original)>=0xC0 and original[0xAC:0xB0]==b"BPRE", "unexpected pinned FireRed game code"
    altered=bytearray(original)
    altered[0xAC:0xB0]=b"ZZZZ"
    altered[0xBD]=(-sum(altered[0xA0:0xBD])-0x19)&0xFF
    (root/"firered_header_changed.gba").write_bytes(altered)
    records.append({"name":"header_changed","sha256":hashlib.sha256(altered).hexdigest(),"size":len(altered),"original_game_code":"BPRE","altered_game_code":"ZZZZ","header_checksum_recalculated":True})
    (root/"fixture_manifest.json").write_text(json.dumps({"source_rom_sha256":hashlib.sha256(original).hexdigest(),"cases":records,"phase1_gates":"FAIL_INCOMPLETE","independent_approvals":0},indent=2)+chr(10))
    print(json.dumps({"fixtures":len(records),"names":[x["name"] for x in records]}))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    p.add_argument("--rom",required=True)
    a=p.parse_args()
    emit(Path(a.output),a.rom)
