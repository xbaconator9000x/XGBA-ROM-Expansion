#include <mgba-util/vfs.h>
#include <mgba/internal/defines.h>

#include <errno.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#define mLOG(...)

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

static unsigned asyncCalls;
static unsigned syncCalls;
static unsigned fsyncCalls;

int __real_msync(void* memory, size_t size, int flags);
int __wrap_msync(void* memory, size_t size, int flags) {
	if (flags == MS_ASYNC) {
		++asyncCalls;
	} else if (flags == MS_SYNC) {
		++syncCalls;
	}
	return __real_msync(memory, size, flags);
}

int __real_fsync(int fd);
int __wrap_fsync(int fd) {
	++fsyncCalls;
	return __real_fsync(fd);
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

static int make_file(const char* path, uint8_t initial) {
	int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0600);
	if (fd < 0 || ftruncate(fd, 4096) < 0 ||
	    pwrite(fd, &initial, 1, 0) != 1) {
		fail("create temporary file");
	}
	return fd;
}

static uint8_t child_file_byte(const char* path) {
	pid_t child = fork();
	if (child < 0) {
		fail("fork");
	}
	if (!child) {
		int fd = open(path, O_RDONLY);
		uint8_t value = 0;
		ssize_t count = fd < 0 ? -1 : pread(fd, &value, 1, 0);
		if (fd >= 0) {
			close(fd);
		}
		_exit(count == 1 ? value : 91);
	}
	int status = 0;
	if (waitpid(child, &status, 0) != child ||
	    !WIFEXITED(status) || WEXITSTATUS(status) > UINT8_MAX) {
		fail("child file read");
	}
	return (uint8_t) WEXITSTATUS(status);
}

static void test_mapping_visibility(const char* sharedPath,
                                   const char* privatePath) {
	int fd = make_file(sharedPath, 0x11);
	struct VFile* vf = VFileFromFD(fd);
	if (!vf) {
		fail("VFileFromFD shared");
	}
	uint8_t* shared = vf->map(vf, 4096, MAP_WRITE);
	if (!shared) {
		fail("map shared");
	}
	shared[0] = 0xA5;
	uint8_t sharedChild = child_file_byte(sharedPath);
	vf->unmap(vf, shared, 4096);
	if (!vf->close(vf) || sharedChild != 0xA5) {
		fprintf(stderr, "shared mapping was not visible to child\n");
		exit(1);
	}

	fd = make_file(privatePath, 0x22);
	vf = VFileFromFD(fd);
	if (!vf) {
		fail("VFileFromFD private");
	}
	uint8_t* privateMap = vf->map(vf, 4096, MAP_READ);
	if (!privateMap) {
		fail("map private");
	}
	privateMap[0] = 0xB6;
	uint8_t privateChild = child_file_byte(privatePath);
	vf->unmap(vf, privateMap, 4096);
	if (!vf->close(vf) || privateChild != 0x22) {
		fprintf(stderr, "private mapping unexpectedly changed backing file\n");
		exit(1);
	}
	printf("PHASE1_VFS_CASE mappings shared_child=%u private_child=%u\n",
	       sharedChild, privateChild);
}

static void test_cleanup_sync(const char* path) {
	asyncCalls = 0;
	syncCalls = 0;
	fsyncCalls = 0;
	int fd = make_file(path, 0x33);
	struct VFile* vf = VFileFromFD(fd);
	if (!vf) {
		fail("VFileFromFD cleanup");
	}
	uint8_t* data = vf->map(vf, 4096, MAP_WRITE);
	if (!data) {
		fail("map cleanup");
	}
	data[0] = 0xC7;
	struct GBASavedata savedata = {
		.vf = vf,
		.dirty = mSAVEDATA_DIRT_NEW,
		.mapMode = MAP_WRITE,
		.data = data,
		.size = 4096,
	};
	GBASavedataClean(&savedata, 100);
	GBASavedataClean(&savedata, 115);
	if (asyncCalls || syncCalls || fsyncCalls || savedata.rtcWrites) {
		fprintf(stderr, "cleanup ran before the strict frame threshold\n");
		exit(1);
	}
	GBASavedataClean(&savedata, 116);
	if (asyncCalls != 1 || syncCalls || fsyncCalls ||
	    savedata.rtcWrites != 1 || savedata.dirty != 0 ||
	    savedata.dirtAge != 100) {
		fprintf(stderr, "dirty cleanup did not invoke the expected sync path\n");
		exit(1);
	}
	vf->unmap(vf, data, 4096);
	if (syncCalls != 1 || asyncCalls != 1 || fsyncCalls ||
	    !vf->close(vf)) {
		fprintf(stderr, "mapped unmap/close path changed\n");
		exit(1);
	}
	printf("PHASE1_VFS_CASE cleanup async_ms=%u sync_ms=%u fsync=%u rtc=%u dirty=%d age=%u\n",
	       asyncCalls, syncCalls, fsyncCalls, savedata.rtcWrites,
	       savedata.dirty, savedata.dirtAge);
}

static void test_close_with_live_mapping(const char* path) {
	struct VFile* vf = VFileFromFD(make_file(path, 0x44));
	if (!vf) {
		fail("VFileFromFD active close");
	}
	uint8_t* data = vf->map(vf, 4096, MAP_WRITE);
	if (!data) {
		fail("map active close");
	}
	data[0] = 0xD8;
	if (!vf->close(vf) || data[0] != 0xD8 || munmap(data, 4096) < 0) {
		fprintf(stderr, "close changed mapping lifetime or failed\n");
		exit(1);
	}
	printf("PHASE1_VFS_CASE close active_mapping_survives=1\n");
}

int main(void) {
	char directory[] = "/tmp/mgba-vfs-fd-witness-XXXXXX";
	if (!mkdtemp(directory)) {
		fail("mkdtemp");
	}
	char sharedPath[PATH_MAX];
	char privatePath[PATH_MAX];
	char cleanupPath[PATH_MAX];
	char activeClosePath[PATH_MAX];
	snprintf(sharedPath, sizeof(sharedPath), "%s/shared.sav", directory);
	snprintf(privatePath, sizeof(privatePath), "%s/private.sav", directory);
	snprintf(cleanupPath, sizeof(cleanupPath), "%s/cleanup.sav", directory);
	snprintf(activeClosePath, sizeof(activeClosePath), "%s/active-close.sav",
	         directory);

	test_mapping_visibility(sharedPath, privatePath);
	test_cleanup_sync(cleanupPath);
	test_close_with_live_mapping(activeClosePath);

	unlink(sharedPath);
	unlink(privatePath);
	unlink(cleanupPath);
	unlink(activeClosePath);
	if (rmdir(directory) < 0) {
		fail("remove temporary directory");
	}
	puts("PHASE1_VFS_DONE");
	return 0;
}
