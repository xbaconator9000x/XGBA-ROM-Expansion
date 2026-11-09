#include "advancemapparser.h"
#include "maplayout.h"
#include "project.h"

#include <QCoreApplication>
#include <QFile>
#include <QTemporaryDir>

#include <iostream>

ProjectConfigStub projectConfig;

namespace {

bool expect(bool condition, const char *label)
{
    if (!condition)
        std::cerr << "ADVANCEMAP_ASSERTION_FAILED=" << label << '\n';
    return condition;
}

void appendU32(QByteArray &bytes, quint32 value)
{
    for (int i = 0; i < 4; ++i)
        bytes.append(static_cast<char>((value >> (8 * i)) & 0xff));
}

void appendU16(QByteArray &bytes, quint16 value)
{
    bytes.append(static_cast<char>(value & 0xff));
    bytes.append(static_cast<char>((value >> 8) & 0xff));
}

bool writeBytes(const QString &path, const QByteArray &bytes)
{
    QFile file(path);
    return file.open(QIODevice::WriteOnly) && file.write(bytes) == bytes.size();
}

QByteArray mapFile(quint32 width, quint32 height, quint32 primary, quint32 secondary,
                   quint8 borderWidth, quint8 borderHeight, const QByteArray &data)
{
    QByteArray bytes;
    appendU32(bytes, width);
    appendU32(bytes, height);
    appendU32(bytes, primary);
    appendU32(bytes, secondary);
    bytes.append(static_cast<char>(borderWidth));
    bytes.append(static_cast<char>(borderHeight));
    bytes.append("\0\0", 2);
    bytes.append(data);
    return bytes;
}

QByteArray metatileFile(const QByteArray &signature, int attributeSize)
{
    QByteArray bytes;
    appendU32(bytes, 1);
    for (quint16 i = 0; i < 8; ++i)
        appendU16(bytes, static_cast<quint16>(0x100 + i));
    const QByteArray attributes = QByteArray::fromHex("78563412");
    bytes.append(attributes.constData(), attributeSize);
    bytes.append(signature);
    return bytes;
}

void deleteMetatiles(const QList<Metatile *> &metatiles)
{
    for (Metatile *metatile : metatiles)
        delete metatile;
}

bool runNormalCases()
{
    QTemporaryDir directory;
    if (!directory.isValid())
        return false;

    Project project;
    bool ok = true;

    QByteArray mapData;
    appendU16(mapData, 0x1234);
    appendU16(mapData, 0xabcd);
    const QString validMapPath = directory.filePath(QStringLiteral("valid.map"));
    ok &= expect(writeBytes(validMapPath, mapFile(2, 1, 0, 1, 0, 0, mapData)),
                 "write_valid_layout_fixture");
    bool error = false;
    Layout *layout = AdvanceMapParser::parseLayout(validMapPath, &error, &project);
    ok &= expect(layout && !error, "valid_layout_accepted");
    if (layout) {
        ok &= expect(layout->width == 2 && layout->height == 1, "layout_dimensions");
        ok &= expect(layout->blockdata.size() == 2 &&
                         layout->blockdata.at(0) == 0x1234 &&
                         layout->blockdata.at(1) == 0xabcd,
                     "layout_little_endian_blockdata");
        ok &= expect(layout->tileset_primary_label == QStringLiteral("PRIMARY_A") &&
                         layout->tileset_secondary_label == QStringLiteral("SECONDARY_A"),
                     "layout_tileset_index_selection");
        delete layout;
    }

    const QString wrongKindPath = directory.filePath(QStringLiteral("wrong-kind.map"));
    ok &= expect(writeBytes(wrongKindPath, mapFile(1, 1, 1, 0, 0, 0, QByteArray::fromHex("3412"))),
                 "write_wrong_kind_layout_fixture");
    error = false;
    layout = AdvanceMapParser::parseLayout(wrongKindPath, &error, &project);
    ok &= expect(layout && !error, "wrong_kind_tileset_ids_fall_back");
    if (layout) {
        ok &= expect(layout->tileset_primary_label == QStringLiteral("PRIMARY_DEFAULT") &&
                         layout->tileset_secondary_label == QStringLiteral("SECONDARY_DEFAULT"),
                     "wrong_kind_tileset_fallback_labels");
        delete layout;
    }

    const QString shortMapPath = directory.filePath(QStringLiteral("short.map"));
    ok &= expect(writeBytes(shortMapPath, QByteArray(19, '\0')), "write_short_layout_fixture");
    error = false;
    layout = AdvanceMapParser::parseLayout(shortMapPath, &error, &project);
    ok &= expect(!layout && error, "short_layout_rejected");

    const QString oddMapPath = directory.filePath(QStringLiteral("odd.map"));
    ok &= expect(writeBytes(oddMapPath, QByteArray(21, '\0')), "write_odd_layout_fixture");
    error = false;
    layout = AdvanceMapParser::parseLayout(oddMapPath, &error, &project);
    ok &= expect(!layout && error, "odd_layout_rejected");

    const QString rsePath = directory.filePath(QStringLiteral("rse.bvd"));
    ok &= expect(writeBytes(rsePath, metatileFile("RSE ", 2)), "write_rse_metatiles_fixture");
    error = false;
    QList<Metatile *> metatiles = AdvanceMapParser::parseMetatiles(rsePath, &error, true);
    ok &= expect(!error && metatiles.size() == 1, "rse_metatile_accepted");
    if (metatiles.size() == 1) {
        ok &= expect(metatiles.first()->tiles.size() == 8 &&
                         metatiles.first()->tiles.first().value == 0x100 &&
                         metatiles.first()->tiles.last().value == 0x107,
                     "rse_metatile_tile_order");
        ok &= expect(metatiles.first()->attributes == 0x5678 &&
                         metatiles.first()->version == BaseGameVersion::pokeemerald,
                     "rse_metatile_attribute_decode");
    }
    deleteMetatiles(metatiles);

    const QString frlgPath = directory.filePath(QStringLiteral("frlg.bvd"));
    ok &= expect(writeBytes(frlgPath, metatileFile("FRLG", 4)), "write_frlg_metatiles_fixture");
    projectConfig.tripleLayerMetatilesEnabled = true;
    error = false;
    metatiles = AdvanceMapParser::parseMetatiles(frlgPath, &error, false);
    ok &= expect(!error && metatiles.size() == 1, "frlg_metatile_accepted");
    if (metatiles.size() == 1) {
        ok &= expect(metatiles.first()->tiles.size() == 12 &&
                         metatiles.first()->tiles.at(8).value == 0,
                     "triple_layer_tiles_filled");
        ok &= expect(metatiles.first()->attributes == 0x12345678 &&
                         metatiles.first()->version == BaseGameVersion::pokefirered,
                     "frlg_four_byte_attribute_decode");
    }
    projectConfig.tripleLayerMetatilesEnabled = false;
    deleteMetatiles(metatiles);

    QByteArray unsupported = metatileFile("NOPE", 2);
    const QString unsupportedPath = directory.filePath(QStringLiteral("unsupported.bvd"));
    ok &= expect(writeBytes(unsupportedPath, unsupported), "write_unsupported_version_fixture");
    error = false;
    metatiles = AdvanceMapParser::parseMetatiles(unsupportedPath, &error, true);
    ok &= expect(error && metatiles.isEmpty(), "unsupported_metatile_version_rejected");
    deleteMetatiles(metatiles);

    const QString palettePath = directory.filePath(QStringLiteral("colors.pal"));
    ok &= expect(writeBytes(palettePath, QByteArray::fromHex("ff0102070033aa55")),
                 "write_palette_fixture");
    error = false;
    const QList<QRgb> palette = AdvanceMapParser::parsePalette(palettePath, &error);
    ok &= expect(!error && palette.size() == 2, "palette_accepted");
    if (palette.size() == 2) {
        ok &= expect(qRed(palette.at(0)) == 255 && qGreen(palette.at(0)) == 1 &&
                         qBlue(palette.at(0)) == 2,
                     "palette_rgb_channels");
        ok &= expect(qRed(palette.at(1)) == 0 && qGreen(palette.at(1)) == 0x33 &&
                         qBlue(palette.at(1)) == 0xaa,
                     "palette_stride_ignores_fourth_byte");
    }

    const QString malformedPalettePath = directory.filePath(QStringLiteral("malformed.pal"));
    ok &= expect(writeBytes(malformedPalettePath, QByteArray(3, '\0')),
                 "write_malformed_palette_fixture");
    error = false;
    const QList<QRgb> malformedPalette =
        AdvanceMapParser::parsePalette(malformedPalettePath, &error);
    ok &= expect(error && malformedPalette.isEmpty(), "malformed_palette_rejected");

    if (ok)
        std::cout << "ADVANCEMAP_IMPORT_NATIVE positive_layout=1 positive_rse=1 "
                     "positive_frlg=1 positive_palette=1 malformed_rejected=1\n";
    return ok;
}

bool runOverflowCase()
{
    QTemporaryDir directory;
    if (!directory.isValid())
        return false;
    Project project;
    const QString path = directory.filePath(QStringLiteral("overflow.map"));
    if (!writeBytes(path, mapFile(65536, 65536, 0, 0, 0, 0, {})))
        return false;
    bool error = false;
    Layout *layout = AdvanceMapParser::parseLayout(path, &error, &project);
    delete layout;
    std::cout << "ADVANCEMAP_OVERFLOW_UNEXPECTED_RETURN error=" << error << '\n';
    return true;
}

}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    if (argc > 1 && QByteArray(argv[1]) == "--overflow")
        return runOverflowCase() ? 0 : 1;
    return runNormalCases() ? 0 : 1;
}
