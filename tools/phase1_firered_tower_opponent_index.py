#!/usr/bin/env python3
"""Pinned FireRed Trainer Tower battle-opponent index dependency (source only).

This checker is NOT a reachability proof, runtime test, or independent review.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
    "src/battle_util2.c": "8a5fbccf67942b9bc55d460cea07a2744c9a2b14",
    "data/scripts/trainer_tower.inc": "6a526e9fc97c431321fe11e8ca20068e7af2c085",
    "include/constants/trainer_tower.h": "ea0039ea1408c06b8c968cfde8e2628213b2a0dc",
    "include/constants/vars.h": "5c7bbf8a3356606af13e744ac24de806c1b0869e",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def body(source, name):
    hits = re.findall(r"(?ms)^void " + re.escape(name) + r"\(void\)\s*\{(.*?)^\}", source)
    require(len(hits) == 1, "function body drift: " + name)
    return hits[0]


def contract(files):
    tower = files["src/trainer_tower.c"]
    battle = files["src/battle_util2.c"]
    scripts = files["data/scripts/trainer_tower.inc"]
    constants = files["include/constants/trainer_tower.h"]
    variables = files["include/constants/vars.h"]

    require(re.search(r"(?m)^#define MAX_TRAINERS_PER_FLOOR\s+3\s*$", constants),
            "per-floor trainer extent drift")
    require(re.search(r"(?m)^#define MAX_TRAINER_TOWER_FLOORS\s+8\s*$", constants),
            "floor extent drift")
    require("Temporary variables. Temp vars are cleared every time a map is loaded." in variables
            and re.search(r"(?m)^#define VAR_TEMP_1\s+\(TEMP_VARS_START \+ 0x1\)", variables),
            "temporary variable definition or lifetime drift")

    alloc = body(battle, "AllocateBattleResources")
    require(re.search(r"if \(gBattleTypeFlags & BATTLE_TYPE_TRAINER_TOWER\)\s*"
                      r"InitTrainerTowerBattleStruct\(\);", alloc),
            "Trainer Tower battle-resource entrypoint drift")
    opponent = body(tower, "InitTrainerTowerBattleStruct")
    require(re.search(r"SetUpTrainerTowerDataStruct\(\);\s*"
                      r"sTrainerTowerOpponent = AllocZeroed\(sizeof\(\*sTrainerTowerOpponent\)\);\s*"
                      r"trainerId = VarGet\(VAR_TEMP_1\);\s*"
                      r"StringCopyN\(sTrainerTowerOpponent->name, "
                      r"CURR_FLOOR\.trainers\[trainerId\]\.name, 11\);", opponent),
            "opponent setup and first index sequence drift")
    before_first = opponent[:opponent.index("StringCopyN(sTrainerTowerOpponent->name")]
    require("if (" not in before_first and "trainerId %" not in before_first,
            "new local opponent-index guard or normalization: revisit proof")
    require(opponent.count("CURR_FLOOR.trainers[trainerId]") >= 4,
            "base trainer-index consumers drift")
    require(re.search(r"if \(CURR_FLOOR.challengeType == CHALLENGE_TYPE_DOUBLE\)"
                      r"\s*\{[^}]*CURR_FLOOR\.trainers\[trainerId \+ 1\]\.speechWin"
                      r"[^}]*CURR_FLOOR\.trainers\[trainerId \+ 1\]\.speechLose",
                      opponent, re.S), "double-battle second trainer index drift")

    knockout = re.search(
        r"(?s)TrainerTower_EventScript_DoKnockoutBattle::(.*?)"
        r"TrainerTower_EventScript_DoKnockoutBattle1:", scripts)
    require(knockout is not None and re.search(
        r"switch VAR_TEMP_1\s*case 0,\s*\S+\s*case 1,\s*\S+\s*case 2,\s*\S+",
        knockout.group(1)), "authored knockout index cases drift")
    require(scripts.count("\taddvar VAR_TEMP_1, 1") == 2,
            "authored knockout index progression drift")
    return {"per_floor_trainer_extent": 3, "authored_knockout_cases": [0, 1, 2],
            "double_battle_additional_index": "trainerId + 1"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root = args.source.resolve()

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(root), *arguments],
                                       text=True, stderr=subprocess.PIPE).strip()

    require(git("rev-parse", "HEAD") == PIN, "upstream commit drift")
    files = {}
    for path, expected in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == expected,
                "pinned Git blob mismatch: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(files)
    mutations = [
        ("include/constants/trainer_tower.h", "#define MAX_TRAINERS_PER_FLOOR  3",
         "#define MAX_TRAINERS_PER_FLOOR  4"),
        ("src/trainer_tower.c", "CURR_FLOOR.trainers[trainerId + 1].speechWin",
         "CURR_FLOOR.trainers[trainerId + 2].speechWin"),
        ("src/trainer_tower.c",
         "trainerId = VarGet(VAR_TEMP_1);\n    StringCopyN",
         "trainerId = VarGet(VAR_TEMP_1);\n    if (trainerId >= MAX_TRAINERS_PER_FLOOR) trainerId = 0;\n    StringCopyN"),
        ("src/battle_util2.c", "InitTrainerTowerBattleStruct();",
         "FreeTrainerTowerBattleStruct();"),
        ("data/scripts/trainer_tower.inc",
         "\tcase 2, TrainerTower_EventScript_DoKnockoutBattle3",
         "\tcase 3, TrainerTower_EventScript_DoKnockoutBattle3"),
    ]
    for number, (path, original, replacement) in enumerate(mutations, 1):
        require(original in files[path], "negative fixture missing: " + str(number))
        altered = dict(files)
        altered[path] = files[path].replace(original, replacement, 1)
        try:
            contract(altered)
        except RuntimeError:
            continue
        raise RuntimeError("negative control incorrectly passed: " + str(number))
    evidence = {
        "evidence_class": "PINNED_FIRERED_TOWER_OPPONENT_INDEX_SOURCE_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "facts": facts,
        "negative_controls_passed": len(mutations),
        "unresolved": [
            "Every runtime producer and consumer of VAR_TEMP_1 during battle entry.",
            "Whether malformed temporary state can reach a battle and exceed floor trainer bounds.",
            "Whether double-battle trainerId + 1 remains within the per-floor extent.",
            "Compiled/runtime, editor/emulator compatibility and independent review.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("PINNED_TOWER_OPPONENT_INDEX_SOURCE_PASS negative_controls=5")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
