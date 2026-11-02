#include <mgba-util/vfs.h>
#include <mgba/internal/defines.h>

#include <errno.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#define mLOG(...)

typedef uint32_t mColor;

enum {
	CPU_COMPONENT_CHEAT_DEVICE = 0,
	HW_GB_PLAYER = 1,
	HW_GB_PLAYER_DETECTION = 2,
	VIDEO_TOTAL_LENGTH = 1
};

struct mCoreCallbacks {
	void* context;
	void (*videoFrameEnded)(void* context);
	void (*savedataUpdated)(void* context);
};

struct mScriptContext {
	unsigned savedataUpdatedEvents;
};

void mScriptContextTriggerCallback(struct mScriptContext* context,
                                   const char* name, void* value) {
	(void) value;
	if (context && !strcmp(name, "savedataUpdated")) {
		++context->savedataUpdatedEvents;
	}
}

PHASE1_INSERT_SCRIPT_CALLBACK_MACROS

static struct mCoreCallbacks mScriptCallbacksFor(
    struct mScriptContext* context) {
	return (struct mCoreCallbacks) {
		PHASE1_INSERT_SCRIPT_CALLBACK_REGISTRATION
	};
}

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

static size_t GBASavedataSize(const struct GBASavedata* savedata) {
	return savedata->size;
}

static void GBASavedataUnmask(struct GBASavedata* savedata) {
	(void) savedata;
}

static void GBASavedataRTCWrite(struct GBASavedata* savedata) {
	++savedata->rtcWrites;
}

PHASE1_INSERT_PINNED_GBASAVEDATACLEAN

struct mCoreCallbacksList {
	struct mCoreCallbacks* callbacks;
	size_t size;
};

size_t mCoreCallbacksListSize(const struct mCoreCallbacksList* list) {
	return list->size;
}

struct mCoreCallbacks* mCoreCallbacksListGetPointer(
    struct mCoreCallbacksList* list, size_t index) {
	return &list->callbacks[index];
}

struct mCheat {
	int unused;
};

struct GBACheatSet {
	bool hook;
	struct mCheat d;
};

struct mCheatSetList {
	struct GBACheatSet** entries;
	size_t size;
};

struct mCheatDevice {
	struct mCheatSetList cheats;
};

size_t mCheatSetsSize(const struct mCheatSetList* list) {
	return list->size;
}

struct GBACheatSet** mCheatSetsGetPointer(
    struct mCheatSetList* list, size_t index) {
	return &list->entries[index];
}

void mCheatRefresh(struct mCheatDevice* device, struct mCheat* cheat) {
	(void) device;
	(void) cheat;
}

struct ARMCore {
	void** components;
};

struct mAVStream {
	void (*postVideoFrame)(struct mAVStream*, const mColor*, size_t);
};

struct mRenderer {
	void (*getPixels)(struct mRenderer*, size_t*, const void**);
};

struct mTiming {
	uint32_t currentTime;
};

struct mRumble {
	void (*integrate)(struct mRumble*, uint32_t);
};

struct GBA {
	struct {
		struct GBASavedata savedata;
		struct {
			unsigned devices;
		} hw;
	} memory;
	struct {
		uint32_t frameCounter;
		struct mRenderer* renderer;
	} video;
	struct ARMCore* cpu;
	struct mAVStream* stream;
	struct mRumble* rumble;
	uint32_t lastRumble;
	struct mTiming timing;
	struct mCoreCallbacksList coreCallbacks;
};

uint32_t mTimingCurrentTime(struct mTiming* timing) {
	return timing->currentTime;
}

void GBASIOPlayerUpdate(struct GBA* gba) {
	(void) gba;
}

PHASE1_INSERT_PINNED_GBAFRAMEENDED

static unsigned asyncCalls;
static bool failAsyncMsync;

int __real_msync(void* memory, size_t size, int flags);
int __wrap_msync(void* memory, size_t size, int flags) {
	if (flags == MS_ASYNC) {
		++asyncCalls;
		if (failAsyncMsync) {
			errno = EIO;
			return -1;
		}
	}
	return __real_msync(memory, size, flags);
}

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	(void) vf;
	(void) buffer;
	(void) size;
	return -1;
}

static void fail(const char* message) {
	perror(message);
	_exit(90);
}

int main(void) {
	char directory[] = "/tmp/mgba-gba-callback-witness-XXXXXX";
	if (!mkdtemp(directory)) {
		fail("mkdtemp");
	}
	char path[PATH_MAX];
	snprintf(path, sizeof(path), "%s/failure.sav", directory);
	int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0600);
	if (fd < 0 || ftruncate(fd, 4096) < 0) {
		fail("create temporary file");
	}
	struct VFile* vf = VFileFromFD(fd);
	if (!vf) {
		fail("VFileFromFD");
	}
	uint8_t* data = vf->map(vf, 4096, MAP_WRITE);
	if (!data) {
		fail("map savedata");
	}
	data[0] = 0xA7;

	struct mScriptContext scriptContext = {0};
	struct mCoreCallbacks callback = mScriptCallbacksFor(&scriptContext);
	struct mCoreCallbacks callbacks[] = {callback};
	struct ARMCore cpu = {0};
	struct GBA gba = {
		.memory = {
			.savedata = {
				.vf = vf,
				.dirty = mSAVEDATA_DIRT_SEEN,
				.dirtAge = 100,
				.mapMode = MAP_WRITE,
				.data = data,
				.size = 4096,
			},
		},
		.video = {.frameCounter = 116},
		.cpu = &cpu,
		.coreCallbacks = {.callbacks = callbacks, .size = 1},
	};

	failAsyncMsync = true;
	GBAFrameEnded(&gba);
	if (asyncCalls != 1 || gba.memory.savedata.dirty != 0 ||
	    gba.memory.savedata.rtcWrites != 0 ||
	    scriptContext.savedataUpdatedEvents != 1) {
		fprintf(stderr, "failed sync callback semantics changed\n");
		return 1;
	}

	failAsyncMsync = false;
	gba.video.frameCounter = 117;
	GBAFrameEnded(&gba);
	unsigned retryCalls = asyncCalls - 1;
	unsigned retryEvents = scriptContext.savedataUpdatedEvents;
	unsigned retryRtcWrites = gba.memory.savedata.rtcWrites;
	if (retryCalls || retryEvents != 1 || retryRtcWrites) {
		fprintf(stderr, "clean frame retried failed sync or callback\n");
		return 1;
	}

	data[0] = 0xB8;
	gba.memory.savedata.dirty = mSAVEDATA_DIRT_NEW;
	gba.video.frameCounter = 130;
	GBAFrameEnded(&gba);
	if (asyncCalls != 1 || scriptContext.savedataUpdatedEvents != 1 ||
	    gba.memory.savedata.dirty == 0) {
		fprintf(stderr, "new dirty write did not restart cleanup timing\n");
		return 1;
	}
	gba.video.frameCounter = 146;
	GBAFrameEnded(&gba);
	if (asyncCalls != 2 || scriptContext.savedataUpdatedEvents != 2 ||
	    gba.memory.savedata.dirty != 0 || gba.memory.savedata.rtcWrites != 1) {
		fprintf(stderr, "successful sync control changed callback behavior\n");
		return 1;
	}

	vf->unmap(vf, data, 4096);
	if (!vf->close(vf) || unlink(path) < 0 || rmdir(directory) < 0) {
		fprintf(stderr, "temporary VFile cleanup failed\n");
		return 1;
	}
	printf("PHASE1_GBA_CALLBACK_CASE failure_async_ms=1 failure_rtc=0 "
	       "failure_dirty=0 failure_script_events=1 retry_async_ms=0 "
	       "retry_script_events=1 retry_rtc=0 new_write_success_async_ms=2 "
	       "success_rtc=1 success_script_events=2\n");
	puts("PHASE1_GBA_CALLBACK_DONE");
	return 0;
}
