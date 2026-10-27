#!/usr/bin/env python3
"""Pinned source-only Trainer Tower temporary-index producer/consumer lifecycle.

This is a scoped dependency proof, not full runtime reachability or independent review.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/overworld.c": "339014da46ae8543143edc99ab72bf7496203a0d",
    "src/event_data.c": "da9391cf0ef74c1addf550def8616c81f16e89e3",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
    "include/constants/vars.h": "5c7bbf8a3356606af13e744ac24de806c1b0869e",
    "data/scripts/trainer_tower.inc": "6a526e9fc97c431321fe11e8ca20068e7af2c085",
    "asm/macros/trainer_tower.inc": "94d9efe775658c7865d74f8819b9c5bfb74db893",
    "data/maps/TrainerTower_1F/scripts.inc": "372c44088964a77dcb5c415c5eb793fa85277339",
    "data/maps/TrainerTower_2F/scripts.inc": "53656a9cd0f16fa7e16792f898c584095a318ba0",
    "data/maps/TrainerTower_3F/scripts.inc": "4a05c3d206ad4735c4527668dd9cef134674194f",
    "data/maps/TrainerTower_4F/scripts.inc": "fe739642eea3973d01555e0deaa2a83bf8c33fee",
    "data/maps/TrainerTower_5F/scripts.inc": "499884160c08741130a250bfd8c437e035ebe0bf",
    "data/maps/TrainerTower_6F/scripts.inc": "44f0ddce87b5edc48301c798551120bdfe5ddd9b",
    "data/maps/TrainerTower_7F/scripts.inc": "2f2f5cde794c5b086196c6f8014cad40b89b4953",
    "data/maps/TrainerTower_8F/scripts.inc": "8f97efe21719bfa16d2dafafc834b0e21d47e69c",
}

def require(value, message):
    if not value:
        raise RuntimeError(message)

def contract(files):
    ow = files["src/overworld.c"]
    event = files["src/event_data.c"]
    tower = files["src/trainer_tower.c"]
    vars_source = files["include/constants/vars.h"]
    scripts = files["data/scripts/trainer_tower.inc"]
    macros = files["asm/macros/trainer_tower.inc"]
    require("Temporary variables. Temp vars are cleared every time a map is loaded." in vars_source
            and re.search(r"#define VAR_TEMP_1\s+\(TEMP_VARS_START \+ 0x1\)", vars_source),
            "temporary-variable identity drift")
    clear = re.search(r"(?ms)^void ClearTempFieldEventData\(void\)\s*\{(.*?)^\}", event)
    require(clear is not None and
            "memset(gSaveBlock1Ptr->vars + ((TEMP_VARS_START - VARS_START) * 2), 0, TEMP_VARS_SIZE);" in clear.group(1),
            "temporary-variable clearing implementation drift")
    for name in ("LoadMapFromCameraTransition", "LoadMapFromWarp"):
        match = re.search(r"(?ms)^(?:static )?void " + name + r"\([^\n]*\)\s*\{(.*?)^\}", ow)
        require(match is not None, "map-load function drift: " + name)
        body = match.group(1)
        require("ClearTempFieldEventData();" in body and
                "RunOnTransitionMapScript();" in body and
                body.index("ClearTempFieldEventData();") < body.index("RunOnTransitionMapScript();"),
                "temporary clear/transition script order drift: " + name)
    for floor in range(1, 9):
        path = f"data/maps/TrainerTower_{floor}F/scripts.inc"
        source = files[path]
        for kind, label in (("MAP_SCRIPT_ON_RESUME", "TrainerTower_OnResume"),
                            ("MAP_SCRIPT_ON_TRANSITION", "TrainerTower_OnTransition"),
                            ("MAP_SCRIPT_ON_FRAME_TABLE", "TrainerTower_OnFrame")):
            require(f"map_script {kind}, {label}" in source,
                    "floor map-script dispatch drift: " + path)
        require("VAR_TEMP_1" not in source,
                "new floor-local temporary index writer/consumer: " + path)
    require(re.search(r"(?s)TrainerTower_OnTransition::(.*?)TrainerTower_EventScript_SetObjectsSingles::",
                      scripts) is not None, "shared transition script drift")
    require("setvar VAR_TEMP_1" not in scripts and "copyvar VAR_TEMP_1" not in scripts,
            "new shared script index initialization: revisit model")
    require(scripts.count("addvar VAR_TEMP_1, 1") == 2,
            "knockout increment count drift")
    for n in range(3):
        require(re.search(r"(?m)^\s*case " + str(n) +
                          r", TrainerTower_EventScript_DoKnockoutBattle" + str(n+1) + r"\s*$",
                          scripts), "knockout switch case drift")
    require("switch VAR_TEMP_1" in scripts and
            "ttower_dobattle" in scripts and
            "case CHALLENGE_TYPE_DOUBLE, TrainerTower_EventScript_DoDoubleBattle" in scripts,
            "shared battle dispatch drift")
    require("trainerId = VarGet(VAR_TEMP_1);" in tower and
            tower.count("CURR_FLOOR.trainers[trainerId + 1]") == 2 and
            "CURR_FLOOR.trainers[trainerId + 1].speechWin" in tower and
            "CURR_FLOOR.trainers[trainerId + 1].speechLose" in tower and
            "u16 trainerIdx = VarGet(VAR_TEMP_1);" in tower and
            "u16 idx = VarGet(VAR_TEMP_1);" in tower,
            "C opponent/party/music index consumers drift")
    require("VarSet(VAR_TEMP_1, windowId);" in tower and
            "u8 windowId = VarGet(VAR_TEMP_1);" in tower,
            "results board variable reuse drift")
    require(re.search(r"(?s)\.macro ttower_showresults(.*?)\.endm", macros)
            and "TRAINER_TOWER_FUNC_SHOW_RESULTS" in macros,
            "results-board macro dispatch drift")
    require("ttower_showresults" not in scripts,
            "shared script newly invokes results-board macro")
    return {
        "floor_script_count": 8,
        "map_load_paths_verified": 2,
        "temp_index_reset": "zero before map transition scripts on two checked paths",
        "authored_knockout_cases": [0, 1, 2],
        "authored_knockout_increments": 2,
        "double_second_index": "trainerId + 1",
        "results_board_reuses_var_temp_1": True,
        "all_ingress_paths_proven": False,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.source.resolve()
    def git(*params):
        return subprocess.check_output(["git", "-C", str(root), *params],
                                       text=True, stderr=subprocess.PIPE).strip()
    require(git("rev-parse", "HEAD") == PIN, "pinned upstream revision drift")
    files = {}
    for path, blob in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == blob,
                "pinned source byte drift: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(files)
    mutations = [
        ("src/overworld.c", "    ClearTempFieldEventData();",
         "    /* missing temp clear */", "clear"),
        ("src/event_data.c", "0, TEMP_VARS_SIZE);",
         "1, TEMP_VARS_SIZE);", "zero"),
        ("data/maps/TrainerTower_8F/scripts.inc", "TrainerTower_OnTransition",
         "TrainerTower_OnOtherTransition", "floor8"),
        ("data/scripts/trainer_tower.inc", "addvar VAR_TEMP_1, 1",
         "addvar VAR_TEMP_1, 2", "knockout"),
        ("src/trainer_tower.c", "CURR_FLOOR.trainers[trainerId + 1]",
         "CURR_FLOOR.trainers[trainerId + 2]", "double"),
    ]
    for path, old, new, label in mutations:
        require(old in files[path], "negative fixture missing: " + label)
        changed = dict(files)
        changed[path] = files[path].replace(old, new, 1)
        try:
            contract(changed)
        except RuntimeError:
            continue
        raise RuntimeError("fail-open negative control: " + label)
    evidence = {
        "evidence_class": "PINNED_FIRERED_TOWER_TEMP_INDEX_LIFETIME_SOURCE_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "facts": facts,
        "negative_controls_passed": len(mutations),
        "unresolved": [
            "Other map-loading/continuation paths and externally triggered script calls.",
            "Compiled script entrypoint inclusion and control-flow reachability.",
            "Malformed temp index and saved progress negative tests in emulators.",
            "Independent whole-file review and editor interoperability.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PINNED_TOWER_TEMP_INDEX_LIFETIME_SOURCE_PASS floors=8 negatives=5")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")

if __name__ == "__main__":
    main()
