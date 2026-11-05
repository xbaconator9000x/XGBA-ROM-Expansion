#!/usr/bin/env python3
"""Phase 1 only: immutable FireRed early-boot save-pointer order, with mutations."""
import argparse
import hashlib
import json
import re
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/main.c": "542b0f5d16dd93107523d11163bfcb70a42b707a",
    "src/intro.c": "bec0f3144ece4167b27dd2eccc0fd12546bf95c4",
    "src/title_screen.c": "75f0e6743a2a84c906090df230bac7accb8dbe84",
    "src/load_save.c": "8b723dd044c6024b3671bb890b25b56a53f99ec5",
    "src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
}

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def function(source, name):
    pat = r"(?m)^[^\n;{}]*\b" + re.escape(name) + r"\s*\([^;{}]*\)\s*\{"
    match = re.search(pat, source)
    require(match is not None, "missing function body: " + name)
    start = source.index("{", match.start())
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():i+1]
    raise AssertionError("unterminated function body: " + name)

def check(bodies):
    main = bodies["main"]
    intro = bodies["intro"]
    title = bodies["title"]
    pointers = bodies["pointers"]
    addresses = bodies["addresses"]
    copy = bodies["copy"]
    require("gSaveBlock2Ptr = &gSaveBlock2;" in main and
            "gSaveBlock1Ptr = &gSaveBlock1;" in main,
            "initial main SaveBlock1/2 pointers missing")
    require("gPokemonStoragePtr" not in main,
            "early main initialization unexpectedly sets storage pointer")
    require("LoadGameSave(SAVE_NORMAL);" in intro and
            "SetSaveBlocksPointers();" not in intro,
            "copyright loader must precede pointer relocation")
    require("SetSaveBlocksPointers();" in title and
            "LoadGameSave(SAVE_NORMAL);" in title and
            title.index("SetSaveBlocksPointers();") < title.index("LoadGameSave(SAVE_NORMAL);"),
            "title loader does not follow pointer relocation")
    require("gSaveBlock2Ptr = (void *)(&gSaveBlock2) + offset;" in pointers and
            "*sav1_LocalVar = (void *)(&gSaveBlock1) + offset;" in pointers and
            "gPokemonStoragePtr = (void *)(&gPokemonStorage) + offset;" in pointers,
            "three relocated pointers do not share source offset")
    require("gRamSaveSectorLocations[i].data = (void *)(gPokemonStoragePtr) +" in addresses,
            "storage-sector destination no longer uses storage pointer")
    require("locations[id].data[j] = gSaveDataBufferPtr->data[j];" in copy,
            "native copy destination semantics changed")
    return True

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    src = {}
    for path, expected in BLOBS.items():
        raw = (a.source / path).read_bytes()
        require(blob(raw) == expected, "source blob mismatch: " + path)
        src[path] = raw.decode("utf-8")
    bodies = {
        "main": function(src["src/main.c"], "InitMainCallbacks"),
        "intro": function(src["src/intro.c"], "CB2_InitCopyrightScreenAfterBootup"),
        "title": function(src["src/title_screen.c"], "SetTitleScreenScene_Cry"),
        "pointers": function(src["src/load_save.c"], "SetSaveBlocksPointers"),
        "addresses": function(src["src/save.c"], "UpdateSaveAddresses"),
        "copy": function(src["src/save.c"], "CopySaveSlotData"),
    }
    check(bodies)
    mutants = []
    def mutate(name, key, old, new):
        altered = dict(bodies)
        require(old in altered[key], "mutation anchor missing: " + name)
        altered[key] = altered[key].replace(old, new, 1)
        try:
            check(altered)
        except AssertionError:
            mutants.append(name)
        else:
            raise AssertionError("semantic mutation escaped: " + name)
    mutate("early_storage_pointer", "main", "gSaveBlock1Ptr = &gSaveBlock1;",
           "gSaveBlock1Ptr = &gSaveBlock1; gPokemonStoragePtr = &gPokemonStorage;")
    mutate("copyright_relocation", "intro", "LoadGameSave(SAVE_NORMAL);",
           "SetSaveBlocksPointers(); LoadGameSave(SAVE_NORMAL);")
    mutate("missing_title_relocation", "title", "SetSaveBlocksPointers();", "")
    altered = dict(bodies)
    t = altered["title"]
    t = t.replace("SetSaveBlocksPointers();", "PHASE1_TITLE_A;", 1)
    t = t.replace("LoadGameSave(SAVE_NORMAL);", "SetSaveBlocksPointers();", 1)
    t = t.replace("PHASE1_TITLE_A;", "LoadGameSave(SAVE_NORMAL);", 1)
    altered["title"] = t
    try:
        check(altered)
    except AssertionError:
        mutants.append("reversed_title_order")
    else:
        raise AssertionError("reversed title order escaped")
    mutate("missing_storage_assignment", "pointers",
           "gPokemonStoragePtr = (void *)(&gPokemonStorage) + offset;", "")
    mutate("wrong_storage_sector_destination", "addresses",
           "(void *)(gPokemonStoragePtr)", "(void *)(gSaveBlock1Ptr)")
    mutate("wrong_copy_destination", "copy",
           "locations[id].data[j] = gSaveDataBufferPtr->data[j];",
           "gSaveDataBufferPtr->data[j] = locations[id].data[j];")
    report = {
        "status": "PINNED_EARLY_BOOT_STORAGE_ORDER_VERIFIED",
        "source_revision": PIN,
        "source_blobs": BLOBS,
        "function_bodies": list(bodies),
        "negative_controls_rejected": mutants,
        "first_boot_storage_ptr_precondition": "NULL is possible before title SetSaveBlocksPointers",
        "second_title_load_precondition": "SetSaveBlocksPointers before LoadGameSave",
        "limitations": [
            "Source contract only; native pointer values require exact-head emulator evidence",
            "No semantic approvals or hardware durability claim",
        ],
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "negative_controls_rejected": len(mutants)}, sort_keys=True))

if __name__ == "__main__":
    main()
