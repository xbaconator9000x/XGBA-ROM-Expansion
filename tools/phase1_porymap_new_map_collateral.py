#!/usr/bin/env python3
"""Phase 1: source-pinned Porymap new-map collateral-write and dirty-state closure."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS = {
    "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
    "include/project.h": "50d3307cf618f4cd5e9603bdbe3e0ea8d9b5e354",
}

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def extract(src, name, return_type="bool"):
    needle = return_type + " Project::" + name + "("
    require(src.count(needle) == 1, "missing/duplicate pinned function " + name)
    start = src.index(needle)
    end = src.find("\n}\n", start)
    require(end > start, "unterminated pinned function " + name)
    return src[start:end+2]

def check(project, header):
    save = extract(project, "saveMap")
    script = 'saveTextFile(fullPath + "/scripts" + this->getScriptFileExtension(projectConfig.usePoryScript), text);'
    text = 'saveTextFile(fullPath + "/text" + this->getScriptFileExtension(projectConfig.usePoryScript), "\\n");'
    event = 'appendTextFile(root + "/" + projectConfig.getFilePath(ProjectFilePath::data_event_scripts), text);'
    anchors = (
        "if (!map->isPersistedToFile())",
        "if (!QDir::root().mkpath(fullPath))",
        script, text, event,
        "QFile mapFile(mapFilepath);",
        "jsonDoc.dump(&mapFile);",
        "mapFile.close();",
        "map->setClean();",
        "if (!skipLayout && !saveLayout(map->layout()))",
        "return true;",
    )
    for a in anchors:
        require(save.count(a) == 1, "missing/duplicate new-map save anchor: " + a)
    positions = [save.index(a) for a in anchors]
    require(positions == sorted(positions), "new-map collateral/map/layout order changed")
    require("if (projectConfig.createMapTextFileEnabled)" in save,
            "optional new-map text branch missing")
    require('text = QString("\\n\\t.include \\"%1/scripts.inc\\"\\n").arg(folderPath);' in save,
            "new-map event-script include generation changed")
    require('text += QString("\\t.include \\"%1/text.inc\\"\\n").arg(folderPath);' in save,
            "optional event-script text include changed")
    require("if (!" + script not in save and "if (!" + event not in save,
            "new-map collateral return now checked; re-review")
    for name in ("saveTextFile", "appendTextFile"):
        b = extract(project, name)
        require(b.count("file.write(text.toUtf8());") == 1 and b.count("return true;") == 1,
                "text writer path changed: " + name)
        require("file.flush()" not in b and "file.error()" not in b,
                "text writer now checks post-write errors: " + name)
    extension = extract(project, "getScriptFileExtension", "QString")
    require('return ".pory";' in extension and 'return ".inc";' in extension,
            "Poryscript/assembly extension selection changed")
    require("bool saveMap(Map *map, bool skipLayout = false);" in header
            and "bool saveTextFile(const QString &path, const QString &text);" in header
            and "bool appendTextFile(const QString &path, const QString &text);" in header,
            "Project public/private declarations changed")
    return True

def source_controls(project, header):
    changes = [
        (project.replace("if (!map->isPersistedToFile())", "if (map->isPersistedToFile())", 1), header),
        (project.replace('saveTextFile(fullPath + "/scripts"', 'if (!saveTextFile(fullPath + "/scripts"', 1), header),
        (project.replace('saveTextFile(fullPath + "/text"', 'if (!saveTextFile(fullPath + "/text"', 1), header),
        (project.replace('appendTextFile(root + "/"', 'if (!appendTextFile(root + "/"', 1), header),
        (project.replace("map->setClean();", "map->setDirty();", 1), header),
        (project.replace("if (!skipLayout && !saveLayout(map->layout()))", "if (skipLayout && saveLayout(map->layout()))", 1), header),
        (project.replace("file.write(text.toUtf8());", "file.flush();", 1), header),
        (project.replace('return ".pory";', 'return ".inc";', 1), header),
        (project, header.replace("bool appendTextFile(const QString &path, const QString &text);",
                                 "void appendTextFile(const QString &path, const QString &text);", 1)),
    ]
    for i, (p,h) in enumerate(changes):
        require((p,h) != (project,header), "ineffective source mutation")
        try:
            check(p,h)
        except ValueError:
            continue
        raise ValueError("new-map source mutation escaped " + str(i))
    return len(changes)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--porymap", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a=p.parse_args()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(a.porymap), *args], text=True).strip()
    require(git("rev-parse","HEAD")==PIN,"wrong pinned Porymap commit")
    src={}
    for path,blob in BLOBS.items():
        require(git("hash-object",path)==blob,"pinned blob changed "+path)
        src[path]=(a.porymap/path).read_text()
    project,header=(src[p] for p in BLOBS)
    check(project,header)
    n=source_controls(project,header)
    d={
        "class":"PINNED_PORYMAP_NEW_MAP_COLLATERAL_WRITE_AND_CLEAN_ORDER",
        "source_pin":PIN,"source_git_blobs":BLOBS,
        "source_sha256":{p:hashlib.sha256(s.encode()).hexdigest() for p,s in src.items()},
        "new_map_script_creation_return_ignored":True,
        "new_map_optional_text_creation_return_ignored":True,
        "new_map_event_scripts_append_return_ignored":True,
        "new_map_json_write_after_collateral_writes":True,
        "map_set_clean_before_optional_layout_save_result":True,
        "poryscript_new_map_file_extension":".pory",
        "event_scripts_include_extension":".inc",
        "poryscript_generated_include_dependency_verified":False,
        "runtime_collateral_write_failure_executed":False,
        "actual_editor_new_map_failure_executed":False,
        "source_mutations_rejected":n,
        "new_complete_file_dispositions":0,
        "independent_approvals":0,"gate":"FAIL_INCOMPLETE",
    }
    def validate(x):
        require(x["source_mutations_rejected"]==9,"source controls changed")
        require(x["new_map_script_creation_return_ignored"] is True and
                x["new_map_event_scripts_append_return_ignored"] is True,
                "collateral return evidence changed")
        require(x["map_set_clean_before_optional_layout_save_result"] is True,
                "layout clean ordering evidence changed")
        require(x["runtime_collateral_write_failure_executed"] is False and
                x["actual_editor_new_map_failure_executed"] is False,
                "runtime evidence overclaimed")
        require(x["poryscript_generated_include_dependency_verified"] is False,
                "generated include dependency overclaimed")
        require(x["gate"]=="FAIL_INCOMPLETE" and x["independent_approvals"]==0,
                "false approval/gate")
    validate(d)
    changes=[
        {"source_mutations_rejected":8},
        {"new_map_script_creation_return_ignored":False},
        {"new_map_event_scripts_append_return_ignored":False},
        {"map_set_clean_before_optional_layout_save_result":False},
        {"runtime_collateral_write_failure_executed":True},
        {"actual_editor_new_map_failure_executed":True},
        {"poryscript_generated_include_dependency_verified":True},
        {"gate":"PASS"},
        {"independent_approvals":1},
    ]
    for i,change in enumerate(changes):
        try:
            validate({**d,**change})
        except ValueError:
            continue
        raise ValueError("new-map evidence mutation escaped "+str(i))
    d["evidence_mutations_rejected"]=len(changes)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(d,sort_keys=True,indent=2)+"\n")
    print(json.dumps(d,sort_keys=True))

if __name__=="__main__":
    main()
