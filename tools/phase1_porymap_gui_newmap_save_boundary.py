#!/usr/bin/env python3
"""Pinned Porymap GUI new-map/save source closure; never a GUI runtime claim."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS = {
    "src/mainwindow.cpp": "08ce1a7a599ef825967717b69626984cdc6d772b",
    "src/ui/newmapdialog.cpp": "c8a028025bf1a9aabb8fd96cccf3d0a76214bb0e",
    "src/editor.cpp": "34112f6355b13d9381de7188624c36e5efeba151",
    "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
    "src/core/map.cpp": "47b279919bd4afcc76b88f9eeecd459b3452989f",
}
# Each anchor is scoped to an exact original function, never a file-wide grep.
CHECKS = {
    ("src/mainwindow.cpp", "void MainWindow::openNewMapDialog()"): (
        "new NewMapDialog(this->editor->project, this);",
        "dialog->open();",
    ),
    ("src/mainwindow.cpp", "void MainWindow::onNewMapCreated(Map *newMap, const QString &groupName)"): (
        "this->mapGroupModel->insertMapItem(newMap->name(), groupName);",
        "userSetMap(newMap->name());",
    ),
    ("src/mainwindow.cpp", "void MainWindow::on_action_Save_Project_triggered()"): ("save(false);",),
    ("src/mainwindow.cpp", "void MainWindow::on_action_Save_triggered()"): ("save(true);",),
    ("src/mainwindow.cpp", "bool MainWindow::save(bool currentOnly)"): (
        "this->editor->saveCurrent() : this->editor->saveAll()",
        'RecentErrorMessage::show(QStringLiteral("Failed to save some project changes."), this);',
    ),
    ("src/mainwindow.cpp", "bool MainWindow::userSetMap(const QString &mapName)"): (
        "if (!setMap(mapName)) {",
        "recordMapNavigation(prevItem);",
    ),
    ("src/ui/newmapdialog.cpp", "void NewMapDialog::accept()"): (
        "saveSettings();",
        "this->project->createNewMap(this->project->newMapSettings, this->mapToCopy);",
        "if (!map) {",
        "QDialog::accept();",
    ),
    ("src/editor.cpp", "bool Editor::setMap(QString map_name)"): (
        "project->loadMap(map_name);",
        "this->project->watchFile(map->getJsonFilepath());",
    ),
    ("src/editor.cpp", "bool Editor::save(bool currentOnly)"): (
        "this->project->saveMap(this->map);",
        "this->project->saveGlobalData()",
        "this->project->saveAll();",
    ),
    ("src/project.cpp", "Map *Project::createNewMap(const Project::NewMapSettings &settings, const Map* toDuplicate)"): (
        "map->setIsPersistedToFile(false);",
        "this->maps.insert(map->name(), map);",
        "emit mapCreated(map, settings.group);",
    ),
    ("src/project.cpp", "bool Project::saveMap(Map *map, bool skipLayout)"): (
        "if (!map->isPersistedToFile()) {",
        'saveTextFile(fullPath + "/scripts" + this->getScriptFileExtension(projectConfig.usePoryScript), text);',
        'appendTextFile(root + "/" + projectConfig.getFilePath(ProjectFilePath::data_event_scripts), text);',
        "jsonDoc.dump(&mapFile);",
        "map->setClean();",
    ),
    ("src/core/map.cpp", "void Map::setClean()"): (
        "m_hasUnsavedDataChanges = false;",
        "m_isPersistedToFile = true;",
    ),
}
GLOBAL = (
    ("src/mainwindow.cpp", "connect(ui->action_NewMap, &QAction::triggered, this, &MainWindow::openNewMapDialog);"),
    ("src/mainwindow.cpp", "connect(project, &Project::mapCreated, this, &MainWindow::onNewMapCreated);"),
)

def need(ok, msg):
    if not ok:
        raise ValueError(msg)

def body(source, signature):
    need(source.count(signature) == 1, "missing/duplicate signature " + signature)
    start = source.index(signature)
    begin = source.index("{", start + len(signature))
    depth = 0
    for i in range(begin, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise ValueError("unclosed function " + signature)

def check(sources):
    for (path, signature), anchors in CHECKS.items():
        fragment = body(sources[path], signature)
        for anchor in anchors:
            need(fragment.count(anchor) == 1, "function boundary drift: " + signature + " :: " + anchor)
    for path, anchor in GLOBAL:
        need(sources[path].count(anchor) == 1, "GUI signal boundary drift: " + anchor)
    accept = body(sources["src/ui/newmapdialog.cpp"], "void NewMapDialog::accept()")
    created = body(sources["src/project.cpp"],
        "Map *Project::createNewMap(const Project::NewMapSettings &settings, const Map* toDuplicate)")
    loaded = body(sources["src/editor.cpp"], "bool Editor::setMap(QString map_name)")
    for name, fragment in (("dialog accept", accept), ("map creation", created), ("map selection", loaded)):
        need("saveMap(" not in fragment and "saveAll(" not in fragment,
             name + " unexpectedly persists a new map")
    save = body(sources["src/project.cpp"], "bool Project::saveMap(Map *map, bool skipLayout)")
    need(save.index("jsonDoc.dump(&mapFile);") < save.index("map->setClean();"),
         "serializer/clean ordering drift")
    need(save.index("map->setClean();") < save.index("if (!skipLayout && !saveLayout("),
         "layout/clean ordering drift")
    return True

def negatives(sources):
    rejected = 0
    for (path, signature), anchors in CHECKS.items():
        original = sources[path]
        fragment = body(original, signature)
        for anchor in anchors:
            need(anchor in fragment, "ineffective scoped mutation")
            mutated = dict(sources)
            mutated[path] = original.replace(fragment, fragment.replace(anchor, "PHASE1_NEGATIVE", 1), 1)
            need(mutated[path] != original, "ineffective source mutation")
            try:
                check(mutated)
            except ValueError:
                rejected += 1
            else:
                raise AssertionError("source mutation escaped: " + anchor)
    for path, anchor in GLOBAL:
        mutated = dict(sources)
        mutated[path] = sources[path].replace(anchor, "PHASE1_NEGATIVE", 1)
        try:
            check(mutated)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError("signal mutation escaped: " + anchor)
    expected = sum(len(v) for v in CHECKS.values()) + len(GLOBAL)
    need(rejected == expected, "negative count drift")
    return rejected

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    def git(*argv):
        return subprocess.check_output(["git", "-C", str(args.porymap), *argv], text=True).strip()
    need(git("rev-parse", "HEAD") == PIN, "pinned Porymap revision changed")
    for path, blob in BLOBS.items():
        need(git("hash-object", path) == blob, "pinned blob changed: " + path)
    sources = {p: (args.porymap / p).read_text() for p in BLOBS}
    check(sources)
    count = negatives(sources)
    record = {
        "evidence_class": "PINNED_GUI_CREATION_SAVE_SOURCE_CLOSURE_ONLY",
        "pin": PIN, "blobs": BLOBS,
        "function_sha256": {f"{p}:{sig}": hashlib.sha256(body(sources[p], sig).encode()).hexdigest()
                            for p, sig in CHECKS},
        "source_mutations_rejected": count,
        "creation_signal_updates_UI_before_explicit_save": True,
        "dialog_accept_directly_saves": False,
        "editor_save_current_calls_map_and_global": True,
        "native_Qt_Project_new_map_retries_executed_separately": True,
        "MainWindow_GUI_runtime_executed": False,
        "file_watcher_recovery_executed": False,
        "whole_file_approved": False,
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(f"PINNED_GUI_NEW_MAP_SOURCE_PASS negatives={count} gate=FAIL_INCOMPLETE approvals=0")

if __name__ == "__main__":
    main()
