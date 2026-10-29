#include <QCoreApplication>
#include <QFile>
#include <QDir>
#include <QString>
#include <QTemporaryDir>
#include <QByteArray>
#include <iostream>
#include <stdexcept>

void logError(const QString &message) {
    std::cerr << "PHASE1_OPEN_ERROR " << message.toStdString() << '\n';
}
class Project {
public:
    bool saveTextFile(const QString &path, const QString &text);
    bool appendTextFile(const QString &path, const QString &text);
};
// The two unchanged pinned Project:: functions are inserted HERE by the source verifier.
PHASE1_INSERT_PINNED_FUNCTIONS

static void require(bool condition, const char *why) {
    if (!condition) throw std::runtime_error(why);
}
static QByteArray readFile(const QString &path) {
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "could not read positive file");
    return file.readAll();
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        QTemporaryDir dir;
        require(dir.isValid(), "temporary directory unavailable");
        const QString path = dir.path() + "/scripts.inc";
        Project project;
        std::cerr << "PHASE1_TEXT_STAGE save_positive\n";
        require(project.saveTextFile(path, "alpha\n"), "normal save returned failure");
        require(readFile(path) == "alpha\n", "normal save bytes differ");
        std::cerr << "PHASE1_TEXT_STAGE append_positive\n";
        require(project.appendTextFile(path, "beta\n"), "normal append returned failure");
        require(readFile(path) == "alpha\nbeta\n", "normal append bytes differ");
        std::cerr << "PHASE1_TEXT_STAGE save_failure\n";
        const bool failedSaveReportedSuccess = project.saveTextFile(
            "/dev/full", QString(4096, QChar('S')));
        std::cerr << "PHASE1_TEXT_RESULT save_failure_return=" << int(failedSaveReportedSuccess) << '\n';
        require(failedSaveReportedSuccess, "pinned saveTextFile no longer ignores write error");
        std::cerr << "PHASE1_TEXT_STAGE append_failure\n";
        const bool failedAppendReportedSuccess = project.appendTextFile(
            "/dev/full", QString(4096, QChar('A')));
        std::cerr << "PHASE1_TEXT_RESULT append_failure_return=" << int(failedAppendReportedSuccess) << '\n';
        require(failedAppendReportedSuccess, "pinned appendTextFile no longer ignores write error");
        std::cerr << "PHASE1_TEXT_STAGE save_open_rejected\n";
        require(!project.saveTextFile(dir.path() + "/missing/scripts.inc", "x"),
                "missing-directory save incorrectly succeeded");
        std::cerr << "PHASE1_TEXT_STAGE append_open_rejected\n";
        require(!project.appendTextFile(dir.path() + "/missing/scripts.inc", "x"),
                "missing-directory append incorrectly succeeded");
        std::cerr << "PHASE1_TEXT_RESULT positive_bytes=11 open_rejections=2\n";
        std::cerr << "PHASE1_TEXT_DONE\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "PHASE1_TEXT_FATAL " << error.what() << '\n';
        return 2;
    }
}
