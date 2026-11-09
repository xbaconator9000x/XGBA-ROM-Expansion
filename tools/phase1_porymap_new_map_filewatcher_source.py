#!/usr/bin/env python3
"""Phase 1 source-only Porymap new-map file-watcher lifecycle closure.
This is NOT GUI runtime evidence, rollback, or an independent approval.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS = {
    "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
    "src/editor.cpp": "34112f6355b13d9381de7188624c36e5efeba151",
    "src/mainwindow.cpp": "08ce1a7a599ef825967717b69626984cdc6d772b",
}
CHECKS = {
    ("src/project.cpp", "bool Project::watchFile(const QString &filename)"): (
        "if (!porymapConfig.monitorFiles)", "new QFileSystemWatcher(this)",
        "&QFileSystemWatcher::fileChanged", "&Project::recordFileChange",
        "this->fileWatcher->addPath(filepath)", "QFileInfo::exists(filepath)",
        "this->failedFileWatchPaths.insert(filepath);",
    ),
    ("src/project.cpp", "void Project::ignoreWatchedFileTemporarily(const QString &filepath)"): (
        "this->modifiedFileTimestamps.insert(filepath, QDateTime::currentMSecsSinceEpoch() + 5000);",
    ),
    ("src/project.cpp", "void Project::recordFileChange(const QString &filepath)"): (
        "!this->fileWatcher->files().contains(filepath) && QFileInfo::exists(filepath)",
        "this->fileWatcher->addPath(filepath);",
        "if (this->modifiedFiles.contains(filepath))",
        "if (this->modifiedFileTimestamps.contains(filepath))",
        "QDateTime::currentMSecsSinceEpoch() < this->modifiedFileTimestamps[filepath]",
        "this->modifiedFiles.insert(filepath);", "emit fileChanged(filepath);",
    ),
    ("src/mainwindow.cpp", "void MainWindow::showFileWatcherWarning()"): (
        "if (!porymapConfig.monitorFiles || !isProjectOpen())",
        "QGuiApplication::applicationState() != Qt::ApplicationActive",
        "QStringList modifiedFiles(project->modifiedFiles.constBegin(),  project->modifiedFiles.constEnd());",
        "project->modifiedFiles.clear();",
        "if (this->fileWatcherWarning)",
        "new QuestionMessage(\"\", this)",
        "&QuestionMessage::accepted, this, &MainWindow::on_action_Reload_Project_triggered",
    ),
    ("src/editor.cpp", "bool Editor::setMap(QString map_name)"): (
        "this->project->watchFile(map->getJsonFilepath());",
    ),
    ("src/mainwindow.cpp", "void MainWindow::onNewMapCreated(Map *newMap, const QString &groupName)"): (
        "userSetMap(newMap->name());",
    ),
}
def need(ok, message):
    if not ok:
        raise ValueError(message)
def body(source, signature):
    need(source.count(signature) == 1, "missing/duplicate signature " + signature)
    pos = source.index("{", source.index(signature) + len(signature))
    depth = 0
    for i in range(pos, len(source)):
        depth += (source[i] == "{") - (source[i] == "}")
        if depth == 0:
            return source[source.index(signature):i + 1]
    raise ValueError("unterminated original function " + signature)
def check(sources):
    for (path, signature), anchors in CHECKS.items():
        fragment = body(sources[path], signature)
        for anchor in anchors:
            need(fragment.count(anchor) == 1, "scoped source drift: " + signature + " / " + anchor)
    warning = body(sources["src/mainwindow.cpp"], "void MainWindow::showFileWatcherWarning()")
    need(warning.index("project->modifiedFiles.clear();") <
         warning.index("if (this->fileWatcherWarning)"),
         "pending file list no longer cleared before existing warning check")
    change = body(sources["src/project.cpp"], "void Project::recordFileChange(const QString &filepath)")
    need(change.index("this->fileWatcher->addPath(filepath);") <
         change.index("if (this->modifiedFileTimestamps.contains(filepath))") <
         change.index("emit fileChanged(filepath);"),
         "re-arm/suppression/signal ordering drift")
    watcher = body(sources["src/project.cpp"], "bool Project::watchFile(const QString &filename)")
    need(watcher.index("QFileInfo::exists(filepath)") <
         watcher.index("this->failedFileWatchPaths.insert(filepath);"),
         "watch failure recording changed")
    return True
def negatives(sources):
    count = 0
    for (path, signature), anchors in CHECKS.items():
        original = sources[path]
        fragment = body(original, signature)
        for anchor in anchors:
            changed = dict(sources)
            changed[path] = original.replace(fragment, fragment.replace(anchor, "PHASE1_NEGATIVE", 1), 1)
            need(changed[path] != original, "ineffective mutation")
            try:
                check(changed)
            except ValueError:
                count += 1
            else:
                raise AssertionError("source mutation escaped: " + signature + " / " + anchor)
    need(count == sum(map(len, CHECKS.values())), "negative count mismatch")
    return count
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porymap", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(a.porymap), *args], text=True).strip()
    need(git("rev-parse", "HEAD") == PIN, "pinned Porymap HEAD drift")
    for path, blob in BLOBS.items():
        need(git("hash-object", path) == blob, "pinned source blob drift " + path)
    sources = {path: (a.porymap / path).read_text() for path in BLOBS}
    check(sources)
    count = negatives(sources)
    result = {
        "evidence_class": "PINNED_PORYMAP_FILE_WATCHER_SOURCE_ONLY",
        "pin": PIN, "blobs": BLOBS,
        "partial_function_sha256": {path + ":" + sig: hashlib.sha256(
            body(sources[path], sig).encode()).hexdigest() for path, sig in CHECKS},
        "scoped_function_count": len(CHECKS),
        "source_mutations_rejected": count,
        "pending_changes_cleared_before_active_warning_guard": True,
        "new_map_watch_attempt_may_precede_disk_creation": True,
        "file_watcher_runtime_executed": False,
        "lost_notification_reproduced": False,
        "new_map_GUI_executed": False,
        "whole_file_approved": False,
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("PORYMAP_FILE_WATCHER_SOURCE_PASS negatives=%d gate=FAIL_INCOMPLETE approvals=0" % count)
if __name__ == "__main__":
    main()
