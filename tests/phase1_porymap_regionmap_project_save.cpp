#include <QApplication>
#include <QFile>
#include <QFileDevice>
#include <QGraphicsPixmapItem>
#include <QGraphicsSceneMouseEvent>
#include <QHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QProcess>
#include <QTemporaryDir>
#include <QUndoCommand>
#include <QUndoGroup>
#include <QUndoStack>

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <sys/stat.h>
#include <unistd.h>

struct MapSectionEntry {
    bool valid = true;
    int x = 0;
    int y = 0;
    int width = 1;
    int height = 1;
};

struct LayoutSquare {
    QString map_section;
};

struct LocationData {
    QString displayName;
    MapSectionEntry map;
    QJsonObject custom;
};

enum class ProjectFilePath { json_region_map_entries };

struct ProjectConfig {
    QString getFilePath(ProjectFilePath) const { return QStringLiteral("region_map_sections.json"); }
};

static ProjectConfig projectConfig;
static QString sectionOutputPath;
static qint64 sectionWriteResult = 0;
static bool sectionFlushResult = true;
static int sectionWriteError = 0;
static int sectionWriteErrno = 0;

class OrderedJson : public QJsonObject {
public:
    using object = QJsonObject;
    using array = QJsonArray;

    OrderedJson() = default;
    explicit OrderedJson(const object &value) : QJsonObject(value) {}

    static void append(object *target, const object &custom) {
        for (auto it = custom.constBegin(); it != custom.constEnd(); ++it)
            target->insert(it.key(), it.value());
    }
};

class OrderedJsonDoc {
public:
    explicit OrderedJsonDoc(OrderedJson *json) : json(json) {}

    void dump(QFile *file) {
        const QByteArray bytes = QJsonDocument(*json).toJson(QJsonDocument::Indented);
        const qint64 written = file->write(bytes);
        const bool flushed = file->flush();
        if (file->fileName() == sectionOutputPath) {
            sectionWriteResult = written;
            sectionFlushResult = flushed;
            sectionWriteError = int(file->error());
            sectionWriteErrno = errno;
        }
    }

private:
    OrderedJson *json;
};

class Project {
public:
    QString root;
    QHash<QString, MapSectionEntry> entries;
    QMap<QString, LocationData> locationData;
    QStringList mapSectionIdNamesSaveOrder;
    QJsonObject customMapSectionsData;

    QHash<QString, MapSectionEntry> getRegionMapEntries() const { return entries; }
    void setRegionMapEntries(const QHash<QString, MapSectionEntry> &value);
    bool saveRegionMapSections();
    int getLocationValue(const QString &) const { return 7; }
    bool saveTextFile(const QString &, const QString &) { return false; }
    void ignoreWatchedFileTemporarily(const QString &) {}
};

class RegionMap {
public:
    enum class LayoutFormat { None, Binary, CArray };

    QUndoStack editHistory;
    QHash<QString, MapSectionEntry> *region_map_entries = nullptr;
    Project *project = nullptr;
    int width = 6;
    int height = 6;
    QString tilemap_path;
    QString layout_path;
    QString default_map_section = QStringLiteral("MAPSEC_NONE");
    QByteArray tilemap_data;
    LayoutFormat layout_format = LayoutFormat::Binary;
    int layout_height = 1;
    int layout_width = 1;
    int offset_left = 0;
    int offset_top = 0;
    QString layout_array_label = QStringLiteral("gRegionMap");
    QString layout_qualifiers = QStringLiteral("const");
    QStringList layout_constants{QStringLiteral("MAPSEC_NONE")};
    QStringList layout_layers{QStringLiteral("main")};
    QMap<QString, QList<LayoutSquare>> layouts;

    void setEntries(QHash<QString, MapSectionEntry> *value) { region_map_entries = value; }
    MapSectionEntry getEntry(QString section);
    void setEntry(QString section, MapSectionEntry entry);
    int padLeft() const { return 1; }
    int padTop() const { return 1; }
    int tilemapWidth() const { return width; }
    int tilemapHeight() const { return height; }
    int getMapSquareIndex(int x, int y) const { return x + y * width; }
    QString fullPath(const QString &path) const { return path; }
    QByteArray getTilemap() const { return tilemap_data; }
    void setTilemap(const QByteArray &value) { tilemap_data = value; }
    QList<LayoutSquare> getLayout(const QString &layer) const { return layouts.value(layer); }
    QJsonObject config() const { return {{QStringLiteral("alias"), QStringLiteral("test")}}; }
    void save();
    void saveTilemap();
    void saveLayout();
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
    void draw() override {}
    void select(int index) { selectedTile = index; }
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
    Project *project = nullptr;
    QHash<QString, MapSectionEntry> region_map_entries;
    RegionMapEntriesPixmapItem *region_map_entries_item = nullptr;
    RegionMap *region_map = nullptr;
    QString activeEntry = QStringLiteral("MAPSEC_TEST");
    QUndoGroup history;
    std::map<QString, RegionMap *> region_maps;
    QString configFilepath;
    bool configSaved = false;

    void onRegionMapEntryDragged(int new_x, int new_y);
    void on_spinBox_RM_Entry_x_valueChanged(int x);
    void on_spinBox_RM_Entry_y_valueChanged(int y);
    void updateRegionMapEntryOptions(const QString &) {}
    bool saveRegionMap(RegionMap *map);
    bool saveRegionMapEntries();
    void saveConfig();
    void on_actionSave_All_triggered();
};

static void logError(const QString &) {}

PINNED_REGIONMAP_PROJECT_SAVE_METHODS

static void require(bool condition, const char *reason) {
    if (!condition) {
        std::fprintf(stderr, "PHASE1_REGIONMAP_PROJECT_SAVE_FATAL %s\n", reason);
        std::exit(4);
    }
}

static QByteArray readFile(const QString &path) {
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "read_file_open");
    const QByteArray bytes = file.readAll();
    file.close();
    return bytes;
}

static void coldRead(const QStringList &arguments) {
    require(arguments.size() == 10, "cold_read_argument_count");
    require(readFile(arguments[2]) == QByteArray::fromHex(arguments[3].toLatin1()),
            "cold_read_sections_mismatch");
    require(readFile(arguments[4]) == QByteArray::fromHex(arguments[5].toLatin1()),
            "cold_read_map_one_mismatch");
    require(readFile(arguments[6]) == QByteArray::fromHex(arguments[7].toLatin1()),
            "cold_read_map_two_mismatch");
    require(readFile(arguments[8]) == QByteArray::fromHex(arguments[9].toLatin1()),
            "cold_read_config_mismatch");
    std::puts("PHASE1_REGIONMAP_PROJECT_SAVE_COLD_READ_PASS");
}

static void verifyFreshProcess(const QString &sectionsPath, const QByteArray &sections,
                               const QString &mapOnePath, const QByteArray &mapOne,
                               const QString &mapTwoPath, const QByteArray &mapTwo,
                               const QString &configPath, const QByteArray &config) {
    QProcess process;
    process.start(QCoreApplication::applicationFilePath(),
                  {"--cold-read", sectionsPath, QString::fromLatin1(sections.toHex()),
                   mapOnePath, QString::fromLatin1(mapOne.toHex()),
                   mapTwoPath, QString::fromLatin1(mapTwo.toHex()),
                   configPath, QString::fromLatin1(config.toHex())});
    require(process.waitForStarted(), "cold_process_start");
    require(process.waitForFinished(10000), "cold_process_timeout");
    require(process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0,
            "cold_process_failed");
    require(process.readAllStandardOutput().contains(
                "PHASE1_REGIONMAP_PROJECT_SAVE_COLD_READ_PASS"),
            "cold_process_witness_missing");
}

static void verifyFreshProcessRejectsMismatch(const QString &sectionsPath,
                                              const QString &mapOnePath,
                                              const QByteArray &mapOne,
                                              const QString &mapTwoPath,
                                              const QByteArray &mapTwo,
                                              const QString &configPath,
                                              const QByteArray &config) {
    QProcess process;
    process.start(QCoreApplication::applicationFilePath(),
                  {"--cold-read", sectionsPath, QStringLiteral("00"),
                   mapOnePath, QString::fromLatin1(mapOne.toHex()),
                   mapTwoPath, QString::fromLatin1(mapTwo.toHex()),
                   configPath, QString::fromLatin1(config.toHex())});
    require(process.waitForStarted(), "cold_negative_start");
    require(process.waitForFinished(10000), "cold_negative_timeout");
    require(process.exitStatus() == QProcess::NormalExit && process.exitCode() == 4,
            "cold_negative_not_rejected");
    require(process.readAllStandardError().contains(
                "PHASE1_REGIONMAP_PROJECT_SAVE_FATAL cold_read_sections_mismatch"),
            "cold_negative_reason_missing");
}

static void seedFile(const QString &path, const QByteArray &bytes) {
    QFile file(path);
    require(file.open(QIODevice::WriteOnly), "seed_file_open");
    require(file.write(bytes) == bytes.size(), "seed_file_write");
    file.close();
}

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    const QStringList arguments = app.arguments();
    if (arguments.size() > 1 && arguments[1] == "--cold-read") {
        coldRead(arguments);
        return 0;
    }

    require(::geteuid() != 0, "enospc_probe_requires_nonroot");
    QTemporaryDir temporary;
    require(temporary.isValid(), "temporary_directory");

    Project project;
    project.root = temporary.path();
    project.mapSectionIdNamesSaveOrder = {QStringLiteral("MAPSEC_TEST")};
    LocationData location;
    location.displayName = QStringLiteral("Test Section");
    project.locationData.insert(QStringLiteral("MAPSEC_TEST"), location);

    RegionMap mapOne;
    RegionMap mapTwo;
    mapOne.project = &project;
    mapTwo.project = &project;
    mapOne.setEntries(&project.entries);
    mapTwo.setEntries(&project.entries);
    mapOne.tilemap_path = temporary.filePath("map-one.bin");
    mapOne.layout_path = temporary.filePath("map-one-layout.bin");
    mapTwo.tilemap_path = temporary.filePath("map-two.bin");
    mapTwo.layout_path = temporary.filePath("map-two-layout.bin");
    mapOne.layouts["main"].append({QStringLiteral("MAPSEC_TEST")});
    mapTwo.layouts["main"].append({QStringLiteral("MAPSEC_TEST")});
    mapOne.tilemap_data = QByteArrayLiteral("map-one-before");
    mapTwo.tilemap_data = QByteArrayLiteral("map-two-before");
    seedFile(mapOne.tilemap_path, mapOne.tilemap_data);
    seedFile(mapOne.layout_path, QByteArrayLiteral("old-layout"));
    seedFile(mapTwo.tilemap_path, mapTwo.tilemap_data);
    seedFile(mapTwo.layout_path, QByteArrayLiteral("old-layout"));

    RegionMapEditor editor;
    editor.project = &project;
    editor.region_map_entries.insert(
        QStringLiteral("MAPSEC_TEST"), MapSectionEntry{true, 1, 1, 2, 2});
    project.entries = editor.region_map_entries;
    project.locationData[QStringLiteral("MAPSEC_TEST")].map =
        editor.region_map_entries.value(QStringLiteral("MAPSEC_TEST"));
    editor.region_map = &mapOne;
    mapOne.setEntries(&editor.region_map_entries);
    mapTwo.setEntries(&editor.region_map_entries);
    editor.region_maps.emplace(QStringLiteral("one"), &mapOne);
    editor.region_maps.emplace(QStringLiteral("two"), &mapTwo);
    editor.configFilepath = temporary.filePath("region-map-config.json");
    editor.history.addStack(&mapOne.editHistory);
    editor.history.addStack(&mapTwo.editHistory);
    editor.history.setActiveStack(&mapOne.editHistory);

    RegionMapEntriesPixmapItem item(&mapOne);
    editor.region_map_entries_item = &item;
    item.setPixmap(QPixmap(64, 64));
    QObject::connect(&item, &RegionMapEntriesPixmapItem::entryPositionChanged,
                     [&editor](int x, int y) { editor.onRegionMapEntryDragged(x, y); });

    QGraphicsSceneMouseEvent pressEvent(QEvent::GraphicsSceneMousePress);
    pressEvent.setPos(QPointF(16, 16));
    item.press(&pressEvent);
    QGraphicsSceneMouseEvent moveEvent(QEvent::GraphicsSceneMouseMove);
    moveEvent.setPos(QPointF(24, 24));
    item.move(&moveEvent);
    const MapSectionEntry firstMove{true, 2, 2, 2, 2};
    require(mapOne.editHistory.count() == 1 && !mapOne.editHistory.isClean(),
            "map_one_drag_not_owned_by_undo_stack");
    require(mapTwo.getEntry(QStringLiteral("MAPSEC_TEST")).x == firstMove.x
                && mapTwo.getEntry(QStringLiteral("MAPSEC_TEST")).y == firstMove.y,
            "map_two_did_not_observe_shared_entry_hash");

    editor.region_map = &mapTwo;
    item.region_map = &mapTwo;
    editor.history.setActiveStack(&mapTwo.editHistory);
    editor.onRegionMapEntryDragged(3, 3);
    require(mapTwo.editHistory.count() == 1 && !mapTwo.editHistory.isClean(),
            "map_two_edit_not_owned_by_undo_stack");

    editor.history.setActiveStack(&mapOne.editHistory);
    editor.history.undo();
    require(editor.region_map_entries.value(QStringLiteral("MAPSEC_TEST")).x == 1,
            "map_one_undo_did_not_restore_shared_state");
    require(!mapTwo.editHistory.isClean(), "map_two_history_lost_after_map_one_undo");
    editor.history.setActiveStack(&mapTwo.editHistory);
    editor.history.undo();
    require(mapOne.editHistory.isClean() && mapTwo.editHistory.isClean(),
            "cross_map_undo_stacks_not_clean");
    require(editor.region_map_entries.value(QStringLiteral("MAPSEC_TEST")).x == 2,
            "cross_map_undo_state_fingerprint_changed");

    editor.onRegionMapEntryDragged(4, 4);
    const QString sectionsPath = project.root + "/" +
        projectConfig.getFilePath(ProjectFilePath::json_region_map_entries);
    sectionOutputPath = sectionsPath;
    const QString backupPath = temporary.filePath("region-map-sections.backup");
    std::puts("PHASE1_REGIONMAP_PROJECT_SAVE_STAGE positive_save_all");
    editor.on_actionSave_All_triggered();
    require(editor.saveRegionMapEntries(), "positive_entry_save_wrapper_failed");
    require(readFile(mapOne.tilemap_path) == mapOne.tilemap_data,
            "positive_map_one_tilemap_missing");
    require(readFile(mapTwo.tilemap_path) == mapTwo.tilemap_data,
            "positive_map_two_tilemap_missing");
    require(readFile(mapOne.layout_path) == QByteArray(1, char(7))
                && readFile(mapTwo.layout_path) == QByteArray(1, char(7)),
            "positive_layout_outputs_missing");
    const QByteArray savedSections = readFile(sectionsPath);
    QJsonParseError jsonError;
    const QJsonDocument savedDocument = QJsonDocument::fromJson(savedSections, &jsonError);
    require(jsonError.error == QJsonParseError::NoError
                && savedDocument.object().value(QStringLiteral("map_sections"))
                    .toArray().first().toObject().value(QStringLiteral("x")).toInt() == 4,
            "positive_project_regionmap_sections_missing");
    require(mapOne.editHistory.isClean() && mapTwo.editHistory.isClean(),
            "positive_save_all_did_not_clean_histories");
    const QByteArray savedConfig = readFile(editor.configFilepath);
    verifyFreshProcess(sectionsPath, savedSections, mapOne.tilemap_path, mapOne.tilemap_data,
                       mapTwo.tilemap_path, mapTwo.tilemap_data,
                       editor.configFilepath, savedConfig);
    verifyFreshProcessRejectsMismatch(sectionsPath, mapOne.tilemap_path, mapOne.tilemap_data,
                                      mapTwo.tilemap_path, mapTwo.tilemap_data,
                                      editor.configFilepath, savedConfig);
    const QString validProjectRoot = project.root;
    project.root = temporary.filePath("missing-project-root");
    const bool openFailureWrapper = editor.saveRegionMapEntries();
    require(openFailureWrapper, "project_open_failure_not_ignored_by_entry_wrapper");
    project.root = validProjectRoot;

    editor.onRegionMapEntryDragged(5, 5);
    mapOne.tilemap_data = QByteArrayLiteral("map-one-after-failure");
    mapTwo.tilemap_data = QByteArrayLiteral("map-two-after-failure");
    struct stat before {};
    require(::stat(sectionsPath.toLocal8Bit().constData(), &before) == 0,
            "section_stat_before_failure");
    require(QFile::rename(sectionsPath, backupPath), "section_backup_rename");
    QFile full(QStringLiteral("/dev/full"));
    require(full.link(sectionsPath), "inject_dev_full_link");
    QFile control(sectionsPath);
    errno = 0;
    require(control.open(QIODevice::WriteOnly), "matched_enospc_control_open");
    const qint64 controlWrite = control.write("X", 1);
    const bool controlFlush = control.flush();
    const int controlErrno = errno;
    const QFileDevice::FileError controlError = control.error();
    control.close();
    require((controlWrite < 0 || !controlFlush) && controlError != QFileDevice::NoError
                && controlErrno == ENOSPC,
            "matched_enospc_control");

    std::puts("PHASE1_REGIONMAP_PROJECT_SAVE_STAGE enospc_save_all");
    editor.on_actionSave_All_triggered();
    require(!sectionFlushResult && sectionWriteError != int(QFileDevice::NoError)
                && sectionWriteErrno == ENOSPC,
            "actual_project_writer_enospc_not_observed");
    require(editor.saveRegionMapEntries(),
            "pinned_entries_wrapper_no_longer_reports_success_on_project_write_error");
    require(!sectionFlushResult && sectionWriteErrno == ENOSPC,
            "repeated_project_writer_enospc_not_observed");
    require(mapOne.editHistory.isClean() && mapTwo.editHistory.isClean(),
            "save_all_failure_history_state_changed");

    require(QFile::remove(sectionsPath), "remove_dev_full_link");
    require(QFile::rename(backupPath, sectionsPath), "restore_section_fixture");
    struct stat after {};
    require(::stat(sectionsPath.toLocal8Bit().constData(), &after) == 0,
            "section_stat_after_restore");
    require(before.st_dev == after.st_dev && before.st_ino == after.st_ino,
            "restored_section_inode_changed");
    require(readFile(sectionsPath) == savedSections,
            "restored_section_bytes_changed");
    require(readFile(mapOne.tilemap_path) == mapOne.tilemap_data
                && readFile(mapTwo.tilemap_path) == mapTwo.tilemap_data,
            "cross_file_partial_commit_missing");
    require(editor.region_map_entries.value(QStringLiteral("MAPSEC_TEST")).x == 5,
            "in_memory_entry_reverted_without_application_rollback");
    verifyFreshProcess(sectionsPath, savedSections, mapOne.tilemap_path, mapOne.tilemap_data,
                       mapTwo.tilemap_path, mapTwo.tilemap_data,
                       editor.configFilepath, savedConfig);

    std::printf(
        "PHASE1_REGIONMAP_PROJECT_SAVE_RESULT "
        "{\"phase1_gate\":\"FAIL_INCOMPLETE\",\"independent_approvals\":0,"
        "\"pinned_original_method_bodies\":true,\"native_qt_file_io\":true,"
        "\"test_only_project_and_serializer_shells\":true,"
        "\"original_regionmap_save_all_called\":true,"
        "\"original_regionmap_asset_writers_called\":true,"
        "\"original_project_setter_and_writer_called\":true,"
        "\"original_entry_save_wrapper_called\":true,"
        "\"cross_map_undo_group_stacks_exercised\":true,"
        "\"cross_map_undo_shared_state_fingerprint_observed\":true,"
        "\"positive_multi_file_save_observed\":true,"
        "\"project_open_failure_wrapper_reports_success\":%s,"
        "\"enospc_control_errno\":%d,\"project_writer_write_result\":%lld,"
        "\"project_writer_flush_failed\":%s,\"project_writer_errno\":%d,"
        "\"project_writer_error\":%d,"
        "\"project_save_wrapper_reports_success_after_enospc\":true,"
        "\"map_assets_persist_after_project_json_failure\":true,"
        "\"test_fixture_restoration_used\":true,"
        "\"application_rollback_observed\":false,"
        "\"fresh_process_byte_readback\":true,"
        "\"cold_project_load_tested\":false,\"gui_interaction_tested\":false,"
        "\"orderedjson_implementation_tested\":false,"
        "\"short_write_tested\":false,\"hardware_durability_tested\":false,"
        "\"gameplay_tested\":false}",
        openFailureWrapper ? "true" : "false", controlErrno,
        static_cast<long long>(sectionWriteResult),
        sectionFlushResult ? "false" : "true",
        sectionWriteErrno, sectionWriteError);
    return 0;
}

#include "moc_regionmap_project_save.cpp"
