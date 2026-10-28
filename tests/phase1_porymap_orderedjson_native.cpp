/* Phase 1: native Qt6, unchanged pinned Porymap OrderedJsonDoc::dump.
 * No GUI, Project::saveMapGroups or other Project writer executed here.
 */
#include "orderedjson.h"
#include <QFile>
#include <QTemporaryDir>
#include <QByteArray>
#include <cstdio>
static void check(bool ok, const char *why) {
    if (!ok) { std::fprintf(stderr, "PHASE1_JSON_FATAL %s\n", why); std::exit(3); }
}
int main() {
    QTemporaryDir dir;
    check(dir.isValid(), "tempdir");
    OrderedJson::object object;
    object["map_sections"] = OrderedJson::array{};
    object["marker"] = "PHASE1";
    OrderedJson json(object);
    OrderedJsonDoc doc(&json);
    std::puts("PHASE1_JSON_STAGE positive"); std::fflush(stdout);
    QFile good(dir.filePath("test.json"));
    check(good.open(QIODevice::WriteOnly), "positive_open");
    doc.dump(&good);
    const int positiveError = (int)good.error();
    good.close();
    QFile readback(good.fileName());
    check(readback.open(QIODevice::ReadOnly), "readback_open");
    QByteArray bytes = readback.readAll();
    check(bytes.contains("PHASE1") && bytes.endsWith('\n') && positiveError == 0,
          "positive_dump_bytes");
    std::printf("PHASE1_JSON_RESULT positive_bytes=%lld positive_error=%d\n",
                (long long)bytes.size(), positiveError); std::fflush(stdout);
    std::puts("PHASE1_JSON_STAGE failed"); std::fflush(stdout);
    QFile full("/dev/full");
    check(full.open(QIODevice::WriteOnly), "failed_open");
    doc.dump(&full);
    const int before = (int)full.error();
    full.close();
    const int after = (int)full.error();
    std::printf("PHASE1_JSON_RESULT failure_before=%d failure_after=%d\n",
                before, after); std::fflush(stdout);
    check(before == 4 && after == 4, "qfile_write_error_expected");
    std::puts("PHASE1_JSON_DONE"); std::fflush(stdout);
    return 0;
}
