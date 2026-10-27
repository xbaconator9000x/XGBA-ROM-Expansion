#!/usr/bin/env python3
"""Pinned FireRed slot counter/physical-slot coherence witness (Phase 1 only).

Models two *synthetic* checksum-valid slot arrangements. It does not execute
the game, load malformed flash in an emulator, or approve source dispositions.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOB_SAVE = "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c"
BLOB_HEADER = "87fb9b615b434b58823d15688056695acda9feab"

def body(src, signature):
    m = re.search(re.escape(signature) + r"\s*\{", src)
    if not m:
        raise ValueError("missing source function: " + signature)
    depth = 1
    for i in range(m.end(), len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[m.end():i]
    raise ValueError("unclosed source function: " + signature)

def contract(save, header):
    if "#define NUM_SECTORS_PER_SLOT         14" not in header or "#define NUM_SAVE_SLOTS 2" not in header:
        raise ValueError("slot constants changed")
    validator = body(save, "static u8 GetSaveValidStatus(const struct SaveSectorLocation *locations)")
    copy = body(save, "static u8 CopySaveSlotData(u16 sectorId, const struct SaveSectorLocation *locations)")
    load = body(save, "static u8 TryLoadSaveSlot(u16 sectorId, const struct SaveSectorLocation *locations)")
    writer = body(save, "static u8 WriteSaveSectorOrSlot(u16 sectorId, const struct SaveSectorLocation *locations)")
    checks = [
        (validator, "slot1saveCounter = gSaveDataBufferPtr->counter;", 1),
        (validator, "slot2saveCounter = gSaveDataBufferPtr->counter;", 1),
        (validator, "validSectors |= 1 << gSaveDataBufferPtr->id;", 2),
        (validator, "if (validSectors == ALL_SECTORS)", 2),
        (validator, "gSaveCounter = slot1saveCounter;", 3),
        (validator, "gSaveCounter = slot2saveCounter;", 3),
        (copy, "u16 sector = NUM_SECTORS_PER_SLOT * (gSaveCounter % NUM_SAVE_SLOTS);", 1),
        (copy, "ReadFlashSector(i + sector, gSaveDataBufferPtr);", 1),
        (load, "status = GetSaveValidStatus(locations);", 1),
        (load, "CopySaveSlotData(FULL_SAVE_SLOT, locations);", 1),
        (writer, "gSaveCounter++;", 1),
        (writer, "sectorNum += NUM_SECTORS_PER_SLOT * (gSaveCounter % NUM_SAVE_SLOTS);", 0),
    ]
    # The write-side slot selector is in HandleWriteSector, called from writer.
    write_sector = body(save, "static u8 HandleWriteSector(u16 sectorId, const struct SaveSectorLocation *locations)")
    checks.append((write_sector, "sectorNum += NUM_SECTORS_PER_SLOT * (gSaveCounter % NUM_SAVE_SLOTS);", 1))
    for text, needle, count in checks:
        if text.count(needle) != count:
            raise ValueError(f"source anchor drift: {needle!r}: {text.count(needle)} != {count}")
    # No per-sector counter equality or parity validation is present in this
    # exact pinned function. If code changes, reassess rather than assuming.
    if re.search(r"gSaveDataBufferPtr->counter\s*(!=|==)\s*(slot1saveCounter|slot2saveCounter|gSaveCounter)", validator):
        raise ValueError("new counter comparison requires semantic reassessment")
    if re.search(r"gSaveDataBufferPtr->counter\s*%\s*NUM_SAVE_SLOTS", validator):
        raise ValueError("new parity check requires semantic reassessment")
    return len(checks)

def synthetic_slot(counters):
    # Precondition: exactly one valid, checksum-correct instance of each ID
    # 0..13 in physical slot 0, and physical slot 1 is empty.
    if len(counters) != 14:
        raise ValueError("fixture must have 14 sectors")
    valid_ids = set(range(len(counters)))
    valid_mask = sum(1 << sector_id for sector_id in valid_ids)
    status_ok = valid_mask == ((1 << 14) - 1)
    chosen_counter = counters[-1]  # validator overwrites on each valid sector
    physical_slot_copied = chosen_counter % 2  # CopySaveSlotData
    return {"validator_status_ok": status_ok,
            "selected_counter": chosen_counter,
            "physical_slot_with_valid_sectors": 0,
            "physical_slot_read_by_copy": physical_slot_copied,
            "counter_values": sorted(set(counters)),
            "mixed_generation": len(set(counters)) > 1,
            "selected_slot_mismatch": physical_slot_copied != 0}

def sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raw_save = (args.source / "src/save.c").read_bytes()
    raw_header = (args.source / "include/save.h").read_bytes()
    if sha(raw_save) != BLOB_SAVE or sha(raw_header) != BLOB_HEADER:
        raise ValueError("pinned save source blob identity mismatch")
    save, header = raw_save.decode(), raw_header.decode()
    anchors = contract(save, header)
    negative = 0
    mutations = [
        ("slot1saveCounter = gSaveDataBufferPtr->counter;", "slot1saveCounter = 0;"),
        ("slot2saveCounter = gSaveDataBufferPtr->counter;", "slot2saveCounter = 0;"),
        ("validSectors |= 1 << gSaveDataBufferPtr->id;", "validSectors |= 0;"),
        ("if (validSectors == ALL_SECTORS)", "if (validSectors == 0)"),
        ("u16 sector = NUM_SECTORS_PER_SLOT * (gSaveCounter % NUM_SAVE_SLOTS);", "u16 sector = 0;"),
        ("CopySaveSlotData(FULL_SAVE_SLOT, locations);", "CopySaveSlotData(0, locations);"),
        ("gSaveCounter++;", "gSaveCounter += 2;"),
        ("sectorNum += NUM_SECTORS_PER_SLOT * (gSaveCounter % NUM_SAVE_SLOTS);", "sectorNum += 0;"),
    ]
    for needle, replacement in mutations:
        if needle not in save:
            raise ValueError("mutation anchor missing: " + needle)
        altered = save.replace(needle, replacement, 1)
        try:
            contract(altered, header)
        except ValueError:
            negative += 1
        else:
            raise AssertionError("mutation escaped checker: " + needle)
    even = synthetic_slot([100] * 13 + [102])
    odd = synthetic_slot([100] * 13 + [101])
    assert even["validator_status_ok"] and even["mixed_generation"] and not even["selected_slot_mismatch"]
    assert odd["validator_status_ok"] and odd["mixed_generation"] and odd["selected_slot_mismatch"]
    out = {"status": "PINNED_SOURCE_AND_SYNTHETIC_MODEL_PASS",
           "source_pin": PIN, "source_blobs": {"src/save.c": BLOB_SAVE, "include/save.h": BLOB_HEADER},
           "source_anchor_checks": anchors, "negative_mutations_passed": negative,
           "synthetic_same_parity_mixed_generation": even,
           "synthetic_wrong_parity_slot_selection": odd,
           "limitations": ["Both fixtures assume valid signatures/checksums and one ID 0..13 per physical slot 0.",
                           "Neither fixture was executed in native FireRed or mGBA.",
                           "No claim that normal saves produce mixed generations.",
                           "Independent approvals remain zero."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("PASS", anchors, "source checks,", negative, "mutation controls, 2 synthetic slot fixtures")

if __name__ == "__main__":
    main()
