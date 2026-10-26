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
    # Resolve every local table pointer to its actual floor record. In the
    # mixed challenge, row membership is not the per-floor battle type.
    expected = {
        "CHALLENGE_TYPE_SINGLE": ["Single_%d" % n for n in range(1, 9)],
        "CHALLENGE_TYPE_DOUBLE": ["Double_%d" % n for n in range(1, 9)],
        "CHALLENGE_TYPE_KNOCKOUT": ["Knockout_%d" % n for n in range(1, 9)],
        "CHALLENGE_TYPE_MIXED": [
            "Mixed_1", "Mixed_2", "Mixed_3", "Double_8",
            "Mixed_5", "Knockout_8", "Double_3", "Knockout_2",
        ],
    }
    refs = []
    for name, values in entries:
        pointers = re.findall(r"&sTrainerTowerFloor_([A-Za-z0-9_]+)", values)
        require(pointers == expected[name],
                "local-floor pointer identity/order drift: " + name)
        refs.extend(pointers)
    require(len(refs) == 32 and len(set(refs)) == 28,
            "local-floor pointer identity cardinality drift")
    definitions = re.findall(
        r"(?ms)^static const struct TrainerTowerFloor "
        r"(sTrainerTowerFloor_[A-Za-z0-9_]+)\\s*=\\s*\\{(.*?)^\\};",
        sets,
    )
    require(len(definitions) == 32 and
            len({name for name, _ in definitions}) == 32,
            "local-floor record definition cardinality/identity drift")
    records = dict(definitions)
    resolved_types = {}
    for pointer in sorted(set(refs)):
        body = records.get("sTrainerTowerFloor_" + pointer)
        require(body is not None, "unresolved local-floor pointer: " + pointer)
        types = re.findall(
            r"(?m)^\\s*\\.challengeType\\s*=\\s*(CHALLENGE_TYPE_[A-Z]+),\\s*$",
            body,
        )
        require(len(types) == 1 and types[0] in {
            "CHALLENGE_TYPE_SINGLE", "CHALLENGE_TYPE_DOUBLE",
            "CHALLENGE_TYPE_KNOCKOUT",
        }, "local-floor record challenge type out of 8x3 column range: " + pointer)
        require(len(re.findall(
            r"(?m)^\\s*\\.floorIdx\\s*=\\s*MAX_TRAINER_TOWER_FLOORS,\\s*$",
            body,
        )) == 1, "local-floor record floorIdx metadata drift: " + pointer)
        resolved_types[pointer] = types[0]
    require([resolved_types[p] for p in expected["CHALLENGE_TYPE_MIXED"]] == [
        "CHALLENGE_TYPE_SINGLE", "CHALLENGE_TYPE_SINGLE",
        "CHALLENGE_TYPE_SINGLE", "CHALLENGE_TYPE_DOUBLE",
        "CHALLENGE_TYPE_DOUBLE", "CHALLENGE_TYPE_KNOCKOUT",
        "CHALLENGE_TYPE_DOUBLE", "CHALLENGE_TYPE_KNOCKOUT",
    ], "mixed local-floor effective challenge-type sequence drift")
    return {
        "local_floor_references": len(refs),
        "unique_referenced_floor_records": len(set(refs)),
        "mixed_effective_challenge_types": [
            resolved_types[p] for p in expected["CHALLENGE_TYPE_MIXED"]
        ],
        "all_referenced_floor_challenge_types_within_0_to_2": True,
        "malformed_or_mutated_floor_data_reachability_proven": False,
    }


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
    facts = contract(files)
    variants = (
        ("src/cereader_tool.c",
         "bool32 ReadTrainerTowerAndValidate(void)\n{\n"
         "    // Stubbed out. Populated in Emerald\n    return FALSE;",
         "bool32 ReadTrainerTowerAndValidate(void)\n{\n"
         "    // Stubbed out. Populated in Emerald\n    return TRUE;"),
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
        ("src/trainer_tower_sets.c",
         "&sTrainerTowerFloor_Mixed_5,",
         "&sTrainerTowerFloor_Mixed_4,"),
        ("src/trainer_tower_sets.c",
         ".challengeType = CHALLENGE_TYPE_SINGLE,",
         ".challengeType = CHALLENGE_TYPE_MIXED,"),
        ("src/trainer_tower_sets.c",
         "&sTrainerTowerFloor_Double_8,",
         "&sTrainerTowerFloor_Double_7,"),
        ("src/trainer_tower_sets.c",
         ".floorIdx = MAX_TRAINER_TOWER_FLOORS,",
         ".floorIdx = 7,"),
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
        "resolved_floor_record_facts": facts,
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
    print("PINNED_TOWER_LOCAL_FLOOR_BRANCH_PASS rows=4 pointers=32 distinct_records=28 negative_controls=8")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
