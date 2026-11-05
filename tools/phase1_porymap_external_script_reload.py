#!/usr/bin/env python3
"""Exercise narrow pinned Porymap script lookup, watcher, and launch boundaries."""
import argparse
import gzip
import hashlib
import io
import json
import shlex
import subprocess
import tarfile
import tempfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"

FILES = {
    "include/core/map.h": (
        "Map script cache, watcher, and filepath interface",
        ("QStringList getScriptLabels(Event::Group group = Event::Group::None);",
         "QString getScriptsFilepath() const;",
         "QPointer<QFileSystemWatcher> m_scriptFileWatcher;"),
    ),
    "src/core/map.cpp": (
        "Map script cache invalidation, filepath selection, and file watcher",
        ("void Map::invalidateScripts() {",
         "QStringList Map::getScriptLabels(Event::Group group) {",
         "QString Map::getScriptsFilepath() const {",
         "&QFileSystemWatcher::fileChanged, this, &Map::invalidateScripts"),
    ),
    "include/core/parseutil.h": (
        "Script label and line lookup interfaces",
        ("static int getScriptLineNumber(const QString &filePath, const QString &scriptLabel);",
         "static QStringList getGlobalScriptLabels(const QString &filePath, QString *error = nullptr);",
         "Returns 0 if a definition for scriptLabel cannot be found."),
    ),
    "src/core/parseutil.cpp": (
        "Disk reads, raw-script label parsing, line lookup, and shell-command splitting",
        ("const QRegularExpression ParseUtil::re_incScriptLabel(",
         "QString ParseUtil::readTextFile(const QString &path, QString *error)",
         "QStringList ParseUtil::getGlobalRawScriptLabels(QString text)",
         "int ParseUtil::getRawScriptLineNumber(QString text, const QString &scriptLabel)",
         "QStringList ParseUtil::splitShellCommand(QStringView command)"),
    ),
    "include/editor.h": (
        "Editor script-navigation and detached-process interfaces",
        ("bool openScriptInFile(const QString &scriptLabel, const QString &filepath) const;",
         "static bool startDetachedProcess(const QString &command,"),
    ),
    "src/editor.cpp": (
        "Editor disk line lookup and detached process startup",
        ("bool Editor::openScriptInFile(const QString &scriptLabel, const QString &filepath) const {",
         "bool Editor::startDetachedProcess(const QString &command, const QString &workingDirectory, qint64 *pid) {",
         "return process.startDetached(pid);"),
    ),
    "include/project.h": (
        "Project watcher, pending file changes, and reload interfaces",
        ("bool watchFile(const QString &filename);",
         "QSet<QString> modifiedFiles;",
         "void recordFileChange(const QString &filepath);"),
    ),
    "src/project.cpp": (
        "Project watcher re-arm and file-change notification source",
        ("bool Project::watchFile(const QString &filename) {",
         "void Project::recordFileChange(const QString &filepath) {",
         "this->fileWatcher->addPath(filepath);",
         "emit fileChanged(filepath);"),
    ),
    "include/mainwindow.h": (
        "MainWindow file-change warning state",
        ("void showFileWatcherWarning();",
         "QPointer<QuestionMessage> fileWatcherWarning"),
    ),
    "src/mainwindow.cpp": (
        "MainWindow external-change warning and project reload handoff",
        ("void MainWindow::showFileWatcherWarning() {",
         "project->modifiedFiles.clear();",
         "if (this->fileWatcherWarning)",
         "&MainWindow::on_action_Reload_Project_triggered"),
    ),
    "include/ui/message.h": (
        "Question dialog API used by the external-change warning",
        ("class QuestionMessage : public Message",
         "static int show(const QString &message, QWidget *parent);"),
    ),
    "src/ui/message.cpp": (
        "Question dialog execution behavior",
        ("QuestionMessage::QuestionMessage(const QString &message, QWidget *parent)",
         "return msgBox.exec();"),
    ),
}

PRIOR_DOSSIERS = {
    "docs/phase1-review-readiness/porymap-event-script-consumer-closure-20261105.md":
        "Prior dropdown-to-parser source path; reused context",
    "docs/phase1-review-readiness/porymap-new-map-filewatcher-20261029.md":
        "Prior Project/MainWindow watcher lifecycle source analysis; no duplicate GUI test",
    "docs/phase1-review-readiness/porymap-external-editor-preference-boundary-20261105.md":
        "Prior preference boundary; no preference-writer repetition",
    "docs/phase1-review-readiness/porymap-cross-file-transaction-rollback-20261105.md":
        "Prior persistence and transaction context; no transaction test repetition",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    require(result.returncode == 0, "git command failed: " + " ".join(args))
    return result.stdout.strip()


def pinned_file(root, path):
    data = (root / path).read_bytes()
    expected = git(root, "rev-parse", PIN + ":" + path)
    blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    require(blob == expected, "working-tree source differs from pinned blob: " + path)
    return {
        "repository": "porymap",
        "commit": PIN,
        "path": path,
        "git_blob": blob,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "lines": len(data.splitlines()),
    }, data.decode("utf-8", "surrogateescape")


def function_body(source, signature, occurrence=None):
    count = source.count(signature)
    if occurrence is None:
        require(count == 1, "missing or duplicate function: " + signature)
        occurrence = 0
    require(0 <= occurrence < count, "missing function occurrence: " + signature)
    start = -1
    offset = 0
    for _ in range(occurrence + 1):
        start = source.index(signature, offset)
        offset = start + len(signature)
    opening = source.index("{", start + len(signature))
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError("unterminated function: " + signature)


def verify_sources(sources):
    for path, (_, anchors) in FILES.items():
        for anchor in anchors:
            require(anchor in sources[path], "source contract changed: " + path + ": " + anchor)

    map_source = sources["src/core/map.cpp"]
    for signature in (
        "void Map::invalidateScripts()",
        "QStringList Map::getScriptLabels(Event::Group group)",
        "QString Map::getScriptsFilepath() const",
    ):
        function_body(map_source, signature)

    parser_source = sources["src/core/parseutil.cpp"]
    for signature in (
        "QString ParseUtil::readTextFile(const QString &path, QString *error)",
        "QStringList ParseUtil::getGlobalScriptLabels(const QString &filePath, QString *error)",
        "QStringList ParseUtil::getGlobalRawScriptLabels(QString text)",
        "int ParseUtil::getScriptLineNumber(const QString &filepath, const QString &scriptLabel)",
        "int ParseUtil::getRawScriptLineNumber(QString text, const QString &scriptLabel)",
        "QString ParseUtil::removeStringLiterals(QString text)",
        "QString ParseUtil::removeLineComments(QString text, const QString &commentSymbol)",
    ):
        function_body(parser_source, signature)
    split_signature = "QStringList ParseUtil::splitShellCommand(QStringView command)"
    require(parser_source.count(split_signature) == 2,
            "expected Qt-version split-command implementations")
    require("#if (QT_VERSION >= QT_VERSION_CHECK(5, 15, 0))" in parser_source
            and parser_source.index("#else", parser_source.index(split_signature))
                > parser_source.index(split_signature),
            "Qt split-command version guard changed")
    function_body(parser_source, split_signature, occurrence=0)

    editor_source = sources["src/editor.cpp"]
    function_body(
        editor_source,
        "bool Editor::openScriptInFile(const QString &scriptLabel, const QString &filepath) const",
    )
    function_body(
        editor_source,
        "bool Editor::startDetachedProcess(const QString &command, const QString &workingDirectory, qint64 *pid)",
    )


def source_negatives(sources):
    rejected = 0
    for path, (_, anchors) in FILES.items():
        anchor = anchors[0]
        changed = dict(sources)
        changed[path] = sources[path].replace(anchor, "PHASE1_SOURCE_MUTATION", 1)
        require(changed[path] != sources[path], "ineffective source mutation: " + path)
        try:
            verify_sources(changed)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + path)
    require(rejected == len(FILES), "source mutation count mismatch")
    return rejected


CPP_TEMPLATE = r'''#include <QCoreApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileDevice>
#include <QEventLoop>
#include <QFileInfo>
#include <QFileSystemWatcher>
#include <QPointer>
#include <QProcess>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QStringList>
#include <QTextStream>
#include <QThread>
#include <QTemporaryDir>
#include <iostream>

class ParseUtil {
public:
    static QString readTextFile(const QString &, QString * = nullptr);
    static QStringList getGlobalScriptLabels(const QString &, QString * = nullptr);
    static QStringList getGlobalRawScriptLabels(QString);
    static int getScriptLineNumber(const QString &, const QString &);
    static int getRawScriptLineNumber(QString, const QString &);
    static QString removeStringLiterals(QString);
    static QString removeLineComments(QString, const QString &);
    static QStringList splitShellCommand(QStringView);
    static QStringList getGlobalPoryScriptLabels(QString) { return {}; }
    static int getPoryScriptLineNumber(QString, const QString &) { return 0; }
    static const QRegularExpression re_incScriptLabel;
    static const QRegularExpression re_globalIncScriptLabel;
    static const QRegularExpression re_poryScriptLabel;
    static const QRegularExpression re_globalPoryScriptLabel;
    static const QRegularExpression re_poryRawSection;
};

@REGEX_DEFINITIONS@

@PARSEUTIL_FUNCTIONS@

enum class ProjectFilePath { data_map_folders };
class Project {
public:
    static QString getScriptFileExtension(bool usePoryScript) {
        return usePoryScript ? ".pory" : ".inc";
    }
};

struct TestConfig {
    QString root;
    bool usePoryScript = false;
    QString projectDir() const { return root; }
    QString getFilePath(ProjectFilePath) const { return "data/maps"; }
};
TestConfig projectConfig;

namespace Util {
static QString stripPrefix(const QString &value, const QString &) { return value; }
}
static void logWarn(const QString &) {}
static void logInfo(const QString &) {}

class Event {
public:
    enum class Group { None };
    QStringList getScripts() const { return {}; }
};

class Map : public QObject {
public:
    static bool m_fileWatchingEnabled;
    QString m_name;
    QString m_sharedScriptsMap;
    QStringList m_scriptLabels;
    bool m_isPersistedToFile = true;
    bool m_scriptsLoaded = false;
    bool m_loggedScriptsFileError = false;
    QPointer<QFileSystemWatcher> m_scriptFileWatcher;
    int scriptsModifiedCount = 0;
    void setName(const QString &name) { m_name = name; }
    QList<Event *> getEvents(Event::Group) const { return {}; }
    void scriptsModified() { ++scriptsModifiedCount; }
    QStringList getScriptLabels(Event::Group);
    QString getScriptsFilepath() const;
    void invalidateScripts();
};

bool Map::m_fileWatchingEnabled = true;
@MAP_FUNCTIONS@

class Editor {
public:
    static QString openedPath;
    static int openedLine;
    static void openInTextEditor(const QString &path, int line) {
        openedPath = path;
        openedLine = line;
    }
    bool openScriptInFile(const QString &, const QString &) const;
    static bool startDetachedProcess(const QString &, const QString &, qint64 *);
};
QString Editor::openedPath;
int Editor::openedLine = 0;
@EDITOR_FUNCTIONS@

static bool writeFile(const QString &path, const QByteArray &contents) {
    QFile file(path);
    return file.open(QIODevice::WriteOnly | QIODevice::Truncate)
        && file.write(contents) == contents.size();
}

static bool waitForInvalidation(QCoreApplication &app, Map &map, int previous) {
    QElapsedTimer timer;
    timer.start();
    while (map.scriptsModifiedCount == previous && timer.elapsed() < 5000) {
        app.processEvents(QEventLoop::AllEvents, 25);
        QThread::msleep(5);
    }
    return map.scriptsModifiedCount == previous + 1;
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QTemporaryDir temporary(QDir(QDir::tempPath()).filePath(
        "porymap-external-script-reload-XXXXXX"));
    if (!temporary.isValid())
        return 2;
    projectConfig.root = temporary.path();

    Map map;
    map.setName("TestMap");
    const QString scriptPath = map.getScriptsFilepath();
    if (!QDir().mkpath(QFileInfo(scriptPath).absolutePath())
        || !writeFile(scriptPath, "OldScript::\n"))
        return 3;

    Editor editor;
    const QStringList initialLabels = map.getScriptLabels(Event::Group::None);
    if (!initialLabels.contains("OldScript")
        || !map.m_scriptFileWatcher
        || !map.m_scriptFileWatcher->files().contains(scriptPath))
        return 4;

    const int initialInvalidations = map.scriptsModifiedCount;
    if (!writeFile(scriptPath, "; changed on disk\nNewScript::\n"))
        return 5;

    const QStringList cachedLabelsBeforeEvent = map.getScriptLabels(Event::Group::None);
    const bool staleCacheObserved = cachedLabelsBeforeEvent.contains("OldScript")
        && !cachedLabelsBeforeEvent.contains("NewScript");
    const bool freshLineResolved = editor.openScriptInFile("NewScript", scriptPath)
        && Editor::openedPath == scriptPath && Editor::openedLine == 2;
    const bool missingLabelRejected = !editor.openScriptInFile("OldScript", scriptPath);
    if (!staleCacheObserved || !freshLineResolved || !missingLabelRejected
        || !waitForInvalidation(app, map, initialInvalidations))
        return 6;

    const QStringList refreshedLabels = map.getScriptLabels(Event::Group::None);
    if (!refreshedLabels.contains("NewScript") || refreshedLabels.contains("OldScript")
        || !map.m_scriptFileWatcher
        || !map.m_scriptFileWatcher->files().contains(scriptPath))
        return 7;
    const int firstChangeInvalidations = map.scriptsModifiedCount;

    if (!writeFile(scriptPath, "; shifted\n; line\nNewScript::\n")
        || !editor.openScriptInFile("NewScript", scriptPath)
        || Editor::openedLine != 3)
        return 8;

    const QString helperPath = "/usr/bin/touch";
    const QString markerPath = QFileInfo(
        QDir(temporary.path()).filePath("launch-marker")).absoluteFilePath();
    if (!QFileInfo(helperPath).isExecutable())
        return 9;
    const QString command = QString("%1 %2").arg(helperPath, markerPath);
    qint64 pid = 0;
    const bool launchReturnedTrue = Editor::startDetachedProcess(command, temporary.path(), &pid);
    QElapsedTimer launchTimer;
    launchTimer.start();
    while (!QFileInfo::exists(markerPath) && launchTimer.elapsed() < 3000) {
        app.processEvents(QEventLoop::AllEvents, 25);
        QThread::msleep(5);
    }
    const bool helperMarkerObserved = QFileInfo::exists(markerPath);
    const bool missingProgramRejected = !Editor::startDetachedProcess(
        "/__phase1_missing_external_editor__/not-found", temporary.path(), nullptr);
    if (!launchReturnedTrue)
        return 11;
    if (pid <= 0)
        return 12;
    if (!helperMarkerObserved)
        return 13;
    if (!missingProgramRejected)
        return 14;

    std::cout << "{\"script_path\":\"" << scriptPath.toStdString()
              << "\",\"initial_label_cached\":true"
              << ",\"stale_labels_before_watcher_event\":" << (staleCacheObserved ? "true" : "false")
              << ",\"fresh_disk_line_lookup\":" << (freshLineResolved ? "true" : "false")
              << ",\"missing_label_rejected\":" << (missingLabelRejected ? "true" : "false")
              << ",\"map_watcher_invalidation\":" << firstChangeInvalidations
              << ",\"labels_refreshed_after_event\":true"
              << ",\"watch_reestablished_after_invalidation\":true"
              << ",\"shifted_line_lookup\":" << Editor::openedLine
              << ",\"helper_launch_returned_true\":true"
              << ",\"helper_pid_positive\":true"
              << ",\"helper_marker_observed\":" << (helperMarkerObserved ? "true" : "false")
              << ",\"missing_program_rejected\":" << (missingProgramRejected ? "true" : "false")
              << ",\"helper_exit_status_observed\":false}\n";
    return 0;
}
'''


def build_and_run(sources):
    map_source = sources["src/core/map.cpp"]
    parse_source = sources["src/core/parseutil.cpp"]
    editor_source = sources["src/editor.cpp"]
    signatures = {
        "parse": (
            (parse_source, "QString ParseUtil::readTextFile(const QString &path, QString *error)"),
            (parse_source, "QStringList ParseUtil::getGlobalScriptLabels(const QString &filePath, QString *error)"),
            (parse_source, "QStringList ParseUtil::getGlobalRawScriptLabels(QString text)"),
            (parse_source, "int ParseUtil::getScriptLineNumber(const QString &filepath, const QString &scriptLabel)"),
            (parse_source, "int ParseUtil::getRawScriptLineNumber(QString text, const QString &scriptLabel)"),
            (parse_source, "QString ParseUtil::removeStringLiterals(QString text)"),
            (parse_source, "QString ParseUtil::removeLineComments(QString text, const QString &commentSymbol)"),
        ),
        "map": (
            (map_source, "void Map::invalidateScripts()"),
            (map_source, "QStringList Map::getScriptLabels(Event::Group group)"),
            (map_source, "QString Map::getScriptsFilepath() const"),
        ),
        "editor": (
            (editor_source, "bool Editor::openScriptInFile(const QString &scriptLabel, const QString &filepath) const"),
            (editor_source, "bool Editor::startDetachedProcess(const QString &command, const QString &workingDirectory, qint64 *pid)"),
        ),
    }
    functions = {
        name: "\n\n".join(function_body(source, signature)
                         for source, signature in entries)
        for name, entries in signatures.items()
    }
    functions["parse"] += "\n\n" + function_body(
        parse_source, "QStringList ParseUtil::splitShellCommand(QStringView command)",
        occurrence=0,
    )
    regexes = []
    for name in (
        "re_incScriptLabel", "re_globalIncScriptLabel", "re_poryScriptLabel",
        "re_globalPoryScriptLabel", "re_poryRawSection",
    ):
        prefix = "const QRegularExpression ParseUtil::" + name + "("
        matches = [line for line in parse_source.splitlines() if line.startswith(prefix)]
        require(len(matches) == 1, "missing/duplicate pinned regex definition: " + name)
        regexes.append(matches[0])

    cpp = (CPP_TEMPLATE
           .replace("@REGEX_DEFINITIONS@", "\n".join(regexes))
           .replace("@PARSEUTIL_FUNCTIONS@", functions["parse"])
           .replace("@MAP_FUNCTIONS@", functions["map"])
           .replace("@EDITOR_FUNCTIONS@", functions["editor"]))
    with tempfile.TemporaryDirectory(prefix="phase1-porymap-external-script-") as directory:
        temp = Path(directory)
        source_path = temp / "native.cpp"
        binary_path = temp / "native"
        source_path.write_text(cpp)
        flags = subprocess.run(
            ["pkg-config", "--cflags", "--libs", "Qt6Core"],
            capture_output=True, text=True, check=False,
        )
        require(flags.returncode == 0, "Qt6 Core development flags unavailable: " + flags.stderr)
        command = shlex.split(flags.stdout)
        compile_result = subprocess.run(
            ["c++", "-std=c++17", "-fPIC", str(source_path), "-o", str(binary_path), *command],
            capture_output=True, text=True, check=False,
        )
        require(compile_result.returncode == 0,
                "native test compilation failed:\n" + compile_result.stdout + compile_result.stderr)
        result = subprocess.run(
            [str(binary_path)], capture_output=True, text=True, check=False, timeout=20
        )
        require(result.returncode == 0,
                "native test failed (%d):\n%s%s" %
                (result.returncode, result.stdout, result.stderr))
        try:
            transcript = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("native test emitted invalid JSON: " + result.stdout) from error
        require(transcript["map_watcher_invalidation"] == 1,
                "native Qt watcher did not invalidate exactly once")
        require(transcript["fresh_disk_line_lookup"] is True,
                "original editor caller did not resolve current disk line")
        require(transcript["missing_label_rejected"] is True,
                "missing script label was not rejected")
        require(transcript["labels_refreshed_after_event"] is True,
                "script label cache did not refresh after fileChanged")
        require(transcript["watch_reestablished_after_invalidation"] is True,
                "script watcher was not re-established")
        require(transcript["shifted_line_lookup"] == 3,
                "line lookup did not reflect the latest file contents")
        require(transcript["helper_launch_returned_true"] is True
                and transcript["helper_pid_positive"] is True
                and transcript["helper_marker_observed"] is True,
                "original detached-process launch boundary failed")
        require(transcript["missing_program_rejected"] is True,
                "missing executable negative control escaped")
        require(transcript["helper_exit_status_observed"] is False,
                "test overclaims detached process exit status")
        return {
            "compile_command": ["c++", "-std=c++17", "-fPIC",
                                "native.cpp", "-o", "native", *command],
            "compile_exit_code": compile_result.returncode,
            "native_exit_code": result.returncode,
            "native_transcript": transcript,
            "native_transcript_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "native_function_sha256": {
                name: hashlib.sha256(value.encode()).hexdigest()
                for name, value in functions.items()
            },
            "native_execution": True,
            "native_qt_core": True,
            "native_full_gui": False,
            "native_project_watcher": False,
            "native_map_script_watcher": True,
            "native_external_editor_application": False,
            "helper_process_exit_status_observed": False,
            "script_write_source": "test harness QFile in-place write; not an external editor save",
            "fsync_or_hardware_durability_tested": False,
        }


def validate_evidence(evidence):
    require(evidence["upstream_pin"] == PIN, "upstream pin changed")
    require(evidence["new_source_file_count"] == 0, "reused sources presented as new coverage")
    require(evidence["reused_context_file_count"] == len(FILES), "context count changed")
    require(len(evidence["files"]) == len(FILES), "source matrix row count changed")
    require(len({row["path"] for row in evidence["files"]}) == len(FILES),
            "duplicate source matrix row")
    require(evidence["source_mutations_rejected"] == len(FILES),
            "source mutation controls incomplete")
    require(evidence["evidence_status"] == "NEEDS_EVIDENCE",
            "bounded evidence overclaimed")
    require(evidence["phase1_gate"] == "FAIL_INCOMPLETE"
            and evidence["independent_approvals"] == 0,
            "Phase 1 gate/approval status overclaimed")
    require(evidence["native_map_script_watcher"] is True,
            "native Map watcher execution missing")
    for field in (
        "native_full_gui", "native_project_watcher", "external_editor_application",
        "external_editor_saved_script", "cold_process_reopen",
        "helper_process_exit_status_observed", "fsync_or_hardware_durability_tested",
        "complete_file_independent_review",
    ):
        require(evidence[field] is False, "unsupported claim: " + field)
    for row in evidence["files"]:
        require(row["coverage"] == "reused_prior_context",
                "prior source context misclassified")
        require(row["disposition"] == "NEEDS_EVIDENCE",
                "source disposition overclaimed")
        require(len(row["sha256"]) == 64, "invalid source SHA-256")
    require(len(evidence["license_evidence"]["sha256"]) == 64,
            "license identity missing")
    require(len(evidence["prior_dossiers"]) == len(PRIOR_DOSSIERS),
            "prior dossier inventory changed")


def evidence_negatives(evidence):
    mutations = (
        {"upstream_pin": "0" * 40},
        {"new_source_file_count": len(FILES)},
        {"reused_context_file_count": 0},
        {"source_mutations_rejected": 0},
        {"evidence_status": "PASSED"},
        {"phase1_gate": "PASS"},
        {"independent_approvals": 1},
        {"native_full_gui": True},
        {"native_project_watcher": True},
        {"external_editor_application": True},
        {"external_editor_saved_script": True},
        {"cold_process_reopen": True},
        {"helper_process_exit_status_observed": True},
        {"fsync_or_hardware_durability_tested": True},
        {"complete_file_independent_review": True},
        {"files": []},
        {"prior_dossiers": []},
    )
    for index, mutation in enumerate(mutations):
        try:
            validate_evidence({**evidence, **mutation})
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped: " + str(index))
    return len(mutations)


def make_archive(dossier, evidence, destination):
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w") as archive:
        for path, name in (
            (dossier, "porymap-external-script-reload-boundary-20261105.md"),
            (evidence, "porymap-external-script-reload-boundary-20261105.json"),
        ):
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    with destination.open("wb") as target:
        with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as compressed:
            compressed.write(raw_tar.getvalue())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", required=True, type=Path)
    parser.add_argument("--dossier", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    root = args.porymap.resolve()
    require(git(root, "rev-parse", "HEAD") == PIN, "pinned Porymap commit drift")

    rows = []
    sources = {}
    for path, (role, _) in FILES.items():
        row, sources[path] = pinned_file(root, path)
        row.update({
            "role": role,
            "coverage": "reused_prior_context",
            "disposition": "NEEDS_EVIDENCE",
        })
        rows.append(row)
    verify_sources(sources)
    source_mutation_count = source_negatives(sources)

    license_row, license_text = pinned_file(root, "LICENSE.md")
    require("GNU LESSER GENERAL PUBLIC LICENSE" in license_text,
            "pinned Porymap root license notice changed")
    prior_dossiers = []
    for path, role in PRIOR_DOSSIERS.items():
        data = Path(path).read_bytes()
        prior_dossiers.append({
            "path": path,
            "role": role,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "lines": len(data.splitlines()),
        })

    native = build_and_run(sources)
    evidence = {
        "class": "PINNED_PORYMAP_EXTERNAL_SCRIPT_RELOAD_BOUNDARY",
        "upstream_pin": PIN,
        "files": rows,
        "new_source_file_count": 0,
        "reused_context_file_count": len(FILES),
        "source_mutations_rejected": source_mutation_count,
        "evidence_mutations_rejected": 17,
        "native_test": native,
        "native_map_script_watcher": True,
        "native_full_gui": False,
        "native_project_watcher": False,
        "external_editor_application": False,
        "external_editor_saved_script": False,
        "cold_process_reopen": False,
        "helper_process_exit_status_observed": False,
        "fsync_or_hardware_durability_tested": False,
        "complete_file_independent_review": False,
        "source_observations": [
            "Map::getScriptLabels caches parsed labels and connects its QFileSystemWatcher fileChanged signal to Map::invalidateScripts.",
            "Map::invalidateScripts clears the cache, deletes/resets that watcher, and emits scriptsModified.",
            "Editor::openScriptInFile calls ParseUtil::getScriptLineNumber for the supplied path; the parser reads the file at lookup time.",
            "Editor::startDetachedProcess returns QProcess::startDetached status; the caller's editor interaction is not an exit-status observation.",
            "Project::recordFileChange and MainWindow::showFileWatcherWarning are source-only reused context, not exercised by this native test.",
            "Porymap has no script text buffer in this path; the test's writes are harness-controlled QFile writes.",
        ],
        "prior_dossiers": prior_dossiers,
        "license_evidence": {
            "path": "LICENSE.md",
            **license_row,
            "license_text_observed": "GNU LESSER GENERAL PUBLIC LICENSE",
            "third_party_scope": "Qt6 Core system dependency; no SQLite or Qt translation files included",
        },
        "evidence_status": "NEEDS_EVIDENCE",
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    validate_evidence(evidence)
    evidence["evidence_mutations_rejected"] = evidence_negatives(evidence)
    validate_evidence(evidence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    make_archive(args.dossier, args.output, args.archive)
    archive_sha = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    args.archive.with_suffix(args.archive.suffix + ".sha256").write_text(
        archive_sha + "  " + args.archive.name + "\n"
    )
    print(json.dumps({
        "evidence_class": evidence["class"],
        "upstream_pin": PIN,
        "reused_context_files": len(FILES),
        "source_mutations_rejected": source_mutation_count,
        "evidence_mutations_rejected": evidence["evidence_mutations_rejected"],
        "native_test": native,
        "dossier_sha256": hashlib.sha256(args.dossier.read_bytes()).hexdigest(),
        "archive_sha256": archive_sha,
        "evidence_status": "NEEDS_EVIDENCE",
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
