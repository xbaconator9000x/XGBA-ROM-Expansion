#!/usr/bin/env python3
"""Fail-closed pinned-source witness for FireRed's three distinct flash-sector formats.

Phase 1 source/format analysis only. This is NOT native compilation, an emulator
run, an approved file disposition, or an XGBA save implementation.
"""
import argparse
import hashlib
import json
from pathlib import Path

PIN_FIRERED = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PIN_MGBA = "fd9dc5c2cbf234365068855851107e762fc6211b"
BLOBS = {
    "fr:include/save.h": "87fb9b615b434b58823d15688056695acda9feab",
    "fr:src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
    "fr:src/cereader_tool.c": "395be0bcbed8454e645a9f5670cde3024eda508e",
    "fr:include/cereader_tool.h": "5cb5a9ebc32db23de07800ccce124bcb28d3ef15",
    "fr:src/hall_of_fame.c": "05c7d75384c2ad8481b6819f71faaf089f683bbf",
    "fr:include/constants/trainer_tower.h": "ea0039ea1408c06b8c968cfde8e2628213b2a0dc",
    "mg:src/gba/savedata.c": "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
    "mg:include/mgba/internal/gba/memory.h": "0aad912613e726560d06bbdbf6061986e69e5842",
}
# Each source anchor is an exact text witness, not a proof of runtime reachability.
ANCHORS = {
    "fr:include/save.h": [
        ("#define SECTOR_DATA_SIZE 3968", 1),
        ("#define SECTOR_FOOTER_SIZE 128", 1),
        ("#define NUM_SECTORS_PER_SLOT         14", 1),
        ("#define SECTOR_ID_HOF_1              28", 1),
        ("#define SECTOR_ID_HOF_2              29", 1),
        ("#define SECTOR_ID_TRAINER_TOWER_1    30", 1),
        ("#define SECTOR_ID_TRAINER_TOWER_2    31", 1),
        ("#define SPECIAL_SECTOR_SENTINEL 0xB39D", 1),
        ("u8 unused[SECTOR_FOOTER_SIZE - 12];", 1),
        ("#define SECTOR_COUNTER_OFFSET   offsetof(struct SaveSector, counter)", 1),
    ],
    "fr:src/save.c": [
        ("sector->id = CalculateChecksum(data, size);", 1),
        ("if (sector->id == checksum)", 1),
        ("sector->signature = SECTOR_SIGNATURE;", 1),
        ("HandleWriteSectorNBytes(SECTOR_ID_HOF_1, tempAddr, SECTOR_DATA_SIZE);", 1),
        ("HandleWriteSectorNBytes(SECTOR_ID_HOF_2, tempAddr + SECTOR_DATA_SIZE, SECTOR_DATA_SIZE);", 1),
        ("result = TryLoadSaveSector(SECTOR_ID_HOF_1, gDecompressionBuffer, SECTOR_DATA_SIZE);", 1),
        ("result = TryLoadSaveSector(SECTOR_ID_HOF_2, gDecompressionBuffer + SECTOR_DATA_SIZE, SECTOR_DATA_SIZE);", 1),
        ("if (*(u32 *)(&gSaveDataBuffer.data[0]) != SPECIAL_SECTOR_SENTINEL)", 1),
        ("*(u32 *)(savDataBuffer) = SPECIAL_SECTOR_SENTINEL;", 1),
        ("size = SECTOR_COUNTER_OFFSET - 1;", 2),
        ("savData = &gSaveDataBuffer.data[4];", 2),
        ("for (; i <= size; i++)", 2),
        ("ReadFlash(sectorId, 0, (u8 *)&gSaveDataBuffer, SECTOR_SIZE);", 1),
        ("if (ProgramFlashSectorAndVerify(sector, savDataBuffer) != 0)", 1),
    ],
    "fr:src/cereader_tool.c": [
        ("#define SEC30_SIZE  (offsetof(struct EReaderTrainerTowerSet, floors[4]))", 1),
        ("#define SEC31_SIZE  (sizeof(struct EReaderTrainerTowerSet) - SEC30_SIZE)", 1),
        ("STATIC_ASSERT(SEC30_SIZE + SEC31_SIZE <= SECTOR_COUNTER_OFFSET * 2", 1),
        ("if (TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer) != 1)", 1),
        ("if (TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer) != 1)", 1),
        ("if (TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer) != TRUE)", 1),
        ("if (TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer) != TRUE)", 1),
        ("if (!ValidateTrainerTowerData(ttdata))", 1),
        ("buffer = AllocZeroed(SECTOR_SIZE);", 2),
    ],
    "fr:include/cereader_tool.h": [
        ("struct TrainerTowerFloor", 1),
        ("/* 0x3DC */ u32 checksum;", 1),
        ("struct EReaderTrainerTowerSet", 2),
        ("struct TrainerTowerFloor floors[MAX_TRAINER_TOWER_FLOORS];", 1),
    ],
    "fr:src/hall_of_fame.c": [
        ("LoadGameSave(SAVE_HALL_OF_FAME)", 2),
        ("TrySavingData(SAVE_HALL_OF_FAME);", 1),
        ("SECTOR_SIZE * NUM_HOF_SECTORS", 5),
    ],
    "fr:include/constants/trainer_tower.h": [
        ("#define MAX_TRAINER_TOWER_FLOORS 8", 1),
        ("#define MAX_TRAINERS_PER_FLOOR  3", 1),
    ],
    "mg:src/gba/savedata.c": [
        ("case GBA_SAVEDATA_FLASH1M:", 1),
        ("return in->read(in, savedata->data, size) == size;", 1),
    ],
    "mg:include/mgba/internal/gba/memory.h": [
        ("GBA_SIZE_FLASH1M = 0x00020000,", 1),
    ],
}

def git_blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def verify_contracts(texts):
    evidence = []
    for key, checks in ANCHORS.items():
        for needle, expected in checks:
            count = texts[key].count(needle)
            if count != expected:
                raise ValueError(f"{key}: expected {expected} instances of {needle!r}, found {count}")
            evidence.append({"source": key, "line": texts[key][:texts[key].index(needle)].count("\n") + 1,
                             "text": needle, "count": count})
    # Footer arithmetic and the inclusive loop are independently evaluated.
    data, footer, unused, fields = 3968, 128, 116, (2, 2, 4, 4)
    assert unused + sum(fields) == footer
    assert data + footer == 4096
    counter_offset = data + unused + sum(fields[:-1])
    assert counter_offset == 4092
    # Pinned loops start at data[4] and iterate inclusively to counter_offset-1.
    special_copy_bytes = (counter_offset - 1) + 1
    assert special_copy_bytes == 4092
    assert 4 + special_copy_bytes == 4096  # includes all four counter bytes
    # Floor size is inferred from annotated 0x3DC checksum offset, not compiled.
    annotated_floor_size = 0x3DC + 4
    first_half = 8 + 4 * annotated_floor_size
    second_half = 4 * annotated_floor_size
    assert (first_half, second_half) == (3976, 3968)
    assert max(first_half, second_half) <= special_copy_bytes
    return evidence, {"sector_bytes": 4096, "standard_data_bytes": 3968,
                      "standard_footer_bytes": 128, "counter_offset": counter_offset,
                      "trainer_tower_sentinel_bytes": 4,
                      "trainer_tower_copy_bytes_per_sector": special_copy_bytes,
                      "trainer_tower_copy_includes_counter": True,
                      "trainer_tower_floor_size_from_source_annotations_only": annotated_floor_size,
                      "trainer_tower_half_sizes_from_annotations_only": [first_half, second_half],
                      "hall_of_fame_checksum_field": "sector.id",
                      "hall_of_fame_signature_field": "sector.signature",
                      "main_save_checksum_field": "sector.checksum",
                      "runtime_verified": False, "native_compiled": False}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firered", type=Path, required=True)
    ap.add_argument("--mgba", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    roots = {"fr": args.firered, "mg": args.mgba}
    texts = {}
    for key, sha in BLOBS.items():
        prefix, path = key.split(":", 1)
        raw = (roots[prefix] / path).read_bytes()
        actual = git_blob_sha(raw)
        if actual != sha:
            raise ValueError(f"{key}: pinned blob mismatch: {actual} != {sha}")
        texts[key] = raw.decode("utf-8")
    evidence, arithmetic = verify_contracts(texts)
    negative = 0
    for key, checks in ANCHORS.items():
        for needle, _ in checks:
            mutated = dict(texts)
            mutated[key] = texts[key].replace(needle, "MUTATED_ANCHOR", 1)
            try:
                verify_contracts(mutated)
            except ValueError:
                negative += 1
            else:
                raise AssertionError(f"negative mutation failed to trip: {key} {needle!r}")
    result = {"status": "PINNED_SOURCE_AND_ARITHMETIC_PASS",
              "pins": {"pret/pokefirered": PIN_FIRERED, "mgba-emu/mgba": PIN_MGBA},
              "verified_blobs": BLOBS, "anchors": evidence,
              "negative_mutation_controls_passed": negative,
              "arithmetic": arithmetic,
              "limitations": ["Source/annotation arithmetic only, no ARM binary or emulator execution.",
                              "No independent whole-file approval.",
                              "Does not establish malformed save runtime reachability."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PASS {len(BLOBS)} pinned blobs, {len(evidence)} source anchors, {negative} mutation controls")
    print(json.dumps(arithmetic, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
