#define _GNU_SOURCE

#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static int (*real_msync)(void*, size_t, int);
static int (*real_open)(const char*, int, ...);
static int (*real_open64)(const char*, int, ...);
static int (*real_fstat)(int, struct stat*);
static int (*real_close)(int);
static int fstatTargetFd = -1;
static bool fstatFailureInjected;

static bool _pathForAddress(const void* address, char* path, size_t pathSize) {
	FILE* maps = fopen("/proc/self/maps", "r");
	if (!maps) {
		return false;
	}

	char line[8192];
	unsigned long begin;
	unsigned long end;
	bool found = false;
	while (fgets(line, sizeof(line), maps)) {
		path[0] = '\0';
		if (sscanf(line, "%lx-%lx %*s %*s %*s %*s %4095[^\n]", &begin, &end, path) != 3) {
			continue;
		}
		while (*path == ' ') {
			memmove(path, path + 1, strlen(path));
		}
		if ((uintptr_t) address >= begin && (uintptr_t) address < end) {
			found = true;
			break;
		}
	}
	fclose(maps);
	return found && pathSize > 0;
}

static void _recordSync(const char* marker, const char* operation, bool injected, int result) {
	if (!marker) {
		return;
	}
	int fd = open(marker, O_WRONLY | O_CREAT | O_APPEND, 0600);
	if (fd < 0) {
		return;
	}
	char line[96];
	int length = snprintf(line, sizeof(line), "operation=%s injected=%d result=%d\n", operation, injected, result);
	if (length > 0 && (size_t) length < sizeof(line)) {
		(void) write(fd, line, (size_t) length);
	}
	close(fd);
}

static void _recordFstat(const char* operation, bool injected, int result,
                         int error) {
	const char* marker = getenv("XGBA_FSTAT_MARKER");
	if (!marker) {
		return;
	}
	int fd = open(marker, O_WRONLY | O_CREAT | O_APPEND, 0600);
	if (fd < 0) {
		return;
	}
	char line[128];
	int length = snprintf(line, sizeof(line),
	                      "operation=%s injected=%d result=%d errno=%s\n",
	                      operation, injected, result,
	                      error == EIO ? "EIO" : "none");
	if (length > 0 && (size_t) length < sizeof(line)) {
		(void) write(fd, line, (size_t) length);
	}
	close(fd);
}

static int _trackFstatTarget(const char* path, int fd) {
	const char* target = getenv("XGBA_FSTAT_TARGET");
	if (fd >= 0 && target && path && strcmp(path, target) == 0) {
		fstatTargetFd = fd;
		fstatFailureInjected = false;
	}
	return fd;
}

static int _openForTarget(const char* path, int flags, mode_t mode,
                          int (**realOpen)(const char*, int, ...)) {
	if (!*realOpen) {
		*realOpen = dlsym(RTLD_NEXT, "open");
		if (!*realOpen) {
			errno = ENOSYS;
			return -1;
		}
	}

	const char* target = getenv("XGBA_OPEN_TARGET");
	if (target && path && strcmp(path, target) == 0) {
		const char* marker = getenv("XGBA_OPEN_MARKER");
		if (marker) {
			int fd = (*realOpen)(marker, O_WRONLY | O_CREAT | O_APPEND, 0600);
			if (fd >= 0) {
				static const char line[] = "operation=open injected=1 result=-1 errno=EIO\n";
				(void) write(fd, line, sizeof(line) - 1);
				close(fd);
			}
		}
		errno = EIO;
		return -1;
	}

	return (*realOpen)(path, flags, mode);
}

static mode_t _openMode(int flags, va_list args) {
	if (flags & O_CREAT) {
		return (mode_t) va_arg(args, int);
	}
#ifdef O_TMPFILE
	if ((flags & O_TMPFILE) == O_TMPFILE) {
		return (mode_t) va_arg(args, int);
	}
#endif
	return 0;
}

int open(const char* path, int flags, ...) {
	va_list args;
	va_start(args, flags);
	mode_t mode = _openMode(flags, args);
	va_end(args);
	return _trackFstatTarget(
		path, _openForTarget(path, flags, mode, &real_open));
}

int open64(const char* path, int flags, ...) {
	va_list args;
	va_start(args, flags);
	mode_t mode = _openMode(flags, args);
	va_end(args);
	if (!real_open64) {
		real_open64 = dlsym(RTLD_NEXT, "open64");
		if (!real_open64) {
			errno = ENOSYS;
			return -1;
		}
	}
	const char* target = getenv("XGBA_OPEN_TARGET");
	if (target && strcmp(path, target) == 0) {
		const char* marker = getenv("XGBA_OPEN_MARKER");
		if (marker) {
			int fd = real_open64(marker, O_WRONLY | O_CREAT | O_APPEND, 0600);
			if (fd >= 0) {
				static const char line[] = "operation=open64 injected=1 result=-1 errno=EIO\n";
				(void) write(fd, line, sizeof(line) - 1);
				close(fd);
			}
		}
		errno = EIO;
		return -1;
	}
	return _trackFstatTarget(path, real_open64(path, flags, mode));
}

int fstat(int fd, struct stat* statbuf) {
	if (!real_fstat) {
		real_fstat = dlsym(RTLD_NEXT, "fstat");
		if (!real_fstat) {
			errno = ENOSYS;
			return -1;
		}
	}
	if (fd == fstatTargetFd) {
		const char* inject = getenv("XGBA_FSTAT_INJECT");
		if (inject && strcmp(inject, "1") == 0 &&
		    !fstatFailureInjected) {
			fstatFailureInjected = true;
			_recordFstat("fstat", true, -1, EIO);
			errno = EIO;
			return -1;
		}
		int result = real_fstat(fd, statbuf);
		_recordFstat("fstat", false, result, result < 0 ? errno : 0);
		fstatTargetFd = -1;
		return result;
	}
	return real_fstat(fd, statbuf);
}

int close(int fd) {
	if (!real_close) {
		real_close = dlsym(RTLD_NEXT, "close");
		if (!real_close) {
			errno = ENOSYS;
			return -1;
		}
	}
	bool targetClose = fd == fstatTargetFd && fstatFailureInjected;
	if (targetClose) {
		fstatTargetFd = -1;
	}
	int result = real_close(fd);
	if (targetClose) {
		_recordFstat("close", false, result, result < 0 ? errno : 0);
	}
	return result;
}

static void _waitForRelease(void) {
	const char* release = getenv("XGBA_SYNC_RELEASE");
	if (!release) {
		return;
	}
	for (unsigned i = 0; i < 5000 && access(release, F_OK) != 0; ++i) {
		usleep(1000);
	}
}

int msync(void* address, size_t length, int flags) {
	if (!real_msync) {
		real_msync = dlsym(RTLD_NEXT, "msync");
		if (!real_msync) {
			errno = ENOSYS;
			return -1;
		}
	}

	char path[4096] = {0};
	const char* target = getenv("XGBA_SYNC_TARGET");
	if (target && _pathForAddress(address, path, sizeof(path)) && strcmp(path, target) == 0) {
		const char* operation = (flags & MS_ASYNC) ? "async" : "sync";
		const char* inject = getenv("XGBA_SYNC_INJECT_OPERATION");
		bool injected = inject && strcmp(inject, operation) == 0;
		if (injected) {
			_recordSync(getenv("XGBA_SYNC_MARKER"), operation, true, -1);
			if (flags & MS_ASYNC) {
				_waitForRelease();
			}
			errno = EIO;
			return -1;
		}
		int result = real_msync(address, length, flags);
		_recordSync(getenv("XGBA_SYNC_MARKER"), operation, false, result);
		if (flags & MS_ASYNC) {
			_waitForRelease();
		}
		return result;
	}

	return real_msync(address, length, flags);
}
