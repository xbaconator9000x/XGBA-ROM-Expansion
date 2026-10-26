#!/usr/bin/env python3
"""Pinned FireRed Trainer Tower saved floor-progress / enemy-party table source contract.

Not a malformed-save reachability proof, compiled/runtime test, or semantic approval.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
    "include/global.h": "77155b09014aa854fcf87260e6ad2969e222da53",
    "include/constants/trainer_tower.h": "ea0039ea1408c06b8c968cfde8e2628213b2a0dc",
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def static_body(source, name):
    found = re.findall(r"(?ms)^static void " + re.escape(name)
                       + r"\(void\)\s*\{(.*?)^\}", source)
    require(len(found) == 1, "function definition drift: " + name)
    return found[0]


def contract(files):
    tower = files["src/trainer_tower.c"]
    saved = files["include/global.h"]
    constants = files["include/constants/trainer_tower.h"]

    require(re.search(r"(?m)^#define MAX_TRAINER_TOWER_FLOORS\s+8\s*$", constants),
            "authored floor-table extent drift")
    require(re.search(r"(?m)^#define MAX_TRAINERS_PER_FLOOR\s+3\s*$", constants),
            "authored trainer extent drift")
    require(re.search(r"struct TrainerTower\s*\{.*?\bu8 floorsCleared;", saved, re.S),
            "saved floor-progress type or layout drift")
    require(re.search(r"(?m)^\s*/\*0x3D34\*/ u32 towerChallengeId;\s*$", saved)
            and re.search(r"(?m)^\s*/\*0x3D38\*/ struct TrainerTower trainerTower"
                          r"\[NUM_TOWER_CHALLENGE_TYPES\];\s*$", saved),
            "saved challenge record structure drift")

    increment = static_body(tower, "TrainerTowerAddFloorCleared")
    require(increment.strip() == "TRAINER_TOWER.floorsCleared++;",
            "unbounded saved floor-progress increment drift")
    start = static_body(tower, "StartTrainerTowerChallenge")
    require("TRAINER_TOWER.floorsCleared = 0;" in start,
            "challenge-start floor-progress reset drift")
    enemy = static_body(tower, "BuildEnemyParty")
    require(re.search(r"u8 floorIdx = TRAINER_TOWER\.floorsCleared;", enemy),
            "saved progress to enemy-party floor index drift")
    require(re.search(r"ZeroEnemyPartyMons\(\);\s*switch \(CURR_FLOOR\.challengeType\)",
                      enemy), "enemy-party control flow before first table read drift")
    require("if (" not in enemy.split("sSingleBattleChallengeMonIdxs[floorIdx][i]")[0],
            "new branch before first floor-table read: review bounds")
    table_specs = {
        "sSingleBattleChallengeMonIdxs": (2, ("[floorIdx][i]",)),
        "sDoubleBattleChallengeMonIdxs": (2, ("[floorIdx][0]", "[floorIdx][1]")),
        "sKnockoutChallengeMonIdxs": (3, ("[floorIdx][trainerIdx]",)),
    }
    for name, (width, accesses) in table_specs.items():
        pattern = (r"(?ms)^static const u8 " + re.escape(name)
                   + r"\[MAX_TRAINER_TOWER_FLOORS\]\[" + str(width)
                   + r"\]\s*=\s*\{(.*?)^\};")
        match = re.search(pattern, tower)
        require(match is not None, "floor-table declaration drift: " + name)
        rows = re.findall(r"(?m)^\s*\{([0-9,\s]+)\},?\s*$", match.group(1))
        require(len(rows) == 8, "floor-table initializer row count drift: " + name)
        for row in rows:
            values = [part.strip() for part in row.split(",")]
            require(len(values) == width and all(v.isdigit() for v in values),
                    "floor-table row width or initializer drift: " + name)
        for access in accesses:
            require(name + access in enemy, "floor-table consumer drift: " + name + access)

    battle = static_body(tower, "DoTrainerTowerBattle")
    require(re.search(r"BuildEnemyParty\(\);\s*CreateTask\(", battle),
            "enemy-party builder call order drift")
    return {"saved_progress_type": "u8", "floor_table_rows": 8,
            "floor_table_widths": {"single": 2, "double": 2, "knockout": 3},
            "source_only_out_of_range_saved_progress": "8..255",
            "progress_reset_at_challenge_start": True,
            "increment_has_local_bound": False,
            "compiled_or_runtime_reachability_proven": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    root = args.source.resolve()

    def git(*cmd):
        return subprocess.check_output(["git", "-C", str(root), *cmd],
                                       text=True, stderr=subprocess.PIPE).strip()

    require(git("rev-parse", "HEAD") == PIN, "upstream commit drift")
    files = {}
    for path, expected in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == expected,
                "upstream Git blob drift: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(files)

    mutations = [
        ("include/global.h", "u8 floorsCleared;", "u16 floorsCleared;"),
        ("include/constants/trainer_tower.h", "#define MAX_TRAINER_TOWER_FLOORS 8",
         "#define MAX_TRAINER_TOWER_FLOORS 9"),
        ("src/trainer_tower.c", "u8 floorIdx = TRAINER_TOWER.floorsCleared;",
         "u8 floorIdx = sTrainerTowerState->floorIdx;"),
        ("src/trainer_tower.c", "TRAINER_TOWER.floorsCleared++;",
         "if (TRAINER_TOWER.floorsCleared < 8) TRAINER_TOWER.floorsCleared++;"),
        ("src/trainer_tower.c", "sKnockoutChallengeMonIdxs[floorIdx][trainerIdx]",
         "sKnockoutChallengeMonIdxs[0][trainerIdx]"),
        ("src/trainer_tower.c", "sDoubleBattleChallengeMonIdxs[floorIdx][0]",
         "sDoubleBattleChallengeMonIdxs[floorIdx + 1][0]"),
        ("src/trainer_tower.c", "BuildEnemyParty();\n    CreateTask",
         "ZeroEnemyPartyMons();\n    CreateTask"),
        ("src/trainer_tower.c", "    {1, 4, 5}\n};\n\nextern",
         "    {1, 4, 5},\n    {1, 4, 5}\n};\n\nextern"),
        ("src/trainer_tower.c", "ZeroEnemyPartyMons();\n\n    switch",
         "ZeroEnemyPartyMons();\n    if (floorIdx >= 8) return;\n\n    switch"),
    ]
    for index, (path, old, new) in enumerate(mutations, 1):
        require(old in files[path], "missing negative fixture: " + str(index))
        changed = dict(files)
        changed[path] = files[path].replace(old, new, 1)
        try:
            contract(changed)
        except RuntimeError:
            continue
        raise RuntimeError("negative fixture passed incorrectly: " + str(index))

    result = {
        "evidence_class": "PINNED_FIRERED_TOWER_FLOOR_PROGRESS_SOURCE_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "facts": facts,
        "negative_controls_passed": len(mutations),
        "unresolved": [
            "Whether saved floorsCleared >= 8 survives save loading and reaches a battle.",
            "Whether authored floor progression or script guards constrain all runtime paths.",
            "Compiled ROM and emulator negative tests; independent whole-file dispositions.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PINNED_TOWER_FLOOR_PROGRESS_SOURCE_PASS rows=8 negative_controls=9")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
