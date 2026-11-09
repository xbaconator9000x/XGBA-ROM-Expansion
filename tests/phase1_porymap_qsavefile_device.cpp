// Phase 1 only: actual Qt API device compatibility, not an upstream Porymap save.
#include <QCoreApplication>
#include <QFile>
#include <QIODevice>
#include <QSaveFile>
#include <QTemporaryDir>
#include <QTextStream>
#include <QByteArray>
#include <type_traits>
#include <iostream>
#include <cstdlib>
#include "lib/orderedjson.h"

static_assert(std::is_same<decltype(&OrderedJsonDoc::dump),
                           void (OrderedJsonDoc::*)(QFile *)>::value,
              "pinned serializer no longer takes QFile*");
static_assert(!std::is_convertible<QSaveFile *, QFile *>::value,
              "QSaveFile unexpectedly became a QFile");
static_assert(std::is_convertible<QSaveFile *, QIODevice *>::value,
              "QSaveFile must implement QIODevice");

static void require(bool ok, const char *why) {
    if (!ok) { std::cerr << "FAIL " << why << std::endl; std::exit(2); }
}
static QByteArray read(const QString &path) {
    QFile f(path);
    require(f.open(QIODevice::ReadOnly), "read open");
    return f.readAll();
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QTemporaryDir temp;
    require(temp.isValid(), "temporary directory");
    const QString path = temp.path() + "/map.json";
    {
        QFile f(path);
        require(f.open(QIODevice::WriteOnly), "baseline open");
        require(f.write("prior\n") == 6, "baseline write");
        require(f.flush(), "baseline flush");
    }
    {
        QSaveFile file(path);
        require(file.open(QIODevice::WriteOnly), "QSaveFile open");
        QTextStream stream(&file);
        stream << "replacement\n";
        stream.flush();
        require(stream.status() == QTextStream::Ok, "QTextStream write");
        require(file.commit(), "QSaveFile commit");
    }
    require(read(path) == QByteArray("replacement\n"), "atomic replacement bytes");
    {
        QSaveFile file(path);
        require(file.open(QIODevice::WriteOnly), "cancel open");
        QTextStream stream(&file);
        stream << "discarded\n";
        stream.flush();
        require(stream.status() == QTextStream::Ok, "cancel stream");
        file.cancelWriting();
    }
    require(read(path) == QByteArray("replacement\n"), "cancel preserved original");
    QFile full("/dev/full");
    require(full.open(QIODevice::WriteOnly), "/dev/full open");
    const qint64 written = full.write(QByteArray(4096, 'x'));
    const bool flushed = full.flush();
    const bool failed = written < 0 || !flushed;
    require(failed && full.error() != QFileDevice::NoError, "/dev/full write failure");
    full.close();
    std::cout << "PHASE1_QSAVEFILE_TYPE QFile=0 QIODevice=1\n"
              << "PHASE1_QSAVEFILE_COMMIT positive=1 bytes=12\n"
              << "PHASE1_QSAVEFILE_CANCEL preserved=1\n"
              << "PHASE1_QFILE_DEVFULL write_error=1\n"
              << "PHASE1_QSAVEFILE_BOUNDARY PASS gate=FAIL_INCOMPLETE approvals=0\n";
    return 0;
}
