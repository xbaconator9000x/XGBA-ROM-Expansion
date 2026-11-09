#include <mgba/core/serialize.h>
#include <mgba-util/vfs.h>

#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#define SDL_VERSION_ATLEAST(major, minor, patch) 0

struct mCore {
	struct {
		unsigned audioBuffers;
	} opts;
	void (*unloadROM)(struct mCore*);
};

struct mLogger {
	int unused;
};

struct mCoreThread {
	struct mCore* core;
	struct {
		struct mLogger* logger;
	} logger;
};

struct mStandardLogger {
	struct mLogger d;
};

struct mArguments {
	const char* fname;
	const char* savestate;
};

struct mSDLAudio {
	unsigned samples;
	unsigned sampleRate;
};

struct mSDLRenderer {
	struct mCore* core;
	struct mSDLAudio audio;
	void (*runloop)(struct mSDLRenderer*, struct mCoreThread*);
};

static struct mStandardLogger _logger;
static struct VFile* _state;
static struct VFile stateVFile;
static bool stateOpenSucceeds;
static bool loadStateResult;
static unsigned loadCalls;
static unsigned threadRunCalls;
static unsigned closeCalls;
static unsigned runloopCalls;
static int observedFlags;
static struct VFile* observedState;

struct VFile* VFileOpen(const char* path, int mode);
bool mCoreLoadFile(struct mCore* core, const char* path);
bool mCoreAutoloadSave(struct mCore* core);
void mArgumentsApplyFileLoads(struct mArguments* args, struct mCore* core);
bool mCoreThreadStart(struct mCoreThread* thread);
void mCoreThreadRunFunction(struct mCoreThread* thread,
                            void (*run)(struct mCoreThread*));
bool mCoreThreadHasCrashed(struct mCoreThread* thread);
void mCoreThreadEnd(struct mCoreThread* thread);
void mCoreThreadJoin(struct mCoreThread* thread);
bool mSDLInitAudio(struct mSDLAudio* audio, struct mCoreThread* thread);
void mSDLPauseAudio(struct mSDLAudio* audio);

static bool closeState(struct VFile* vf) {
	if (vf != &stateVFile) {
		return false;
	}
	++closeCalls;
	return true;
}

struct VFile* VFileOpen(const char* path, int mode) {
	if (!path || mode != O_RDONLY || !stateOpenSucceeds) {
		return NULL;
	}
	memset(&stateVFile, 0, sizeof(stateVFile));
	stateVFile.close = closeState;
	return &stateVFile;
}

bool mCoreLoadStateNamed(struct mCore* core, struct VFile* vf, int flags) {
	(void) core;
	++loadCalls;
	observedFlags = flags;
	observedState = vf;
	return loadStateResult;
}

bool mCoreLoadFile(struct mCore* core, const char* path) {
	return core && path;
}

bool mCoreAutoloadSave(struct mCore* core) {
	return core != NULL;
}

void mArgumentsApplyFileLoads(struct mArguments* args, struct mCore* core) {
	(void) args;
	(void) core;
}

bool mCoreThreadStart(struct mCoreThread* thread) {
	return thread && thread->core;
}

void mCoreThreadRunFunction(struct mCoreThread* thread,
                            void (*run)(struct mCoreThread*)) {
	++threadRunCalls;
	run(thread);
}

bool mCoreThreadHasCrashed(struct mCoreThread* thread) {
	(void) thread;
	return false;
}

void mCoreThreadEnd(struct mCoreThread* thread) {
	(void) thread;
}

void mCoreThreadJoin(struct mCoreThread* thread) {
	(void) thread;
}

bool mSDLInitAudio(struct mSDLAudio* audio, struct mCoreThread* thread) {
	return audio && thread;
}

void mSDLPauseAudio(struct mSDLAudio* audio) {
	(void) audio;
}

static void unloadROM(struct mCore* core) {
	(void) core;
}

static void runloop(struct mSDLRenderer* renderer, struct mCoreThread* thread) {
	(void) renderer;
	(void) thread;
	++runloopCalls;
}

PHASE1_INSERT_PINNED_SDL_LOADSTATE
PHASE1_INSERT_PINNED_SDL_MSDLRUN

static void resetCase(bool openSucceeds, bool loaderResult) {
	_state = NULL;
	memset(&stateVFile, 0, sizeof(stateVFile));
	stateOpenSucceeds = openSucceeds;
	loadStateResult = loaderResult;
	loadCalls = 0;
	threadRunCalls = 0;
	closeCalls = 0;
	runloopCalls = 0;
	observedFlags = 0;
	observedState = NULL;
}

static int execute(bool openSucceeds, bool loaderResult,
                   unsigned expectedLoadCalls, unsigned expectedCloseCalls) {
	struct mCore core = {
		.opts = {.audioBuffers = 4},
		.unloadROM = unloadROM,
	};
	struct mSDLRenderer renderer = {
		.core = &core,
		.runloop = runloop,
	};
	struct mArguments args = {
		.fname = "fixture.rom",
		.savestate = "fixture.state",
	};
	resetCase(openSucceeds, loaderResult);
	const int result = mSDLRun(&renderer, &args);
	if (result != 0 || loadCalls != expectedLoadCalls ||
	    closeCalls != expectedCloseCalls || runloopCalls != 1 ||
	    threadRunCalls != expectedLoadCalls || _state != NULL) {
		return 1;
	}
	if (expectedLoadCalls &&
	    (observedState != &stateVFile || observedFlags != SAVESTATE_RTC)) {
		return 1;
	}
	return 0;
}

static int executeRetry(void) {
	struct mCore core = {
		.opts = {.audioBuffers = 4},
		.unloadROM = unloadROM,
	};
	struct mSDLRenderer renderer = {
		.core = &core,
		.runloop = runloop,
	};
	struct mArguments args = {
		.fname = "fixture.rom",
		.savestate = "fixture.state",
	};
	resetCase(true, false);
	if (mSDLRun(&renderer, &args) != 0 || loadCalls != 1 ||
	    closeCalls != 1 || runloopCalls != 1 || _state != NULL) {
		return 1;
	}
	loadStateResult = true;
	if (mSDLRun(&renderer, &args) != 0 || loadCalls != 2 ||
	    closeCalls != 2 || runloopCalls != 2 || threadRunCalls != 2 ||
	    _state != NULL) {
		return 1;
	}
	return 0;
}

int main(void) {
	if (execute(true, false, 1, 1)) {
		return 1;
	}
	puts("PHASE1_SDL_CASE loader_failure mcore=0 msdlrun=0 ignored=1 "
	     "state_closed=1 global_cleared=1 runloop=1");

	if (execute(true, true, 1, 1)) {
		return 1;
	}
	puts("PHASE1_SDL_CASE loader_success mcore=1 msdlrun=0 state_closed=1 "
	     "global_cleared=1 runloop=1");

	if (execute(false, false, 0, 0)) {
		return 1;
	}
	puts("PHASE1_SDL_CASE open_failure callback=0 close=0 runloop=1");

	if (executeRetry()) {
		return 1;
	}
	puts("PHASE1_SDL_CASE retry failed_close=1 success_close=1 "
	     "global_cleared=1");
	puts("PHASE1_SDL_RESTORE_DONE");
	return 0;
}
