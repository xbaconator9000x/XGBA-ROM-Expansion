#!/usr/bin/env python3
"""Pinned Porymap -> FireRed map-groups round-trip source witness.

Read-only. Structural source checks plus a JSON transformation model; this
does not execute Qt, mapjson, the assembler, or the emulator, and never
certifies a whole-file review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PORYMAP_PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
FIRERED_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "project": ("porymap", "src/project.cpp", "d43b0949303433111d4478ad76117c2b3445dd13"),
    "editor": ("porymap", "src/editor.cpp", "34112f6355b13d9381de7188624c36e5efeba151"),
    "config": ("porymap", "include/config.h", "539c5f3d416d22d847020cd324726b33725e5437"),
    "config_impl": ("porymap", "src/config.cpp", "9264f99bb18e0a725ef023f514c00df529d1d28d"),
    "generator": ("firered", "tools/mapjson/mapjson.cpp", "8d8ec4e4e6e1c011b06f00819abe40bad10d19d5"),
    "groups": ("firered", "data/maps/map_groups.json", "8c382f504d208286161903244772c93138cd7662"),
    "rules": ("firered", "map_data_rules.mk", "b32b85a91d9460642345ca983c37d165e820741f"),
    "mainwindow": ("porymap", "src/mainwindow.cpp", "08ce1a7a599ef825967717b69626984cdc6d772b"),
    "connection": ("porymap", "src/core/mapconnection.cpp", "d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4"),
    "map": ("porymap", "src/core/map.cpp", "47b279919bd4afcc76b88f9eeecd459b3452989f"),
    "editcommands": ("porymap", "src/core/editcommands.cpp", "684d98c7ea8b2c600a5fb8888831b95723e741f3"),
    "parseutil": ("porymap", "src/core/parseutil.cpp", "a1c3e69daed3f04d7ed64e1a34bd95db56137ae2"),
    "connection_h": ("porymap", "include/core/mapconnection.h", "40713d3a26157fce7a36465858e8273c78dc12f6"),
    "mapmacro": ("firered", "asm/macros/map.inc", "83ef472c926ce767c9133ab9bd6922280b38bb2d"),
    "fieldheader": ("firered", "include/global.fieldmap.h", "e2828ec0cb1439718e830fbef4366770b3b77b1c"),
}

# Exact source anchors, not approximate keyword counts. Any upstream change
# must be reviewed and re-pinned before the checker is updated.
CHECKS = {
    "default_false": ("config", "this->preserveMatchingOnlyData = false;"),
    "config_override": ("config_impl", 'key == "preserve_matching_only_data"'),
    "load_removes": ("project", 'mapGroupsObj.remove("connections_include_order");'),
    "load_condition": ("project", '// Chuck the "connections_include_order" field, this is only for matching.'),
    "load_retains_other_fields": ("project", "this->customMapGroupsData = mapGroupsObj;"),
    "save_appends_custom": ("project", "OrderedJson::append(&mapGroupsObj, this->customMapGroupsData);"),
    "save_global_calls_groups": ("project", "if (!saveMapGroups()) success = false;"),
    "current_saves_map": ("editor", "success = this->project->saveMap(this->map);"),
    "current_saves_global": ("editor", "if (!this->project->saveGlobalData())"),
    "generator_optional_order": ("generator", 'groups_data["connections_include_order"].array_items()'),
    "generator_conditional_sort": ("generator", "if (connections_include_order.size() > 0)"),
    "generator_sort": ("generator", "sort(map_names.begin(), map_names.end()"),
    "generator_emits_includes": ("generator", '"/connections.inc'),
    "build_consumes_groups": ("rules", '$(MAPS_DIR)/map_groups.json'),
    "project_emits_map_loaded": ("project", "emit mapLoaded(map);"),
    "window_hooks_project": ("mainwindow", "connect(project, &Project::mapLoaded, this, &MainWindow::onMapLoaded);"),
    "window_hooks_map": ("mainwindow", "connect(map, &Map::modified, [this, map] { markMapEdited(map); });"),
    "window_marks_target_dirty": ("mainwindow", "map->setHasUnsavedDataChanges(true);"),
    "mirror_lazy_load": ("connection", "return project ? project->loadMap(mapName) : nullptr;"),
    "mirror_resolve_target": ("connection", "MapConnection* MapConnection::findMirror() {"),
    "mirror_offset_propagates": ("connection", "connection->setOffset(-offset, false);"),
    "mirror_marks_target": ("connection", "m_parentMap->modify();"),
    "map_emits_modified": ("map", "emit modified();"),
    "map_dirty_check": ("map", "m_hasUnsavedDataChanges || !m_isPersistedToFile"),
    "save_all_maps": ("project", "for (auto map : this->maps) {"),
    "save_map_cleans": ("project", "map->setClean();"),
    "mirror_default": ("config_impl", "this->mirrorConnectingMaps = true;"),
    "mirror_command_snapshot": ("editcommands", "MapConnectionMove::MapConnectionMove("),
    "parse_numeric_offset": ("parseutil", "case QJsonValue::Double: return value.toInt();"),
    "connection_signed_offset": ("connection_h", "int m_offset;"),
    "mirror_negation_compare": ("connection", "a->m_offset == -b->m_offset"),
    "mirror_negation_create": ("connection", "oppositeDirection(m_direction), -m_offset"),
    "native_32bit_offset": ("mapmacro", ".4byte " + chr(92) + "offset"),
    "native_offset_unsigned": ("fieldheader", "/*0x04*/ u32 offset;"),
}

def check_contract(sources: dict[str, str]) -> None:
    for name, (key, needle) in CHECKS.items():
        if needle not in sources[key]:
            raise ValueError(f"Fail closed: source anchor missing: {name}")
    p = sources["project"]
    e = sources["editor"]
    g = sources["generator"]
    w = sources["mainwindow"]
    conn = sources["connection"]
    # Source-order checks exclude false positives from unrelated functions.
    if "if (!projectConfig.preserveMatchingOnlyData) {" not in p[p.index(CHECKS["load_condition"][1]):p.index('mapGroupsObj.remove("connections_include_order");')]:
        raise ValueError("Map-groups conditional removal guard changed")
    if not (p.index('mapGroupsObj.remove("connections_include_order");')
            < p.index("this->customMapGroupsData = mapGroupsObj;")):
        raise ValueError("Map-groups load order changed")
    if not (p.index("OrderedJson::append(&mapGroupsObj, this->customMapGroupsData);")
            < p.index("if (!saveMapGroups()) success = false;")):
        raise ValueError("Map-groups writer/global-save order changed")
    if not (e.index("success = this->project->saveMap(this->map);")
            < e.index("if (!this->project->saveGlobalData())")):
        raise ValueError("Editor current-save order changed")
    if not (w.index("connect(project, &Project::mapLoaded, this, &MainWindow::onMapLoaded);")
            < w.index("void MainWindow::onMapLoaded(Map *map)")):
        raise ValueError("MainWindow map-loaded signal registration changed")
    if "auto map = targetMap();" not in conn[conn.index("MapConnection* MapConnection::findMirror() {"):conn.index("MapConnection * MapConnection::createMirror() {")]:
        raise ValueError("Mirror resolution no longer lazily loads target")
    edits = sources["editcommands"]
    if "this->mirrored = porymapConfig.mirrorConnectingMaps;" not in edits[edits.index("MapConnectionMove::MapConnectionMove("):edits.index("void MapConnectionMove::redo()")]:
        raise ValueError("Mirrored edit command preference snapshot changed")
    if not (conn.index("void MapConnection::setOffset(int offset, bool mirror)")
            < conn.index("connection->setOffset(-offset, false);")
            < conn.index("markMapEdited();", conn.index("void MapConnection::setOffset(int offset, bool mirror)"))):
        raise ValueError("Mirrored target offset/dirty propagation changed")
    if not (p.index("bool Project::saveAll()")
            < p.index("for (auto map : this->maps) {", p.index("bool Project::saveAll()"))
            < p.index("bool Project::saveMap(")):
        raise ValueError("Save All loaded-map iteration changed")
    if not (g.index("if (connections_include_order.size() > 0)")
            < g.index("sort(map_names.begin(), map_names.end()")
            < g.index('"/connections.inc')):
        raise ValueError("Generator connection order path changed")

def run_git(path: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", type=Path, required=True)
    parser.add_argument("--firered", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("audit-output/porymap_mapgroups_roundtrip.json"))
    args = parser.parse_args()
    roots = {"porymap": args.porymap, "firered": args.firered}
    for name, pin in (("porymap", PORYMAP_PIN), ("firered", FIRERED_PIN)):
        if run_git(roots[name], "rev-parse", "HEAD") != pin:
            raise ValueError(f"Wrong pinned {name} revision")
    sources = {}
    for key, (owner, rel, sha) in BLOBS.items():
        actual = run_git(roots[owner], "hash-object", rel)
        if actual != sha:
            raise ValueError(f"Wrong pinned Git blob for {owner}/{rel}: {actual}")
        sources[key] = (roots[owner] / rel).read_text(encoding="utf-8")
    check_contract(sources)

    negative_controls = []
    for name, (key, needle) in CHECKS.items():
        changed = dict(sources)
        changed[key] = changed[key].replace(needle, "", 1)
        try:
            check_contract(changed)
        except ValueError:
            negative_controls.append(name)
        else:
            raise AssertionError(f"Mutation did not fail closed: {name}")

    authored = json.loads(sources["groups"])
    order = authored["connections_include_order"]
    group_names = authored["group_order"]
    maps = [name for group in group_names for name in authored[group]]
    if (len(group_names), len(maps), len(set(maps)), len(order), len(set(order))) != (43, 425, 425, 63, 63):
        raise ValueError("Pinned authored cardinality changed")
    if set(order) - set(maps):
        raise ValueError("Order contains unknown map names")
    ordered_set = set(order)
    natural_active = [name for name in maps if name in ordered_set]
    if natural_active != order:
        raise ValueError("Active connection order not invariant after metadata removal")
    first_active = next(i for i, name in enumerate(maps) if name in ordered_set)
    last_active = max(i for i, name in enumerate(maps) if name in ordered_set)

    # Explicitly a model of the guarded QJsonObject::remove + custom-field
    # append path, not an executed Porymap Qt round trip.
    model = dict(authored)
    model.pop("connections_include_order")
    if "connections_include_order" in model:
        raise AssertionError("Metadata was not removed")
    if model["group_order"] != group_names or any(model[g] != authored[g] for g in group_names):
        raise AssertionError("Group identity changed in the metadata-only model")

    result = {
        "status": "SOURCE_AND_JSON_MODEL_ONLY_NOT_APPROVED",
        "pins": {"porymap": PORYMAP_PIN, "firered": FIRERED_PIN},
        "blobs": {k: v[2] for k, v in BLOBS.items()},
        "source_anchors_checked": len(CHECKS),
        "fail_closed_mutations": len(negative_controls),
        "negative_controls": negative_controls,
        "group_count": len(group_names),
        "map_count": len(maps),
        "ordered_connection_maps": len(order),
        "omitted_from_order": len(maps) - len(order),
        "first_ordered_map_group_position_zero_based": first_active,
        "last_ordered_map_group_position_zero_based": last_active,
        "metadata_lost_by_default_model": True,
        "mirror_target_dirty_normal_gui_source_chain": True,
        "save_current_is_not_two_map_transaction": True,
        "signed_int_min_reciprocal_negation_unrepresentable": True,
        "signed_int_min_compiled_or_qt_tested": False,
        "qt_mirror_save_executed": False,
        "relative_order_of_63_ordered_maps_preserved_in_pinned_data": True,
        "compiled_equivalence_claimed": False,
        "qt_roundtrip_claimed": False,
        "independent_approvals": 0,
        "phase1": "FAIL_INCOMPLETE",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
