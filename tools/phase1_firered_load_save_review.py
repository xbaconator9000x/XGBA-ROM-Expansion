#!/usr/bin/env python3
"""Fail-closed Phase 1 whole-file source identity/anchor review of FireRed load_save.c.
This is structural and dependency verification, NOT an independent approval.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/load_save.c": "8b723dd044c6024b3671bb890b25b56a53f99ec5",
    "src/item.c": "0587adf7db9feea06275fbe33dc1756adf23759a",
    "src/quest_log.c": "0a2f76f2c4019fa0938d5044da73fcea1b2b069c",
    "src/reset_save_heap.c": "745270dc7415b869c302daaa7b9c2b2e5b2865f1",
    "src/overworld.c": "339014da46ae8543143edc99ab72bf7496203a0d",
    "src/berry_powder.c": "d5090e0ddcd47f11afb018e047b23c97b5a89bd8",
    "include/malloc.h": "bf89badc53a4cad8ba5615900d5014cc34f76fea",
    "ld_script_modern.ld": "e930243522bd21da40cc1a05de9a42b8ad409b46",
    "include/load_save.h": "95de991a82204927d209a39e426f78633af0c04c",
}
FUNCTIONS = (
    "CheckForFlashMemory", "ClearSav2", "ClearSav1", "SetSaveBlocksPointers",
    "MoveSaveBlocks_ResetHeap", "UseContinueGameWarp", "ClearContinueGameWarpStatus",
    "SetContinueGameWarpStatus", "SetContinueGameWarpStatusToDynamicWarp",
    "ClearContinueGameWarpStatus2", "SavePlayerParty", "LoadPlayerParty",
    "SaveObjectEvents", "LoadObjectEvents", "SaveSerializedGame",
    "LoadSerializedGame", "LoadPlayerBag", "SavePlayerBag",
    "ApplyNewEncryptionKeyToHword", "ApplyNewEncryptionKeyToWord",
    "ApplyNewEncryptionKeyToAllEncryptedData",
)
ANCHORS = (
    "#define SAVEBLOCK_MOVE_RANGE    128",
    "sizeof(struct SaveBlock2) + sizeof(gSaveBlock2_DMA)",
    "sizeof(struct SaveBlock1) + sizeof(gSaveBlock1_DMA)",
    "offset = (Random()) & ((SAVEBLOCK_MOVE_RANGE - 1) & ~3);",
    "SetBagPocketsPointers();",
    "QL_AddASLROffset(oldSave);",
    "gMain.vblankCounter1 = NULL;",
    "InitHeap(gHeap, HEAP_SIZE);",
    "ApplyNewEncryptionKeyToAllEncryptedData(encryptionKey);",
    "gSaveBlock2Ptr->encryptionKey = gLastEncryptionKey;",
    "ApplyNewEncryptionKeyToBagItems(encryptionKeyBackup);",
    "#if REVISION >= 0xA",
    "svc_SetSaveBlock2(gSaveBlock2Ptr);",
)
DEPENDENCIES = {
    "src/item.c": ("void SetBagPocketsPointers(void)", "void ApplyNewEncryptionKeyToBagItems(u32 key)"),
    "src/quest_log.c": ("void QL_AddASLROffset(void *oldSaveBlockPtr)", "ptrdiff_t offset = (void *)gSaveBlock1Ptr - oldSaveBlockPtr;"),
    "src/reset_save_heap.c": ("void ReloadSave(void)", "SetSaveBlocksPointers();"),
    "src/overworld.c": ("void ApplyNewEncryptionKeyToGameStats(u32 newKey)",),
    "src/berry_powder.c": ("void ApplyNewEncryptionKeyToBerryPowder(u32 encryptionKey)",),
    "include/malloc.h": ("#define HEAP_SIZE 0x1C000",),
    "ld_script_modern.ld": ("gHeap = .;", ". = 0x1C000;"),
    "include/load_save.h": ("void ApplyNewEncryptionKeyToAllEncryptedData(u32 encryptionKey);",),
}

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args]).decode().strip()

def read_pinned(root):
    if git(root, "rev-parse", "HEAD") != PIN:
        raise ValueError("Wrong pinned FireRed commit")
    result = {}
    for path, expected in BLOBS.items():
        if git(root, "rev-parse", "HEAD:" + path) != expected:
            raise ValueError("Pinned tree identity drift: " + path)
        data = subprocess.check_output(["git", "-C", str(root), "cat-file", "blob", expected])
        if git_blob(data) != expected:
            raise ValueError("Pinned full-byte Git blob mismatch: " + path)
        result[path] = data.decode("utf-8")
    return result

def validate_structure(source):
    lines = source.splitlines()
    if len(lines) != 298:
        raise ValueError("Whole-file line inventory drift")
    includes = re.findall(r'(?m)^#include "[^"]+"$', source)
    if len(includes) != 13:
        raise ValueError("Include inventory drift")
    names = re.findall(r"(?m)^(?:void|u32|u16|u8|bool8|bool32|int)\s+(\w+)\([^;\n]*\)\s*\n\{", source)
    if tuple(names) != FUNCTIONS:
        raise ValueError("Whole-file function inventory drift: " + repr(names))
    if source.count("#if REVISION >= 0xA") != 1 or source.count("#endif") != 1:
        raise ValueError("Revision branch drift")
    for anchor in ANCHORS:
        if source.count(anchor) != 1:
            raise ValueError("Required source anchor missing or duplicated: " + anchor)
    return {"physical_lines": len(lines), "function_definitions": len(names), "direct_includes": len(includes)}

def validate_dependencies(sources):
    for path, anchors in DEPENDENCIES.items():
        for anchor in anchors:
            if sources[path].count(anchor) != 1:
                raise ValueError("Pinned dependency anchor drift: " + path + ": " + anchor)

    if sources['include/load_save.h'].count('void MoveSaveBlocks_ResetHeap(void);') != 2:
        raise ValueError('Pinned duplicate relocation prototype drift')

def negative_controls(sources):
    original = sources["src/load_save.c"]
    cases = (
        ("QL_AddASLROffset(oldSave);", "/* omitted relocation */"),
        ("SetBagPocketsPointers();", "/* omitted pocket rebinding */"),
        ("InitHeap(gHeap, HEAP_SIZE);", "/* omitted heap reset */"),
        ("#if REVISION >= 0xA", "#if REVISION >= 0xB"),
        ("gSaveBlock2Ptr->encryptionKey = gLastEncryptionKey;", "/* omitted staged key */"),
        ("offset = (Random()) & ((SAVEBLOCK_MOVE_RANGE - 1) & ~3);", "offset = Random();"),
    )
    count = 0
    for old, new in cases:
        if original.count(old) != 1:
            raise ValueError("Fixture anchor ambiguous")
        try:
            validate_structure(original.replace(old, new, 1))
        except ValueError:
            count += 1
        else:
            raise AssertionError("Accepted a mutated source anchor")
    tampered = original.encode() + b"\n"
    if git_blob(tampered) == BLOBS["src/load_save.c"]:
        raise AssertionError("Accepted tampered Git blob")
    count += 1
    changed = dict(sources)
    changed["src/quest_log.c"] = changed["src/quest_log.c"].replace(
        "ptrdiff_t offset = (void *)gSaveBlock1Ptr - oldSaveBlockPtr;",
        "ptrdiff_t offset = 0;", 1)
    try:
        validate_dependencies(changed)
    except ValueError:
        count += 1
    else:
        raise AssertionError("Accepted changed quest-log dependency")
    return count

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    sources = read_pinned(args.source_root)
    coverage = validate_structure(sources["src/load_save.c"])
    validate_dependencies(sources)
    controls = negative_controls(sources)
    result = {
        "phase": "Phase 1 source-only analyst review preparation",
        "pin": PIN,
        "file": "src/load_save.c",
        "git_blob_sha1": BLOBS["src/load_save.c"],
        "pinned_dependency_blobs": len(BLOBS) - 1,
        "negative_controls_passed": controls,
        "prepared_register_unchanged": True,
        "independently_approved": False,
        "gate": "FAIL_INCOMPLETE",
        **coverage,
    }
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
