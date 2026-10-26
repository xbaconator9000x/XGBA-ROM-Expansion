#!/usr/bin/env python3
"""Pinned FireRed ReloadSave RAM/save/continuation source contract; Phase 1 only.

Source checks do not certify compiled layout, runtime reachability, or save recovery.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/reset_save_heap.c": "745270dc7415b869c302daaa7b9c2b2e5b2865f1",
    "src/load_save.c": "8b723dd044c6024b3671bb890b25b56a53f99ec5",
    "src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
    "src/new_game.c": "3768b3ccb98cdad514b858cbc59244f21bedb7b0",
    "src/overworld.c": "339014da46ae8543143edc99ab72bf7496203a0d",
    "src/link.c": "84506bf0e9a2374bbd8b06c6e78e03905927d17a",
    "src/link_rfu_2.c": "78087d76fd3b2869b2bedc5b6dc29840e7d7a55a",
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def function(text, signature):
    pattern = re.escape(signature) + r"\s*\{(?P<body>.*?)\n\}"
    match = re.search(pattern, text, re.S)
    require(match is not None, "function boundary missing: " + signature)
    return match.group("body")


def ordered(body, tokens, label):
    last = -1
    for token in tokens:
        index = body.find(token, last + 1)
        require(index > last, label + " missing/reordered: " + token)
        last = index


def contract(files):
    reload_body = function(files["src/reset_save_heap.c"], "void ReloadSave(void)")
    ordered(reload_body, [
        "u16 imeBackup = REG_IME;",
        "REG_IME = 0;",
        "RegisterRamReset(RESET_EWRAM);",
        "ClearGpuRegBits(REG_OFFSET_DISPCNT, DISPCNT_FORCED_BLANK);",
        "REG_IME = imeBackup;",
        "gMain.inBattle = FALSE;",
        "SetSaveBlocksPointers();",
        "ResetMenuAndMonGlobals();",
        "Save_ResetSaveCounters();",
        "LoadGameSave(SAVE_NORMAL);",
        "if (gSaveFileStatus == SAVE_STATUS_EMPTY || gSaveFileStatus == SAVE_STATUS_INVALID)",
        "Sav2_ClearSetDefault();",
        "SetPokemonCryStereo(gSaveBlock2Ptr->optionsSound);",
        "InitHeap(gHeap, HEAP_SIZE);",
        "SetMainCallback2(CB2_ContinueSavedGame);",
    ], "ReloadSave")
    require(reload_body.count("RegisterRamReset(") == 1, "unexpected additional RAM reset")
    require(reload_body.count("LoadGameSave(") == 1, "unexpected additional load")

    load = files["src/load_save.c"]
    for token in [
        "EWRAM_DATA struct SaveBlock2 gSaveBlock2 = {0};",
        "EWRAM_DATA struct SaveBlock1 gSaveBlock1 = {0};",
        "EWRAM_DATA struct PokemonStorage gPokemonStorage = {0};",
        "COMMON_DATA struct SaveBlock1 *gSaveBlock1Ptr = NULL;",
        "COMMON_DATA struct SaveBlock2 *gSaveBlock2Ptr = NULL;",
        "COMMON_DATA struct PokemonStorage *gPokemonStoragePtr = NULL;",
        "#define SAVEBLOCK_MOVE_RANGE    128",
    ]:
        require(token in load, "save block memory classification drift: " + token)
    pointer_body = function(load, "void SetSaveBlocksPointers(void)")
    ordered(pointer_body, [
        "offset = (Random()) & ((SAVEBLOCK_MOVE_RANGE - 1) & ~3);",
        "gSaveBlock2Ptr = (void *)(&gSaveBlock2) + offset;",
        "*sav1_LocalVar = (void *)(&gSaveBlock1) + offset;",
        "gPokemonStoragePtr = (void *)(&gPokemonStorage) + offset;",
        "SetBagPocketsPointers();",
        "QL_AddASLROffset(oldSave);",
    ], "save pointer rebinding")
    require("LoadPlayerParty();" in function(load, "void LoadSerializedGame(void)")
            and "LoadObjectEvents();" in function(load, "void LoadSerializedGame(void)"),
            "serialized party/object restoration drift")

    save = files["src/save.c"]
    ordered(function(save, "void Save_ResetSaveCounters(void)"), [
        "gSaveCounter = 0;",
        "gLastWrittenSector = 0;",
        "gDamagedSaveSectors = 0;",
    ], "save counters")
    load_body = function(save, "u8 LoadGameSave(u8 saveType)")
    ordered(load_body, [
        "if (gFlashMemoryPresent != TRUE)",
        "gSaveFileStatus = SAVE_STATUS_NO_FLASH;",
        "return SAVE_STATUS_ERROR;",
        "UpdateSaveAddresses();",
        "case SAVE_NORMAL:",
        "result = TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);",
        "LoadSerializedGame();",
        "gSaveFileStatus = result;",
        "gGameContinueCallback = NULL;",
        "case SAVE_HALL_OF_FAME:",
    ], "save-load dispatch")
    require(re.search(r"result = TryLoadSaveSlot\([^;]+;\s*LoadSerializedGame\(\);", load_body),
            "normal save deserialization no longer follows slot load unconditionally")

    new = files["src/new_game.c"]
    ordered(function(new, "void Sav2_ClearSetDefault(void)"),
            ["ClearSav2();", "SetDefaultOptions();"], "save2 fallback")
    ordered(function(new, "void ResetMenuAndMonGlobals(void)"),
            ["ZeroPlayerPartyMons();", "ZeroEnemyPartyMons();",
             "ResetQuestLog();", "ResetSpecialVars();"], "transient global reset")

    continue_body = function(files["src/overworld.c"], "void CB2_ContinueSavedGame(void)")
    ordered(continue_body, [
        "LoadSaveblockMapHeader();",
        "LoadSaveblockObjEventScripts();",
        "InitMapFromSavedGame();",
        "if (UseContinueGameWarp() == TRUE)",
        "SetWarpDestinationToContinueGameWarp();",
        "SetMainCallback2(CB2_LoadMap);",
        "gFieldCallback = FieldCB_ShowMapNameOnContinue;",
        "CB2_ReturnToField();",
    ], "continue callback branch")

    link = files["src/link.c"]
    require(re.search(
        r"if \(gWirelessCommType == 1\).*?if \(JOY_NEW\(A_BUTTON\)\)"
        r".*?gWirelessCommType = 0;.*?ReloadSave\(\);",
        link, re.S), "link error acknowledgment reload route drift")
    require(re.search(
        r"#if REVISION >= 0xA\s*if \(reloadOrReset\).*?"
        r"if \(FuncIsActiveTask\(Task_MysteryGift\)\) RfuSoftReset\(\);"
        r"\s*else RfuReloadSave\(\);", link, re.S),
        "revision-10 RFU reload vs mystery-gift reset routing drift")
    rfu = files["src/link_rfu_2.c"]
    require(re.search(
        r"#if REVISION >= 0xA\s*static inline void RfuReloadCommon"
        r".*?void RfuReloadSave\(void\)\s*\{\s*RfuReloadCommon\(\);"
        r"\s*ReloadSave\(\);\s*\}", rfu, re.S),
        "revision-10 RFU wrapper drift")

    return {
        "entry": "ReloadSave: interrupt-mask EWRAM-only reset, pointer rebind, save load, continuation",
        "reset_scope": "RESET_EWRAM only",
        "pointer_storage": "IWRAM COMMON_DATA; save block storage EWRAM_DATA",
        "pointer_offset": "Random() masked to 4-byte aligned 0..124",
        "load_result_ignored_by_reloader": True,
        "empty_or_invalid_only_triggers_save2_defaults": True,
        "normal_slot_deserialization_before_status_assignment": True,
        "continue_has_warp_and_nonwarp_paths": True,
        "revision_10_rfu_disconnect_has_reload_vs_softreset_branch": True,
        "runtime_reachability_or_recovery_correctness_proved": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()

    def git(*parts):
        return subprocess.check_output(["git", "-C", str(root), *parts],
                                       text=True, stderr=subprocess.PIPE).strip()

    require(git("rev-parse", "HEAD") == PIN, "pinned upstream commit drift")
    files = {}
    for path, blob in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == blob,
                "pinned source blob mismatch: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(files)

    mutations = [
        ("src/reset_save_heap.c", "REG_IME = 0;", "REG_IME = 1;"),
        ("src/reset_save_heap.c", "RegisterRamReset(RESET_EWRAM);",
         "RegisterRamReset(RESET_ALL);"),
        ("src/reset_save_heap.c", "REG_IME = imeBackup;", "REG_IME = 0;"),
        ("src/reset_save_heap.c", "LoadGameSave(SAVE_NORMAL);",
         "LoadGameSave(SAVE_HALL_OF_FAME);"),
        ("src/reset_save_heap.c",
         "if (gSaveFileStatus == SAVE_STATUS_EMPTY || gSaveFileStatus == SAVE_STATUS_INVALID)",
         "if (gSaveFileStatus == SAVE_STATUS_EMPTY)"),
        ("src/reset_save_heap.c", "SetMainCallback2(CB2_ContinueSavedGame);",
         "SetMainCallback2(CB2_LoadMap);"),
        ("src/load_save.c", "COMMON_DATA struct SaveBlock1 *gSaveBlock1Ptr = NULL;",
         "EWRAM_DATA struct SaveBlock1 *gSaveBlock1Ptr = NULL;"),
        ("src/load_save.c",
         "offset = (Random()) & ((SAVEBLOCK_MOVE_RANGE - 1) & ~3);",
         "offset = 0;"),
        ("src/save.c", "LoadSerializedGame();", "SaveSerializedGame();"),
        ("src/save.c", "u8 LoadGameSave(u8 saveType)\n{\n    u8 result;\n\n    if (gFlashMemoryPresent != TRUE)",
         "u8 LoadGameSave(u8 saveType)\n{\n    u8 result;\n\n    if (gFlashMemoryPresent == TRUE)"),
        ("src/link.c", "sLinkErrorBuffer.disconnected = 0;\n                ReloadSave();",
         "sLinkErrorBuffer.disconnected = 0;\n                DoSoftReset();"),
        ("src/link_rfu_2.c", "RfuReloadCommon();\n    ReloadSave();",
         "RfuReloadCommon();\n    DoSoftReset();"),
        ("src/overworld.c", "if (UseContinueGameWarp() == TRUE)",
         "if (UseContinueGameWarp() == FALSE)"),
        ("src/new_game.c", "SetDefaultOptions();", "ResetMenuAndMonGlobals();"),
        ("src/save.c", "void Save_ResetSaveCounters(void)\n{\n    gSaveCounter = 0;\n    gLastWrittenSector = 0;\n    gDamagedSaveSectors = 0;",
         "void Save_ResetSaveCounters(void)\n{\n    gSaveCounter = 0;\n    gLastWrittenSector = 0;\n    gDamagedSaveSectors = 1;"),
    ]
    for index, (path, before, after) in enumerate(mutations, 1):
        require(before in files[path], "negative fixture missing " + str(index))
        modified = dict(files)
        modified[path] = files[path].replace(before, after, 1)
        try:
            contract(modified)
        except RuntimeError:
            continue
        raise RuntimeError("negative fixture accepted " + str(index) + ": " + path)

    evidence = {
        "evidence_class": "PINNED_FIRERED_RELOAD_SAVE_SOURCE_ONLY",
        "pinned_commit": PIN,
        "source_blobs": BLOBS,
        "facts": facts,
        "negative_controls_passed": len(mutations),
        "gate": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "unresolved": [
            "Compiled EWRAM/IWRAM placement and pointer range across variants",
            "Emulator/hardware EWRAM reset and RFU disconnect execution traces",
            "Invalid/no-flash save continuation and recovery semantics",
            "External-bank save/asset remapping and editor round-trip contracts",
            "Independent whole-file semantic disposition",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PINNED_FIRERED_RELOAD_SAVE_SOURCE_PASS negative_controls=" + str(len(mutations)))
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
