#include <QCoreApplication>
#include <QHash>
#include <QMap>
#include <QPointer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QImage>
#include <QPixmap>
#include <QPoint>
#include <QSet>
#include <QStringList>
#include <QUndoCommand>
#include <QUndoStack>
#include <QtAlgorithms>

#include <cstdio>
#include <cstdlib>
#include <utility>

#include "mapconnection.h"
#include "editcommands.h"

struct Layout {
    bool hasUnsavedChanges() const { return false; }
};

class Map;

class Project : public QObject {
    Q_OBJECT
public:
    QMap<QString, Map *> maps;
    QMap<QString, Layout *> mapLayouts;
    QSet<QString> loadedMaps;
    QList<Map *> savedMaps;
    bool hasUnsavedDataChanges = false;
    int globalSaveCalls = 0;
    int saveAllCalls = 0;

    Map *loadMap(const QString &name);
    bool hasUnsavedChanges();
    bool saveMap(Map *map);
    bool saveLayout(Layout *) { return true; }
    bool saveGlobalData() { ++globalSaveCalls; return true; }
    bool saveAll() { ++saveAllCalls; return true; }

signals:
    void mapLoaded(Map *map);
};

class Map : public QObject {
    Q_OBJECT
public:
    explicit Map(QString name)
        : m_name(std::move(name)), m_editHistory(new QUndoStack(this)) {}

    ~Map() override { qDeleteAll(m_ownedConnections); }

    QString name() const { return m_name; }
    QList<MapConnection *> getConnections() const { return m_connections; }
    bool containsConnection(MapConnection *connection) const {
        return m_connections.contains(connection);
    }
    QUndoStack *editHistory() const { return m_editHistory; }
    void setHasUnsavedDataChanges(bool changed) { m_hasUnsavedDataChanges = changed; }

    void addConnection(MapConnection *connection);
    void loadConnection(MapConnection *connection);
    void trackConnection(MapConnection *connection);
    void removeConnection(MapConnection *connection);
    void commit(QUndoCommand *command);
    void modify();
    void setClean();
    bool hasUnsavedChanges() const;
    void pruneEditHistory();

signals:
    void modified();
    void connectionAdded(MapConnection *connection);
    void connectionRemoved(MapConnection *connection);

private:
    QString m_name;
    QList<MapConnection *> m_connections;
    QSet<MapConnection *> m_ownedConnections;
    QUndoStack *m_editHistory;
    bool m_hasUnsavedDataChanges = false;
    bool m_isPersistedToFile = true;
    Layout *m_layout = nullptr;
};

struct ProjectConfig {
    bool mirrorConnectingMaps = false;
};

extern ProjectConfig porymapConfig;
ProjectConfig porymapConfig;

class Editor {
public:
    Project *project = nullptr;
    Map *map = nullptr;
    Layout *layout = nullptr;

    void saveEncounterTabData() {}
    bool save(bool currentOnly);
};

class MainWindow : public QObject {
    Q_OBJECT
public:
    explicit MainWindow(Editor *editor) : editor(editor) {}

    Editor *editor = nullptr;
    int mapListUpdates = 0;

    void updateWindowTitle() {}
    void updateMapList() { ++mapListUpdates; }
    void markMapEdited(Map *map);
    void onMapLoaded(Map *map);
};

static void require(bool condition, const char *reason) {
    if (!condition) {
        std::fprintf(stderr, "PHASE1_CROSS_MAP_UNDO_FATAL %s\n", reason);
        std::exit(4);
    }
}

PROJECT_LOAD_MAP_TEST_STUB
PINNED_PROJECT_HAS_UNSAVED_CHANGES_METHOD
PROJECT_SAVE_ROUTING_TEST_STUB
PINNED_MAP_CONNECTION_METHODS
PINNED_MAP_METHODS
PINNED_EDIT_COMMAND_METHODS
PINNED_MAINWINDOW_METHODS
PINNED_EDITOR_SAVE_METHOD

static void exerciseCrossMapHistory(Project &project, Map &mapA, Map &mapB,
                                    MapConnection *connection) {
    porymapConfig.mirrorConnectingMaps = true;
    mapA.setClean();
    mapB.setClean();

    mapA.commit(new MapConnectionMove(connection, 5, 11));
    MapConnection *mirror = connection->findMirror();
    require(mirror && connection->offset() == 5 && mirror->offset() == -5,
            "first_move_mirrors_offsets");
    require(mapA.hasUnsavedChanges() && mapB.hasUnsavedChanges()
            && project.hasUnsavedChanges(),
            "mirror_modified_signal_marks_both_maps_dirty");

    Editor editor;
    editor.project = &project;
    editor.map = &mapA;
    require(editor.save(true), "current_save_result");
    require(project.savedMaps.size() == 1 && project.savedMaps.first() == &mapA,
            "current_save_targets_only_active_map");
    require(!mapA.hasUnsavedChanges() && mapB.hasUnsavedChanges()
            && project.hasUnsavedChanges(),
            "current_save_leaves_mirrored_map_unsaved");

    mapA.setClean();
    mapB.setClean();
    mapA.pruneEditHistory();
    const QUndoCommand *mapACommand = mapA.editHistory()->command(0);
    require(mapACommand && mapACommand->id() != CommandId::ID_MapConnectionMove,
            "connection_command_id_contains_direction_mask");
    require(!mapACommand->isObsolete(), "prune_did_not_match_masked_id");

    mapB.commit(new MapConnectionMove(mirror, -8, 12));
    require(connection->offset() == 8 && mirror->offset() == -8,
            "second_map_edit_changes_both_maps");
    mapA.editHistory()->undo();
    require(connection->offset() == 0 && mirror->offset() == 0,
            "stale_first_stack_undo_overwrites_second_map_edit");
    mapB.editHistory()->undo();
    require(connection->offset() == 5 && mirror->offset() == -5,
            "second_stack_undo_restores_its_recorded_old_value");
}

static void exerciseOtherConnectionCommands(Map &mapA, Map &mapB, Map &mapC,
                                           MapConnection *connection) {
    mapA.editHistory()->clear();
    mapB.editHistory()->clear();
    mapC.editHistory()->clear();
    mapA.setClean();
    mapB.setClean();
    mapC.setClean();

    mapA.commit(new MapConnectionChangeDirection(connection, QStringLiteral("left")));
    MapConnection *mirror = connection->findMirror();
    require(connection->direction() == QStringLiteral("left")
            && mirror && mirror->direction() == QStringLiteral("right"),
            "direction_change_mirrors");
    mapA.editHistory()->undo();
    require(connection->direction() == QStringLiteral("up")
            && mirror->direction() == QStringLiteral("down"),
            "direction_undo_mirrors");

    mapA.commit(new MapConnectionChangeMap(connection, QStringLiteral("C")));
    mirror = connection->findMirror();
    require(connection->targetMapName() == QStringLiteral("C")
            && mirror && mirror->parentMap() == &mapC
            && !mapB.containsConnection(mirror),
            "map_change_moves_mirror");
    mapA.editHistory()->undo();
    mirror = connection->findMirror();
    require(connection->targetMapName() == QStringLiteral("B")
            && mirror && mirror->parentMap() == &mapB,
            "map_change_undo_moves_mirror_back");

    mapA.editHistory()->clear();
    mapA.setClean();
    mapB.setClean();
    auto added = new MapConnection(QStringLiteral("B"), QStringLiteral("right"), 3);
    mapA.commit(new MapConnectionAdd(&mapA, added));
    auto addedMirror = added->findMirror();
    require(addedMirror && mapA.containsConnection(added)
            && mapB.containsConnection(addedMirror),
            "add_command_adds_both_connections");
    mapA.editHistory()->undo();
    require(!mapA.containsConnection(added) && !mapB.containsConnection(addedMirror)
            && added && addedMirror,
            "add_undo_retains_connection_objects_for_redo");
    mapA.editHistory()->redo();
    require(mapA.containsConnection(added) && mapB.containsConnection(addedMirror),
            "add_redo_restores_both_connections");

    mapA.commit(new MapConnectionRemove(&mapA, added));
    require(!mapA.containsConnection(added) && !mapB.containsConnection(addedMirror),
            "remove_command_removes_both_connections");
    mapA.editHistory()->undo();
    require(mapA.containsConnection(added) && mapB.containsConnection(addedMirror),
            "remove_undo_restores_both_connections");
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    Project project;
    Map mapA(QStringLiteral("A"));
    Map mapB(QStringLiteral("B"));
    Map mapC(QStringLiteral("C"));
    project.maps.insert(mapA.name(), &mapA);
    project.maps.insert(mapB.name(), &mapB);
    project.maps.insert(mapC.name(), &mapC);

    Editor editor;
    editor.project = &project;
    editor.map = &mapA;
    MainWindow window(&editor);
    QObject::connect(&project, &Project::mapLoaded, &window,
                     [&window](Map *map) { window.onMapLoaded(map); });
    MapConnection::project = &project;
    project.loadMap(QStringLiteral("A"));
    project.loadMap(QStringLiteral("B"));
    project.loadMap(QStringLiteral("C"));

    porymapConfig.mirrorConnectingMaps = false;
    auto connection = new MapConnection(QStringLiteral("B"), QStringLiteral("up"), 0);
    mapA.addConnection(connection);
    auto mirror = connection->createMirror();
    require(mirror && mapB.containsConnection(mirror), "fixture_mirror_created");
    mapA.setClean();
    mapB.setClean();
    mapC.setClean();

    int mapAModified = 0;
    int mapBModified = 0;
    QObject::connect(&mapA, &Map::modified, &mapA, [&mapAModified] { ++mapAModified; });
    QObject::connect(&mapB, &Map::modified, &mapB, [&mapBModified] { ++mapBModified; });

    exerciseCrossMapHistory(project, mapA, mapB, connection);
    require(mapAModified > 0 && mapBModified > 0, "both_map_modified_signals_observed");
    exerciseOtherConnectionCommands(mapA, mapB, mapC, connection);

    QJsonObject result{
        {QStringLiteral("phase1_gate"), QStringLiteral("FAIL_INCOMPLETE")},
        {QStringLiteral("independent_approvals"), 0},
        {QStringLiteral("pinned_original_method_bodies"), true},
        {QStringLiteral("native_qt_qundo_stack"), true},
        {QStringLiteral("test_only_project_and_ui_shells"), true},
        {QStringLiteral("original_mainwindow_dirty_handlers_called"), true},
        {QStringLiteral("mirrored_dirty_state_observed_on_both_maps"), true},
        {QStringLiteral("original_editor_current_save_routing_called"), true},
        {QStringLiteral("current_save_left_mirror_map_dirty"), true},
        {QStringLiteral("masked_command_remained_nonobsolete"), true},
        {QStringLiteral("stale_stack_undo_overwrote_cross_map_edit"), true},
        {QStringLiteral("second_stack_undo_restored_recorded_value"), true},
        {QStringLiteral("direction_and_map_change_undo_redo"), true},
        {QStringLiteral("add_remove_mirror_lifecycle_undo_redo"), true},
        {QStringLiteral("map_a_modified_signal_count"), mapAModified},
        {QStringLiteral("map_b_modified_signal_count"), mapBModified},
        {QStringLiteral("actual_project_map_json_write_tested"), false},
        {QStringLiteral("actual_project_save_all_tested"), false},
        {QStringLiteral("actual_gui_interaction_tested"), false},
        {QStringLiteral("cold_project_reopen_tested"), false},
        {QStringLiteral("stock_gameplay_tested"), false},
        {QStringLiteral("hardware_durability_tested"), false}
    };
    const QByteArray json = QJsonDocument(result).toJson(QJsonDocument::Compact);
    std::printf("PHASE1_CROSS_MAP_UNDO_RESULT %s\n", json.constData());
    std::puts("PHASE1_CROSS_MAP_UNDO_PASS");
    return 0;
}

#include "moc_mapconnection.cpp"
#include "moc_cross_map_undo.cpp"
