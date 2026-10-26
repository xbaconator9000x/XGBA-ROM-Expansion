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
    "src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
    "src/load_save.c": "8b723dd044c6024b3671bb890b25b56a53f99ec5",
    "src/new_game.c": "3768b3ccb98cdad514b858cbc59244f21bedb7b0",
    "src/overworld.c": "339014da46ae8543143edc99ab72bf7496203a0d",
    "data/maps/TrainerTower_Lobby/scripts.inc": "b2543ec3f7fe3481bb43ebe3bf783e33b668c9c5",
    "data/maps/SevenIsland_TrainerTower/scripts.inc": "b357537593138b61bb43e399d70fca17fd991f0f",
    "data/maps/TrainerTower_Lobby/map.json": "bc3221e5c44e960804fa565e93e3828544722e84",
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


def verify_save_load_boundary(source):
    """Confirm the bounded save-load/whiteout dependency, not global validation."""
    save = source["src/save.c"]
    loader = source["src/load_save.c"]
    new_game = source["src/new_game.c"]
    overworld = source["src/overworld.c"]
    require("result = TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);"
            in save and "LoadSerializedGame();" in save,
            "normal save load/callback sequence drift")
    require("status = GetSaveValidStatus(locations);" in save
            and "CopySaveSlotData(FULL_SAVE_SLOT, locations);" in save,
            "slot validation/copy sequence drift")
    require("gSaveDataBufferPtr->checksum == checksum" in save
            and "locations[id].data[j] = gSaveDataBufferPtr->data[j];" in save,
            "checksum-gated sector copy drift")
    require(re.search(r"void LoadSerializedGame\(void\)\s*\{\s*"
                      r"LoadPlayerParty\(\);\s*LoadObjectEvents\(\);\s*\}",
                      loader) is not None,
            "serialized party/object restore body drift")
    require("ClearSav1();" in new_game and "ResetTrainerTowerResults();" in new_game,
            "new-game save clear/record reset drift")
    require("SetWhiteoutRespawnWarpAndHealerNpc(&sWarpDestination);" in overworld,
            "whiteout caller drift")
    # This is deliberately a bounded observation about these three files,
    # NOT a proof that no other caller validates or normalizes saved IDs.
    require(all("towerChallengeId" not in source[path]
                for path in ("src/save.c", "src/load_save.c", "src/new_game.c")),
            "save/new-game saved-ID handling changed; re-review required")
    mutations = (
        ("src/save.c", "locations[id].data[j] = gSaveDataBufferPtr->data[j];",
         "locations[id].data[j] = 0;"),
        ("src/load_save.c", "LoadObjectEvents();", "LoadBag();"),
        ("src/overworld.c", "SetWhiteoutRespawnWarpAndHealerNpc(&sWarpDestination);",
         "SetWarpDestinationToLastHealLocation();"),
    )
    for index, (path, before, after) in enumerate(mutations, 1):
        require(before in source[path], f"save boundary mutation {index} unavailable")
        altered = dict(source)
        altered[path] = source[path].replace(before, after, 1)
        try:
            verify_save_load_contract_only(altered)
        except RuntimeError:
            continue
        raise RuntimeError(f"save boundary negative control {index} accepted")


def verify_save_load_contract_only(source):
    save, loader, overworld = (source[p] for p in
                               ("src/save.c", "src/load_save.c", "src/overworld.c"))
    require("locations[id].data[j] = gSaveDataBufferPtr->data[j];" in save,
            "sector-copy contract drift")
    require("LoadObjectEvents();" in loader, "serialized restore contract drift")
    require("SetWhiteoutRespawnWarpAndHealerNpc(&sWarpDestination);" in overworld,
            "whiteout caller contract drift")


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



def verify_scene_lifecycle_contract(lobby, exterior, lobby_map):
    """Bounded authored-script/coordinate-event ordering, not runtime reachability."""
    def section(text, first, last):
        require(text.count(first) == text.count(last) == 1,
                "Trainer Tower script section marker drift: " + first)
        return text.split(first, 1)[1].split(last, 1)[0]

    begin = section(lobby, "TrainerTower_Lobby_EventScript_BeginChallenge::",
                    "TrainerTower_Lobby_EventScript_DeclineChallenge::")
    sequence = (
        "copyvar VAR_0x8005, VAR_RESULT",
        "setvar VAR_MAP_SCENE_TRAINER_TOWER, 1",
        "special HealPlayerParty",
        "ttower_startchallenge",
    )
    require(all(begin.count(part) == 1 for part in sequence)
            and [begin.index(part) for part in sequence]
            == sorted(begin.index(part) for part in sequence),
            "lobby challenge scene assignment/start ordering drift")

    exit_script = section(lobby, "TrainerTower_Lobby_EventScript_ExitChallenge::",
                          "TrainerTower_Lobby_EventScript_EnterEnd::")
    require(exit_script.count("setvar VAR_MAP_SCENE_TRAINER_TOWER, 0") == 1,
            "lobby exit challenge scene reset drift")
    transition = section(exterior, "SevenIsland_TrainerTower_OnTransition::",
                         "SevenIsland_TrainerTower_EventScript_TrainerTowerSign::")
    require(transition.count("setvar VAR_MAP_SCENE_TRAINER_TOWER, 0") == 1,
            "exterior transition scene reset drift")

    # These counts apply only to the two pinned scripts, not all generated
    # or compiled script sites in the game.
    scene_set = re.compile(r"(?m)^\\s*setvar VAR_MAP_SCENE_TRAINER_TOWER, [01]\\s*$")
    require(len(scene_set.findall(lobby)) == 2
            and len(scene_set.findall(exterior)) == 1,
            "pinned authored scene setter count drift")

    events = lobby_map.get("coord_events")
    require(isinstance(events, list), "lobby coordinate event table drift")
    triggers = [e for e in events
                if e.get("var") == "VAR_MAP_SCENE_TRAINER_TOWER"]
    require(len(triggers) == 1 and triggers[0].get("var_value") == "0"
            and triggers[0].get("script") ==
                "TrainerTower_Lobby_EventScript_EntryTrigger"
            and (triggers[0].get("x"), triggers[0].get("y"),
                 triggers[0].get("elevation")) == (9, 7, 3),
            "lobby entry scene-gated coordinate trigger drift")


def verify_scene_lifecycle(source):
    lobby = source["data/maps/TrainerTower_Lobby/scripts.inc"]
    exterior = source["data/maps/SevenIsland_TrainerTower/scripts.inc"]
    lobby_map = json.loads(source["data/maps/TrainerTower_Lobby/map.json"])
    verify_scene_lifecycle_contract(lobby, exterior, lobby_map)

    # Each fixture must fail its own source-order/scene-guard contract.
    reordered = lobby.replace(
        "\\tsetvar VAR_MAP_SCENE_TRAINER_TOWER, 1\\n", "", 1
    ).replace(
        "\\tttower_startchallenge\\n",
        "\\ttower_startchallenge\\n\\tsetvar VAR_MAP_SCENE_TRAINER_TOWER, 1\\n", 1
    )
    scene_zero = lobby.replace(
        "setvar VAR_MAP_SCENE_TRAINER_TOWER, 1",
        "setvar VAR_MAP_SCENE_TRAINER_TOWER, 0", 1
    )
    exit_reset = lobby.replace(
        "setvar VAR_MAP_SCENE_TRAINER_TOWER, 0",
        "setvar VAR_MAP_SCENE_TRAINER_TOWER, 1", 1
    )
    exterior_reset = exterior.replace(
        "setvar VAR_MAP_SCENE_TRAINER_TOWER, 0",
        "setvar VAR_MAP_SCENE_TRAINER_TOWER, 1", 1
    )
    changed_trigger = json.loads(json.dumps(lobby_map))
    for event in changed_trigger["coord_events"]:
        if event.get("var") == "VAR_MAP_SCENE_TRAINER_TOWER":
            event["var_value"] = "1"
    variants = (
        (reordered, exterior, lobby_map),
        (scene_zero, exterior, lobby_map),
        (exit_reset, exterior, lobby_map),
        (lobby, exterior_reset, lobby_map),
        (lobby, exterior, changed_trigger),
    )
    require(reordered != lobby and scene_zero != lobby and exit_reset != lobby
            and exterior_reset != exterior and changed_trigger != lobby_map,
            "scene lifecycle negative fixtures failed to mutate")
    for index, (variant_lobby, variant_exterior, variant_map) in enumerate(variants, 1):
        try:
            verify_scene_lifecycle_contract(
                variant_lobby, variant_exterior, variant_map
            )
        except RuntimeError:
            continue
        raise RuntimeError(
            f"scene lifecycle negative control {index} accepted"
        )


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
    require(re.search(r"\bu32 towerChallengeId;\s*/\*0x3D38\*/\s*"
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
    verify_save_load_boundary(source)
    verify_scene_lifecycle(source)

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
        "save_load_negative_controls_passed": 3,
        "authored_tower_scene_lifecycle_negative_controls_passed": 5,
        "authored_lobby_scene_set_precedes_challenge_start": True,
        "lobby_exit_and_exterior_transition_reset_scene": True,
        "lobby_coordinate_entry_trigger_scene_value": 0,
        "save_sector_checksum_validation": True,
        "normal_save_load_copies_sectors_then_restores_party_and_object_events": True,
        "new_game_clears_saveblock1_and_resets_tower_record_times": True,
        "whiteout_caller": "Overworld_SetWhiteoutRespawnPoint",
        "save_load_semantic_range_validation_proven": False,
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
    print("PINNED_TOWER_WHITEOUT_SOURCE_PASS array_extent=4 negative_controls=3 scene_lifecycle_controls=5")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
