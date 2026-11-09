#include <QByteArray>
#include <QCoreApplication>
#include <QFile>
#include <QFileDevice>
#include <QHash>
#include <QMap>
#include <QProcess>
#include <QStringList>
#include <QTemporaryDir>
#include <QUndoCommand>
#include <QUndoStack>
#include <QVector>

#include <cstdio>
#include <cstdlib>
#include <cerrno>
#include <sys/stat.h>
#include <unistd.h>

struct MapSectionEntry {
    int x = 0;
};

struct LayoutSquare {
    QString map_section;
};

struct Project {
    QHash<QString, MapSectionEntry> entries;
    bool sectionSaveResult = true;
    int sectionSaveCalls = 0;

    QHash<QString, MapSectionEntry> getRegionMapEntries() const { return entries; }
    void setRegionMapEntries(const QHash<QString, MapSectionEntry> &value) { entries = value; }
    bool saveRegionMapSections() {
        ++sectionSaveCalls;
        return sectionSaveResult;
    }
    int getLocationValue(const QString &) const { return 7; }
    bool saveTextFile(const QString &, const QString &) { return false; }
};

class RegionMap {
public:
    enum class LayoutFormat { None, Binary, CArray };

    Project *project = nullptr;
    QUndoStack editHistory;
    QString tilemap_path;
    QString layout_path;
    QString default_map_section = "MAPSEC_NONE";
    QByteArray tilemap_data;
    LayoutFormat layout_format = LayoutFormat::None;
    int layout_height = 1;
    int layout_width = 1;
    int offset_left = 0;
    int offset_top = 0;
    QString layout_array_label = "gRegionMap";
    QString layout_qualifiers = "const";
    QStringList layout_constants{"MAPSEC_NONE"};
    QStringList layout_layers{"main"};
    QMap<QString, QList<LayoutSquare>> layouts;

    QString fullPath(const QString &path) const { return path; }
    QByteArray getTilemap() const { return tilemap_data; }
    void setTilemap(const QByteArray &value) { tilemap_data = value; }
    QList<LayoutSquare> getLayout(const QString &layer) const { return layouts.value(layer); }

    void save();
    void saveTilemap();
    void saveLayout();
};

class EditTilemap : public QUndoCommand {
public:
    EditTilemap(RegionMap *map, QByteArray oldTilemap, QByteArray newTilemap,
                unsigned actionId, QUndoCommand *parent = nullptr);
    void redo() override;
    int id() const override { return 0; }

private:
    RegionMap *map;
    QByteArray oldTilemap;
    QByteArray newTilemap;
    unsigned actionId;
};

class RegionMapEditor {
public:
    Project *project = nullptr;
    QHash<QString, MapSectionEntry> region_map_entries;

    bool saveRegionMap(RegionMap *map);
    bool saveRegionMapEntries();
};

static void logError(const QString &) {}

PHASE1_INSERT_PINNED_FUNCTIONS

static void require(bool condition, const char *reason) {
    if (!condition) {
        std::fprintf(stderr, "PHASE1_REGIONMAP_FATAL %s\n", reason);
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
    require(arguments.size() == 6, "cold_read_argument_count");
    require(readFile(arguments[2]) == QByteArray::fromHex(arguments[4].toLatin1()),
            "cold_read_tilemap_mismatch");
    require(readFile(arguments[3]) == QByteArray::fromHex(arguments[5].toLatin1()),
            "cold_read_layout_mismatch");
    std::puts("PHASE1_REGIONMAP_COLD_READ_PASS");
}

static void verifyFreshProcess(const QString &tilemapPath, const QByteArray &tilemap,
                              const QString &layoutPath, const QByteArray &layout) {
    QProcess process;
    process.start(QCoreApplication::applicationFilePath(),
                  {"--cold-read", tilemapPath, layoutPath,
                   QString::fromLatin1(tilemap.toHex()),
                   QString::fromLatin1(layout.toHex())});
    require(process.waitForStarted(), "cold_process_start");
    require(process.waitForFinished(10000), "cold_process_timeout");
    require(process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0,
            "cold_process_failed");
    require(process.readAllStandardOutput().contains("PHASE1_REGIONMAP_COLD_READ_PASS"),
            "cold_process_witness_missing");
    std::puts("PHASE1_REGIONMAP_COLD_READ_PASS");
}

static void verifyFreshProcessRejectsMismatch(const QString &tilemapPath,
                                             const QString &layoutPath,
                                             const QByteArray &layout) {
    QProcess process;
    process.start(QCoreApplication::applicationFilePath(),
                  {"--cold-read", tilemapPath, layoutPath,
                   QString::fromLatin1(QByteArray("deliberately-wrong").toHex()),
                   QString::fromLatin1(layout.toHex())});
    require(process.waitForStarted(), "cold_negative_start");
    require(process.waitForFinished(10000), "cold_negative_timeout");
    require(process.exitStatus() == QProcess::NormalExit && process.exitCode() == 4,
            "cold_negative_not_rejected");
    require(process.readAllStandardError().contains("PHASE1_REGIONMAP_FATAL cold_read_tilemap_mismatch"),
            "cold_negative_reason_missing");
    std::puts("PHASE1_REGIONMAP_COLD_NEGATIVE_PASS");
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const QStringList arguments = app.arguments();
    if (arguments.size() > 1 && arguments[1] == "--cold-read") {
        coldRead(arguments);
        return 0;
    }

    require(::geteuid() != 0, "permission_probe_requires_nonroot");
    QTemporaryDir temporary;
    require(temporary.isValid(), "temporary_directory");

    Project project;
    RegionMap map;
    map.project = &project;
    map.tilemap_path = temporary.filePath("map.bin");
    map.layout_path = temporary.filePath("layout.bin");
    map.layout_format = RegionMap::LayoutFormat::Binary;
    LayoutSquare square;
    square.map_section = "MAPSEC_TEST";
    map.layouts["main"].append(square);

    {
        QFile tilemap(map.tilemap_path);
        require(tilemap.open(QIODevice::WriteOnly), "seed_tilemap_open");
        require(tilemap.write("old-tilemap") == 11, "seed_tilemap_write");
        tilemap.close();
        QFile layout(map.layout_path);
        require(layout.open(QIODevice::WriteOnly), "seed_layout_open");
        require(layout.write("old-layout") == 10, "seed_layout_write");
        layout.close();
    }

    RegionMapEditor editor;
    editor.project = &project;
    map.editHistory.push(new EditTilemap(&map, "old-tilemap", "saved-tilemap", 1));
    require(!map.editHistory.isClean(), "positive_edit_not_dirty");
    std::puts("PHASE1_REGIONMAP_STAGE positive_save");
    require(editor.saveRegionMap(&map), "positive_save_return");
    const QByteArray savedLayout(1, char(7));
    require(readFile(map.tilemap_path) == "saved-tilemap", "positive_tilemap_persisted");
    require(readFile(map.layout_path) == savedLayout, "positive_layout_persisted");
    require(map.editHistory.isClean(), "positive_history_not_clean");
    verifyFreshProcess(map.tilemap_path, "saved-tilemap",
                       map.layout_path, savedLayout);
    verifyFreshProcessRejectsMismatch(map.tilemap_path, map.layout_path, savedLayout);

    struct stat before {};
    require(::stat(map.layout_path.toLocal8Bit().constData(), &before) == 0,
            "layout_stat_before");
    const QByteArray oldLayout = readFile(map.layout_path);
    require(::chmod(map.layout_path.toLocal8Bit().constData(), S_IRUSR | S_IRGRP | S_IROTH) == 0,
            "layout_readonly_mode");
    QFile permissionControl(map.layout_path);
    errno = 0;
    const bool permissionOpen = permissionControl.open(QIODevice::WriteOnly);
    const int permissionErrno = errno;
    const auto permissionError = permissionControl.error();
    if (permissionOpen) permissionControl.close();
    const QString permissionText = permissionControl.errorString();
    require(!permissionOpen && permissionErrno == EACCES
                && permissionError != QFileDevice::NoError
                && permissionText == QStringLiteral("Permission denied"),
            "matched_permission_control");
    std::printf("PHASE1_REGIONMAP_PERMISSION errno=%d error=%d text=%s\n",
                permissionErrno, int(permissionError),
                permissionText.toLocal8Bit().constData());

    map.editHistory.push(new EditTilemap(&map, "saved-tilemap", "failed-layout-save", 2));
    require(!map.editHistory.isClean(), "failure_edit_not_dirty");
    std::puts("PHASE1_REGIONMAP_STAGE mixed_save_failure");
    require(editor.saveRegionMap(&map), "failure_wrapper_false_success_not_observed");
    require(readFile(map.tilemap_path) == "failed-layout-save",
            "tilemap_positive_side_of_mixed_save_missing");
    require(readFile(map.layout_path) == oldLayout, "failed_layout_bytes_changed");
    struct stat after {};
    require(::stat(map.layout_path.toLocal8Bit().constData(), &after) == 0,
            "layout_stat_after");
    require(before.st_dev == after.st_dev && before.st_ino == after.st_ino,
            "failed_layout_inode_changed");
    require(map.editHistory.isClean(), "failure_history_not_cleared");
    verifyFreshProcess(map.tilemap_path, "failed-layout-save",
                       map.layout_path, oldLayout);

    project.sectionSaveResult = false;
    const bool entriesReturn = editor.saveRegionMapEntries();
    require(project.sectionSaveCalls == 1, "section_save_call_missing");
    require(entriesReturn, "entries_wrapper_false_success_not_observed");

    require(::chmod(map.layout_path.toLocal8Bit().constData(), S_IRUSR | S_IWUSR) == 0,
            "restore_layout_permissions");
    std::printf(
        "PHASE1_REGIONMAP_RESULT {\"phase1_gate\":\"FAIL_INCOMPLETE\","
        "\"independent_approvals\":0,\"pinned_original_methods\":true,"
        "\"test_only_object_model\":true,\"qt_filesystem_and_undo_stack\":true,"
        "\"mixed_save_wrapper_reported_success\":true,"
        "\"tilemap_written_before_layout_failure\":true,"
        "\"failed_layout_bytes_and_inode_preserved\":true,"
        "\"undo_history_cleared_after_failure\":true,"
        "\"project_entries_wrapper_reported_success_on_injected_false\":true,"
        "\"permission_control_errno\":%d,\"permission_control_qt_error_code\":%d,"
        "\"permission_control_text\":\"Permission denied\","
        "\"fresh_process_file_readback\":true,\"fresh_process_wrong_bytes_rejected\":true,"
        "\"full_project_reopen_tested\":false,\"gui_interaction_tested\":false,"
        "\"application_rollback_observed\":false,\"hardware_durability_tested\":false}\n",
        permissionErrno, int(permissionError));
    return 0;
}
