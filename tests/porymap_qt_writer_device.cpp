// Phase 1 only: execute pinned Porymap OrderedJsonDoc with real Qt6 QFile devices.
// This is NOT the full Project::saveMap / GUI save transaction.
#include "orderedjson.h"
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QTemporaryFile>
#include <QTextStream>
#include <QByteArray>
#include <iostream>
#include <type_traits>
#include <utility>

static_assert(std::is_void<decltype(std::declval<OrderedJsonDoc&>().dump(
    std::declval<QFile*>()))>::value, "Pinned serializer no longer returns void");

int main() {
    OrderedJson::object fields;
    fields["sentinel"] = "pinned-qt-writer-control";
    OrderedJson object(fields);
    OrderedJsonDoc writer(&object);

    // Positive control: real QFile-backed temporary file and JSON parser.
    QTemporaryFile good;
    if (!good.open()) {
        std::cerr << "cannot open positive control" << std::endl;
        return 2;
    }
    writer.dump(&good);
    if (!good.flush() || !good.seek(0)) {
        std::cerr << "positive control flush/seek failed" << std::endl;
        return 3;
    }
    QJsonParseError parseError;
    QJsonDocument parsed = QJsonDocument::fromJson(good.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError ||
        parsed.object().value("sentinel").toString() != "pinned-qt-writer-control") {
        std::cerr << "positive control JSON mismatch" << std::endl;
        return 4;
    }

    // Negative device: Linux /dev/full accepts open but refuses writes.
    // Probe the device independently, so this test fails closed on hosts
    // without the expected write-failure semantics.
    QFile probe("/dev/full");
    if (!probe.open(QIODevice::WriteOnly)) {
        std::cerr << "cannot open negative control device" << std::endl;
        return 5;
    }
    const qint64 probeWritten = probe.write(QByteArray(8192, 'x'));
    const bool probeFlushed = probe.flush();
    const bool probeFailed = probeWritten < 0 || !probeFlushed ||
                             probe.error() != QFileDevice::NoError;
    probe.close();
    if (!probeFailed) {
        std::cerr << "/dev/full did not reject writes" << std::endl;
        return 6;
    }

    QFile failing("/dev/full");
    if (!failing.open(QIODevice::WriteOnly)) {
        std::cerr << "cannot open serializer negative control" << std::endl;
        return 7;
    }
    // Actual pinned serializer executes; the caller receives no status
    // because the method returns void. QFile::flush is checked *here* only
    // by the test harness, not by Project::saveMap / saveMapGroups.
    writer.dump(&failing);
    const bool serializerFlushed = failing.flush();
    const int serializerFileError = static_cast<int>(failing.error());
    failing.close();
    if (serializerFlushed && serializerFileError == static_cast<int>(QFileDevice::NoError)) {
        std::cerr << "serializer negative device did not surface an error" << std::endl;
        return 8;
    }

    QJsonObject evidence;
    evidence.insert("qt_positive_json_roundtrip", true);
    evidence.insert("negative_device_write_failure_confirmed", true);
    evidence.insert("pinned_serializer_executed_on_negative_device", true);
    evidence.insert("serializer_return_type", "void");
    evidence.insert("serializer_flush_result_checked_by_harness", serializerFlushed);
    evidence.insert("serializer_qfile_error", serializerFileError);
    evidence.insert("full_porymap_project_or_gui_executed", false);
    evidence.insert("phase1_gate", "FAIL_INCOMPLETE");
    std::cout << QJsonDocument(evidence).toJson(QJsonDocument::Indented).constData();
    return 0;
}
