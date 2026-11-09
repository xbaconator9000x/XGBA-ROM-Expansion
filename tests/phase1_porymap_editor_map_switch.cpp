#include <QCoreApplication>
#include <QList>
#include <QMap>
#include <QObject>
#include <QSet>
#include <QString>
#include <QUndoCommand>
#include <QUndoGroup>
#include <QUndoStack>

#include <cstdio>
#include <cstdlib>
#include <utility>

PINNED_COMMAND_ENUM_AND_MASKS

class MapConnection {
public:
    QString direction() const { return QStringLiteral("up"); }
};

int getConnectionDirectionMask(const QList<QString> &directions);

class Map : public QObject {
    Q_OBJECT
public:
    explicit Map(QString name) : m_name(std::move(name)), m_editHistory(new QUndoStack(this)) {}

    QUndoStack *editHistory() const { return m_editHistory; }
    QString getJsonFilepath() const { return m_name + QStringLiteral(".json"); }
    QString layoutId() const { return QStringLiteral("layout"); }
    void invalidateScripts() {}
    void pruneEditHistory();

signals:
    void openScriptRequested(const QString &path);
    void connectionAdded(MapConnection *connection);
    void connectionRemoved(MapConnection *connection);

private:
    QString m_name;
    QUndoStack *m_editHistory;
};

class Project : public QObject {
    Q_OBJECT
public:
    QMap<QString, Map *> maps;

    Map *loadMap(const QString &name) const { return maps.value(name, nullptr); }
    void stopFileWatch(const QString &) {}
    void watchFile(const QString &) {}
};

class Editor : public QObject {
    Q_OBJECT
public:
    Project *project = nullptr;
    Map *map = nullptr;
    QUndoGroup editGroup;
    QList<int> selectedEvents;

    void unsetMap();
    bool setMap(QString map_name);
    bool setLayout(QString) { return true; }
    bool displayMap() { return true; }
    void displayWildMonTables() {}
    void updateEvents() {}
    void clearMapEvents() {}
    void clearMapConnections() {}
    void openScript(QString) {}
    void displayConnection(MapConnection *) {}
    void removeConnectionPixmap(MapConnection *) {}
};

class MapConnectionMove : public QUndoCommand {
public:
    MapConnectionMove(MapConnection *connection, int *value, int oldValue, int newValue)
        : connection(connection), value(value), oldValue(oldValue), newValue(newValue) {}

    void redo() override { *value = newValue; }
    void undo() override { *value = oldValue; }
    int id() const override;

private:
    MapConnection *connection;
    int *value;
    int oldValue;
    int newValue;
};

class LaterEditCommand : public QUndoCommand {
public:
    LaterEditCommand(int *value, int oldValue, int newValue)
        : value(value), oldValue(oldValue), newValue(newValue) {}

    void redo() override { *value = newValue; }
    void undo() override { *value = oldValue; }
    int id() const override { return ID_PaintMetatile; }

private:
    int *value;
    int oldValue;
    int newValue;
};

class UnmaskedConnectionControl : public QUndoCommand {
public:
    int id() const override { return ID_MapConnectionMove; }
};

PINNED_DIRECTION_MASK_METHOD
PINNED_CONNECTION_MOVE_ID_METHOD
PINNED_MAP_PRUNE_METHOD
PINNED_EDITOR_MAP_METHODS

static void require(bool condition, const char *reason) {
    if (!condition) {
        std::fprintf(stderr, "PHASE1_EDITOR_MAP_SWITCH_FATAL %s\n", reason);
        std::exit(4);
    }
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    Project project;
    Map mapA(QStringLiteral("A"));
    Map mapB(QStringLiteral("B"));
    Map control(QStringLiteral("control"));
    project.maps.insert(QStringLiteral("A"), &mapA);
    project.maps.insert(QStringLiteral("B"), &mapB);

    control.editHistory()->push(new UnmaskedConnectionControl);
    control.pruneEditHistory();
    require(control.editHistory()->command(0)->isObsolete(),
            "unmasked_positive_control_is_pruned");

    Editor editor;
    editor.project = &project;
    require(editor.setMap(QStringLiteral("A")), "set_map_a");
    require(editor.map == &mapA && editor.editGroup.activeStack() == mapA.editHistory(),
            "editor_owns_active_a_history");

    MapConnection connection;
    int sharedValue = 0;
    mapA.editHistory()->push(
        new MapConnectionMove(&connection, &sharedValue, 0, 5));
    const int maskedId = mapA.editHistory()->command(0)->id();
    require(maskedId == (ID_MapConnectionMove | IDMask_ConnectionDirection_Up),
            "original_move_id_contains_direction_mask");
    require(sharedValue == 5, "a_command_initial_redo");

    require(editor.setMap(QStringLiteral("B")), "switch_to_map_b");
    require(mapA.editHistory()->command(0) && !mapA.editHistory()->command(0)->isObsolete(),
            "masked_a_history_survives_editor_unset");
    require(editor.map == &mapB && editor.editGroup.activeStack() == mapB.editHistory(),
            "editor_routes_undo_to_b_history");
    require(!editor.editGroup.canUndo(), "inactive_a_command_not_routed_while_b_active");

    mapB.editHistory()->push(new LaterEditCommand(&sharedValue, 5, 8));
    require(sharedValue == 8, "b_edit_applies_after_switch");
    require(editor.setMap(QStringLiteral("A")), "switch_back_to_map_a");
    require(editor.editGroup.activeStack() == mapA.editHistory()
            && editor.editGroup.canUndo(),
            "stale_a_history_becomes_active_again");

    editor.editGroup.undo();
    require(sharedValue == 0, "stale_a_undo_overwrites_later_b_edit");
    editor.editGroup.redo();
    require(sharedValue == 5, "stale_a_redo_reapplies_prior_a_value");

    std::printf(
        "PHASE1_EDITOR_MAP_SWITCH_RESULT {\"phase1_gate\":\"FAIL_INCOMPLETE\","
        "\"independent_approvals\":0,\"native_qt_qundo_group\":true,"
        "\"pinned_editor_set_unset_map_bodies\":true,"
        "\"pinned_map_prune_body\":true,\"pinned_connection_move_id_body\":true,"
        "\"masked_history_survives_switch\":true,\"unmasked_control_pruned\":true,"
        "\"inactive_stack_not_routed\":true,\"stale_history_reactivated\":true,"
        "\"undo_overwrite_observed\":true,\"redo_overwrite_observed\":true,"
        "\"full_gui\":false,\"project_json_persistence\":false,"
        "\"cold_reopen\":false,\"gameplay\":false}\n");
    return 0;
}

#include "moc_editor_map_switch.cpp"
