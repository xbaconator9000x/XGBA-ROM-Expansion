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
#include <QTimer>
#include <QMessageBox>
#include <QAbstractButton>
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
// Matched QFile control: the same symlink path must resolve to /dev/full,
// and Qt must expose an actual device error before the GUI Save action.
// This is not instrumentation of Project::saveMap's own QFile handle.
static bool verifyFailureDevice(const QString &path) {
    require(QFileInfo(path).canonicalFilePath() == QStringLiteral("/dev/full"),
            "injected GUI save path does not resolve to /dev/full");
    QFile direct(path);
    require(direct.open(QIODevice::WriteOnly), "matched /dev/full QFile open failed");
    const qint64 written = direct.write("X", 1);
    const bool flushed = direct.flush();
    const QFileDevice::FileError error = direct.error();
    direct.close();
    require((written < 0 || !flushed) && error != QFileDevice::NoError,
            "matched /dev/full QFile did not report a write/flush device error");
    return true;
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

    // Reopen through actual MainWindow::initialize -> openProject, including
    // setProjectUI and map-list initialization (previous bypass crashed).
    // MainWindow constructor sets these names; match them BEFORE resolving
    // QStandardPaths::AppDataLocation for the startup recent-project config.
    QCoreApplication::setOrganizationName("pret");
    QCoreApplication::setApplicationName("porymap");
    porymapConfig.load();
    porymapConfig.addRecentProject(root);
    porymapConfig.reopenOnLaunch = true;
    porymapConfig.projectManuallyClosed = false;
    porymapConfig.checkForUpdates = false;
    porymapConfig.showProjectLoadingScreen = false;
    porymapConfig.shownInGameReloadMessage = true;
    require(porymapConfig.save(), "could not persist startup recent-project config");
    require(porymapConfig.getRecentProject() == root, "recent project not configured");
    {
        MainWindow window(nullptr);
        std::cerr << "PHASE1_GUI_STAGE real_open_project_begin" << std::endl;
        window.initialize();
        std::cerr << "PHASE1_GUI_STAGE real_open_project_done recent="
                  << porymapConfig.getRecentProject().toStdString()
                  << " reopen=" << porymapConfig.reopenOnLaunch
                  << " manually_closed=" << porymapConfig.projectManuallyClosed << std::endl;
        require(window.editor && window.editor->project,
                "MainWindow::openProject did not initialize real Editor/Project");
        Project *project = window.editor->project;
        std::cerr << "PHASE1_GUI_STAGE editor_setmap_begin" << std::endl;
        require(window.editor->setMap("PalletTown"), "real Editor::setMap failed");
        std::cerr << "PHASE1_GUI_STAGE editor_setmap_done" << std::endl;
        Map *map = window.editor->map;
        require(map != nullptr && !map->getConnections().isEmpty(), "map connections absent");
        MapConnection *conn = map->getConnections().first();
        std::cerr << "PHASE1_GUI_STAGE mirror_lookup_begin" << std::endl;
        MapConnection *mirror = conn->findMirror();
        std::cerr << "PHASE1_GUI_STAGE mirror_lookup_done" << std::endl;
        require(mirror != nullptr, "expected authored Route1 mirror not found");
        Map *other = project->loadMap(conn->targetMapName());
        require(other != nullptr, "target map not loaded");
        const QString direction = conn->direction();
        const QString target = project->getMapConstant(conn->targetMapName(), conn->targetMapName());
        const QString otherDirection = mirror->direction();
        const QString otherTarget = project->getMapConstant(mirror->targetMapName(), mirror->targetMapName());
        const int original = conn->offset();
        require(mirror->offset() == -original, "original mirror offset inconsistent");
        require(diskOffset(palletPath, direction, target) == original, "pallet disk baseline mismatch");
        require(diskOffset(routePath, otherDirection, otherTarget) == -original, "route disk baseline mismatch");

        // Prevent one-time informational popup; no save logic is patched.
        porymapConfig.shownInGameReloadMessage = true;
        QAction *save = window.findChild<QAction*>("action_Save");
        QAction *saveAll = window.findChild<QAction*>("action_Save_Project");
        require(save != nullptr && saveAll != nullptr, "real GUI save actions absent");
        require(save->isEnabled() && saveAll->isEnabled(),
                "real MainWindow::openProject left save actions disabled");
        unsigned saveTriggers = 0, allTriggers = 0;
        QObject::connect(save, &QAction::triggered, [&] { ++saveTriggers; });
        QObject::connect(saveAll, &QAction::triggered, [&] { ++allTriggers; });

        // Source-driven Map::modified -> MainWindow::onMapLoaded/markMapEdited.
        conn->setOffset(original + 1, true);
        require(map->hasUnsavedChanges(), "MainWindow did not mark current map dirty");
        require(other->hasUnsavedChanges(), "MainWindow did not mark mirrored map dirty");
        require(mirror->offset() == -(original + 1), "mirror not updated in memory");
        std::cerr << "PHASE1_GUI_STAGE first_gui_save" << std::endl;
        save->trigger(); // Real QAction -> MainWindow::on_action_Save_triggered -> Editor::saveCurrent
        require(saveTriggers == 1, "GUI current-map QAction did not emit triggered");
        require(!map->hasUnsavedChanges(), "current-map GUI save did not clear dirty flag");
        require(diskOffset(palletPath, direction, target) == original + 1,
                "GUI current-map save did not persist PalletTown");
        require(other->hasUnsavedChanges(), "current-only save unexpectedly cleared mirror dirty flag");
        require(diskOffset(routePath, otherDirection, otherTarget) == -original,
                "current-only save unexpectedly wrote Route1");
        std::cerr << "PHASE1_GUI_STAGE save_project" << std::endl;
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
        const bool mirroredDeviceFailure = verifyFailureDevice(palletPath);
        std::cerr << "PHASE1_GUI_STAGE injected_failure_gui_save" << std::endl;
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

        const int diskAfterFailedGuiSave = diskOffset(palletPath, direction, target);
        require(diskAfterFailedGuiSave == original + 1,
                "failed current-only save disk snapshot unexpectedly changed");
        // Consequential edge case: the failed current-only save cleared the
        // PalletTown dirty flag, while the mirrored Route1 edit remains dirty.
        // Trigger the actual Save Project QAction again. Does it repair BOTH
        // on-disk connections, or save only the remaining dirty mirror?
        // Record either outcome; do not assume the source-level hazard.
        std::cerr << "PHASE1_GUI_STAGE save_all_after_failed_current" << std::endl;
        saveAll->trigger();
        require(allTriggers == 2, "post-failure GUI Save Project QAction not triggered");
        const int currentDiskAfterRetry = diskOffset(palletPath, direction, target);
        const int mirrorDiskAfterRetry = diskOffset(routePath, otherDirection, otherTarget);
        require(mirrorDiskAfterRetry == -(original + 2),
                "Save Project failed to persist remaining dirty Route1 mirror");
        require(currentDiskAfterRetry == original + 1 || currentDiskAfterRetry == original + 2,
                "unexpected PalletTown disk state after Save Project retry");
        const bool divergentDiskMirror = currentDiskAfterRetry != -mirrorDiskAfterRetry;
        const bool currentDirtyAfterRetry = map->hasUnsavedChanges();
        const bool mirrorDirtyAfterRetry = other->hasUnsavedChanges();
        require(!mirrorDirtyAfterRetry, "Save Project did not clear persisted Route1 dirty state");
        // If divergentDiskMirror is true, this is observed disk inconsistency,
        // not just the earlier in-memory/disk mismatch.

        // Isolated single-map unsaved edit: unlike reciprocal connection
        // mutations, this must not leave a second loaded map dirty.
        // This probes the real GUI close path after a failed current-map Save.
        require(!project->hasUnsavedChanges(),
                "Save Project retry left unexpected dirty state; close test invalid");
        QJsonObject custom = map->customAttributes();
        custom.insert("xgba_phase1_unsaved_only", QStringLiteral("persisted-v1"));
        map->setCustomAttributes(custom);
        map->setHasUnsavedDataChanges(true);
        require(map->hasUnsavedChanges() && project->hasUnsavedChanges(),
                "isolated current-map edit was not marked dirty");
        require(!other->hasUnsavedChanges(),
                "isolated edit unexpectedly dirtied mirrored Route1");
        // Positive control: this exact custom attribute must be serialized
        // by a successful real GUI Save, or its later loss proves nothing.
        std::cerr << "PHASE1_GUI_STAGE isolated_single_map_positive_save" << std::endl;
        save->trigger();
        require(saveTriggers == 3, "single-map positive GUI Save not triggered");
        require(bytes(palletPath).contains("persisted-v1"),
                "single-map custom attribute not serialized by successful Save");
        require(!map->hasUnsavedChanges() && !project->hasUnsavedChanges(),
                "single-map positive GUI Save did not clean project");
        // Positive control for the close warning: an actually dirty map must
        // show the pinned SaveChangesMessage and Cancel must reject closing.
        // The timer only interacts with the real modal QMessageBox after it opens.
        custom.insert("xgba_phase1_unsaved_only", QStringLiteral("dirty-close-control"));
        map->setCustomAttributes(custom);
        map->setHasUnsavedDataChanges(true);
        require(map->hasUnsavedChanges() && project->hasUnsavedChanges(),
                "dirty close positive control was not marked dirty");
        const QByteArray diskBeforeDirtyClose = bytes(palletPath);
        bool dirtyClosePromptObserved = false;
        QTimer::singleShot(0, &window, [&] {
            for (QWidget *widget : QApplication::topLevelWidgets()) {
                auto *dialog = qobject_cast<QMessageBox*>(widget);
                if (!dialog || !dialog->isVisible() ||
                    !dialog->text().contains("modified, save changes?"))
                    continue;
                QAbstractButton *cancel = dialog->button(QMessageBox::Cancel);
                require(cancel != nullptr, "dirty-close dialog lacked Cancel");
                dirtyClosePromptObserved = true;
                cancel->click(); // Real GUI Cancel button, no save and no auto-approval.
                return;
            }
        });
        std::cerr << "PHASE1_GUI_STAGE dirty_close_cancel_positive_control" << std::endl;
        const bool dirtyCloseAccepted = window.close();
        require(dirtyClosePromptObserved && !dirtyCloseAccepted,
                "dirty project close did not show cancellable warning");
        require(map->hasUnsavedChanges() && project->hasUnsavedChanges(),
                "Cancel close incorrectly cleaned project");
        require(bytes(palletPath) == diskBeforeDirtyClose,
                "Cancel close unexpectedly wrote map JSON");

        custom.insert("xgba_phase1_unsaved_only", QStringLiteral("not-on-disk-v2"));
        map->setCustomAttributes(custom);
        map->setHasUnsavedDataChanges(true);
        require(map->hasUnsavedChanges() && project->hasUnsavedChanges(),
                "second isolated map edit not dirty");
        const QByteArray diskBeforeSingleMapFailure = bytes(palletPath);
        const QString singleMapBackup = palletPath + ".phase1-single-map-backup";
        require(QFile::rename(palletPath, singleMapBackup),
                "cannot isolate single-map disk baseline");
        QFile fullSingle("/dev/full");
        require(fullSingle.link(palletPath), "cannot inject single-map /dev/full");
        require(QFileInfo(palletPath).isSymLink(),
                "single-map failure injection was not a symlink");
        const bool isolatedDeviceFailure = verifyFailureDevice(palletPath);
        std::cerr << "PHASE1_GUI_STAGE isolated_single_map_failed_save" << std::endl;
        save->trigger();
        require(saveTriggers == 4, "single-map GUI Save QAction not triggered");
        const bool singleMapDirtyAfterFailure = map->hasUnsavedChanges();
        const bool projectDirtyAfterFailure = project->hasUnsavedChanges();
        require(QFile::remove(palletPath), "cannot remove single-map failure symlink");
        require(QFile::rename(singleMapBackup, palletPath),
                "cannot restore single-map disk baseline");
        require(bytes(palletPath) == diskBeforeSingleMapFailure,
                "single-map failed save changed physical JSON");
        require(!singleMapDirtyAfterFailure,
                "pinned single-map failure dirty-state hazard changed");
        require(!projectDirtyAfterFailure,
                "project still dirty; no-prompt close test would be invalid");
        require(bytes(palletPath).contains("persisted-v1") &&
                !bytes(palletPath).contains("not-on-disk-v2"),
                "failed GUI Save lost baseline or persisted unsaved edit");
        QJsonObject result;
        result["real_mainwindow_initialized"] = true;
        result["real_editor_map_loaded"] = true;
        result["qaction_current_save_triggers"] = int(saveTriggers);
        result["qaction_save_project_triggers"] = int(allTriggers);
        result["current_only_disk_offset"] = original + 1;
        result["mirror_disk_offset_after_save_all"] = -(original + 1);
        result["failed_gui_save_disk_offset"] = diskAfterFailedGuiSave;
        result["failed_gui_save_in_memory_offset"] = conn->offset();
        result["failed_gui_save_cleared_dirty"] = !dirtyAfterFailedGuiSave;
        result["failed_gui_save_mirror_remains_dirty"] = true; // captured immediately after failure
        result["save_all_after_failure_triggers"] = int(allTriggers);
        result["post_failure_retry_current_disk_offset"] = currentDiskAfterRetry;
        result["post_failure_retry_mirror_disk_offset"] = mirrorDiskAfterRetry;
        result["post_failure_retry_disk_mirrors_divergent"] = divergentDiskMirror;
        result["post_failure_retry_current_dirty"] = currentDirtyAfterRetry;
        result["post_failure_retry_mirror_dirty"] = mirrorDirtyAfterRetry;
        result["single_map_failed_save_disk_unchanged"] = true;
        result["single_map_failed_save_map_dirty"] = singleMapDirtyAfterFailure;
        result["single_map_failed_save_project_dirty"] = projectDirtyAfterFailure;
        result["single_map_positive_save_persisted"] = true;
        result["dirty_close_cancel_prompt_observed"] = dirtyClosePromptObserved;
        result["dirty_close_cancel_rejected"] = !dirtyCloseAccepted;
        result["dirty_close_cancel_preserved_disk"] = true;
        result["single_map_unsaved_attribute_not_persisted"] = true;
        result["single_map_gui_save_triggers"] = int(saveTriggers);
        result["failure_device"] = "/dev/full";
        result["mirrored_matched_qfile_error"] = mirroredDeviceFailure;
        result["isolated_matched_qfile_error"] = isolatedDeviceFailure;
        result["phase1_gate"] = "FAIL_INCOMPLETE";
        result["independent_approval"] = false;
        // QWidget::close invokes the actual MainWindow::closeEvent ->
        // closeProject chain. The project is falsely clean, so a prompt
        // should not occur; require accepted close and never auto-answer
        // an unexpected modal SaveChangesMessage.
        std::cerr << "PHASE1_GUI_STAGE close_after_failed_single_map_save" << std::endl;
        const bool closeAccepted = window.close();
        require(closeAccepted, "real MainWindow close event was rejected");
        result["close_after_failed_single_map_save_accepted"] = closeAccepted;
        std::cout << "PHASE1_GUI_RESULT="
                  << QJsonDocument(result).toJson(QJsonDocument::Compact).constData()
                  << std::endl;
    }
    // Cold-reopen with a newly constructed real MainWindow/Editor, after
    // the falsely clean prior window has closed and been destroyed.
    porymapConfig.addRecentProject(root);
    porymapConfig.reopenOnLaunch = true;
    porymapConfig.projectManuallyClosed = false;
    porymapConfig.checkForUpdates = false;
    porymapConfig.showProjectLoadingScreen = false;
    require(porymapConfig.save(), "cannot configure cold editor reopen");
    {
        MainWindow coldWindow(nullptr);
        coldWindow.initialize();
        require(coldWindow.editor && coldWindow.editor->project,
                "cold MainWindow did not load project");
        require(coldWindow.editor->setMap("PalletTown"),
                "cold Editor could not reopen PalletTown");
        Map *reopened = coldWindow.editor->map;
        require(reopened != nullptr, "cold editor map missing");
        require(reopened->customAttributes().value("xgba_phase1_unsaved_only").toString()
                    == QStringLiteral("persisted-v1"),
                "cold editor did not recover prior persisted value");
        QJsonObject coldResult;
        coldResult["fresh_mainwindow_editor"] = true;
        coldResult["recovered_prior_persisted_value"] = true;
        coldResult["unsaved_failed_value_absent"] = true;
        coldResult["phase1_gate"] = "FAIL_INCOMPLETE";
        std::cout << "PHASE1_GUI_COLD_REOPEN="
                  << QJsonDocument(coldResult).toJson(QJsonDocument::Compact).constData()
                  << std::endl;
    }
    delete porysplash;
    porysplash = nullptr;
    return 0;
}
