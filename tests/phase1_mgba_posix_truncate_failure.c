#define _GNU_SOURCE
#include <mgba-util/vfs.h>

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#define GBA_SIZE_SRAM 0x8000
#define GBA_SIZE_SRAM512 0x10000
#define GBA_SIZE_FLASH512 0x10000
#define GBA_SIZE_FLASH1M 0x20000
#define GBA_SIZE_EEPROM 0x2000
#define GBA_SIZE_EEPROM512 0x200
#define GBA_SIZE_ROM0 0x8000
#define GBA_IDLE_LOOP_NONE 0
#define mCALLBACKS_INVOKE(...) ((void) 0)
#define mLOG(...) ((void) 0)

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

enum {
	EEPROM_COMMAND_NULL,
	FLASH_STATE_RAW
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

struct GBA {
	struct {
		struct {
			unsigned type;
		} unl;
		uint8_t* rom;
		size_t romSize;
		uint32_t romMask;
		struct GBASavedata savedata;
	} memory;
	struct VFile* romVf;
	size_t pristineRomSize;
	bool isPristine;
	size_t yankedRomSize;
	int idleLoop;
};

struct mCore {
	struct GBA* board;
};

static int truncate_trace_fd = -1;
static int truncate_fault_errno;

int __real_ftruncate(int fd, off_t length);
int __wrap_ftruncate(int fd, off_t length) {
	if (truncate_fault_errno) {
		char event = truncate_fault_errno == ENOSPC ? 'N' : 'E';
		(void) write(truncate_trace_fd, &event, 1);
		errno = truncate_fault_errno;
		truncate_fault_errno = 0;
		return -1;
	}
	int result = __real_ftruncate(fd, length);
	char event = result == 0 ? 'S' : 'X';
	(void) write(truncate_trace_fd, &event, 1);
	return result;
}

void* anonymousMemoryMap(size_t size) {
	return calloc(1, size);
}

void mappedMemoryFree(void* memory, size_t size) {
	UNUSED(size);
	free(memory);
}

void GBAMemoryClearAGBPrint(struct GBA* gba) {
	UNUSED(gba);
}

void GBAUnlCartUnload(struct GBA* gba) {
	UNUSED(gba);
}

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	UNUSED(vf);
	UNUSED(buffer);
	UNUSED(size);
	return -1;
}

static void GBASavedataInitFlash(struct GBASavedata* savedata) {
	UNUSED(savedata);
}

static void GBASavedataInitEEPROM(struct GBASavedata* savedata) {
	UNUSED(savedata);
}

static void GBASavedataInitSRAM512(struct GBASavedata* savedata) {
	UNUSED(savedata);
}

static bool GBASavedataLoad(struct GBASavedata* savedata, struct VFile* in) {
	UNUSED(savedata);
	UNUSED(in);
	return false;
}

static void GBASavedataForceType(struct GBASavedata* savedata,
                                 enum GBASavedataType type);
static void GBASavedataInitSRAM(struct GBASavedata* savedata);

PHASE1_INSERT_PINNED_ASHES
PHASE1_INSERT_PINNED_SAVEDATA_SIZE
PHASE1_INSERT_PINNED_SAVEDATA_INIT
PHASE1_INSERT_PINNED_SAVEDATA_DEINIT
PHASE1_INSERT_PINNED_SAVEDATA_UNMASK
PHASE1_INSERT_PINNED_SAVEDATA_FORCE_TYPE
PHASE1_INSERT_PINNED_SAVEDATA_INIT_SRAM
PHASE1_INSERT_PINNED_GBA_LOAD_SAVE
PHASE1_INSERT_PINNED_GBA_CORE_LOAD_SAVE
PHASE1_INSERT_PINNED_GBA_UNLOAD_ROM

static void fail(const char* message) {
	perror(message);
	_exit(90);
}

static void create_save(const char* path) {
	int fd = open(path, O_CREAT | O_EXCL | O_RDWR, 0600);
	if (fd < 0) {
		fail("create temporary savedata");
	}
	const uint8_t seed = 0x2A;
	if (write(fd, &seed, sizeof(seed)) != sizeof(seed) || close(fd) < 0) {
		fail("initialize temporary savedata");
	}
}

static bool file_is_initialized(const char* path) {
	int fd = open(path, O_RDONLY);
	if (fd < 0) {
		return false;
	}
	struct stat stat;
	bool valid = fstat(fd, &stat) == 0 && stat.st_size == GBA_SIZE_SRAM;
	uint8_t buffer[4096];
	for (off_t offset = 0; valid && offset < stat.st_size;) {
		size_t amount = (size_t) (stat.st_size - offset);
		if (amount > sizeof(buffer)) {
			amount = sizeof(buffer);
		}
		ssize_t count = pread(fd, buffer, amount, offset);
		if (count != (ssize_t) amount) {
			valid = false;
			break;
		}
		for (size_t i = 0; i < amount; ++i) {
			uint8_t expected = offset + (off_t) i == 0 ? 0x2A : 0xFF;
			if (buffer[i] != expected) {
				valid = false;
				break;
			}
		}
		offset += (off_t) amount;
	}
	if (close(fd) < 0) {
		return false;
	}
	return valid;
}

struct ChildResult {
	int status;
	char events[8];
	size_t event_count;
};

static struct ChildResult run_load_save(const char* path, int injected_errno) {
	int events[2];
	if (pipe(events) < 0) {
		fail("pipe");
	}
	pid_t child = fork();
	if (child < 0) {
		fail("fork");
	}
	if (!child) {
		close(events[0]);
		struct rlimit core_limit = { 0, 0 };
		(void) setrlimit(RLIMIT_CORE, &core_limit);
		truncate_trace_fd = events[1];
		truncate_fault_errno = injected_errno;

		struct GBA gba;
		memset(&gba, 0, sizeof(gba));
		gba.memory.savedata.type = GBA_SAVEDATA_SRAM;
		struct mCore core = { .board = &gba };
		struct VFile* vf = VFileOpenFD(path, O_RDWR);
		if (!vf) {
			_exit(91);
		}
		bool loaded = _GBACoreLoadSave(&core, vf);
		if (!loaded || !gba.memory.savedata.data ||
		    gba.memory.savedata.type != GBA_SAVEDATA_SRAM ||
		    gba.memory.savedata.vf != vf ||
		    gba.memory.savedata.realVf != vf) {
			_exit(92);
		}
		char returned = 'R';
		(void) write(events[1], &returned, 1);
		if (!file_is_initialized(path)) {
			_exit(93);
		}
		GBAUnloadROM(&gba);
		char cleaned = 'C';
		(void) write(events[1], &cleaned, 1);
		_exit(0);
	}

	close(events[1]);
	struct ChildResult result = { 0 };
	if (waitpid(child, &result.status, 0) != child) {
		fail("waitpid");
	}
	ssize_t count;
	while ((count = read(events[0], result.events + result.event_count,
	                     sizeof(result.events) - result.event_count)) > 0) {
		result.event_count += (size_t) count;
		if (result.event_count == sizeof(result.events)) {
			break;
		}
	}
	close(events[0]);
	return result;
}

static void require(bool condition, const char* message) {
	if (!condition) {
		fprintf(stderr, "%s\n", message);
		exit(1);
	}
}

static void run_success_case(const char* directory, const char* name) {
	char path[512];
	snprintf(path, sizeof(path), "%s/%s.sav", directory, name);
	create_save(path);
	struct ChildResult result = run_load_save(path, 0);
	require(WIFEXITED(result.status) && WEXITSTATUS(result.status) == 0,
	        "successful savedata growth did not return normally");
	require(result.event_count == 3 && memcmp(result.events, "SRC", 3) == 0,
	        "successful growth did not truncate, return, and clean up once");
	require(file_is_initialized(path),
	        "successful growth did not produce the expected SRAM bytes");
	printf("PHASE1_POSIX_TRUNCATE_CASE %s caller_return=1 "
	       "truncate_events=SRC file_size=%u initial_byte=42 fill=FF "
	       "cleanup=original_GBAUnloadROM signal=none\n",
	       name, (unsigned) GBA_SIZE_SRAM);
	require(unlink(path) == 0, "remove successful savedata fixture");
}

static const char* errno_name(int value) {
	return value == ENOSPC ? "ENOSPC" : "EIO";
}

static void run_failure_case(const char* directory, const char* name,
                             int injected_errno) {
	char path[512];
	snprintf(path, sizeof(path), "%s/%s.sav", directory, name);
	create_save(path);
	struct ChildResult failed = run_load_save(path, injected_errno);
	require(WIFSIGNALED(failed.status) && WTERMSIG(failed.status) == SIGBUS,
	        "injected truncate failure did not produce isolated SIGBUS");
	require(failed.event_count == 1 &&
	        failed.events[0] == (injected_errno == ENOSPC ? 'N' : 'E'),
	        "expected exactly one injected truncate failure");
	printf("PHASE1_POSIX_TRUNCATE_CASE injected_%s caller_return=unreturned "
	       "truncate_events=%c signal=SIGBUS automatic_retry=0 "
	       "cleanup=child_process_exit\n",
	       errno_name(injected_errno), failed.events[0]);

	struct ChildResult recovered = run_load_save(path, 0);
	require(WIFEXITED(recovered.status) && WEXITSTATUS(recovered.status) == 0,
	        "savedata growth did not recover when truncate fault was removed");
	require(recovered.event_count == 3 &&
	        memcmp(recovered.events, "SRC", 3) == 0,
	        "recovery did not truncate, return, and clean up once");
	require(file_is_initialized(path),
	        "recovery did not produce the expected SRAM bytes");
	printf("PHASE1_POSIX_TRUNCATE_CASE recovery_after_%s caller_return=1 "
	       "truncate_events=SRC file_size=%u initial_byte=42 fill=FF "
	       "cleanup=original_GBAUnloadROM signal=none\n",
	       errno_name(injected_errno), (unsigned) GBA_SIZE_SRAM);
	require(unlink(path) == 0, "remove recovered savedata fixture");
}

int main(void) {
	char directory[] = "/tmp/xgba-posix-truncate-XXXXXX";
	require(mkdtemp(directory) != NULL, "create temporary directory");
	run_success_case(directory, "success");
	run_failure_case(directory, "eio", EIO);
	run_failure_case(directory, "enospc", ENOSPC);
	require(rmdir(directory) == 0, "remove temporary directory");
	puts("PHASE1_POSIX_TRUNCATE_DONE");
	return 0;
}
