#include <mgba-util/vfs.h>

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

struct ExpectedVFileFDLayout {
	struct VFile d;
	int fd;
};

struct mDirectorySet {
	char baseName[PATH_MAX + 1];
	struct VDir* save;
};

struct mCoreConfig {
	int unused;
};

struct mCore {
	struct mDirectorySet dirs;
	struct mCoreConfig config;
	bool (*loadSave)(struct mCore*, struct VFile*);
};

static const char* targetPath;
static int targetOpenAttempts;
static int targetFds[4];
static int targetFdCount;
static int allocationAttempts;
static int allocationFailures;
static int failAllocationAt;
static int targetCloseCalls;
static int saveCallbackCalls;
static int nullSaveCallbackCalls;

bool mCoreConfigGetIntValue(const struct mCoreConfig*, const char*, int*);

int __real_open(const char* path, int flags, ...);
int __real_close(int fd);
void* __real_malloc(size_t size);

int __wrap_open(const char* path, int flags, ...) {
	int fd;
	if (flags & O_CREAT) {
		va_list args;
		va_start(args, flags);
		mode_t mode = (mode_t) va_arg(args, int);
		va_end(args);
		fd = __real_open(path, flags, mode);
	} else {
		fd = __real_open(path, flags);
	}
	if (targetPath && !strcmp(path, targetPath)) {
		++targetOpenAttempts;
		if (fd >= 0 && targetFdCount < 4) {
			targetFds[targetFdCount++] = fd;
		}
	}
	return fd;
}

void* __wrap_malloc(size_t size) {
	if (size == sizeof(struct ExpectedVFileFDLayout) &&
	    allocationAttempts < targetFdCount) {
		++allocationAttempts;
		if (failAllocationAt == allocationAttempts) {
			++allocationFailures;
			errno = ENOMEM;
			return NULL;
		}
	}
	return __real_malloc(size);
}

int __wrap_close(int fd) {
	for (int i = 0; i < targetFdCount; ++i) {
		if (fd == targetFds[i]) {
			++targetCloseCalls;
			break;
		}
	}
	return __real_close(fd);
}

static void reset_case(const char* path, int failAt) {
	targetPath = path;
	targetOpenAttempts = 0;
	memset(targetFds, 0xFF, sizeof(targetFds));
	targetFdCount = 0;
	allocationAttempts = 0;
	allocationFailures = 0;
	failAllocationAt = failAt;
	targetCloseCalls = 0;
	saveCallbackCalls = 0;
	nullSaveCallbackCalls = 0;
}

static int descriptor_is_open(int fd) {
	errno = 0;
	return fcntl(fd, F_GETFD) >= 0 || errno != EBADF;
}

static bool load_save_fixture(struct mCore* core, struct VFile* vf) {
	(void) core;
	++saveCallbackCalls;
	if (!vf) {
		++nullSaveCallbackCalls;
		return false;
	}
	return vf->close(vf);
}

bool mCoreConfigGetIntValue(const struct mCoreConfig* config,
                            const char* key, int* value) {
	(void) config;
	(void) key;
	(void) value;
	return false;
}

PHASE1_INSERT_PINNED_MDIRECTORYSET_OPEN_SUFFIX

PHASE1_INSERT_PINNED_MCORE_AUTOLOAD_SAVE

static void test_successful_autoload(struct mCore* core, const char* path) {
	reset_case(path, 0);
	bool result = mCoreAutoloadSave(core);
	int descriptorOpen = targetFdCount == 1 &&
	                     descriptor_is_open(targetFds[0]);
	if (!result || targetOpenAttempts != 1 || targetFdCount != 1 ||
	    allocationAttempts != 1 || allocationFailures ||
	    saveCallbackCalls != 1 || nullSaveCallbackCalls ||
	    targetCloseCalls != 1 || descriptorOpen) {
		fprintf(stderr, "successful autoload control changed\n");
		exit(1);
	}
	printf("PHASE1_AUTOLOAD_CASE success return=1 target_opens=1 "
	       "allocation_attempts=1 allocation_failures=0 "
	       "save_callbacks=1 null_callbacks=0 close_calls=1 "
	       "target_fd_open=0\n");
}

static int test_failed_autoload_and_retry(struct mCore* core,
                                          const char* path) {
	reset_case(path, 1);
	bool failed = mCoreAutoloadSave(core);
	int leakedFd = targetFdCount ? targetFds[0] : -1;
	int leakedAfterFailure = leakedFd >= 0 && descriptor_is_open(leakedFd);
	if (failed || targetOpenAttempts != 1 || targetFdCount != 1 ||
	    allocationAttempts != 1 || allocationFailures != 1 ||
	    saveCallbackCalls != 1 || nullSaveCallbackCalls != 1 ||
	    targetCloseCalls || !leakedAfterFailure) {
		fprintf(stderr, "autoload did not hand NULL to the save callback\n");
		exit(1);
	}

	failAllocationAt = 0;
	bool recovered = mCoreAutoloadSave(core);
	int leakedAfterRetry = descriptor_is_open(leakedFd);
	int retryFdClosed = targetFdCount == 2 &&
	                    !descriptor_is_open(targetFds[1]);
	if (!recovered || targetOpenAttempts != 2 || targetFdCount != 2 ||
	    allocationAttempts != 2 || allocationFailures != 1 ||
	    saveCallbackCalls != 2 || nullSaveCallbackCalls != 1 ||
	    targetCloseCalls != 1 || !leakedAfterRetry || !retryFdClosed) {
		fprintf(stderr, "autoload retry or descriptor ownership changed\n");
		exit(1);
	}
	printf("PHASE1_AUTOLOAD_CASE allocation_failure return=0 "
	       "target_opens=1 allocation_attempts=1 allocation_failures=1 "
	       "save_callbacks=1 null_callbacks=1 close_calls=0 "
	       "leaked_fd_open=1\n");
	printf("PHASE1_AUTOLOAD_CASE retry failure_return=0 retry_return=1 "
	       "target_opens=2 allocation_attempts=2 allocation_failures=1 "
	       "save_callbacks=2 null_callbacks=1 close_calls=1 "
	       "leaked_first_fd_open=1 retry_fd_closed=1\n");
	return leakedFd;
}

static void test_missing_save_directory(struct mCore* core, const char* path) {
	struct mCore withoutSaveDirectory = *core;
	withoutSaveDirectory.dirs.save = NULL;
	reset_case(path, 0);
	bool result = mCoreAutoloadSave(&withoutSaveDirectory);
	if (result || targetOpenAttempts || targetFdCount || allocationAttempts ||
	    allocationFailures || saveCallbackCalls || nullSaveCallbackCalls ||
	    targetCloseCalls) {
		fprintf(stderr, "missing-save-directory negative control changed\n");
		exit(1);
	}
	printf("PHASE1_AUTOLOAD_CASE missing_save_directory return=0 "
	       "target_opens=0 allocation_attempts=0 save_callbacks=0\n");
}

int main(void) {
	char directory[] = "/tmp/mgba-core-autoload-save-XXXXXX";
	if (!mkdtemp(directory)) {
		perror("mkdtemp");
		return 1;
	}
	char path[sizeof(directory) + sizeof("/game.sav")];
	snprintf(path, sizeof(path), "%s/game.sav", directory);
	struct mCore core = {
		.dirs = { .save = VDirOpen(directory) },
		.loadSave = load_save_fixture,
	};
	if (!core.dirs.save) {
		perror("VDirOpen");
		return 1;
	}
	snprintf(core.dirs.baseName, sizeof(core.dirs.baseName), "game");

	test_successful_autoload(&core, path);
	int leakedFd = test_failed_autoload_and_retry(&core, path);
	test_missing_save_directory(&core, path);

	if (__real_close(leakedFd) < 0 || unlink(path) < 0 ||
	    !core.dirs.save->close(core.dirs.save) || rmdir(directory) < 0) {
		perror("cleanup autoload witness fixtures");
		return 1;
	}
	printf("PHASE1_AUTOLOAD_DONE\n");
	return 0;
}
