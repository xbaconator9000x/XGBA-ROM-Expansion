#!/usr/bin/env python3
"""Exact-pinned FireRed Trainer Tower prefix-validation boundary.

Static source anchors and deterministic synthetic records only: NOT native runtime.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/cereader_tool.c": "395be0bcbed8454e645a9f5670cde3024eda508e",
    "src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
    "data/specials.inc": "d880bf6b9dc9fd765f0b85e6d698411e3da81d5d",
    "src/util.c": "b32799584937a120a03b08897886f08adc033fce",
    "src/ereader_screen.c": "20ec25d0150084bc259de47038ac7d8c972dd268",
    "include/gba/isagbprint.h": "9c79e03e8e95c02b17361073eff841bd59a8311c",
    "include/cereader_tool.h": "5cb5a9ebc32db23de07800ccce124bcb28d3ef15",
    "include/save.h": "87fb9b615b434b58823d15688056695acda9feab",
    "include/constants/trainer_tower.h": "ea0039ea1408c06b8c968cfde8e2628213b2a0dc",
}
FLOOR_SIZE = 992  # Prior ARMv4T Clang witness; not compiled by this checker.
SET_HEADER = 8
MAX_FLOORS = 8
ANCHORS = {
    "src/cereader_tool.c": [
        r"#define\s+SEC30_SIZE\s*\(offsetof\(struct EReaderTrainerTowerSet, floors\[4\]\)\)",
        r"#define\s+SEC31_SIZE\s*\(sizeof\(struct EReaderTrainerTowerSet\)\s*-\s*SEC30_SIZE\)",
        r"numFloors\s*=\s*ttdata->numFloors",
        r"numFloors\s*<\s*1\s*\|\|\s*numFloors\s*>\s*MAX_TRAINER_TOWER_FLOORS",
        r"for\s*\(i\s*=\s*0;\s*i\s*<\s*numFloors;\s*i\+\+\)",
        r"CalcByteArraySum\(\(const u8 \*\)ttdata->floors, numFloors \* sizeof\(ttdata->floors\[0\]\)\)\s*!=\s*ttdata->checksum",
        r"CalcByteArraySum\(\(const u8 \*\)floor, offsetof\(typeof\(\*floor\), checksum\)\)\s*!=\s*floor->checksum",
        r"TryReadSpecialSaveSector\(SECTOR_ID_TRAINER_TOWER_1, buffer\)\s*!=\s*1",
        r"TryReadSpecialSaveSector\(SECTOR_ID_TRAINER_TOWER_2, buffer\)\s*!=\s*1",
        r"memcpy\(ttdata \+ 0x000, buffer, SEC30_SIZE\)",
        r"memcpy\(\(u8 \*\)ttdata \+ SEC30_SIZE, buffer, SEC31_SIZE\)",
        r"if\s*\(!ValidateTrainerTowerData\(ttdata\)\)",
        r"memset\(buffer, 0, SECTOR_SIZE\)",
        r"memcpy\(buffer, ttdata, SEC30_SIZE\)",
        r"buffer\[1\] = GetTrainerHillUnkVal\(\)",
        r"AGB_ASSERT_EX\(ttdata->dummy == 0",
        r"AGB_ASSERT_EX\(ttdata->id == 0",
        r"memcpy\(buffer, \(u8 \*\)ttdata \+ SEC30_SIZE, SEC31_SIZE\)",
    ],
    "src/save.c": [
        r"sectorId != SECTOR_ID_TRAINER_TOWER_1 && sectorId != SECTOR_ID_TRAINER_TOWER_2",
        r"\*\(u32 \*\)\(&gSaveDataBuffer.data\[0\]\) != SPECIAL_SECTOR_SENTINEL",
        r"size\s*=\s*SECTOR_COUNTER_OFFSET\s*-\s*1",
        r"savData\s*=\s*&gSaveDataBuffer.data\[4\]",
        r"for\s*\(; i <= size; i\+\+\)",
        r"ProgramFlashSectorAndVerify\(sector, savDataBuffer\)",
        r"ReadFlash\(sectorId, 0, \(u8 \*\)&gSaveDataBuffer, SECTOR_SIZE\)",
        r"\*\(u32 \*\)\(savDataBuffer\) = SPECIAL_SECTOR_SENTINEL",
    ],
    "src/trainer_tower.c": [
        r"if\s*\(ReadTrainerTowerAndValidate\(\) == TRUE\)",
        r"CEReaderTool_LoadTrainerTower\(&sTrainerTowerState->data\)",
        r"floors_p\s*=\s*gTrainerTowerFloors\[challengeType\]",
        r"if\s*\(!ReadTrainerTowerAndValidate\(\)\)",
        r"TRAINER_TOWER\.validated\s*=\s*TRUE",
    ],
    "data/specials.inc": [
        r"def_special ReadTrainerTowerAndValidate",
    ],
    "src/ereader_screen.c": [
        r"data->status = ValidateTrainerTowerData\(\(struct EReaderTrainerTowerSet \*\)gDecompressionBuffer\)",
        r"CEReaderTool_SaveTrainerTower\(\(struct EReaderTrainerTowerSet \*\)gDecompressionBuffer\)",
    ],
    "include/gba/isagbprint.h": [
        r"#ifdef NDEBUG",
        r"#define AGB_ASSERT_EX\(exp, file, line\)",
        r"#define AGB_ASSERT_EX\(exp, file, line\) \(exp\)",
    ],
    "src/util.c": [
        r"u32 CalcByteArraySum\(const u8 \* array, u32 size\)",
        r"for\s*\(i = 0; i < size; i\+\+\)",
        r"result \+= array\[i\]",
    ],
    "include/cereader_tool.h": [
        r"struct EReaderTrainerTowerSet",
        r"struct TrainerTowerFloor floors\[MAX_TRAINER_TOWER_FLOORS\]",
        r"u32 checksum;",
    ],
    "include/save.h": [
        r"#define SECTOR_ID_TRAINER_TOWER_1\s+30",
        r"#define SECTOR_ID_TRAINER_TOWER_2\s+31",
        r"#define SPECIAL_SECTOR_SENTINEL\s+0xB39D",
        r"#define SECTOR_COUNTER_OFFSET\s+offsetof\(struct SaveSector, counter\)",
    ],
    "include/constants/trainer_tower.h": [
        r"#define MAX_TRAINER_TOWER_FLOORS\s+8",
        r"#define CHALLENGE_TYPE_KNOCKOUT\s+2",
    ],
}

def check_anchors(path, source):
    for n, pattern in enumerate(ANCHORS[path], 1):
        if not re.search(pattern, source, re.MULTILINE):
            raise ValueError(f"missing anchor {path} #{n}")

def verify_sources(root):
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise ValueError(f"upstream HEAD {head} differs from pin {PIN}")
    records = {}
    for name, expected in BLOBS.items():
        path = root / name
        actual = subprocess.check_output(["git", "-C", str(root), "hash-object", name], text=True).strip()
        if actual != expected:
            raise ValueError(f"source blob mismatch {name}: {actual} != {expected}")
        source = path.read_text()
        check_anchors(name, source)
        for pattern in ANCHORS[name]:
            changed = re.sub(pattern, "", source, flags=re.MULTILINE)
            try:
                check_anchors(name, changed)
            except ValueError:
                continue
            raise ValueError(f"negative mutation not detected: {name}: {pattern}")
        records[name] = {
            "git_blob": actual,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_anchors": len(ANCHORS[name]),
            "negative_mutations": len(ANCHORS[name]),
        }
    return records

def make_set(n):
    if not 1 <= n <= MAX_FLOORS:
        raise ValueError("invalid floor count")
    data = bytearray(SET_HEADER + MAX_FLOORS * FLOOR_SIZE)
    data[0] = n
    for i in range(MAX_FLOORS):
        pos = SET_HEADER + i * FLOOR_SIZE
        data[pos + 1] = i + 1
        data[pos + 2] = 0
        data[pos + FLOOR_SIZE - 4:pos + FLOOR_SIZE] = (
            sum(data[pos:pos + FLOOR_SIZE - 4]).to_bytes(4, "little")
        )
    data[4:8] = sum(data[SET_HEADER:SET_HEADER + n * FLOOR_SIZE]).to_bytes(4, "little")
    return data

def model_validate(data, first_sentinel=True, second_sentinel=True):
    # The model checks only the explicitly traced native predicates.
    if not first_sentinel or not second_sentinel or len(data) != SET_HEADER + MAX_FLOORS * FLOOR_SIZE:
        return False
    n = data[0]
    if not 1 <= n <= MAX_FLOORS:
        return False
    for i in range(n):
        pos = SET_HEADER + i * FLOOR_SIZE
        if not 1 <= data[pos + 1] <= MAX_FLOORS or data[pos + 2] > 2:
            return False
        checksum = int.from_bytes(data[pos + FLOOR_SIZE - 4:pos + FLOOR_SIZE], "little")
        if sum(data[pos:pos + FLOOR_SIZE - 4]) != checksum:
            return False
    return sum(data[SET_HEADER:SET_HEADER + n * FLOOR_SIZE]) == int.from_bytes(data[4:8], "little")

def synthetic_tests():
    result = {}
    for n in (1, 4, 5, 8):
        original = make_set(n)
        assert model_validate(original)
        active = bytearray(original)
        active[SET_HEADER + (n - 1) * FLOOR_SIZE + 100] ^= 0x40
        assert not model_validate(active)
        assert not model_validate(original, second_sentinel=False)
        record = {
            "checked_floor_bytes": n * FLOOR_SIZE,
            "unchecked_floor_bytes": (MAX_FLOORS - n) * FLOOR_SIZE,
            "active_floor_mutation_rejected": True,
            "missing_second_sentinel_rejected": True,
        }
        if n < MAX_FLOORS:
            unused = bytearray(original)
            unused[SET_HEADER + n * FLOOR_SIZE + 100] ^= 0x40
            assert model_validate(unused)
            record["unchecked_tail_mutation_accepted"] = True
        result[str(n)] = record
    assert SET_HEADER + 4 * FLOOR_SIZE == 3976 and 4 * FLOOR_SIZE == 3968
    assert result["4"]["unchecked_floor_bytes"] == 3968
    header = bytearray(make_set(4))
    header[1] ^= 0x80  # Native writer uses this byte as a generation value.
    header[2] ^= 0x40  # dummy is not checked by the load validator.
    assert model_validate(header)
    original = make_set(8)
    original[SET_HEADER + 100:SET_HEADER + 102] = bytes((2, 5))
    pos = SET_HEADER
    original[pos + FLOOR_SIZE - 4:pos + FLOOR_SIZE] = (
        sum(original[pos:pos + FLOOR_SIZE - 4]).to_bytes(4, "little")
    )
    original[4:8] = sum(original[SET_HEADER:]).to_bytes(4, "little")
    assert model_validate(original)
    swapped = bytearray(original)
    swapped[SET_HEADER + 100], swapped[SET_HEADER + 101] = (
        swapped[SET_HEADER + 101], swapped[SET_HEADER + 100]
    )
    assert model_validate(swapped)
    return {
        "floor_counts": result,
        "first_sector_struct_payload_bytes": 3976,
        "second_sector_struct_payload_bytes": 3968,
        "two_byte_swap_undetected_by_additive_checksums": True,
        "header_id_dummy_mutation_not_checked_by_model": True,
        "evidence_kind": "synthetic_model_not_emulator",
    }


def synthetic_torn_generation_cases():
    """Model valid-sentinel sectors from different save generations.

    Source-level predicates only; not evidence that flash actually tears.
    """
    split = SET_HEADER + 4 * FLOOR_SIZE
    assert split == 3976 and SET_HEADER + 8 * FLOOR_SIZE == 7944

    def generation(n, seed):
        data = make_set(n)
        for i in range(8):
            pos = SET_HEADER + i * FLOOR_SIZE
            data[pos + 100] = seed + i
            data[pos + FLOOR_SIZE - 4:pos + FLOOR_SIZE] = (
                sum(data[pos:pos + FLOOR_SIZE - 4]).to_bytes(4, "little")
            )
        data[4:8] = sum(data[SET_HEADER:SET_HEADER + n * FLOOR_SIZE]).to_bytes(4, "little")
        assert model_validate(data)
        return data

    results = {}
    for n in (1, 4, 5, 8):
        old, new = generation(n, 16), generation(n, 64)
        mixed = new[:split] + old[split:]
        accepted = model_validate(mixed)
        assert accepted == (n <= 4)
        assert not model_validate(mixed, first_sentinel=False)
        assert not model_validate(mixed, second_sentinel=False)
        results[str(n)] = {
            "first_sector_generation": "new",
            "second_sector_generation": "old",
            "both_sentinels_valid": True,
            "active_floor_bytes_in_second_sector": max(0, n - 4) * FLOOR_SIZE,
            "mixed_generation_accepted_by_modeled_predicates": accepted,
            "either_missing_sentinel_rejected": True,
        }
    return results


def synthetic_special_sector_wrapper():
    """Model special-sector copy bounds, NOT flash or emulator behavior.

    The native special-sector code starts at physical offset 4 and copies
    SECTOR_COUNTER_OFFSET bytes, including the four bytes ordinarily named
    SaveSector.counter. This is within the 4096-byte physical sector.
    """
    sector_size = 3968 + 128
    counter_offset = 3968 + (128 - 12) + 2 + 2 + 4
    sentinel = 0xB39D
    copy_size = counter_offset
    assert sector_size == 4096 and counter_offset == 4092
    assert 4 + copy_size == sector_size

    payload = bytearray((i * 17 + 3) % 256 for i in range(copy_size))
    physical = bytearray(sector_size)
    physical[:4] = sentinel.to_bytes(4, "little")
    physical[4:4 + copy_size] = payload
    assert physical[counter_offset:] == payload[-4:]
    assert physical[0:4] == b"\x9d\xb3\x00\x00"

    def read_if_sentinel(image):
        if int.from_bytes(image[:4], "little") != sentinel:
            return None
        return bytes(image[4:4 + copy_size])

    assert read_if_sentinel(physical) == bytes(payload)
    corrupted = bytearray(physical)
    corrupted[0] ^= 1
    assert read_if_sentinel(corrupted) is None
    # A mutation to the last four physical bytes does not affect the sentinel.
    # The special-sector reader returns the mutated bytes without validating them.
    corrupted = bytearray(physical)
    corrupted[-1] ^= 1
    assert read_if_sentinel(corrupted) is not None
    assert read_if_sentinel(corrupted)[-1] != payload[-1]
    return {
        "physical_sector_bytes": sector_size,
        "sentinel_bytes": 4,
        "copy_bytes": copy_size,
        "physical_copy_offsets_inclusive": [4, 4095],
        "includes_last_four_bytes_named_counter_in_save_sector_layout": True,
        "copy_out_of_bounds": False,
        "sentinel_mutation_rejected": True,
        "last_byte_mutation_not_authenticated_by_wrapper": True,
        "evidence_kind": "synthetic_wrapper_not_flash_or_emulator",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not args.source_dir and not args.self_test:
        parser.error("provide --source-dir and/or --self-test")
    report = {
        "pin": PIN,
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals_added": 0,
        "synthetic": synthetic_tests(),
        "torn_generation_cases": synthetic_torn_generation_cases(),
        "special_sector_wrapper": synthetic_special_sector_wrapper(),
    }
    if args.source_dir:
        report["pinned_sources"] = verify_sources(args.source_dir)
        report["source_level_reachability"] = {
            "fire_red_read_trainer_tower_and_validate_returns_false": True,
            "trainer_tower_gameplay_uses_local_floor_fallback": True,
            "gameplay_external_sector_load_branch_unreachable_under_pinned_source": True,
            "external_sector_writer_still_reachable_from_ereader_screen": True,
            "compiled_or_runtime_reachability_verified": False,
            "evidence_kind": "pinned_source_static_control_flow_not_emulator",
        }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()
