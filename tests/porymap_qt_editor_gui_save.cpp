// Phase 1 ONLY: actual MainWindow QAction -> Editor -> Project save path.
// Full pinned Qt application, real pinned FireRed project. Never claim independent approval.
#include "mainwindow.h"
#include "editor.h"
#include "project.h"
#include "config.h"
#include "map.h"
#include "mapconnection.h"
#include "loadingscreen.h"
#include <QApplication>
#include <QAction>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QStandardPaths>
#include <iostream>
#include <cstdlib>

static void require(bool ok, const char *why) {
    if (!ok) { std::cerr << "FAIL: " << why << std::endl; std::exit(2); }
}
static QByteArray bytes(const QString &path) {
    QFile f(path);
    require(f.open(QIODevice::ReadOnly), "cannot read map JSON");
    return f.readAll();
}
static int diskOffset(const QString &path, const QString &direction, const QString &target) {
    QJsonParseError error;
    auto doc = QJsonDocument::fromJson(bytes(path), &error);
    require(error.error == QJsonParseError::NoError, "malformed on-disk JSON");
    for (const auto &v : doc.object().value("connections").toArray()) {
        auto c = v.toObject();
        if (c.value("direction").toString() == direction && c.value("map").toString() == target)
            return c.value("offset").toInt(0x7fffffff);
    }
    require(false, "expected map connection missing");
    return 0;
}
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    QStandardPaths::setTestModeEnabled(true);
    require(argc == 2, "usage: porymap-phase1-gui PROJECT_ROOT");
    porysplash = new PorymapLoadingScreen;
    const QString root = QString::fromLocal8Bit(argv[1]);
    require(QFileInfo(root).isDir(), "missing pinned project");
    require(projectConfig.load(root), "ProjectConfig load failed");
    require(userConfig.load(root), "UserConfig load failed");

    const QString palletPath = root + "/data/maps/PalletTown/map.json";
    const QString routePath = root + "/data/maps/Route1/map.json";
    require(QFileInfo(palletPath).isFile() && QFileInfo(routePath).isFile(),
            "pinned map pair missing");
    Project project;
    project.setRoot(root);
    {
        MainWindow window(nullptr);
        window.initialize();
        require(window.editor, "MainWindow did not initialize real Editor");
        // MainWindow::openProject ordinarily installs this exact signal connection.
        require(QObject::connect(&project, SIGNAL(mapLoaded(Map*)), &window, SLOT(onMapLoaded(Map*))),
                "cannot connect real Project mapLoaded to private MainWindow Qt slot");
        window.editor->setProject(&project);
        require(project.load(), "full pinned project load failed");
        require(window.editor->setMap("PalletTown"), "real Editor::setMap failed");
        Map *map = window.editor->map;
        require(map != nullptr && !map->getConnections().isEmpty(), "map connections absent");
        MapConnection *conn = map->getConnections().first();
        MapConnection *mirror = conn->findMirror();
        require(mirror != nullptr, "expected authored Route1 mirror not found");
        Map *other = project.loadMap(conn->targetMapName());
        require(other != nullptr, "target map not loaded");
        const QString direction = conn->direction();
        const QString target = project.getMapConstant(conn->targetMapName(), conn->targetMapName());
        const QString otherDirection = mirror->direction();
        const QString otherTarget = project.getMapConstant(mirror->targetMapName(), mirror->targetMapName());
        const int original = conn->offset();
        require(mirror->offset() == -original, "original mirror offset inconsistent");
        require(diskOffset(palletPath, direction, target) == original, "pallet disk baseline mismatch");
        require(diskOffset(routePath, otherDirection, otherTarget) == -original, "route disk baseline mismatch");

        // Prevent one-time informational popup; no save logic is patched.
        porymapConfig.shownInGameReloadMessage = true;
        QAction *save = window.findChild<QAction*>("action_Save");
        QAction *saveAll = window.findChild<QAction*>("action_Save_Project");
        require(save != nullptr && saveAll != nullptr, "real GUI save actions absent");
        // Project was attached through public Editor API rather than private openProject.
        save->setEnabled(true);
        saveAll->setEnabled(true);
        unsigned saveTriggers = 0, allTriggers = 0;
        QObject::connect(save, &QAction::triggered, [&] { ++saveTriggers; });
        QObject::connect(saveAll, &QAction::triggered, [&] { ++allTriggers; });

        // Source-driven Map::modified -> MainWindow::onMapLoaded/markMapEdited.
        conn->setOffset(original + 1, true);
        require(map->hasUnsavedChanges(), "MainWindow did not mark current map dirty");
        require(other->hasUnsavedChanges(), "MainWindow did not mark mirrored map dirty");
        require(mirror->offset() == -(original + 1), "mirror not updated in memory");
        save->trigger(); // Real QAction -> MainWindow::on_action_Save_triggered -> Editor::saveCurrent
        require(saveTriggers == 1, "GUI current-map QAction did not emit triggered");
        require(!map->hasUnsavedChanges(), "current-map GUI save did not clear dirty flag");
        require(diskOffset(palletPath, direction, target) == original + 1,
                "GUI current-map save did not persist PalletTown");
        require(other->hasUnsavedChanges(), "current-only save unexpectedly cleared mirror dirty flag");
        require(diskOffset(routePath, otherDirection, otherTarget) == -original,
                "current-only save unexpectedly wrote Route1");
        saveAll->trigger(); // Real QAction -> MainWindow::save(false) -> Editor::saveAll
        require(allTriggers == 1, "GUI save-project QAction did not emit triggered");
        require(!other->hasUnsavedChanges(), "GUI save-all did not clean mirror");
        require(diskOffset(routePath, otherDirection, otherTarget) == -(original + 1),
                "GUI save-all did not persist mirrored Route1 connection");

        const QByteArray savedPallet = bytes(palletPath);
        conn->setOffset(original + 2, true);
        require(map->hasUnsavedChanges() && other->hasUnsavedChanges(),
                "second mirrored mutation did not dirty both maps");
        const QString backup = palletPath + ".phase1-gui-backup";
        require(QFile::rename(palletPath, backup), "cannot isolate positive disk file");
        QFile full("/dev/full");
        require(full.link(palletPath), "cannot inject /dev/full symlink");
        require(QFileInfo(palletPath).isSymLink(), "injected failure path not symlink");
        save->trigger(); // Actual GUI save QAction on a failing output device.
        require(saveTriggers == 2, "GUI failure save action not triggered");
        const bool dirtyAfterFailedGuiSave = map->hasUnsavedChanges();
        require(QFile::remove(palletPath), "cannot remove failure symlink");
        require(QFile::rename(backup, palletPath), "cannot restore positive disk file");
        require(bytes(palletPath) == savedPallet, "on-disk file changed after failed write");
        require(diskOffset(palletPath, direction, target) == original + 1,
                "failed GUI save silently persisted changed offset");
        require(!dirtyAfterFailedGuiSave, "pinned GUI failure dirty-state behaviour changed");
        require(other->hasUnsavedChanges(), "mirror dirty-state lost unexpectedly");
        require(diskOffset(routePath, otherDirection, otherTarget) == -(original + 1),
                "failed current-only GUI save unexpectedly persisted mirror");

        QJsonObject result;
        result["real_mainwindow_initialized"] = true;
        result["real_editor_map_loaded"] = true;
        result["qaction_current_save_triggers"] = int(saveTriggers);
        result["qaction_save_project_triggers"] = int(allTriggers);
        result["current_only_disk_offset"] = original + 1;
        result["mirror_disk_offset_after_save_all"] = -(original + 1);
        result["failed_gui_save_disk_offset"] = diskOffset(palletPath, direction, target);
        result["failed_gui_save_in_memory_offset"] = conn->offset();
        result["failed_gui_save_cleared_dirty"] = !dirtyAfterFailedGuiSave;
        result["failed_gui_save_mirror_remains_dirty"] = other->hasUnsavedChanges();
        result["failure_device"] = "/dev/full";
        result["phase1_gate"] = "FAIL_INCOMPLETE";
        result["independent_approval"] = false;
        std::cout << "PHASE1_GUI_RESULT="
                  << QJsonDocument(result).toJson(QJsonDocument::Compact).constData()
                  << std::endl;
    }
    delete porysplash;
    porysplash = nullptr;
    return 0;
}
