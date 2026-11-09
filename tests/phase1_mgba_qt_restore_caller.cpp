#include <QBuffer>
#include <QByteArray>
#include <QIODevice>
#include <QString>

#include <mgba-util/vfs.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>

struct VFile *VFileOpen(const char *path, int mode);

#define emit
#define mLOG(...)

struct mCore {
    QByteArray state;
    int observedFlags = -1;
};

struct mCoreThread {
    mCore *core;
    void *userData;
    int clearCrashedCalls = 0;
    int runCalls = 0;
};

static VFile *activeBackup = nullptr;
static bool lastLoadResult = false;
static int saveCalls = 0;
static class TrackingBuffer *activeFileDevice = nullptr;

class MemoryVFile : public VFile {
public:
    QByteArray bytes;
    qint64 position = 0;
    bool closed = false;

    MemoryVFile() {
        close = closeFile;
        seek = seekFile;
        read = readFile;
        readline = readLineFile;
        write = writeFile;
        map = mapFile;
        unmap = unmapFile;
        truncate = truncateFile;
        size = sizeFile;
        sync = syncFile;
    }

    static MemoryVFile *self(VFile *vf) {
        return static_cast<MemoryVFile *>(vf);
    }

    static bool closeFile(VFile *vf) {
        auto *file = self(vf);
        file->closed = true;
        if (activeBackup == vf) {
            activeBackup = nullptr;
        }
        delete file;
        return true;
    }

    static off_t seekFile(VFile *vf, off_t offset, int whence) {
        auto *file = self(vf);
        qint64 base = 0;
        if (whence == SEEK_CUR) {
            base = file->position;
        } else if (whence == SEEK_END) {
            base = file->bytes.size();
        }
        file->position = base + offset;
        return file->position;
    }

    static ssize_t readFile(VFile *vf, void *buffer, size_t size) {
        auto *file = self(vf);
        const qint64 count = qMin<qint64>(
            static_cast<qint64>(size), file->bytes.size() - file->position);
        if (count <= 0) {
            return 0;
        }
        std::memcpy(buffer, file->bytes.constData() + file->position, count);
        file->position += count;
        return count;
    }

    static ssize_t readLineFile(VFile *vf, char *buffer, size_t size) {
        return readFile(vf, buffer, size);
    }

    static ssize_t writeFile(VFile *vf, const void *buffer, size_t size) {
        auto *file = self(vf);
        const qint64 end = file->position + static_cast<qint64>(size);
        if (end > file->bytes.size()) {
            file->bytes.resize(end);
        }
        std::memcpy(file->bytes.data() + file->position, buffer, size);
        file->position = end;
        return size;
    }

    static void *mapFile(VFile *vf, size_t, int) {
        return self(vf)->bytes.data();
    }

    static void unmapFile(VFile *, void *, size_t) {}

    static void truncateFile(VFile *vf, size_t size) {
        self(vf)->bytes.resize(static_cast<qsizetype>(size));
    }

    static ssize_t sizeFile(VFile *vf) {
        return self(vf)->bytes.size();
    }

    static bool syncFile(VFile *, void *, size_t) {
        return true;
    }
};

bool mCoreSaveStateNamed(mCore *core, VFile *vf, int) {
    ++saveCalls;
    if (!vf) {
        return false;
    }
    vf->seek(vf, 0, SEEK_SET);
    return vf->write(vf, core->state.constData(), core->state.size()) ==
           core->state.size();
}

bool mCoreLoadStateNamed(mCore *core, VFile *vf, int flags) {
    core->observedFlags = flags;
    if (!vf) {
        lastLoadResult = false;
        return false;
    }
    vf->seek(vf, 0, SEEK_SET);
    const ssize_t size = vf->size(vf);
    QByteArray bytes(static_cast<qsizetype>(size), Qt::Uninitialized);
    const ssize_t count = vf->read(vf, bytes.data(), bytes.size());
    if (count != size || bytes == QByteArrayLiteral("corrupt-state")) {
        lastLoadResult = false;
        return false;
    }
    core->state = bytes;
    lastLoadResult = true;
    return true;
}

void mCoreThreadClearCrashed(mCoreThread *thread) {
    ++thread->clearCrashedCalls;
}

void mCoreThreadRunFunction(mCoreThread *thread,
                            void (*run)(mCoreThread *)) {
    ++thread->runCalls;
    run(thread);
}

namespace QGBA {

class VFileDevice {
public:
    static VFile *wrap(QIODevice *, QIODevice::OpenMode);
    static VFile *open(const QString &, int);
    static VFile *openMemory();
};

PHASE1_INSERT_PINNED_VFILE_ABSTRACT_WRAPPER_CLASS
PHASE1_INSERT_PINNED_VFILE_ABSTRACT_WRAPPER_METHODS
PHASE1_INSERT_PINNED_QT_VFILE_WRAP
PHASE1_INSERT_PINNED_QT_VFILE_OPEN

VFile *VFileDevice::openMemory() {
    auto *memory = new MemoryVFile;
    activeBackup = memory;
    return memory;
}

class BackupState {
public:
    bool isOpen() const {
        return m_vf != nullptr;
    }

    BackupState &operator=(VFile *vf) {
        m_vf = vf;
        return *this;
    }

    void seek(qint64 position) {
        m_vf->seek(m_vf, position, SEEK_SET);
    }

    void close() {
        if (m_vf) {
            VFile *vf = m_vf;
            m_vf = nullptr;
            vf->close(vf);
        }
    }

    VFile *get() const {
        return m_vf;
    }

    operator VFile *() const {
        return m_vf;
    }

private:
    VFile *m_vf = nullptr;
};

class CoreController {
public:
    explicit CoreController(mCore *core) {
        m_threadContext.core = core;
        m_threadContext.userData = this;
    }

    void loadState(QIODevice *iodev, int flags);
    void loadState(const QString &path, int flags);
    void loadBackupState();
    void frameAvailable() {
        ++frameSignals;
    }
    void stateLoaded() {
        ++stateSignals;
    }

    mCoreThread m_threadContext{};
    VFile *m_stateVf = nullptr;
    QString m_statePath;
    int m_loadStateFlags = 0x11;
    int m_saveStateFlags = 0x22;
    bool m_crashSeen = true;
    BackupState m_backupLoadState;
    int frameSignals = 0;
    int stateSignals = 0;
};

PHASE1_INSERT_PINNED_QT_LOADSTATE_QIODEVICE
PHASE1_INSERT_PINNED_QT_LOADSTATE_FILENAME
PHASE1_INSERT_PINNED_QT_LOADBACKUPSTATE

}

class TrackingBuffer : public QBuffer {
public:
    explicit TrackingBuffer(const QByteArray &bytes) : QBuffer() {
        setData(bytes);
    }

    bool open(OpenMode mode) override {
        ++openCalls;
        return QBuffer::open(mode);
    }

    void close() override {
        ++closeCalls;
        QBuffer::close();
    }

    int openCalls = 0;
    int closeCalls = 0;
};

struct VFile *VFileOpen(const char *path, int) {
    const QByteArray name(path);
    if (name != QByteArrayLiteral("corrupt-file") &&
        name != QByteArrayLiteral("valid-file")) {
        return nullptr;
    }
    const QByteArray contents =
        name == QByteArrayLiteral("corrupt-file")
            ? QByteArrayLiteral("corrupt-state")
            : QByteArrayLiteral("file-state");
    activeFileDevice = new TrackingBuffer(contents);
    return QGBA::VFileDevice::wrap(activeFileDevice, QIODevice::ReadOnly);
}

class RejectingDevice : public QIODevice {
public:
    bool open(OpenMode) override {
        ++openCalls;
        return false;
    }

    void close() override {
        ++closeCalls;
        QIODevice::close();
    }

    int openCalls = 0;
    int closeCalls = 0;

protected:
    qint64 readData(char *, qint64) override {
        return -1;
    }

    qint64 writeData(const char *, qint64) override {
        return -1;
    }
};

static void require(bool condition, const char *why) {
    if (!condition) {
        std::fprintf(stderr, "PHASE1_QT_RESTORE_FATAL %s\n", why);
        std::exit(2);
    }
}

int main() {
    mCore core{QByteArrayLiteral("original-state")};
    QGBA::CoreController controller(&core);

    TrackingBuffer corrupt(QByteArrayLiteral("corrupt-state"));
    controller.loadState(&corrupt, 0x35);
    require(corrupt.openCalls == 1 && corrupt.closeCalls == 1 &&
                !corrupt.isOpen() && !lastLoadResult &&
                controller.frameSignals == 0 && controller.stateSignals == 0 &&
                controller.m_backupLoadState.isOpen() &&
                core.state == QByteArrayLiteral("original-state") &&
                core.observedFlags == 0x35 && controller.m_loadStateFlags == 0x11,
            "Qt rejected-state result, signals, flag restoration, or cleanup");
    std::puts("PHASE1_QT_RESTORE_CASE rejected open=1 close=1 result=0 "
              "frame=0 state=0 backup_open=1 core_unchanged=1");

    controller.loadBackupState();
    require(lastLoadResult && core.state == QByteArrayLiteral("original-state") &&
                controller.frameSignals == 1 && controller.stateSignals == 1 &&
                !controller.m_backupLoadState.isOpen(),
            "Qt backup recovery result, signals, or VFile cleanup");
    std::puts("PHASE1_QT_RESTORE_CASE recovery result=1 frame=1 state=1 "
              "backup_open=0 core_original=1");

    controller.loadState(QStringLiteral("valid-file"), 0x46);
    require(activeFileDevice && activeFileDevice->openCalls == 1 &&
                activeFileDevice->closeCalls == 1 &&
                !activeFileDevice->isOpen() && lastLoadResult &&
                core.state == QByteArrayLiteral("file-state") &&
                controller.frameSignals == 2 && controller.stateSignals == 2 &&
                core.observedFlags == 0x46 && controller.m_loadStateFlags == 0x11,
            "Qt filename retry result, success signals, or cleanup");
    delete activeFileDevice;
    activeFileDevice = nullptr;
    controller.m_backupLoadState.close();
    std::puts("PHASE1_QT_RESTORE_CASE filename_retry open=1 close=1 result=1 "
              "frame=2 state=2 flags=70 core_updated=1");

    RejectingDevice rejected;
    const int runCallsBefore = controller.m_threadContext.runCalls;
    const int clearCallsBefore = controller.m_threadContext.clearCrashedCalls;
    const int saveCallsBefore = saveCalls;
    controller.loadState(&rejected, 0x57);
    require(rejected.openCalls == 1 && rejected.closeCalls == 0 &&
                controller.m_threadContext.runCalls == runCallsBefore &&
                controller.m_threadContext.clearCrashedCalls == clearCallsBefore &&
                saveCalls == saveCallsBefore && controller.frameSignals == 2 &&
                controller.stateSignals == 2,
            "Qt QIODevice open-failure control");
    std::puts("PHASE1_QT_RESTORE_CASE open_failure open=1 close=0 "
              "thread_calls=0 signals_unchanged=1");

    const int namedRunCallsBefore = controller.m_threadContext.runCalls;
    const int namedSaveCallsBefore = saveCalls;
    controller.loadState(QStringLiteral("missing-file"), 0x68);
    require(!activeFileDevice &&
                controller.m_threadContext.runCalls == namedRunCallsBefore + 1 &&
                saveCalls == namedSaveCallsBefore &&
                controller.frameSignals == 2 && controller.stateSignals == 2,
            "Qt filename open-failure control");
    std::puts("PHASE1_QT_RESTORE_CASE filename_open_failure "
              "thread_calls=1 core_calls=0 signals_unchanged=1");
    std::puts("PHASE1_QT_RESTORE_DONE");
    return 0;
}
