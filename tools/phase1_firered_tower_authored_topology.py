#!/usr/bin/env python3
"""Pinned authored Trainer Tower map topology and battle-progress dependency census.

Source-only evidence. This does not certify script reachability, runtime bounds,
malformed-save behavior, emulator compatibility, or independent semantic approval.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
FLOOR_BLOBS = [
    "5304effe2201feb9736487ba3efa2bc100341169",
    "9d15aa978a397768961a61702133e8b352833a74",
    "a78eee80a32b426d325b312871fb9c21d0ef58a3",
    "5fe5dce7a6a388f7f85c9a3d0fa3e0f34bac4126",
    "5b1e39ebd835feed47bb35a67c106e8ab03053e1",
    "3f64443c4752f7d5db019cdb3ee296dcde2d149c",
    "db35b661c08175cc7461dc272e02c53fa5dff8d6",
    "0193e52d1d7aaf90869f4fad46862fc147467a8e",
]
BLOBS = {
    **{f"data/maps/TrainerTower_{n}F/map.json": blob
       for n, blob in enumerate(FLOOR_BLOBS, 1)},
    "data/maps/TrainerTower_Lobby/map.json": "bc3221e5c44e960804fa565e93e3828544722e84",
    "data/maps/TrainerTower_Roof/map.json": "3e603b3cd23bf368af3353b5ba9541eb411f0145",
    "data/maps/TrainerTower_Elevator/map.json": "285a704d1b0d47291ff44dc0b1920526a39300be",
    "data/maps/TrainerTower_Lobby/scripts.inc": "b2543ec3f7fe3481bb43ebe3bf783e33b668c9c5",
    "data/maps/TrainerTower_Elevator/scripts.inc": "5aa850140d1ee5ed9de5910ed35997f1bcc60b57",
    "data/scripts/trainer_tower.inc": "6a526e9fc97c431321fe11e8ca20068e7af2c085",
    "asm/macros/trainer_tower.inc": "94d9efe775658c7865d74f8819b9c5bfb74db893",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
    "include/constants/trainer_tower.h": "ea0039ea1408c06b8c968cfde8e2628213b2a0dc",
}

def require(ok, why):
    if not ok:
        raise RuntimeError(why)

def body_after_label(source, label):
    match = re.search(r"(?ms)^" + re.escape(label) +
                      r":{1,2}\s*\n(.*?)(?=^[A-Za-z_][\w]*:{1,2}\s*$|\Z)", source)
    require(match is not None, "missing script label: " + label)
    return match.group(1)

def inspect(files):
    floor_rows = []
    expected_triggers = {
        ("TrainerTower_EventScript_SingleBattleTrigger", "VAR_TEMP_E"),
        ("TrainerTower_EventScript_DoubleBattleTriggerTop", "VAR_TEMP_F"),
        ("TrainerTower_EventScript_DoubleBattleTriggerBottom", "VAR_TEMP_F"),
    }
    for n in range(1, 9):
        # Position and elevation are part of the authored trigger ABI, not
        # merely decoration: the 1F upper double trigger is elevation zero.
        expected_positions = {
            "TrainerTower_EventScript_SingleBattleTrigger": (10, 13, 3),
            "TrainerTower_EventScript_DoubleBattleTriggerTop":
                (9, 12, 0 if n == 1 else 3),
            "TrainerTower_EventScript_DoubleBattleTriggerBottom": (9, 13, 3),
        }
        path = f"data/maps/TrainerTower_{n}F/map.json"
        m = json.loads(files[path])
        require(m["layout"] == f"LAYOUT_TRAINER_TOWER_{n}F",
                f"floor {n}: layout drift")
        warps = m["warp_events"]
        expected_up = (f"MAP_TRAINER_TOWER_{n + 1}F" if n < 8
                       else "MAP_TRAINER_TOWER_ROOF")
        expected_down = (f"MAP_TRAINER_TOWER_{n - 1}F" if n > 1
                         else "MAP_TRAINER_TOWER_LOBBY")
        require(len(warps) == (2 if n == 1 else 3),
                f"floor {n}: warp count drift")
        require(warps[0]["dest_map"] == expected_up and
                str(warps[0]["dest_warp_id"]) == "1" and
                warps[1]["dest_map"] == expected_down and
                str(warps[1]["dest_warp_id"]) == "0",
                f"floor {n}: stair destination drift")
        expected_warp_positions = [(15, 6, 3), (4, 6, 3)]
        if n > 1:
            expected_warp_positions.append((13, 5, 0))
        require(
            [(w["x"], w["y"], w["elevation"]) for w in warps]
            == expected_warp_positions,
            f"floor {n}: authored warp coordinate/elevation drift",
        )
        if n > 1:
            require(warps[2]["dest_map"] == "MAP_TRAINER_TOWER_ELEVATOR",
                    f"floor {n}: elevator destination drift")
        triggers = m["coord_events"]
        require(len(triggers) == 3 and
                {(e["script"], e["var"]) for e in triggers} == expected_triggers
                and all(str(e["var_value"]) == "0" and e["type"] == "trigger"
                        for e in triggers)
                and {(e["script"], e["x"], e["y"], e["elevation"])
                     for e in triggers}
                == {(name, *position)
                    for name, position in expected_positions.items()},
                f"floor {n}: authored battle-trigger drift")
        floor_rows.append({
            "floor": n,
            "layout": m["layout"],
            "up": expected_up,
            "down": expected_down,
            "elevator": n > 1,
            "trigger_scripts": sorted(e["script"] for e in triggers),
            "trigger_positions": {
                e["script"]: [e["x"], e["y"], e["elevation"]]
                for e in triggers
            },
            "warp_positions": expected_warp_positions,
            "source_blob": BLOBS[path],
        })
    lobby = json.loads(files["data/maps/TrainerTower_Lobby/map.json"])
    roof = json.loads(files["data/maps/TrainerTower_Roof/map.json"])
    elevator = json.loads(files["data/maps/TrainerTower_Elevator/map.json"])
    require(lobby["layout"] == "LAYOUT_TRAINER_TOWER_LOBBY" and
            {e["dest_map"] for e in lobby["warp_events"]} ==
            {"MAP_TRAINER_TOWER_1F", "MAP_SEVEN_ISLAND_TRAINER_TOWER",
             "MAP_TRAINER_TOWER_ELEVATOR"},
            "lobby authored warps drift")
    require(roof["layout"] == "LAYOUT_TRAINER_TOWER_ROOF" and
            {e["dest_map"] for e in roof["warp_events"]} ==
            {"MAP_TRAINER_TOWER_8F", "MAP_TRAINER_TOWER_ELEVATOR"},
            "roof authored warps drift")
    require(elevator["layout"] == "LAYOUT_TRAINER_TOWER_ELEVATOR" and
            len(elevator["warp_events"]) == 1 and
            elevator["warp_events"][0]["dest_map"] == "MAP_DYNAMIC",
            "elevator dynamic return warp drift")
    elevscript = files["data/maps/TrainerTower_Elevator/scripts.inc"]
    roof_select = body_after_label(elevscript,
                                   "TrainerTower_Elevator_EventScript_SelectRoof")
    lobby_select = body_after_label(elevscript,
                                    "TrainerTower_Elevator_EventScript_SelectLobby")
    require(re.search(r"^\s*goto TrainerTower_Elevator_EventScript_CloseFloorSelect\s*$",
                      roof_select, re.M) and "warp " not in roof_select,
            "elevator roof selection no-op drift")
    require("setdynamicwarp MAP_TRAINER_TOWER_LOBBY, 17, 8" in lobby_select and
            "warp MAP_TRAINER_TOWER_LOBBY, 17, 8" in lobby_select,
            "elevator lobby selection warp drift")
    shared = files["data/scripts/trainer_tower.inc"]
    macro = files["asm/macros/trainer_tower.inc"]
    lobby_script = files["data/maps/TrainerTower_Lobby/scripts.inc"]
    tower = files["src/trainer_tower.c"]
    constants = files["include/constants/trainer_tower.h"]
    require("#define MAX_TRAINER_TOWER_FLOORS 8" in constants,
            "floor extent drift")
    require("ttower_startchallenge" in lobby_script and
            "copyvar VAR_0x8005, VAR_RESULT" in lobby_script and
            "TRAINER_TOWER.floorsCleared = 0;" in tower,
            "lobby challenge initialization drift")
    require("ttower_clearedfloor" in macro and
            "TRAINER_TOWER_FUNC_CLEARED_FLOOR" in macro and
            shared.count("ttower_clearedfloor") == 1 and
            re.search(r"(?m)^TrainerTower_EventScript_SetFloorCleared:\s*\n\s*ttower_clearedfloor\s*$",
                      shared) and
            "TRAINER_TOWER.floorsCleared++;" in tower,
            "authored floor increment path drift")
    require("case B_OUTCOME_WON, TrainerTower_EventScript_WonBattle" in shared
            and "case B_OUTCOME_LOST, TrainerTower_EventScript_WarpToLobbyLost" in shared
            and "case B_OUTCOME_DREW, TrainerTower_EventScript_WarpToLobbyLost" in shared,
            "battle-outcome dispatch drift")
    require("ttower_isfloorcleared" in shared and
            "setvar DISABLE_SINGLES_TRIGGER, TRUE" in shared and
            "setvar DISABLE_DOUBLES_TRIGGER, TRUE" in shared,
            "prior-floor trigger disable drift")
    require("u8 floorIdx = TRAINER_TOWER.floorsCleared;" in tower and
            "sSingleBattleChallengeMonIdxs[floorIdx][i]" in tower and
            "sDoubleBattleChallengeMonIdxs[floorIdx][0]" in tower and
            "sKnockoutChallengeMonIdxs[floorIdx][trainerIdx]" in tower,
            "saved progress table consumer drift")
    return {
        "floor_rows": floor_rows,
        "authored_floor_count": len(floor_rows),
        "authored_floor_battle_triggers": len(floor_rows) * 3,
        "authored_elevator_floor_entries": 7,
        "elevator_roof_selection": "close menu, no warp in inspected label",
        "elevator_lobby_selection": "dynamic warp and explicit lobby warp",
        "authored_floor_clear_macro_calls": 1,
        "floor_progress_source": "saved TRAINER_TOWER.floorsCleared",
        "normal_gameplay_reachability_proven": False,
        "malformed_save_index_safety_proven": False,
        "compiled_or_emulator_behavior_proven": False,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root = args.source.resolve()
    def git(*cmd):
        return subprocess.check_output(["git", "-C", str(root), *cmd],
                                       text=True, stderr=subprocess.PIPE).strip()
    require(git("rev-parse", "HEAD") == PIN, "upstream commit drift")
    files = {}
    for path, blob in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == blob,
                "pinned source drift: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    facts = inspect(files)
    mutations = [
        ("data/maps/TrainerTower_8F/map.json",
         "MAP_TRAINER_TOWER_ROOF", "MAP_TRAINER_TOWER_1F", "stair"),
        ("data/maps/TrainerTower_4F/map.json",
         "TrainerTower_EventScript_SingleBattleTrigger",
         "TrainerTower_EventScript_OtherTrigger", "trigger"),
        ("data/maps/TrainerTower_Elevator/scripts.inc",
         "goto TrainerTower_Elevator_EventScript_CloseFloorSelect",
         "goto TrainerTower_Elevator_EventScript_SelectLobby", "elevator"),
        ("src/trainer_tower.c",
         "TRAINER_TOWER.floorsCleared++;",
         "TRAINER_TOWER.floorsCleared += 2;", "progress"),
        ("data/maps/TrainerTower_4F/map.json",
         '"x": 10,\n      "y": 13,\n      "elevation": 3',
         '"x": 11,\n      "y": 13,\n      "elevation": 3',
         "trigger_coordinate"),
        ("data/maps/TrainerTower_1F/map.json",
         '"x": 9,\n      "y": 12,\n      "elevation": 0',
         '"x": 9,\n      "y": 12,\n      "elevation": 3',
         "first_floor_trigger_elevation"),
        ("data/maps/TrainerTower_8F/map.json",
         '"x": 15,\n      "y": 6,\n      "elevation": 3',
         '"x": 14,\n      "y": 6,\n      "elevation": 3',
         "stair_coordinate"),
    ]
    for path, old, new, label in mutations:
        require(old in files[path], "negative fixture missing: " + label)
        changed = dict(files)
        changed[path] = files[path].replace(old, new, 1)
        try:
            inspect(changed)
        except (RuntimeError, ValueError, KeyError):
            continue
        raise RuntimeError("fail-open negative control: " + label)
    evidence = {
        "evidence_class": "PINNED_FIRERED_TOWER_AUTHORED_TOPOLOGY_SOURCE_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "facts": facts,
        "negative_controls_passed": len(mutations),
        "unresolved": [
            "Compiled map/script inclusion and full engine trigger execution semantics",
            "All battle-outcome and repeat-entry paths before floor increment",
            "Saved floorsCleared and temporary opponent index reachability",
            "Editor round-trip and emulator runtime compatibility",
            "Independent whole-file semantic dispositions",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PINNED_TOWER_TOPOLOGY_SOURCE_PASS floors=8 triggers=24 negatives=7")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")

if __name__ == "__main__":
    main()
