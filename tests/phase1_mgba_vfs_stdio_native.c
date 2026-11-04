#define _GNU_SOURCE

#include <mgba-util/memory.h>
#include <mgba-util/vfs.h>

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#define GBA_SIZE_SRAM 4096
#define GBA_SIZE_SRAM512 512
#define GBA_SIZE_FLASH512 8192
#define GBA_SIZE_FLASH1M 16384
#define GBA_SIZE_EEPROM 8192
#define GBA_SIZE_EEPROM512 512
#define GBA_SIZE_ROM0 32768
#define GBA_IDLE_LOOP_NONE 0
#define EEPROM_COMMAND_NULL 0
#define FLASH_STATE_RAW 0
#define mSAVEDATA_CLEANUP_THRESHOLD 15
#define mCALLBACKS_INVOKE(...) ((void) 0)
#define mLOG(...)

enum {
	mSAVEDATA_DIRT_NONE = 0,
	mSAVEDATA_DIRT_NEW = 1,
	mSAVEDATA_DIRT_SEEN = 2,
};

enum GBASavedataType {
	GBA_SAVEDATA_AUTODETECT,
	GBA_SAVEDATA_SRAM,
	GBA_SAVEDATA_SRAM512,
	GBA_SAVEDATA_FLASH512,
	GBA_SAVEDATA_FLASH1M,
	GBA_SAVEDATA_EEPROM,
	GBA_SAVEDATA_EEPROM512,
	GBA_SAVEDATA_FORCE_NONE
};

struct mTiming {
	int unused;
};

struct mTimingEvent {
	const char* name;
	int priority;
	void* context;
	void (*callback)(struct mTiming*, void*, uint32_t);
};

struct GBASavedata {
	void* p;
	enum GBASavedataType type;
	uint8_t* data;
	int command;
	int flashState;
	struct VFile* vf;
	int mapMode;
	bool maskWriteback;
	struct VFile* realVf;
	int dirty;
	uint32_t dirtAge;
	struct mTimingEvent dust;
};

struct GBAMemory {
	struct {
		unsigned type;
	} unl;
	uint8_t* rom;
	size_t romSize;
	uint32_t romMask;
	struct GBASavedata savedata;
};

struct GBA {
	struct GBAMemory memory;
	struct VFile* romVf;
	size_t pristineRomSize;
	bool isPristine;
	size_t yankedRomSize;
	int idleLoop;
};

struct Cookie {
	uint8_t bytes[8192];
	size_t size;
	size_t written;
	off64_t position;
	size_t maxWrite;
	size_t readBudget;
	size_t readBytes;
	bool readFailureArmed;
	bool closeFailure;
	bool closed;
};

static FILE* failFlushFile;
static unsigned injectedFlushes;
static bool trackNativeWriteErrors;
static unsigned nativeWriteErrors;
static unsigned rtcWrites;

int __real_fflush(FILE* file);
size_t __real_fwrite(const void* buffer, size_t size, size_t count,
                     FILE* file);

size_t __wrap_fwrite(const void* buffer, size_t size, size_t count,
                     FILE* file) {
	size_t result = __real_fwrite(buffer, size, count, file);
	if (trackNativeWriteErrors && result < count) {
		++nativeWriteErrors;
	}
	return result;
}

int __wrap_fflush(FILE* file) {
	if (file == failFlushFile) {
		failFlushFile = NULL;
		++injectedFlushes;
		errno = EIO;
		return EOF;
	}
	return __real_fflush(file);
}

void* anonymousMemoryMap(size_t size) {
	return calloc(1, size);
}

void mappedMemoryFree(void* memory, size_t size) {
	(void) size;
	free(memory);
}

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	(void) vf;
	(void) buffer;
	(void) size;
	return -1;
}

static void check(bool result, const char* message) {
	if (!result) {
		fprintf(stderr, "stdio VFile witness: %s\n", message);
		exit(1);
	}
}

static ssize_t cookie_read(void* opaque, char* buffer, size_t size) {
	struct Cookie* cookie = opaque;
	if (cookie->readFailureArmed && !cookie->readBudget) {
		errno = EIO;
		return -1;
	}
	if (cookie->readFailureArmed && size > cookie->readBudget) {
		size = cookie->readBudget;
	}
	if (cookie->position < 0 || (size_t) cookie->position >= cookie->size) {
		return 0;
	}
	size_t available = cookie->size - (size_t) cookie->position;
	if (size > available) {
		size = available;
	}
	memcpy(buffer, &cookie->bytes[cookie->position], size);
	cookie->position += (off64_t) size;
	cookie->readBytes += size;
	if (cookie->readFailureArmed) {
		cookie->readBudget -= size;
	}
	return (ssize_t) size;
}

static ssize_t cookie_write(void* opaque, const char* buffer, size_t size) {
	struct Cookie* cookie = opaque;
	if (cookie->maxWrite && size > cookie->maxWrite) {
		size = cookie->maxWrite;
	}
	if (cookie->position < 0 ||
	    (uint64_t) cookie->position + size > sizeof(cookie->bytes)) {
		errno = EFBIG;
		return -1;
	}
	memcpy(&cookie->bytes[cookie->position], buffer, size);
	cookie->position += (off64_t) size;
	if ((size_t) cookie->position > cookie->size) {
		cookie->size = (size_t) cookie->position;
	}
	cookie->written += size;
	return (ssize_t) size;
}

static int cookie_seek(void* opaque, off64_t* offset, int whence) {
	struct Cookie* cookie = opaque;
	off64_t base;
	switch (whence) {
	case SEEK_SET:
		base = 0;
		break;
	case SEEK_CUR:
		base = cookie->position;
		break;
	case SEEK_END:
		base = (off64_t) cookie->size;
		break;
	default:
		errno = EINVAL;
		return -1;
	}
	if (base + *offset < 0 ||
	    (uint64_t) (base + *offset) > sizeof(cookie->bytes)) {
		errno = EINVAL;
		return -1;
	}
	cookie->position = base + *offset;
	*offset = cookie->position;
	return 0;
}

static int cookie_close(void* opaque) {
	struct Cookie* cookie = opaque;
	cookie->closed = true;
	if (cookie->closeFailure) {
		errno = EIO;
		return -1;
	}
	return 0;
}

static FILE* open_cookie(struct Cookie* cookie, const char* mode) {
	cookie_io_functions_t functions = {
		.read = cookie_read,
		.write = cookie_write,
		.seek = cookie_seek,
		.close = cookie_close,
	};
	FILE* file = fopencookie(cookie, mode, functions);
	check(file != NULL, "fopencookie failed");
	check(setvbuf(file, NULL, _IONBF, 0) == 0, "setvbuf failed");
	return file;
}

static void make_file(const char* path, const uint8_t* bytes, size_t size) {
	int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0600);
	check(fd >= 0, "open seed file failed");
	size_t written = 0;
	while (written < size) {
		ssize_t result = write(fd, bytes + written, size - written);
		check(result > 0, "seed file write failed");
		written += (size_t) result;
	}
	check(close(fd) == 0, "close seed file failed");
}

static uint8_t read_in_child(const char* path) {
	pid_t child = fork();
	check(child >= 0, "fork failed");
	if (!child) {
		int fd = open(path, O_RDONLY);
		uint8_t value = 0;
		ssize_t count = fd < 0 ? -1 : pread(fd, &value, 1, 0);
		if (fd >= 0) {
			close(fd);
		}
		_exit(count == 1 ? value : 90);
	}
	int status = 0;
	check(waitpid(child, &status, 0) == child, "waitpid failed");
	check(WIFEXITED(status) && WEXITSTATUS(status) <= UINT8_MAX,
	      "child read failed");
	return (uint8_t) WEXITSTATUS(status);
}

static void _ashesToAshes(struct mTiming* timing, void* user,
                          uint32_t cyclesLate) {
	(void) timing;
	(void) user;
	(void) cyclesLate;
}

static size_t GBASavedataSize(const struct GBASavedata* savedata);
static void GBASavedataInit(struct GBASavedata* savedata, struct VFile* vf);
static void GBASavedataDeinit(struct GBASavedata* savedata);
static void GBASavedataMask(struct GBASavedata* savedata, struct VFile* vf,
                            bool writeback);
static bool GBASavedataLoad(struct GBASavedata* savedata, struct VFile* in);
static void GBASavedataUnmask(struct GBASavedata* savedata);
static void GBASavedataForceType(struct GBASavedata* savedata,
                                 enum GBASavedataType type);
static void GBASavedataInitSRAM(struct GBASavedata* savedata);
static void GBASavedataInitFlash(struct GBASavedata* savedata);
static void GBASavedataInitEEPROM(struct GBASavedata* savedata);
static void GBASavedataInitSRAM512(struct GBASavedata* savedata);
static void GBASavedataClean(struct GBASavedata* savedata,
                             uint32_t frameCount);
static void GBASavedataRTCWrite(struct GBASavedata* savedata);
static bool GBALoadSave(struct GBA* gba, struct VFile* sav);
static void GBAUnloadROM(struct GBA* gba);
static void GBAMemoryClearAGBPrint(struct GBA* gba);
static void GBAUnlCartUnload(struct GBA* gba);

PHASE1_INSERT_PINNED_M_SAVEDATA_CLEAN
PHASE1_INSERT_PINNED_VFILE_OPEN
PHASE1_INSERT_PINNED_SAVEDATA_SIZE
PHASE1_INSERT_PINNED_SAVEDATA_INITIALIZER_BODY
PHASE1_INSERT_PINNED_SAVEDATA_DEINIT
PHASE1_INSERT_PINNED_SAVEDATA_MASK
PHASE1_INSERT_PINNED_SAVEDATA_LOAD
PHASE1_INSERT_PINNED_SAVEDATA_UNMASK
PHASE1_INSERT_PINNED_SAVEDATA_FORCE_TYPE
PHASE1_INSERT_PINNED_SRAM_INITIALIZER_BODY
PHASE1_INSERT_PINNED_SAVEDATA_CLEAN
PHASE1_INSERT_PINNED_GBA_LOAD_SAVE
PHASE1_INSERT_PINNED_GBA_UNLOAD_ROM

static void GBASavedataRTCWrite(struct GBASavedata* savedata) {
	(void) savedata;
	++rtcWrites;
}

static void GBASavedataInitFlash(struct GBASavedata* savedata) {
	(void) savedata;
}

static void GBASavedataInitEEPROM(struct GBASavedata* savedata) {
	(void) savedata;
}

static void GBASavedataInitSRAM512(struct GBASavedata* savedata) {
	(void) savedata;
}

static void GBAMemoryClearAGBPrint(struct GBA* gba) {
	(void) gba;
}

static void GBAUnlCartUnload(struct GBA* gba) {
	(void) gba;
}

static void test_regular_lifecycle(const char* directory) {
	char path[256];
	snprintf(path, sizeof(path), "%s/regular.sav", directory);
	uint8_t seed[GBA_SIZE_SRAM] = {0};
	make_file(path, seed, sizeof(seed));

	struct GBA gba = {0};
	struct VFile* save = VFileOpen(path, O_RDWR);
	check(save != NULL, "original VFileOpen dispatcher failed");
	check(GBALoadSave(&gba, save), "original GBALoadSave failed");
	GBASavedataForceType(&gba.memory.savedata, GBA_SAVEDATA_SRAM);
	check(gba.memory.savedata.data != NULL, "original SRAM map failed");
	gba.memory.savedata.data[0] = 0x5C;
	GBAUnloadROM(&gba);

	bool cleared = !gba.memory.savedata.vf && !gba.memory.savedata.data &&
	               !gba.memory.savedata.realVf;
	uint8_t childByte = read_in_child(path);
	check(cleared && childByte == 0x5C, "regular stdio save lifecycle changed");
	printf("PHASE1_STDIO_CASE regular_lifecycle backend=stdio data_cleared=1 "
	       "child_byte=%u\n", childByte);
	check(unlink(path) == 0, "unlink regular save failed");
}

static void test_mapped_short_unmap(void) {
	struct Cookie cookie = {.size = GBA_SIZE_SRAM};
	memset(cookie.bytes, 0x21, cookie.size);
	struct VFile* vf = VFileFromFILE(open_cookie(&cookie, "w+"));
	struct GBASavedata savedata = {0};
	GBASavedataInit(&savedata, vf);
	GBASavedataForceType(&savedata, GBA_SAVEDATA_SRAM);
	check(savedata.data != NULL, "cookie-backed SRAM map failed");
	savedata.data[0] = 0xA7;
	cookie.maxWrite = 3;
	GBASavedataDeinit(&savedata);
	bool cleared = savedata.data == NULL && savedata.vf == NULL;
	check(cleared && cookie.written == 3 && cookie.bytes[0] == 0xA7,
	      "short stdio unmap behavior changed");
	printf("PHASE1_STDIO_CASE mapped_short_unmap requested=4096 "
	       "written=%zu data_cleared=%u\n", cookie.written, (unsigned) cleared);
	check(vf->close(vf), "close short-unmap cookie failed");
}

static void test_raw_short_load(const char* directory) {
	char path[256];
	snprintf(path, sizeof(path), "%s/raw-input.sav", directory);
	const uint8_t inputBytes[] = "12345678";
	make_file(path, inputBytes, sizeof(inputBytes) - 1);
	struct VFile* input = VFileOpen(path, O_RDONLY);
	check(input != NULL, "open raw-load input failed");

	struct Cookie outputCookie = {.maxWrite = 3};
	struct VFile* output = VFileFromFILE(open_cookie(&outputCookie, "w+"));
	struct GBASavedata savedata = {0};
	GBASavedataInit(&savedata, output);
	bool loaded = GBASavedataLoad(&savedata, input);
	check(loaded && outputCookie.written == 3 &&
	      memcmp(outputCookie.bytes, inputBytes, 3) == 0,
	      "raw GBASavedataLoad short-write behavior changed");
	printf("PHASE1_STDIO_CASE raw_short_load source_bytes=8 "
	       "written=%zu load_result=%u\n", outputCookie.written,
	       (unsigned) loaded);
	check(input->close(input), "close raw-load input failed");
	check(output->close(output), "close raw-load output failed");
	check(unlink(path) == 0, "unlink raw-load input failed");
}

static void test_unmask_short_read(const char* directory) {
	char path[256];
	snprintf(path, sizeof(path), "%s/unmask.sav", directory);
	uint8_t seed[GBA_SIZE_SRAM] = {0};
	make_file(path, seed, sizeof(seed));

	struct GBA gba = {0};
	struct VFile* real = VFileOpen(path, O_RDWR);
	check(real && GBALoadSave(&gba, real), "load real stdio save failed");
	GBASavedataForceType(&gba.memory.savedata, GBA_SAVEDATA_SRAM);

	struct Cookie temporary = {.size = GBA_SIZE_SRAM};
	memset(temporary.bytes, 0xD4, temporary.size);
	struct VFile* masked = VFileFromFILE(open_cookie(&temporary, "w+"));
	GBASavedataMask(&gba.memory.savedata, masked, true);
	check(gba.memory.savedata.data != NULL, "masked stdio save map failed");

	temporary.readFailureArmed = true;
	temporary.readBudget = 32;
	temporary.readBytes = 0;
	GBASavedataUnmask(&gba.memory.savedata);
	size_t bytesRead = temporary.readBytes;
	bool unmaskCompleted = temporary.closed &&
	                       gba.memory.savedata.data != NULL &&
	                       gba.memory.savedata.data[0] == 0xD4 &&
	                       !gba.memory.savedata.maskWriteback;
	check(unmaskCompleted && bytesRead == 32,
	      "short read did not traverse original unmask lifecycle");
	GBAUnloadROM(&gba);
	uint8_t childByte = read_in_child(path);
	check(childByte == 0xD4, "unmask short-read writeback not visible to child");
	printf("PHASE1_STDIO_CASE unmask_short_read read_bytes=%zu requested=4096 "
	       "unmask_completed=%u child_byte=%u\n", bytesRead,
	       (unsigned) unmaskCompleted, childByte);
	check(unlink(path) == 0, "unlink unmask save failed");
}

static void test_injected_flush(const char* directory) {
	char path[256];
	snprintf(path, sizeof(path), "%s/flush.sav", directory);
	FILE* stream = fopen(path, "w+b");
	check(stream != NULL, "open injected-flush file failed");
	struct VFile* vf = VFileFromFILE(stream);
	static const uint8_t payload[] = "Flush";
	ssize_t written = vf->write(vf, payload, sizeof(payload) - 1);
	failFlushFile = stream;
	bool synced = vf->sync(vf, NULL, 0);
	bool injected = injectedFlushes == 1;
	bool closed = vf->close(vf);
	uint8_t childByte = read_in_child(path);
	check(written == (ssize_t) (sizeof(payload) - 1) && !synced && injected &&
	      closed && childByte == 'F',
	      "injected stdio fflush result changed");
	printf("PHASE1_STDIO_CASE injected_flush write_return=%zd sync_result=%u "
	       "injected=%u close_result=%u child_byte=%u\n", written,
	       (unsigned) synced, injectedFlushes, (unsigned) closed, childByte);
	check(unlink(path) == 0, "unlink injected-flush file failed");
}

static void test_dev_full_flush(void) {
	struct VFile* vf = VFileOpen("/dev/full", O_WRONLY);
	check(vf != NULL, "Linux /dev/full unavailable");
	struct GBASavedata savedata = {
		.vf = vf,
		.type = GBA_SAVEDATA_SRAM,
		.data = calloc(1, GBA_SIZE_SRAM),
		.mapMode = MAP_WRITE,
		.dirty = mSAVEDATA_DIRT_SEEN,
	};
	check(savedata.data != NULL, "allocate /dev/full savedata buffer failed");
	nativeWriteErrors = 0;
	trackNativeWriteErrors = true;
	rtcWrites = 0;
	GBASavedataClean(&savedata, mSAVEDATA_CLEANUP_THRESHOLD + 1);
	trackNativeWriteErrors = false;
	unsigned observedWriteErrors = nativeWriteErrors;
	bool closed = vf->close(vf);
	check(observedWriteErrors > 0 && savedata.dirty == 0 && rtcWrites == 0,
	      "Linux /dev/full cleanup did not observe a write error");
	printf("PHASE1_STDIO_CASE dev_full_clean write_errors=%u dirty=%u "
	       "rtc_writes=%u close_result=%u\n", observedWriteErrors,
	       (unsigned) savedata.dirty, rtcWrites, (unsigned) closed);
	free(savedata.data);
}

static void test_unload_close_error(void) {
	struct Cookie cookie = {.closeFailure = true};
	struct VFile* vf = VFileFromFILE(open_cookie(&cookie, "w+"));
	struct GBA gba = {0};
	GBASavedataInit(&gba.memory.savedata, vf);
	GBAUnloadROM(&gba);
	bool cleared = !gba.memory.savedata.vf && !gba.memory.savedata.realVf;
	bool wrapperRetained = cleared && cookie.closed;
	check(wrapperRetained, "GBA unload close-error state changed");
	free(vf);
	printf("PHASE1_STDIO_CASE unload_close_error underlying_closed=%u "
	       "wrapper_retained=%u savedata_cleared=%u\n",
	       (unsigned) cookie.closed, (unsigned) wrapperRetained,
	       (unsigned) cleared);
}

int main(void) {
	char directory[] = "/tmp/mgba-vfs-stdio-XXXXXX";
	check(mkdtemp(directory) != NULL, "mkdtemp failed");
	test_regular_lifecycle(directory);
	test_mapped_short_unmap();
	test_raw_short_load(directory);
	test_unmask_short_read(directory);
	test_injected_flush(directory);
	test_dev_full_flush();
	test_unload_close_error();
	check(rmdir(directory) == 0, "remove temporary directory failed");
	puts("PHASE1_STDIO_DONE");
	return 0;
}
