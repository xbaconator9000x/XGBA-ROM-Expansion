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

static const char* targetPath;
static int targetOpenCalls;
static int openedFd = -1;
static int injectAllocationFailure;
static int allocationAttempts;
static int allocationFailures;
static int trackedCloseCalls;

int __real_open(const char* path, int flags, ...);
int __real_close(int fd);
void* __real_malloc(size_t size);

int __wrap_open(const char* path, int flags, ...) {
	int fd;
	if (flags & O_CREAT) {
		va_list args;
		va_start(args, flags);
		mode_t mode = va_arg(args, mode_t);
		va_end(args);
		fd = __real_open(path, flags, mode);
	} else {
		fd = __real_open(path, flags);
	}
	if (targetPath && !strcmp(path, targetPath)) {
		++targetOpenCalls;
		if (fd >= 0) {
			openedFd = fd;
		}
	}
	return fd;
}

void* __wrap_malloc(size_t size) {
	if (openedFd >= 0 && size == sizeof(struct ExpectedVFileFDLayout) &&
	    allocationAttempts < targetOpenCalls) {
		++allocationAttempts;
		if (injectAllocationFailure) {
			++allocationFailures;
			errno = ENOMEM;
			return NULL;
		}
	}
	return __real_malloc(size);
}

int __wrap_close(int fd) {
	if (fd == openedFd) {
		++trackedCloseCalls;
	}
	return __real_close(fd);
}

static void reset_case(const char* path, int inject) {
	targetPath = path;
	targetOpenCalls = 0;
	openedFd = -1;
	injectAllocationFailure = inject;
	allocationAttempts = 0;
	allocationFailures = 0;
	trackedCloseCalls = 0;
}

static int make_file(char* path, size_t size) {
	int fd = mkstemp(path);
	if (fd < 0 || ftruncate(fd, (off_t) size) < 0 || __real_close(fd) < 0) {
		perror("create fixture");
		exit(1);
	}
	return 0;
}

static void test_successful_open_and_close(const char* path) {
	reset_case(path, 0);
	struct VFile* vf = VFileOpen(path, O_RDWR);
	if (!vf || targetOpenCalls != 1 || allocationAttempts != 1 ||
	    allocationFailures || openedFd < 0 || !vf->close(vf) ||
	    trackedCloseCalls != 1 || fcntl(openedFd, F_GETFD) != -1 ||
	    errno != EBADF) {
		fprintf(stderr, "successful VFile open/close control failed\n");
		exit(1);
	}
	printf("PHASE1_ALLOC_CASE success caller_return=1 open_calls=1 "
	       "allocation_attempts=1 allocation_failures=0 close_calls=1 "
	       "fd_open_after_close=0\n");
}

static void test_allocation_failure_leaves_descriptor_open(const char* path) {
	reset_case(path, 1);
	struct VFile* vf = VFileOpen(path, O_RDWR);
	int descriptorOpen = openedFd >= 0 && fcntl(openedFd, F_GETFD) >= 0;
	if (vf || targetOpenCalls != 1 || allocationAttempts != 1 ||
	    allocationFailures != 1 || trackedCloseCalls || !descriptorOpen) {
		fprintf(stderr, "allocation-failure ownership observation changed\n");
		exit(1);
	}
	printf("PHASE1_ALLOC_CASE allocation_failure caller_return=0 "
	       "open_calls=1 allocation_attempts=1 allocation_failures=1 "
	       "close_calls=0 fd_open_after_return=%d\n", descriptorOpen);
	if (__real_close(openedFd) < 0) {
		perror("cleanup leaked fixture descriptor");
		exit(1);
	}
}

static void test_open_failure(const char* path) {
	reset_case(path, 1);
	errno = 0;
	struct VFile* vf = VFileOpen(path, O_RDONLY);
	int openError = errno;
	if (vf || targetOpenCalls != 1 || allocationAttempts ||
	    allocationFailures || openedFd >= 0 || openError != ENOENT) {
		fprintf(stderr, "open-failure negative control changed\n");
		exit(1);
	}
	printf("PHASE1_ALLOC_CASE open_failure caller_return=0 open_calls=1 "
	       "allocation_attempts=0 allocation_failures=0 errno=ENOENT\n");
}

int main(void) {
	char directory[] = "/tmp/mgba-vfs-fd-allocation-XXXXXX";
	if (!mkdtemp(directory)) {
		perror("mkdtemp");
		return 1;
	}
	char path[sizeof(directory) + sizeof("/save")];
	snprintf(path, sizeof(path), "%s/save", directory);
	char missingPath[sizeof(directory) + sizeof("/missing")];
	snprintf(missingPath, sizeof(missingPath), "%s/missing", directory);
	char fixture[] = "/tmp/mgba-vfs-fd-allocation-file-XXXXXX";
	if (make_file(fixture, 16) < 0 || rename(fixture, path) < 0) {
		perror("prepare fixture path");
		return 1;
	}

	test_successful_open_and_close(path);
	test_allocation_failure_leaves_descriptor_open(path);
	test_open_failure(missingPath);

	if (unlink(path) < 0 || rmdir(directory) < 0) {
		perror("remove fixture");
		return 1;
	}
	printf("PHASE1_ALLOC_DONE\n");
	return 0;
}
