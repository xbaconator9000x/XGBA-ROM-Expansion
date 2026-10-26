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
    "src/quest_log.c": "0a2f76f2c4019fa0938d5044da73fcea1b2b069c",
    "src/scrcmd.c": "97b695ee2f6fca80a3b78f52f6a444f696fe5814",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
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

    script_sites = []
    for path in sorted((root / "data/maps").rglob("scripts.inc")):
        relative = path.relative_to(root).as_posix()
        matches = re.findall(r"(?m)^\s*setmaplayoutindex\s+(LAYOUT_[A-Z0-9_]+)\s*$",
                             path.read_text(encoding="utf-8"))
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
    selected = [row["layout"] for row in script_sites] + floor_ids + ["LAYOUT_TRAINER_TOWER_ROOF"]
    require(len(selected) == len(set(selected)) == 29, "explicit alternate layout overlap/drift")
    dimensions = []
    for ident in selected:
        require(ident in layout_by_id, "unresolved alternate layout: " + ident)
        slot, width, height = layout_by_id[ident]
        require(width == height == 2, "alternate selector border dimension drift: " + ident)
        dimensions.append({"layout": ident, "table_slot_1_based": slot,
                           "border_width": width, "border_height": height})

    output = {
        "evidence_class": "PINNED_AUTHORED_LAYOUT_WRITERS_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "direct_save_layout_writers": {"src/overworld.c": 2, "src/quest_log.c": 2},
        "script_opcode": "0xA7",
        "script_selector_sites": script_sites,
        "trainer_tower_floor_layouts": len(floor_ids),
        "trainer_tower_roof_layouts": 1,
        "explicit_alternate_layouts": dimensions,
        "zero_border_layout_count": len(zero),
        "zero_border_explicit_alternate_selectors": sorted(set(selected) & zero),
        "unresolved": [
            "VarGet script operand and quest-log restored nonzero IDs lack a local range check.",
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
