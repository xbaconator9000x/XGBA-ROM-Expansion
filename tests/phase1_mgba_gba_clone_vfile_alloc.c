#include <mgba/core/cheats.h>
#include <mgba/core/core.h>
#include <mgba/core/serialize.h>
#include <mgba/core/version.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/savedata.h>
#include <mgba-util/vfs.h>
#include <mgba-util/memory.h>

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct TestVFile {
	struct VFile vf;
	uint8_t bytes[GBA_SIZE_SRAM + 4096];
	size_t length;
	size_t position;
};

static uint8_t sourceSavedata[GBA_SIZE_SRAM];
static unsigned wrapperAllocAttempts;
static unsigned wrapperAllocFailures;
static unsigned wrapperFrees;
static unsigned cloneBufferFrees;
static bool injectWrapperFailure;
static bool failNextWrapperAllocation;
static void* cloneBuffer;
static void* memoryVFileWrapper;
const char* const projectName = "mGBA witness";
const char* const projectVersion = "Phase 1";

static size_t vfile_memory_wrapper_size(void) {
	return sizeof(struct VFile) + sizeof(void*) + 3 * sizeof(size_t);
}

void* __real_malloc(size_t size);
void __real_free(void* memory);

void* __wrap_malloc(size_t size) {
	if (size == GBA_SIZE_SRAM && !cloneBuffer) {
		void* memory = __real_malloc(size);
		if (memory) {
			cloneBuffer = memory;
			failNextWrapperAllocation = injectWrapperFailure;
		}
		return memory;
	}
	if (size == vfile_memory_wrapper_size()) {
		++wrapperAllocAttempts;
		if (failNextWrapperAllocation) {
			failNextWrapperAllocation = false;
			++wrapperAllocFailures;
			return NULL;
		}
		memoryVFileWrapper = __real_malloc(size);
		return memoryVFileWrapper;
	}
	return __real_malloc(size);
}

void __wrap_free(void* memory) {
	if (memory && memory == cloneBuffer) {
		++cloneBufferFrees;
		cloneBuffer = NULL;
	}
	if (memory && memory == memoryVFileWrapper) {
		++wrapperFrees;
		memoryVFileWrapper = NULL;
	}
	__real_free(memory);
}

void* anonymousMemoryMap(size_t size) {
	return __real_malloc(size);
}

void mappedMemoryFree(void* memory, size_t size) {
	(void) size;
	__real_free(memory);
}

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	(void) vf;
	(void) buffer;
	(void) size;
	return -1;
}

bool mCheatSaveFile(struct mCheatDevice* device, struct VFile* vf) {
	(void) device;
	(void) vf;
	return false;
}

static bool test_vf_close(struct VFile* vf) {
	(void) vf;
	return true;
}

static off_t test_vf_seek(struct VFile* vf, off_t offset, int whence) {
	struct TestVFile* test = (struct TestVFile*) vf;
	off_t base = 0;
	if (whence == SEEK_CUR) {
		base = (off_t) test->position;
	} else if (whence == SEEK_END) {
		base = (off_t) test->length;
	} else if (whence != SEEK_SET) {
		errno = EINVAL;
		return -1;
	}
	if (offset < -base || (uint64_t) (base + offset) > sizeof(test->bytes)) {
		errno = EINVAL;
		return -1;
	}
	test->position = (size_t) (base + offset);
	return (off_t) test->position;
}

static ssize_t test_vf_read(struct VFile* vf, void* buffer, size_t size) {
	struct TestVFile* test = (struct TestVFile*) vf;
	size_t available = test->length - test->position;
	if (size > available) {
		size = available;
	}
	memcpy(buffer, test->bytes + test->position, size);
	test->position += size;
	return (ssize_t) size;
}

static ssize_t test_vf_write(struct VFile* vf, const void* buffer, size_t size) {
	struct TestVFile* test = (struct TestVFile*) vf;
	if (size > sizeof(test->bytes) - test->position) {
		errno = ENOSPC;
		return -1;
	}
	memcpy(test->bytes + test->position, buffer, size);
	test->position += size;
	if (test->position > test->length) {
		test->length = test->position;
	}
	return (ssize_t) size;
}

static void* test_vf_map(struct VFile* vf, size_t size, int flags) {
	struct TestVFile* test = (struct TestVFile*) vf;
	(void) flags;
	if (size > sizeof(test->bytes)) {
		return NULL;
	}
	if (size > test->length) {
		test->length = size;
	}
	return test->bytes;
}

static void test_vf_unmap(struct VFile* vf, void* memory, size_t size) {
	(void) vf;
	(void) memory;
	(void) size;
}

static void test_vf_truncate(struct VFile* vf, size_t size) {
	struct TestVFile* test = (struct TestVFile*) vf;
	if (size <= sizeof(test->bytes)) {
		test->length = size;
		if (test->position > size) {
			test->position = size;
		}
	}
}

static ssize_t test_vf_size(struct VFile* vf) {
	return (ssize_t) ((struct TestVFile*) vf)->length;
}

static bool test_vf_sync(struct VFile* vf, void* memory, size_t size) {
	(void) vf;
	(void) memory;
	(void) size;
	return true;
}

static void init_vf(struct TestVFile* test) {
	memset(test, 0, sizeof(*test));
	test->vf.close = test_vf_close;
	test->vf.seek = test_vf_seek;
	test->vf.read = test_vf_read;
	test->vf.write = test_vf_write;
	test->vf.map = test_vf_map;
	test->vf.unmap = test_vf_unmap;
	test->vf.truncate = test_vf_truncate;
	test->vf.size = test_vf_size;
	test->vf.sync = test_vf_sync;
}

static size_t core_state_size(struct mCore* core) {
	(void) core;
	return 8;
}

static bool core_save_state(struct mCore* core, void* state) {
	(void) core;
	memcpy(state, "STATE123", 8);
	return true;
}

static bool core_save_extra_state(struct mCore* core,
                                  struct mStateExtdata* extdata) {
	(void) core;
	(void) extdata;
	return true;
}

PHASE1_INSERT_PINNED_GBA_CLONE_FUNCTIONS

static void reset_case(struct mCore* core, struct GBA* gba,
                       struct TestVFile* vf, bool fail_wrapper) {
	memset(core, 0, sizeof(*core));
	memset(gba, 0, sizeof(*gba));
	init_vf(vf);
	core->stateSize = core_state_size;
	core->saveState = core_save_state;
	core->saveExtraState = core_save_extra_state;
	core->savedataClone = _GBACoreSavedataClone;
	core->board = gba;
	gba->memory.savedata.type = GBA_SAVEDATA_SRAM;
	gba->memory.savedata.data = sourceSavedata;
	cloneBuffer = NULL;
	memoryVFileWrapper = NULL;
	wrapperAllocAttempts = 0;
	wrapperAllocFailures = 0;
	wrapperFrees = 0;
	cloneBufferFrees = 0;
	injectWrapperFailure = fail_wrapper;
	failNextWrapperAllocation = false;
}

static bool verify_savedata(struct TestVFile* vf) {
	struct mStateExtdata extdata;
	struct mStateExtdataItem item;
	mStateExtdataInit(&extdata);
	if (vf->length == 8) {
		mStateExtdataDeinit(&extdata);
		return false;
	}
	if (vf->vf.seek(&vf->vf, 8, SEEK_SET) < 0 ||
	    !mStateExtdataDeserialize(&extdata, &vf->vf) ||
	    !mStateExtdataGet(&extdata, EXTDATA_SAVEDATA, &item)) {
		mStateExtdataDeinit(&extdata);
		return false;
	}
	bool valid = item.data && item.size == sizeof(sourceSavedata) &&
	             memcmp(item.data, sourceSavedata, sizeof(sourceSavedata)) == 0;
	mStateExtdataDeinit(&extdata);
	return valid;
}

static void test_successful_clone(void) {
	struct mCore core;
	struct GBA gba;
	struct TestVFile vf;
	reset_case(&core, &gba, &vf, false);
	bool result = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!result || wrapperAllocAttempts != 1 || wrapperAllocFailures != 0 ||
	    wrapperFrees != 1 || cloneBufferFrees != 1 || vf.length <= 8 ||
	    !verify_savedata(&vf)) {
		fprintf(stderr, "successful original GBA clone control failed\n");
		exit(1);
	}
	printf("PHASE1_GBA_CLONE_CASE success caller_return=1 "
	       "callback_clone_result=32768 "
	       "wrapper_alloc_attempts=1 wrapper_alloc_failures=0 wrapper_frees=1 "
	       "clone_buffer_frees=1 savedata_present=1 payload_match=1\n");
}

static void test_wrapper_allocation_failure(void) {
	struct mCore core;
	struct GBA gba;
	struct TestVFile vf;
	reset_case(&core, &gba, &vf, true);
	bool result = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!result || wrapperAllocAttempts != 1 || wrapperAllocFailures != 1 ||
	    wrapperFrees != 0 || cloneBufferFrees != 1 || vf.length != 8) {
		fprintf(stderr, "original GBA clone wrapper-allocation cleanup changed\n");
		exit(1);
	}
	printf("PHASE1_GBA_CLONE_CASE wrapper_allocation_failure caller_return=1 "
	       "callback_clone_result=0 "
	       "wrapper_alloc_attempts=1 wrapper_alloc_failures=1 wrapper_frees=0 "
	       "clone_buffer_frees=1 savedata_present=0\n");
}

static void test_retry_after_wrapper_failure(void) {
	struct mCore core;
	struct GBA gba;
	struct TestVFile vf;
	reset_case(&core, &gba, &vf, true);
	bool failed = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!failed || wrapperAllocFailures != 1 || cloneBufferFrees != 1) {
		fprintf(stderr, "initial wrapper failure control changed\n");
		exit(1);
	}
	reset_case(&core, &gba, &vf, false);
	bool retried = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!retried || wrapperAllocAttempts != 1 || wrapperAllocFailures != 0 ||
	    wrapperFrees != 1 || cloneBufferFrees != 1 || vf.length <= 8 ||
	    !verify_savedata(&vf)) {
		fprintf(stderr, "retry after original GBA clone failure failed\n");
		exit(1);
	}
	printf("PHASE1_GBA_CLONE_CASE retry_after_wrapper_failure caller_return=1 "
	       "callback_clone_result=32768 "
	       "wrapper_alloc_attempts=1 wrapper_alloc_failures=0 wrapper_frees=1 "
	       "clone_buffer_frees=1 savedata_present=1 payload_match=1\n");
}

int main(void) {
	for (size_t i = 0; i < sizeof(sourceSavedata); ++i) {
		sourceSavedata[i] = (uint8_t) (i * 17U + 3U);
	}
	test_successful_clone();
	test_wrapper_allocation_failure();
	test_retry_after_wrapper_failure();
	puts("PHASE1_GBA_CLONE_DONE");
	return 0;
}
