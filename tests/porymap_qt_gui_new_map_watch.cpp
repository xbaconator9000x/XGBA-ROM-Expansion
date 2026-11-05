// Phase 1: unchanged pinned Porymap MainWindow QAction -> NewMapDialog ->
// Project::createNewMap -> Editor::setMap -> QAction Save; native Qt6.
// Test-only project copy and /dev/full failure. Not independent approval.
#include "mainwindow.h"
#include "newmapdialog.h"
#include "editor.h"
#include "project.h"
#include "config.h"
#include "map.h"
#include "loadingscreen.h"
#include <QApplication>
#include <QAction>
#include <QAbstractButton>
#include <QComboBox>
#include <QDir>
#include <QDialogButtonBox>
#include <QEvent>
#include <QFile>
#include <QFileInfo>
#include <QFileSystemWatcher>
#include <QMessageBox>
#include <QPointer>
#include <QSaveFile>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QThread>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QLineEdit>
#include <QStandardPaths>
#include <iostream>
#include <cstdlib>
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

static void need(bool b, const char *why) {
    if (!b) { std::cerr << "FAIL " << why << std::endl; std::_Exit(3); }
}
static QByteArray bytes(const QString &p) {
    QFile f(p); need(f.open(QIODevice::ReadOnly), "read_file");
    return f.readAll();
}
static int count(const QByteArray &s, const QByteArray &n) {
    int hits=0, i=0;
    while ((i=s.indexOf(n,i))>=0) { ++hits; i+=n.size(); }
    return hits;
}
int main(int argc,char **argv) {
    QApplication app(argc,argv);
    QStandardPaths::setTestModeEnabled(true);
    const bool coldReopen=argc==3 &&
        QString::fromLocal8Bit(argv[2])==QStringLiteral("--cold-reopen");
    need(argc==2 || coldReopen,"usage_PROJECT_ROOT");
    porysplash=new PorymapLoadingScreen;
    const QString root=QString::fromLocal8Bit(argv[1]);
    need(QFileInfo(root).isDir(),"project_root");
    need(projectConfig.load(root) && userConfig.load(root),"project_configs");
    QCoreApplication::setOrganizationName("pret");
    QCoreApplication::setApplicationName("porymap");
    porymapConfig.load();
    porymapConfig.addRecentProject(root);
    porymapConfig.reopenOnLaunch=true;
    porymapConfig.projectManuallyClosed=false;
    porymapConfig.checkForUpdates=false;
    porymapConfig.showProjectLoadingScreen=false;
    porymapConfig.shownInGameReloadMessage=true;
    porymapConfig.monitorFiles=true;
    need(porymapConfig.save(),"startup_config");
    if(coldReopen) {
        MainWindow window(nullptr);
        window.initialize();
        need(window.editor && window.editor->project,"cold_reopen_project");
        const QString name="XGBAPhase1GuiNewMapFailure";
        const QString json=root+"/data/maps/"+name+"/map.json";
        need(window.editor->setMap(name),"cold_reopen_new_map");
        Map *map=window.editor->map;
        need(map && map->isPersistedToFile(),"cold_reopen_persisted_map");
        QJsonParseError error;
        const QJsonDocument doc=QJsonDocument::fromJson(bytes(json),&error);
        need(error.error==QJsonParseError::NoError &&
             doc.object().value("name").toString()==name,"cold_reopen_disk_json");
        QFileSystemWatcher *watcher=window.editor->project->findChild<QFileSystemWatcher*>();
        need(watcher && watcher->files().contains(json),"cold_reopen_watcher");
        QJsonObject out;
        out["fresh_process"]=true;
        out["original_mainwindow_project_reopened"]=true;
        out["new_map_reloaded"]=true;
        out["map_json_valid"]=true;
        out["watcher_registered_on_reopen"]=true;
        out["phase1_gate"]="FAIL_INCOMPLETE";
        out["independent_approvals"]=0;
        std::cout<<"PHASE1_GUI_NEWMAP_COLD="<<QJsonDocument(out).toJson(QJsonDocument::Compact).constData()<<std::endl;
        delete porysplash;
        porysplash=nullptr;
        return 0;
    }
    {
        MainWindow window(nullptr);
        window.initialize();
        need(window.editor && window.editor->project,"real_mainwindow_project");
        Project *project=window.editor->project;
        need(window.editor->setMap("PalletTown"),"base_map");
        Map *base=window.editor->map;
        need(base && !project->groupNames.isEmpty(),"base_settings");
        project->newMapSettings.group=project->groupNames.first();
        project->newMapSettings.header=*base->header();
        project->newMapSettings.canFlyTo=false;
        const QString name="XGBAPhase1GuiNewMapFailure";
        const QString json=root+"/data/maps/"+name+"/map.json";
        need(!QFileInfo::exists(json),"fresh_gui_map");
        QAction *create=window.findChild<QAction*>("action_NewMap");
        QAction *save=window.findChild<QAction*>("action_Save");
        need(create && save && create->isEnabled(),"gui_actions");
        unsigned triggers=0;
        QObject::connect(create,&QAction::triggered,[&]{++triggers;});
        create->trigger();
        need(triggers==1,"actual_new_map_action");
        NewMapDialog *cancelDialog=window.findChild<NewMapDialog*>();
        need(cancelDialog!=nullptr,"actual_new_map_cancel_dialog");
        QCoreApplication::processEvents();
        need(cancelDialog->isVisible() && cancelDialog->isModal() &&
             cancelDialog->windowModality()==Qt::WindowModal,
             "actual_new_map_cancel_modal");
        auto *cancelButtons=cancelDialog->findChild<QDialogButtonBox*>("buttonBox");
        need(cancelButtons && cancelButtons->button(QDialogButtonBox::Cancel),
             "actual_new_map_cancel_button");
        const QString cancelledName="XGBAPhase1GuiNewMapCancelled";
        QLineEdit *cancelName=cancelDialog->findChild<QLineEdit*>("lineEdit_Name");
        need(cancelName!=nullptr,"actual_new_map_cancel_name");
        cancelName->setText(cancelledName);
        QPointer<NewMapDialog> cancelledDialog(cancelDialog);
        cancelButtons->button(QDialogButtonBox::Cancel)->click();
        QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
        need(cancelledDialog.isNull() && !project->isLoadedMap(cancelledName) &&
             window.editor->map==base,"actual_new_map_cancel_preserved_editor");

        create->trigger();
        need(triggers==2,"second_actual_new_map_action");
        NewMapDialog *dialog=window.findChild<NewMapDialog*>();
        need(dialog!=nullptr,"actual_new_map_dialog");
        QCoreApplication::processEvents();
        need(dialog->isVisible() && dialog->isModal() &&
             dialog->windowModality()==Qt::WindowModal,
             "actual_new_map_accept_modal");
        QLineEdit *nameEdit=dialog->findChild<QLineEdit*>("lineEdit_Name");
        QComboBox *group=dialog->findChild<QComboBox*>("comboBox_Group");
        QComboBox *layout=dialog->findChild<QComboBox*>("comboBox_LayoutID");
        need(nameEdit && group && layout,"original_dialog_fields");
        nameEdit->setText(name);
        int gi=group->findText(project->groupNames.first());
        int li=layout->findText(base->layoutId());
        need(gi>=0 && li>=0,"existing_group_and_layout");
        group->setCurrentIndex(gi);
        layout->setCurrentIndex(li);
        auto *acceptButtons=dialog->findChild<QDialogButtonBox*>("buttonBox");
        need(acceptButtons && acceptButtons->button(QDialogButtonBox::Ok),
             "actual_new_map_accept_button");
        acceptButtons->button(QDialogButtonBox::Ok)->click();
        Map *map=project->getMap(name);
        need(map && project->isLoadedMap(name),"dialog_created_map");
        need(window.editor->map==map,"gui_selected_new_map");
        need(!map->isPersistedToFile() && !QFileInfo::exists(json),
             "gui_creation_must_not_persist");
        QFileSystemWatcher *watcher=project->findChild<QFileSystemWatcher*>();
        need(watcher!=nullptr,"original_qt_filewatcher");
        need(!project->watchFile(json),"unsaved_map_watch_must_fail");
        need(!watcher->files().contains(json),"unsaved_map_not_watched");
        const QString dir=QFileInfo(json).absolutePath();
        need(QDir().mkpath(dir),"map_folder");
        const QString script=dir+"/scripts"+Project::getScriptFileExtension(projectConfig.usePoryScript);
        need(!QFileInfo::exists(script),"fresh_script");
        QFile full("/dev/full");
        need(full.link(script),"failure_symlink");
        need(QFileInfo(script).canonicalFilePath()==QStringLiteral("/dev/full"),
             "matched_failure_device");
        QFile control(script);
        need(control.open(QIODevice::WriteOnly),"failure_control_open");
        qint64 written=control.write("X",1);
        bool flushed=control.flush();
        auto error=control.error();
        control.close();
        need((written<0 || !flushed) && error!=QFileDevice::NoError,
             "actual_qt_device_failure");
        const QString events=root+"/"+projectConfig.getFilePath(ProjectFilePath::data_event_scripts);
        const QString folder=projectConfig.getFilePath(ProjectFilePath::data_map_folders)+name;
        const QByteArray include=QString("\t.include \"%1/scripts.inc\"").arg(folder).toUtf8();
        need(count(bytes(events),include)==0,"no_prior_include");
        save->trigger();
        need(map->isPersistedToFile() && QFileInfo::exists(json),
             "gui_save_false_clean_persisted");
        need(QFile::remove(script),"remove_failure_device");
        need(!QFileInfo::exists(script),"script_missing_after_failed_gui_save");
        need(count(bytes(events),include)==1,"first_gui_include_once");
        save->trigger();
        need(!QFileInfo::exists(script),"gui_retry_skipped_missing_script");
        need(count(bytes(events),include)==1,"gui_retry_no_duplicate");
        need(!watcher->files().contains(json),"new_map_watcher_not_auto_rearmed");
        need(project->watchFile(json),"manual_watch_recovery");
        need(watcher->files().contains(json),"manual_watch_attached");
        // Observe native Qt delivery and Project::recordFileChange rearming
        // after QSaveFile atomically replaces the watched map file.
        int delivered=0;
        QObject::connect(watcher,&QFileSystemWatcher::fileChanged,
                         &window,[&](const QString &path) {
            if (path==json) ++delivered;
        });
        const QByteArray beforeReplace=bytes(json);
        QSaveFile atomicReplace(json);
        need(atomicReplace.open(QIODevice::WriteOnly),"atomic_replace_open");
        const QByteArray replacedBytes=beforeReplace+"\n";
        need(atomicReplace.write(replacedBytes)==replacedBytes.size(),"atomic_replace_write");
        need(atomicReplace.commit(),"atomic_replace_commit");
        QElapsedTimer elapsed;
        elapsed.start();
        while ((delivered==0 || !watcher->files().contains(json)) &&
              elapsed.elapsed()<4000) {
           QCoreApplication::processEvents(QEventLoop::AllEvents,50);
           QThread::msleep(10);
        }
        need(delivered>0,"atomic_replace_file_changed_signal");
        need(watcher->files().contains(json),"atomic_replace_watcher_rearmed");
        const int atomicReplaceSignals=delivered;

        // A second mutation proves the re-armed watch remains live.
        delivered=0;
        QFile touched(json);
        need(touched.open(QIODevice::WriteOnly|QIODevice::Append),
            "watched_json_append_open");
        need(touched.write("\n",1)==1 && touched.flush(),
             "watched_json_append_flush");
        touched.close();
        elapsed.start();
        while (delivered==0 && elapsed.elapsed()<4000) {
            QCoreApplication::processEvents(QEventLoop::AllEvents,50);
            QThread::msleep(10);
        }
        need(delivered>0,"post_replace_file_changed_signal");

        const QString permissionName="XGBAPhase1PermissionDenied";
        const QString permissionJson=root+"/data/maps/"+permissionName+"/map.json";
        create->trigger();
        need(triggers==3,"permission_map_action");
        NewMapDialog *permissionDialog=window.findChild<NewMapDialog*>();
        need(permissionDialog!=nullptr,"permission_map_dialog");
        QCoreApplication::processEvents();
        need(permissionDialog->isVisible() && permissionDialog->isModal(),
             "permission_map_modal");
        QLineEdit *permissionNameEdit=permissionDialog->findChild<QLineEdit*>("lineEdit_Name");
        QComboBox *permissionGroup=permissionDialog->findChild<QComboBox*>("comboBox_Group");
        QComboBox *permissionLayout=permissionDialog->findChild<QComboBox*>("comboBox_LayoutID");
        need(permissionNameEdit && permissionGroup && permissionLayout,"permission_map_fields");
        permissionNameEdit->setText(permissionName);
        const int permissionGroupIndex=permissionGroup->findText(project->groupNames.first());
        const int permissionLayoutIndex=permissionLayout->findText(base->layoutId());
        need(permissionGroupIndex>=0 && permissionLayoutIndex>=0,"permission_map_settings");
        permissionGroup->setCurrentIndex(permissionGroupIndex);
        permissionLayout->setCurrentIndex(permissionLayoutIndex);
        auto *permissionButtons=permissionDialog->findChild<QDialogButtonBox*>("buttonBox");
        need(permissionButtons && permissionButtons->button(QDialogButtonBox::Ok),
             "permission_map_accept_button");
        permissionButtons->button(QDialogButtonBox::Ok)->click();
        Map *permissionMap=project->getMap(permissionName);
        need(permissionMap && window.editor->map==permissionMap &&
             !permissionMap->isPersistedToFile(),"permission_map_unpersisted");
        const QString permissionDir=QFileInfo(permissionJson).absolutePath();
        need(QDir().mkpath(permissionDir),"permission_map_directory");
        const QByteArray permissionDirBytes=QFile::encodeName(permissionDir);
        const QByteArray permissionProbeBytes=QFile::encodeName(permissionJson);
        const QByteArray writableControlBytes=
            QFile::encodeName(permissionDir+"/permission-write-control");
        int writableControl=::open(writableControlBytes.constData(),
                                   O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
        need(writableControl>=0,"permission_writable_control_open");
        ::close(writableControl);
        need(::unlink(writableControlBytes.constData())==0,
             "permission_writable_control_cleanup");
        const auto writablePermissions=QFileInfo(permissionDir).permissions();
        const auto readOnlyDirectory=QFile::ReadOwner|QFile::ExeOwner|
                                     QFile::ReadGroup|QFile::ExeGroup|
                                     QFile::ReadOther|QFile::ExeOther;
        need(geteuid()!=0,"permission_test_requires_unprivileged_process");
        need(QFile::setPermissions(permissionDir,readOnlyDirectory),
             "permission_denial_inject");
        struct stat permissionDirStat {};
        need(::stat(permissionDirBytes.constData(),&permissionDirStat)==0 &&
             permissionDirStat.st_uid==geteuid() &&
             (permissionDirStat.st_mode&S_IWUSR)==0,
             "permission_denial_mode_effective");
        errno=0;
        int deniedFd=::open(permissionProbeBytes.constData(),
                            O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
        const int permissionErrno=errno;
        if (deniedFd>=0) {
            ::close(deniedFd);
            ::unlink(permissionProbeBytes.constData());
        }
        std::cerr << "permission probe: euid=" << geteuid()
                  << " owner=" << permissionDirStat.st_uid
                  << " mode=" << std::oct << (permissionDirStat.st_mode&0777) << std::dec
                  << " open_errno=" << permissionErrno
                  << " expected_EACCES=" << EACCES << std::endl;
        need(deniedFd<0 && permissionErrno==EACCES,
             "permission_os_open_must_fail_eacces");
        QFile deniedProbe(permissionJson);
        const bool qfileOpenDenied=!deniedProbe.open(QIODevice::WriteOnly);
        const auto qfilePermissionError=deniedProbe.error();
        if (!qfileOpenDenied) {
            deniedProbe.close();
            QFile::remove(permissionJson);
        }
        std::cerr << "QFile permission probe: opened=" << !qfileOpenDenied
                  << " error=" << static_cast<int>(qfilePermissionError)
                  << " error_string=" << deniedProbe.errorString().toStdString() << std::endl;
        need(qfileOpenDenied && qfilePermissionError!=QFileDevice::NoError,
             "permission_denial_probe");
        need(!QFileInfo::exists(permissionJson),"permission_map_not_yet_persisted");
        save->trigger();
        need(QFile::setPermissions(permissionDir,writablePermissions),
             "permission_denial_save_restore");
        need(!QFileInfo::exists(permissionJson) && !permissionMap->isPersistedToFile() &&
             window.editor->map==permissionMap,"permission_denied_first_save_state");
        QMessageBox *saveError=nullptr;
        elapsed.start();
        while (!saveError && elapsed.elapsed()<4000) {
            QCoreApplication::processEvents(QEventLoop::AllEvents,50);
            saveError=qobject_cast<QMessageBox*>(QApplication::activeModalWidget());
            if (!saveError) QThread::msleep(10);
        }
        need(saveError!=nullptr,"save_error_dialog_shown");
        const bool errorReported=
            saveError->text()==QStringLiteral("Failed to save some project changes.") &&
            saveError->isModal() &&
            saveError->informativeText().contains(QStringLiteral("Please see")) &&
            saveError->detailedText().contains(QStringLiteral("Could not open"));
        QAbstractButton *errorOk=saveError->button(QMessageBox::Ok);
        need(errorOk!=nullptr,"save_error_dialog_ok");
        errorOk->click();
        QCoreApplication::processEvents();
        need(errorReported,"save_error_dialog_details");
        need(QDir(permissionDir).removeRecursively(),"permission_map_cleanup");

        const QByteArray beforeFailedCommit=bytes(json);
        QSaveFile failedCommit(json);
        failedCommit.setDirectWriteFallback(false);
        need(failedCommit.open(QIODevice::WriteOnly),"failed_commit_open");
        const QByteArray failedBytes=beforeFailedCommit+"\n";
        need(failedCommit.write(failedBytes)==failedBytes.size(),"failed_commit_write");
        const auto mapDirectoryPermissions=QFileInfo(dir).permissions();
        need(QFile::setPermissions(dir,readOnlyDirectory),"failed_commit_permission_inject");
        const bool failedCommitAccepted=failedCommit.commit();
        need(QFile::setPermissions(dir,mapDirectoryPermissions),"failed_commit_permission_restore");
        need(!failedCommitAccepted,"failed_commit_must_fail");
        need(bytes(json)==beforeFailedCommit,"failed_commit_preserves_old_bytes");
        need(watcher->files().contains(json),"watcher_retained_after_failed_commit");
        delivered=0;
        QFile touchedAfterFailure(json);
        need(touchedAfterFailure.open(QIODevice::WriteOnly|QIODevice::Append),
             "post_failure_watch_open");
        need(touchedAfterFailure.write("\n",1)==1 && touchedAfterFailure.flush(),
             "post_failure_watch_write");
        touchedAfterFailure.close();
        elapsed.start();
        while (delivered==0 && elapsed.elapsed()<4000) {
            QCoreApplication::processEvents(QEventLoop::AllEvents,50);
            QThread::msleep(10);
        }
        need(delivered>0,"post_failure_watch_signal");

        QJsonObject out;
        out["original_mainwindow_qaction"]=true;
        out["original_newmapdialog_accept"]=true;
        out["actual_modal_newmap_cancel_preserved_editor"]=true;
        out["actual_modal_newmap_accept_selected_map"]=true;
        out["new_map_unpersisted_until_save"]=true;
        out["matched_qfile_enospc"]=true;
        out["gui_false_clean_missing_script_on_retry"]=true;
        out["watch_missing_before_save"]=true;
        out["watch_not_auto_rearmed_after_save"]=true;
        out["manual_watch_recovery"]=true;
        out["native_qt6"]=true;
        out["synthetic_new_map"]=true;
        out["atomic_replace_committed"]=true;
        out["atomic_replace_file_changed_signal"]=atomicReplaceSignals>0;
        out["watcher_rearmed_after_atomic_replace"]=watcher->files().contains(json);
        out["post_replace_file_changed_signal"]=true;
        out["permission_denied_first_save_rejected"]=true;
        out["permission_failure_preserved_unpersisted_editor_map"]=true;
        out["permission_test_unprivileged"]=geteuid()!=0;
        out["permission_os_denial_eacces"]=permissionErrno==EACCES;
        out["permission_qfile_open_denied"]=qfileOpenDenied;
        out["save_error_dialog_reported"]=true;
        out["failed_commit_rejected"]=true;
        out["failed_commit_old_bytes_preserved"]=true;
        out["watcher_retained_after_failed_commit"]=true;
        out["post_failure_watch_signal"]=true;
        out["file_changed_signal_tested"]=true;
        out["stock_gameplay"]=false;
        out["human_modal_interaction"]=false;
        out["fsync_failure_injected"]=false;
        out["permission_failure_injected"]=true;
        out["physical_durability_tested"]=false;
        out["phase1_gate"]="FAIL_INCOMPLETE";
        out["independent_approvals"]=0;
        std::cout<<"PHASE1_GUI_NEWMAP="<<QJsonDocument(out).toJson(QJsonDocument::Compact).constData()<<std::endl;
    }
    delete porysplash; porysplash=nullptr;
    return 0;
}
