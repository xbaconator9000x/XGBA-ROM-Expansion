struct mCore* core;
bool deferredSetup;

static void _doDeferredSetup(void) {
}

static size_t inputVFilesCreated;
static size_t inputVFilesClosed;
static bool (*inputVFileClose)(struct VFile*);

extern struct VFile* __real_VFileFromConstMemory(const void*, size_t);

static bool observedInputVFileClose(struct VFile* vf) {
	++inputVFilesClosed;
	vf->close = inputVFileClose;
	return inputVFileClose(vf);
}

struct VFile* __wrap_VFileFromConstMemory(const void* memory, size_t size) {
	struct VFile* vf = __real_VFileFromConstMemory(memory, size);
	if (vf) {
		++inputVFilesCreated;
		inputVFileClose = vf->close;
		vf->close = observedInputVFileClose;
	}
	return vf;
}

PHASE1_INSERT_PINNED_LIBRETRO_UNSERIALIZE

static bool loadThroughLibretro(struct TestCore* test, const uint8_t* bytes,
                                size_t size, bool expectedResult,
                                size_t expectedRestoreVFiles) {
	core = &test->core;
	inputVFilesCreated = 0;
	inputVFilesClosed = 0;
	restoreVFilesCreated = 0;
	restoreVFilesClosed = 0;
	captureRestoreVFile = true;
	bool result = retro_unserialize(bytes, size);
	captureRestoreVFile = false;
	if (result != expectedResult || inputVFilesCreated != 1 ||
	    inputVFilesClosed != 1 ||
	    restoreVFilesCreated != expectedRestoreVFiles) {
		fail("pinned libretro state caller result or input ownership changed");
	}
	return result;
}

static void testLibretroAbsentExtdata(void) {
	struct TestCore test;
	uint8_t snapshot[SNAPSHOT_SIZE];
	initCore(&test);
	size_t size = makeSnapshot(snapshot, &test, SNAPSHOT_ABSENT);
	loadThroughLibretro(&test, snapshot, size, true, 0);
	if (!matches(test.realSaveData, test.initial)) {
		fail("absent extdata unexpectedly restored GBA savedata");
	}
	puts("PHASE1_CALLER_CASE absent result=1 input_vfiles=1 input_closed=1 "
	     "restore_vfiles=0 save_unchanged=1 clean=1");
	cleanupCore(&test);
}

static void testLibretroMalformedExtdata(void) {
	struct TestCore test;
	uint8_t snapshot[SNAPSHOT_SIZE];
	initCore(&test);
	size_t size = makeSnapshot(snapshot, &test, SNAPSHOT_SHORT_HEADER);
	loadThroughLibretro(&test, snapshot, size, true, 0);
	if (!matches(test.realSaveData, test.initial)) {
		fail("malformed extdata unexpectedly restored GBA savedata");
	}
	size = makeSnapshot(snapshot, &test, SNAPSHOT_SHORT_PAYLOAD);
	loadThroughLibretro(&test, snapshot, size, true, 0);
	if (!matches(test.realSaveData, test.initial)) {
		fail("short extdata payload unexpectedly restored GBA savedata");
	}
	puts("PHASE1_CALLER_CASE malformed result=1 input_closed=1 "
	     "restore_vfiles=0 save_unchanged=1 clean=1");
	cleanupCore(&test);
}

static void testLibretroBaseStateFailure(void) {
	struct TestCore test;
	uint8_t snapshot[SNAPSHOT_SIZE];
	initCore(&test);
	memcpy(snapshot, "STATE123", STATE_SIZE);
	loadThroughLibretro(&test, snapshot, STATE_SIZE - 1, false, 0);
	if (!matches(test.realSaveData, test.initial)) {
		fail("failed core-state extraction unexpectedly changed savedata");
	}
	puts("PHASE1_CALLER_CASE short_state result=0 input_closed=1 "
	     "restore_vfiles=0 save_unchanged=1 clean=1");
	cleanupCore(&test);
}

static void testLibretroValidRestoreAndRetry(void) {
	struct TestCore test;
	uint8_t snapshot[SNAPSHOT_SIZE];
	initCore(&test);
	size_t size = makeSnapshot(snapshot, &test, SNAPSHOT_SHORT_PAYLOAD);
	loadThroughLibretro(&test, snapshot, size, true, 0);
	if (!matches(test.realSaveData, test.initial)) {
		fail("malformed first extdata attempt changed savedata");
	}
	size = makeSnapshot(snapshot, &test, SNAPSHOT_VALID);
	loadThroughLibretro(&test, snapshot, size, true, 1);
	struct GBASavedata* savedata = &test.gba.memory.savedata;
	if (savedata->vf == savedata->realVf ||
	    !matches(test.realSaveData, test.initial) ||
	    restoreVFilesClosed != 0) {
		fail("libretro restore did not transfer VFile ownership to mask");
	}
	GBASavedataUnmask(savedata);
	if (restoreVFilesClosed != 1 || savedata->vf != savedata->realVf ||
	    !matches(test.realSaveData, test.expected)) {
		fail("libretro restore retry did not close and apply deferred savedata");
	}
	puts("PHASE1_CALLER_CASE valid_retry result=1 input_closed=1 "
	     "restore_vfiles=1 restore_closed_after_unmask=1 save_match=1 clean=1");
	cleanupCore(&test);
}

int main(void) {
	if (sizeof(struct mStateExtdataHeader) != HEADER_SIZE) {
		fail("pinned extdata header layout changed");
	}
	deferredSetup = false;
	testLibretroAbsentExtdata();
	testLibretroMalformedExtdata();
	testLibretroBaseStateFailure();
	testLibretroValidRestoreAndRetry();
	puts("PHASE1_SAVESTATE_CALLER_INTEGRATION_DONE");
	return 0;
}
