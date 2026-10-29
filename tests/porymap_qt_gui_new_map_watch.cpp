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
#include <QComboBox>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFileSystemWatcher>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QThread>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLineEdit>
#include <QStandardPaths>
#include <iostream>
#include <cstdlib>

static void need(bool b, const char *why) {
    if (!b) { std::cerr << "FAIL " << why << std::endl; std::exit(3); }
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
    need(argc==2,"usage_PROJECT_ROOT");
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
        NewMapDialog *dialog=window.findChild<NewMapDialog*>();
        need(dialog!=nullptr,"actual_new_map_dialog");
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
        dialog->accept();
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
        // Actual Linux/Qt event delivery, distinct from watcher registration.
        // Append legal JSON whitespace, leaving map contents semantically unchanged.
        int delivered=0;
        QObject::connect(watcher,&QFileSystemWatcher::fileChanged,
                         &window,[&](const QString &path) {
            if (path==json) ++delivered;
        });
        QFile touched(json);
        need(touched.open(QIODevice::WriteOnly|QIODevice::Append),
             "watched_json_append_open");
        need(touched.write("\\n",1)==1 && touched.flush(),
             "watched_json_append_flush");
        touched.close();
        QElapsedTimer elapsed;
        elapsed.start();
        while (delivered==0 && elapsed.elapsed()<4000) {
            QCoreApplication::processEvents(QEventLoop::AllEvents,50);
            QThread::msleep(10);
        }
        need(delivered>0,"actual_original_qt_filechanged_signal");
        QJsonObject out;
        out["original_mainwindow_qaction"]=true;
        out["original_newmapdialog_accept"]=true;
        out["new_map_unpersisted_until_save"]=true;
        out["matched_qfile_enospc"]=true;
        out["gui_false_clean_missing_script_on_retry"]=true;
        out["watch_missing_before_save"]=true;
        out["watch_not_auto_rearmed_after_save"]=true;
        out["manual_watch_recovery"]=true;
        out["native_qt6"]=true;
        out["synthetic_new_map"]=true;
        out["file_changed_signal_tested"]=true;
        out["stock_gameplay"]=false;
        out["phase1_gate"]="FAIL_INCOMPLETE";
        out["independent_approvals"]=0;
        std::cout<<"PHASE1_GUI_NEWMAP="<<QJsonDocument(out).toJson(QJsonDocument::Compact).constData()<<std::endl;
    }
    delete porysplash; porysplash=nullptr;
    return 0;
}
