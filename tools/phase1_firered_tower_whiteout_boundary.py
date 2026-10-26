#!/usr/bin/env python3
"""Pinned FireRed Trainer Tower whiteout/save-index source boundary.

Conditional source-level proof obligation only. No compiled/runtime reachability,
save corruption, independent review, or memory-safety failure is asserted.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/heal_location.c": "80700d49a328bd46e620c30071976375d6f748ce",
    "include/global.h": "77155b09014aa854fcf87260e6ad2969e222da53",
    "include/constants/global.h": "21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
}
SIGNATURE = "void SetWhiteoutRespawnWarpAndHealerNpc(struct WarpData * warp)"
NEXT_FUNCTION = "static void SetWhiteoutRespawnHealerNpcAsLastTalked(u32 healLocationIdx)"
INDEX = "gSaveBlock1Ptr->trainerTower[gSaveBlock1Ptr->towerChallengeId].spokeToOwner"
SCENE_AND_INDEX = re.compile(
    r"if\s*\(VarGet\(VAR_MAP_SCENE_TRAINER_TOWER\)\s*==\s*1\)\s*"
    r"\{\s*if\s*\(!gSaveBlock1Ptr->trainerTower"
    r"\[gSaveBlock1Ptr->towerChallengeId\]\.spokeToOwner\)"
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def verify_whiteout_function(source):
    require(source.count(SIGNATURE) == 1, "whiteout function identity drift")
    body = source.split(SIGNATURE, 1)[1]
    require(NEXT_FUNCTION in body, "whiteout function end marker drift")
    body = body.split(NEXT_FUNCTION, 1)[0]
    require(SCENE_AND_INDEX.search(body) is not None,
            "whiteout scene-gated saved-ID array index drift")
    require(body.count(INDEX) == 1, "whiteout saved-ID array read count drift")
    position = body.index(INDEX)
    require("towerChallengeId" not in body[:position],
            "new pre-index challenge-ID handling requires semantic re-review")
    # The BUGFIX branch below the scene-gated read handles a different
    # healLocationIdx lookup, not the trainerTower[challengeId] read.
    require("#ifdef BUGFIX" in body and position < body.index("#ifdef BUGFIX"),
            "whiteout BUGFIX branch positioning drift")


def negative_controls(source):
    verify_whiteout_function(source)
    variants = (
        source.replace("VAR_MAP_SCENE_TRAINER_TOWER) == 1",
                       "VAR_MAP_SCENE_TRAINER_TOWER) == 0", 1),
        source.replace(INDEX, "gSaveBlock1Ptr->trainerTower[0].spokeToOwner", 1),
        source.replace("if (!" + INDEX + ")",
                       "if (gSaveBlock1Ptr->towerChallengeId >= NUM_TOWER_CHALLENGE_TYPES)\n"
                       "            return;\n        if (!" + INDEX + ")", 1),
    )
    require(len(set(variants)) == 3 and all(v != source for v in variants),
            "whiteout negative fixture mutation did not apply")
    for index, variant in enumerate(variants, 1):
        try:
            verify_whiteout_function(variant)
        except RuntimeError:
            continue
        raise RuntimeError(f"whiteout negative control {index} accepted")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    require(git(root, "rev-parse", "HEAD") == PIN, "FireRed source revision drift")
    source = {}
    for path, blob in BLOBS.items():
        require((root / path).is_file(), "missing pinned source: " + path)
        require(git(root, "hash-object", path) == blob,
                "pinned source byte drift: " + path)
        source[path] = (root / path).read_text(encoding="utf-8")

    global_header = source["include/global.h"]
    constants = source["include/constants/global.h"]
    tower = source["src/trainer_tower.c"]
    require(re.search(r"\bu32 towerChallengeId;\s*"
                      r"struct TrainerTower trainerTower\[NUM_TOWER_CHALLENGE_TYPES\];",
                      global_header) is not None,
            "saved challenge ID and array layout drift")
    require(re.search(r"(?m)^#define NUM_TOWER_CHALLENGE_TYPES 4$", constants)
            is not None, "Trainer Tower save-array extent drift")
    require("void CallTrainerTowerFunc(void)\n{\n"
            "    SetUpTrainerTowerDataStruct();\n"
            "    sTrainerTowerFunctions[gSpecialVar_0x8004]();" in tower,
            "Trainer Tower setup-before-dispatch order drift")
    require("if (gSaveBlock1Ptr->towerChallengeId >= NUM_TOWER_CHALLENGE_TYPES)"
            in tower and "gSaveBlock1Ptr->towerChallengeId = 0;" in tower,
            "challenge-start saved-ID normalization drift")
    require("floors_p = gTrainerTowerFloors[challengeType];" in tower,
            "setup-time saved-ID table index drift")
    negative_controls(source["src/heal_location.c"])

    output = {
        "evidence_class": "PINNED_FIRERED_WHITEOUT_INDEX_SOURCE_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "trainer_tower_saved_array_extent": 4,
        "saved_challenge_id_type": "u32",
        "whiteout_scene_predicate": "VarGet(VAR_MAP_SCENE_TRAINER_TOWER) == 1",
        "whiteout_reads_saved_challenge_id_without_local_bounds_check": True,
        "whiteout_bugfix_branch_is_later_else_branch": True,
        "conditional_out_of_bounds_witness_id": 4,
        "negative_controls_passed": 3,
        "unresolved": [
            "Whether an out-of-range saved ID can survive save loading or occur in ordinary play.",
            "Whether the whiteout scene predicate and malformed ID can coincide.",
            "Compiled ROM execution, memory-safety outcome, and emulator/save tests.",
            "Independent whole-file semantic dispositions and Phase 1 exit gates.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("PINNED_TOWER_WHITEOUT_SOURCE_PASS array_extent=4 negative_controls=3")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
