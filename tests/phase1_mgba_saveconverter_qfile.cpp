#include <QByteArray>
#include <QFile>
#include <QIODevice>
#include <QObject>
#include <QString>
#include <QTemporaryDir>
#include <QVector>

#include <cstdio>
#include <cstdlib>
#include <sys/stat.h>
#include <sys/sysmacros.h>

struct QFileObservation {
	bool openCalled = false;
	bool openResult = false;
	int openError = -1;
	QByteArray openErrorStringHex;
	qint64 writeResult = -2;
	int writeError = -1;
	bool closeCalled = false;
	int closeError = -1;
	QByteArray closeErrorStringHex;
	int dialogs = 0;
};

static QFileObservation active;
static QString activePath;

class ObservedQFile : public QFile {
public:
	using QFile::QFile;

	bool open(QIODevice::OpenMode flags) override {
		active.openCalled = true;
		active.openResult = QFile::open(flags);
		active.openError = static_cast<int>(QFile::error());
		active.openErrorStringHex = QFile::errorString().toUtf8().toHex();
		return active.openResult;
	}

	qint64 write(const QByteArray& data) {
		active.writeResult = QFile::write(data);
		active.writeError = static_cast<int>(QFile::error());
		return active.writeResult;
	}

	void close() override {
		active.closeCalled = true;
		QFile::close();
		active.closeError = static_cast<int>(QFile::error());
		active.closeErrorStringHex = QFile::errorString().toUtf8().toHex();
	}
};

class QMessageBox {
public:
	enum Icon { Warning };
	enum StandardButton { Ok };

	QMessageBox(Icon, const QString&, const QString&, StandardButton,
	            QObject*, Qt::WindowType) {}

	void setAttribute(Qt::WidgetAttribute) {}

	void show() {
		++active.dialogs;
	}
};

struct AnnotatedSave {
	QByteArray convertTo(const AnnotatedSave&) const {
		return QByteArrayLiteral("pinned-converter-qfile-payload");
	}
};

struct Selector {
	int currentIndex() const {
		return 0;
	}
};

struct OutputFile {
	QString text() const {
		return activePath;
	}
};

class SaveConverter : public QObject {
public:
	struct Ui {
		Selector* inputType;
		Selector* outputType;
		OutputFile* outputFile;
	};

	SaveConverter()
		: m_ui{&inputType, &outputType, &outputFile},
		  m_validSaves{AnnotatedSave{}},
		  m_validOutputs{AnnotatedSave{}} {}

	static QString tr(const char* text) {
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

#define QFile ObservedQFile
PHASE1_INSERT_PINNED_CONVERT_BODY
#undef QFile

static void require(bool condition, const char* message) {
	if (!condition) {
		std::fprintf(stderr, "PHASE1_QFILE_FATAL %s\n", message);
		std::exit(2);
	}
}

static QFileObservation run(const QString& path) {
	active = QFileObservation{};
	activePath = path;
	SaveConverter converter;
	converter.convert();
	return active;
}

int main() {
	const QByteArray expected = QByteArrayLiteral("pinned-converter-qfile-payload");
	QTemporaryDir directory;
	require(directory.isValid(), "temporary directory unavailable");

	const QString regularPath = directory.filePath(QStringLiteral("output.sav"));
	const QFileObservation regular = run(regularPath);
	QFile output(regularPath);
	require(output.open(QIODevice::ReadOnly), "temporary output cannot be reopened");
	const QByteArray actual = output.readAll();
	output.close();
	require(regular.openCalled && regular.openResult &&
	            regular.writeResult == expected.size() &&
	            regular.closeCalled &&
	            regular.closeError == static_cast<int>(QFileDevice::NoError) &&
	            regular.dialogs == 0 && actual == expected,
	        "native QFile temporary-file success control");

	struct stat fullDevice {};
	require(::stat("/dev/full", &fullDevice) == 0 &&
	            S_ISCHR(fullDevice.st_mode) &&
	            major(fullDevice.st_rdev) == 1 &&
	            minor(fullDevice.st_rdev) == 7,
	        "/dev/full is unavailable or not a character device");
	const QFileObservation full = run(QStringLiteral("/dev/full"));
	require(full.openCalled && full.openResult &&
	            full.writeResult == expected.size() &&
	            full.writeError == static_cast<int>(QFileDevice::NoError) &&
	            full.closeCalled &&
	            full.closeError == static_cast<int>(QFileDevice::ResourceError) &&
	            full.closeErrorStringHex ==
	                QByteArrayLiteral("4e6f207370616365206c656674206f6e20646576696365") &&
	            full.dialogs == 0,
	        "native QFile /dev/full write-error witness");

	const QString missingPath =
	    directory.filePath(QStringLiteral("missing-parent/output.sav"));
	const QFileObservation openFailure = run(missingPath);
	require(openFailure.openCalled && !openFailure.openResult &&
	            openFailure.writeResult == -2 && !openFailure.closeCalled &&
	            openFailure.dialogs == 1,
	        "native QFile failed-open warning control");

	std::printf(
	    "PHASE1_QFILE_CASE temporary open=%d open_error=%d write=%lld write_error=%d "
	    "close=%d close_error=%d bytes_match=%d dialogs=%d\n",
	    regular.openResult ? 1 : 0, regular.openError,
	    static_cast<long long>(regular.writeResult), regular.writeError,
	    regular.closeCalled ? 1 : 0, regular.closeError,
	    actual == expected ? 1 : 0, regular.dialogs);
	std::printf(
	    "PHASE1_QFILE_CASE dev_full open=%d open_error=%d write=%lld write_error=%d "
	    "close=%d close_error=%d close_error_text_hex=%s "
	    "bytes_match=0 dialogs=%d\n",
	    full.openResult ? 1 : 0, full.openError,
	    static_cast<long long>(full.writeResult), full.writeError,
	    full.closeCalled ? 1 : 0, full.closeError,
	    full.closeErrorStringHex.constData(), full.dialogs);
	std::printf(
	    "PHASE1_QFILE_CASE open_failure open=%d open_error=%d "
	    "open_error_text_hex=%s write=%lld close=%d dialogs=%d\n",
	    openFailure.openResult ? 1 : 0, openFailure.openError,
	    openFailure.openErrorStringHex.constData(),
	    static_cast<long long>(openFailure.writeResult),
	    openFailure.closeCalled ? 1 : 0, openFailure.dialogs);
	std::puts("PHASE1_QFILE_DONE");
	return 0;
}
