#include <mgba/core/cheats.h>
#include <mgba/core/core.h>
#include <mgba/core/serialize.h>
#include <mgba/gba/interface.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/savedata.h>
#include <mgba-util/math.h>
#include <mgba-util/memory.h>
#include <mgba-util/vfs.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STATE_SIZE 8
#define SAVEDATA_SIZE GBA_SIZE_SRAM
#define HEADER_SIZE 16
#define SAVEDATA_OFFSET (STATE_SIZE + 2 * HEADER_SIZE)
#define SNAPSHOT_SIZE (SAVEDATA_OFFSET + SAVEDATA_SIZE)

static void* allocations[64];
static size_t allocationCount;
static bool captureRestoreVFile;
static size_t restoreVFilesCreated;
static size_t restoreVFilesClosed;
static bool (*restoreVFileClose)(struct VFile*);

extern void* __real_malloc(size_t);
extern void __real_free(void*);
extern struct VFile* __real_VFileMemChunk(const void*, size_t);

void* __wrap_malloc(size_t size) {
	void* allocation = __real_malloc(size);
	if (!allocation) {
		return NULL;
	}
	if (allocationCount == sizeof(allocations) / sizeof(allocations[0])) {
		__real_free(allocation);
		return NULL;
	}
	allocations[allocationCount++] = allocation;
	return allocation;
}

void __wrap_free(void* allocation) {
	if (!allocation) {
		return;
	}
	for (size_t i = 0; i < allocationCount; ++i) {
		if (allocations[i] == allocation) {
			allocations[i] = allocations[--allocationCount];
			break;
		}
	}
	__real_free(allocation);
}

void* anonymousMemoryMap(size_t size) {
	void* memory = malloc(size);
	if (memory) {
		memset(memory, 0, size);
	}
	return memory;
}

void mappedMemoryFree(void* memory, size_t size) {
	(void) size;
	free(memory);
}

size_t toPow2(size_t size) {
	size_t result = 1;
	while (result < size) {
		result <<= 1;
	}
	return result;
}

static bool observedRestoreClose(struct VFile* vf) {
	++restoreVFilesClosed;
	vf->close = restoreVFileClose;
	return restoreVFileClose(vf);
}

struct VFile* __wrap_VFileMemChunk(const void* memory, size_t size) {
	struct VFile* vf = __real_VFileMemChunk(memory, size);
	if (vf && captureRestoreVFile) {
		++restoreVFilesCreated;
		restoreVFileClose = vf->close;
		vf->close = observedRestoreClose;
	}
	return vf;
}

bool mCheatParseFile(struct mCheatDevice* device, struct VFile* vf) {
	(void) device;
	(void) vf;
	return false;
}

void mCheatDeviceClear(struct mCheatDevice* device) {
	(void) device;
}

int _mLOG_CAT_SAVESTATE;
int _mLOG_CAT_GBA_SAVE;

void mLog(int category, enum mLogLevel level, const char* format, ...) {
	(void) category;
	(void) level;
	(void) format;
}

void GBASavedataInitFlash(struct GBASavedata* savedata) {
	(void) savedata;
}

void GBASavedataInitEEPROM(struct GBASavedata* savedata) {
	(void) savedata;
}

void GBASavedataInitSRAM512(struct GBASavedata* savedata) {
	(void) savedata;
}

PHASE1_INSERT_PINNED_RESTORE_FUNCTIONS

static size_t stateSize(struct mCore* core) {
	(void) core;
	return STATE_SIZE;
}

static bool loadState(struct mCore* core, const void* state) {
	(void) core;
	return memcmp(state, "STATE123", STATE_SIZE) == 0;
}

static bool loadExtraState(struct mCore* core,
                           const struct mStateExtdata* extdata) {
	(void) core;
	(void) extdata;
	return true;
}

static void currentVideoSize(struct mCore* core, unsigned* width,
                             unsigned* height) {
	(void) core;
	*width = 0;
	*height = 0;
}

struct TestCore {
	struct mCore core;
	struct GBA gba;
	struct VFile* realSave;
	uint8_t* realSaveData;
	uint8_t initial[SAVEDATA_SIZE];
	uint8_t expected[SAVEDATA_SIZE];
};

static void fail(const char* message) {
	fprintf(stderr, "%s\n", message);
	exit(1);
}

static void initCore(struct TestCore* test) {
	memset(test, 0, sizeof(*test));
	memset(test->initial, 0xA5, sizeof(test->initial));
	for (size_t i = 0; i < sizeof(test->expected); ++i) {
		test->expected[i] = (uint8_t) (i * 13 + 7);
	}
	test->realSave = VFileMemChunk(test->initial, sizeof(test->initial));
	if (!test->realSave) {
		fail("failed to create host savedata VFile");
	}
	struct GBASavedata* savedata = &test->gba.memory.savedata;
	savedata->p = &test->gba;
	savedata->type = GBA_SAVEDATA_SRAM;
	savedata->vf = test->realSave;
	savedata->realVf = test->realSave;
	savedata->mapMode = MAP_WRITE;
	savedata->data = test->realSave->map(
	    test->realSave, SAVEDATA_SIZE, MAP_WRITE);
	test->realSaveData = savedata->data;
	if (!savedata->data) {
		fail("failed to map host savedata VFile");
	}
	test->core.board = &test->gba;
	test->core.stateSize = stateSize;
	test->core.loadState = loadState;
	test->core.loadExtraState = loadExtraState;
	test->core.currentVideoSize = currentVideoSize;
	test->core.savedataRestore = _GBACoreSavedataRestore;
}

enum SnapshotKind {
	SNAPSHOT_ABSENT,
	SNAPSHOT_SHORT_HEADER,
	SNAPSHOT_SHORT_PAYLOAD,
	SNAPSHOT_VALID
};

static size_t makeSnapshot(uint8_t* snapshot, const struct TestCore* test,
                           enum SnapshotKind kind) {
	memset(snapshot, 0, SNAPSHOT_SIZE);
	memcpy(snapshot, "STATE123", STATE_SIZE);
	if (kind == SNAPSHOT_ABSENT) {
		return STATE_SIZE;
	}
	if (kind == SNAPSHOT_SHORT_HEADER) {
		return STATE_SIZE + 5;
	}

	struct mStateExtdataHeader* header =
	    (struct mStateExtdataHeader*) (snapshot + STATE_SIZE);
	STORE_32LE(EXTDATA_SAVEDATA,
	           offsetof(struct mStateExtdataHeader, tag), &header[0]);
	STORE_32LE(SAVEDATA_SIZE,
	           offsetof(struct mStateExtdataHeader, size), &header[0]);
	STORE_64LE(SAVEDATA_OFFSET,
	           offsetof(struct mStateExtdataHeader, offset), &header[0]);
	STORE_32LE(EXTDATA_NONE,
	           offsetof(struct mStateExtdataHeader, tag), &header[1]);
	STORE_32LE(0, offsetof(struct mStateExtdataHeader, size), &header[1]);
	STORE_64LE(0, offsetof(struct mStateExtdataHeader, offset), &header[1]);
	memcpy(snapshot + SAVEDATA_OFFSET, test->expected, SAVEDATA_SIZE);
	if (kind == SNAPSHOT_SHORT_PAYLOAD) {
		return SNAPSHOT_SIZE - 1;
	}
	return SNAPSHOT_SIZE;
}

static struct VFile* makeStateVFile(const struct TestCore* test,
                                    enum SnapshotKind kind) {
	uint8_t snapshot[SNAPSHOT_SIZE];
	size_t size = makeSnapshot(snapshot, test, kind);
	return VFileMemChunk(snapshot, size);
}

static bool loadSnapshot(struct TestCore* test, enum SnapshotKind kind,
                         int flags, size_t expectedVFiles,
                         size_t expectedCloses) {
	struct VFile* state = makeStateVFile(test, kind);
	if (!state) {
		fail("failed to create host savestate VFile");
	}
	size_t before = allocationCount;
	restoreVFilesCreated = 0;
	restoreVFilesClosed = 0;
	captureRestoreVFile = true;
	bool result = mCoreLoadStateNamed(&test->core, state, flags);
	captureRestoreVFile = false;
	state->close(state);
	if (!result || restoreVFilesCreated != expectedVFiles ||
	    restoreVFilesClosed != expectedCloses) {
		fail("pinned savestate restore callback observation changed");
	}
	size_t expectedLive = 2 + (expectedCloses < expectedVFiles ? 2 : 0);
	if (allocationCount != expectedLive || allocationCount > before) {
		fail("pinned savestate restore cleanup observation changed");
	}
	return result;
}

static bool matches(const uint8_t* actual, const uint8_t* expected) {
	return memcmp(actual, expected, SAVEDATA_SIZE) == 0;
}

static void cleanupCore(struct TestCore* test) {
	GBASavedataDeinit(&test->gba.memory.savedata);
	test->realSave->close(test->realSave);
	if (allocationCount) {
		fail("pinned savestate restore left host allocations live");
	}
}

static void testAbsent(void) {
	struct TestCore test;
	initCore(&test);
	if (!loadSnapshot(&test, SNAPSHOT_ABSENT, SAVESTATE_SAVEDATA, 0, 0) ||
	    !matches(test.realSaveData, test.initial)) {
		fail("absent extdata unexpectedly restored GBA savedata");
	}
	puts("PHASE1_RESTORE_CASE absent caller_return=1 restore_vfiles=0 "
	     "close_after_load=0 save_unchanged=1 clean=1");
	cleanupCore(&test);
}

static void testShortHeader(void) {
	struct TestCore test;
	initCore(&test);
	if (!loadSnapshot(&test, SNAPSHOT_SHORT_HEADER, SAVESTATE_SAVEDATA, 0, 0) ||
	    !matches(test.realSaveData, test.initial)) {
		fail("short extdata header unexpectedly restored GBA savedata");
	}
	puts("PHASE1_RESTORE_CASE short_header caller_return=1 restore_vfiles=0 "
	     "close_after_load=0 save_unchanged=1 clean=1");
	cleanupCore(&test);
}

static void testShortPayload(void) {
	struct TestCore test;
	initCore(&test);
	if (!loadSnapshot(&test, SNAPSHOT_SHORT_PAYLOAD, SAVESTATE_SAVEDATA, 0, 0) ||
	    !matches(test.realSaveData, test.initial)) {
		fail("short extdata payload unexpectedly restored GBA savedata");
	}
	puts("PHASE1_RESTORE_CASE short_payload caller_return=1 restore_vfiles=0 "
	     "close_after_load=0 save_unchanged=1 clean=1");
	cleanupCore(&test);
}

static void testValidWriteback(void) {
	struct TestCore test;
	initCore(&test);
	if (!loadSnapshot(&test, SNAPSHOT_VALID, SAVESTATE_SAVEDATA, 1, 1) ||
	    !matches(test.realSaveData, test.expected)) {
		fail("valid writeback extdata did not restore GBA savedata");
	}
	puts("PHASE1_RESTORE_CASE valid_writeback caller_return=1 "
	     "restore_vfiles=1 close_after_load=1 save_match=1 clean=1");
	cleanupCore(&test);
}

static void testValidDeferredRestore(void) {
	struct TestCore test;
	initCore(&test);
	if (!loadSnapshot(&test, SNAPSHOT_VALID, 0, 1, 0)) {
		fail("valid deferred extdata load failed");
	}
	struct GBASavedata* savedata = &test.gba.memory.savedata;
	if (savedata->vf == savedata->realVf ||
	    !matches(test.realSaveData, test.initial) || allocationCount != 4) {
		fail("savedata VFile ownership was not deferred through mask");
	}
	GBASavedataUnmask(savedata);
	if (restoreVFilesClosed != 1 || savedata->vf != savedata->realVf ||
	    !matches(test.realSaveData, test.expected) || allocationCount != 2) {
		fail("deferred savedata VFile was not restored and closed on unmask");
	}
	puts("PHASE1_RESTORE_CASE valid_deferred caller_return=1 "
	     "restore_vfiles=1 close_after_load=0 mask_owned=1 "
	     "save_match_after_unmask=1 close_after_unmask=1 clean=1");
	cleanupCore(&test);
}

static void testRetryAfterMalformedPayload(void) {
	struct TestCore test;
	initCore(&test);
	if (!loadSnapshot(&test, SNAPSHOT_SHORT_PAYLOAD, SAVESTATE_SAVEDATA, 0, 0) ||
	    !matches(test.realSaveData, test.initial)) {
		fail("malformed first extdata attempt changed savedata");
	}
	if (!loadSnapshot(&test, SNAPSHOT_VALID, SAVESTATE_SAVEDATA, 1, 1) ||
	    !matches(test.realSaveData, test.expected)) {
		fail("valid retry after malformed extdata did not restore savedata");
	}
	puts("PHASE1_RESTORE_CASE retry_after_malformed malformed_return=1 "
	     "malformed_restore_vfiles=0 retry_return=1 retry_restore_vfiles=1 "
	     "save_match=1 clean=1");
	cleanupCore(&test);
}

int main(void) {
	if (sizeof(struct mStateExtdataHeader) != HEADER_SIZE) {
		fail("pinned extdata header layout changed");
	}
	testAbsent();
	testShortHeader();
	testShortPayload();
	testValidWriteback();
	testValidDeferredRestore();
	testRetryAfterMalformedPayload();
	puts("PHASE1_SAVESTATE_RESTORE_DONE");
	return 0;
}
