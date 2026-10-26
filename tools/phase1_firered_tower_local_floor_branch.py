#!/usr/bin/env python3
"""Fail-closed source-only Trainer Tower local-floor branch contract.

No compiled/runtime execution, malformed-save reachability, or semantic signoff.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/cereader_tool.c": "395be0bcbed8454e645a9f5670cde3024eda508e",
    "src/trainer_tower_sets.c": "a79580e10e5014c916e2f622cae24ef868381fa9",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
    "include/constants/global.h": "21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9",
}


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def contract(files):
    ereader = files["src/cereader_tool.c"]
    tower = files["src/trainer_tower.c"]
    sets = files["src/trainer_tower_sets.c"]
    constants = files["include/constants/global.h"]
    stub = re.findall(
        r"(?ms)^bool32 ReadTrainerTowerAndValidate\(void\)\s*\{(.*?)^\}",
        ereader,
    )
    require(len(stub) == 1 and
            re.fullmatch(r"\s*//[^\n]*\n\s*return FALSE;\s*", stub[0]),
            "e-Reader validation stub changed: revisit local-floor branch")
    require(re.search(r"(?m)^#define NUM_TOWER_CHALLENGE_TYPES 4$", constants),
            "challenge type count changed")
    bodies = re.findall(
        r"(?ms)^static void SetUpTrainerTowerDataStruct\(void\)\s*\{(.*?)^\}",
        tower,
    )
    require(len(bodies) == 1, "setup definition identity drift")
    body = bodies[0]
    match = re.search(
        r"u32 challengeType = gSaveBlock1Ptr->towerChallengeId;.*?"
        r"if \(ReadTrainerTowerAndValidate\(\) == TRUE\)\s*"
        r"CEReaderTool_LoadTrainerTower\(&sTrainerTowerState->data\);\s*"
        r"else\s*\{(?P<local>.*?)\n    \}",
        body, re.S,
    )
    require(match is not None, "setup local-floor branch or saved-ID capture drift")
    local = match.group("local")
    index = "floors_p = gTrainerTowerFloors[challengeType];"
    require(local.count(index) == 1 and
            "challengeType" not in local[:local.index(index)],
            "new saved challenge-ID handling before floor lookup")
    require(re.search(
        r"floors_p = gTrainerTowerFloors\[challengeType\];\s*"
        r"for \(i = 0; i < MAX_TRAINER_TOWER_FLOORS; i\+\+\)",
        local,
    ), "local-floor table read/copy order drift")
    table = re.search(
        r"(?ms)^const struct TrainerTowerFloor \*const "
        r"gTrainerTowerFloors\[NUM_TOWER_CHALLENGE_TYPES\]"
        r"\[MAX_TRAINER_TOWER_FLOORS\] = \{(.*?)^\};",
        sets,
    )
    require(table is not None, "local-floor table declaration drift")
    entries = re.findall(
        r"\[(CHALLENGE_TYPE_[A-Z]+)\]\s*=\s*\{(.*?)\}",
        table.group(1), re.S,
    )
    require(len(entries) == 4 and
            {name for name, _ in entries} ==
            {"CHALLENGE_TYPE_SINGLE", "CHALLENGE_TYPE_DOUBLE",
             "CHALLENGE_TYPE_KNOCKOUT", "CHALLENGE_TYPE_MIXED"},
            "local-floor challenge-type rows drift")
    for name, values in entries:
        pointers = re.findall(r"&sTrainerTowerFloor_[A-Za-z0-9_]+", values)
        require(len(pointers) == 8 and
                re.sub(r"&sTrainerTowerFloor_[A-Za-z0-9_]+|,|\s", "", values) == "",
                "local-floor row must have eight explicit pointers: " + name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    git = lambda *cmd: subprocess.check_output(
        ["git", "-C", str(root), *cmd], text=True, stderr=subprocess.PIPE
    ).strip()
    require(git("rev-parse", "HEAD") == PIN, "upstream commit drift")
    files = {}
    for path, blob in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == blob,
                "source blob drift: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    contract(files)
    variants = (
        ("src/cereader_tool.c", "return FALSE;", "return TRUE;"),
        ("include/constants/global.h",
         "#define NUM_TOWER_CHALLENGE_TYPES 4",
         "#define NUM_TOWER_CHALLENGE_TYPES 5"),
        ("src/trainer_tower.c",
         "floors_p = gTrainerTowerFloors[challengeType];",
         "floors_p = gTrainerTowerFloors[0];"),
        ("src/trainer_tower.c",
         "floors_p = gTrainerTowerFloors[challengeType];",
         "if (challengeType >= NUM_TOWER_CHALLENGE_TYPES) challengeType = 0;\n"
         "        floors_p = gTrainerTowerFloors[challengeType];"),
    )
    for number, (path, before, after) in enumerate(variants, 1):
        require(before in files[path], "fixture target missing: " + str(number))
        changed = dict(files)
        changed[path] = files[path].replace(before, after, 1)
        try:
            contract(changed)
        except RuntimeError:
            continue
        raise RuntimeError("negative control accepted: " + str(number))
    evidence = {
        "evidence_class": "PINNED_FIRERED_TOWER_LOCAL_FLOOR_BRANCH_SOURCE_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "ereader_validator_stub_returns_false": True,
        "setup_local_floor_branch_selected_by_source_stub": True,
        "local_floor_table_rows": 4,
        "local_floor_pointers_per_row": 8,
        "saved_id_local_pre_index_bounds_check_present": False,
        "negative_controls_passed": len(variants),
        "unresolved": [
            "Whether malformed saved challenge IDs can reach setup during play/load.",
            "Compiled linkage, actual runtime effects, and save-state integrity.",
            "Independent whole-file semantic approval and Phase 1 gates.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("PINNED_TOWER_LOCAL_FLOOR_BRANCH_PASS rows=4 pointers_per_row=8 negative_controls=4")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
