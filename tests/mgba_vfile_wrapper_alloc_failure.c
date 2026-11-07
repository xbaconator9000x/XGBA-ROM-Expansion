/* Bounded witness for VFileMemChunk's wrapper-allocation failure path. */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <mgba-util/vfs.h>

#define MAX_WRAPPER_ALLOCATION 256
#define MAX_BACKING_ALLOCATION 8

static bool probe_active;
static bool fail_next_malloc;
static bool allocation_bound_exceeded;
static size_t last_malloc_size;
static unsigned malloc_calls;
static unsigned calloc_calls;
static unsigned free_calls;
static unsigned failed_mallocs;
static int failures;

void* __real_malloc(size_t size);
void* __real_calloc(size_t count, size_t size);
void __real_free(void* memory);

void* __wrap_malloc(size_t size) {
	if (!probe_active) {
		return __real_malloc(size);
	}
	last_malloc_size = size;
	++malloc_calls;
	if (size > MAX_WRAPPER_ALLOCATION) {
		allocation_bound_exceeded = true;
		return 0;
	}
	if (fail_next_malloc) {
		fail_next_malloc = false;
		++failed_mallocs;
		return 0;
	}
	return __real_malloc(size);
}

void* __wrap_calloc(size_t count, size_t size) {
	if (!probe_active) {
		return __real_calloc(count, size);
	}
	++calloc_calls;
	if (size && count > SIZE_MAX / size) {
		allocation_bound_exceeded = true;
		return 0;
	}
	if (count * size > MAX_BACKING_ALLOCATION) {
		allocation_bound_exceeded = true;
		return 0;
	}
	return __real_calloc(count, size);
}

void __wrap_free(void* memory) {
	if (probe_active && memory) {
		++free_calls;
	}
	__real_free(memory);
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
	fail_next_malloc = false;
	allocation_bound_exceeded = false;
	last_malloc_size = 0;
	malloc_calls = 0;
	calloc_calls = 0;
	free_calls = 0;
	failed_mallocs = 0;
}

static void end_probe(void) {
	probe_active = false;
	fail_next_malloc = false;
}

int main(void) {
	const uint8_t seed[4] = { 0x11, 0x22, 0x33, 0x44 };
	struct VFile* vf;
	void* mapped;
	bool copied;
	bool closed;
	bool within_bounds;
	unsigned positive_malloc_calls;
	unsigned positive_calloc_calls;
	unsigned positive_free_calls;
	unsigned failed_malloc_calls;
	unsigned failure_calloc_calls;
	unsigned failure_free_calls;
	size_t failed_wrapper_size;
	bool bounds_ok;

	puts("SCOPE original pinned memory.c and vfs-mem.c; synthetic malloc/calloc/free link wrappers; mCore caller not executed");

	begin_probe();
	vf = VFileMemChunk(seed, sizeof(seed));
	mapped = vf ? vf->map(vf, sizeof(seed), MAP_READ) : 0;
	copied = vf && mapped && !memcmp(mapped, seed, sizeof(seed));
	within_bounds = !allocation_bound_exceeded && last_malloc_size > 0
		&& last_malloc_size <= MAX_WRAPPER_ALLOCATION;
	closed = vf && vf->close(vf);
	positive_malloc_calls = malloc_calls;
	positive_calloc_calls = calloc_calls;
	positive_free_calls = free_calls;
	bounds_ok = !allocation_bound_exceeded;
	end_probe();
	check("positive constructor allocates bounded wrapper and backing, preserving input", copied
		&& within_bounds && positive_malloc_calls == 1 && positive_calloc_calls == 1);
	check("positive constructor close returns true and releases backing plus wrapper", closed
		&& positive_free_calls == 2 && bounds_ok);

	begin_probe();
	fail_next_malloc = true;
	vf = VFileMemChunk(seed, sizeof(seed));
	failed_wrapper_size = last_malloc_size;
	failed_malloc_calls = malloc_calls;
	failure_calloc_calls = calloc_calls;
	failure_free_calls = free_calls;
	bounds_ok = !allocation_bound_exceeded;
	end_probe();
	check("wrapper malloc failure returns null before backing allocation", vf == 0
		&& failed_mallocs == 1 && failed_malloc_calls == 1
		&& failure_calloc_calls == 0 && failed_wrapper_size > 0
		&& failed_wrapper_size <= MAX_WRAPPER_ALLOCATION && bounds_ok);
	check("failed constructor creates no VFile to close and releases no allocation", vf == 0
		&& failure_free_calls == 0);

	printf("SUMMARY assertions=%d failures=%d max_wrapper_allocation=%u max_backing_allocation=%u\n",
		4, failures, MAX_WRAPPER_ALLOCATION, MAX_BACKING_ALLOCATION);
	return failures ? 1 : 0;
}
