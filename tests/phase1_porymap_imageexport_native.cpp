#include "imageexport.h"

#include <QCoreApplication>
#include <QFile>
#include <QImage>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTemporaryDir>

#include <iostream>

namespace {

int logErrorCount = 0;
QString lastLogError;

QImage makeIndexedImage(int width, int height) {
    QImage image(width, height, QImage::Format_Indexed8);
    QVector<QRgb> colors;
    for (int i = 0; i < 16; ++i) {
        colors.append(qRgb(i * 13, i * 7, i * 3));
    }
    image.setColorTable(colors);
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            image.setPixel(x, y, (y * width + x + 1) % 16);
        }
    }
    return image;
}

bool matchesPixels(const QImage &actual, const QImage &expected) {
    if (actual.size() != expected.size()) {
        return false;
    }
    for (int y = 0; y < expected.height(); ++y) {
        for (int x = 0; x < expected.width(); ++x) {
            if (actual.pixelColor(x, y) != expected.pixelColor(x, y)) {
                return false;
            }
        }
    }
    return true;
}

int byteAt(const QByteArray &data, qsizetype index) {
    return static_cast<unsigned char>(data.at(index));
}

}

void logError(const QString &message) {
    ++logErrorCount;
    lastLogError = message;
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QTemporaryDir directory;
    if (!directory.isValid()) {
        return 10;
    }

    const QString evenPath = directory.filePath(QStringLiteral("even.png"));
    const QImage evenInput = makeIndexedImage(4, 2);
    exportIndexed4BPPPng(evenInput, evenPath);
    QFile evenFile(evenPath);
    if (!evenFile.open(QIODevice::ReadOnly)) {
        return 11;
    }
    const QByteArray evenPng = evenFile.readAll();
    evenFile.close();
    if (evenPng.size() < 26 || evenPng.left(8) != QByteArray::fromHex("89504e470d0a1a0a")) {
        return 12;
    }
    const int bitDepth = byteAt(evenPng, 24);
    const int colorType = byteAt(evenPng, 25);
    QImage evenOutput;
    const bool evenLoaded = evenOutput.load(evenPath);
    const bool evenRoundTrip = evenLoaded && matchesPixels(evenOutput, evenInput);
    if (bitDepth != 4 || colorType != 3 || !evenRoundTrip) {
        return 13;
    }

    const QString oddPath = directory.filePath(QStringLiteral("odd.png"));
    const QImage oddInput = makeIndexedImage(3, 2);
    exportIndexed4BPPPng(oddInput, oddPath);
    QFile oddFile(oddPath);
    const bool oddFileOpened = oddFile.open(QIODevice::ReadOnly);
    const QByteArray oddPng = oddFileOpened ? oddFile.readAll() : QByteArray();
    if (oddFileOpened) {
        oddFile.close();
    }
    QImage oddOutput;
    const bool oddLoaded = oddOutput.load(oddPath);
    const bool oddRoundTrip = oddLoaded && matchesPixels(oddOutput, oddInput);
    if (!oddFileOpened || oddPng.isEmpty() || oddRoundTrip) {
        return 14;
    }

    const QString nullPath = directory.filePath(QStringLiteral("null.png"));
    exportIndexed4BPPPng(QImage(), nullPath);
    const bool nullRejected = !QFile::exists(nullPath) && logErrorCount == 1
        && lastLogError.contains(nullPath);
    if (!nullRejected) {
        return 15;
    }

    QJsonObject result;
    result.insert(QStringLiteral("even_width_roundtrip"), evenRoundTrip);
    result.insert(QStringLiteral("png_bit_depth"), bitDepth);
    result.insert(QStringLiteral("png_color_type"), colorType);
    result.insert(QStringLiteral("odd_width_file_nonempty"), !oddPng.isEmpty());
    result.insert(QStringLiteral("odd_width_decoder_loaded"), oddLoaded);
    result.insert(QStringLiteral("odd_width_roundtrip"), oddRoundTrip);
    result.insert(QStringLiteral("null_image_logged"), logErrorCount == 1);
    result.insert(QStringLiteral("null_image_no_file"), !QFile::exists(nullPath));
    result.insert(QStringLiteral("phase1_gate"), QStringLiteral("FAIL_INCOMPLETE"));
    result.insert(QStringLiteral("independent_approvals"), 0);
    std::cout << "PHASE1_IMAGEEXPORT_RESULT="
              << QJsonDocument(result).toJson(QJsonDocument::Compact).constData()
              << '\n';
    return 0;
}
