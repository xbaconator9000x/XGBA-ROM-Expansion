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
    return {"unmatched_switch_fallthrough_edges": edges,
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
    print("PINNED_TOWER_SCRIPT_FALLTHROUGH_SOURCE_PASS edges=5 negatives=6")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")

if __name__ == "__main__":
    main()
