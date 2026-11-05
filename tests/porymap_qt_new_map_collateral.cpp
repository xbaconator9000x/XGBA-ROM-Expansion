// Phase 1 only: execute unchanged Porymap Project new-map save under native Qt.
// Test-only new maps and injected filesystem failures; not a MainWindow GUI test.
#include "project.h"
#include "config.h"
#include "map.h"
#include "mapconnection.h"
#include "loadingscreen.h"
#include <QApplication>
#include <QCoreApplication>
#include <QDir>
#include <QEventLoop>
#include <QFile>
#include <QFileSystemWatcher>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QThread>
#include <QElapsedTimer>
#include <cerrno>
#include <fcntl.h>
#include <signal.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <unistd.h>
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
static bool sameFileIdentity(const QString &path, const struct stat &expected) {
    struct stat actual {};
    const QByteArray nativePath = QFile::encodeName(path);
    return ::stat(nativePath.constData(), &actual) == 0 &&
           actual.st_dev == expected.st_dev && actual.st_ino == expected.st_ino;
}
static bool waitForSignal(int &signalCount, int expected, int timeoutMs = 4000) {
    QElapsedTimer timer;
    timer.start();
    while (signalCount < expected && timer.elapsed() < timeoutMs) {
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
        QThread::msleep(10);
    }
    return signalCount >= expected;
}
static void coldReopen(const QString &root) {
    need(projectConfig.load(root) && userConfig.load(root), "cold project configs");
    Project project;
    project.setRoot(root);
    MapConnection::project = &project;
    need(project.load(), "cold original Project load");
    const QStringList names = {
        "XGBAPhase1ScriptFailure", "XGBAPhase1MapJsonFailure",
        "XGBAPhase1EventEnospc", "XGBAPhase1PartialAppend"
    };
    QList<Map *> maps;
    for (const QString &name : names) {
        Map *map = project.loadMap(name);
        need(map != nullptr && map->isPersistedToFile(), "cold map load");
        maps.append(map);
    }
    const QString eventPath = root + "/" +
        projectConfig.getFilePath(ProjectFilePath::data_event_scripts);
    const QByteArray eventBytes = readBytes(eventPath);
    const auto include = [](const QString &name, const QString &suffix) {
        const QString folder = projectConfig.getFilePath(ProjectFilePath::data_map_folders) + name;
        return QString("\t.include \"%1/%2.inc\"").arg(folder, suffix).toUtf8();
    };
    const QByteArray includeA = include(names.at(0), "scripts");
    const QByteArray includeB = include(names.at(1), "scripts");
    const QByteArray includeC = include(names.at(2), "scripts");
    const QByteArray includeD = include(names.at(3), "scripts");
    need(occurrences(eventBytes, includeA) == 1, "cold script-failure include retained");
    need(occurrences(eventBytes, includeB) == 3, "cold retry duplicate includes retained");
    need(occurrences(eventBytes, includeC) == 0, "cold ENOSPC include absent");
    need(occurrences(eventBytes, includeD) == 0, "cold partial append rolled back");

    const QString folderA = root + "/" +
        projectConfig.getFilePath(ProjectFilePath::data_map_folders) + names.at(0);
    const QString folderB = root + "/" +
        projectConfig.getFilePath(ProjectFilePath::data_map_folders) + names.at(1);
    const QString folderC = root + "/" +
        projectConfig.getFilePath(ProjectFilePath::data_map_folders) + names.at(2);
    const QString folderD = root + "/" +
        projectConfig.getFilePath(ProjectFilePath::data_map_folders) + names.at(3);
    const QString extension = Project::getScriptFileExtension(projectConfig.usePoryScript);
    const QString scriptA = folderA + "/scripts" + extension;
    const QString scriptB = folderB + "/scripts" + extension;
    const QString scriptC = folderC + "/scripts" + extension;
    const QString scriptD = folderD + "/scripts" + extension;
    const QString textA = folderA + "/text" + extension;
    const QString textB = folderB + "/text" + extension;
    const QString textC = folderC + "/text" + extension;
    const QString textD = folderD + "/text" + extension;
    need(!QFileInfo::exists(scriptA), "cold failed script remains absent");
    need(QFileInfo(scriptB).isFile() && QFileInfo(scriptC).isFile() &&
         QFileInfo(scriptD).isFile() && QFileInfo(textA).isFile() &&
         QFileInfo(textB).isFile() && QFileInfo(textC).isFile() &&
         QFileInfo(textD).isFile(),
         "cold collateral files persisted");
    need(maps.at(2)->getScriptsFilepath() == scriptC, "cold script consumer path");
    need(maps.at(2)->getScriptLabels(Event::Group::None)
             .contains(names.at(2) + "_MapScripts"),
         "cold original script parser");

    Map *watchedMap = maps.at(3);
    const QString watchedScript = watchedMap->getScriptsFilepath();
    const QString watchedDir = QFileInfo(watchedScript).absolutePath();
    const QByteArray oldScriptBytes = readBytes(watchedScript);
    const QByteArray nativeScriptPath = QFile::encodeName(watchedScript);
    struct stat oldScriptStat {};
    need(::stat(nativeScriptPath.constData(), &oldScriptStat) == 0,
         "script snapshot stat");
    int scriptChangedSignals = 0;
    QObject::connect(watchedMap, &Map::scriptsModified, watchedMap,
                     [&scriptChangedSignals]() { ++scriptChangedSignals; });
    need(watchedMap->getScriptLabels(Event::Group::None)
             .contains(names.at(3) + "_MapScripts"),
         "script watcher initial parse");
    QFileSystemWatcher *scriptWatcher = watchedMap->findChild<QFileSystemWatcher *>();
    need(scriptWatcher && scriptWatcher->files().contains(watchedScript),
         "script watcher initial registration");

    QSaveFile failedReplacement(watchedScript);
    failedReplacement.setDirectWriteFallback(false);
    need(failedReplacement.open(QIODevice::WriteOnly), "script failed replacement open");
    const QByteArray failedBytes = oldScriptBytes + "\n";
    need(failedReplacement.write(failedBytes) == failedBytes.size(),
         "script failed replacement write");
    const auto oldPermissions = QFileInfo(watchedDir).permissions();
    const auto readOnlyDirectory = QFile::ReadOwner | QFile::ExeOwner |
                                   QFile::ReadGroup | QFile::ExeGroup |
                                   QFile::ReadOther | QFile::ExeOther;
    need(geteuid() != 0, "script permission test must be unprivileged");
    need(QFile::setPermissions(watchedDir, readOnlyDirectory),
         "script failed replacement permission injection");
    const QByteArray deniedPath = QFile::encodeName(watchedDir + "/permission-write-control");
    errno = 0;
    const int deniedFd = ::open(deniedPath.constData(), O_WRONLY | O_CREAT | O_EXCL, 0600);
    const int deniedErrno = errno;
    if (deniedFd >= 0) {
        ::close(deniedFd);
        ::unlink(deniedPath.constData());
    }
    const bool failedCommitAccepted = failedReplacement.commit();
    const auto failedCommitError = failedReplacement.error();
    const bool restoredPermissions = QFile::setPermissions(watchedDir, oldPermissions);
    need(!failedCommitAccepted, "script failed replacement commit unexpectedly succeeded");
    need(failedCommitError == QFileDevice::RenameError,
         "script failed replacement commit error was not RenameError");
    need(deniedFd < 0 && deniedErrno == EACCES,
         "script permission control did not fail with EACCES");
    need(restoredPermissions, "script directory permissions were not restored");
    need(readBytes(watchedScript) == oldScriptBytes &&
         sameFileIdentity(watchedScript, oldScriptStat),
         "script failed replacement preserves bytes and inode");
    need(scriptChangedSignals == 0, "failed replacement does not notify script watcher");

    QSaveFile successfulReplacement(watchedScript);
    successfulReplacement.setDirectWriteFallback(false);
    need(successfulReplacement.open(QIODevice::WriteOnly),
         "script atomic replacement open");
    const QByteArray replacementBytes = oldScriptBytes + "\n";
    need(successfulReplacement.write(replacementBytes) == replacementBytes.size(),
         "script atomic replacement write");
    need(successfulReplacement.commit(), "script atomic replacement commit");
    need(waitForSignal(scriptChangedSignals, 1),
         "script watcher receives atomic replacement");
    QFileSystemWatcher *afterReplacement = watchedMap->findChild<QFileSystemWatcher *>();
    const bool watcherDroppedAfterReplacement =
        !afterReplacement || !afterReplacement->files().contains(watchedScript);
    need(watcherDroppedAfterReplacement, "script watcher invalidated after replacement");
    struct stat replacementStat {};
    need(::stat(nativeScriptPath.constData(), &replacementStat) == 0 &&
         (replacementStat.st_dev != oldScriptStat.st_dev ||
          replacementStat.st_ino != oldScriptStat.st_ino),
         "script atomic replacement changed inode");
    need(readBytes(watchedScript) == replacementBytes,
         "script atomic replacement bytes");
    need(watchedMap->getScriptLabels(Event::Group::None)
             .contains(names.at(3) + "_MapScripts"),
         "script watcher re-read after replacement");
    QFileSystemWatcher *rearmedWatcher = watchedMap->findChild<QFileSystemWatcher *>();
    need(rearmedWatcher && rearmedWatcher->files().contains(watchedScript),
         "script watcher re-registered after read");

    QFile touch(watchedScript);
    const int signalsBeforeAppend = scriptChangedSignals;
    need(touch.open(QIODevice::WriteOnly | QIODevice::Append),
         "script post-rearm append open");
    need(touch.write("\n", 1) == 1 && touch.flush(),
         "script post-rearm append");
    touch.close();
    need(waitForSignal(scriptChangedSignals, signalsBeforeAppend + 1),
         "script post-rearm change delivered");
    need(watchedMap->getScriptLabels(Event::Group::None)
             .contains(names.at(3) + "_MapScripts"),
         "script parser after second change");
    rearmedWatcher = watchedMap->findChild<QFileSystemWatcher *>();
    need(rearmedWatcher && rearmedWatcher->files().contains(watchedScript),
         "script watcher re-registered after second change");

    QJsonObject out;
    out["fresh_process"] = true;
    out["original_project_reopened"] = true;
    out["four_maps_reloaded"] = true;
    out["script_failure_map_and_include_mixed_state"] = true;
    out["map_json_failure_retry_duplicate_include"] = true;
    out["event_enospc_map_saved_without_include"] = true;
    out["partial_append_fixture_rollback_verified"] = true;
    out["script_text_outputs_reloaded"] = true;
    out["original_script_parser_reloaded"] = true;
    out["qsavefile_permission_commit_rejected"] = true;
    out["qsavefile_failed_old_bytes_preserved"] = true;
    out["qsavefile_failed_old_inode_preserved"] = true;
    out["qsavefile_atomic_replace_committed"] = true;
    out["qsavefile_atomic_replace_new_inode"] = true;
    out["script_watcher_invalidated_after_replace"] = watcherDroppedAfterReplacement;
    out["script_watcher_rearmed_after_read"] = true;
    out["script_watcher_delivered_post_rearm_change"] = scriptChangedSignals >= 2;
    out["qsavefile_is_test_only"] = true;
    out["physical_durability_tested"] = false;
    out["phase1_gate"] = "FAIL_INCOMPLETE";
    out["independent_approvals"] = 0;
    std::cout << "PHASE1_TRANSACTION_COLD="
              << QJsonDocument(out).toJson(QJsonDocument::Compact).constData()
              << std::endl;
    MapConnection::project = nullptr;
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
    need(argc == 2 || (argc == 3 && QString::fromLocal8Bit(argv[2]) == "--cold-reopen"),
         "usage: test PROJECT_ROOT [--cold-reopen]");
    porysplash = new PorymapLoadingScreen;
    const QString root = QString::fromLocal8Bit(argv[1]);
    need(QFileInfo(root).isDir(), "project root absent");
    if (argc == 3) {
        coldReopen(root);
        delete porysplash;
        porysplash = nullptr;
        return 0;
    }
    need(projectConfig.load(root) && userConfig.load(root), "project configs failed");
    Project project;
    project.setRoot(root);
    MapConnection::project = &project;
    need(project.load(), "original Project load failed");
    Map *base = project.loadMap("PalletTown");
    need(base != nullptr, "original PalletTown load failed");
    need(projectConfig.createMapTextFileEnabled && !projectConfig.usePoryScript,
         "stock FireRed script/text mode");
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
    const int includeCountAfterBFailures = occurrences(readBytes(eventPath), includeB);
    const bool persistedBAfterFailures = !b->isPersistedToFile();
    need(QDir().rmdir(jsonB), "B map JSON failure directory cleanup");
    const bool recoveredSaveB = project.saveMap(b, true);
    need(recoveredSaveB && b->isPersistedToFile(), "B save after obstruction removal");
    need(occurrences(readBytes(eventPath), includeB) == 3,
         "B recovery retains duplicate includes");

    const QString nameC = "XGBAPhase1EventEnospc";
    Map *c = newMap(project, base, nameC);
    const QString folderC = projectConfig.getFilePath(ProjectFilePath::data_map_folders) + nameC;
    const QString dirC = root + "/" + folderC;
    const QString jsonC = c->getJsonFilepath();
    const QString scriptC = dirC + "/scripts" + Project::getScriptFileExtension(projectConfig.usePoryScript);
    const QString textC = dirC + "/text" + Project::getScriptFileExtension(projectConfig.usePoryScript);
    const QByteArray includeC = QString("\t.include \"%1/scripts.inc\"").arg(folderC).toUtf8();
    const QByteArray textIncludeC = QString("\t.include \"%1/text.inc\"").arg(folderC).toUtf8();
    const QByteArray eventBeforeC = readBytes(eventPath);
    struct stat eventStatBeforeC {};
    const QByteArray nativeEventPath = QFile::encodeName(eventPath);
    need(::stat(nativeEventPath.constData(), &eventStatBeforeC) == 0,
         "C event source stat");
    const QString eventBackupC = eventPath + ".phase1-transaction-backup";
    need(!QFileInfo::exists(eventBackupC) && QFile::rename(eventPath, eventBackupC),
         "C event source backup");
    QFile fullEvent("/dev/full");
    need(fullEvent.link(eventPath), "C event ENOSPC injection");
    need(QFileInfo(eventPath).canonicalFilePath() == QStringLiteral("/dev/full"),
         "C event ENOSPC target identity");
    QFile eventControl(eventPath);
    need(eventControl.open(QIODevice::Append), "C matched event control open");
    const qint64 eventControlBytes = eventControl.write("X", 1);
    const bool eventControlFlushed = eventControl.flush();
    const auto eventControlError = eventControl.error();
    eventControl.close();
    need((eventControlBytes < 0 || !eventControlFlushed) &&
         eventControlError != QFileDevice::NoError,
         "C matched event control reports ENOSPC");
    std::cerr << "PHASE1_TXN_ENOSPC_STAGE event_scripts.s" << std::endl;
    const bool saveC = project.saveMap(c, true);
    const bool persistedC = c->isPersistedToFile();
    const bool cleanC = !c->hasUnsavedChanges();
    need(QFile::remove(eventPath) && QFile::rename(eventBackupC, eventPath),
         "C event source restore");
    need(readBytes(eventPath) == eventBeforeC &&
         sameFileIdentity(eventPath, eventStatBeforeC),
         "C event bytes and inode restored");
    need(saveC && persistedC && QFileInfo(jsonC).isFile() &&
         QFileInfo(scriptC).isFile() && QFileInfo(textC).isFile() && cleanC,
         "C map and collateral files persist after event ENOSPC");
    need(occurrences(readBytes(eventPath), includeC) == 0 &&
         occurrences(readBytes(eventPath), textIncludeC) == 0,
         "C event includes absent after ENOSPC");

    const QString nameD = "XGBAPhase1PartialAppend";
    Map *d = newMap(project, base, nameD);
    const QString folderD = projectConfig.getFilePath(ProjectFilePath::data_map_folders) + nameD;
    const QString jsonD = d->getJsonFilepath();
    const QByteArray eventBeforeD = readBytes(eventPath);
    struct stat eventStatBeforeD {};
    need(::stat(nativeEventPath.constData(), &eventStatBeforeD) == 0,
         "D event source stat");
    struct rlimit originalLimit {};
    need(::getrlimit(RLIMIT_FSIZE, &originalLimit) == 0,
         "D get file-size resource limit");
    const rlim_t partialLimit = static_cast<rlim_t>(eventBeforeD.size() + 8);
    need(originalLimit.rlim_max == RLIM_INFINITY ||
         partialLimit <= originalLimit.rlim_max,
         "D file-size hard limit supports partial-write test");
    struct sigaction ignoreSigxfsz {};
    struct sigaction oldSigxfsz {};
    ignoreSigxfsz.sa_handler = SIG_IGN;
    sigemptyset(&ignoreSigxfsz.sa_mask);
    const bool sigactionInstalled =
        ::sigaction(SIGXFSZ, &ignoreSigxfsz, &oldSigxfsz) == 0;
    struct rlimit limited = originalLimit;
    limited.rlim_cur = partialLimit;
    const bool limitInstalled = sigactionInstalled &&
        ::setrlimit(RLIMIT_FSIZE, &limited) == 0;
    bool saveD = false;
    bool persistedD = false;
    QByteArray eventDuringD;
    bool limitRestored = false;
    bool sigactionRestored = false;
    if (limitInstalled) {
        std::cerr << "PHASE1_TXN_PARTIAL_STAGE event_scripts.s limit=8" << std::endl;
        saveD = project.saveMap(d, true);
        persistedD = d->isPersistedToFile();
        eventDuringD = readBytes(eventPath);
        limitRestored = ::setrlimit(RLIMIT_FSIZE, &originalLimit) == 0;
        sigactionRestored = ::sigaction(SIGXFSZ, &oldSigxfsz, nullptr) == 0;
    } else if (sigactionInstalled) {
        ::sigaction(SIGXFSZ, &oldSigxfsz, nullptr);
    }
    const QByteArray expectedPartialPrefix =
        QString("\n\t.include \"%1/scripts.inc\"").arg(folderD).toUtf8().left(8);
    const bool partialAppendObserved =
        eventDuringD.size() == eventBeforeD.size() + 8 &&
        eventDuringD.left(eventBeforeD.size()) == eventBeforeD &&
        eventDuringD.mid(eventBeforeD.size()) == expectedPartialPrefix;
    QFile eventRestore(eventPath);
    const bool eventRestoreOpened = eventRestore.open(QIODevice::ReadWrite);
    const bool eventRestoreResized = eventRestoreOpened &&
        eventRestore.resize(eventBeforeD.size()) && eventRestore.flush();
    eventRestore.close();
    const bool partialRollback =
        eventRestoreResized && readBytes(eventPath) == eventBeforeD &&
        sameFileIdentity(eventPath, eventStatBeforeD);
    need(limitInstalled && limitRestored && sigactionRestored && saveD && persistedD &&
         QFileInfo(jsonD).isFile() && !d->hasUnsavedChanges() &&
         partialAppendObserved && partialRollback,
         "D partial append and byte/inode rollback");

    const QByteArray groupPath = QFile::encodeName(
        root + "/" + projectConfig.getFilePath(ProjectFilePath::json_map_groups));
    const QString groupsFile = QString::fromLocal8Bit(groupPath);
    const QByteArray groupsBefore = readBytes(groupsFile);
    struct stat groupsBeforeSaveAll {};
    need(::stat(groupPath.constData(), &groupsBeforeSaveAll) == 0,
         "map groups original stat");
    const bool saveAll = project.saveAll();
    need(saveAll, "original Project::saveAll after mixed collateral states");
    const QByteArray groupsAfter = readBytes(groupsFile);
    const QByteArray eventAfterSaveAll = readBytes(eventPath);
    need(eventAfterSaveAll == eventBeforeD &&
         sameFileIdentity(eventPath, eventStatBeforeD),
         "Save All leaves restored event source unchanged");
    need(groupsAfter != groupsBefore && sameFileIdentity(groupsFile, groupsBeforeSaveAll),
         "Save All updates map groups without replacing its source inode");
    need(groupsAfter.contains(nameA.toUtf8()) && groupsAfter.contains(nameB.toUtf8()) &&
         groupsAfter.contains(nameC.toUtf8()) && groupsAfter.contains(nameD.toUtf8()),
         "Save All publishes persisted maps to map groups");

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
    out["case_b_persisted_flag_false"] = persistedBAfterFailures;
    out["case_b_event_include_count_after_retry"] = includeCountAfterBFailures;
    out["native_qt_project"] = true;
    out["real_gui_new_map"] = false;
    out["physical_durability_tested"] = false;
    out["phase1_gate"] = "FAIL_INCOMPLETE";
    out["independent_approvals"] = 0;
    std::cout << "PHASE1_NEW_MAP_QT=" << QJsonDocument(out).toJson(QJsonDocument::Compact).constData() << std::endl;
    QJsonObject transaction;
    transaction["native_original_project"] = true;
    transaction["synthetic_new_maps"] = true;
    transaction["case_c_event_enospc_write_attempted"] = true;
    transaction["case_c_original_event_bytes_and_inode_preserved"] = true;
    transaction["case_c_map_json_script_text_saved_without_include"] =
        saveC && persistedC && QFileInfo(jsonC).isFile() &&
        QFileInfo(scriptC).isFile() && QFileInfo(textC).isFile() && cleanC;
    transaction["case_d_partial_append_observed"] = partialAppendObserved;
    transaction["case_d_partial_append_bytes"] = 8;
    transaction["case_d_map_saved_clean_after_partial_append"] =
        saveD && persistedD && !d->hasUnsavedChanges();
    transaction["case_d_original_event_bytes_and_inode_restored"] = partialRollback;
    transaction["save_all_published_persisted_maps"] = saveAll;
    transaction["text_file_branch_enabled"] = projectConfig.createMapTextFileEnabled;
    transaction["poryscript_mode"] = projectConfig.usePoryScript;
    transaction["poryscript_runtime_exercised"] = false;
    transaction["host_filesystem_only"] = true;
    transaction["physical_durability_tested"] = false;
    transaction["phase1_gate"] = "FAIL_INCOMPLETE";
    transaction["independent_approvals"] = 0;
    std::cout << "PHASE1_TRANSACTION_NATIVE="
              << QJsonDocument(transaction).toJson(QJsonDocument::Compact).constData()
              << std::endl;
    MapConnection::project = nullptr;
    delete porysplash;
    porysplash = nullptr;
    return 0;
}
