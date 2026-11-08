#include <mgba/core/cheats.h>
#include <mgba/core/core.h>
#include <mgba/core/serialize.h>
#include <mgba/core/version.h>
#include <mgba-util/vfs.h>

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

struct TestVFile {
	struct VFile vf;
	uint8_t bytes[4096];
	size_t length;
	size_t position;
};

static const uint8_t expectedSave[] = { 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88 };
const char* const projectName = "mGBA witness";
const char* const projectVersion = "Phase 1";
static int cloneCalls;
static bool cloneFails;
static bool cloneHasNoSave;

struct VFile* VFileMemChunk(const void* memory, size_t size) {
	(void) memory;
	(void) size;
	return NULL;
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

static size_t core_savedata_clone(struct mCore* core, void** output) {
	(void) core;
	++cloneCalls;
	*output = NULL;
	if (cloneFails || cloneHasNoSave) {
		return 0;
	}
	*output = malloc(sizeof(expectedSave));
	if (!*output) {
		return 0;
	}
	memcpy(*output, expectedSave, sizeof(expectedSave));
	return sizeof(expectedSave);
}

PHASE1_INSERT_PINNED_SAVESTATE_CLONE_FUNCTIONS

static void reset_core(struct mCore* core, struct TestVFile* vf, bool fail) {
	memset(core, 0, sizeof(*core));
	init_vf(vf);
	core->stateSize = core_state_size;
	core->saveState = core_save_state;
	core->saveExtraState = core_save_extra_state;
	core->savedataClone = core_savedata_clone;
	cloneCalls = 0;
	cloneFails = fail;
	cloneHasNoSave = false;
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
	bool valid = item.data && item.size == sizeof(expectedSave) &&
	             memcmp(item.data, expectedSave, sizeof(expectedSave)) == 0;
	mStateExtdataDeinit(&extdata);
	return valid;
}

static void test_normal_clone(void) {
	struct mCore core;
	struct TestVFile vf;
	reset_core(&core, &vf, false);
	bool result = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!result || cloneCalls != 1 || vf.length <= 8 ||
	    !verify_savedata(&vf)) {
		fprintf(stderr, "normal savedata clone control failed\n");
		exit(1);
	}
	printf("PHASE1_CLONE_CASE normal caller_return=1 clone_result=8 "
	       "clone_calls=1 state_bytes=8 savedata_present=1 payload_match=1\n");
}

static void test_zero_result_failure(void) {
	struct mCore core;
	struct TestVFile vf;
	reset_core(&core, &vf, true);
	bool result = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!result || cloneCalls != 1 || vf.length != 8) {
		fprintf(stderr, "zero-result caller behavior changed\n");
		exit(1);
	}
	printf("PHASE1_CLONE_CASE zero_result_failure caller_return=1 "
	       "clone_result=0 clone_calls=1 state_bytes=8 savedata_present=0\n");
}

static void test_zero_result_no_save(void) {
	struct mCore core;
	struct TestVFile vf;
	reset_core(&core, &vf, false);
	cloneHasNoSave = true;
	bool result = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!result || cloneCalls != 1 || vf.length != 8) {
		fprintf(stderr, "zero-result no-save control changed\n");
		exit(1);
	}
	printf("PHASE1_CLONE_CASE zero_result_no_save caller_return=1 "
	       "clone_result=0 clone_calls=1 state_bytes=8 savedata_present=0\n");
}

static void test_no_savedata_flag(void) {
	struct mCore core;
	struct TestVFile vf;
	reset_core(&core, &vf, true);
	bool result = mCoreSaveStateNamed(&core, &vf.vf, 0);
	if (!result || cloneCalls || vf.length != 8) {
		fprintf(stderr, "savedata flag-off control changed\n");
		exit(1);
	}
	printf("PHASE1_CLONE_CASE no_savedata_flag caller_return=1 "
	       "clone_calls=0 state_bytes=8 savedata_present=0\n");
}

static void test_retry_after_zero(void) {
	struct mCore core;
	struct TestVFile vf;
	reset_core(&core, &vf, true);
	bool failed = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!failed || cloneCalls != 1 || vf.length != 8) {
		fprintf(stderr, "initial zero-result observation changed\n");
		exit(1);
	}
	reset_core(&core, &vf, false);
	bool retried = mCoreSaveStateNamed(&core, &vf.vf, SAVESTATE_SAVEDATA);
	if (!retried || cloneCalls != 1 || vf.length <= 8 ||
	    !verify_savedata(&vf)) {
		fprintf(stderr, "savedata clone retry control failed\n");
		exit(1);
	}
	printf("PHASE1_CLONE_CASE retry_after_zero caller_return=1 "
	       "clone_result=8 clone_calls=1 state_bytes=8 savedata_present=1 "
	       "payload_match=1\n");
}

int main(void) {
	test_normal_clone();
	test_zero_result_no_save();
	test_zero_result_failure();
	test_no_savedata_flag();
	test_retry_after_zero();
	puts("PHASE1_SAVESTATE_CLONE_DONE");
	return 0;
}
