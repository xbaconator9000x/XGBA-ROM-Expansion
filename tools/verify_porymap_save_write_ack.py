#!/usr/bin/env python3
"""Exact-pinned Porymap save-acknowledgement source witness, not a Qt runtime test."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PINS = {
    "porymap": "26b919d7ff4b54152de010abd5bf344af2ebe116",
    "pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
}
FILES = {
    ("porymap", "src/project.cpp"): (
        "d43b0949303433111d4478ad76117c2b3445dd13",
        [
            "bool Project::saveMap(Map *map, bool skipLayout)",
            "if (!mapFile.open(QIODevice::WriteOnly))",
            "jsonDoc.dump(&mapFile);",
            "mapFile.close();",
            "map->setClean();",
            "saveTextFile(fullPath + \"/scripts\"",
            "saveTextFile(fullPath + \"/text\"",
            "appendTextFile(root + \"/\"",
            "bool Project::saveTextFile(",
            "bool Project::appendTextFile(",
            "file.write(text.toUtf8());",
            "bool Project::saveMapGroups()",
            "jsonDoc.dump(&mapGroupsFile);",
            "bool Project::saveGlobalData()",
            "this->hasUnsavedDataChanges = false;",
        ],
    ),
    ("porymap", "include/lib/orderedjson.h"): (
        "cb5139d37d955f2469ebd2eaaf089668b82884fe",
        [
            "class JsonDoc",
            "void dump(QFile *file)",
            "QTextStream fileStream(file);",
            "fileStream << m_obj->dump(&m_indent);",
        ],
    ),
    ("porymap", "src/core/map.cpp"): (
        "47b279919bd4afcc76b88f9eeecd459b3452989f",
        [
            "void Map::setClean()",
            "m_editHistory->setClean();",
            "m_hasUnsavedDataChanges = false;",
            "m_isPersistedToFile = true;",
        ],
    ),
    ("porymap", "src/editor.cpp"): (
        "34112f6355b13d9381de7188624c36e5efeba151",
        [
            "bool Editor::save(bool currentOnly)",
            "success = this->project->saveMap(this->map);",
            "if (!this->project->saveGlobalData())",
        ],
    ),
    ("porymap", "src/core/mapconnection.cpp"): (
        "d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4",
        [
            "MapConnection* MapConnection::findMirror()",
            "void MapConnection::markMapEdited()",
            "m_parentMap->modify();",
        ],
    ),
    ("pokefirered", "data/event_scripts.s"): (
        "88d75946a7300ccf952f4a36c283966c6aebf5c0",
        ['.include "data/maps/ViridianForest/scripts.inc"'],
    ),
    ("pokefirered", "map_data_rules.mk"): (
        "b32b85a91d9460642345ca983c37d165e820741f",
        ["$(MAPS_OUTDIR)/connections.inc", "$(MAPS_DIR)/map_groups.json"],
    ),
}


def git(checkout, *args):
    return subprocess.check_output(["git", "-C", str(checkout), *args]).strip()


def read_source(root, repo, path, expected):
    checkout = root / repo
    if git(checkout, "rev-parse", "HEAD").decode() != PINS[repo]:
        raise ValueError("Pinned commit mismatch: " + repo)
    if git(checkout, "rev-parse", "HEAD:" + path).decode() != expected:
        raise ValueError("Pinned tree/blob mismatch: " + path)
    data = subprocess.check_output(["git", "-C", str(checkout), "cat-file", "blob", expected])
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if actual != expected:
        raise ValueError("Git blob hash mismatch: " + path)
    return data.decode("utf-8", "surrogateescape")


def method(text, start, end):
    a = text.index(start)
    b = text.index(end, a + len(start))
    return text[a:b]


def validate(source):
    count = 0
    for key, (_, anchors) in FILES.items():
        for anchor in anchors:
            if anchor not in source[key]:
                raise ValueError(f"Missing guarded anchor {key}: {anchor}")
            count += 1
    project = source[("porymap", "src/project.cpp")]
    save_map = method(project, "bool Project::saveMap(Map *map, bool skipLayout)", "bool Project::saveLayout(")
    if not (save_map.index("if (!mapFile.open(QIODevice::WriteOnly))") <
            save_map.index("jsonDoc.dump(&mapFile);") <
            save_map.index("mapFile.close();") <
            save_map.index("map->setClean();")):
        raise ValueError("Map write/clean order changed")
    for name in ("saveTextFile(fullPath + \"/scripts\"", "saveTextFile(fullPath + \"/text\"",
                 "appendTextFile(root + \"/\""):
        line = next((s.strip() for s in save_map.splitlines() if name in s), "")
        if not line.startswith(name):
            raise ValueError("Collateral save result now handled: " + name)
    for name, next_name in (("bool Project::saveTextFile(", "bool Project::appendTextFile("),
                            ("bool Project::appendTextFile(", "bool Project::readWildMonData(")):
        body = method(project, name, next_name)
        if not re.search(r"file\.write\(text\.toUtf8\(\)\);\s*return true;", body):
            raise ValueError("Text writer error propagation changed: " + name)
    map_groups = method(project, "bool Project::saveMapGroups()", "bool Project::saveRegionMapSections()")
    if not re.search(r"jsonDoc\.dump\(&mapGroupsFile\);\s*mapGroupsFile\.close\(\);\s*return true;", map_groups):
        raise ValueError("Map-group write result path changed")
    editor = method(source[("porymap", "src/editor.cpp")], "bool Editor::save(bool currentOnly)", "void Editor::setProject(")
    if editor.index("success = this->project->saveMap(this->map);") >= editor.index("if (!this->project->saveGlobalData())"):
        raise ValueError("Save Current global save order changed")
    json_header = source[("porymap", "include/lib/orderedjson.h")]
    if not re.search(r"void dump\(QFile \*file\)\s*\{\s*QTextStream fileStream\(file\);", json_header):
        raise ValueError("JSON dump signature changed")
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("audit-output/porymap_save_write_ack.json"))
    args = parser.parse_args()
    source = {key: read_source(args.source_root, *key, expected) for key, (expected, _) in FILES.items()}
    anchors = validate(source)
    mutations = 0
    for key, (_, items) in FILES.items():
        for anchor in items:
            changed = dict(source)
            changed[key] = changed[key].replace(anchor, anchor[:1] + "MUTATED_" + anchor[1:])
            try:
                validate(changed)
            except ValueError:
                mutations += 1
            else:
                raise ValueError("Mutation escaped source witness: " + anchor)
    result = {
        "schema": "xgba-porymap-save-write-ack-source-v1",
        "pinned_revisions": PINS,
        "source_blobs": [
            {"repo": key[0], "path": key[1], "git_blob_sha1": FILES[key][0],
             "source_sha256": hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()}
            for key, text in sorted(source.items())
        ],
        "guarded_source_anchors": anchors,
        "negative_mutation_controls": mutations,
        "source_level_findings": [
            "map.json JSON stream/close status not checked before setClean",
            "new-map scripts/text/event_scripts collateral save return values ignored",
            "map_groups.json JSON stream status not checked before returning success",
        ],
        "not_proven": [
            "Qt fault-injection execution", "actual disk write failure", "FireRed build outcome",
            "independent whole-file semantic review", "independent approval",
        ],
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"files": len(FILES), "anchors": anchors, "mutations": mutations,
                      "approvals": 0, "gate": "FAIL_INCOMPLETE"}, sort_keys=True))


if __name__ == "__main__":
    main()
