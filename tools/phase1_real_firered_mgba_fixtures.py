#!/usr/bin/env python3
"""Deterministic native Flash fixtures. Do not mistake a synthetic save for an in-game save."""
from pathlib import Path
import argparse, hashlib, json, struct

SECTOR=4096
SECTOR_DATA_SIZE=0xF80
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

def checksum(data, size):
    # Pinned src/save.c CalculateChecksum: folded little-endian u32 sum.
    assert size % 4 == 0 and size <= SECTOR_DATA_SIZE
    total = sum(struct.unpack_from("<I", data, i)[0] for i in range(0, size, 4)) & 0xFFFFFFFF
    return ((total >> 16) + total) & 0xFFFF

def make_pallet_fixture(data, null_layout=False, continue_warp=False):
    # Still synthetic, not a game-generated player save.
    slot(data, 0, 0)
    sb2 = memoryview(data)[:SECTOR]
    sb2[:4] = bytes((0xCD, 0xBF, 0xBE, 0xFF))  # Gen3 RED + terminator
    struct.pack_into("<H", sb2, 0xFF6, checksum(sb2, 0xF24))
    sb1 = memoryview(data)[SECTOR:2*SECTOR]
    struct.pack_into("<hh", sb1, 0, 11, 10)
    struct.pack_into("<bbbBhh", sb1, 4, 3, 0, -1, 0, 11, 10)
    if continue_warp:
        # Pinned global.h SaveBlock2+0x009 and SaveBlock1+0x000C;
        # save_location.h CONTINUE_GAME_WARP bit 0. This deliberately
        # selects CB2_LoadMap rather than the ordinary ReturnToFieldLocal.
        sb2[9] |= 1
        struct.pack_into("<bbbBhh", sb1, 0x0C, 3, 0, -1, 0, 11, 10)
        struct.pack_into("<H", sb2, 0xFF6, checksum(sb2, 0xF24))
    struct.pack_into("<H", sb1, 0x32, 0 if null_layout else 78)
    struct.pack_into("<H", sb1, 0xFF6, checksum(sb1, SECTOR_DATA_SIZE))

def verify_authored_pallet(source):
    source = Path(source)
    groups = json.loads((source / "data/maps/map_groups.json").read_text())
    layouts = json.loads((source / "data/layouts/layouts.json").read_text())["layouts"]
    assert groups["group_order"][3] == "gMapGroup_TownsAndRoutes"
    assert groups["gMapGroup_TownsAndRoutes"][0] == "PalletTown"
    assert layouts[77]["id"] == "LAYOUT_PALLET_TOWN"
    return {"map_group": 3, "map_num": 0, "layout_id": 78,
            "pinned_map_groups_blob": "8c382f504d208286161903244772c93138cd7662",
            "pinned_layouts_blob": "41d0eb1b5e51fa75d535b5a098bae2bd650f710d",
            "pinned_global_header_blob": "77155b09014aa854fcf87260e6ad2969e222da53"}

def emit(root, rom, source):
    root.mkdir(parents=True,exist_ok=True)
    records=[]
    authored = verify_authored_pallet(source)
    variants={
        "empty":(False,False,None,False),
        "slot0":(True,False,None,False),
        "both":(True,True,None,False),
        "malformed_id14":(True,True,"id",False),
        "mixed_counters":(True,True,None,True),
        "mixed_counter_tail0":(True,True,None,False),
        "mixed_counter_tail1":(True,True,None,False),
        "mixed_counter_tail3":(True,True,None,False),
        "malformed_id15":(True,True,"id15",False),
        "malformed_id65535":(True,True,"id65535",False),
        "older_slot_fallback":(True,True,"signature",False),
        "pallet_valid":(True,False,None,False),
        "pallet_null_layout":(True,False,None,False),
        "pallet_continue_warp":(True,False,None,False),
    }
    for name,(old,new,corrupt,mixed) in variants.items():
        b=bytearray(bytes([0xFF])*(32*SECTOR))
        if old:slot(b,0,0)
        if new:slot(b,1,1,corrupt,mixed)
        if name == "mixed_counter_tail1":
            # All 14 sectors remain checksum-valid: first 13 counter2, last counter1.
            slot(b,1,2)
            b[27*SECTOR:28*SECTOR] = sector(13,1)
        elif name in ("mixed_counter_tail0", "mixed_counter_tail3"):
            # Last physical sector alone changes counter; no checksum alteration.
            tail = 0 if name.endswith("tail0") else 3
            b[27*SECTOR:28*SECTOR] = sector(13,tail)
        if name.startswith("pallet_"):
            make_pallet_fixture(b, null_layout=(name=="pallet_null_layout"),
                                continue_warp=(name=="pallet_continue_warp"))
        p=root/(name+".sav");p.write_bytes(b)
        records.append({"name":name,"sha256":hashlib.sha256(b).hexdigest(),"size":len(b),"fixture_not_game_generated":True,
                        "authored_pallet_map": authored if name.startswith("pallet_") else None})
    original=Path(rom).read_bytes()
    assert len(original)>=0xC0 and original[0xAC:0xB0]==b"BPRE", "unexpected pinned FireRed game code"
    altered=bytearray(original)
    altered[0xAC:0xB0]=b"ZZZZ"
    altered[0xBD]=(-sum(altered[0xA0:0xBD])-0x19)&0xFF
    (root/"firered_header_changed.gba").write_bytes(altered)
    records.append({"name":"header_changed","sha256":hashlib.sha256(altered).hexdigest(),"size":len(altered),"original_game_code":"BPRE","altered_game_code":"ZZZZ","header_checksum_recalculated":True})
    (root/"fixture_manifest.json").write_text(json.dumps({"source_rom_sha256":hashlib.sha256(original).hexdigest(),"cases":records,"authored_pallet_source":authored,"phase1_gates":"FAIL_INCOMPLETE","independent_approvals":0},indent=2)+chr(10))
    print(json.dumps({"fixtures":len(records),"names":[x["name"] for x in records]}))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    p.add_argument("--rom",required=True)
    p.add_argument("--firered-source",required=True)
    a=p.parse_args()
    emit(Path(a.output),a.rom,a.firered_source)
