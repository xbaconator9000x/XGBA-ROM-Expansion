#!/usr/bin/env python3
"""Exact-pinned Trainer Tower script-switch fallthrough and index boundary audit.

Source semantics only: no claim of malformed-state reachability, runtime exploit,
compiled behavior, independent semantic approval or Phase 2 implementation.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "data/scripts/trainer_tower.inc": "6a526e9fc97c431321fe11e8ca20068e7af2c085",
    "asm/macros/event.inc": "142ad979d7d3093244087a247fa2b4883424f77f",
    "src/scrcmd.c": "97b695ee2f6fca80a3b78f52f6a444f696fe5814",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
    "asm/macros/trainer_tower.inc": "94d9efe775658c7865d74f8819b9c5bfb74db893",
    "include/constants/trainer_tower.h": "ea0039ea1408c06b8c968cfde8e2628213b2a0dc",
    "include/constants/global.h": "21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9",
}

def require(value, reason):
    if not value:
        raise RuntimeError(reason)

def script_labels(source):
    matches = list(re.finditer(r"(?m)^([A-Za-z_]\w*)::?\s*$", source))
    require(matches, "script labels missing")
    return {
        match.group(1): (source[match.end():matches[i + 1].start()]
                         if i + 1 < len(matches) else source[match.end():])
        for i, match in enumerate(matches)
    }, [match.group(1) for match in matches]

def commands(body):
    return [line.strip() for line in body.splitlines()
            if line.strip() and not line.lstrip().startswith("@")]

def verify_switch(labels, ordered, label, prefix, variable, cases, next_label):
    require(label in labels and next_label in labels, "missing label: " + label)
    lines = commands(labels[label])
    expected = ([part for part in prefix.split("\n") if part] + ["switch " + variable]) + [
        "case " + value + ", " + destination for value, destination in cases
    ]
    require(lines == expected, "switch branch/default/fallthrough drift: " + label)
    require(ordered[ordered.index(label) + 1] == next_label,
            "adjacent fallthrough target drift: " + label)
    return {"source_label": label, "unmatched_next_label": next_label,
            "tested_cases": [value for value, _ in cases]}

def verify_floor_transition(labels, ordered, files):
    """Pin C floor-layout index before the script's unmatched-type fallback."""
    tower = files["src/trainer_tower.c"]
    macros = files["asm/macros/trainer_tower.inc"]
    constants = files["include/constants/trainer_tower.h"]
    global_constants = files["include/constants/global.h"]
    for name, value, header in [
        ("CHALLENGE_TYPE_SINGLE", 0, constants),
        ("CHALLENGE_TYPE_DOUBLE", 1, constants),
        ("CHALLENGE_TYPE_KNOCKOUT", 2, constants),
        ("CHALLENGE_TYPE_MIXED", 3, constants),
        ("MAX_TRAINER_TOWER_FLOORS", 8, constants),
        ("NUM_TOWER_CHALLENGE_TYPES", 4, global_constants),
    ]:
        require(re.search(r"(?m)^#define\s+" + name + r"\s+" + str(value) + r"\s*(?://[^\n]*)?$",
                          header), "Trainer Tower dimension/enum drift: " + name)
    require(re.search(
        r"(?s)\.macro ttower_initfloor\s+"
        r"setvar VAR_0x8004, TRAINER_TOWER_FUNC_INIT_FLOOR\s+"
        r"special CallTrainerTowerFunc\s+\.endm", macros),
        "script-to-C init-floor macro dispatch drift")
    require(re.search(
        r"\[TRAINER_TOWER_FUNC_INIT_FLOOR\]\s*=\s*InitTrainerTowerFloor,", tower),
        "native init-floor dispatch drift")
    table = re.search(
        r"static const u16 sFloorLayouts\[MAX_TRAINER_TOWER_FLOORS\]"
        r"\[NUM_TOWER_CHALLENGE_TYPES - 1\]\s*=\s*\{(.*?)\n\};", tower, re.S)
    require(table is not None, "8x3 floor-layout declaration drift")
    actual_rows = re.findall(r"\{[^{}]+\}", table.group(1))
    expected_rows = [
        "{LAYOUT_TRAINER_TOWER_%dF, LAYOUT_TRAINER_TOWER_%dF_DOUBLES, LAYOUT_TRAINER_TOWER_%dF_KNOCKOUT}" % (n, n, n)
        for n in range(1, 9)
    ]
    require([re.sub(r"\s+", "", row) for row in actual_rows] ==
            [re.sub(r"\s+", "", row) for row in expected_rows],
            "8x3 floor-layout initializer drift")
    init = re.search(
        r"(?ms)^static void InitTrainerTowerFloor\(void\)\s*\{.*?^\}", tower)
    require(init is not None, "native init-floor definition missing")
    original = re.sub(r"//[^\n]*", "", init.group(0))
    expected = """static void InitTrainerTowerFloor(void)
    {
        if (gMapHeader.mapLayoutId - LAYOUT_TRAINER_TOWER_LOBBY > sTrainerTowerState->data.numFloors)
        {
            gSpecialVar_Result = 3;
            SetCurrentMapLayout(LAYOUT_TRAINER_TOWER_ROOF);
        }
        else
        {
            gSpecialVar_Result = CURR_FLOOR.challengeType;
            SetCurrentMapLayout(sFloorLayouts[sTrainerTowerState->floorIdx][gSpecialVar_Result]);
            SetTrainerTowerNPCGraphics();
        }
    }"""
    require(re.sub(r"\s+", " ", original).strip() ==
            re.sub(r"\s+", " ", expected).strip(),
            "native floor-layout index / roof branch / pre-index guard drift")
    label = "TrainerTower_OnTransition"
    next_label = "TrainerTower_EventScript_SetObjectsSingles"
    require(label in labels and next_label in labels and
            ordered[ordered.index(label) + 1] == next_label,
            "script transition label adjacency drift")
    require(commands(labels[label]) == [
        "ttower_initfloor",
        "switch VAR_RESULT",
        "case CHALLENGE_TYPE_SINGLE, TrainerTower_EventScript_SetObjectsSingles",
        "case CHALLENGE_TYPE_DOUBLE, TrainerTower_EventScript_SetObjectsDoubles",
        "case CHALLENGE_TYPE_KNOCKOUT, TrainerTower_EventScript_SetObjectsKnockout",
        "setflag HIDE_TRAINER_DOUBLES1",
        "setflag HIDE_TRAINER_SINGLES",
        "setflag HIDE_TRAINER_KNOCKOUT",
        "setflag HIDE_TRAINER_DOUBLES2",
        "setvar DISABLE_SINGLES_TRIGGER, TRUE",
        "setvar DISABLE_DOUBLES_TRIGGER, TRUE",
        "end",
    ], "unmatched transition challenge-type fallback drift")
    return {
        "native_floor_layout_rows": 8,
        "native_floor_layout_columns": 3,
        "mixed_challenge_id": 3,
        "native_layout_index_checked_locally": False,
        "unmatched_transition_script_hides_trainers_and_triggers": True,
        "script_default_can_prevent_native_preceding_index": False,
        "invalid_floor_challenge_type_reachability_proven": False,
    }

def contract(files):
    script = files["data/scripts/trainer_tower.inc"]
    macros = files["asm/macros/event.inc"]
    runtime = files["src/scrcmd.c"]
    tower = files["src/trainer_tower.c"]
    require(re.search(
        r"(?s)\.macro switch var:req\s+copyvar VAR_0x8000, \\var\s+\.endm"
        r"\s+\.macro case condition:req, dest:req\s+"
        r"compare VAR_0x8000, \\condition\s+goto_if_eq \\dest\s+\.endm",
        macros), "switch/case macro conditional-dispatch drift")
    jump = re.search(
        r"bool8 ScrCmd_goto_if\(struct ScriptContext \* ctx\)\s*\{([^{}]*)\}",
        runtime, re.S)
    require(jump is not None, "runtime conditional jump function drift")
    jump_body = jump.group(1)
    require(re.search(
        r"if \(sScriptConditionTable\[condition\]\[ctx->comparisonResult\] == 1\)"
        r"\s*ScriptJump\(ctx, scrptr\);", jump_body),
        "runtime conditional jump semantics drift")
    compare = re.search(
        r"bool8 ScrCmd_compare_var_to_value\(struct ScriptContext \* ctx\)"
        r"\s*\{([^{}]*)\}", runtime, re.S)
    require(compare is not None and
            "ctx->comparisonResult = Compare(value1, value2);" in compare.group(1),
            "runtime compare semantics drift")
    labels, ordered = script_labels(script)
    floor_facts = verify_floor_transition(labels, ordered, files)
    edges = [
        verify_switch(labels, ordered, "TrainerTower_EventScript_TriggerBattle",
                      "ttower_getchallengetype", "VAR_RESULT",
                      [("CHALLENGE_TYPE_SINGLE", "TrainerTower_EventScript_DoSingleBattle"),
                       ("CHALLENGE_TYPE_DOUBLE", "TrainerTower_EventScript_DoDoubleBattle"),
                       ("CHALLENGE_TYPE_KNOCKOUT", "TrainerTower_EventScript_DoKnockoutBattle")],
                      "TrainerTower_EventScript_DoSingleBattle"),
        verify_switch(labels, ordered, "TrainerTower_EventScript_DoKnockoutBattle",
                      "", "VAR_TEMP_1",
                      [("0", "TrainerTower_EventScript_DoKnockoutBattle1"),
                       ("1", "TrainerTower_EventScript_DoKnockoutBattle2"),
                       ("2", "TrainerTower_EventScript_DoKnockoutBattle3")],
                      "TrainerTower_EventScript_DoKnockoutBattle1"),
        verify_switch(labels, ordered, "TrainerTower_EventScript_DoBattle",
                      "ttower_dobattle\nwaitstate", "VAR_RESULT",
                      [("B_OUTCOME_WON", "TrainerTower_EventScript_WonBattle"),
                       ("B_OUTCOME_LOST", "TrainerTower_EventScript_WarpToLobbyLost"),
                       ("B_OUTCOME_DREW", "TrainerTower_EventScript_WarpToLobbyLost")],
                      "TrainerTower_EventScript_WonBattle"),
        verify_switch(labels, ordered, "TrainerTower_EventScript_WonBattle",
                      "ttower_getchallengetype", "VAR_RESULT",
                      [("CHALLENGE_TYPE_SINGLE", "TrainerTower_EventScript_SetFloorCleared"),
                       ("CHALLENGE_TYPE_DOUBLE", "TrainerTower_EventScript_MoveDoublesTrainers"),
                       ("CHALLENGE_TYPE_KNOCKOUT", "TrainerTower_EventScript_CheckNextKnockoutBattle")],
                      "TrainerTower_EventScript_CheckNextKnockoutBattle"),
        verify_switch(labels, ordered, "TrainerTower_EventScript_CheckNextKnockoutBattle",
                      "", "VAR_TEMP_1",
                      [("0", "TrainerTower_EventScript_DoSecondKnockoutBattle"),
                       ("1", "TrainerTower_EventScript_DoThirdKnockoutBattle"),
                       ("2", "TrainerTower_EventScript_MoveLastKnockoutTrainer")],
                      "TrainerTower_EventScript_DoSecondKnockoutBattle"),
    ]
    # An empty prefix must not add an empty command.
    require(commands(labels["TrainerTower_EventScript_DoSecondKnockoutBattle"]) ==
            ["addvar VAR_TEMP_1, 1",
             "goto TrainerTower_EventScript_DoKnockoutBattle"],
            "unmatched knockout progression path drift")
    require(commands(labels["TrainerTower_EventScript_DoThirdKnockoutBattle"]) ==
            ["addvar VAR_TEMP_1, 1",
             "goto TrainerTower_EventScript_DoKnockoutBattle"],
            "normal knockout progression path drift")
    require("ttower_getspeech TRAINER_TOWER_TEXT_INTRO, VAR_TEMP_1" in
            labels["TrainerTower_EventScript_DoKnockoutBattleIntro"],
            "knockout speech index dependency drift")
    require(re.search(r"trainerId = VarGet\(VAR_TEMP_1\);", tower) and
            "CURR_FLOOR.trainers[trainerId + 1]" in tower,
            "native battle index dependency drift")
    return {"floor_init_layout_index": floor_facts,
            "unmatched_switch_fallthrough_edges": edges,
            "unmatched_outcome_next_label": "TrainerTower_EventScript_WonBattle",
            "unmatched_knockout_progression": "increment VAR_TEMP_1 then retry dispatch",
            "source_semantics_proven": True,
            "unmatched_value_reachability_proven": False,
            "compiled_runtime_compatibility_proven": False}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    root = args.source.resolve()
    def git(*cmd):
        return subprocess.check_output(["git", "-C", str(root), *cmd],
                                       text=True, stderr=subprocess.PIPE).strip()
    require(git("rev-parse", "HEAD") == PIN, "upstream revision drift")
    files = {}
    for path, blob in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == blob,
                "upstream Git blob drift: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(files)
    changes = [
        ("asm/macros/event.inc", "goto_if_eq \\dest", "goto \\dest", "macro_conditional"),
        ("src/scrcmd.c", "if (sScriptConditionTable[condition][ctx->comparisonResult] == 1)",
         "if (TRUE)", "runtime_conditional"),
        ("data/scripts/trainer_tower.inc",
         "case B_OUTCOME_DREW, TrainerTower_EventScript_WarpToLobbyLost",
         "goto TrainerTower_EventScript_WarpToLobbyLost", "outcome_default"),
        ("data/scripts/trainer_tower.inc",
         "case 2, TrainerTower_EventScript_DoKnockoutBattle3",
         "case 3, TrainerTower_EventScript_DoKnockoutBattle3", "knockout_dispatch"),
        ("data/scripts/trainer_tower.inc",
         "case 2, TrainerTower_EventScript_MoveLastKnockoutTrainer",
         "goto TrainerTower_EventScript_MoveLastKnockoutTrainer", "knockout_default"),
        ("data/scripts/trainer_tower.inc",
         "addvar VAR_TEMP_1, 1\n\tgoto TrainerTower_EventScript_DoKnockoutBattle",
         "setvar VAR_TEMP_1, 0\n\tgoto TrainerTower_EventScript_DoKnockoutBattle",
         "knockout_increment"),
        ("src/trainer_tower.c",
         "SetCurrentMapLayout(sFloorLayouts[sTrainerTowerState->floorIdx][gSpecialVar_Result]);",
         "SetCurrentMapLayout(sFloorLayouts[sTrainerTowerState->floorIdx][gSpecialVar_Result % 3]);",
         "floor_layout_index_clamp"),
        ("src/trainer_tower.c",
         "gSpecialVar_Result = 3; // Skip past usable challenge types",
         "gSpecialVar_Result = 2; // Skip past usable challenge types",
         "roof_sentinel"),
        ("src/trainer_tower.c",
         "LAYOUT_TRAINER_TOWER_8F_KNOCKOUT}",
         "LAYOUT_TRAINER_TOWER_7F_KNOCKOUT}", "floor_layout_row"),
        ("data/scripts/trainer_tower.inc",
         "setflag HIDE_TRAINER_SINGLES", "clearflag HIDE_TRAINER_SINGLES",
         "transition_hide_all"),
        ("include/constants/trainer_tower.h",
         "#define CHALLENGE_TYPE_MIXED      3",
         "#define CHALLENGE_TYPE_MIXED      2", "mixed_enum"),
        ("asm/macros/trainer_tower.inc",
         "special CallTrainerTowerFunc", "special UnrelatedSpecial",
         "transition_macro_dispatch"),
    ]
    for path, before, after, name in changes:
        require(before in files[path], "missing negative fixture: " + name)
        modified = dict(files)
        modified[path] = files[path].replace(before, after, 1)
        try:
            contract(modified)
        except RuntimeError:
            continue
        raise RuntimeError("fail-open negative control: " + name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "evidence_class": "PINNED_FIRERED_TOWER_SCRIPT_SWITCH_SOURCE_ONLY",
        "upstream_commit": PIN, "pinned_blobs": BLOBS,
        "phase1_verdict": "FAIL_INCOMPLETE", "independent_whole_file_approvals": 0,
        "facts": facts, "negative_controls_passed": len(changes),
        "unresolved": [
            "Reachability of unmatched battle outcomes, challenge types, and temporary indices",
            "Compiled script dispatch and runtime/emulator behavior",
            "Full save-state lifecycle and independent whole-file semantic dispositions",
            "Cross-repository editor round-trip and compatibility gates",
        ],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PINNED_TOWER_SCRIPT_FALLTHROUGH_SOURCE_PASS edges=5 floor_layout=8x3 negatives=12")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")

if __name__ == "__main__":
    main()
