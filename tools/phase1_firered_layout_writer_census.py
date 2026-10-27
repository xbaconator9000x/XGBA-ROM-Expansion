#!/usr/bin/env python3
"""Fail-closed, pinned-source census of FireRed layout-ID writers and selectors.

Source-level authored candidates only; not runtime reachability, compiled inclusion,
emulator proof, or independent whole-file semantic review.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "data/layouts/layouts.json": "41d0eb1b5e51fa75d535b5a098bae2bd650f710d",
    "src/overworld.c": "339014da46ae8543143edc99ab72bf7496203a0d",
    "src/event_data.c": "da9391cf0ef74c1addf550def8616c81f16e89e3",
    "include/constants/vars.h": "5c7bbf8a3356606af13e744ac24de806c1b0869e",
    "src/quest_log.c": "0a2f76f2c4019fa0938d5044da73fcea1b2b069c",
    "src/scrcmd.c": "97b695ee2f6fca80a3b78f52f6a444f696fe5814",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
    "src/cereader_tool.c": "395be0bcbed8454e645a9f5670cde3024eda508e",
    "src/trainer_tower_sets.c": "a79580e10e5014c916e2f622cae24ef868381fa9",
    "include/cereader_tool.h": "5cb5a9ebc32db23de07800ccce124bcb28d3ef15",
    "include/constants/trainer_tower.h": "ea0039ea1408c06b8c968cfde8e2628213b2a0dc",
    "asm/macros/event.inc": "142ad979d7d3093244087a247fa2b4883424f77f",
    "data/script_cmd_table.inc": "c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1",
    "data/maps/ThreeIsland_DunsparceTunnel/scripts.inc": "889af04201aef92c34fc9ceac64a5370fba27fe2",
    "data/maps/SeafoamIslands_B3F/scripts.inc": "0f0494f1aaeca0fddaf94bacaf002d717d0e2cc6",
    "data/maps/SeafoamIslands_B4F/scripts.inc": "d6a90577860179caa8613c8efa90dfb671d09b7c",
    "data/maps/SevenIsland_House_Room1/scripts.inc": "5e7ce493bdb26c3ddbbbfee6e2c9c338faff3dcf",
}
SCRIPT_SELECTORS = {
    "data/maps/ThreeIsland_DunsparceTunnel/scripts.inc": "LAYOUT_THREE_ISLAND_DUNSPARCE_TUNNEL_DUG_OUT",
    "data/maps/SeafoamIslands_B3F/scripts.inc": "LAYOUT_SEAFOAM_ISLANDS_B3F_CURRENT_STOPPED",
    "data/maps/SeafoamIslands_B4F/scripts.inc": "LAYOUT_SEAFOAM_ISLANDS_B4F_CURRENT_STOPPED",
    "data/maps/SevenIsland_House_Room1/scripts.inc": "LAYOUT_SEVEN_ISLAND_HOUSE_ROOM1_DOOR_OPEN",
}

# Recognise every authored instruction line before validating its operand.
# The old LAYOUT_-only matcher silently ignored numeric and variable operands.
SCRIPT_INSTRUCTION_RE = re.compile(
    r"(?m)^[ \t]*(?:[A-Za-z_][A-Za-z0-9_]*:{1,2}[ \t]*)?setmaplayoutindex\b([^\r\n]*)$"
)

def authored_script_layout_operands(source):
    operands = []
    for match in SCRIPT_INSTRUCTION_RE.finditer(source):
        operand = match.group(1).split("@", 1)[0].strip()
        require(re.fullmatch(r"LAYOUT_[A-Z0-9_]+", operand) is not None,
                "unsupported authored setmaplayoutindex operand: " + repr(operand))
        operands.append(operand)
    return operands

def verify_selector_scanner_negative_controls():
    require(authored_script_layout_operands(
        "\tsetmaplayoutindex LAYOUT_EXAMPLE @ comment\n"
        "Example_Label:: setmaplayoutindex LAYOUT_OTHER\n"
    ) == ["LAYOUT_EXAMPLE", "LAYOUT_OTHER"],
            "selector scanner positive controls failed")
    for invalid in (
        "\tsetmaplayoutindex VAR_QLBAK_MAP_LAYOUT\n",
        "\tsetmaplayoutindex 300\n",
        "\tsetmaplayoutindex\n",
        "\tsetmaplayoutindex LAYOUT_A, LAYOUT_B\n",
    ):
        try:
            authored_script_layout_operands(invalid)
        except RuntimeError:
            continue
        raise RuntimeError("selector scanner accepted invalid operand: " + repr(invalid))

def run_git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   text=True, stderr=subprocess.PIPE).strip()

def require(ok, msg):
    if not ok:
        raise RuntimeError(msg)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.source.resolve()
    require(run_git(root, "rev-parse", "HEAD") == PIN, "upstream revision drift")
    sources = {}
    for path, blob in BLOBS.items():
        p = root / path
        require(p.is_file(), "missing pinned file: " + path)
        # Hash actual working-tree bytes, not only the HEAD tree: fail closed on edits.
        require(run_git(root, "hash-object", path) == blob, "source byte drift: " + path)
        sources[path] = p.read_text(encoding="utf-8")

    layouts = json.loads(sources["data/layouts/layouts.json"])["layouts"]
    require(len(layouts) == 383, "layout table position drift")
    layout_by_id = {}
    for slot, row in enumerate(layouts, 1):
        if not row:
            continue
        ident = row["id"]
        require(ident not in layout_by_id, "duplicate layout ID")
        layout_by_id[ident] = (slot, row["border_width"], row["border_height"])
    require(len(layout_by_id) == 365, "named layout census drift")
    zero = {name for name, (_, w, h) in layout_by_id.items() if w == 0 or h == 0}
    require(len(zero) == 28, "zero-border census drift")

    overworld = sources["src/overworld.c"]
    quest = sources["src/quest_log.c"]
    scrcmd = sources["src/scrcmd.c"]
    tower = sources["src/trainer_tower.c"]
    event_data = sources["src/event_data.c"]
    var_constants = sources["include/constants/vars.h"]
    # A literal script operand is not a variable lookup in this pinned engine.
    # VarGet returns its argument unchanged when GetVarPointer returns NULL.
    get_var_ptr = event_data.split("u16 *GetVarPointer(u16 idx)", 1)
    require(len(get_var_ptr) == 2, "GetVarPointer definition missing")
    get_var_ptr = get_var_ptr[1].split("static bool8 IsFlagOrVarStoredInQuestLog", 1)[0]
    var_get = event_data.split("u16 VarGet(u16 idx)", 1)
    require(len(var_get) == 2, "VarGet definition missing")
    var_get = var_get[1].split("bool8 VarSet(u16 idx", 1)[0]
    require("if (idx < VARS_START)\n        return NULL;" in get_var_ptr,
            "literal variable-pointer identity contract drift")
    require("u16 *ptr = GetVarPointer(idx);" in var_get
            and "if (ptr == NULL)\n        return idx;" in var_get
            and "return *ptr;" in var_get, "VarGet literal identity contract drift")
    require("#define VARS_START 0x4000" in var_constants,
            "variable range start drift")
    require("#define VAR_QLBAK_MAP_LAYOUT        0x40AE" in var_constants,
            "quest-log backup variable identity drift")
    vars_start = 0x4000
    for expression in (
        "gSaveBlock1Ptr->mapLayoutId = gMapHeader.mapLayoutId;",
        "gSaveBlock1Ptr->mapLayoutId = mapLayoutId;",
        "return gMapLayouts[mapLayoutId - 1];",
        "gMapHeader.mapLayout = GetMapLayout();",
    ):
        require(expression in overworld, "overworld layout writer/consumer drift: " + expression)
    for expression in (
        "gSaveBlock1Ptr->mapLayoutId = VarGet(VAR_QLBAK_MAP_LAYOUT);",
        "gSaveBlock1Ptr->mapLayoutId = header.mapLayoutId;",
        "if (gSaveBlock1Ptr->mapLayoutId == 0)",
        "VarSet(VAR_QLBAK_MAP_LAYOUT, gSaveBlock1Ptr->mapLayoutId);",
    ):
        require(expression in quest, "quest-log layout restore drift: " + expression)
    for expression in (
        "u16 value = VarGet(ScriptReadHalfword(ctx));",
        "SetCurrentMapLayout(value);",
    ):
        require(expression in scrcmd, "script layout setter drift: " + expression)
    require(".4byte ScrCmd_setmaplayoutindex" in sources["data/script_cmd_table.inc"],
            "script opcode dispatch drift")
    require(".macro setmaplayoutindex index:req" in sources["asm/macros/event.inc"]
            and r".2byte \index" in sources["asm/macros/event.inc"],
            "script layout opcode encoding drift")

    assignment = re.compile(r"gSaveBlock1Ptr->mapLayoutId\s*=(?!=)")
    require(len(assignment.findall(overworld)) == 2, "overworld direct writer count drift")
    require(len(assignment.findall(quest)) == 2, "quest-log direct writer count drift")

    verify_selector_scanner_negative_controls()
    script_sites = []
    # Scan all authored data assembly sources, not only map scripts.inc files.
    # Fail closed if an invocation uses a numeric/variable/unknown operand.
    for path in sorted(p for p in (root / "data").rglob("*")
                       if p.is_file() and p.suffix in (".inc", ".s")):
        relative = path.relative_to(root).as_posix()
        matches = authored_script_layout_operands(path.read_text(encoding="utf-8"))
        if not matches:
            continue
        require(relative in SCRIPT_SELECTORS and matches == [SCRIPT_SELECTORS[relative]],
                "unmodeled script layout selector: " + relative)
        require(run_git(root, "hash-object", relative) == BLOBS[relative],
                "script selector source byte drift: " + relative)
        script_sites.append({"path": relative, "layout": matches[0]})
    require(len(script_sites) == 4, "script layout selector census drift")

    begin = tower.find("static const u16 sFloorLayouts[")
    require(begin >= 0, "trainer tower layout table missing")
    end = tower.find("};", begin)
    require(end > begin, "trainer tower layout table unterminated")
    floor_ids = re.findall(r"LAYOUT_[A-Z0-9_]+", tower[begin:end])
    require(len(floor_ids) == len(set(floor_ids)) == 24, "trainer tower floor selector drift")
    require("SetCurrentMapLayout(LAYOUT_TRAINER_TOWER_ROOF);" in tower,
            "trainer tower roof selector drift")
    require("SetCurrentMapLayout(sFloorLayouts[sTrainerTowerState->floorIdx][gSpecialVar_Result]);"
            in tower, "trainer tower dynamic floor selector drift")
    # Source-grounded branch disposition: FireRed's reader predicate is a stub,
    # so SetUpTrainerTowerDataStruct chooses its local table. Do not mistake
    # the dormant e-Reader validation for an active setup-time guarantee.
    reader = sources["src/cereader_tool.c"]
    reader_header = sources["include/cereader_tool.h"]
    tower_constants = sources["include/constants/trainer_tower.h"]
    local_sets = sources["src/trainer_tower_sets.c"]
    require(re.search(r"bool32 ReadTrainerTowerAndValidate\(void\)\s*\{\s*"
                      r"// Stubbed out\. Populated in Emerald\s*return FALSE;\s*\}",
                      reader) is not None, "FireRed e-Reader stub drift")
    require("if (ReadTrainerTowerAndValidate() == TRUE)\n"
            "        CEReaderTool_LoadTrainerTower(&sTrainerTowerState->data);"
            in tower, "Trainer Tower branch selector drift")
    require("if (numFloors < 1 || numFloors > MAX_TRAINER_TOWER_FLOORS)"
            in reader and "if (floor->challengeType > CHALLENGE_TYPE_KNOCKOUT)"
            in reader and "if (!ValidateTrainerTowerData(ttdata))" in reader,
            "dormant reader validation contract drift")
    require("#define MAX_TRAINER_TOWER_FLOORS 8" in tower_constants
            and "#define CHALLENGE_TYPE_KNOCKOUT   2" in tower_constants
            and "#define CHALLENGE_TYPE_MIXED      3" in tower_constants,
            "Trainer Tower bounds constants drift")
    require("struct EReaderTrainerTowerSet" in reader_header
            and "struct TrainerTowerFloor floors[MAX_TRAINER_TOWER_FLOORS];"
            in reader_header, "Trainer Tower data shape drift")
    require(".numFloors = MAX_TRAINER_TOWER_FLOORS," in local_sets,
            "built-in tower floor count drift")
    modes = re.findall(r"\[CHALLENGE_TYPE_(SINGLE|DOUBLE|KNOCKOUT|MIXED)\]\s*=\s*"
                       r"\{([^{}]*)\}", local_sets)
    require(len(modes) == 4 and len({mode for mode, _ in modes}) == 4,
            "built-in Trainer Tower challenge mode drift")
    local_mode_counts = {
        mode: len(re.findall(r"&sTrainerTowerFloor_[A-Za-z0-9_]+", body))
        for mode, body in modes
    }
    require(all(count == 8 for count in local_mode_counts.values()),
            "built-in Trainer Tower row count drift")
    require("u32 challengeType = gSaveBlock1Ptr->towerChallengeId;" in tower
            and "floors_p = gTrainerTowerFloors[challengeType];" in tower,
            "saved challenge ID to local pointer table drift")
    require("if (gSaveBlock1Ptr->towerChallengeId >= NUM_TOWER_CHALLENGE_TYPES)"
            in tower and "gSaveBlock1Ptr->towerChallengeId = 0;" in tower,
            "challenge-start normalization drift")
    # The dispatcher constructs tower data before calling any selected
    # function, including StartTrainerTowerChallenge. Therefore its saved-ID
    # normalization is too late to guard this invocation's setup lookup.
    require("void CallTrainerTowerFunc(void)\n{\n"
            "    SetUpTrainerTowerDataStruct();\n"
            "    sTrainerTowerFunctions[gSpecialVar_0x8004]();\n"
            "    FreeTrainerTowerDataStruct();" in tower,
            "Trainer Tower dispatch-before-setup order drift")
    require("[TRAINER_TOWER_FUNC_START_CHALLENGE]        = StartTrainerTowerChallenge,"
            in tower, "Trainer Tower start dispatcher slot drift")
    require("void PrintTrainerTowerRecords(void)\n{" in tower
            and "    SetUpTrainerTowerDataStruct();" in
            tower.split("void PrintTrainerTowerRecords(void)\n{", 1)[1],
            "Trainer Tower records setup call drift")
    # Recording snapshots the backup variable after it is written. Playback
    # can also populate normal save vars from quest-log flag/var records.
    require(quest.index("    BackUpMapLayout();") <
            quest.index("    SetGameStateAtScene(sCurrentSceneNum);"),
            "quest-log backup/snapshot ordering drift")
    require("VarSet(VAR_QLBAK_MAP_LAYOUT, gSaveBlock1Ptr->mapLayoutId);"
            in quest and
            "CpuCopy16(gSaveBlock1Ptr->vars, questLog->vars, sizeof(gSaveBlock1Ptr->vars));"
            in quest, "quest-log backup snapshot drift")
    require("case QL_PLAYBACK_STATE_RUNNING:" in get_var_ptr
            and "ptr = QuestLogGetFlagOrVarPtr(FALSE, idx);" in get_var_ptr
            and "gSaveBlock1Ptr->vars[idx - VARS_START] = *ptr;" in get_var_ptr,
            "quest-log playback variable replay drift")
    require("void *QuestLogGetFlagOrVarPtr(bool8 isFlag, u16 idx)" in quest
            and "sFlagOrVarRecords[sFlagOrVarPlayhead].idx == idx" in quest,
            "quest-log replay record lookup drift")

    # Authored Trainer Tower map-header IDs are consecutive table positions.
    # This establishes the arithmetic for normal 1F..8F headers, not the
    # integrity of runtime floor data or the e-Reader challenge-type values.
    lobby_slot = layout_by_id["LAYOUT_TRAINER_TOWER_LOBBY"][0]
    authored_floor_slots = [
        layout_by_id[f"LAYOUT_TRAINER_TOWER_{n}F"][0] for n in range(1, 9)
    ]
    roof_slot = layout_by_id["LAYOUT_TRAINER_TOWER_ROOF"][0]
    require(authored_floor_slots == list(range(lobby_slot + 1, lobby_slot + 9)),
            "trainer tower authored floor ID arithmetic drift")
    require(roof_slot == lobby_slot + 9, "trainer tower roof slot drift")
    require("sTrainerTowerState->floorIdx = gMapHeader.mapLayoutId - LAYOUT_TRAINER_TOWER_1F;"
            in tower, "trainer tower floor index origin drift")
    require("gMapHeader.mapLayoutId - LAYOUT_TRAINER_TOWER_LOBBY > sTrainerTowerState->data.numFloors"
            in tower, "trainer tower roof branch drift")
    selected = [row["layout"] for row in script_sites] + floor_ids + ["LAYOUT_TRAINER_TOWER_ROOF"]
    require(len(selected) == len(set(selected)) == 29, "explicit alternate layout overlap/drift")
    dimensions = []
    for ident in selected:
        require(ident in layout_by_id, "unresolved alternate layout: " + ident)
        slot, width, height = layout_by_id[ident]
        require(width == height == 2, "alternate selector border dimension drift: " + ident)
        dimensions.append({"layout": ident, "table_slot_1_based": slot,
                           "border_width": width, "border_height": height})

    # Every authored script site passes a layout constant, not VAR_QLBAK_MAP_LAYOUT.
    # Verify each generated one-based table slot is below the variable range.
    literal_script_ids = [
        {"path": row["path"], "layout": row["layout"],
         "immediate_operand": layout_by_id[row["layout"]][0],
         "varget_result": layout_by_id[row["layout"]][0]}
        for row in script_sites
    ]
    require(all(0 < row["immediate_operand"] < vars_start
                for row in literal_script_ids),
            "script selector operand crosses into variable range")
    output = {
        "evidence_class": "PINNED_AUTHORED_LAYOUT_WRITERS_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "direct_save_layout_writers": {"src/overworld.c": 2, "src/quest_log.c": 2},
        "script_opcode": "0xA7",
        "script_selector_sites": script_sites,
        "literal_script_operand_identity": literal_script_ids,
        "literal_varget_threshold": vars_start,
        "quest_log_backup_var_id": 0x40AE,
        "quest_log_restore_is_dynamic": True,
        "trainer_tower_authored_header_floor_slots": [
            {"floor": n, "layout_table_slot_1_based": slot,
             "derived_floor_idx": slot - authored_floor_slots[0]}
            for n, slot in enumerate(authored_floor_slots, 1)
        ],
        "trainer_tower_lobby_slot": lobby_slot,
        "trainer_tower_roof_slot": roof_slot,
        "trainer_tower_active_setup_branch": "BUILT_IN_DATA_PINNED_STUB_FALSE",
        "trainer_tower_ereader_validation_present_but_not_invoked_by_setup": True,
        "trainer_tower_reader_validator": {
            "floor_count_min": 1, "floor_count_max": 8,
            "challenge_type_max": 2,
        },
        "trainer_tower_built_in_modes": local_mode_counts,
        "trainer_tower_built_in_floor_count": 8,
        "trainer_tower_challenge_start_normalizes_saved_id": True,
        "trainer_tower_setup_saved_id_locally_checked": False,
        "trainer_tower_start_dispatch_setup_precedes_id_normalization": True,
        "trainer_tower_records_board_direct_setup": True,
        "quest_log_backup_var_snapshot_after_write": True,
        "quest_log_playback_may_replay_variable_records": True,
        "trainer_tower_floor_layouts": len(floor_ids),
        "trainer_tower_roof_layouts": 1,
        "explicit_alternate_layouts": dimensions,
        "zero_border_layout_count": len(zero),
        "zero_border_explicit_alternate_selectors": sorted(set(selected) & zero),
        "unresolved": [
            "The four authored script layout constants are literal VarGet identity operands, not variable references.",
            "Quest-log backup 0x40AE is a variable and its restored nonzero value lacks a local range check.",
            "Built-in setup precedes even the START_CHALLENGE dispatcher call; saved challenge-ID normalization cannot guard that initial lookup.",
            "Authored floor IDs map to 0..7; corrupted saved IDs, replayed quest-log vars, compiled ABI and runtime integrity remain unproven.",
            "No exhaustive dataflow, save integrity, runtime reachability, or linked ROM proof.",
            "Source selector census is not independent whole-file semantic approval.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PINNED_LAYOUT_WRITERS_PASS script_sites=4 tower_layouts=25 alternate_2x2=29")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")

if __name__ == "__main__":
    main()
