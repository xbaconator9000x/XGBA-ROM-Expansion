#!/usr/bin/env python3
"""Phase 1: source-pinned Porymap JSON writer error-propagation closure.

This checker does NOT change upstream, test six native write failures, or
assert a universal Qt durability defect. It identifies six source-level
unchecked dump/close sites, one of which has separate native GUI evidence.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS = {
    "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
    "src/editor.cpp": "34112f6355b13d9381de7188624c36e5efeba151",
    "src/mainwindow.cpp": "08ce1a7a599ef825967717b69626984cdc6d772b",
}
WRITERS = {
    "saveMapLayouts": "layoutsFile",
    "saveMapGroups": "mapGroupsFile",
    "saveRegionMapSections": "file",
    "saveWildMonData": "wildEncountersFile",
    "saveHealLocations": "file",
    "saveMap": "mapFile",
}

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def function(source, name):
    matches = list(re.finditer(r"(?m)^bool Project::" + re.escape(name) + r"\s*\(", source))
    require(len(matches) == 1, "missing/duplicate pinned Project writer " + name)
    start = matches[0].start()
    end = source.find("\n}\n", start)
    require(end > start, "unterminated Project writer " + name)
    return source[start:end+2]

def check_writer(source, name, handle):
    body = function(source, name)
    dump = "jsonDoc.dump(&" + handle + ");"
    close = handle + ".close();"
    require(body.count(dump) == 1 and body.count(close) == 1,
            "missing/duplicate pinned JSON dump/close in " + name)
    require(body.index(dump) < body.index(close) < body.rfind("return true;"),
            "unexpected writer result order in " + name)
    require(re.search(r"\bQFile\s+" + re.escape(handle) + r"\s*\(", body) is not None,
            "JSON writer no longer owns a QFile: " + name)
    require("if (!" + handle + ".open(QIODevice::WriteOnly))" in body,
            "missing initial QFile open-error guard: " + name)
    tail = body[body.index(dump):]
    require(handle + ".error()" not in tail and
            handle + ".flush()" not in tail and
            "commit()" not in tail,
            "writer now checks/persists its dump; re-review: " + name)
    if name == "saveMap":
        require(tail.index(close) < tail.index("map->setClean()") < tail.rfind("return true;"),
                "map clean timing changed")
    return {
        "function": name,
        "qfile_handle": handle,
        "initial_open_failure_guard": True,
        "dump_then_close_without_error_gate": True,
        "returns_success_without_dump_error_gate": True,
        "clears_map_dirty_after_dump": name == "saveMap",
        "runtime_failed_save_observed_separately": name == "saveMap",
    }

def check_closure(project, editor, mainwindow):
    writers = [check_writer(project, name, handle) for name, handle in WRITERS.items()]
    save_global = function(project, "saveGlobalData")
    for name in ("saveMapLayouts", "saveMapGroups", "saveRegionMapSections",
                 "saveHealLocations", "saveWildMonData"):
        require("if (!" + name + "()) success = false;" in save_global,
                "global writer propagation changed: " + name)
    save_all = function(project, "saveAll")
    require("if (!saveMap(map, true))" in save_all and
            "if (!saveGlobalData()) success = false;" in save_all,
            "saveAll failure propagation changed")
    require("success = this->project->saveMap(this->map);" in editor and
            "success = this->project->saveAll();" in editor and
            "return success;" in editor, "Editor save result propagation changed")
    require("bool success = currentOnly ? this->editor->saveCurrent() : this->editor->saveAll();" in mainwindow and
            "if (!success) {" in mainwindow and
            'RecentErrorMessage::show(QStringLiteral("Failed to save some project changes.")' in mainwindow,
            "MainWindow error reporting propagation changed")
    return writers

def source_controls(project, editor, mainwindow):
    changes = []
    for name, handle in WRITERS.items():
        body = function(project, name)
        target = "jsonDoc.dump(&" + handle + ");\n"
        require(target in body, "source mutation anchor absent: " + name)
        altered_body = body.replace(target,
                                    target + "    if (" + handle + ".error() != QFile::NoError) return false;\n", 1)
        altered = project.replace(body, altered_body, 1)
        require(altered != project, "ineffective source mutation: " + name)
        changes.append((altered, editor, mainwindow))
    changes += [
        (project.replace("if (!saveMap(map, true))", "if (saveMap(map, true))", 1),
         editor, mainwindow),
        (project, editor.replace("success = this->project->saveMap(this->map);",
                                 "success = true;", 1), mainwindow),
        (project, editor, mainwindow.replace("if (!success) {", "if (success) {", 1)),
    ]
    for index, (p, e, m) in enumerate(changes):
        require((p, e, m) != (project, editor, mainwindow),
                "ineffective source mutation " + str(index))
        try:
            check_closure(p, e, m)
        except ValueError:
            continue
        raise ValueError("source propagation mutation escaped: " + str(index))
    return len(changes)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.porymap
    def git(*argv):
        return subprocess.check_output(["git", "-C", str(root), *argv], text=True).strip()
    require(git("rev-parse", "HEAD") == PIN, "pinned Porymap revision mismatch")
    sources = {}
    for path, expected in BLOBS.items():
        require(git("hash-object", path) == expected, "pinned Porymap blob mismatch: " + path)
        sources[path] = (root / path).read_text()
    project = sources["src/project.cpp"]
    editor = sources["src/editor.cpp"]
    mainwindow = sources["src/mainwindow.cpp"]
    writers = check_closure(project, editor, mainwindow)
    mutations = source_controls(project, editor, mainwindow)
    evidence = {
        "class": "PINNED_PORYMAP_PROJECT_JSON_WRITER_RESULT_PROPAGATION",
        "porymap_commit": PIN, "source_git_blobs": BLOBS,
        "source_writers_without_post_dump_error_gate": writers,
        "source_writer_count": len(writers),
        "source_mutations_rejected": mutations,
        "distinct_native_gui_error_observed_for_saveMap_only": True,
        "other_five_writer_failures_executed": False,
        "upstream_porymap_patched": False,
        "recommended_reuse": "existing Qt QFile/QSaveFile and Project/Editor/MainWindow APIs; no custom serializer or editor",
        "atomic_replacement_and_file_watcher_semantics": "UNVERIFIED",
        "new_complete_file_reviews": 0, "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    def validate(d):
        require(d["source_writer_count"] == 6 and d["source_mutations_rejected"] == 9,
                "writer/negative-control evidence changed")
        require(d["phase1_gate"] == "FAIL_INCOMPLETE" and
                d["independent_approvals"] == 0, "false approval or gate")
        require(d["other_five_writer_failures_executed"] is False and
                d["upstream_porymap_patched"] is False, "runtime/patch overclaim")
    validate(evidence)
    negatives = (
        {"source_writer_count": 5},
        {"source_mutations_rejected": 8},
        {"phase1_gate": "PASS"},
        {"independent_approvals": 1},
        {"other_five_writer_failures_executed": True},
        {"upstream_porymap_patched": True},
    )
    for index, mutation in enumerate(negatives):
        try:
            validate({**evidence, **mutation})
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped: " + str(index))
    evidence["evidence_mutations_rejected"] = len(negatives)
    evidence["source_sha256"] = {
        path: hashlib.sha256(value.encode()).hexdigest() for path, value in sources.items()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()
