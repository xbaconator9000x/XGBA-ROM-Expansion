#include "qgifimage.h"
#include "gif_lib.h"

#include <QBuffer>
#include <QCoreApplication>
#include <QImage>
#include <QJsonDocument>
#include <QJsonObject>

#include <dlfcn.h>
#include <iostream>

namespace {
int dGifOpenCalls = 0;
int dGifSlurpCalls = 0;
int dGifCloseCalls = 0;
int eGifOpenCalls = 0;
int eGifSpewCalls = 0;
int eGifCloseCalls = 0;
int lastDGifSlurp = -1;
int lastEGifSpew = -1;

void resetCalls()
{
    dGifOpenCalls = 0;
    dGifSlurpCalls = 0;
    dGifCloseCalls = 0;
    eGifOpenCalls = 0;
    eGifSpewCalls = 0;
    eGifCloseCalls = 0;
    lastDGifSlurp = -1;
    lastEGifSpew = -1;
}

class RejectWritesDevice : public QIODevice
{
public:
    bool start()
    {
        return open(QIODevice::ReadWrite);
    }

    int writeAttempts() const
    {
        return m_writeAttempts;
    }

protected:
    qint64 readData(char *, qint64) override
    {
        return -1;
    }

    qint64 writeData(const char *, qint64) override
    {
        ++m_writeAttempts;
        setErrorString(QStringLiteral("injected write failure"));
        return -1;
    }

private:
    int m_writeAttempts = 0;
};

bool expect(bool value, const char *name)
{
    if (!value)
        std::cerr << "PHASE1_QTGIF_ASSERTION_FAILED=" << name << '\n';
    return value;
}
}

extern "C" {
GifFileType *__real_DGifOpen(void *, InputFunc, int *);
int __real_DGifSlurp(GifFileType *);
int __real_DGifCloseFile(GifFileType *);
GifFileType *__real_EGifOpen(void *, OutputFunc, int *);
int __real_EGifSpew(GifFileType *);

GifFileType *__wrap_DGifOpen(void *data, InputFunc readFunc, int *error)
{
    ++dGifOpenCalls;
    return __real_DGifOpen(data, readFunc, error);
}

int __wrap_DGifSlurp(GifFileType *file)
{
    ++dGifSlurpCalls;
    lastDGifSlurp = __real_DGifSlurp(file);
    return lastDGifSlurp;
}

int __wrap_DGifCloseFile(GifFileType *file)
{
    ++dGifCloseCalls;
    return __real_DGifCloseFile(file);
}

GifFileType *__wrap_EGifOpen(void *data, OutputFunc writeFunc, int *error)
{
    ++eGifOpenCalls;
    return __real_EGifOpen(data, writeFunc, error);
}

int __wrap_EGifSpew(GifFileType *file)
{
    ++eGifSpewCalls;
    lastEGifSpew = __real_EGifSpew(file);
    return lastEGifSpew;
}

int EGifCloseFile(GifFileType *file)
{
    ++eGifCloseCalls;
    using CloseFunction = int (*)(GifFileType *);
    const auto closeFunction =
        reinterpret_cast<CloseFunction>(dlsym(RTLD_NEXT, "EGifCloseFile"));
    if (!closeFunction)
        return GIF_ERROR;
    return closeFunction(file);
}
}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QJsonObject result;
    bool ok = true;

    QImage frame(2, 2, QImage::Format_RGB32);
    frame.fill(Qt::red);
    QGifImage image(QSize(2, 2));
    image.addFrame(frame, 100);

    QBuffer output;
    output.open(QIODevice::ReadWrite);
    resetCalls();
    const bool saved = image.save(&output);
    const QByteArray gifBytes = output.data();
    const int successSpew = lastEGifSpew;
    const int successOutputCloses = eGifCloseCalls;
    ok &= expect(saved && gifBytes.size() > 20, "positive_gif_save");
    ok &= expect(eGifOpenCalls == 1 && eGifSpewCalls == 1,
                 "positive_save_reached_original_giflib");
    ok &= expect(successSpew == GIF_OK && successOutputCloses == 1,
                 "positive_save_spew_and_close");

    QBuffer input;
    input.setData(gifBytes);
    input.open(QIODevice::ReadOnly);
    QGifImage decoded;
    resetCalls();
    const bool loaded = decoded.load(&input);
    const int positiveLoadSlurp = lastDGifSlurp;
    const int positiveLoadCloses = dGifCloseCalls;
    ok &= expect(loaded && decoded.frameCount() == 1, "positive_gif_load");
    ok &= expect(dGifOpenCalls == 1 && dGifSlurpCalls == 1 &&
                     positiveLoadSlurp == GIF_OK && positiveLoadCloses == 1,
                 "positive_load_slurp_and_close");

    QBuffer truncated;
    truncated.setData(gifBytes.left(gifBytes.size() - 1));
    truncated.open(QIODevice::ReadOnly);
    QGifImage corrupt;
    resetCalls();
    const bool corruptLoaded = corrupt.load(&truncated);
    const int corruptSlurp = lastDGifSlurp;
    const int corruptCloses = dGifCloseCalls;
    ok &= expect(!corruptLoaded && dGifOpenCalls == 1 && dGifSlurpCalls == 1 &&
                     corruptSlurp == GIF_ERROR,
                 "truncated_gif_reaches_slurp_error");
    ok &= expect(corruptCloses == 0, "slurp_error_skips_qgifimage_close");

    RejectWritesDevice rejecting;
    rejecting.start();
    resetCalls();
    const bool failedOutputSaved = image.save(&rejecting);
    const int rejectedSpew = lastEGifSpew;
    const int rejectedOutputCloses = eGifCloseCalls;
    ok &= expect(rejecting.writeAttempts() > 0 && rejectedSpew == GIF_ERROR,
                 "injected_write_reaches_egif_spew_error");
    ok &= expect(failedOutputSaved, "qgifimage_ignores_egif_spew_failure");
    ok &= expect(rejectedOutputCloses == 0,
                 "egif_spew_error_skips_giflib_close");

    QBuffer writeOnly;
    writeOnly.setData(gifBytes);
    writeOnly.open(QIODevice::WriteOnly);
    QGifImage wrongModeLoad;
    resetCalls();
    const bool writeOnlyLoaded = wrongModeLoad.load(&writeOnly);
    const bool writeOnlyReachedOpen = dGifOpenCalls == 1;
    ok &= expect(!writeOnlyLoaded && writeOnlyReachedOpen,
                 "write_only_load_enters_giflib_open");

    QBuffer readOnly;
    readOnly.setData(gifBytes);
    readOnly.open(QIODevice::ReadOnly);
    resetCalls();
    const bool readOnlySaved = image.save(&readOnly);
    const int readOnlySpew = lastEGifSpew;
    ok &= expect(readOnlySaved && eGifOpenCalls == 1 && eGifSpewCalls == 1 &&
                     readOnlySpew == GIF_ERROR,
                 "read_only_save_enters_giflib_and_reports_success");
    ok &= expect(eGifCloseCalls == 0,
                 "read_only_save_error_skips_giflib_close");

    result.insert(QStringLiteral("original_qgifimage_and_giflib"),
                  QStringLiteral("compiled from immutable source; test-only linker wrappers and EGifCloseFile symbol interposition"));
    result.insert(QStringLiteral("positive_save"), saved);
    result.insert(QStringLiteral("positive_gif_bytes"), gifBytes.size());
    result.insert(QStringLiteral("positive_egif_spew_result"), successSpew);
    result.insert(QStringLiteral("positive_egif_close_calls"), successOutputCloses);
    result.insert(QStringLiteral("positive_load"), loaded);
    result.insert(QStringLiteral("positive_frames"), decoded.frameCount());
    result.insert(QStringLiteral("positive_dgif_slurp_result"), positiveLoadSlurp);
    result.insert(QStringLiteral("positive_dgif_close_calls"), positiveLoadCloses);
    result.insert(QStringLiteral("truncated_load_returned_false"), !corruptLoaded);
    result.insert(QStringLiteral("truncated_dgif_slurp_result"), corruptSlurp);
    result.insert(QStringLiteral("truncated_dgif_close_calls"), corruptCloses);
    result.insert(QStringLiteral("injected_write_attempts"), rejecting.writeAttempts());
    result.insert(QStringLiteral("injected_egif_spew_result"), rejectedSpew);
    result.insert(QStringLiteral("injected_save_returned_true"), failedOutputSaved);
    result.insert(QStringLiteral("injected_egif_close_calls"), rejectedOutputCloses);
    result.insert(QStringLiteral("write_only_load_entered_dgif_open"), writeOnlyReachedOpen);
    result.insert(QStringLiteral("read_only_save_returned_true"), readOnlySaved);
    result.insert(QStringLiteral("read_only_egif_spew_result"), readOnlySpew);
    result.insert(QStringLiteral("read_only_egif_close_calls"), eGifCloseCalls);
    result.insert(QStringLiteral("allocation_leak_measured"), false);
    result.insert(QStringLiteral("status"),
                  ok ? QStringLiteral("PASS_NATIVE_BOUNDED_WITNESS")
                     : QStringLiteral("FAIL"));
    std::cout << "PHASE1_QTGIF_NATIVE="
              << QJsonDocument(result).toJson(QJsonDocument::Compact).constData()
              << '\n';
    return ok ? 0 : 1;
}
