/* Pinned mGBA source excerpts are MPL-2.0; see the accompanying workpaper. */
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif
#define PATH_SEP "/"
#define MAX_LOG_BUF 1024

enum mLogLevel {
	mLOG_INFO = 0x08
};

struct mLogFilter {
	int defaultLevels;
};

struct VFile {
	ssize_t (*write)(struct VFile*, const void*, size_t);
	bool (*sync)(struct VFile*, void*, size_t);
	bool (*close)(struct VFile*);
};

struct mLogger {
	void (*log)(struct mLogger*, int, enum mLogLevel, const char*, va_list);
	struct mLogFilter* filter;
};

struct mStandardLogger {
	struct mLogger d;
	bool logToStdout;
	struct VFile* logFile;
};

struct mGUILogger {
	struct mLogger d;
	struct VFile* vf;
	int logLevel;
};

struct GBASavedata {
	struct VFile* vf;
	int dirty;
	uint32_t dirtAge;
	bool maskWriteback;
	int mapMode;
	uint8_t* data;
	size_t size;
	unsigned rtcWrites;
};

struct FakeFile {
	struct VFile vf;
	char bytes[256];
	size_t length;
	unsigned writes;
	unsigned closes;
	ssize_t forcedResult;
	bool forceResult;
};

enum {
	MAP_WRITE = 2,
	mSAVEDATA_CLEANUP_THRESHOLD = 15,
	mSAVEDATA_DIRT_NONE = 0,
	mSAVEDATA_DIRT_NEW = 1,
	mSAVEDATA_DIRT_SEEN = 2
};

static struct mStandardLogger standardLogger;
static struct mGUILogger guiLogger;
static struct mLogger router;
static struct FakeFile standardFile;
static struct FakeFile guiFile;
static struct FakeFile replacementFile;
static struct FakeFile shortFile;
static unsigned reopenCalls;
static unsigned syncCalls;
static bool reopenArgumentsExact;

bool mLogFilterTest(const struct mLogFilter* filter, int category,
                    enum mLogLevel level) {
	(void) category;
	return (filter->defaultLevels & level) != 0;
}

const char* mLogCategoryName(int category) {
	(void) category;
	return "GBA";
}

void mCoreConfigDirectory(char* path, size_t size) {
	snprintf(path, size, "/tmp");
}

struct VFile* VFileOpen(const char* path, int mode) {
	++reopenCalls;
	reopenArgumentsExact = strcmp(path, "/tmp/log") == 0 &&
	    mode == (O_CREAT | O_WRONLY | O_APPEND);
	return &replacementFile.vf;
}

static ssize_t fakeWrite(struct VFile* vf, const void* bytes, size_t size) {
	struct FakeFile* file = (struct FakeFile*) vf;
	++file->writes;
	if (file->forceResult) {
		if (file->forcedResult > 0) {
			size_t copied = (size_t) file->forcedResult;
			if (copied > size) {
				copied = size;
			}
			memcpy(file->bytes + file->length, bytes, copied);
			file->length += copied;
		}
		return file->forcedResult;
	}
	if (size > sizeof(file->bytes) - file->length) {
		return -1;
	}
	memcpy(file->bytes + file->length, bytes, size);
	file->length += size;
	return (ssize_t) size;
}

static bool fakeSync(struct VFile* vf, void* data, size_t size) {
	(void) vf;
	(void) data;
	(void) size;
	++syncCalls;
	return false;
}

static bool fakeClose(struct VFile* vf) {
	++((struct FakeFile*) vf)->closes;
	return true;
}

static struct FakeFile makeFile(void) {
	struct FakeFile file = {0};
	file.vf.write = fakeWrite;
	file.vf.sync = fakeSync;
	file.vf.close = fakeClose;
	return file;
}

static size_t GBASavedataSize(const struct GBASavedata* savedata) {
	return savedata->size;
}

static void GBASavedataUnmask(struct GBASavedata* savedata) {
	(void) savedata;
}

static void GBASavedataRTCWrite(struct GBASavedata* savedata) {
	++savedata->rtcWrites;
}

#define mLOG(CATEGORY, LEVEL, ...) mLog(1, mLOG_INFO, __VA_ARGS__)

static struct mLogger* _defaultLogger;
void mLog(int category, enum mLogLevel level, const char* format, ...);

PHASE1_INSERT_PINNED_M_SAVEDATA_CLEAN
PHASE1_INSERT_PINNED_GBA_SAVEDATA_CLEAN
PHASE1_INSERT_PINNED_MLOG_GET_THREAD
PHASE1_INSERT_PINNED_MLOG_GET_CONTEXT
PHASE1_INSERT_PINNED_MLOG_SET_DEFAULT
PHASE1_INSERT_PINNED_MLOG
PHASE1_INSERT_PINNED_STANDARD_LOG
PHASE1_INSERT_PINNED_GUI_LOG

static void fanoutLog(struct mLogger* logger, int category,
                      enum mLogLevel level, const char* format, va_list args) {
	(void) logger;
	va_list standardArgs;
	va_copy(standardArgs, args);
	standardLogger.d.log(&standardLogger.d, category, level, format, standardArgs);
	va_end(standardArgs);
	va_list guiArgs;
	va_copy(guiArgs, args);
	guiLogger.d.log(&guiLogger.d, category, level, format, guiArgs);
	va_end(guiArgs);
}

static void emitLog(const char* message) {
	mLog(1, mLOG_INFO, "%s", message);
}

static void resetFile(struct FakeFile* file) {
	memset(file->bytes, 0, sizeof(file->bytes));
	file->length = 0;
	file->writes = 0;
	file->closes = 0;
	file->forcedResult = 0;
	file->forceResult = false;
}

int main(void) {
	standardFile = makeFile();
	guiFile = makeFile();
	replacementFile = makeFile();
	shortFile = makeFile();
	struct mLogFilter standardFilter = {.defaultLevels = mLOG_INFO};
	standardLogger.d.log = PHASE1_PINNED_STANDARD_LOG_SYMBOL;
	standardLogger.d.filter = &standardFilter;
	standardLogger.logToStdout = true;
	standardLogger.logFile = &standardFile.vf;
	guiLogger.d.log = PHASE1_PINNED_GUI_LOG_SYMBOL;
	guiLogger.logLevel = mLOG_INFO;
	guiLogger.vf = &guiFile.vf;
	router.log = fanoutLog;
	router.filter = NULL;
	mLogSetDefaultLogger(&router);

	char standardOutput[1024] = {0};
	FILE* capture = tmpfile();
	if (!capture) {
		return 2;
	}
	int stdoutFd = dup(STDOUT_FILENO);
	if (stdoutFd < 0 || dup2(fileno(capture), STDOUT_FILENO) < 0) {
		return 3;
	}
	uint8_t saveData[32] = {0};
	struct GBASavedata savedata = {
		.vf = &standardFile.vf,
		.dirty = mSAVEDATA_DIRT_SEEN,
		.dirtAge = 0,
		.mapMode = MAP_WRITE,
		.data = saveData,
		.size = sizeof(saveData)
	};
	GBASavedataClean(&savedata, 16);
	fflush(stdout);
	if (dup2(stdoutFd, STDOUT_FILENO) < 0) {
		return 4;
	}
	close(stdoutFd);
	rewind(capture);
	size_t standardOutputLength = fread(
	    standardOutput, 1, sizeof(standardOutput) - 1, capture);
	standardOutput[standardOutputLength] = '\0';
	fclose(capture);
	bool standardStdoutExact =
	    strcmp(standardOutput, "GBA: Savedata failed to sync!\n") == 0;
	bool standardFileExact =
	    standardFile.length == strlen("GBA: Savedata failed to sync!\n") &&
	    memcmp(standardFile.bytes, "GBA: Savedata failed to sync!\n",
	           standardFile.length) == 0;
	bool guiFileExact =
	    guiFile.length == strlen("GBA: Savedata failed to sync!\n") &&
	    memcmp(guiFile.bytes, "GBA: Savedata failed to sync!\n",
	           guiFile.length) == 0;

	standardLogger.logToStdout = false;
	standardLogger.logFile = NULL;
	guiLogger.logLevel = 0;
	resetFile(&guiFile);
	emitLog("filtered control");
	unsigned filteredWrites = guiFile.writes;

	guiLogger.logLevel = mLOG_INFO;
	guiLogger.vf = NULL;
	emitLog("missing sink control");
	unsigned missingSinkWrites = guiFile.writes;

	guiLogger.vf = &guiFile.vf;
	guiFile.forceResult = true;
	guiFile.forcedResult = -1;
	emitLog("reopen control");
	unsigned negativeWriteCalls = guiFile.writes;
	unsigned negativeWriteCloses = guiFile.closes;
	unsigned negativeReopenCalls = reopenCalls;
	bool recoveryFileExact =
	    replacementFile.length == strlen("GBA: reopen control\n") &&
	    memcmp(replacementFile.bytes, "GBA: reopen control\n",
	           replacementFile.length) == 0;

	guiLogger.vf = &shortFile.vf;
	shortFile.forceResult = true;
	shortFile.forcedResult = 1;
	reopenCalls = 0;
	emitLog("short control");

	printf(
	    "PHASE1_MGBA_FRONTEND_LOG_WITNESS "
	    "{\"evidence_class\":\"compiled_pinned_source_host_sink\","
	    "\"native_frontend_runtime_observed\":false,"
	    "\"sync_failure_calls\":%u,"
	    "\"standard_stdout_exact\":%s,"
	    "\"standard_file_exact\":%s,"
	    "\"gui_file_exact\":%s,"
	    "\"gui_filter_suppressed_writes\":%u,"
	    "\"gui_missing_sink_writes\":%u,"
	    "\"gui_negative_write_calls\":%u,"
	    "\"gui_negative_write_closes\":%u,"
	    "\"gui_negative_reopen_calls\":%u,"
	    "\"gui_reopen_arguments_exact\":%s,"
	    "\"gui_recovery_file_exact\":%s,"
	    "\"gui_positive_short_calls\":%u,"
	    "\"gui_positive_short_retries\":%u,"
	    "\"persistence_acknowledgment\":false,"
	    "\"stock_gameplay\":false,\"physical_flash\":false}\n",
	    syncCalls, standardStdoutExact ? "true" : "false",
	    standardFileExact ? "true" : "false",
	    guiFileExact ? "true" : "false",
	    filteredWrites, missingSinkWrites, negativeWriteCalls,
	    negativeWriteCloses, negativeReopenCalls,
	    reopenArgumentsExact ? "true" : "false",
	    recoveryFileExact ? "true" : "false",
	    shortFile.writes, reopenCalls);
	return 0;
}
