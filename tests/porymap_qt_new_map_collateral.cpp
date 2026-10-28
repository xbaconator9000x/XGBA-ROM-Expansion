// Phase 1 only: execute unchanged Porymap Project new-map save under native Qt.
// Test-only new maps and injected filesystem failures; not a MainWindow GUI test.
#include "project.h"
#include "config.h"
#include "map.h"
#include "mapconnection.h"
#include "loadingscreen.h"
#include <QApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <iostream>
#include <cstdlib>

static void need(bool ok, const char *message) {
    if (!ok) { std::cerr << "FAIL " << message << std::endl; std::exit(3); }
}
static QByteArray readBytes(const QString &path) {
    QFile f(path);
    need(f.open(QIODevice::ReadOnly), "read file");
    return f.readAll();
}
static int occurrences(const QByteArray &data, const QByteArray &needle) {
    int count = 0, pos = 0;
    while ((pos = data.indexOf(needle, pos)) >= 0) { ++count; pos += needle.size(); }
    return count;
}
static Map *newMap(Project &project, Map *templateMap, const QString &name) {
    Project::NewMapSettings settings = project.newMapSettings;
    settings.name = name;
    need(!project.groupNames.isEmpty(), "no pinned map group");
    settings.group = project.groupNames.first();
    settings.canFlyTo = false;
    settings.layout.id = templateMap->layoutId();
    settings.header = *templateMap->header();
    Map *map = project.createNewMap(settings, templateMap);
    need(map != nullptr, "createNewMap failed");
    need(!map->isPersistedToFile(), "new map already persisted");
    need(project.loadMap(name) == map, "new map loadMap failed");
    need(project.isLoadedMap(name), "new map not loaded");
    return map;
}
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    need(argc == 2, "usage: test PROJECT_ROOT");
    porysplash = new PorymapLoadingScreen;
    const QString root = QString::fromLocal8Bit(argv[1]);
    need(QFileInfo(root).isDir(), "project root absent");
    need(projectConfig.load(root) && userConfig.load(root), "project configs failed");
    Project project;
    project.setRoot(root);
    MapConnection::project = &project;
    need(project.load(), "original Project load failed");
    Map *base = project.loadMap("PalletTown");
    need(base != nullptr, "original PalletTown load failed");
    const QString eventPath = root + "/" + projectConfig.getFilePath(ProjectFilePath::data_event_scripts);
    const QByteArray originalEvent = readBytes(eventPath);

    // Case A: original saveTextFile opens /dev/full, but its write fails.
    const QString nameA = "XGBAPhase1ScriptFailure";
    Map *a = newMap(project, base, nameA);
    const QString folderA = projectConfig.getFilePath(ProjectFilePath::data_map_folders) + nameA;
    const QString dirA = root + "/" + folderA;
    need(QDir().mkpath(dirA), "new map A directory");
    const QString scriptA = dirA + "/scripts" + Project::getScriptFileExtension(projectConfig.usePoryScript);
    need(!QFileInfo::exists(scriptA), "script A already exists");
    QFile full("/dev/full");
    need(full.link(scriptA), "cannot inject scripts /dev/full symlink");
    need(QFileInfo(scriptA).canonicalFilePath() == QStringLiteral("/dev/full"), "script failure device mismatch");
    QFile control(scriptA);
    need(control.open(QIODevice::WriteOnly), "script failure control open");
    const qint64 bytesWritten = control.write("PHASE1", 6);
    const bool flushed = control.flush();
    const QFileDevice::FileError error = control.error();
    control.close();
    need((bytesWritten < 0 || !flushed) && error != QFileDevice::NoError,
         "matched Qt script write did not fail");
    const bool firstSaveA = project.saveMap(a, true);
    const bool persistedA = a->isPersistedToFile();
    need(QFile::remove(scriptA), "remove script failure symlink");
    need(firstSaveA && persistedA, "source-pinned ignored script failure changed");
    need(QFileInfo::exists(a->getJsonFilepath()), "new map A JSON not saved");
    need(readBytes(a->getJsonFilepath()).contains(nameA.toUtf8()), "new map A JSON name absent");
    need(!QFileInfo::exists(scriptA), "failed script A unexpectedly persisted");
    const QByteArray afterFirstA = readBytes(eventPath);
    const QByteArray includeA = QString("\t.include \"%1/scripts.inc\"").arg(folderA).toUtf8();
    need(occurrences(originalEvent, includeA) == 0, "preexisting A include");
    need(occurrences(afterFirstA, includeA) == 1, "A include not appended exactly once");
    need(project.saveMap(a, true), "A retry failed");
    need(!QFileInfo::exists(scriptA), "A retry regenerated collateral despite persisted flag");
    need(occurrences(readBytes(eventPath), includeA) == 1, "A retry appended duplicate include");

    // Case B: map.json cannot be opened. New-map collateral is appended again
    // on each failed retry because setClean is never reached.
    const QString nameB = "XGBAPhase1MapJsonFailure";
    Map *b = newMap(project, base, nameB);
    const QString folderB = projectConfig.getFilePath(ProjectFilePath::data_map_folders) + nameB;
    const QString dirB = root + "/" + folderB;
    need(QDir().mkpath(dirB), "new map B directory");
    const QString jsonB = b->getJsonFilepath();
    need(QDir().mkpath(jsonB), "map JSON failure directory injection");
    need(QFileInfo(jsonB).isDir(), "map JSON failure path not directory");
    QFile mapOpenControl(jsonB);
    need(!mapOpenControl.open(QIODevice::WriteOnly), "map JSON failure control unexpectedly opened");
    const QByteArray includeB = QString("\t.include \"%1/scripts.inc\"").arg(folderB).toUtf8();
    need(occurrences(readBytes(eventPath), includeB) == 0, "preexisting B include");
    const bool firstSaveB = project.saveMap(b, true);
    need(!firstSaveB && !b->isPersistedToFile(), "B first open failure incorrectly marked persisted");
    need(occurrences(readBytes(eventPath), includeB) == 1, "B first append absent");
    const bool secondSaveB = project.saveMap(b, true);
    need(!secondSaveB && !b->isPersistedToFile(), "B retry open failure incorrectly marked persisted");
    need(occurrences(readBytes(eventPath), includeB) == 2, "B retry did not duplicate append");
    need(QFileInfo(dirB + "/scripts" + Project::getScriptFileExtension(projectConfig.usePoryScript)).isFile(),
         "B script positive control absent");

    QJsonObject out;
    out["original_porymap_project_executed"] = true;
    out["original_firered_project_loaded"] = true;
    out["case_a_matched_qfile_error"] = true;
    out["case_a_save_returned_true"] = firstSaveA;
    out["case_a_persisted_flag_true"] = persistedA;
    out["case_a_script_absent_after_retry"] = true;
    out["case_a_event_include_count_after_retry"] = 1;
    out["case_b_map_json_open_rejected"] = true;
    out["case_b_save_returned_false_twice"] = !firstSaveB && !secondSaveB;
    out["case_b_persisted_flag_false"] = !b->isPersistedToFile();
    out["case_b_event_include_count_after_retry"] = 2;
    out["native_qt_project"] = true;
    out["real_gui_new_map"] = false;
    out["physical_durability_tested"] = false;
    out["phase1_gate"] = "FAIL_INCOMPLETE";
    out["independent_approvals"] = 0;
    std::cout << "PHASE1_NEW_MAP_QT=" << QJsonDocument(out).toJson(QJsonDocument::Compact).constData() << std::endl;
    MapConnection::project = nullptr;
    delete porysplash;
    porysplash = nullptr;
    return 0;
}
