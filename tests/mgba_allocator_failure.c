/* Bounded allocation-failure probe for unchanged pinned mGBA sources.
 * The memcpy linker wrapper suppresses invalid copies after injected OOM.
 */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <mgba-util/vfs.h>

#define MAX_BACKING_ALLOCATION 8

static bool probe_active;
static bool fail_next_calloc;
static bool allocation_failed;
static bool allocation_bound_exceeded;
static size_t last_allocation_size;
static unsigned allocation_count;
static unsigned failed_allocations;
static unsigned suppressed_copies;
static int failures;

void* __real_calloc(size_t count, size_t size);
void* __real_memcpy(void* destination, const void* source, size_t size);

void* __wrap_calloc(size_t count, size_t size) {
	if (!probe_active) {
		return __real_calloc(count, size);
	}
	last_allocation_size = size && count > SIZE_MAX / size ? SIZE_MAX : count * size;
	++allocation_count;
	if (last_allocation_size > MAX_BACKING_ALLOCATION) {
		allocation_bound_exceeded = true;
		return 0;
	}
	if (fail_next_calloc) {
		fail_next_calloc = false;
		allocation_failed = true;
		++failed_allocations;
		return 0;
	}
	return __real_calloc(count, size);
}

void* __wrap_memcpy(void* destination, const void* source, size_t size) {
	if (probe_active && allocation_failed) {
		++suppressed_copies;
		return destination;
	}
	return __real_memcpy(destination, source, size);
}

ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size) {
	UNUSED(vf);
	UNUSED(buffer);
	UNUSED(size);
	return -1;
}

static void check(const char* label, bool condition) {
	printf("%s %s\n", condition ? "PASS" : "FAIL", label);
	if (!condition) {
		++failures;
	}
}

static void begin_probe(void) {
	probe_active = true;
	fail_next_calloc = false;
	allocation_failed = false;
	allocation_bound_exceeded = false;
	last_allocation_size = 0;
	allocation_count = 0;
	failed_allocations = 0;
	suppressed_copies = 0;
}

static void end_probe(void) {
	probe_active = false;
	fail_next_calloc = false;
	allocation_failed = false;
}

int main(void) {
	const uint8_t seed[5] = { 0x11, 0x22, 0x33, 0x44, 0x55 };
	const uint8_t tail = 0x66;
	struct VFile* vf;
	void* mapped;
	bool closed;

	puts("SCOPE original pinned memory.c and vfs-mem.c compiled unchanged; calloc/memcpy linker wrappers active");

	begin_probe();
	vf = VFileMemChunk(seed, sizeof(seed));
	mapped = vf ? vf->map(vf, sizeof(seed), MAP_READ) : 0;
	check("positive allocation copies five bytes into rounded eight-byte backing", vf && mapped
		&& !memcmp(mapped, seed, sizeof(seed)) && last_allocation_size == 8
		&& allocation_count == 1 && !allocation_bound_exceeded);
	closed = vf && vf->close(vf);
	check("positive allocation teardown returns true", closed);
	end_probe();

	begin_probe();
	fail_next_calloc = true;
	vf = VFileMemChunk(0, MAX_BACKING_ALLOCATION);
	mapped = vf ? vf->map(vf, MAX_BACKING_ALLOCATION, MAP_READ) : 0;
	check("backing allocation failure returns wrapper with null mapping", vf && !mapped
		&& failed_allocations == 1 && last_allocation_size == MAX_BACKING_ALLOCATION
		&& !allocation_bound_exceeded);
	closed = vf && vf->close(vf);
	check("null-backed wrapper teardown returns true", closed);
	end_probe();

	begin_probe();
	fail_next_calloc = true;
	vf = VFileMemChunk(seed, 4);
	mapped = vf ? vf->map(vf, 4, MAP_READ) : 0;
	check("failed initialization copy is intercepted and wrapper remains non-null", vf && !mapped
		&& failed_allocations == 1 && suppressed_copies == 1
		&& !allocation_bound_exceeded);
	closed = vf && vf->close(vf);
	check("failed initialization teardown returns true", closed);
	end_probe();

	vf = VFileMemChunk(seed, 4);
	if (!vf || vf->seek(vf, 4, SEEK_SET) != 4) {
		if (vf) {
			vf->close(vf);
		}
		puts("FAIL expansion probe setup");
		return 1;
	}
	begin_probe();
	fail_next_calloc = true;
	ssize_t written = vf->write(vf, &tail, sizeof(tail));
	mapped = vf->map(vf, 5, MAP_READ);
	check("failed expansion is masked by successful write count with null mapping", written == 1
		&& vf->size(vf) == 5 && !mapped && failed_allocations == 1
		&& last_allocation_size == MAX_BACKING_ALLOCATION && suppressed_copies == 2
		&& !allocation_bound_exceeded);
	closed = vf->close(vf);
	check("failed expansion teardown returns true", closed);
	end_probe();

	printf("SUMMARY assertions=%d failures=%d max_backing_allocation=%u\n",
		8, failures, MAX_BACKING_ALLOCATION);
	return failures ? 1 : 0;
}
