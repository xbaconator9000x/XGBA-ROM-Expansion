#!/usr/bin/env python3
"""Pinned Porymap Qt JSON writer durability boundary (source-only half).

Fail closed on source drift. This does not run the full editor, approve any file,
or establish a GUI save/reopen failure. The separate C++ witness executes the
real pinned OrderedJsonDoc serializer against Qt file devices.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS = {
    "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
    "src/editor.cpp": "34112f6355b13d9381de7188624c36e5efeba151",
    "src/core/map.cpp": "47b279919bd4afcc76b88f9eeecd459b3452989f",
    "include/lib/orderedjson.h": "cb5139d37d955f2469ebd2eaaf089668b82884fe",
    "src/lib/orderedjson.cpp": "4d3a460c652541371a01132116e508db8c4c872c",
}
FUNCTIONS = {
    "map_writer": ("src/project.cpp", "bool Project::saveMap(Map *map, bool skipLayout)"),
    "groups_writer": ("src/project.cpp", "bool Project::saveMapGroups()"),
    "global_writer": ("src/project.cpp", "bool Project::saveGlobalData()"),
    "editor_save": ("src/editor.cpp", "bool Editor::save(bool currentOnly)"),
    "clean": ("src/core/map.cpp", "void Map::setClean()"),
    "serializer": ("include/lib/orderedjson.h", "void dump(QFile *file)"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def extract(source: str, signature: str) -> str:
    start = source.find(signature)
    require(start >= 0, "missing function signature: " + signature)
    brace = source.find("{", start + len(signature))
    require(brace >= 0, "missing function opening brace: " + signature)
    depth = 1
    for pos in range(brace + 1, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:pos]
    raise ValueError("unterminated function: " + signature)


def ordered(body: str, tokens: list[str], name: str) -> None:
    previous = -1
    for token in tokens:
        found = body.find(token, previous + 1)
        require(found > previous, name + " missing/reordered " + token)
        previous = found


def contract(files: dict[str, str]) -> dict:
    parts = {key: extract(files[path], signature)
             for key, (path, signature) in FUNCTIONS.items()}
    m = parts["map_writer"]
    g = parts["groups_writer"]
    s = parts["serializer"]
    ordered(m, [
        'if (!mapFile.open(QIODevice::WriteOnly))',
        "jsonDoc.dump(&mapFile);",
        "mapFile.close();",
        "map->setClean();",
        "return true;",
    ], "map writer")
    ordered(g, [
        'if (!mapGroupsFile.open(QIODevice::WriteOnly))',
        "jsonDoc.dump(&mapGroupsFile);",
        "mapGroupsFile.close();",
        "return true;",
    ], "map-group writer")
    ordered(s, [
        "QTextStream fileStream(file);",
        "fileStream << m_obj->dump(&m_indent);",
        'fileStream << "\\n";',
    ], "serializer")
    require("return " not in s and "fileStream.status()" not in s,
            "serializer gained an error/result path: reassess")
    require("mapFile.error()" not in m and "mapFile.flush()" not in m,
            "map writer gained error/flush validation: reassess")
    require("mapGroupsFile.error()" not in g and "mapGroupsFile.flush()" not in g,
            "groups writer gained error/flush validation: reassess")
    require("m_hasUnsavedDataChanges = false;" in parts["clean"],
            "Map::setClean changed")
    require("if (!saveMapGroups()) success = false;" in parts["global_writer"],
            "global save propagation changed")
    require("success = this->project->saveMap(this->map);" in parts["editor_save"]
            and "if (!this->project->saveGlobalData())" in parts["editor_save"],
            "editor Save Current call chain changed")
    require("void dump(QFile *file)" in files["include/lib/orderedjson.h"],
            "writer return type changed")
    # The independent Qt harness tests the serializer's success/failure device
    # behaviour. These checks establish only the project-level result gap.
    return {
        "porymap_pin": PIN,
        "git_blobs": BLOBS,
        "source_functions_checked": sorted(parts),
        "map_writer_checks_open": True,
        "map_writer_checks_stream_or_close": False,
        "map_writer_clears_dirty_after_unchecked_dump": True,
        "mapgroups_writer_checks_stream_or_close": False,
        "serializer_return_type": "void",
        "editor_save_current_can_propagate_unchecked_success": True,
        "actual_gui_save_failure_observed": False,
        "independent_whole_file_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }


def negative_controls(files: dict[str, str]) -> list[str]:
    cases = [
        ("src/project.cpp", "jsonDoc.dump(&mapFile);",
         "if (!jsonDoc.dump(&mapFile)) return false;", "map checked dump"),
        ("src/project.cpp", "map->setClean();",
         "map->modify();", "dirty flag changed"),
        ("src/project.cpp", "jsonDoc.dump(&mapGroupsFile);",
         "if (!jsonDoc.dump(&mapGroupsFile)) return false;", "groups checked dump"),
        ("include/lib/orderedjson.h", "void dump(QFile *file)",
         "bool dump(QFile *file)", "serializer return type"),
        ("include/lib/orderedjson.h", "fileStream << m_obj->dump(&m_indent);",
         'fileStream << "{}";', "serializer payload"),
        ("src/project.cpp", "if (!saveMapGroups()) success = false;",
         "saveMapGroups();", "global save propagation"),
        ("src/editor.cpp", "if (!this->project->saveGlobalData())",
         "if (false)", "editor save propagation"),
        ("src/core/map.cpp", "m_hasUnsavedDataChanges = false;",
         "m_hasUnsavedDataChanges = true;", "map clean flag"),
    ]
    passed = []
    for path, before, after, label in cases:
        require(before in files[path], "negative control source missing: " + label)
        modified = dict(files)
        modified[path] = files[path].replace(before, after, 1)
        try:
            contract(modified)
        except ValueError:
            passed.append(label)
        else:
            raise ValueError("negative control escaped detection: " + label)
    return passed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.porymap.resolve()

    def git(*command: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *command],
                                       text=True).strip()

    require(git("rev-parse", "HEAD") == PIN, "wrong Porymap revision")
    files = {}
    for path, expected in BLOBS.items():
        require(git("hash-object", path) == expected, "blob mismatch: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    result = contract(files)
    result["negative_controls"] = negative_controls(files)
    result["negative_control_count"] = len(result["negative_controls"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("Pinned Porymap writer source contract PASS;",
          result["negative_control_count"], "negative controls")


if __name__ == "__main__":
    main()
