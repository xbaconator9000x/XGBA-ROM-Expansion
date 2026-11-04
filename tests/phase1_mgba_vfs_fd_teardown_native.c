#include <mgba-util/memory.h>
#include <mgba-util/vfs.h>

#include <errno.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#ifndef UNUSED
#define UNUSED(value) ((void) (value))
#endif
#define GBA_SIZE_SRAM 4096
#define GBA_SIZE_SRAM512 512
#define GBA_SIZE_FLASH512 8192
#define GBA_SIZE_FLASH1M 16384
#define GBA_SIZE_EEPROM 8192
#define GBA_SIZE_EEPROM512 512
#define GBA_SIZE_ROM0 32768
#define GBA_IDLE_LOOP_NONE 0

enum GBASavedataType {
	GBA_SAVEDATA_AUTODETECT,
	GBA_SAVEDATA_SRAM,
	GBA_SAVEDATA_SRAM512,
	GBA_SAVEDATA_FLASH512,
	GBA_SAVEDATA_FLASH1M,
	GBA_SAVEDATA_EEPROM,
	GBA_SAVEDATA_EEPROM512,
	GBA_SAVEDATA_FORCE_NONE
};

enum {
	EEPROM_COMMAND_NULL,
	FLASH_STATE_RAW
};

struct mTiming {
	int unused;
};

struct mTimingEvent {
	const char* name;
	int priority;
	void* context;
	void (*callback)(struct mTiming*, void*, uint32_t);
};

struct GBASavedata {
	void* p;
	enum GBASavedataType type;
	uint8_t* data;
	int command;
	int flashState;
	struct VFile* vf;
	int mapMode;
	bool maskWriteback;
	struct VFile* realVf;
	int dirty;
	uint32_t dirtAge;
	struct mTimingEvent dust;
};

struct GBA {
	struct {
		struct {
			unsigned type;
		} unl;
		uint8_t* rom;
		size_t romSize;
		uint32_t romMask;
		struct GBASavedata savedata;
	} memory;
	struct VFile* romVf;
	size_t pristineRomSize;
	bool isPristine;
	size_t yankedRomSize;
	int idleLoop;
};

static void* failSyncMap;
static void* failUnmapMap;
static int failCloseFd = -1;
static unsigned closeFailuresRemaining;
static int shortReadFd = -1;
static unsigned syncCalls;
static unsigned syncErrors;
static unsigned unmapCalls;
static unsigned unmapErrors;
static unsigned closeCalls;
static unsigned closeErrors;
static unsigned shortReadBytes;
static unsigned shortReadRequested;
static bool traceEnabled;
static char trace[64];
static size_t traceLength;
static int tracedFds[2] = {-1, -1};

static void record(char event) {
	if (traceEnabled && traceLength + 1 < sizeof(trace)) {
		trace[traceLength++] = event;
		trace[traceLength] = '\0';
	}
}

void* anonymousMemoryMap(size_t size) {
	return calloc(1, size);
}

void mappedMemoryFree(void* memory, size_t size) {
	UNUSED(size);
	free(memory);
}

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	UNUSED(vf);
	UNUSED(buffer);
	UNUSED(size);
	return -1;
}

static size_t GBASavedataSize(const struct GBASavedata* savedata);
static void GBASavedataInit(struct GBASavedata* savedata, struct VFile* vf);
static void GBASavedataDeinit(struct GBASavedata* savedata);
static void GBASavedataMask(struct GBASavedata* savedata, struct VFile* vf,
                            bool writeback);
static bool GBASavedataLoad(struct GBASavedata* savedata, struct VFile* in);
static void GBASavedataUnmask(struct GBASavedata* savedata);
static void GBASavedataForceType(struct GBASavedata* savedata,
                                 enum GBASavedataType type);
static void GBAUnloadROM(struct GBA* gba);

PHASE1_INSERT_PINNED_ASHES

PHASE1_INSERT_PINNED_SAVEDATA_SIZE

PHASE1_INSERT_PINNED_SAVEDATA_INIT

PHASE1_INSERT_PINNED_SAVEDATA_DEINIT

PHASE1_INSERT_PINNED_SAVEDATA_MASK

PHASE1_INSERT_PINNED_SAVEDATA_LOAD

PHASE1_INSERT_PINNED_SAVEDATA_UNMASK

static void GBASavedataForceType(struct GBASavedata* savedata,
                                 enum GBASavedataType type) {
	savedata->type = type;
	if (savedata->vf && type != GBA_SAVEDATA_FORCE_NONE) {
		ssize_t size = savedata->vf->size(savedata->vf);
		if (size <= 0) {
			savedata->data = NULL;
			return;
		}
		savedata->data = savedata->vf->map(savedata->vf, (size_t) size,
		                                   savedata->mapMode);
	}
}

static void GBAMemoryClearAGBPrint(struct GBA* gba) {
	UNUSED(gba);
}

static void GBAUnlCartUnload(struct GBA* gba) {
	UNUSED(gba);
}

PHASE1_INSERT_PINNED_GBA_UNLOAD_ROM

int __real_msync(void* memory, size_t size, int flags);
int __wrap_msync(void* memory, size_t size, int flags) {
	if (flags == MS_SYNC) {
		++syncCalls;
		record('S');
		if (memory == failSyncMap) {
			++syncErrors;
			errno = EIO;
			return -1;
		}
	}
	return __real_msync(memory, size, flags);
}

int __real_munmap(void* memory, size_t size);
int __wrap_munmap(void* memory, size_t size) {
	++unmapCalls;
	record('U');
	if (memory == failUnmapMap) {
		++unmapErrors;
		errno = EIO;
		return -1;
	}
	return __real_munmap(memory, size);
}

int __real_close(int fd);
int __wrap_close(int fd) {
	if (fd == tracedFds[0] || fd == tracedFds[1]) {
		++closeCalls;
		record('C');
	}
	if (fd == failCloseFd && closeFailuresRemaining) {
		--closeFailuresRemaining;
		++closeErrors;
		errno = EIO;
		return -1;
	}
	return __real_close(fd);
}

ssize_t __real_read(int fd, void* buffer, size_t size);
ssize_t __wrap_read(int fd, void* buffer, size_t size) {
	ssize_t result = __real_read(fd, buffer, size);
	if (fd == shortReadFd && size > shortReadRequested) {
		shortReadRequested = (unsigned) size;
		shortReadBytes = result > 0 ? (unsigned) result : 0;
	}
	return result;
}

static void fail(const char* message) {
	perror(message);
	_exit(90);
}

static int make_file(const char* path, size_t size, uint8_t initial) {
	int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0600);
	if (fd < 0 || ftruncate(fd, (off_t) size) < 0 ||
	    pwrite(fd, &initial, 1, 0) != 1) {
		fail("create temporary savedata file");
	}
	return fd;
}

static uint8_t read_in_child(const char* path) {
	pid_t child = fork();
	if (child < 0) {
		fail("fork");
	}
	if (!child) {
		int fd = open(path, O_RDONLY);
		uint8_t value = 0;
		ssize_t count = fd < 0 ? -1 : pread(fd, &value, 1, 0);
		if (fd >= 0) {
			close(fd);
		}
		_exit(count == 1 ? value : 91);
	}
	int status = 0;
	if (waitpid(child, &status, 0) != child ||
	    !WIFEXITED(status) || WEXITSTATUS(status) > UINT8_MAX) {
		fail("read savedata in child");
	}
	return (uint8_t) WEXITSTATUS(status);
}

static void reset_trace(int fd1, int fd2) {
	syncCalls = syncErrors = unmapCalls = unmapErrors = 0;
	closeCalls = closeErrors = 0;
	shortReadBytes = shortReadRequested = 0;
	traceLength = 0;
	trace[0] = '\0';
	tracedFds[0] = fd1;
	tracedFds[1] = fd2;
	failSyncMap = NULL;
	failUnmapMap = NULL;
	failCloseFd = -1;
	closeFailuresRemaining = 0;
	shortReadFd = -1;
}

static struct VFile* init_savedata(struct GBA* gba, const char* path,
                                  uint8_t initial, uint8_t replacement,
                                  int* fd, uint8_t** data) {
	memset(gba, 0, sizeof(*gba));
	*fd = make_file(path, 4096, initial);
	struct VFile* vf = VFileFromFD(*fd);
	if (!vf) {
		fail("VFileFromFD");
	}
	GBASavedataInit(&gba->memory.savedata, vf);
	GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_AUTODETECT);
	if (!gba->memory.savedata.data) {
		fail("map initialized savedata");
	}
	*data = gba->memory.savedata.data;
	(*data)[0] = replacement;
	return vf;
}

static void test_unload_case(const char* directory, const char* label,
                             uint8_t replacement, bool failSync,
                             bool failUnmap, bool failClose) {
	char path[PATH_MAX];
	snprintf(path, sizeof(path), "%s/%s.sav", directory, label);
	struct GBA gba;
	int fd;
	uint8_t* data;
	struct VFile* vf = init_savedata(&gba, path, 0x11, replacement, &fd, &data);
	reset_trace(fd, -1);
	if (failSync) {
		failSyncMap = data;
	}
	if (failUnmap) {
		failUnmapMap = data;
	}
	if (failClose) {
		failCloseFd = fd;
		closeFailuresRemaining = 1;
	}
	traceEnabled = true;
	GBAUnloadROM(&gba);
	traceEnabled = false;

	bool cleared = !gba.memory.savedata.vf && !gba.memory.savedata.data &&
	               !gba.memory.savedata.realVf;
	bool orphanReadable = failUnmap && data[0] == replacement;
	unsigned orphanByte = orphanReadable ? data[0] : 0;
	unsigned observedSyncCalls = syncCalls;
	unsigned observedSyncErrors = syncErrors;
	unsigned observedUnmapCalls = unmapCalls;
	unsigned observedUnmapErrors = unmapErrors;
	unsigned observedCloseCalls = closeCalls;
	unsigned observedCloseErrors = closeErrors;
	char observedTrace[sizeof(trace)];
	snprintf(observedTrace, sizeof(observedTrace), "%s", trace);
	tracedFds[0] = tracedFds[1] = -1;
	unsigned retryClose = 0;
	if (failClose) {
		if (vf->size(vf) != 4096 || !vf->close(vf)) {
			fprintf(stderr, "failed close did not retain a retryable VFile\n");
			exit(1);
		}
		retryClose = 1;
	}
	uint8_t freshByte = read_in_child(path);
	if (!cleared || observedSyncCalls != 1 ||
	    observedSyncErrors != (unsigned) failSync ||
	    observedUnmapCalls != 1 || observedUnmapErrors != (unsigned) failUnmap ||
	    observedCloseCalls != 1 || observedCloseErrors != (unsigned) failClose ||
	    orphanReadable != failUnmap || freshByte != replacement) {
		fprintf(stderr, "unexpected GBA unload state for %s\n", label);
		exit(1);
	}
	if (failUnmap && __real_munmap(data, 4096) < 0) {
		fail("manual orphan mapping cleanup");
	}
	printf("PHASE1_TEARDOWN_CASE %s sync_calls=%u sync_errors=%u "
	       "unmap_calls=%u unmap_errors=%u close_calls=%u close_errors=%u "
	       "state_cleared=%u orphan_map_read=%u retry_close=%u "
	       "fresh_process_byte=%u trace=%s\n",
	       label, observedSyncCalls, observedSyncErrors, observedUnmapCalls,
	       observedUnmapErrors, observedCloseCalls, observedCloseErrors,
	       (unsigned) cleared, orphanByte, retryClose, freshByte, observedTrace);
	if (unlink(path) < 0) {
		fail("remove temporary savedata file");
	}
}

static void test_masked_writeback(const char* directory) {
	char realPath[PATH_MAX];
	char maskPath[PATH_MAX];
	snprintf(realPath, sizeof(realPath), "%s/masked-real.sav", directory);
	snprintf(maskPath, sizeof(maskPath), "%s/masked-temp.sav", directory);
	struct GBA gba;
	memset(&gba, 0, sizeof(gba));
	int realFd = make_file(realPath, 4096, 0x11);
	struct VFile* realVf = VFileFromFD(realFd);
	if (!realVf) {
		fail("open real VFile");
	}
	GBASavedataInit(&gba.memory.savedata, realVf);
	GBASavedataForceType(&gba.memory.savedata, GBA_SAVEDATA_AUTODETECT);
	int maskFd = make_file(maskPath, 32, 0xE5);
	struct VFile* maskVf = VFileFromFD(maskFd);
	if (!maskVf) {
		fail("open masked VFile");
	}
	GBASavedataMask(&gba.memory.savedata, maskVf, true);
	uint8_t* maskData = gba.memory.savedata.data;
	if (!maskData) {
		fail("map masked savedata");
	}
	maskData[0] = 0x5A;
	gba.memory.savedata.dirty = 1;
	reset_trace(realFd, maskFd);
	failSyncMap = maskData;
	failUnmapMap = maskData;
	failCloseFd = maskFd;
	closeFailuresRemaining = 1;
	shortReadFd = maskFd;
	traceEnabled = true;
	GBAUnloadROM(&gba);
	traceEnabled = false;

	bool cleared = !gba.memory.savedata.vf && !gba.memory.savedata.data &&
	               !gba.memory.savedata.realVf &&
	               !gba.memory.savedata.maskWriteback;
	bool loadWasShort = shortReadBytes == 32 && shortReadRequested == 4096;
	bool orphanReadable = maskData[0] == 0x5A;
	unsigned orphanByte = orphanReadable ? maskData[0] : 0;
	unsigned observedSyncCalls = syncCalls;
	unsigned observedSyncErrors = syncErrors;
	unsigned observedUnmapCalls = unmapCalls;
	unsigned observedUnmapErrors = unmapErrors;
	unsigned observedCloseCalls = closeCalls;
	unsigned observedCloseErrors = closeErrors;
	unsigned observedReadBytes = shortReadBytes;
	unsigned observedReadRequested = shortReadRequested;
	char observedTrace[sizeof(trace)];
	snprintf(observedTrace, sizeof(observedTrace), "%s", trace);
	tracedFds[0] = tracedFds[1] = -1;
	if (!cleared || !loadWasShort || !orphanReadable || syncCalls != 2 ||
	    syncErrors != 1 || unmapCalls != 2 || unmapErrors != 1 ||
	    closeCalls != 2 || closeErrors != 1 ||
	    strcmp(observedTrace, "SUCSUC") != 0) {
		fprintf(stderr, "masked writeback failure path changed\n");
		exit(1);
	}
	if (!maskVf->close(maskVf) || __real_munmap(maskData, 32) < 0) {
		fail("cleanup orphaned masked VFile");
	}
	uint8_t freshByte = read_in_child(realPath);
	if (freshByte != 0xE5) {
		fprintf(stderr, "short masked read was not reflected in savedata mapping\n");
		exit(1);
	}
	printf("PHASE1_TEARDOWN_CASE masked_writeback_short_read "
	       "sync_calls=%u sync_errors=%u unmap_calls=%u unmap_errors=%u "
	       "close_calls=%u close_errors=%u state_cleared=%u "
	       "orphan_map_read=%u retry_close=1 fresh_process_byte=%u "
	       "short_read=%u requested=%u trace=%s\n",
	       observedSyncCalls, observedSyncErrors, observedUnmapCalls,
	       observedUnmapErrors, observedCloseCalls, observedCloseErrors,
	       (unsigned) cleared, orphanByte, freshByte, observedReadBytes,
	       observedReadRequested, observedTrace);
	if (unlink(realPath) < 0 || unlink(maskPath) < 0) {
		fail("remove masked VFile files");
	}
}

static void test_memory_vfile(void) {
	uint8_t backing[32] = {0};
	struct VFile* borrowed = VFileFromMemory(backing, sizeof(backing));
	if (!borrowed) {
		fail("VFileFromMemory");
	}
	uint8_t* borrowedMap = borrowed->map(borrowed, sizeof(backing), MAP_WRITE);
	if (!borrowedMap) {
		fail("map borrowed memory VFile");
	}
	borrowedMap[0] = 0xCC;
	bool borrowedSync = borrowed->sync(borrowed, borrowedMap, sizeof(backing));
	borrowed->unmap(borrowed, borrowedMap, sizeof(backing));
	bool borrowedLive = backing[0] == 0xCC;
	bool borrowedClose = borrowed->close(borrowed);

	struct VFile* chunk = VFileMemChunk(NULL, sizeof(backing));
	if (!chunk) {
		fail("VFileMemChunk");
	}
	uint8_t* chunkMap = chunk->map(chunk, sizeof(backing), MAP_WRITE);
	if (!chunkMap) {
		fail("map chunk memory VFile");
	}
	chunkMap[0] = 0xDD;
	bool chunkSync = chunk->sync(chunk, chunkMap, sizeof(backing));
	chunk->unmap(chunk, chunkMap, sizeof(backing));
	bool chunkLive = chunkMap[0] == 0xDD;
	bool chunkClose = chunk->close(chunk);
	if (!borrowedSync || !borrowedLive || !borrowedClose ||
	    !chunkSync || !chunkLive || !chunkClose || backing[0] != 0xCC) {
		fprintf(stderr, "memory VFile no-op sync/unmap/close behavior changed\n");
		exit(1);
	}
	printf("PHASE1_TEARDOWN_CASE memory borrowed_unmap_live=1 borrowed_sync=1 "
	       "borrowed_close=1 borrowed_byte=%u chunk_unmap_live=1 "
	       "chunk_sync=1 chunk_close=1\n", backing[0]);
}

int main(void) {
	char directory[] = "/tmp/mgba-vfs-teardown-XXXXXX";
	if (!mkdtemp(directory)) {
		fail("mkdtemp");
	}
	test_unload_case(directory, "success", 161, false, false, false);
	test_unload_case(directory, "sync_failure", 162, true, false, false);
	test_unload_case(directory, "unmap_failure", 163, false, true, false);
	test_unload_case(directory, "close_failure", 164, false, false, true);
	test_masked_writeback(directory);
	test_memory_vfile();
	if (rmdir(directory) < 0) {
		fail("remove temporary directory");
	}
	puts("PHASE1_TEARDOWN_DONE");
	return 0;
}
