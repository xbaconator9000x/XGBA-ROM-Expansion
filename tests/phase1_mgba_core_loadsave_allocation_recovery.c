#include <mgba-util/vfs.h>

#include <errno.h>
#include <fcntl.h>
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

struct mCore {
	bool (*loadSave)(struct mCore*, struct VFile*);
	bool (*loadTemporarySave)(struct mCore*, struct VFile*);
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
}

static int descriptor_is_open(int fd) {
	errno = 0;
	return fcntl(fd, F_GETFD) >= 0 || errno != EBADF;
}

static bool close_save_file(struct mCore* core, struct VFile* vf) {
	(void) core;
	++saveCallbackCalls;
	return vf->close(vf);
}

PHASE1_INSERT_PINNED_MCORE_LOADSAVEFILE

static int make_file(char* path) {
	int fd = mkstemp(path);
	if (fd < 0 || ftruncate(fd, 16) < 0 || __real_close(fd) < 0) {
		perror("create fixture");
		return -1;
	}
	return 0;
}

static void test_normal_caller(const char* path, struct mCore* core) {
	reset_case(path, 0);
	bool result = mCoreLoadSaveFile(core, path, false);
	int descriptorOpen = targetFdCount == 1 &&
	                     descriptor_is_open(targetFds[0]);
	if (!result || targetOpenAttempts != 1 || targetFdCount != 1 ||
	    allocationAttempts != 1 || allocationFailures ||
	    saveCallbackCalls != 1 || targetCloseCalls != 1 || descriptorOpen) {
		fprintf(stderr, "normal caller control changed\n");
		exit(1);
	}
	printf("PHASE1_CALLER_CASE normal caller_return=1 open_attempts=1 "
	       "successful_opens=1 allocation_attempts=1 allocation_failures=0 "
	       "save_callbacks=1 close_calls=1 target_fd_open=0\n");
}

static void test_failed_caller_retry_and_cleanup(const char* path,
                                                struct mCore* core) {
	reset_case(path, 1);
	bool failed = mCoreLoadSaveFile(core, path, false);
	int leakedFd = targetFdCount ? targetFds[0] : -1;
	int leakedAfterFailure = leakedFd >= 0 && descriptor_is_open(leakedFd);
	if (failed || targetOpenAttempts != 1 || targetFdCount != 1 ||
	    allocationAttempts != 1 || allocationFailures != 1 ||
	    saveCallbackCalls || targetCloseCalls || !leakedAfterFailure) {
		fprintf(stderr, "caller did not fail before save callback as expected\n");
		exit(1);
	}

	failAllocationAt = 0;
	bool recovered = mCoreLoadSaveFile(core, path, false);
	int leakedAfterRetry = descriptor_is_open(leakedFd);
	int retryFdClosed = targetFdCount == 2 &&
	                    !descriptor_is_open(targetFds[1]);
	if (!recovered || targetOpenAttempts != 2 || targetFdCount != 2 ||
	    allocationAttempts != 2 || allocationFailures != 1 ||
	    saveCallbackCalls != 1 || targetCloseCalls != 1 ||
	    !leakedAfterRetry || !retryFdClosed) {
		fprintf(stderr, "caller retry or descriptor ownership changed\n");
		exit(1);
	}
	printf("PHASE1_CALLER_CASE allocation_failure caller_return=0 "
	       "open_attempts=1 successful_opens=1 allocation_attempts=1 "
	       "allocation_failures=1 save_callbacks=0 close_calls=0 "
	       "leaked_fd_open=1\n");
	printf("PHASE1_CALLER_CASE retry failure_return=0 retry_return=1 "
	       "open_attempts=2 successful_opens=2 allocation_attempts=2 "
	       "allocation_failures=1 save_callbacks=1 close_calls=1 "
	       "leaked_first_fd_open=1 retry_fd_closed=1\n");

	if (__real_close(leakedFd) < 0) {
		perror("cleanup observed leaked descriptor");
		exit(1);
	}
}

static void test_open_failure(const char* path, struct mCore* core) {
	reset_case(path, 1);
	errno = 0;
	bool result = mCoreLoadSaveFile(core, path, false);
	int openError = errno;
	if (result || targetOpenAttempts != 1 || targetFdCount ||
	    allocationAttempts || allocationFailures || saveCallbackCalls ||
	    targetCloseCalls || openError != ENOENT) {
		fprintf(stderr, "caller open-failure control changed\n");
		exit(1);
	}
	printf("PHASE1_CALLER_CASE open_failure caller_return=0 "
	       "open_attempts=1 successful_opens=0 allocation_attempts=0 "
	       "allocation_failures=0 save_callbacks=0 errno=ENOENT\n");
}

int main(void) {
	char directory[] = "/tmp/mgba-core-loadsave-allocation-XXXXXX";
	if (!mkdtemp(directory)) {
		perror("mkdtemp");
		return 1;
	}
	char path[sizeof(directory) + sizeof("/save")];
	snprintf(path, sizeof(path), "%s/save", directory);
	char missingPath[sizeof(directory) + sizeof("/missing/save")];
	snprintf(missingPath, sizeof(missingPath), "%s/missing/save", directory);
	char fixture[] = "/tmp/mgba-core-loadsave-allocation-file-XXXXXX";
	if (make_file(fixture) < 0 || rename(fixture, path) < 0) {
		perror("prepare fixture path");
		return 1;
	}

	struct mCore core = {
		.loadSave = close_save_file,
		.loadTemporarySave = close_save_file,
	};
	test_normal_caller(path, &core);
	test_failed_caller_retry_and_cleanup(path, &core);
	test_open_failure(missingPath, &core);

	if (unlink(path) < 0 || rmdir(directory) < 0) {
		perror("remove fixture");
		return 1;
	}
	printf("PHASE1_CALLER_DONE\n");
	return 0;
}
