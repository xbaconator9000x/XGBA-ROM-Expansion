#include <QCoreApplication>
#include <QFile>
#include <QTemporaryDir>
#include <QVector>

#include <cstdint>
#include <iostream>

struct Tile {
    uint16_t value = 0;
    uint16_t rawValue() const { return value; }
};

struct Metatile {
    QVector<Tile> tiles;
    uint32_t attributes = 0;
    uint32_t getAttributes() const { return attributes; }
};

struct ProjectConfigStub {
    int metatileAttributesSize = 4;
    int getNumTilesInMetatile() const { return 1; }
};

ProjectConfigStub projectConfig;

void logError(const QString &) {}

class Tileset {
public:
    QString metatiles_path;
    QString metatile_attrs_path;
    QVector<Metatile *> m_metatiles;

    bool saveMetatiles();
    bool saveMetatileAttributes();
};

@ORIGINAL_SAVE_METATILES@

@ORIGINAL_SAVE_METATILE_ATTRIBUTES@

namespace {

QByteArray readFile(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        return {};
    return file.readAll();
}

bool expect(bool condition, const char *label)
{
    if (!condition)
        std::cerr << "PHASE1_TILESET_ASSERTION_FAILED=" << label << '\n';
    return condition;
}

}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QTemporaryDir directory;
    if (!directory.isValid())
        return 2;

    Metatile metatile;
    metatile.tiles.append(Tile{0x1234});
    metatile.attributes = 0x89abcdef;

    Tileset tileset;
    tileset.m_metatiles.append(&metatile);
    tileset.metatiles_path = directory.filePath(QStringLiteral("metatiles.bin"));
    tileset.metatile_attrs_path = directory.filePath(QStringLiteral("attributes.bin"));

    bool ok = true;
    const bool savedMetatiles = tileset.saveMetatiles();
    ok &= expect(savedMetatiles && readFile(tileset.metatiles_path) ==
                     QByteArray::fromHex("3412"),
                 "positive_little_endian_metatile_bytes");

    const bool savedAttributes = tileset.saveMetatileAttributes();
    ok &= expect(savedAttributes && readFile(tileset.metatile_attrs_path) ==
                     QByteArray::fromHex("efcdab89"),
                 "positive_little_endian_attribute_bytes");

    tileset.metatiles_path = directory.filePath(
        QStringLiteral("missing-parent/metatiles.bin"));
    const bool missingPathSaved = tileset.saveMetatiles();
    ok &= expect(!missingPathSaved, "missing_parent_open_failure");

    tileset.metatiles_path = QStringLiteral("/dev/full");
    tileset.metatile_attrs_path = QStringLiteral("/dev/full");
    const bool fullMetatiles = tileset.saveMetatiles();
    const bool fullAttributes = tileset.saveMetatileAttributes();
    ok &= expect(fullMetatiles, "dev_full_metatile_write_reported_success");
    ok &= expect(fullAttributes, "dev_full_attribute_write_reported_success");

    std::cout << "PHASE1_TILESET_NATIVE positive_metatiles="
              << (savedMetatiles && readFile(directory.filePath(
                      QStringLiteral("metatiles.bin"))) == QByteArray::fromHex("3412"))
              << " positive_attributes="
              << (savedAttributes && readFile(directory.filePath(
                      QStringLiteral("attributes.bin"))) == QByteArray::fromHex("efcdab89"))
              << " missing_path_rejected=" << !missingPathSaved
              << " dev_full_metatiles_returned_true=" << fullMetatiles
              << " dev_full_attributes_returned_true=" << fullAttributes << '\n';

    return ok ? 0 : 1;
}
