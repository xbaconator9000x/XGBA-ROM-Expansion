#!/usr/bin/env python3
"""Phase 1 source-only: Porymap new-map collateral retry and persisted-flag closure.

The exact original pinned source is inspected; this does not execute a GUI,
prove an actual failed new-map save, or change any upstream implementation.
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
    "src/core/map.cpp": "47b279919bd4afcc76b88f9eeecd459b3452989f",
}
PROJECT_ANCHORS = (
    "if (!map->isPersistedToFile()) {",
    'saveTextFile(fullPath + "/scripts" + this->getScriptFileExtension(projectConfig.usePoryScript), text);',
    'saveTextFile(fullPath + "/text" + this->getScriptFileExtension(projectConfig.usePoryScript), "\\n");',
    "appendTextFile(root + \"/\" + projectConfig.getFilePath(ProjectFilePath::data_event_scripts), text);",
    "if (!mapFile.open(QIODevice::WriteOnly)) {",
    "jsonDoc.dump(&mapFile);",
    "mapFile.close();",
    "map->setClean();",
    "if (!skipLayout && !saveLayout(map->layout()))",
)
MAP_ANCHORS = (
    "m_editHistory->setClean();",
    "m_hasUnsavedDataChanges = false;",
    "m_isPersistedToFile = true;",
    "!m_isPersistedToFile",
)
HEADER_ANCHORS = (
    "bool isPersistedToFile() const { return m_isPersistedToFile; }",
    "void setIsPersistedToFile(bool persistedToFile) { m_isPersistedToFile = persistedToFile; }",
)

def need(value, message):
    if not value:
        raise ValueError(message)

def body(source, signature):
    start = source.find(signature)
    need(start >= 0 and source.find(signature, start + 1) == -1,
         "missing or duplicate function: " + signature)
    begin = source.find("{", start + len(signature))
    need(begin >= 0, "missing function body: " + signature)
    depth = 0
    for pos in range(begin, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start:pos+1]
    raise ValueError("unterminated function: " + signature)

def check(project, mapping, header):
    save = body(project, "bool Project::saveMap(Map *map, bool skipLayout)")
    clean = body(mapping, "void Map::setClean()")
    dirty = body(mapping, "bool Map::hasUnsavedChanges() const")
    for anchor in PROJECT_ANCHORS:
        need(save.count(anchor) == 1, "new-map save drift: " + anchor)
    for anchor in MAP_ANCHORS[:3]:
        need(clean.count(anchor) == 1, "setClean drift: " + anchor)
    need(dirty.count(MAP_ANCHORS[3]) == 1, "dirty-state persisted test drift")
    for anchor in HEADER_ANCHORS:
        need(header.count(anchor) == 1, "map header persisted API drift")
    # The exact original call expressions must be unguarded statements,
    # not checked return values. No regex across arbitrary callers.
    need(len(re.findall(r"(?m)^\s+saveTextFile\(", save)) == 2,
         "new-map text write return handling changed")
    need(len(re.findall(r"(?m)^\s+appendTextFile\(", save)) == 1,
         "new-map append return handling changed")
    offsets = [save.index(x) for x in PROJECT_ANCHORS]
    need(offsets == sorted(offsets), "new-map collateral/clean/layout order changed")
    need(clean.index("m_isPersistedToFile = true;") >
         clean.index("m_hasUnsavedDataChanges = false;"),
         "persisted flag order changed")
    # The retry skips collateral because setClean sets persisted=true.
    # This is conditional source reasoning, NOT an executed retry.
    need("m_isPersistedToFile = true;" in clean and
         "if (!map->isPersistedToFile()) {" in save,
         "new-map retry branch contract drift")
    return save, clean, dirty

def negatives(project, mapping, header):
    count = 0
    for anchor in PROJECT_ANCHORS:
        scoped = body(project, "bool Project::saveMap(Map *map, bool skipLayout)")
        need(anchor in scoped, "missing scoped project mutation anchor")
        changed = project.replace(scoped, scoped.replace(anchor, "PHASE1_MUTATED", 1), 1)
        need(changed != project, "missing project mutation anchor")
        try:
            check(changed, mapping, header)
        except ValueError:
            count += 1
        else:
            raise AssertionError("project source mutation escaped: " + anchor)
    for anchor in MAP_ANCHORS:
        signature = ("void Map::setClean()" if anchor != "!m_isPersistedToFile"
                     else "bool Map::hasUnsavedChanges() const")
        scoped = body(mapping, signature)
        need(anchor in scoped, "missing scoped map mutation anchor")
        changed = mapping.replace(scoped, scoped.replace(anchor, "PHASE1_MUTATED", 1), 1)
        need(changed != mapping, "missing map mutation anchor")
        try:
            check(project, changed, header)
        except ValueError:
            count += 1
        else:
            raise AssertionError("map source mutation escaped: " + anchor)
    for anchor in HEADER_ANCHORS:
        changed = header.replace(anchor, "PHASE1_MUTATED", 1)
        need(changed != header, "missing header mutation anchor")
        try:
            check(project, mapping, changed)
        except ValueError:
            count += 1
        else:
            raise AssertionError("map header mutation escaped: " + anchor)
    need(count == 15, "source negative control count drift")
    return count

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--porymap", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(a.porymap), *args],
                                       text=True).strip()
    need(git("rev-parse", "HEAD") == PIN, "pinned Porymap revision changed")
    for path, sha in BLOBS.items():
        need(git("hash-object", path) == sha, "upstream blob changed: " + path)
    project = (a.porymap / "src/project.cpp").read_text()
    mapping = (a.porymap / "src/core/map.cpp").read_text()
    header = (a.porymap / "include/core/map.h").read_text()
    save, clean, dirty = check(project, mapping, header)
    rejected = negatives(project, mapping, header)
    record = {
        "evidence_class": "PINNED_SOURCE_DEPENDENCY_CLOSURE_ONLY",
        "porymap_pin": PIN, "source_blobs": BLOBS,
        "source_sha256": {
            "saveMap_function": hashlib.sha256(save.encode()).hexdigest(),
            "setClean_function": hashlib.sha256(clean.encode()).hexdigest(),
            "hasUnsavedChanges_function": hashlib.sha256(dirty.encode()).hexdigest(),
        },
        "source_negative_controls_rejected": rejected,
        "collateral_returns_ignored": True,
        "setClean_marks_persisted": True,
        "retry_collateral_branch_conditionally_skipped": True,
        "layout_failure_follows_setClean": True,
        "native_qt_new_map_failure_executed": False,
        "gui_new_map_reopen_tested": False,
        "whole_file_review": False,
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0,
        "unresolved": [
            "Actual Qt Project new-map creation with injected failed collateral open/write",
            "Whether caller can retry with new Map object or resets persisted flag",
            "Global event_scripts.s append rollback/idempotency and file-watcher effects",
            "Original GUI new-map lifecycle and fresh-process reopen",
            "Independent complete-file dispositions and licensing review",
        ],
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print("PINNED_NEW_MAP_RETRY_SOURCE_PASS negatives=%d gate=FAIL_INCOMPLETE approvals=0" % rejected)

if __name__ == "__main__":
    main()
