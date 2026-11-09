#include <mgba-util/vfs.h>

#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#define GBA_SIZE_SRAM 4096
#define GBA_SIZE_SRAM512 512
#define GBA_SIZE_FLASH512 8192
#define GBA_SIZE_FLASH1M 16384
#define GBA_SIZE_EEPROM 8192
#define GBA_SIZE_EEPROM512 512
#define GBA_SIZE_ROM0 32768
#define GBA_SIZE_BIOS 16384
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
		uint8_t* bios;
		struct GBASavedata savedata;
	} memory;
	struct VFile* romVf;
	struct VFile* biosVf;
	size_t pristineRomSize;
	bool isPristine;
	size_t yankedRomSize;
	int idleLoop;
	int video;
	int audio;
	int sio;
	struct mTiming timing;
	int coreCallbacks;
};

struct ARMCore {
	int unused;
};

struct mCoreOpts {
	int unused;
};

struct mCore {
	struct ARMCore* cpu;
	struct GBA* board;
	struct mCoreOpts opts;
};

struct GBACore {
	struct mCore d;
	void* debuggerPlatform;
	void* cheatDevice;
};

static size_t GBASavedataSize(const struct GBASavedata* savedata);
static void GBASavedataDeinit(struct GBASavedata* savedata);
static void GBASavedataUnmask(struct GBASavedata* savedata);
static bool GBASavedataLoad(struct GBASavedata* savedata, struct VFile* in);
static void GBASavedataForceType(struct GBASavedata* savedata,
                                 enum GBASavedataType type);
static void GBAUnloadROM(struct GBA* gba);
static void GBADestroy(struct GBA* gba);
static void _GBACoreDeinit(struct mCore* core);

int __wrap_close(int fd);
int __real_close(int fd);
int __wrap_msync(void* memory, size_t size, int flags);
int __real_msync(void* memory, size_t size, int flags);
int __wrap_munmap(void* memory, size_t size);
int __real_munmap(void* memory, size_t size);
void __real_free(void* memory);

static int tracedFd = -1;
static int failCloseFd = -1;
static unsigned closeFailuresRemaining;
static bool failSync;
static bool traceEnabled;
static unsigned syncCalls;
static unsigned syncErrors;
static unsigned unmapCalls;
static unsigned closeCalls;
static unsigned closeErrors;
static unsigned boardFreeCalls;
static unsigned coreFreeCalls;
static bool savedataClearedOnBoardFree;
static struct GBA* trackedBoard;
static struct mCore* trackedCore;
static char trace[16];
static size_t traceLength;

static void record(char event) {
	if (traceEnabled && traceLength + 1 < sizeof(trace)) {
		trace[traceLength++] = event;
		trace[traceLength] = '\0';
	}
}

int __wrap_close(int fd) {
	if (traceEnabled && fd == tracedFd) {
		++closeCalls;
		record('C');
		if (fd == failCloseFd && closeFailuresRemaining) {
			--closeFailuresRemaining;
			++closeErrors;
			errno = EIO;
			return -1;
		}
	}
	return __real_close(fd);
}

int __wrap_msync(void* memory, size_t size, int flags) {
	if (traceEnabled && flags == MS_SYNC) {
		++syncCalls;
		record('S');
		if (failSync) {
			++syncErrors;
			errno = EIO;
			return -1;
		}
	}
	return __real_msync(memory, size, flags);
}

int __wrap_munmap(void* memory, size_t size) {
	if (traceEnabled) {
		++unmapCalls;
		record('U');
	}
	return __real_munmap(memory, size);
}

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	(void) vf;
	(void) buffer;
	(void) size;
	return -1;
}

void* anonymousMemoryMap(size_t size) {
	return calloc(1, size);
}

void mappedMemoryFree(void* memory, size_t size) {
	(void) size;
	if (memory == trackedBoard) {
		struct GBA* gba = memory;
		savedataClearedOnBoardFree =
			!gba->memory.savedata.vf && !gba->memory.savedata.data &&
			!gba->memory.savedata.realVf;
		++boardFreeCalls;
	}
	free(memory);
}

void __wrap_free(void* memory) {
	if (memory == trackedCore) {
		++coreFreeCalls;
	}
	__real_free(memory);
}

static void ARMDeinit(struct ARMCore* cpu) {
	(void) cpu;
}

static void GBAMemoryClearAGBPrint(struct GBA* gba) {
	(void) gba;
}

static void GBAUnlCartUnload(struct GBA* gba) {
	(void) gba;
}

static void GBAUnloadMB(struct GBA* gba) {
	(void) gba;
}

static void GBAMemoryDeinit(struct GBA* gba) {
	(void) gba;
}

static void GBAVideoDeinit(void* video) {
	(void) video;
}

static void GBAAudioDeinit(void* audio) {
	(void) audio;
}

static void GBASIODeinit(void* sio) {
	(void) sio;
}

static void mTimingDeinit(struct mTiming* timing) {
	(void) timing;
}

static void mCoreCallbacksListDeinit(void* callbacks) {
	(void) callbacks;
}

static void mCoreConfigFreeOpts(struct mCoreOpts* opts) {
	(void) opts;
}

static bool GBASavedataLoad(struct GBASavedata* savedata,
                            struct VFile* input) {
	(void) savedata;
	(void) input;
	return false;
}

static void GBASavedataForceType(struct GBASavedata* savedata,
                                 enum GBASavedataType type) {
	(void) savedata;
	(void) type;
}

static void mCheatDeviceDestroy(void* cheatDevice) {
	(void) cheatDevice;
}

PHASE1_INSERT_PINNED_SAVEDATA_SIZE

PHASE1_INSERT_PINNED_SAVEDATA_DEINIT

PHASE1_INSERT_PINNED_SAVEDATA_UNMASK

PHASE1_INSERT_PINNED_GBA_UNLOAD_ROM

PHASE1_INSERT_PINNED_GBA_DESTROY

PHASE1_INSERT_PINNED_GBA_CORE_DEINIT

static int make_savedata_file(const char* path) {
	int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0600);
	if (fd < 0 || ftruncate(fd, GBA_SIZE_SRAM) < 0) {
		perror("create savedata fixture");
		exit(1);
	}
	return fd;
}

static void reset_observations(void) {
	syncCalls = syncErrors = unmapCalls = 0;
	closeCalls = closeErrors = 0;
	boardFreeCalls = coreFreeCalls = 0;
	savedataClearedOnBoardFree = false;
	traceLength = 0;
	trace[0] = '\0';
	failCloseFd = -1;
	closeFailuresRemaining = 0;
	failSync = false;
}

static bool descriptor_open(int fd) {
	errno = 0;
	return fcntl(fd, F_GETFD) >= 0;
}

static void run_case(const char* directory, const char* label,
                     bool injectSyncFailure, bool injectCloseFailure) {
	char path[512];
	snprintf(path, sizeof(path), "%s/%s.sav", directory, label);
	int fd = make_savedata_file(path);
	struct VFile* vf = VFileFromFD(fd);
	if (!vf) {
		perror("VFileFromFD");
		exit(1);
	}

	struct GBA* gba = calloc(1, sizeof(*gba));
	struct ARMCore* cpu = calloc(1, sizeof(*cpu));
	struct GBACore* gbacore = calloc(1, sizeof(*gbacore));
	if (!gba || !cpu || !gbacore) {
		perror("allocate core fixture");
		exit(1);
	}
	gba->memory.savedata.vf = vf;
	gba->memory.savedata.realVf = vf;
	gba->memory.savedata.type = GBA_SAVEDATA_SRAM;
	gba->memory.savedata.mapMode = MAP_WRITE;
	gba->memory.savedata.data = vf->map(vf, GBA_SIZE_SRAM, MAP_WRITE);
	if (!gba->memory.savedata.data) {
		fprintf(stderr, "savedata mapping setup failed\n");
		exit(1);
	}
	gba->memory.savedata.data[0] = 0xA7;
	gbacore->d.cpu = cpu;
	gbacore->d.board = gba;

	reset_observations();
	tracedFd = fd;
	trackedBoard = gba;
	trackedCore = &gbacore->d;
	failSync = injectSyncFailure;
	if (injectCloseFailure) {
		failCloseFd = fd;
		closeFailuresRemaining = 1;
	}
	traceEnabled = true;
	_GBACoreDeinit(&gbacore->d);
	traceEnabled = false;

	bool fdOpenAfter = descriptor_open(fd);
	bool wrapperSurvives = false;
	bool harnessCleanupClose = false;
	if (injectCloseFailure) {
		wrapperSurvives = vf->size(vf) == GBA_SIZE_SRAM;
		failCloseFd = -1;
		harnessCleanupClose = vf->close(vf);
	}
	bool expectedOpen = injectCloseFailure;
	bool valid = syncCalls == 1 && syncErrors == (unsigned) injectSyncFailure &&
		unmapCalls == 1 && closeCalls == 1 &&
		closeErrors == (unsigned) injectCloseFailure &&
		boardFreeCalls == 1 && coreFreeCalls == 1 &&
		savedataClearedOnBoardFree && fdOpenAfter == expectedOpen &&
		(!injectCloseFailure || (wrapperSurvives && harnessCleanupClose)) &&
		(injectCloseFailure || !fdOpenAfter) &&
		strcmp(trace, "SUC") == 0;

	printf("PHASE1_CORE_TEARDOWN_CASE %s sync_calls=%u sync_errors=%u "
	       "unmap_calls=%u close_calls=%u close_errors=%u "
	       "savedata_refs_cleared=%u board_freed=%u core_freed=%u "
	       "fd_open_after_production=%u wrapper_survives=%u "
	       "harness_cleanup_close=%u production_retry=0 trace=%s\n",
	       label, syncCalls, syncErrors, unmapCalls, closeCalls, closeErrors,
	       (unsigned) savedataClearedOnBoardFree, boardFreeCalls, coreFreeCalls,
	       (unsigned) fdOpenAfter, (unsigned) wrapperSurvives,
	       (unsigned) harnessCleanupClose, trace);
	tracedFd = -1;
	trackedBoard = NULL;
	trackedCore = NULL;
	if (!valid || (!injectCloseFailure && unlink(path) < 0) ||
	    (injectCloseFailure && unlink(path) < 0)) {
		fprintf(stderr, "production core teardown case failed: %s\n", label);
		exit(1);
	}
}

int main(void) {
	char directory[] = "/tmp/mgba-core-teardown-XXXXXX";
	if (!mkdtemp(directory)) {
		perror("mkdtemp");
		return 1;
	}
	run_case(directory, "normal", false, false);
	run_case(directory, "sync_and_close_failure", true, true);
	if (rmdir(directory) < 0) {
		perror("rmdir");
		return 1;
	}
	puts("PHASE1_CORE_TEARDOWN_DONE");
	return 0;
}
