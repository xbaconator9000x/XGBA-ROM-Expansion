#!/usr/bin/env python3
"""Phase 1 only: exact-pinned FireRed flash sector ID and map-view serialization contracts.

This is a source/arithmetical witness, NOT a malformed-flash emulator test or fix.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "include/save.h": "87fb9b615b434b58823d15688056695acda9feab",
    "include/global.h": "77155b09014aa854fcf87260e6ad2969e222da53",
    "include/config.h": "db131b2717ab739e62e41c5054a798f045c0631d",
    "src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
    "src/load_save.c": "8b723dd044c6024b3671bb890b25b56a53f99ec5",
    "src/fieldmap.c": "41567772299000ba5855419e5c39ad9373a34c20",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def body(source, signature):
    match = re.search(re.escape(signature) + r"\s*\{", source)
    require(match is not None, "missing function: " + signature)
    start = match.end()
    depth = 1
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i]
    raise ValueError("unclosed function: " + signature)


def ordered(source, tokens, label):
    pos = -1
    for token in tokens:
        next_pos = source.find(token, pos + 1)
        require(next_pos > pos, label + " missing/reordered " + token)
        pos = next_pos


def contract(f):
    header = f["include/save.h"]
    global_h = f["include/global.h"]
    save = f["src/save.c"]
    load = f["src/load_save.c"]
    field = f["src/fieldmap.c"]
    config = f["include/config.h"]

    for token in [
        "#define SECTOR_DATA_SIZE 3968",
        "#define SECTOR_ID_SAVEBLOCK2          0",
        "#define NUM_SECTORS_PER_SLOT         14",
        "#define FULL_SAVE_SLOT 0xFFFF",
        "u16 id;",
        "u16 checksum;",
        "u32 signature;",
        "u32 counter;",
    ]:
        require(token in header, "save sector header drift: " + token)
    for token in [
        "/*0x898*/ u16 mapView[0x100];",
        "/*0xA98*/ struct LinkBattleRecords linkBattleRecords;",
        "/*0xAF0*/ struct BerryCrush berryCrush;",
        "/*0xB00*/ struct PokemonJumpRecords pokeJump;",
        "/*0xB10*/ struct BerryPickingResults berryPick;",
        "/*0xB20*/ u8 filler_B20[0x400];",
        "}; // size: 0xF24",
    ]:
        require(token in global_h, "SaveBlock2 layout drift: " + token)
    require("SAVEBLOCK_CHUNK(struct SaveBlock2, 0), // SECTOR_ID_SAVEBLOCK2" in save,
            "save slot no longer starts with SaveBlock2")
    require("STATIC_ASSERT(sizeof(struct SaveBlock2) <= SECTOR_DATA_SIZE, SaveBlock2FreeSpace);" in save,
            "SaveBlock2 sector bound not asserted")
    addr = body(save, "static void UpdateSaveAddresses(void)")
    ordered(addr, [
        "gRamSaveSectorLocations[i].data = (void *)(gSaveBlock2Ptr) + sSaveSlotLayout[i].offset;",
        "gRamSaveSectorLocations[i].size = sSaveSlotLayout[i].size;",
    ], "sector source pointer")
    require("gRamSaveSectorLocations[NUM_SECTORS_PER_SLOT]" in save,
            "sector location array extent drift")
    require("gSaveBlock2Ptr = (void *)(&gSaveBlock2) + offset;" in load,
            "randomized save pointer rebinding drift")
    require("offset = (Random()) & ((SAVEBLOCK_MOVE_RANGE - 1) & ~3);" in load,
            "save pointer offset alignment drift")

    write = body(save, "u8 HandleSavingData(u8 saveType)")
    require("case SAVE_NORMAL:" in write and "case SAVE_LINK:" in write,
            "normal save case boundaries missing")
    normal = write.split("case SAVE_NORMAL:", 1)[1].split("case SAVE_LINK:", 1)[0]
    ordered(normal, [
        "SaveSerializedGame();",
        "WriteSaveSectorOrSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);",
        "break;",
    ], "normal save producer")
    read = body(save, "u8 LoadGameSave(u8 saveType)")
    ordered(read, [
        "case SAVE_NORMAL:",
        "result = TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);",
        "LoadSerializedGame();",
    ], "normal save consumer")

    slot = body(save, "static u8 TryLoadSaveSlot(u16 sectorId, const struct SaveSectorLocation *locations)")
    ordered(slot, [
        "status = GetSaveValidStatus(locations);",
        "CopySaveSlotData(FULL_SAVE_SLOT, locations);",
    ], "slot validation and copying")
    require("if (status == SAVE_STATUS_OK)" not in slot,
            "slot copying newly gated on validation status")

    validity = body(save, "static u8 GetSaveValidStatus(const struct SaveSectorLocation *locations)")
    require(validity.count("locations[gSaveDataBufferPtr->id].size") == 2,
            "two save-slot checksum size lookups changed")
    require(validity.count("validSectors |= 1 << gSaveDataBufferPtr->id;") == 2,
            "two save-slot bitmask shifts changed")
    require(validity.count("if (gSaveDataBufferPtr->signature == SECTOR_SIGNATURE)") == 2,
            "save-slot signature guards changed")
    require("gSaveDataBufferPtr->id < NUM_SECTORS_PER_SLOT" not in validity
            and "gSaveDataBufferPtr->id >= NUM_SECTORS_PER_SLOT" not in validity,
            "save-slot ID guard changed: reassess classification")
    copy = body(save, "static u8 CopySaveSlotData(u16 sectorId, const struct SaveSectorLocation *locations)")
    ordered(copy, [
        "id = gSaveDataBufferPtr->id;",
        "checksum = CalculateChecksum(gSaveDataBufferPtr->data, locations[id].size);",
        "if (gSaveDataBufferPtr->signature == SECTOR_SIGNATURE && gSaveDataBufferPtr->checksum == checksum)",
        "locations[id].data[j] = gSaveDataBufferPtr->data[j];",
    ], "raw sector copy")
    require("id >= NUM_SECTORS_PER_SLOT" not in copy
            and "id < NUM_SECTORS_PER_SLOT" not in copy,
            "copy ID guard changed: reassess classification")

    scan = body(field, "static bool32 SavedMapViewIsEmpty(void)")
    ordered(scan, [
        "#ifndef UBFIX",
        "for (i = 0; i < 0x200; i++)",
        "#else",
        "for (i = 0; i < NELEMS(gSaveBlock2Ptr->mapView); i++)",
        "#endif",
    ], "saved map-view variant")
    require("#if MODERN" in config and "#define UBFIX" in config,
            "modern variant UBFIX policy drift")
    require("LoadSavedMapView();" in body(field, "void InitMapFromSavedGame(void)"),
            "save map view no longer consumed on continue")
    # All offsets are relative to the *relocated* SaveBlock2 pointer, not absolute EWRAM.
    start, length, structure, sector_size, legacy_words = 0x898, 0x100 * 2, 0xF24, 3968, 0x200
    require(start + length == 0xA98 and start + legacy_words * 2 == 0xC98,
            "arithmetic witness mismatch")
    require(0xC98 <= structure <= sector_size, "legacy scan no longer within SaveBlock2 sector")
    return {
        "source_pin": PIN,
        "source_blobs": BLOBS,
        "sector_location_entries": 14,
        "raw_sector_id_bits": 16,
        "sector_payload_bytes": sector_size,
        "saveblock2_bytes": structure,
        "mapview_offset": start,
        "mapview_bytes": length,
        "mapview_end_exclusive": 0xA98,
        "legacy_scan_end_exclusive": 0xC98,
        "legacy_scan_extra_bytes": 512,
        "normal_save_sector_contains_mapview": True,
        "normal_load_restores_saveblock2_before_mapview_reader": True,
        "signature_guard_precedes_id_lookup_in_validation": True,
        "copy_id_lookup_precedes_signature_and_checksum_validation": True,
        "id_range_checked_before_location_lookup": False,
        "compiled_or_runtime_malformed_sector_executed": False,
        "independent_review_approved": False,
    }


def mutation_tests(f):
    cases = [
        ("include/save.h", "#define NUM_SECTORS_PER_SLOT         14", "#define NUM_SECTORS_PER_SLOT         32"),
        ("include/save.h", "u16 id;", "u8 id;"),
        ("include/save.h", "#define SECTOR_DATA_SIZE 3968", "#define SECTOR_DATA_SIZE 2048"),
        ("include/global.h", "/*0x898*/ u16 mapView[0x100];", "/*0x898*/ u16 mapView[0x200];"),
        ("src/save.c", "SAVEBLOCK_CHUNK(struct SaveBlock2, 0)", "SAVEBLOCK_CHUNK(struct SaveBlock1, 0)"),
        ("src/save.c", "locations[gSaveDataBufferPtr->id].size", "locations[gSaveDataBufferPtr->id % NUM_SECTORS_PER_SLOT].size"),
        ("src/save.c", "validSectors |= 1 << gSaveDataBufferPtr->id;", "validSectors |= 1 << 0;"),
        ("src/save.c", "id = gSaveDataBufferPtr->id;", "id = gSaveDataBufferPtr->id % NUM_SECTORS_PER_SLOT;"),
        ("src/save.c", "id = gSaveDataBufferPtr->id;", "id = gSaveDataBufferPtr->id;\n        if (id >= NUM_SECTORS_PER_SLOT) continue;"),
        ("src/save.c", "status = GetSaveValidStatus(locations);", "status = SAVE_STATUS_OK;"),
        ("src/save.c", "CopySaveSlotData(FULL_SAVE_SLOT, locations);", "CopySaveSlotData(SECTOR_ID_SAVEBLOCK2, locations);"),
        ("src/save.c", "WriteSaveSectorOrSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);", "WriteSaveSectorOrSlot(SECTOR_ID_SAVEBLOCK2, gRamSaveSectorLocations);"),
        ("src/load_save.c", "gSaveBlock2Ptr = (void *)(&gSaveBlock2) + offset;", "gSaveBlock2Ptr = &gSaveBlock2;"),
        ("src/fieldmap.c", "for (i = 0; i < 0x200; i++)", "for (i = 0; i < 0x100; i++)"),
        ("src/fieldmap.c", "LoadSavedMapView();", "ClearSavedMapView();"),
        ("include/config.h", "#define UBFIX", "#define NO_UBFIX"),
    ]
    for path, old, new in cases:
        require(old in f[path], "mutation source missing: " + path + ": " + old)
        changed = dict(f)
        changed[path] = changed[path].replace(old, new, 1)
        try:
            contract(changed)
        except ValueError:
            continue
        raise ValueError("mutation escaped contract: " + path + ": " + old)
    return len(cases)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root = args.source.resolve()
    def git(*parts):
        return subprocess.check_output(["git", "-C", str(root), *parts], text=True).strip()
    require(git("rev-parse", "HEAD") == PIN, "wrong FireRed source revision")
    f = {}
    for path, blob in BLOBS.items():
        require(git("hash-object", path) == blob, "blob drift: " + path)
        f[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(f)
    facts["negative_mutation_controls"] = mutation_tests(f)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print("Pinned FireRed save-sector/map-view boundary PASS; mutations:",
          facts["negative_mutation_controls"])


if __name__ == "__main__":
    main()
