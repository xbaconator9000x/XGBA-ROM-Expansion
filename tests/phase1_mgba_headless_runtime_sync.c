#define _GNU_SOURCE

#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static int (*real_msync)(void*, size_t, int);

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
		const char* inject = getenv("XGBA_SYNC_INJECT_EIO");
		bool injected = (flags & MS_ASYNC) && inject && strcmp(inject, "1") == 0;
		if (injected) {
			_recordSync(getenv("XGBA_SYNC_MARKER"), operation, true, -1);
			_waitForRelease();
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
