#!/usr/bin/env python3
"""R47 no-silent-omissions gate for full three-original-ROM content intake.

The baseline represents verified read-only inventories of the actual user-
supplied Emerald, TRE English 3.06, and Heart & Soul 2.0.6 ROMs. It is NOT
a native gameplay result. Treat all counted NPCs, warps and event triggers as
required original source inventory, never as expendable demo extras.

Pass the private R41 original three-ROM JSON via --inventory; check exact
original per-source counts, SHA-256, zero slots and event classes. A future
R47 runtime coverage manifest should be checked against this immutable baseline
before any native original NPC/script coverage milestone is advertised.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

BASELINE={
    "emerald":{
        "sha256":"a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af",
        "bytes":16777216, "populated_maps":518, "map_slots":518, "null_map_slots":0,
        "objects":2941, "warps":1313, "coord_events":375,
        "bg_events":720, "script_maps":518, "connections":148,
    },
    "rocket":{
        "sha256":"5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca",
        "bytes":33554432, "populated_maps":1778, "map_slots":1778, "null_map_slots":0,
        "objects":9410, "warps":4399, "coord_events":1378,
        "bg_events":2923, "script_maps":1778, "connections":567,
    },
    "heart_soul":{
        "sha256":"cdfb9e1f83f72c05cb47af40fdf5635567b1973bcb759e070ad0971f67a49191",
        "bytes":33554432, "populated_maps":560, "map_slots":1495, "null_map_slots":935,
        "objects":4738, "warps":1434, "coord_events":587,
        "bg_events":1054, "script_maps":560, "connections":219,
    }
}
COVERAGE_CLASSES=(
    "maps","npc_object_placements","npc_graphics","npc_movement",
    "script_roots","script_bytecode","dialogue_text","text_encoding",
    "trainer_parties","trainer_events","wild_encounters","pokemons",
    "moves","abilities","items","item_events","music","sfx",
    "tilesets","palettes","metatile_attributes","collision",
    "warps","connections","coord_events","background_events",
    "quest_flags","quest_variables","quest_specials","native_engine_callbacks",
    "party_storage","bag","battle_engine","flash_save",
)


class IncompleteThreeRomIntegration(ValueError):
    pass


def validate_original_inventory(report:dict)->dict:
    if (not isinstance(report,dict) or
        "sources" not in report or not isinstance(report["sources"],dict)):
        raise IncompleteThreeRomIntegration("No original three-ROM source report")
    sources=report["sources"]
    if set(sources)!=set(BASELINE):
        raise IncompleteThreeRomIntegration("Required original source worlds missing/replaced")
    totals={k:0 for k in ("populated_maps","objects","warps","coord_events",
                           "bg_events","script_maps","connections")}
    for name,expected in BASELINE.items():
        record=sources[name]
        counts=record.get("event_counts")
        if not isinstance(counts,dict):
            raise IncompleteThreeRomIntegration(f"{name}: original NPC/script event counts absent")
        actual={
            "sha256":record.get("rom_sha256"),
            "bytes":record.get("original_bytes"),
            "populated_maps":record.get("structurally_valid_populated_maps"),
            "map_slots":record.get("original_numeric_map_slots"),
            "null_map_slots":record.get("original_zero_pointer_slots_preserved"),
            **{key:counts.get(key) for key in totals if key!="populated_maps"},
        }
        if actual!=expected:
            missing={key:{"original":val,"supplied":actual.get(key)}
                     for key,val in expected.items() if actual.get(key)!=val}
            raise IncompleteThreeRomIntegration(f"{name} source inventory was reduced or altered: {missing}")
        for key in totals:
            totals[key]+=actual[key]
    return {
        "phase":"R47_ACTUAL_ORIGINAL_WHOLE_GAME_CONTENT_INTAKE_BASELINE",
        "required_sources":list(BASELINE),
        "original_counts_by_source":BASELINE,
        "totals":totals,
        "full_integrated_gameplay_verified":False,
        "actual_foreign_NPC_dialogue_executed":False,
        "foreign_script_event_executed":False,
        "inter_world_original_engine_navigation_verified":False,
        "original_trainer_battles_integration_verified":False,
        "three_source_flash_persistence_verified":False,
        "source_class_coverage_not_yet_demonstrated":list(COVERAGE_CLASSES),
        "rule":"No map-only, offline, homebrew viewer or synthetic NPC substitution can satisfy original-engine acceptance.",
    }


def validate_progress_report(progress:dict,original:dict)->None:
    """Guard source retention, not execution claims; runtime proof is separate."""
    if not isinstance(progress,dict) or set(progress)!=set(BASELINE):
        raise IncompleteThreeRomIntegration("Per-source content coverage missing")
    for source,required in BASELINE.items():
        entry=progress[source]
        if not isinstance(entry,dict):
            raise IncompleteThreeRomIntegration(f"{source}: malformed content coverage")
        for key in ("objects","warps","coord_events","bg_events","script_maps",
                    "populated_maps"):
            present=entry.get(key)
            if type(present) is not int or present!=required[key]:
                raise IncompleteThreeRomIntegration(
                    f"{source}: expected all {required[key]} original {key} retained, got {present!r}")
        for cls in COVERAGE_CLASSES:
            # None indicates not yet assessed, not permission to omit data.
            if cls not in entry:
                raise IncompleteThreeRomIntegration(
                    f"{source}: {cls} lacks an explicit preserved/unsupported/unassessed status")
            if entry[cls] not in ("preserved", "unsupported_retained", "unassessed"):
                raise IncompleteThreeRomIntegration(
                    f"{source}: {cls} was silently dropped or marked executable without original native proof")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory",type=Path,required=True)
    parser.add_argument("--coverage",type=Path,default=None)
    parser.add_argument("--out",type=Path,default=None)
    args=parser.parse_args(argv)
    inventory=json.loads(args.inventory.read_text(encoding="utf-8"))
    result=validate_original_inventory(inventory)
    if args.coverage is not None:
        validate_progress_report(
            json.loads(args.coverage.read_text(encoding="utf-8")),result)
        result["per_source_coverage_accounted_for"]=True
    else:
        result["per_source_coverage_accounted_for"]=False
    if args.out is not None:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",
                            encoding="utf-8")
    print(json.dumps({"status":"PASS_R47_ORIGINAL_THREE_GAME_NPC_SCRIPT_AND_EVENT_INVENTORY",
                      "totals":result["totals"],
                      "all_gameplay_verified":False},sort_keys=True))


if __name__=="__main__":
    main()
