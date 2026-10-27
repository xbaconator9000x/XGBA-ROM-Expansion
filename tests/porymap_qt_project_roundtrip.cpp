// Phase 1 ONLY: full pinned Porymap Project load/save/reload, including Qt failure injection.
// This does not approve editor compatibility or certify a GUI transaction.
#include "project.h"
#include "config.h"
#include "map.h"
#include "mapconnection.h"
#include "loadingscreen.h"
#include <QApplication>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QByteArray>
#include <iostream>

static void require(bool ok, const char *message) {
    if (!ok) { std::cerr << "FAIL: " << message << std::endl; std::exit(2); }
}
static QByteArray fileBytes(const QString &path) {
    QFile f(path);
    require(f.open(QIODevice::ReadOnly), "cannot read map.json");
    return f.readAll();
}
static int diskOffset(const QString &path, const QString &direction, const QString &target) {
    QJsonParseError error;
    const QJsonDocument doc = QJsonDocument::fromJson(fileBytes(path), &error);
    require(error.error == QJsonParseError::NoError, "on-disk map.json malformed");
    const auto entries = doc.object().value("connections").toArray();
    for (const auto &entry : entries) {
        const auto o = entry.toObject();
        if (o.value("direction").toString() == direction && o.value("map").toString() == target)
            return o.value("offset").toInt(0x7fffffff);
    }
    require(false, "target connection missing from disk");
    return 0;
}
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    require(argc == 2, "usage: porymap-phase1 PROJECT_ROOT");
    porysplash = new PorymapLoadingScreen;
    const QString root = QString::fromLocal8Bit(argv[1]);
    require(QFileInfo(root).isDir(), "missing cloned project root");
    require(projectConfig.load(root), "pinned ProjectConfig load failed");
    require(userConfig.load(root), "pinned UserConfig load failed");
    const QString name = "PalletTown";
    const QString jsonPath = root + "/data/maps/PalletTown/map.json";
    require(QFileInfo(jsonPath).isFile(), "pinned PalletTown map missing");
    Project project;
    project.setRoot(root);
    MapConnection::project = &project;
    require(project.load(), "full pinned Project::load failed");
    Map *map = project.loadMap(name);
    require(map != nullptr, "full pinned Project::loadMap failed");
    auto connections = map->getConnections();
    require(!connections.isEmpty(), "expected PalletTown connection");
    MapConnection *connection = connections.first();
    const QString direction = connection->direction();
    const QString target = project.getMapConstant(connection->targetMapName(), connection->targetMapName());
    const int original = connection->offset();
    const int persisted = original + 1;
    connection->setOffset(persisted, false);
    require(map->hasUnsavedChanges(), "connection mutation did not dirty map");
    require(project.saveMap(map, true), "full Project::saveMap positive control failed");
    require(!map->hasUnsavedChanges(), "successful save did not clear map dirty state");
    require(diskOffset(jsonPath, direction, target) == persisted, "connection not saved to disk");
    {
        Project reopened;
        reopened.setRoot(root);
        MapConnection::project = &reopened;
        require(reopened.load(), "full Project reload failed");
        Map *reloaded = reopened.loadMap(name);
        require(reloaded != nullptr, "reopened map failed");
        bool found = false;
        for (const auto *c : reloaded->getConnections()) {
            if (c->direction() == direction && c->targetMapName() == connection->targetMapName()) {
                require(c->offset() == persisted, "connection offset changed on full reload");
                found = true;
            }
        }
        require(found, "connection missing after full reload");
    }
    MapConnection::project = &project;
    // A successful real project round trip is now established. Inject a genuine
    // Linux write error into the same Project::saveMap path using /dev/full.
    const QByteArray savedBytes = fileBytes(jsonPath);
    const int unsaved = original + 2;
    connection->setOffset(unsaved, false);
    require(map->hasUnsavedChanges(), "second mutation did not dirty map");
    const QString backup = jsonPath + ".phase1-backup";
    require(QFile::rename(jsonPath, backup), "cannot isolate original map file");
    QFile full("/dev/full");
    require(full.link(jsonPath), "cannot inject /dev/full symlink");
    require(QFileInfo(jsonPath).isSymLink(), "injected path not a symlink");
    const bool reported = project.saveMap(map, true);
    const bool dirtyAfterFailure = map->hasUnsavedChanges();
    require(QFile::remove(jsonPath), "cannot remove injected symlink");
    require(QFile::rename(backup, jsonPath), "cannot restore original map");
    require(fileBytes(jsonPath) == savedBytes, "original persisted map changed during injected failure");
    require(diskOffset(jsonPath, direction, target) == persisted, "disk offset changed despite failed write");
    // Fail closed on the source-pinned hazard: Project reports success and
    // clears dirty state without checking QFile::flush / close errors.
    require(reported, "pinned Project::saveMap changed failure contract");
    require(!dirtyAfterFailure, "pinned dirty-state failure contract changed");
    QJsonObject result;
    result["full_project_load"] = true;
    result["full_map_save_reload"] = true;
    result["map"] = name;
    result["direction"] = direction;
    result["connection_offset_original"] = original;
    result["connection_offset_reloaded"] = persisted;
    result["in_memory_unsaved_offset"] = unsaved;
    result["injected_write_failure_device"] = "/dev/full";
    result["project_save_returned_true_on_device_failure"] = reported;
    result["map_dirty_after_device_failure"] = dirtyAfterFailure;
    result["disk_content_preserved_after_injected_failure"] = true;
    result["phase1_gate"] = "FAIL_INCOMPLETE";
    result["independent_approval"] = false;
    std::cout << QJsonDocument(result).toJson(QJsonDocument::Indented).constData();
    MapConnection::project = nullptr;
    delete porysplash;
    porysplash = nullptr;
    return 0;
}
