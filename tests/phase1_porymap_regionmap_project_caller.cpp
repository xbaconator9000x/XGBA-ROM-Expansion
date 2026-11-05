#include <QApplication>
#include <QGraphicsPixmapItem>
#include <QGraphicsSceneMouseEvent>
#include <QHash>
#include <QPixmap>
#include <QUndoCommand>
#include <QUndoStack>

#include <cstdio>
#include <cstdlib>
#include <functional>

struct MapSectionEntry {
    bool valid = true;
    int x = 0;
    int y = 0;
    int width = 1;
    int height = 1;
};

class RegionMap {
public:
    QUndoStack editHistory;
    QHash<QString, MapSectionEntry> *region_map_entries = nullptr;
    int width = 6;
    int height = 6;

    void setEntries(QHash<QString, MapSectionEntry> *value) { region_map_entries = value; }
    MapSectionEntry getEntry(QString section);
    void setEntry(QString section, MapSectionEntry entry);
    int padLeft() const { return 1; }
    int padTop() const { return 1; }
    int tilemapWidth() const { return width; }
    int tilemapHeight() const { return height; }
    int getMapSquareIndex(int x, int y) const { return x + y * width; }
};

class SelectablePixmapItem : public QObject, public QGraphicsPixmapItem {
    Q_OBJECT
public:
    explicit SelectablePixmapItem(int cellWidth = 8, int cellHeight = 8)
        : cellWidth(cellWidth), cellHeight(cellHeight) {}
    virtual void draw() = 0;

protected:
    int cellWidth;
    int cellHeight;
    QPoint getCellPos(const QPointF &itemPos);
};

class RegionMapEntriesPixmapItem : public SelectablePixmapItem {
    Q_OBJECT
public:
    explicit RegionMapEntriesPixmapItem(RegionMap *map)
        : SelectablePixmapItem(8, 8), region_map(map) {}

    RegionMap *region_map;
    QString currentSection = QStringLiteral("MAPSEC_TEST");
    int pressedX = 0;
    int pressedY = 0;
    bool draggingEntry = false;
    int selectedTile = 0;
    std::function<void(int)> selected;

    void draw() override {}
    void select(int index) {
        selectedTile = index;
        if (selected) selected(index);
    }
    void press(QGraphicsSceneMouseEvent *event) { mousePressEvent(event); }
    void move(QGraphicsSceneMouseEvent *event) { mouseMoveEvent(event); }
    void release(QGraphicsSceneMouseEvent *event) { mouseReleaseEvent(event); }

signals:
    void entryPositionChanged(int, int);

protected:
    void mousePressEvent(QGraphicsSceneMouseEvent *event);
    void mouseMoveEvent(QGraphicsSceneMouseEvent *event);
    void mouseReleaseEvent(QGraphicsSceneMouseEvent *event);
};

class EditEntry : public QUndoCommand {
public:
    EditEntry(RegionMap *map, QString section, MapSectionEntry oldEntry,
              MapSectionEntry newEntry, QUndoCommand *parent = nullptr);
    void redo() override;
    void undo() override;
    bool mergeWith(const QUndoCommand *command) override;
    int id() const override { return 3; }

protected:
    RegionMap *map = nullptr;
    QString section;
    MapSectionEntry oldEntry;
    MapSectionEntry newEntry;
};

class RegionMapEditor {
public:
    RegionMap *region_map = nullptr;
    QHash<QString, MapSectionEntry> region_map_entries;
    RegionMapEntriesPixmapItem *region_map_entries_item = nullptr;
    QString activeEntry = QStringLiteral("MAPSEC_TEST");
    int optionUpdates = 0;

    void onRegionMapEntryDragged(int new_x, int new_y);
    void on_spinBox_RM_Entry_x_valueChanged(int x);
    void on_spinBox_RM_Entry_y_valueChanged(int y);
    void updateRegionMapEntryOptions(const QString &) { ++optionUpdates; }
};

PINNED_REGIONMAP_ENTRY_METHODS

static void require(bool condition, const char *reason) {
    if (!condition) {
        std::fprintf(stderr, "PHASE1_REGIONMAP_PROJECT_CALLER_FATAL %s\n", reason);
        std::exit(4);
    }
}

static bool sameEntry(const MapSectionEntry &left, const MapSectionEntry &right) {
    return left.valid == right.valid && left.x == right.x && left.y == right.y
        && left.width == right.width && left.height == right.height;
}

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    RegionMap map;
    RegionMapEditor editor;
    RegionMapEntriesPixmapItem item(&map);
    const MapSectionEntry original{true, 1, 1, 2, 2};
    editor.region_map = &map;
    editor.region_map_entries.insert(QStringLiteral("MAPSEC_TEST"), original);
    editor.region_map_entries_item = &item;
    map.setEntries(&editor.region_map_entries);
    map.editHistory.setClean();
    item.setPixmap(QPixmap(64, 64));

    int emittedMoves = 0;
    QObject::connect(&item, &RegionMapEntriesPixmapItem::entryPositionChanged,
                     [&editor, &emittedMoves](int x, int y) {
        ++emittedMoves;
        editor.onRegionMapEntryDragged(x, y);
    });

    QGraphicsSceneMouseEvent pressEvent(QEvent::GraphicsSceneMousePress);
    pressEvent.setPos(QPointF(16, 16));
    item.press(&pressEvent);
    require(item.draggingEntry && item.pressedX == 0 && item.pressedY == 0,
            "pinned_entry_press_selection");

    QGraphicsSceneMouseEvent moveEvent(QEvent::GraphicsSceneMouseMove);
    moveEvent.setPos(QPointF(24, 24));
    item.move(&moveEvent);
    const MapSectionEntry moved{true, 2, 2, 2, 2};
    require(emittedMoves == 1, "pinned_entry_signal_count");
    require(sameEntry(map.getEntry(QStringLiteral("MAPSEC_TEST")), moved),
            "pinned_editor_slot_applied_move");
    require(map.editHistory.count() == 1 && map.editHistory.index() == 1
                && !map.editHistory.isClean(),
            "pinned_undo_stack_dirty_after_move");

    map.editHistory.undo();
    require(sameEntry(map.getEntry(QStringLiteral("MAPSEC_TEST")), original)
                && sameEntry(editor.region_map_entries.value(QStringLiteral("MAPSEC_TEST")), original),
            "undo_restores_shared_project_entry_state");
    require(map.editHistory.isClean(), "undo_returns_to_clean_index");

    map.editHistory.redo();
    require(sameEntry(map.getEntry(QStringLiteral("MAPSEC_TEST")), moved)
                && sameEntry(editor.region_map_entries.value(QStringLiteral("MAPSEC_TEST")), moved),
            "redo_restores_shared_project_entry_state");

    QGraphicsSceneMouseEvent boundsEvent(QEvent::GraphicsSceneMouseMove);
    boundsEvent.setPos(QPointF(63, 63));
    item.move(&boundsEvent);
    require(emittedMoves == 1, "pinned_entry_bounds_rejected");

    QGraphicsSceneMouseEvent releaseEvent(QEvent::GraphicsSceneMouseRelease);
    item.release(&releaseEvent);
    require(!item.draggingEntry, "pinned_entry_release_clears_drag");
    item.move(&moveEvent);
    require(emittedMoves == 1, "move_after_release_rejected");

    std::puts(
        "PHASE1_REGIONMAP_PROJECT_CALLER_RESULT "
        "{\"phase1_gate\":\"FAIL_INCOMPLETE\",\"independent_approvals\":0,"
        "\"pinned_original_method_bodies\":true,"
        "\"native_qt_signal_dispatch\":true,\"test_only_object_model\":true,"
        "\"entry_drag_reaches_editor_undo_stack\":true,"
        "\"undo_restores_shared_entry_state\":true,\"redo_restores_moved_entry_state\":true,"
        "\"out_of_bounds_move_rejected\":true,\"move_after_release_rejected\":true,"
        "\"project_file_write_tested\":false,\"project_save_tested\":false,"
        "\"stale_disk_bytes_checked\":false,\"full_project_load_tested\":false,"
        "\"cold_project_reopen_tested\":false,\"application_failure_rollback_observed\":false,"
        "\"hardware_durability_tested\":false,\"gameplay_tested\":false,"
        "\"full_original_application_tested\":false}");
    return 0;
}
