#!/usr/bin/env python3
"""Pinned FireRed map-view save boundary witness; not a runtime or review signoff."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/fieldmap.c": "41567772299000ba5855419e5c39ad9373a34c20",
    "include/global.h": "77155b09014aa854fcf87260e6ad2969e222da53",
    "include/fieldmap.h": "639e329a9a0f721abd7e40001228859cb9466005",
    "include/config.h": "db131b2717ab739e62e41c5054a798f045c0631d",
    "Makefile": "8b454dbd18eb0069fa5851d788697190890a5b37",
}
MAP_VIEW_WORDS = 0x100
RETAIL_SCAN_WORDS = 0x200
MAP_OFFSET_W = 15
MAP_OFFSET_H = 14


def require(text: str, fragment: str, description: str) -> None:
    if fragment not in text:
        raise AssertionError("Pinned source contract changed: " + description)


def model_is_empty(map_words: list[int], adjacent_words: list[int], scan: int) -> bool:
    """Synthetic C-like halfword scan, not a ROM/emulator execution."""
    assert len(map_words) == MAP_VIEW_WORDS
    assert len(adjacent_words) >= RETAIL_SCAN_WORDS - MAP_VIEW_WORDS
    return not any((map_words + adjacent_words)[:scan])


def self_test() -> None:
    empty = [0] * MAP_VIEW_WORDS
    adjacent = [0] * MAP_VIEW_WORDS
    adjacent[0] = 1
    assert model_is_empty(empty, adjacent, MAP_VIEW_WORDS)
    assert not model_is_empty(empty, adjacent, RETAIL_SCAN_WORDS)
    adjacent[0] = 0
    assert model_is_empty(empty, adjacent, RETAIL_SCAN_WORDS)
    assert MAP_OFFSET_W * MAP_OFFSET_H == 210
    assert MAP_VIEW_WORDS - 210 == 46
    assert 0x898 + MAP_VIEW_WORDS * 2 == 0xA98
    assert 0x898 + RETAIL_SCAN_WORDS * 2 == 0xC98
    try:
        require("no matching declaration", "mapView[0x100]", "negative mutation control")
    except AssertionError:
        pass
    else:
        raise AssertionError("Missing source anchor was not rejected")


def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def inspect(root: pathlib.Path) -> dict:
    assert git(root, "rev-parse", "HEAD") == PIN, "FireRed checkout is not exact pinned commit"
    sources = {}
    for path, blob in BLOBS.items():
        assert git(root, "hash-object", path) == blob, "Blob identity mismatch: " + path
        sources[path] = (root / path).read_text()
    field = sources["src/fieldmap.c"]
    global_h = sources["include/global.h"]
    field_h = sources["include/fieldmap.h"]
    config_h = sources["include/config.h"]
    makefile = sources["Makefile"]
    require(global_h, '#include "config.h"', "global header includes build configuration")
    for frag in ["#if MODERN", "#ifndef UBFIX", "#define UBFIX"]:
        require(config_h, frag, "modern build forces UBFIX")
    require(makefile, "-DMODERN=$(MODERN)", "build mode passed to preprocessor")
    for frag, label in [
        ("u16 mapView[0x100];", "SaveBlock2 map-view array length"),
        ("/*0x898*/", "SaveBlock2 map-view start offset"),
        ("/*0xA98*/ struct LinkBattleRecords linkBattleRecords;", "next saved field"),
        ("/*0xAF0*/ struct BerryCrush berryCrush;", "subsequent saved field"),
        ("/*0xB00*/ struct PokemonJumpRecords pokeJump;", "subsequent saved field"),
        ("/*0xB10*/ struct BerryPickingResults berryPick;", "subsequent saved field"),
        ("/*0xB20*/ u8 filler_B20[0x400];", "following padding"),
    ]:
        require(global_h, frag, label)
    for frag, label in [
        ("#define MAP_OFFSET_W (MAP_OFFSET * 2 + 1)", "map-view width"),
        ("#define MAP_OFFSET_H (MAP_OFFSET * 2)", "map-view height"),
        ("#define MAP_OFFSET 7", "map-view border offset"),
    ]:
        require(field_h, frag, label)
    save = field.split("void SaveMapView(void)", 1)[1].split("static bool32 SavedMapViewIsEmpty(void)", 1)[0]
    scan = field.split("static bool32 SavedMapViewIsEmpty(void)", 1)[1].split("static void ClearSavedMapView(void)", 1)[0]
    load = field.split("static void LoadSavedMapView(void)\n{", 1)[1].split("static void MoveMapViewToBackup", 1)[0]
    for frag in [
        "mapView = gSaveBlock2Ptr->mapView;",
        "for (i = y; i < y + MAP_OFFSET_H; i++)",
        "for (j = x; j < x + MAP_OFFSET_W; j++)",
        "*mapView++ = gBackupMapData[width * i + j];",
    ]:
        require(save, frag, "SaveMapView producer")
    for frag in [
        "#ifndef UBFIX",
        "for (i = 0; i < 0x200; i++)",
        "#else",
        "for (i = 0; i < NELEMS(gSaveBlock2Ptr->mapView); i++)",
        "marker |= gSaveBlock2Ptr->mapView[i];",
    ]:
        require(scan, frag, "build-conditional emptiness scan")
    for frag in [
        "if (!SavedMapViewIsEmpty())",
        "gBackupMapData[j + width * i] = *mapView;",
        "ClearSavedMapView();",
    ]:
        require(load, frag, "LoadSavedMapView consumer")
    return {
        "pin": PIN, "blobs": BLOBS,
        "saved_array_halfwords": MAP_VIEW_WORDS,
        "producer_window_halfwords": MAP_OFFSET_W * MAP_OFFSET_H,
        "unused_array_tail_halfwords": MAP_VIEW_WORDS - MAP_OFFSET_W * MAP_OFFSET_H,
        "retail_scan_halfwords_without_UBFIX": RETAIL_SCAN_WORDS,
        "extra_halfwords_read_outside_array": RETAIL_SCAN_WORDS - MAP_VIEW_WORDS,
        "mapView_start_offset": "0x898", "mapView_end_exclusive": "0xA98",
        "retail_scan_end_exclusive": "0xC98",
        "model": "synthetic adjacent nonzero field makes retail scan nonempty while UBFIX scan remains empty",
        "build_condition": "MODERN=1 forces UBFIX via include/config.h; MODERN=0 has no such automatic definition",
        "compiled_or_runtime_test": False,
        "independent_approval": False,
        "phase1": "FAIL_INCOMPLETE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("upstream/pokefirered"))
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("audit-output/fieldmap_save_boundary.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        print("Synthetic model and fail-closed mutation control passed")
        return
    report = inspect(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
