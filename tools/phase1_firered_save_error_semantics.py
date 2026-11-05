#!/usr/bin/env python3
"""Fail-closed pinned FireRed source/compiled-variant save-error dependency proof.

This is SOURCE verification, not emulator injection or a successful failed-save
runtime observation. No source, ROM, RAM or Flash mutation is performed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

PINNED = {
    "src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
    "include/save.h": "87fb9b615b434b58823d15688056695acda9feab",
    "Makefile": "8b454dbd18eb0069fa5851d788697190890a5b37",
    "config.mk": "c07d31fc083fa341cca29c340e560ed107d5364a",
    "src/fieldmap.c": "41567772299000ba5855419e5c39ad9373a34c20",
    "src/field_camera.c": "88f94bff08ef951523facf2b579fbc3d4d8455b2",
    "include/global.h": "77155b09014aa854fcf87260e6ad2969e222da53",
}


def git_blob(text):
    data = text.encode("utf-8")
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def function(src, name):
    pattern = r"\b(?:static\s+)?(?:u8|bool8|void)\s+" + re.escape(name) + r"\s*\([^;]*?\)\s*\{"
    match = re.search(pattern, src)
    assert match, ("missing pinned function definition", name)
    start = match.start()
    depth = 0
    for i in range(match.end() - 1, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(("unterminated function", name))


def contains_all(src, anchors, label):
    missing = [anchor for anchor in anchors if anchor not in src]
    assert not missing, (label, "source semantic anchor missing", missing)


def verify(text):
    save = text["src/save.c"]
    status = text["include/save.h"]
    config = text["config.mk"]
    make = text["Makefile"]
    funcs = {name: function(save, name) for name in (
        "TrySavingData", "TryWriteSector", "WriteSaveSectorOrSlot",
        "HandleSavingData", "GetSaveValidStatus", "CopySaveSlotData")}
    contains_all(funcs["TrySavingData"], [
        "if (gFlashMemoryPresent != TRUE)", "gSaveAttemptStatus = SAVE_STATUS_ERROR;",
        "HandleSavingData(saveType);", "if (!gDamagedSaveSectors)",
        "gSaveAttemptStatus = SAVE_STATUS_OK;", "DoSaveFailedScreen(saveType);",
        "return SAVE_STATUS_ERROR;", "return SAVE_STATUS_OK;"
    ], "TrySavingData")
    contains_all(funcs["TryWriteSector"], [
        "#if REVISION >= 0xA", "svc_WriteSector(sectorNum, data);",
        "ProgramFlashSectorAndVerify(sectorNum, data)",
        "SetDamagedSectorBits(ENABLE, sectorNum);",
        "SetDamagedSectorBits(DISABLE, sectorNum);"
    ], "TryWriteSector revision-dependent Flash verification")
    contains_all(funcs["WriteSaveSectorOrSlot"], [
        "gLastSaveCounter = gSaveCounter;", "gSaveCounter++;",
        "i < NUM_SECTORS_PER_SLOT", "gDamagedSaveSectors != 0",
        "gSaveCounter = gLastSaveCounter;"
    ], "full-slot failure rollback")
    contains_all(funcs["HandleSavingData"], [
        "case SAVE_NORMAL:", "SaveSerializedGame();",
        "WriteSaveSectorOrSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);"
    ], "SAVE_NORMAL transaction")
    contains_all(funcs["GetSaveValidStatus"], [
        "locations[gSaveDataBufferPtr->id].size",
        "validSectors |= 1 << gSaveDataBufferPtr->id"
    ], "unchecked sector-ID hazard")
    contains_all(funcs["CopySaveSlotData"], [
        "id = gSaveDataBufferPtr->id;",
        "locations[id].size", "locations[id].data[j]"
    ], "unchecked copy-ID hazard")
    contains_all(status, [
        "#define SAVE_STATUS_OK       1",
        "#define SAVE_STATUS_ERROR    0xFF",
        "#define NUM_SECTORS_PER_SLOT         14"
    ], "status ABI")
    contains_all(config, ["GAME_REVISION ?= 0", "MODERN        ?= 0"], "build defaults")
    contains_all(make, ["-DREVISION=$(GAME_REVISION)", "-D$(GAME_VERSION)"], "compiler flags")
    contains_all(text["src/fieldmap.c"], [
        "bool8 CameraMove(s32 x, s32 y)",
        "gSaveBlock1Ptr->pos.x += x;", "gSaveBlock1Ptr->pos.y += y;"
    ], "player position writer")
    contains_all(text["src/field_camera.c"], ["void CameraUpdate(void)", "CameraMove(deltaX, deltaY);"],
                 "camera movement caller")
    contains_all(text["include/global.h"], [
        "struct SaveBlock1", "/*0x0000*/ struct Coords16 pos;"
    ], "SaveBlock1 position ABI")
    return {k: len(v) for k, v in funcs.items()}


def main(a):
    root = Path(a.source)
    source = {}
    for path, expected in PINNED.items():
        content = (root / path).read_text()
        observed = git_blob(content)
        assert observed == expected, ("immutable source blob mismatch", path, observed, expected)
        source[path] = content
    sizes = verify(source)
    controls = [
        ("missing Flash guard", "src/save.c",
         "if (gFlashMemoryPresent != TRUE)", "if (FALSE)"),
        ("missing failure screen", "src/save.c",
         "DoSaveFailedScreen(saveType);", "/* removed */"),
        ("missing counter rollback", "src/save.c",
         "gSaveCounter = gLastSaveCounter;", "/* rollback removed */"),
        ("wrong compiled revision", "config.mk",
         "GAME_REVISION ?= 0", "GAME_REVISION ?= 10"),
        ("unchecked sector ID guard absent", "src/save.c",
         "locations[gSaveDataBufferPtr->id].size", "locations[0].size"),
    ]
    for label, path, old, new in controls:
        assert old in source[path], ("negative control anchor absent", label)
        mutated = dict(source)
        mutated[path] = source[path].replace(old, new)
        try:
            verify(mutated)
        except AssertionError:
            pass
        else:
            raise AssertionError(("negative control incorrectly accepted", label))
    output = {
        "source_repo": "pret/pokefirered",
        "source_commit": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
        "blob_sha1": PINNED,
        "function_lengths": sizes,
        "negative_controls_rejected": [c[0] for c in controls],
        "compiled_default_revision": 0,
        "source_proven_save_error_return": "SAVE_STATUS_ERROR=0xFF if no Flash or damaged sectors",
        "revision_10_branch": "svc_WriteSector; not covered by revision0 native CI",
        "unchecked_sector_ids": "source hazard; arbitrary malformed-ID safety NOT proven",
        "runtime_save_error_injection": "NOT TESTED",
        "hardware_power_loss_durability": "NOT TESTED",
        "independent_approval": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"source_paths": len(PINNED), "functions": len(sizes),
                      "negative_controls": len(controls),
                      "gate": "FAIL_INCOMPLETE"}, sort_keys=True))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--output", required=True)
    main(p.parse_args())
