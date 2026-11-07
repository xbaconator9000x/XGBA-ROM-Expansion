#include <QByteArray>
#include <QIODevice>
#include <QObject>
#include <QString>
#include <QVector>

#include <cstdio>
#include <cstdlib>

struct Scenario {
    enum Mode { Full, Short, Negative, OpenFailure } mode = Full;
    QByteArray accepted;
    qint64 requested = 0;
    qint64 writeDataResult = 0;
    qint64 qtWriteResult = 0;
    int writeCalls = 0;
    int openCalls = 0;
    int closeCalls = 0;
    int shownDialogs = 0;
};

static Scenario active;

class FaultInjectingDevice : public QIODevice {
public:
    explicit FaultInjectingDevice(const QString &) {}

    bool open(QIODevice::OpenMode mode) {
        ++active.openCalls;
        if (active.mode == Scenario::OpenFailure) {
            return false;
        }
        return QIODevice::open(mode | QIODevice::Unbuffered);
    }

    qint64 write(const QByteArray &data) {
        active.qtWriteResult = QIODevice::write(data);
        return active.qtWriteResult;
    }

    void close() {
        ++active.closeCalls;
        QIODevice::close();
    }

protected:
    qint64 readData(char *, qint64) override {
        return -1;
    }

    qint64 writeData(const char *data, qint64 size) override {
        ++active.writeCalls;
        active.requested += size;
        if (active.mode == Scenario::Negative) {
            active.writeDataResult = -1;
            return -1;
        }
        if (active.mode == Scenario::Short) {
            active.accepted.append(data, 1);
            active.writeDataResult = 1;
            return 1;
        }
        active.accepted.append(data, static_cast<int>(size));
        active.writeDataResult = size;
        return size;
    }
};

class QMessageBox {
public:
    enum Icon { Warning };
    enum StandardButton { Ok };

    QMessageBox(Icon, const QString &, const QString &, StandardButton,
                QObject *, Qt::WindowType) {}

    void setAttribute(Qt::WidgetAttribute) {}

    void show() {
        ++active.shownDialogs;
    }
};

struct AnnotatedSave {
    QByteArray converted;

    QByteArray convertTo(const AnnotatedSave &) const {
        return converted;
    }
};

struct Selector {
    int currentIndex() const {
        return 0;
    }
};

struct OutputFile {
    QString text() const {
        return QStringLiteral("fault-injected-output");
    }
};

class SaveConverter : public QObject {
public:
    struct Ui {
        Selector *inputType;
        Selector *outputType;
        OutputFile *outputFile;
    };

    SaveConverter()
        : m_ui{&inputType, &outputType, &outputFile},
          m_validSaves{AnnotatedSave{QByteArrayLiteral("converted-save-payload")}},
          m_validOutputs{AnnotatedSave{QByteArray()}} {}

    static QString tr(const char *text) {
        return QString::fromUtf8(text);
    }

    void convert();

private:
    Selector inputType;
    Selector outputType;
    OutputFile outputFile;
    Ui m_ui;
    QVector<AnnotatedSave> m_validSaves;
    QVector<AnnotatedSave> m_validOutputs;
};

PHASE1_INSERT_PINNED_CONVERT_BODY

static void require(bool condition, const char *why) {
    if (!condition) {
        std::fprintf(stderr, "PHASE1_SAVECONVERTER_FATAL %s\n", why);
        std::exit(2);
    }
}

static Scenario run(Scenario::Mode mode) {
    active = Scenario{};
    active.mode = mode;
    SaveConverter converter;
    converter.convert();
    return active;
}

int main() {
    const QByteArray expected = QByteArrayLiteral("converted-save-payload");
    const Scenario full = run(Scenario::Full);
    require(full.openCalls == 1 && full.writeCalls == 1 &&
                full.qtWriteResult == expected.size() &&
                full.accepted == expected && full.closeCalls == 1 &&
                full.shownDialogs == 0,
            "native full-write control");

    const Scenario shortWrite = run(Scenario::Short);
    require(shortWrite.openCalls == 1 && shortWrite.writeCalls == 1 &&
                shortWrite.qtWriteResult == 1 &&
                shortWrite.accepted == expected.left(1) &&
                shortWrite.closeCalls == 1 && shortWrite.shownDialogs == 0,
            "native one-of-N short-write witness");

    const Scenario negativeWrite = run(Scenario::Negative);
    require(negativeWrite.openCalls == 1 && negativeWrite.writeCalls == 1 &&
                negativeWrite.qtWriteResult == -1 &&
                negativeWrite.accepted.isEmpty() &&
                negativeWrite.closeCalls == 1 &&
                negativeWrite.shownDialogs == 0,
            "native negative-write witness");

    const Scenario openFailure = run(Scenario::OpenFailure);
    require(openFailure.openCalls == 1 && openFailure.writeCalls == 0 &&
                openFailure.closeCalls == 0 &&
                openFailure.shownDialogs == 1,
            "failed-open visible-warning control");

    std::printf("PHASE1_SAVECONVERTER_CASE full requested=%lld accepted=%lld qt_write=%lld close=%d dialogs=%d\n",
                static_cast<long long>(full.requested),
                static_cast<long long>(full.accepted.size()),
                static_cast<long long>(full.qtWriteResult),
                full.closeCalls, full.shownDialogs);
    std::printf("PHASE1_SAVECONVERTER_CASE short requested=%lld accepted=%lld qt_write=%lld close=%d dialogs=%d\n",
                static_cast<long long>(shortWrite.requested),
                static_cast<long long>(shortWrite.accepted.size()),
                static_cast<long long>(shortWrite.qtWriteResult),
                shortWrite.closeCalls, shortWrite.shownDialogs);
    std::printf("PHASE1_SAVECONVERTER_CASE negative requested=%lld accepted=%lld qt_write=%lld close=%d dialogs=%d\n",
                static_cast<long long>(negativeWrite.requested),
                static_cast<long long>(negativeWrite.accepted.size()),
                static_cast<long long>(negativeWrite.qtWriteResult),
                negativeWrite.closeCalls, negativeWrite.shownDialogs);
    std::printf("PHASE1_SAVECONVERTER_CASE open_failure requested=%lld accepted=%lld qt_write=%lld close=%d dialogs=%d\n",
                static_cast<long long>(openFailure.requested),
                static_cast<long long>(openFailure.accepted.size()),
                static_cast<long long>(openFailure.qtWriteResult),
                openFailure.closeCalls, openFailure.shownDialogs);
    std::puts("PHASE1_SAVECONVERTER_DONE");
    return 0;
}
